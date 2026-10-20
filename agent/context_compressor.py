"""
上下文管理器
两阶段策略：
  阶段一：硬性轮次截断（保留最近N轮对话）
  阶段二：按 token 占比触发压缩（超过82%触发）
参考：AstrBot ContextManager + Anthropic Context Engineering
"""
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContextManager:
    """统一上下文管理器"""

    def __init__(
        self,
        max_context_tokens: int = 8000,
        max_turns: int = 50,
        compression_threshold: float = 0.82,
        compression_mode: str = "summarize",
        compression_strategy: str = "llm_summarize",
        truncate_keep_turns: int = 30,
        truncate_drop_turns: int = 1,
        provider=None,
        compression_prompt: str = None,
    ):
        """
        Args:
            max_context_tokens: token 上限
            max_turns: 硬性保留的对话轮数上限（-1 表示不限）
            compression_threshold: 触发压缩的 token 占比（默认 82%）
            compression_mode: 压缩模式（truncate / summarize），llm_summarize策略下生效
            compression_strategy: 压缩策略（llm_summarize / truncate）
            truncate_keep_turns: truncate策略下保留的轮数
            truncate_drop_turns: truncate策略下每次丢弃的轮数
            provider: LLM 提供商（llm_summarize策略需要）
            compression_prompt: 自定义压缩提示词
        """
        self.max_context_tokens = max_context_tokens
        self.max_turns = max_turns
        self.compression_threshold = compression_threshold
        self.compression_mode = compression_mode
        self.compression_strategy = compression_strategy
        self.truncate_keep_turns = truncate_keep_turns
        self.truncate_drop_turns = truncate_drop_turns
        self.provider = provider
        self.compression_prompt = compression_prompt or DEFAULT_COMPRESS_PROMPT

    # ─── 外部入口 ───

    async def process(
        self, messages: List[Dict], trusted_token_usage: int = 0
    ) -> List[Dict]:
        """处理消息列表：先截断再压缩

        Args:
            messages: 原始消息列表
            trusted_token_usage: 已知的 token 消耗（如流式已用量）

        Returns:
            处理后的消息列表
        """
        # 阶段一：硬性轮次截断
        if self.max_turns > 0:
            messages = self._truncate_by_turns(messages)

        # 阶段二：按 token 占比触发压缩
        if self.max_context_tokens > 0:
            total = self._estimate_messages_tokens(messages)
            total += trusted_token_usage

            if total > 0 and total / self.max_context_tokens > self.compression_threshold:
                logger.info(
                    f"上下文超限: {total}/{self.max_context_tokens} "
                    f"({total/self.max_context_tokens:.1%})，触发压缩"
                )

                if self.compression_strategy == "truncate":
                    # 截断策略：一直丢到不超限为止
                    while True:
                        messages = self._truncate_by_dropping_n_turns(messages)
                        total = self._estimate_messages_tokens(messages)
                        if total / self.max_context_tokens <= self.compression_threshold:
                            break
                        if len([m for m in messages if m["role"] != "system"]) <= 2:
                            break
                elif self.compression_mode == "summarize" and self.provider:
                    messages = await self._llm_compress(messages)
                else:
                    messages = self._truncate_by_dropping_oldest(messages)

        return messages

    # ─── 阶段一：硬性轮次截断 ───

    def _truncate_by_turns(self, messages: List[Dict]) -> List[Dict]:
        """保留最近的 N 轮对话，删掉最旧的"""
        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        # 按 user-assistant 成对保留
        # 一轮 = 1条user + 1条assistant（中间可能夹tool消息）
        turns_to_keep = self.max_turns * 2
        if len(non_system) <= turns_to_keep:
            return messages

        # 从尾部往前保留
        kept = non_system[-turns_to_keep:]

        # 确保第一条非 system 消息是 user（很多 API 要求）
        if kept and kept[0]["role"] != "user":
            # 找到原来的第一条 user 消息补上
            first_user = next(
                (m for m in non_system if m["role"] == "user"),
                None
            )
            if first_user:
                kept = [first_user] + kept

        logger.info(
            f"轮次截断: {len(non_system)//2}轮 -> {len(kept)//2+1}轮 "
            f"(system {len(system_msgs)}条)"
        )
        return system_msgs + kept

    # ─── 阶段二：token 压缩 ───

    def _truncate_by_dropping_n_turns(self, messages: List[Dict]) -> List[Dict]:
        """根据 truncate_drop_turns 删掉最旧的 N 轮对话"""
        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]
        
        turns_to_drop = self.truncate_drop_turns
        if turns_to_drop <= 0:
            turns_to_drop = 1
        
        # 一轮 = 1条user + 1条assistant（中间可能夹tool消息）
        msgs_to_drop = turns_to_drop * 2
        if len(non_system) <= msgs_to_drop:
            # 不够丢的，只保留最后1轮
            kept = non_system[-(turns_to_drop * 2):] if len(non_system) > 2 else non_system
        else:
            kept = non_system[msgs_to_drop:]
        
        # 确保第一条是 user
        if kept and kept[0]["role"] != "user":
            first_user = next((m for m in non_system if m["role"] == "user"), None)
            if first_user:
                kept = [first_user] + kept
        
        logger.info(f"截断策略: 丢弃 {msgs_to_drop} 条 ({turns_to_drop}轮)，剩余 {len(kept)} 条")
        return system_msgs + kept

    def _truncate_by_dropping_oldest(self, messages: List[Dict]) -> List[Dict]:
        """删掉最旧的 1 轮对话"""
        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        if len(non_system) <= 2:
            return system_msgs + non_system

        # 找到第一轮 user-assistant 对的末尾
        first_user = next(
            (i for i, m in enumerate(non_system) if m["role"] == "user"),
            None
        )
        if first_user is None:
            return system_msgs + non_system

        # 找到这一轮的结束（下一条 user 或末尾）
        next_user = next(
            (i for i in range(first_user + 1, len(non_system))
             if non_system[i]["role"] == "user"),
            len(non_system)
        )

        dropped = non_system[:next_user]
        kept = non_system[next_user:]

        logger.info(f"删轮次压缩: 删除了 {len(dropped)} 条消息（1轮）")
        return system_msgs + kept

    async def _llm_compress(self, messages: List[Dict]) -> List[Dict]:
        """用 LLM 总结旧对话"""
        if not self.provider:
            logger.warning("LLM 压缩不可用（无 provider），退回到删轮次")
            return self._truncate_by_dropping_oldest(messages)

        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]

        if len(non_system) < 4:
            return messages

        # 保留最近的 15% 对话原样
        keep_ratio = 0.15
        keep_count = max(2, int(len(non_system) * keep_ratio))
        to_summarize = non_system[:-keep_count]
        recent_kept = non_system[-keep_count:]

        if not to_summarize:
            return system_msgs + recent_kept

        # 构建对话文本
        conversation_text = ""
        for msg in to_summarize:
            role = msg["role"]
            content = msg.get("content", "")
            if role == "tool":
                conversation_text += f"[工具结果]: {content}\n"
            elif role == "assistant":
                conversation_text += f"AI: {content}\n"
            else:
                conversation_text += f"用户: {content}\n"

        conversation_text = conversation_text[:6000]

        try:
            prompt = self.compression_prompt.format(
                conversation_text=conversation_text
            )

            resp = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            summary = resp.get("content", "").strip()

            if not summary or len(summary) < 10:
                logger.warning("LLM 压缩结果为空，跳过")
                return messages

            logger.info(f"LLM 压缩完成: {summary[:50]}...")

            # 返回：system + 摘要(user-assistant对) + 保留的近几轮
            summary_user = {
                "role": "user",
                "content": f"我们之前对话的历史摘要：{summary}"
            }
            summary_asst = {
                "role": "assistant",
                "content": "已确认。"
            }
            return system_msgs + [summary_user, summary_asst] + recent_kept

        except Exception as e:
            logger.warning(f"LLM 压缩失败: {e}")
            return messages

    # ─── token 估算 ───

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算文本 token 数"""
        if not text:
            return 0
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other = len(text) - chinese
        return int(chinese / 1.5 + other / 4)

    def _estimate_messages_tokens(self, messages: List[Dict]) -> int:
        """估算消息列表的 token 总数"""
        total = 0
        for msg in messages:
            total += self._estimate_tokens(msg.get("content", ""))
            total += self._estimate_tokens(
                json.dumps(msg.get("tool_calls", ""))
            )
            total += 10  # 每条消息的固定开销
        return total


# ─── 默认压缩提示词 ───

DEFAULT_COMPRESS_PROMPT = (
    "请将以下对话历史压缩为简洁的摘要，用于后续检索。\n"
    "要求：\n"
    "1. 保留用户的核心需求、偏好、关键决策和重要结论\n"
    "2. 如果使用了工具，只记录调用了哪些工具以及提取有价值的洞察，"
    "**不要保留工具的原始输出值**\n"
    "3. 用中文输出，保持客观\n\n"
    "对话历史：\n{conversation_text}\n\n"
    "摘要："
)
