"""
艾宾浩斯遗忘曲线管理（自适应版）
核心公式：retention = initial * e^(-decay * days * capacity_mod * emotion_mod)

自适应因子：
1. 容量因子：超过目标容量后加速遗忘
2. 情感因子：情感越强衰减越慢
3. 访问因子：被检索越多衰减越慢（已有）
"""
import math
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EbbinghausManager:
    """
    自适应艾宾浩斯遗忘管理器
    
    核心公式：
        retention = default_retention * e^(-effective_decay * days * capacity_mod * emotion_mod)
    
    自适应调节：
        - 容量 < 目标：容量因子=1.0，不影响
        - 容量 > 目标：容量因子>1.0，加速遗忘腾空间
        - 情感强度高：情感因子<1.0，减速遗忘
        - 访问次数多：等效天数减少，减速遗忘
    """

    def __init__(
        self,
        default_retention: float = 0.8,
        decay_factor: float = 0.1,
        cleanup_threshold: float = 0.3,
        target_capacity: int = 750000,  # 目标容量（约5GB）
    ):
        self.default_retention = default_retention
        self.decay_factor = decay_factor
        self.cleanup_threshold = cleanup_threshold
        self.target_capacity = target_capacity

        logger.info(
            f"自适应艾宾浩斯管理器初始化: retention={default_retention}, "
            f"decay={decay_factor}, threshold={cleanup_threshold}, "
            f"target_capacity={target_capacity}"
        )

    def calculate_retention(
        self,
        created_at: float,
        importance: float = 0.5,
        access_count: int = 0,
        emotion_intensity: float = 0.5,
        total_memories: int = 0,
        # ─── 新增参数（VAD+类型+提及）───
        v: float = 0.0,
        a: float = 0.0,
        d: float = 0.0,
        memory_type: str = "",
        mention_count: int = 1,
    ) -> float:
        """
        计算当前记忆保留率（自适应版）

        Args:
            created_at: 记忆创建时间戳（秒）
            importance: 重要性分数 (0-1)
            access_count: 被检索/访问次数
            emotion_intensity: 情感强度 (0-1)，越强忘得越慢
            total_memories: 当前总记忆数，用于容量自适应
            v/a/d: VAD三维坐标
            memory_type: 记忆类型
            mention_count: 提及次数
        """
        elapsed_seconds = time.time() - created_at
        elapsed_days = elapsed_seconds / 86400.0

        if elapsed_days <= 0:
            return self.default_retention

        # 1) 重要性影响（不变）
        importance_modifier = 1.5 - importance * 1.2
        effective_decay = self.decay_factor * importance_modifier

        # 2) 访问次数影响（不变）
        access_bonus = 0.15 * math.log(access_count + 1)
        effective_days = max(0.01, elapsed_days - access_bonus)

        # 3) 容量自适应因子（不变）
        capacity_modifier = 1.0
        if total_memories > self.target_capacity:
            overflow_ratio = (total_memories - self.target_capacity) / self.target_capacity
            capacity_modifier = 1.0 + overflow_ratio * 0.5

        # 4) 类型衰减因子 ← 新增
        type_decay_map = {"偏好": 0.6, "事实": 0.8, "状态": 1.0, "事件": 1.2, "查询": 2.0}
        type_modifier = type_decay_map.get(memory_type, 1.0)

        # 5) VAD情感衰减 ← 替代旧的 emotion_intensity
        vad_modifier = 1.0 - (abs(v) * 0.2 + a * 0.1 + abs(d) * 0.1)
        # 向下兼容：如果VAD都是0，用旧的emotion_intensity
        if abs(v) < 0.01 and abs(a) < 0.01 and abs(d) < 0.01:
            vad_modifier = 1.0 - emotion_intensity * 0.3

        # 6) 提及+检索次数衰减 ← 更新
        total_refs = mention_count + access_count
        mention_modifier = 1.0 - 0.04 * math.log(total_refs + 1)

        # 综合衰减率
        combined_decay = effective_decay * capacity_modifier * vad_modifier * type_modifier * mention_modifier

        # 艾宾浩斯遗忘曲线
        retention = self.default_retention * math.exp(-combined_decay * effective_days)

        return max(0.0, min(1.0, retention))

    def should_cleanup(
        self,
        created_at: float,
        importance: float = 0.5,
        access_count: int = 0,
        emotion_intensity: float = 0.5,
        total_memories: int = 0,
        v: float = 0.0,
        a: float = 0.0,
        d: float = 0.0,
        memory_type: str = "",
        mention_count: int = 1,
    ) -> bool:
        """判断记忆是否应该被清理"""
        retention = self.calculate_retention(
            created_at, importance, access_count, emotion_intensity, total_memories,
            v=v, a=a, d=d, memory_type=memory_type, mention_count=mention_count,
        )
        return retention < self.cleanup_threshold

    def get_memory_ttl(
        self,
        importance: float = 0.5,
        access_count: int = 0,
        emotion_intensity: float = 0.5,
        total_memories: int = 0,
    ) -> int:
        """估算记忆的生存时间（秒）"""
        importance_modifier = 1.5 - importance * 1.2
        base_decay = self.decay_factor * importance_modifier

        capacity_modifier = 1.0
        if total_memories > self.target_capacity:
            overflow_ratio = (total_memories - self.target_capacity) / self.target_capacity
            capacity_modifier = 1.0 + overflow_ratio * 0.5

        emotion_modifier = 1.0 - emotion_intensity * 0.3
        effective_decay = base_decay * capacity_modifier * emotion_modifier

        if effective_decay <= 0:
            return 86400 * 365

        try:
            ratio = self.cleanup_threshold / self.default_retention
            if ratio <= 0:
                return 0
            days = -math.log(ratio) / effective_decay
            return int(days * 86400)
        except (ValueError, ZeroDivisionError):
            return 86400 * 30

    def get_all_stats(self, total_memories: int = 0) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return {
            "default_retention": self.default_retention,
            "decay_factor": self.decay_factor,
            "cleanup_threshold": self.cleanup_threshold,
            "target_capacity": self.target_capacity,
            "current_memories": total_memories,
            "capacity_usage_pct": round(total_memories / self.target_capacity * 100, 2) if self.target_capacity else 0,
            "high_importance_ttl_days": round(self.get_memory_ttl(0.9, 0, 0, total_memories) / 86400, 1),
            "low_importance_ttl_days": round(self.get_memory_ttl(0.2, 0, 0, total_memories) / 86400, 1),
        }
