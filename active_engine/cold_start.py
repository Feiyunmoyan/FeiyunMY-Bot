"""
冷启动问候模块
启动时 AI 主动打招呼，带自适应输出长度算法
"""
import logging
import time
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ColdStarter:
    """冷启动问候器"""

    def __init__(self, provider, memory=None, persona_manager=None, db=None):
        """
        Args:
            provider: LLM provider 实例
            memory: 记忆选择器（可选）
            persona_manager: 人格管理器（可选）
            db: 数据库实例（可选），用于查普通消息最近上下文
        """
        self.provider = provider
        self.memory = memory
        self.persona_manager = persona_manager
        self.db = db  # 用于查普通消息最近上下文

        # 自适应输出长度（根据截断情况动态调整）
        self._adaptive_max_tokens = 230       # 当前输出上限（初始宽裕）
        self._adaptive_min_tokens = 80        # 最低
        self._adaptive_max_tokens_limit = 500 # 最高
        self._complete_count = 0              # 连续完整句次数
        self._token_history = []              # 滑动窗口：完整句子时的 max_tokens

    async def try_greet(self, push_callback: Callable):
        """
        尝试生成并推送冷启动问候（三层记忆注入）

        Args:
            push_callback: 推送回调函数，接收 content 字符串参数
        """
        if not self.provider:
            return

        # 0. 防重复推送：检测最近2小时内是否有冷启动问候
        try:
            if self.db:
                last_greet = await self.db.get_config("last_cold_start_time")
                if last_greet and time.time() - float(last_greet) < 7200:
                    logger.info(f"冷启动跳过：2小时内已问候过")
                    return
        except Exception:
            pass

        # 1. 读取人格设定
        persona_name = "绯璃"
        persona_prompt = ""
        if self.persona_manager:
            try:
                p = self.persona_manager.get_active_persona()
                persona_prompt = str(p.get("prompt", ""))
                persona_name = p.get("name", "绯璃")
            except Exception:
                pass

        sys_content = f"{persona_prompt}\n\n你是{persona_name}，正在开始一段新的对话。\n\n"

        # 2. 三层记忆注入（总量控制在 200 tokens 以内）
        memory_lines = []
        used_contents = set()  # 去重

        # 2-1. 第一层：语义检索长期记忆（最相关的 2 条）
        try:
            if self.memory:
                related = self.memory.query("打招呼问候", top_k=3)
                for m in related:
                    content = m.get("content", "").strip()
                    if not content or content in used_contents:
                        continue
                    # 时间衰减：超过3天的降权
                    created_at = m.get("created_at", 0)
                    if created_at and time.time() - created_at > 259200:  # 3天
                        continue
                    memory_lines.append(f"  记忆：{content[:80]}")
                    used_contents.add(content)
                    if len(memory_lines) >= 2:
                        break
        except Exception:
            pass

        # 2-2. 第二层：普通消息最近上下文（最近 3 条）
        try:
            if self.db:
                recent_push = await self.db.list_push_messages(page=1, page_size=5)
                push_items = recent_push.get("items", [])
                # 取最新的 3 条（非用户消息优先）
                push_texts = []
                for item in reversed(push_items):
                    role = item.get("role", "")
                    content = item.get("content", "").strip()
                    if not content or content in used_contents:
                        continue
                    prefix = "你" if role == "assistant" else "用户"
                    push_texts.append(f"  {prefix}说：{content[:80]}")
                    used_contents.add(content)
                    if len(push_texts) >= 3:
                        break
                if push_texts:
                    memory_lines.append("")
                    memory_lines.append("  最近在聊：")
                    memory_lines.extend(push_texts)
        except Exception:
            pass

        # 2-3. 第三层：全局长期记忆兜底（最近 1 条，仅当没有其他记忆时）
        if not memory_lines:
            try:
                recent = self.memory.get_recent(n=3) if self.memory else []
                for m in recent:
                    content = m.get("content", "").strip()
                    if not content or content in used_contents:
                        continue
                    memory_lines.append(f"  印象：{content[:80]}")
                    used_contents.add(content)
                    break
            except Exception:
                pass

        # 3. 拼入 system prompt，带引导语
        if memory_lines:
            sys_content += "以下是可以参考的信息，自然地融入问候，不要一一列举：\n"
            sys_content += "\n".join(memory_lines)
            # 情感判断：从记忆元数据中提取 VAD 情感坐标
            # 第一层记忆（语义检索）和第三层记忆（兜底）都带有 VAD 元数据
            vad_sum = {"v": 0, "a": 0, "d": 0}
            vad_count = 0
            try:
                if self.memory:
                    # 收集最近记忆的情感数据
                    recent_mems = self.memory.get_recent(n=5) if hasattr(self.memory, 'get_recent') else []
                    for m in recent_mems:
                        meta = m.get("metadata", {}) or {}
                        v = meta.get("v")
                        a = meta.get("a")
                        d = meta.get("d")
                        if v is not None and a is not None and d is not None:
                            vad_sum["v"] += v
                            vad_sum["a"] += a
                            vad_sum["d"] += d
                            vad_count += 1
            except Exception:
                pass

            if vad_count > 0:
                avg_v = vad_sum["v"] / vad_count
                avg_a = vad_sum["a"] / vad_count
                if avg_v < -0.2:
                    guidance = "\n\n对方最近情绪不太好，自然地关心一下就好。"
                elif avg_v > 0.2:
                    guidance = "\n\n对方最近心情不错，可以顺着开心的话题聊。"
                elif avg_a > 0.5:
                    guidance = "\n\n对方最近情绪波动较大，温和地回应就好。"
                else:
                    guidance = "\n\n自然地打个招呼，顺着话题聊下去就好。"
            else:
                # 没有 VAD 数据时用中性提示
                guidance = "\n\n自然地打个招呼，顺着话题聊下去就好。"

            sys_content += guidance
        else:
            sys_content += "自然地和用户打个招呼就好。"

        # 4. 自适应算法生成问候语
        content = await self._generate_with_adaptive(sys_content)

        # 5. 推送
        if content and len(content) > 5:
            logger.info(f"冷启动问候: {content[:40]}...")
            push_callback(content)
            # 记录冷启动时间，防止重复问候
            try:
                if self.db:
                    await self.db.set_config("last_cold_start_time", str(time.time()))
            except Exception:
                pass

    async def _generate_with_adaptive(self, sys_content: str) -> str:
        """
        自适应长度生成：滑动窗口 + 完成率估算 + 重试 + 上下调整

        算法说明：
        - 基准值 = 滑动窗口平均（最近10次完整输出）
        - 最多3次尝试（首次 + 2次重试）
        - 被截断时按完成率估算完整长度重试
        - 连续3次完整 → 下调10，被截断 → 上调20
        """
        # 基准值 = 滑动窗口平均（如果窗口够的话）
        if len(self._token_history) >= 3:
            base_tokens = int(sum(self._token_history) / len(self._token_history))
        else:
            base_tokens = self._adaptive_max_tokens

        best_text = ""
        for attempt in range(3):  # 最多3次（首次 + 2次重试）
            resp = await self.provider.chat(
                messages=[{"role": "system", "content": sys_content}],
                temperature=0.8,
                max_tokens=base_tokens,
            )
            content = str(resp.get("content", "")).strip()

            if len(content) > len(best_text):
                best_text = content

            if not _is_truncated(content):
                logger.info(f"冷启动第{attempt+1}次生成完整，{len(content)}字 @ {base_tokens}")
                # 记录到滑动窗口
                self._token_history.append(base_tokens)
                if len(self._token_history) > 10:
                    self._token_history.pop(0)
                break

            # 被截断 → 按完成率估算完整长度
            ratio = _completion_ratio(content)
            if ratio > 0:
                estimated = int(base_tokens / ratio)
                base_tokens = min(estimated, self._adaptive_max_tokens_limit)
                logger.info(f"冷启动完成率{ratio:.0%}，估算{base_tokens}，重试...")
            else:
                base_tokens = min(base_tokens + 40, self._adaptive_max_tokens_limit)
        else:
            logger.info(f"冷启动3次后取最长，{len(best_text)}字")

        content = best_text
        if content:
            # 自适应：上调（仍截断）或下调（连续完整）
            if _is_truncated(content):
                self._adaptive_max_tokens = min(
                    self._adaptive_max_tokens + 20,
                    self._adaptive_max_tokens_limit
                )
                self._complete_count = 0
                logger.info(f"冷启动仍被截断，上调至 {self._adaptive_max_tokens}")
            else:
                self._complete_count += 1
                if self._complete_count >= 3 and self._adaptive_max_tokens > self._adaptive_min_tokens:
                    self._adaptive_max_tokens = max(
                        self._adaptive_max_tokens - 10,
                        self._adaptive_min_tokens
                    )
                    self._complete_count = 0
                    logger.info(f"冷启动连续完整，下调至 {self._adaptive_max_tokens}")

        return content


def _is_truncated(text: str) -> bool:
    """判断文本是否被截断（不以完整句子结尾）"""
    if not text:
        return True
    text = text.strip()
    if not text:
        return True
    end_chars = set('。！？."\'）】」』》~…!?)]}')
    return text[-1] not in end_chars


def _completion_ratio(text: str) -> float:
    """估算文本完成率（0~1）"""
    if not text:
        return 0.0
    if not _is_truncated(text):
        return 1.0
    # 找最后一个完整句子
    for sep in '。！？."\'！？':
        last_idx = text.rfind(sep)
        if last_idx > 0:
            complete = text[:last_idx + 1]
            ratio = len(complete) / len(text)
            return min(ratio, 0.95)
    return 0.5  # 没有找到任何标点 → 完全被截断
