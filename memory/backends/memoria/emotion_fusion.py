"""
多轮对话情感融合层
追踪会话级情感历史，检测情感冲突，输出修正后的综合情感
"""
import logging
import time
from typing import Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 情感冲突判定阈值
CONFLICT_THRESHOLD = 0.3
# 情感历史保留轮数
MAX_HISTORY_TURNS = 10


@dataclass
class EmotionTurn:
    """单轮情感记录"""
    emotion_type: str
    intensity: float
    polarity: int
    timestamp: float
    text_preview: str


class EmotionFusion:
    """
    多轮情感融合器
    
    功能：
    1. 记录每轮对话的情感状态
    2. 检测情感冲突（如说"我没事"但历史偏置为负）
    3. 输出修正后的综合情感
    """

    # 情感极性映射
    POLARITY_MAP = {
        "喜": 1, "乐": 1, "爱": 1, "惊喜": 1,
        "怒": -1, "哀": -1, "惧": -1, "恶": -1,
        "中性": 0,
    }

    def __init__(self, max_history: int = MAX_HISTORY_TURNS):
        self.max_history = max_history
        self._history: Dict[str, List[EmotionTurn]] = {}  # session_id -> [emotion turns]

    def add_turn(self, session_id: str, emotion_type: str, intensity: float,
                 polarity: int, text: str = "") -> None:
        """记录一轮对话的情感"""
        if session_id not in self._history:
            self._history[session_id] = []

        self._history[session_id].append(EmotionTurn(
            emotion_type=emotion_type,
            intensity=intensity,
            polarity=polarity,
            timestamp=time.time(),
            text_preview=text[:50],
        ))

        # 保留最近N轮
        if len(self._history[session_id]) > self.max_history:
            self._history[session_id] = self._history[session_id][-self.max_history:]

    def get_history_polarity(self, session_id: str, window: int = 3) -> float:
        """
        获取历史情感偏置（最近N轮加权平均极性）
        
        Returns:
            float: -1.0 ~ 1.0，负值=消极偏置，正值=积极偏置
        """
        if session_id not in self._history or not self._history[session_id]:
            return 0.0

        recent = self._history[session_id][-window:]
        if not recent:
            return 0.0

        # 时间衰减权重：越近的权重越高
        total_weight = 0.0
        weighted_polarity = 0.0
        for i, turn in enumerate(recent):
            weight = (i + 1) / len(recent)  # 0.33 ~ 1.0
            weighted_polarity += turn.polarity * turn.intensity * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return weighted_polarity / total_weight

    def _get_adaptive_threshold(self, session_id: str) -> float:
        """
        获取自适应冲突检测阈值
        
        根据用户的历史情绪波动性动态调整：
        - 波动小的人 → 阈值低 → 容易检测冲突
        - 波动大的人 → 阈值高 → 宽松检测
        """
        summary = self.get_session_emotion_summary(session_id)
        if summary["turn_count"] < 3:
            return CONFLICT_THRESHOLD  # 默认0.3

        # 自适应：基线波动性 + 固定余量
        adaptive = summary["volatility"] + 0.2
        return min(1.0, max(0.2, adaptive))

    def detect_conflict(self, session_id: str, emotion_type: str,
                        intensity: float) -> Tuple[bool, float]:
        """
        检测情感冲突（自适应版）
        
        根据用户历史情绪波动性动态调整检测灵敏度。
        波动大的人情感切换是常态，修正力度递减。
        
        Args:
            session_id: 会话ID
            emotion_type: 当前轮的情感类型
            intensity: 当前轮的情感强度
            
        Returns:
            (是否冲突, 冲突强度)
        """
        history_polarity = self.get_history_polarity(session_id)
        current_polarity = self.POLARITY_MAP.get(emotion_type, 0)

        # 检查是否有冲突：历史偏置和当前极性相反
        if history_polarity * current_polarity >= 0:
            return False, 0.0

        if abs(history_polarity) <= CONFLICT_THRESHOLD:
            return False, 0.0

        conflict_strength = abs(history_polarity) * intensity

        # 自适应缩放：波动越大，修正越弱
        summary = self.get_session_emotion_summary(session_id)
        if summary["turn_count"] >= 3:
            volatility = summary["volatility"]
            # 平滑缩放：波动0.2→修正力度1.0, 波动0.6→0.5, 波动1.0→0.0
            correction_scale = max(0.0, 1.0 - (volatility - 0.2) * 1.25)
            conflict_strength *= correction_scale
            if conflict_strength <= 0.01:
                return False, 0.0

        return True, conflict_strength

    def fuse(self, session_id: str, emotion_type: str, intensity: float,
             polarity: int, text: str = "") -> Dict:
        """
        融合情感：结合历史偏置和当前检测，输出修正后的情感
        
        Args:
            session_id: 会话ID
            emotion_type: 原始情感类型
            intensity: 原始情感强度
            polarity: 原始情感极性
            text: 原始文本（用于记录）
            
        Returns:
            dict: 修正后的情感结果 {emotion_type, intensity, polarity, confidence, conflict_detected}
        """
        # 先记录当前轮
        self.add_turn(session_id, emotion_type, intensity, polarity, text)

        # 检测冲突
        has_conflict, conflict_strength = self.detect_conflict(
            session_id, emotion_type, intensity
        )

        if not has_conflict:
            # 无冲突，但用历史偏置微调强度
            history_polarity = self.get_history_polarity(session_id)
            if abs(history_polarity) > CONFLICT_THRESHOLD:
                # 历史有持续情感，适当增强强度
                adjusted_intensity = min(1.0, intensity + abs(history_polarity) * 0.15)
            else:
                adjusted_intensity = intensity

            return {
                "emotion_type": emotion_type,
                "intensity": round(adjusted_intensity, 3),
                "polarity": polarity,
                "confidence": round(intensity, 3),
                "conflict_detected": False,
            }

        # 检测到冲突 → 修正情感
        # 例如：历史偏置为负（哀0.6），当前说"我没事"（中性）
        # → 修正为"强压情绪"，保留历史极性
        history_polarity = self.get_history_polarity(session_id)

        if history_polarity < 0:
            # 历史消极，当前说没事 → "强压悲伤"
            corrected_type = "哀"
            corrected_intensity = min(1.0, (intensity + conflict_strength) * 0.8)
            corrected_polarity = -1
        else:
            # 历史积极，当前说不好 → 可能是转折
            corrected_type = emotion_type
            corrected_intensity = intensity
            corrected_polarity = polarity

        logger.info(
            f"情感冲突检测: 历史偏置={history_polarity:.2f}, "
            f"当前={emotion_type}({intensity}), "
            f"修正={corrected_type}({corrected_intensity:.2f})"
        )

        return {
            "emotion_type": corrected_type,
            "intensity": round(corrected_intensity, 3),
            "polarity": corrected_polarity,
            "confidence": round(intensity, 3),
            "conflict_detected": True,
        }

    def clear_session(self, session_id: str) -> None:
        """清空指定会话的情感历史"""
        self._history.pop(session_id, None)

    def get_session_emotion_summary(self, session_id: str) -> Dict:
        """获取会话的情感摘要"""
        if session_id not in self._history or not self._history[session_id]:
            return {"dominant": "中性", "volatility": 0.0, "turn_count": 0}

        history = self._history[session_id]
        polarities = [t.polarity for t in history]
        avg_polarity = sum(polarities) / len(polarities)

        # 情绪波动性（极性变化的剧烈程度）
        volatility = 0.0
        if len(polarities) > 1:
            changes = [abs(polarities[i] - polarities[i - 1]) for i in range(1, len(polarities))]
            volatility = sum(changes) / len(changes)

        # 主导情感（出现最多的）
        from collections import Counter
        type_counts = Counter(t.emotion_type for t in history)
        dominant = type_counts.most_common(1)[0][0]

        return {
            "dominant": dominant,
            "avg_polarity": round(avg_polarity, 2),
            "volatility": round(volatility, 2),
            "turn_count": len(history),
        }
