"""
Agent 执行器
统一管理所有 Agent 执行逻辑：消息组装、工具调用、流式输出、上下文管理
"""
import json
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, AsyncGenerator

from provider import BaseProvider
from provider.openai_provider import OpenAIProvider
from agent.conversation_store import ConversationContext
from agent.context_compressor import ContextManager
from agent.provider_select import ProviderSelectMixin
from memory import MemoryBridge
from persona.manager import PersonaManager
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class _SummaryPrompt:
    """对话总结 prompt 模板"""
    SYSTEM = """请将以下对话总结为关键要点，用于长期记忆。
目标：使后续检索时能准确回忆起这次对话的核心信息。

要求：
1. 提取用户表达的核心信息（偏好、需求、观点、经历等）
2. 提取 {persona_name} 回复中的重要知识或建议
3. 用简洁的中文描述，每条要点 1-2 句，保留关键实体信息（人名、地名、数字等）
4. 如果使用了工具，记录调用了什么工具以及关键结果，但**不要保留时效性数据**（如具体时间、日期）
5. 去除寒暄、重复等低价值内容
6. 输出格式：使用列表，每条以 "- " 开头

示例：
- 用户喜欢科幻小说，{persona_name} 推荐了阿西莫夫的作品
- 用户正在学习 Python 编程，{persona_name} 给出了基础语法指导
- 用户下周要去北京出差，{persona_name} 用天气工具查到了北京的天气情况"""


# 压缩提示词，可从 config.yaml 的 provider.compression_prompt 自定义
DEFAULT_COMPRESS_PROMPT = (
    "请将以下多轮对话压缩为一段简洁的摘要。\n"
    "目标：使后续对话能够无缝继续。\n\n"
    "要求：\n"
    "1. 覆盖讨论过的核心话题及最终结论，突出最新关注重点\n"
    "2. 如果使用了工具，只记录调用了哪些工具以及提取有价值的洞察，**不要保留工具的原始输出值**\n"
    "3. 如果有初始目标，说明当前进度/状态\n"
    "4. 去掉寒暄和重复内容，使用用户使用的语言\n"
    "5. 摘要需连贯可读，200字以内\n\n"
    "对话内容：\n{conversation_text}\n\n摘要："
)


class AgentRunner(ProviderSelectMixin):
    """Agent 执行器"""

    def __init__(
        self,
        provider: BaseProvider,
        context: ConversationContext,
        memory: MemoryBridge,
        persona_manager: PersonaManager,
        tool_registry: ToolRegistry,
        mcp_manager: Optional[Any] = None,
        skills_manager: Optional[Any] = None,
        config: Optional[dict] = None,
        max_rounds: int = 20,
        provider_manager: Optional[Any] = None,
        scheduler: Optional[Any] = None,  # 主动引擎调度器（AI自主通道用）
    ) -> None:
        self.provider = provider
        self.context = context
        self.memory = memory
        self.persona_manager = persona_manager
        self.tool_registry = tool_registry
        self.mcp_manager = mcp_manager
        self.skills_manager = skills_manager
        self.config = config or {}
        self.provider_manager = provider_manager
        self.scheduler = scheduler
        self.max_rounds = max_rounds
        self.max_context_tokens = (config or {}).get("provider", {}).get("max_context_tokens", 8000)
        
        # 上下文管理器（统一管理压缩和截断）
        self._round_count = 0  # 对话轮次计数器
        self._round_date = ""  # 计数器所属日期，跨天归零
        compression_cfg = (config or {}).get("provider", {})
        self.context_manager = ContextManager(
            max_context_tokens=self.max_context_tokens,
            max_turns=compression_cfg.get("max_turns", 100),
            compression_threshold=compression_cfg.get("compression_threshold", 0.82),
            compression_mode=compression_cfg.get("compression_mode", "summarize"),
            compression_strategy=compression_cfg.get("compression_strategy", "llm_summarize"),
            truncate_keep_turns=compression_cfg.get("truncate_keep_turns", 30),
            truncate_drop_turns=compression_cfg.get("truncate_drop_turns", 1),
            provider=self.provider,
        )
    
    def _bump_round_count(self) -> None:
        """当天总轮次计数 +1；日期变了先归零（闸门语义是当天累计，非按会话）"""
        today = time.strftime("%Y-%m-%d")
        if today != self._round_date:
            self._round_date = today
            self._round_count = 0
        self._round_count += 1

    # ─── 对话总结 ───

    async def _summarize_conversation(self, user_message: str, reply: str) -> str:
        """
        调用 LLM 总结对话要点
        
        Args:
            user_message: 用户消息
            reply: AI 回复
            
        Returns:
            str: 总结文本，如果无需总结则返回空字符串
        """
        try:
            # 快速判断：太短的对话不值得总结
            if len(user_message) < 10 and len(reply) < 30:
                return ""

            # 获取当前人格名称
            persona_name = self.persona_manager.active_name or "AI"
            summary_prompt = (
                f"{_SummaryPrompt.SYSTEM.format(persona_name=persona_name)}\n\n"
                f"用户消息：{user_message[:500]}\n\n"
                f"{persona_name}回复：{reply[:800]}\n\n"
                f"请提取对话要点："
            )

            resp = await self.provider.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.3,
                max_tokens=300,
            )

            summary = resp.get("content", "").strip()

            # 过滤空结果
            if not summary or len(summary) < 10:
                return ""

            logger.info(f"对话总结完成: {summary[:50]}...")
            return summary

        except Exception as e:
            logger.warning(f"对话总结失败: {e}")
            # 降级：使用原始用户消息作为记忆
            if len(user_message) >= 20:
                return user_message[:200]
            return ""

    # ─── Token 估算与上下文管理 ───




    # ─── 消息组装 ───

    async def build_messages(
        self,
        system_prompt: str,
        memories: List[Dict],
        session_id: str,
        persona_enabled: bool = True,
        agent_config: Optional[dict] = None,
    ) -> List[Dict]:
        """
        组装完整的消息列表（1条人格system + 记忆system + 预设对话 + 历史对话）

        Args:
            system_prompt: 系统提示词
            memories: 检索到的记忆
            session_id: 会话 ID
            persona_enabled: 是否启用人格
            agent_config: 子 Agent 配置（可选），传入时使用子 Agent 的人格/模型设定
        """
        messages = []

        # 1. 人格设定 + 当前时间 + 自主通道规则（合并）
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        persona_content = system_prompt + "\n当前时间：" + now + "（时区：CST 中国标准时间）"

        # V2.3: AI自主行动能力——自然语言表达，系统自动执行
        persona_content += (
            "\n\n【自主行动】你可以自由决定想做什么。"
            "如果需要查资料、读文件或做其他事情，直接在对话中自然地说出来，"
            "系统会自动帮你执行。不需要特殊格式，像和人聊天一样自然就好。"
        )
        messages.append({"role": "system", "content": persona_content})

        # 2. 历史记忆（你记得什么）—— 注入过滤
        if memories:
            ctx = "以下是之前的对话记忆，不反映当前状态。如果需要实时信息，请使用工具查询。\n"
            
            # 类型偏移表（偏好最重要门槛最低，查询最不重要门槛最高）
            TYPE_OFFSET = {
                "偏好": -0.08, "事实": -0.04, "状态":  0.00,
                "事件":  0.04, "查询":  0.08, "未知":  0.10,
            }
            
            # 检索总数因子：记忆越少门槛越低，让AI多回忆
            total = len(memories)
            if total <= 2:
                count_factor = 0.6
            elif total <= 5:
                count_factor = 0.8
            elif total <= 10:
                count_factor = 0.9
            else:
                count_factor = 1.0
            
            # 按动态阈值过滤并注入
            injected = 0
            for m in memories:
                rank = m.get("rank_score", 0)
                imp = m.get("importance", 0.5)
                mtype = m.get("memory_type", "未知")
                type_offset = TYPE_OFFSET.get(mtype, 0.10)
                
                # 动态阈值 = 基值 + 类型偏移 - 重要性权重 - rank权重 x 总数因子
                filter_threshold = (0.35 + type_offset - 0.15 * imp - 0.10 * rank) * count_factor
                filter_threshold = max(0.05, min(0.55, filter_threshold))
                
                if rank < filter_threshold:
                    continue
                
                # V4: 添加来源/时间/情感标记
                meta = m.get("metadata", {}) or {}
                source = m.get("_source", "inner")
                
                created_at = meta.get("created_at", m.get("created_at", 0))
                time_tag = ""
                if created_at:
                    import datetime as _dt
                    dt = _dt.datetime.fromtimestamp(created_at)
                    now = _dt.datetime.now()
                    if dt.date() == now.date():
                        time_tag = dt.strftime("今天%H:%M")
                    elif (now - dt).days == 1:
                        time_tag = "昨天" + dt.strftime("%H:%M")
                    else:
                        time_tag = dt.strftime("%m-%d")
                
                emotion_tag = meta.get("emotion_label_cn", "")
                if emotion_tag:
                    emotion_tag = "·" + emotion_tag
                
                if source == "cloud_activated":
                    source_tag = "[云中跃出"
                else:
                    source_tag = "[记忆"
                
                if time_tag:
                    source_tag += "·" + time_tag
                if emotion_tag:
                    source_tag += emotion_tag
                source_tag += "]"
                
                ctx += f"  {source_tag} {m.get('content', '')}\n"
                injected += 1
                if injected >= 5:
                    break
            
            # 保底：一条都没选上就取最好的1条
            if injected == 0 and memories:
                m0 = memories[0]
                meta0 = m0.get("metadata", {}) or {}
                source0 = m0.get("_source", "inner")
                ca0 = meta0.get("created_at", m0.get("created_at", 0))
                tt0 = ""
                if ca0:
                    import datetime as _dt2
                    dt0 = _dt2.datetime.fromtimestamp(ca0)
                    n0 = _dt2.datetime.now()
                    if dt0.date() == n0.date():
                        tt0 = dt0.strftime("今天%H:%M")
                    elif (n0 - dt0).days == 1:
                        tt0 = "昨天" + dt0.strftime("%H:%M")
                    else:
                        tt0 = dt0.strftime("%m-%d")
                et0 = meta0.get("emotion_label_cn", "")
                if et0:
                    et0 = "·" + et0
                st0 = "[云中跃出" if source0 == "cloud_activated" else "[记忆"
                if tt0:
                    st0 += "·" + tt0
                if et0:
                    st0 += et0
                st0 += "]"
                ctx += f"  {st0} {m0.get('content', '')}\n"
            
            messages.append({"role": "system", "content": ctx})

        # 3. 人格示例（你怎么说话）
        if persona_enabled:
            if agent_config and agent_config.get("persona_id"):
                persona = self.persona_manager.get_persona(agent_config["persona_id"])
            else:
                persona = self.persona_manager.get_active_persona()
            convs = persona.get("preset_conversations", [])
            if convs:
                lines = ["以下是对话风格示例，请参考这些示例的回复风格和语气："]
                for c in convs:
                    if "user" in c and "assistant" in c:
                        lines.append(f"用户: {c['user']}")
                        lines.append(f"你: {c['assistant']}")
                messages.append({"role": "system", "content": "\n".join(lines)})

        
        
        # 4. 历史对话
        # 普通消息频道：走正常get_history（受max_turns控制），额外注入摘要
        from api.push_messages import PUSH_CHANNEL_ID
        if session_id == PUSH_CHANNEL_ID:
            history = await self.context.get_history(session_id)
            # 注入历史摘要（分层：近的完整，远的精简，超5天跳过）
            try:
                summaries = await self._get_layered_summaries()
                for s in summaries:
                    messages.append({"role": "system", "content": s})
            except Exception:
                pass
        else:
            history = await self.context.get_history(session_id)
        
        for msg in history:
            role = msg["role"]
            if role in ("tool",):
                if msg.get("tool_call_id"):
                    messages.append({"role": "tool", "content": msg["content"], "tool_call_id": msg["tool_call_id"]})
                else:
                    messages.append({"role": "system", "content": f"[工具结果] {msg.get('content', '')}"})
            else:
                # 不再把reasoning_content拼入content，前端从reasoning字段独立读取
                # 给消息加上时间戳，让AI知道每条消息的发送时间
                _content = msg.get("content", "")
                _ts = msg.get("timestamp", 0)
                if _ts and role in ("user", "assistant"):
                    try:
                        from datetime import datetime as _dt
                        _time_str = _dt.fromtimestamp(_ts).strftime("%m-%d %H:%M")
                        _content = f"[{_time_str}] {_content}"
                    except Exception:
                        pass
                messages.append({"role": role, "content": _content})

        return messages

    
    async def _check_daily_compress(self):
        """检查昨天消息是否已压缩，未压缩则触发增量压缩（只存摘要，不删消息）"""
        try:
            from datetime import datetime, timezone, timedelta
            
            now = datetime.now(timezone.utc)
            today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            yesterday_start = today_start - timedelta(days=1)
            yesterday_end = today_start
            
            db = self.context.db
            
            # 查昨天是否有摘要
            yesterday_summaries = await db.get_push_messages_in_range(
                yesterday_start.timestamp(), yesterday_end.timestamp(),
                msg_type="daily_summary"
            )
            if yesterday_summaries:
                return  # 已有摘要，跳过
            
            # 查昨天的原始消息
            yesterday_msgs = await db.get_push_messages_in_range(
                yesterday_start.timestamp(), yesterday_end.timestamp(),
                msg_type="chat_reply"
            )
            if len(yesterday_msgs) < 3:
                return  # 消息太少，不值得压缩
            
            # 查今天的轮次，确认是否真的聊够了
            today_msgs = await db.get_push_messages_in_range(
                today_start.timestamp(), now.timestamp(),
                msg_type="chat_reply"
            )
            today_turns = sum(1 for m in today_msgs if m.get("role") == "user")
            if today_turns < 10:
                return  # 今天聊得还不够多
            
            logger.info(f"增量压缩: 昨天{len(yesterday_msgs)}条消息，今天{today_turns}轮")
            
            from active_engine.push_compressor import _generate_summary, _ts_to_date_str
            
            # 获取人格名称
            persona_name = "AI"
            try:
                p = self.persona_manager.get_active_persona()
                persona_name = p.get("name", "AI")
            except Exception:
                pass
            
            date_str = _ts_to_date_str(yesterday_start.timestamp())
            if not date_str:
                return
            
            # 所有消息都压缩，不保留（原始消息保留在push_messages表供展示）
            summary = await _generate_summary(yesterday_msgs, self.provider, date_str, persona_name)
            if not summary:
                return
            
            # 只存摘要，不删任何原始消息
            await db.add_push_message({
                "id": f"daily_summary_{date_str}",
                "role": "system",
                "content": summary,
                "type": "daily_summary",
                "priority": "normal",
                "source": "daily_compress",
                "created_at": yesterday_start.timestamp(),
            })
            logger.info(f"增量压缩: {date_str} 摘要已生成（原始消息全保留）")
            
            # 摘要滚动：超过10条删最早的
            from active_engine.push_compressor import _roll_summaries
            all_summaries = await db.get_push_messages_by_type("daily_summary")
            await _roll_summaries(db, all_summaries)
            
        except Exception as e:
            logger.warning(f"增量压缩失败（不影响主流程）: {e}")

    async def _get_layered_summaries(self) -> list:
        """获取分层摘要：最近1天完整，2~5天精简，超5天跳过"""
        try:
            db = self.context.db
            summaries = await db.get_push_messages_by_type("daily_summary")
            if not summaries:
                return []
            
            summaries.sort(key=lambda s: s.get("created_at", 0), reverse=True)
            
            now = time.time()
            result = []
            for s in summaries:
                ts = s.get("created_at", 0)
                days_ago = (now - ts) / 86400
                content = s.get("content", "")
                if not content:
                    continue
                
                if days_ago <= 1.5:
                    # 最近1天：完整注入
                    result.append(content)
                elif days_ago <= 5:
                    # 2~5天：精简到一句话（取第一句）
                    first_sentence = content.split("。")[0] + "。" if "。" in content else content[:60]
                    result.append(f"[历史] {first_sentence}")
                # 超过5天：跳过，不注入
            
            if result:
                logger.info(f"分层摘要: 注入 {len(result)} 条")
            return result
        except Exception as e:
            logger.warning(f"获取分层摘要失败: {e}")
            return []


    async def run(self, user_message: str, session_id: str) -> Dict[str, Any]:
        """非流式 Agent 执行"""
        await self.context.add_message(session_id, "user", user_message)

        recent = self.memory.get_recent(n=5)
        related = self.memory.query(user_message, top_k=3)
        memories = related if related else recent

        persona_enabled = self.config.get("persona", {}).get("enabled", True)
        sp = "你是一个有用的AI助手。"
        if persona_enabled:
            p = self.persona_manager.get_active_persona().get("prompt", "")
            if p:
                sp = p

        messages = await self.build_messages(sp, memories, session_id, persona_enabled)
        
        # 检查是否需要压缩上下文
        messages = await self.context_manager.process(messages)

        tools_used = []
        final_reply = ""
        reasoning_content = None
        pc = self.config.get("provider", {})

        for _ in range(self.max_rounds):
            messages = await self.context_manager.process(messages)
            
            # 刷新当前时间
            try:
                from datetime import datetime
                _now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                for _m in messages:
                    if _m["role"] == "system" and "当前时间" in str(_m.get("content", "")):
                        import re
                        _m["content"] = re.sub(
                            r'当前时间：[\d\-: ：]+',
                            f'当前时间：{_now_str}',
                            _m["content"]
                        )
                        break
            except Exception:
                pass
            
            available = self.tool_registry.get_tool_definitions()

            resp = await self.provider.chat(
                messages=messages,
                tools=available if available else None,
                temperature=pc.get("temperature", 0.7),
                max_tokens=pc.get("max_tokens", 4096),
                top_p=pc.get("top_p", 1.0),
                presence_penalty=pc.get("presence_penalty", 0.0),
                frequency_penalty=pc.get("frequency_penalty", 0.0),
            )

            content = resp.get("content", "")
            tcs = resp.get("tool_calls")
            reas = resp.get("reasoning_content")

            if reas and reasoning_content is None:
                reasoning_content = reas

            msg = {"role": "assistant", "content": content}
            if tcs:
                msg["tool_calls"] = tcs
            if reas:
                msg["reasoning_content"] = reas
            messages.append(msg)

            if not tcs:
                final_reply = content
                break

            async def exec_one(tc):
                name = tc.get("function", {}).get("name", "")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                r = await self.tool_registry.execute(name, args)
                return tc, name, args, r

            results = await asyncio.gather(*[exec_one(tc) for tc in tcs])
            for tc, name, args, result in results:
                tools_used.append({"name": name, "args": args, "result": str(result)[:200]})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(result)})
                await self.context.add_message(session_id, "system", f"[工具:{name}] {str(result)[:200]}")

        if final_reply:
            extra = {"reasoning_content": reasoning_content[:300]} if reasoning_content else {}
            await self.context.add_message(session_id, "assistant", final_reply, **extra)

            # 总结对话并存储长期记忆
            summary = await self._summarize_conversation(user_message, final_reply)
            if summary:
                self.memory.add("memory", summary, {
                    "session_id": session_id,
                    "user_message": user_message,  # 传用户原文给情感分析用
                })

        # 更新轮次计数器
        self._bump_round_count()

        # 检查是否需要增量压缩昨天消息
        from api.push_messages import PUSH_CHANNEL_ID
        if session_id == PUSH_CHANNEL_ID and self._round_count >= 10:
            asyncio.create_task(self._check_daily_compress())

        result = {"reply": final_reply, "memories_used": memories, "tools_used": tools_used}
        if self.config.get("features", {}).get("keep_thinking") and reasoning_content:
            result["reasoning"] = reasoning_content

        # 解析AI回复中的自主意图（AI自主通道）
        if self.scheduler and final_reply:
            self._parse_and_execute_intents(final_reply, session_id)

        return result

    def _parse_and_execute_intents(self, reply: str, session_id: str):
        """V2.3: AI自主意图已在自然对话中通过工具调用完成，不再需要JSON解析"""
        # V2.3: AI在自然对话中表达意图，工具调用通过正常API tools参数执行
        # AI说"让我查一下"就会触发工具调用，结果自动回到AI手中
        # 不再需要 {"_intents": [...]} 格式
        pass

    # ─── 流式执行 ───

    async def run_stream(
        self, user_message: str, session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式 Agent 执行，每次 yield 一个事件"""
        all_tools_used = []
        persona_enabled = self.config.get("persona", {}).get("enabled", True)
        sp = "你是一个有用的AI助手。"
        if persona_enabled:
            p = self.persona_manager.get_active_persona().get("prompt", "")
            if p:
                sp = p

        recent = self.memory.get_recent(n=5)
        related = self.memory.query(user_message, top_k=3)
        memories = related if related else recent

        messages = await self.build_messages(sp, memories, session_id, persona_enabled)
        messages.append({"role": "user", "content": user_message})
        
        # 检查是否需要压缩上下文
        messages = await self.context_manager.process(messages)

        final_reply = ""
        final_reasoning = None
        round_text = ""
        round_reasoning = None

        for round_idx in range(self.max_rounds):
            messages = await self.context_manager.process(messages)
            available = self.tool_registry.get_tool_definitions()
            logger.info(f"流式第 {round_idx+1} 轮, 消息数: {len(messages)}")
            
            # 每轮刷新当前时间，让AI知道最新时间
            try:
                from datetime import datetime
                _now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                for _m in messages:
                    if _m["role"] == "system" and "当前时间" in str(_m.get("content", "")):
                        import re
                        _m["content"] = re.sub(
                            r'当前时间：[\d\-: ：]+',
                            f'当前时间：{_now_str}',
                            _m["content"]
                        )
                        break
            except Exception:
                pass

            round_text = ""
            round_reasoning = None
            round_tc = None

            try:
                async for ev in self.provider.chat_stream(
                    messages=messages,
                    tools=available if available else None,
                    temperature=self.config.get("provider", {}).get("temperature", 0.7),
                    max_tokens=self.config.get("provider", {}).get("max_tokens", 4096),
                ):
                    if ev["type"] == "text":
                        round_text += ev["content"]
                        yield ev
                    elif ev["type"] == "reasoning":
                        round_reasoning = (round_reasoning or "") + ev["content"]
                        yield ev
                    elif ev["type"] == "done":
                        round_text = ev.get("content", round_text)
                        round_reasoning = ev.get("reasoning_content", round_reasoning)
                        round_tc = ev.get("tool_calls")
            except Exception as e:
                logger.error(f"流式失败，回退非流式: {e}")
                import traceback
                logger.error(traceback.format_exc())
                result = await self.provider.chat(messages=messages, tools=available if available else None)
                round_text = result.get("content", "")
                round_reasoning = result.get("reasoning_content")
                round_tc = result.get("tool_calls")
                yield {"type": "text", "content": round_text}

            msg = {"role": "assistant", "content": round_text}
            if round_tc:
                msg["tool_calls"] = round_tc
            if round_reasoning:
                msg["reasoning_content"] = round_reasoning
            messages.append(msg)

            if not round_tc:
                final_reply = round_text
                final_reasoning = round_reasoning
                break

            async def exec_one(tc):
                name = tc.get("function", {}).get("name", "")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                r = await self.tool_registry.execute(name, args)
                return tc, name, args, r

            exec_results = await asyncio.gather(*[exec_one(tc) for tc in round_tc])
            for tc, name, args, result in exec_results:
                all_tools_used.append({"name": name, "args": args})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": str(result)})
                await self.context.add_message(session_id, "tool", f"[{name}] {str(result)[:200]}")
                yield {"type": "tool_used", "name": name, "args": args, "result": str(result)[:300]}
        else:
            final_reply = round_text
            final_reasoning = round_reasoning

        if final_reply:
            await self.context.add_message(session_id, "user", user_message)
            extra = {"reasoning_content": final_reasoning[:300]} if final_reasoning else {}
            await self.context.add_message(session_id, "assistant", final_reply, **extra)

            # 总结对话并存储长期记忆
            summary = await self._summarize_conversation(user_message, final_reply)
            if summary:
                self.memory.add("memory", summary, {
                    "session_id": session_id,
                    "user_message": user_message,
                })
        else:
            # 即使没有 final_reply，也保存用户消息
            await self.context.add_message(session_id, "user", user_message)

        # 更新轮次计数器
        self._bump_round_count()

        # 检查是否需要增量压缩昨天消息（普通消息频道，今天聊够10轮后触发）
        from api.push_messages import PUSH_CHANNEL_ID
        if session_id == PUSH_CHANNEL_ID and self._round_count >= 10:
            asyncio.create_task(self._check_daily_compress())

        # 解析AI回复中的自主意图（流式版）
        if self.scheduler and final_reply:
            self._parse_and_execute_intents(final_reply, session_id)

        yield {
            "type": "done",
            "reply": final_reply,
            "reasoning": final_reasoning,
            "tools_used": all_tools_used,
            "memories_used": memories,
        }
