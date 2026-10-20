"""
主动引擎调度器 V2
四通道驱动：记忆通道、上下文通道、指令通道、AI自主通道
情境矩阵评分 + 反馈回路 + 动态冷却
"""
import os
import time
import json
import random
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime

from active_engine.disturbance import (
    calculate_disturbance_index,
    AdaptiveLearner,
    get_chatter_mode_threshold,
)
from active_engine.push import PushEngine, PushMessage
from active_engine.weights import SITUATION_MATRICES, WeightsMixin, _score_memory

logger = logging.getLogger(__name__)


# 冷却配置
COOLDOWN_TABLE = {
    "深夜": 1800,
    "工作时间": 900,
    "休息时间": 600,
    "刚聊完": 1200,
    "很久没聊": 300,
}


def _judge_situation(active_scheduler) -> str:
    """判断当前情境"""
    now = datetime.now()
    hour = now.hour

    # 优先检查定时任务
    try:
        if active_scheduler._task_queue and active_scheduler._task_queue.qsize() > 0:
            return "任务提醒"
    except Exception:
        pass

    # 检查是否有待办任务到期
    if hasattr(active_scheduler, '_pending_tasks') and active_scheduler._pending_tasks:
        for task in active_scheduler._pending_tasks:
            if task.get("due_at", 0) <= time.time():
                return "任务提醒"

    # 情感关怀：刚聊完 + 情绪偏负
    last_chat = getattr(active_scheduler, '_last_chat_time', 0)
    time_since_chat = time.time() - last_chat if last_chat > 0 else 9999

    if time_since_chat < 300:  # 5分钟内
        # 查最近记忆的情感倾向
        try:
            recent = active_scheduler.memory.get_recent(n=3) if active_scheduler.memory else []
            for m in recent:
                meta = m.get("metadata", {})
                if meta.get("v", 0) < -0.3:
                    return "情感关怀"
        except Exception:
            pass

    # 久别重逢：超过2小时没聊
    if time_since_chat > 7200:
        return "久别重逢"

    # 顺势而为：正在活跃对话
    if time_since_chat < 600:
        return "顺势而为"

    return "日常维系"


def _get_cooldown_seconds(current_hour: int, time_since_last_push: float) -> int:
    """动态冷却函数"""
    if current_hour >= 23 or current_hour < 8:
        base = COOLDOWN_TABLE["深夜"]
    elif 9 <= current_hour < 18:
        base = COOLDOWN_TABLE["工作时间"]
    else:
        base = COOLDOWN_TABLE["休息时间"]

    # 很久没聊，缩短冷却
    if time_since_last_push > 7200:
        base = COOLDOWN_TABLE["很久没聊"]

    # 刚聊完，延长冷却
    if time_since_last_push < 600:
        base = COOLDOWN_TABLE["刚聊完"]

    return base


class AutonomousRateLimiter:
    """AI自主通道的频率限制"""
    def __init__(self):
        self._turn_count = 0
        self._recent_5min_times = []
        self._last_reset = time.time()

    def allow(self) -> tuple:
        now = time.time()
        # 清理5分钟前的记录
        self._recent_5min_times = [t for t in self._recent_5min_times if now - t < 300]

        if self._turn_count >= 3:
            return False, "本轮已达上限"
        if len(self._recent_5min_times) >= 5:
            return False, "频率过高"

        self._turn_count += 0
        self._recent_5min_times.append(now)
        return True, "通过"

    def new_turn(self):
        self._turn_count = 0


class ActiveScheduler(WeightsMixin):
    """
    主动引擎调度器 V2

    四通道驱动：
    - 🧠 记忆通道：情境矩阵评分，检索长期记忆
    - 💬 上下文通道：对话中自然延续的话题
    - 📋 指令通道：用户交代的定时任务
    - 🤖 AI自主通道：AI自己产生的念头

    其他特性：
    - 情境矩阵评分（5种情境 × 预设权重 + 交叉项）
    - 反馈回路（VAD分析回复态度 → 回流调整权重）
    - 动态冷却函数
    - 冷启动（新会话有记忆就问候）
    """

    def __init__(
        self,
        push_engine: PushEngine,
        adaptive_learner: AdaptiveLearner,
        workspace_manager=None,
        memory_selector=None,
        provider=None,
        persona_manager=None,
    ):
        self.push_engine = push_engine
        self.adaptive = adaptive_learner
        self.ws_manager = workspace_manager
        self.memory = memory_selector
        self.provider = provider
        self.persona_manager = persona_manager

        # 配置
        saved = self._load_config()
        self.chatter_mode = saved.get("chatter_mode", "medium")
        self.quiet_hours_start = saved.get("quiet_hours_start", 23)
        self.quiet_hours_end = saved.get("quiet_hours_end", 8)
        self.running = False

        # 自主通道限流
        self._rate_limiter = AutonomousRateLimiter()

        # 推送追踪（反馈回路用）
        self._push_history: list = []           # 已推送记录 [{topic, memory_id, time, tag}]
        self._last_push_time: float = 0         # 上次推送时间
        self._last_chat_time: float = time.time()  # 上次对话时间

        # 待办任务（指令通道）
        self._pending_tasks: list = []

        # 情境矩阵权重（可被反馈回路微调）
        self._matrices = {k: dict(v) for k, v in SITUATION_MATRICES.items()}

        # 用户偏好画像（反馈回路积累）
        self._user_profile = {
            "positive_topics": [],      # 积极回应的话题
            "negative_topics": [],      # 敷衍/负面的话题
            "best_hour_range": "14-16", # 最佳推送时段
            "situation_tuning": {},     # 情境微调
        }

        # 上次推送的记忆ID（去重用）
        self._last_pushed_memory_ids: set = set()

        # 调度器任务
        self._scheduler_task: Optional[asyncio.Task] = None
        self._task_queue: asyncio.Queue = asyncio.Queue()

        # 冷启动器（由外部注入）
        self._cold_starter = None

    async def start(self):
        """启动调度器"""
        if self.running:
            return
        self.running = True
        self._scheduler_task = asyncio.create_task(self._run_loop())
        logger.info("主动引擎调度器 V2 已启动")

    async def stop(self):
        """停止调度器"""
        self.running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self.adaptive.update_from_session()
        self._save_config()
        logger.info("主动引擎调度器 V2 已停止")

    async def _run_loop(self):
        """主循环：四通道轮询"""
        channel_intervals = {
            "memory": 600,      # 记忆通道：10分钟
            "instruction": 60,  # 指令通道：1分钟
            "context": 0,       # 上下文通道：不由轮询触发
            "autonomous": 0,    # AI自主通道：不由轮询触发
        }
        elapsed = 0

        # 冷启动：启动后不久检查一次
        await asyncio.sleep(10)
        if self._cold_starter:
            await self._cold_starter.try_greet(self._push_greeting)

        while self.running:
            try:
                now = datetime.now()
                hour = now.hour

                # 1. 指令通道：检查到期任务
                await self._check_instruction_channel()

                # 2. 记忆通道：情境判断 → 矩阵评分 → 推送
                elapsed += 30  # 每30秒 tick
                if elapsed >= channel_intervals["memory"]:
                    elapsed = 0
                    # 加随机抖动
                    jitter = random.randint(-120, 120)
                    channel_intervals["memory"] = 600 + jitter

                    # 很久没聊缩短间隔
                    if time.time() - self._last_chat_time > 7200:
                        channel_intervals["memory"] = int(channel_intervals["memory"] * 0.6)

                    await self._check_memory_channel(hour)

                # 定期存盘
                if elapsed % 600 == 0:
                    self.adaptive.persist()

                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度器异常: {e}")
                await asyncio.sleep(60)

    # ═══════════════════════════════════════
    #  四通道
    # ═══════════════════════════════════════

    async def _check_memory_channel(self, hour: int):
        """记忆通道：情境矩阵评分 → 推送"""
        if not self.memory:
            return

        # 先过三道门
        if not await self.check_can_push():
            return
        if self._in_quiet_hours(hour):
            return

        # 判断当前情境 → 选矩阵
        situation = _judge_situation(self)
        matrix = self._matrices.get(situation)

        if situation == "任务提醒":
            await self._check_instruction_channel()
            return

        if matrix is None:
            return

        # 根据情境构造语义检索query
        query_map = {
            "情感关怀": "用户的情绪和心情感受",
            "久别重逢": "用户的重要信息个人偏好和习惯",
            "日常维系": "用户最近的状态和活动",
        }
        query = query_map.get(situation, "")

        signals = []

        # 优先语义检索
        if query:
            try:
                results = self.memory.query(query, top_k=10) if hasattr(self.memory, 'query') else []
                if results:
                    signals = results
            except Exception:
                pass

        # 兜底：语义检索没结果时，用 get_recent + 情感/重要性过滤
        if not signals:
            try:
                recent = self.memory.get_recent(n=15)
                for m in recent:
                    meta = m.get("metadata", {})
                    if abs(meta.get("v", 0)) > 0.4 or meta.get("importance", 0) > 0.6:
                        signals.append(m)
            except Exception:
                pass
        
        # 去重
        signals = [s for s in signals if s.get("id") not in self._last_pushed_memory_ids]

        if not signals:
            return

        scored = []
        for s in signals:
            s["_score"] = _score_memory(s, matrix)
            scored.append(s)

        # 排序取最高
        scored.sort(key=lambda s: s["_score"], reverse=True)
        best = scored[0]

        if best["_score"] < 0.1:
            return  # 评分太低，不推

        # 生成推送内容
        content = best.get("content", "")
        preview = content[:80] if content else ""
        memory_id = best.get("id", "")
        memory_type = best.get("metadata", {}).get("memory_type", "")

        # 记录推送
        self._last_pushed_memory_ids.add(memory_id)
        if len(self._last_pushed_memory_ids) > 50:
            self._last_pushed_memory_ids.clear()

        self._push_history.append({
            "memory_id": memory_id,
            "content_preview": preview,
            "memory_type": memory_type,
            "score": best["_score"],
            "situation": situation,
            "time": time.time(),
        })
        if len(self._push_history) > 100:
            self._push_history.pop(0)

        self._last_push_time = time.time()

        # 根据情境生成自然提示词，末尾带自主许可
        situation_prompts = {
            "情感关怀": f"用户之前情绪不太好，记得ta提到过：{preview}。自然地关心一下ta现在怎么样了，如果合适可以自己查查天气或者推荐点放松的事。你可以自由决定怎么做",
            "久别重逢": f"你和用户好久没聊了，记得ta提过：{preview}。可以自然地提起这个话题，如果想了解更多可以自己去查看相关记录。自由发挥就好",
            "顺势而为": f"顺着当前的话题，用户之前提到过：{preview}。你可以自然地延伸这个话题，想查什么就去查。自己决定聊什么",
            "日常维系": f"我记得用户提到过：{preview}。你可以自由决定聊什么，想做什么就做什么",
        }
        hint = situation_prompts.get(situation, situation_prompts["日常维系"])
        await self._push_to_ai_chat(hint, source=situation)

    async def _check_context_channel(self, context_hint: str):
        """上下文通道：对话中自然延续"""
        if not context_hint:
            return
        await self._push_to_ai_chat(context_hint, source="上下文")

    async def _check_instruction_channel(self):
        """指令通道：检查到期任务"""
        now = time.time()
        still_pending = []
        for task in self._pending_tasks:
            if task.get("due_at", 0) <= now:
                # 到期了，推送
                await self._push_to_ai_chat(
                    task.get("content", ""),
                    source="任务提醒",
                )
                logger.info(f"指令通道触发: {task.get('content', '')[:40]}")
            else:
                still_pending.append(task)
        self._pending_tasks = still_pending

    async def _check_autonomous_channel(self, intent: dict):
        """AI自主通道——V2.3: AI在自然对话中调工具，不再需要JSON意图解析"""
        # V2.3: AI通过自然语言表达意图，工具调用走正常API tools参数
        # AI回复时自然说"让我查一下"就会触发工具调用
        # 此方法保留为空钩子，后续如需特定限流策略再实现
        pass

    # ═══════════════════════════════════════
    #  冷启动（委托给独立模块）
    # ═══════════════════════════════════════

    def set_cold_starter(self, cold_starter):
        """注入冷启动器"""
        self._cold_starter = cold_starter

    def _push_greeting(self, content: str):
        """冷启动回调：推送问候消息"""
        import asyncio
        asyncio.ensure_future(self._do_push_greeting(content))

    async def _do_push_greeting(self, content: str):
        """异步推送问候消息"""
        from active_engine.push import PushMessage
        msg = PushMessage(
            content=content,
            msg_type="active_push",
            priority="normal",
            source="系统",
            store_policy="memorable",
        )
        await self.push_engine.push(msg)
        self.adaptive.record_push(replied=False)

    # ═══════════════════════════════════════
    #  反馈回路
    # ═══════════════════════════════════════

    async def record_user_reply(self, replied_to_msg_id: str = "", reply_text: str = ""):
        """
        记录用户回复，进入反馈回路

        Args:
            replied_to_msg_id: 回复的消息ID（如果是回复推送）
            reply_text: 回复内容
        """
        # 更新对话时间
        self._last_chat_time = time.time()

        # 记录回应
        self.adaptive.record_push(replied=True)

        if not reply_text or not self._push_history:
            return

        # 用情感分析分析回复态度
        try:
            from memory.backends.memoria.emotion import EmotionAnalyzer
            analyzer = EmotionAnalyzer()
            emotion = analyzer.analyze(reply_text)
            v, a, d = emotion.v, emotion.a, emotion.d
        except Exception:
            # 降级：简单关键词判断
            v, a, d = 0.0, 0.0, 0.0
            positive_words = ["好", "棒", "有意思", "喜欢", "哈哈", "对呀", "是的", "谢谢"]
            negative_words = ["唉", "烦", "累", "没空", "算了", "别提了", "嗯嗯"]
            if any(w in reply_text for w in positive_words):
                v, a = 0.3, 0.2
            elif any(w in reply_text for w in negative_words):
                v, a = -0.3, -0.1

        # 找到最近一次推送
        last_push = self._push_history[-1] if self._push_history else None
        if not last_push:
            return

        # 更新记忆mention_count
        memory_id = last_push.get("memory_id", "")
        if memory_id:
            try:
                mem = self.memory.get_by_id(memory_id) if hasattr(self.memory, 'get_by_id') else None
                if mem:
                    meta = mem.get("metadata", {})
                    meta["mention_count"] = meta.get("mention_count", 0) + 1
                    meta["last_feedback_v"] = v
                    self.memory.update(memory_id, {"metadata": meta})
            except Exception:
                pass

        situation = last_push.get("situation", "日常维系")
        topic = last_push.get("memory_type", "")
        self._tune_matrices(situation, v)
        self._update_profile(topic, v)

        logger.debug(f"反馈回路: v={v:.2f}, a={a:.2f}, d={d:.2f}, topic={topic}")

    # ═══════════════════════════════════════
    #  推送方法
    # ═══════════════════════════════════════

    async def _push_to_ai_chat(self, content_hint: str, source: str = ""):
        """推送给AI生成自然聊天内容"""
        if not content_hint:
            return

        msg = PushMessage(
            content=content_hint,
            msg_type="active_push",
            priority="normal",
            source=source,
            store_policy="memorable",
        )
        await self.push_engine.push(msg)
        self.adaptive.record_push(replied=False)

    async def push_system_event(self, content: str, priority: str = "normal", source: str = ""):
        """推送系统事件（不走AI生成）"""
        msg = PushMessage(
            content=content,
            msg_type="system_event",
            priority=priority,
            source=source,
            store_policy="ephemeral",
        )
        await self.push_engine.push(msg)

    def add_task(self, content: str, due_at: float):
        """添加一条定时任务（指令通道）"""
        self._pending_tasks.append({
            "content": content,
            "due_at": due_at,
            "created_at": time.time(),
        })
        logger.info(f"添加定时任务: {content[:40]}... 到期: {due_at}")

    def handle_ai_intent(self, intent: dict):
        """处理AI回复中的自主意图——V2.3: AI直接在自然对话中调工具，无需JSON格式"""
        # V2.3: AI自主通道已整合到自然对话流程中
        # AI想做什么直接在自然语言中表达，工具调用机制自动处理
        # 此方法保留为安全钩子，实际逻辑由工具系统接管
        pass

    # ═══════════════════════════════════════
    #  时机判断
    # ═══════════════════════════════════════

    def _in_quiet_hours(self, hour: int) -> bool:
        """检查是否在免打扰时段"""
        if self.chatter_mode == "off":
            return True
        if self.quiet_hours_start <= hour or hour < self.quiet_hours_end:
            return True
        return False

    async def check_can_push(self) -> bool:
        """
        检查当前是否可以推送
        结合打扰指数 + 话痨模式 + 冷却判断
        """
        if self.chatter_mode == "off":
            return False

        # 冷却判断
        now = time.time()
        hour = datetime.now().hour
        cooldown = _get_cooldown_seconds(hour, now - self._last_push_time)

        if now - self._last_push_time < cooldown:
            return False

        # 打扰指数判断
        threshold = self.adaptive.get_session_adjusted_threshold(self.chatter_mode)
        disturbance = calculate_disturbance_index()

        return disturbance >= threshold

    # ═══════════════════════════════════════
    #  配置 & 状态
    # ═══════════════════════════════════════

    CONFIG_FILE = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "active_config.json"
    )

    def _load_config(self) -> dict:
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
            except Exception as e:
                logger.warning(f"加载配置失败: {e}")
        return {}

    def _save_config(self):
        os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
        data = {
            "chatter_mode": self.chatter_mode,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
        }
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def get_config(self) -> dict:
        return {
            "chatter_mode": self.chatter_mode,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "version": "V2",
            "adaptive_stats": self.adaptive.get_stats(),
        }

    def update_config(self, updates: dict):
        if "chatter_mode" in updates:
            mode = updates["chatter_mode"]
            if mode in ("high", "medium", "low", "off"):
                self.chatter_mode = mode
        if "quiet_hours_start" in updates:
            self.quiet_hours_start = updates["quiet_hours_start"]
        if "quiet_hours_end" in updates:
            self.quiet_hours_end = updates["quiet_hours_end"]
        self._save_config()
        logger.info(f"配置已更新: {updates}")
