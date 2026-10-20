"""
打扰指数算法 + 自适应学习
根据用户状态动态计算"现在是否适合打扰"
"""
import os
import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 自适应参数文件
ADAPTIVE_PARAMS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "active_params.json"
)

# 默认参数
DEFAULT_ACTIVE_THRESHOLD = 0.5   # 默认活跃阈值
MIN_ACTIVE_THRESHOLD = 0.3       # 最低阈值
MAX_ACTIVE_THRESHOLD = 0.8       # 最高阈值
FUSION_RATE = 0.3                # 关机时新数据的融合权重

# 话痨模式：档位 -> 所需的最低打扰指数
CHATTER_MODE_THRESHOLDS = {
    "high": 0.3,    # 🗣️ 高：较低门槛，常主动
    "medium": 0.5,  # 🙆 中：默认平衡
    "low": 0.7,     # 🤫 低：较高门槛，少打扰
    "off": 1.1,     # 🔇 关：不触发（需要 > 1.0 永达不到）
}

# 时段权重
TIME_WEIGHTS = {
    "深夜": 0.1,     # 23:00 ~ 8:00
    "工作时间": 0.6,  # 9:00 ~ 18:00
    "休息时间": 0.8,  # 18:00 ~ 23:00
}


def _get_time_period(hour: int) -> str:
    """获取当前时段名称"""
    if 23 <= hour or hour < 8:
        return "深夜"
    elif 9 <= hour < 18:
        return "工作时间"
    else:
        return "休息时间"


def calculate_disturbance_index(
    keyboard_freq: float = 0.0,
    cpu_usage: float = 0.0,
    gpu_usage: float = 0.0,
    screen_focused: bool = True,
    hour: Optional[int] = None,
    emotional_weight: float = 0.0,
) -> float:
    """
    计算打扰指数（0.0 ~ 1.0）

    Args:
        keyboard_freq: 键盘/鼠标活动频率 (0~100)
        cpu_usage: CPU 使用率 (0~100)
        gpu_usage: GPU 使用率 (0~100)
        screen_focused: 页面是否聚焦
        hour: 当前小时 (0~23)，None 自动获取
        emotional_weight: 情感权重 (0~0.3)，情绪低落时提高，让绯璃更容易主动关心

    Returns:
        打扰指数，越高越适合打扰
    """
    if hour is None:
        from datetime import datetime
        hour = datetime.now().hour

    # 输入分：敲得越快，分越低（越忙）
    input_score = 1.0 - min(keyboard_freq / 100, 1.0)

    # 负载分：占用越高，分越低（越忙）
    load_score = 1.0 - max(cpu_usage, gpu_usage) / 100

    # 焦点分：没看页面，分低
    focus_score = 1.0 if screen_focused else 0.3

    # 时段权重
    period = _get_time_period(hour)
    time_weight = TIME_WEIGHTS.get(period, 0.5)

    # 情感权重：情绪低落时提高打扰指数（让绯璃更容易主动关心）
    emotion_boost = emotional_weight * 0.3  # 最高 +0.09

    # 加权计算
    index = (input_score * 0.35 + load_score * 0.3 + focus_score * 0.35) * time_weight + emotion_boost

    # 限制范围
    return max(0.0, min(1.0, index))


def get_chatter_mode_threshold(mode: str) -> float:
    """获取话痨模式对应的触发阈值"""
    return CHATTER_MODE_THRESHOLDS.get(mode, CHATTER_MODE_THRESHOLDS["medium"])


class AdaptiveLearner:
    """
    自适应学习器
    根据用户的回复行为，动态调整活跃阈值
    """

    def __init__(self):
        self.params = self._load()
        self._session_pushes = []       # 本次会话的推送记录
        self._session_threshold_adjust = 0.0  # 会话内临时调整

    def _load(self) -> dict:
        """加载自适应参数"""
        if os.path.exists(ADAPTIVE_PARAMS_PATH):
            try:
                with open(ADAPTIVE_PARAMS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载自适应参数失败: {e}")
        return {
            "active_threshold": DEFAULT_ACTIVE_THRESHOLD,
            "total_pushes": 0,
            "total_replies": 0,
            "last_updated": time.time(),
        }

    def _save(self):
        """保存自适应参数到磁盘"""
        os.makedirs(os.path.dirname(ADAPTIVE_PARAMS_PATH), exist_ok=True)
        self.params["last_updated"] = time.time()
        with open(ADAPTIVE_PARAMS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.params, f, ensure_ascii=False, indent=2)

    def record_push(self, replied: bool):
        """
        记录一次主动推送及是否被回复

        Args:
            replied: 用户是否回复了这条推送
        """
        self.params["total_pushes"] += 1
        if replied:
            self.params["total_replies"] += 1
        self._session_pushes.append({"replied": replied, "time": time.time()})

    def get_session_adjusted_threshold(self, mode: str = "medium") -> float:
        """
        获取经会话内调整后的阈值

        Args:
            mode: 话痨模式 high/medium/low/off

        Returns:
            调整后的阈值
        """
        base_threshold = get_chatter_mode_threshold(mode)

        # 从历史数据中获取基础阈值
        historical = self.params.get("active_threshold", DEFAULT_ACTIVE_THRESHOLD)

        # 如果历史数据积累足够，用历史数据作为基准
        if self.params.get("total_pushes", 0) >= 10:
            base_threshold = historical

        # 加上会话内的临时调整
        adjusted = base_threshold + self._session_threshold_adjust

        return max(MIN_ACTIVE_THRESHOLD, min(MAX_ACTIVE_THRESHOLD, adjusted))

    def update_from_session(self):
        """
        会话结束时，用本次会话的数据做慢速融合更新
        """
        if not self._session_pushes:
            return

        total = len(self._session_pushes)
        replied = sum(1 for p in self._session_pushes if p["replied"])

        if total < 3:
            # 数据太少，不调整
            self._session_pushes = []
            return

        reply_rate = replied / total

        # 根据回应率计算本次会话的学习结果
        if reply_rate < 0.3:
            # 回应率低 → 阈值调高（减少打扰）
            session_learned = min(
                self.params.get("active_threshold", DEFAULT_ACTIVE_THRESHOLD) + 0.05,
                MAX_ACTIVE_THRESHOLD
            )
        elif reply_rate > 0.7:
            # 回应率高 → 阈值调低（更积极）
            session_learned = max(
                self.params.get("active_threshold", DEFAULT_ACTIVE_THRESHOLD) - 0.05,
                MIN_ACTIVE_THRESHOLD
            )
        else:
            # 回应率正常，维持不变
            session_learned = self.params.get("active_threshold", DEFAULT_ACTIVE_THRESHOLD)

        # 慢速融合：新阈值 = 旧阈值 * (1 - fusion_rate) + 学习结果 * fusion_rate
        old_threshold = self.params.get("active_threshold", DEFAULT_ACTIVE_THRESHOLD)
        new_threshold = old_threshold * (1 - FUSION_RATE) + session_learned * FUSION_RATE

        self.params["active_threshold"] = round(new_threshold, 2)
        self._session_pushes = []
        self._session_threshold_adjust = 0.0

        logger.info(
            f"自适应学习: 回应率={reply_rate:.0%}, "
            f"阈值 {old_threshold:.2f} → {new_threshold:.2f}"
        )
        self._save()

    def set_session_adjust(self, adjust: float):
        """会话内临时调整阈值"""
        self._session_threshold_adjust = max(-0.2, min(0.2, adjust))

    def persist(self):
        """将当前统计数据持久化到磁盘（不进融合，纯保存）"""
        self._save()

    def get_stats(self) -> dict:
        """获取自适应学习统计"""
        total = self.params.get("total_pushes", 0)
        replied = self.params.get("total_replies", 0)
        return {
            "active_threshold": self.params.get("active_threshold", DEFAULT_ACTIVE_THRESHOLD),
            "total_pushes": total,
            "total_replies": replied,
            "reply_rate": round(replied / total, 2) if total > 0 else 0,
            "last_updated": self.params.get("last_updated", 0),
        }
