"""
子 Agent 执行器
负责根据 Agent 配置驱动 LLM 执行任务，拥有独立会话和上下文
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SubAgentExecutor:
    """
    子 Agent 执行器

    每个子 Agent 拥有：
    - 独立的 provider（根据 model_id 自动匹配）
    - 独立的 SQLite 会话（上下文隔离）
    - 独立的人格设定
    - 独立的工具列表

    使用方式：
        executor = SubAgentExecutor(
            agent_config=agent_config,
            task_description="用Vue搭建前端框架",
            workspace_id="...",
            provider_manager=provider_manager,
            context=context,
            memory=memory_selector,
            persona_manager=persona_manager,
            tool_registry=tool_registry,
            workspace_manager=ws_manager,
        )
        result = await executor.run()
    """

    def __init__(
        self,
        agent_config: dict,
        task_description: str,
        workspace_id: str,
        provider_manager=None,
        context=None,
        memory=None,
        persona_manager=None,
        tool_registry=None,
        workspace_manager=None,
        main_config: Optional[dict] = None,
    ):
        self.agent_config = agent_config
        self.task_description = task_description
        self.workspace_id = workspace_id
        self.provider_manager = provider_manager
        self.context = context
        self.memory = memory
        self.persona_manager = persona_manager
        self.tool_registry = tool_registry
        self.workspace_manager = workspace_manager
        self.main_config = main_config or {}

        # 为每个子 Agent 创建独立的长期记忆（namespace 隔离）
        from memory.backends.simple import SimpleMemory
        agent_name = self.agent_config.get("name", "unknown")
        self._agent_memory = SimpleMemory(namespace=f"agent_{agent_name}")

        # 生成的会话 ID（run 后可用）
        self.session_id: Optional[str] = None
        self.result_summary: str = ""

    async def run(self) -> Dict[str, Any]:
        """
        执行子 Agent 任务

        Returns:
            {"success": bool, "reply": str, "session_id": str, "summary": str}
        """
        agent_name = self.agent_config.get("name", "unknown")
        if self.context:
            db_path = getattr(getattr(self.context, "db", None), "db_path", "unknown")
            logger.info(f"子 Agent [{agent_name}] 使用数据库: {db_path}")
        logger.info(f"子 Agent [{agent_name}] 开始执行任务: {self.task_description[:50]}...")

        # 1. 获取对应的 provider
        provider = self._get_provider()
        if not provider:
            return {"success": False, "reply": "无法获取模型提供商", "session_id": "", "summary": ""}

        # 2. 创建工作空间内的独立会话
        self.session_id = await self._create_session()
        if not self.session_id:
            return {"success": False, "reply": "创建会话失败", "session_id": "", "summary": ""}

        # 3. 更新工作空间中的 Agent 状态
        await self._update_status("working", f"正在执行: {self.task_description[:30]}...")

        try:
            # 4. 构建 system prompt（使用 Agent 自身的人格）
            system_prompt = self._build_system_prompt()

            # 5. 准备消息
            messages = [{"role": "system", "content": system_prompt}]
            messages.append({"role": "user", "content": self.task_description})

            # 6. 查询长期记忆，注入经验到 system prompt
            try:
                past_memories = self._agent_memory.query(self.task_description, top_k=3)
                if past_memories:
                    memory_text = "\n".join([f"- {m.get('content', '')}" for m in past_memories])
                    messages[0]["content"] += f"\n\n【你的经验】\n根据以往的经验，你可能需要参考以下信息：\n{memory_text}"
                    logger.info(f"子 Agent [{agent_name}] 注入了 {len(past_memories)} 条历史记忆")
            except Exception as e:
                logger.warning(f"查询子 Agent 记忆失败: {e}")

            # 7. 保存用户消息到会话
            if self.context:
                await self.context.add_message(self.session_id, "user", self.task_description)

            # 8. 执行多轮对话（工具调用循环）
            max_rounds = self.main_config.get("tools", {}).get("max_agent_rounds", 20)
            final_reply = ""
            tools_used = []

            circuit_breaker_tripped = False
            for round_num in range(max_rounds):
                # 获取可用工具（Agent 专属工具列表）
                available_tools = self._get_tools()

                # 服务熔断：捕获 provider 调用异常，避免崩溃
                try:
                    resp = await provider.chat(
                        messages=messages,
                        tools=available_tools if available_tools else None,
                        temperature=self.agent_config.get("temperature", 0.7),
                        max_tokens=self.agent_config.get("max_tokens", 4096),
                    )
                except Exception as e:
                    logger.error(f"子 Agent [{agent_name}] Provider 调用失败 (第{round_num+1}轮): {e}")
                    circuit_breaker_tripped = True
                    if round_num == 0:
                        final_reply = f"抱歉，我在调用模型时遇到问题: {str(e)[:100]}"
                    else:
                        final_reply = final_reply + f"\n[后续执行中断，模型调用失败: {str(e)[:50]}]"
                    break

                content = resp.get("content", "")
                tool_calls = resp.get("tool_calls")

                msg = {"role": "assistant", "content": content}
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                messages.append(msg)

                # 保存 assistant 消息
                if self.context:
                    await self.context.add_message(self.session_id, "assistant", content)

                if circuit_breaker_tripped:
                    break
                if not tool_calls:
                    final_reply = content
                    break

                # 执行工具调用
                for tc in tool_calls:
                    name = tc.get("function", {}).get("name", "")
                    args_str = tc.get("function", {}).get("arguments", "{}")
                    import json
                    try:
                        args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        args = {}

                    tools_used.append(name)

                    if self.tool_registry:
                        result = await self.tool_registry.execute(name, args)
                    else:
                        result = f"工具 {name} 不可用"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": str(result)[:1000],
                    })

                if round_num < max_rounds - 1:
                    await self._update_status("working", f"第 {round_num+1} 轮完成，继续...")

            # 9. 保存最终结果
            if final_reply and self.context:
                await self.context.add_message(self.session_id, "assistant", final_reply)

            self.result_summary = final_reply[:200] if final_reply else "无输出"

            # 10. 更新工作空间状态
            await self._update_status("done", self.result_summary)

            # 11. 总结并保存到独立长期记忆（用 Agent 自己的模型总结）
            if final_reply:
                try:
                    summary_prompt = f"请将以下任务执行过程总结为1-2句关键要点，用于长期记忆：\n\n任务: {self.task_description}\n执行结果: {final_reply[:500]}"
                    summary_resp = await provider.chat(
                        messages=[{"role": "user", "content": summary_prompt}],
                        temperature=0.3,
                        max_tokens=200,
                    )
                    summary = summary_resp.get("content", "").strip()
                    if not summary or len(summary) < 5:
                        summary = f"任务: {self.task_description[:60]} | 结果: {final_reply[:80]}"
                except Exception:
                    summary = f"任务: {self.task_description[:60]} | 结果: {final_reply[:80]}"
                
                self._agent_memory.add("assistant", summary, {
                    "agent": agent_name,
                    "workspace_id": self.workspace_id,
                    "task": self.task_description,
                })
                logger.info(f"子 Agent [{agent_name}] 记忆已保存: {summary[:60]}...")

            logger.info(f"子 Agent [{agent_name}] 任务完成，使用了 {len(tools_used)} 个工具")
            return {
                "success": True,
                "reply": final_reply,
                "session_id": self.session_id,
                "summary": self.result_summary,
                "tools_used": tools_used,
            }

        except Exception as e:
            logger.error(f"子 Agent [{agent_name}] 执行失败: {e}")
            await self._update_status("failed", f"错误: {str(e)[:100]}")
            return {
                "success": False,
                "reply": f"执行出错: {str(e)}",
                "session_id": self.session_id or "",
                "summary": f"失败: {str(e)[:50]}",
            }

    # ─── 内部方法 ───

    def _get_provider(self):
        """获取适合此 Agent 的 provider"""
        if self.provider_manager:
            return self.provider_manager.get_provider_for_agent(self.agent_config)
        return None

    def _build_system_prompt(self) -> str:
        """构建 Agent 的 system prompt"""
        parts = []

        # Agent 自身的人格
        persona_id = self.agent_config.get("persona_id", "")
        if persona_id and self.persona_manager:
            persona = self.persona_manager.get_persona(persona_id)
            if persona and persona.get("prompt"):
                parts.append(persona["prompt"])

        if not parts:
            parts.append(f"你是 {self.agent_config.get('display_name', self.agent_config.get('name', '助手'))}，一个AI助手。")

        # 任务上下文
        parts.append(f"\n你正在参与项目工作，负责以下任务：\n{self.task_description}")

        # 工具说明
        tools = self.agent_config.get("tools_enabled", [])
        if tools:
            parts.append(f"\n你可以使用以下工具：{', '.join(tools)}")

        return "\n\n".join(parts)

    def _get_tools(self) -> list:
        """获取 Agent 专属的可用工具列表"""
        if not self.tool_registry:
            return []

        all_defs = self.tool_registry.get_tool_definitions()
        enabled_tools = self.agent_config.get("tools_enabled", [])

        if not enabled_tools:
            return all_defs  # 没配置就全用

        return [
            d for d in all_defs
            if d.get("function", {}).get("name", "") in enabled_tools
            or d.get("function", {}).get("name", "").lower() in [t.lower() for t in enabled_tools]
        ]

    async def _create_session(self) -> Optional[str]:
        """获取或创建工作空间内子 Agent 的独立会话（复用已有的）"""
        if not self.context:
            return None

        agent_name = self.agent_config.get("name", "agent")

        # 1. 先看工作空间是否已有该 Agent 的会话
        if self.workspace_manager and self.workspace_id:
            existing = self.workspace_manager.get_agent_session(
                self.workspace_id, agent_name
            )
            if existing:
                # 验证会话是否还存在
                sessions = await self.context.list_sessions()
                if any(s.get("id") == existing for s in sessions):
                    logger.info(f"子 Agent [{agent_name}] 复用已有会话: {existing}")
                    return existing

        # 2. 没有则创建新会话
        session_name = f"[{agent_name}] {self.task_description[:30]}"
        try:
            session_id = await self.context.create_session(name=session_name)
            logger.info(f"子 Agent [{agent_name}] 创建新会话: {session_id}")

            # 关联到工作空间
            if self.workspace_manager and self.workspace_id:
                self.workspace_manager.set_agent_session(
                    self.workspace_id, agent_name, session_id
                )

            return session_id
        except Exception as e:
            logger.error(f"创建子 Agent 会话失败: {e}")
            return None

    async def _update_status(self, status: str, progress: str = ""):
        """更新工作空间中此 Agent 的状态"""
        if not self.workspace_manager or not self.workspace_id:
            return
        agent_name = self.agent_config.get("name", "")
        if agent_name:
            self.workspace_manager.update_agent_status(
                self.workspace_id, agent_name, status, progress
            )
