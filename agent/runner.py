"""
Agent 执行器
统一管理所有 Agent 执行逻辑：消息组装、工具调用、流式输出、上下文管理
"""
import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator

from provider import BaseProvider
from provider.openai_provider import OpenAIProvider
from agent.conversation_store import ConversationContext
from agent.context_builder import ContextBuilderMixin
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


class AgentRunner(ContextBuilderMixin, ProviderSelectMixin):
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
