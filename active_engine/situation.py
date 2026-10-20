"""
主动引擎情境判断模块（从 scheduler.py 原样搬出，逻辑未改动）

包含：情境判定 _judge_situation、动态冷却 COOLDOWN_TABLE / _get_cooldown_seconds、
免打扰时段与推送许可检查（SituationMixin）。
"""
import time
from datetime import datetime

from active_engine.disturbance import calculate_disturbance_index


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


class SituationMixin:
    """时机判断（需要宿主提供 chatter_mode / quiet_hours_* / _last_push_time / adaptive）。"""

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

