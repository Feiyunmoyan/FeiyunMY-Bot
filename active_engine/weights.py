"""
主动引擎情境矩阵权重模块（从 scheduler.py 原样搬出，逻辑未改动）

包含：情境矩阵常量表 SITUATION_MATRICES、记忆评分 _score_memory、
反馈回路的矩阵微调与用户画像更新（WeightsMixin）。
"""
import random


# ─── 情境矩阵定义 ───

SITUATION_MATRICES = {
    "情感关怀": {
        "v": 0.4, "a": 0.3, "d": 0.2,
        "importance": 0.1,
        "v*a": 0.3, "abs(v)*d": 0.2, "v*importance": 0.2,
        "bias": 0.1,
    },
    "久别重逢": {
        "importance": 0.4, "recency": 0.3, "mention_count": 0.2,
        "type_偏好": 0.3,
        "imp*recency": 0.2,
        "bias": 0.0,
    },
    "顺势而为": {
        "semantic_similarity": 0.5, "importance": 0.2,
        "vad_arousal": 0.2,
        "sim*imp": 0.1,
        "bias": 0.0,
    },
    "日常维系": {
        "importance": 0.2, "vad_强度": 0.2, "recency": 0.2,
        "mention_count": 0.1,
        "random_jitter": 0.3,
        "bias": 0.0,
    },
}


def _score_memory(memory: dict, matrix: dict) -> float:
    """用情境矩阵对一条记忆打分，输出 [-1, 1]"""
    if matrix is None:
        return 0.0

    meta = memory.get("metadata", memory)
    v = meta.get("v", 0.0)
    a = meta.get("a", 0.0)
    d = meta.get("d", 0.0)
    importance = meta.get("importance", 0.5)
    recency = meta.get("recency", 0.5)
    mention_count = meta.get("mention_count", 1)
    similarity = memory.get("relevance", 0.5)

    score = 0.0
    # 线性项
    score += matrix.get("v", 0) * v
    score += matrix.get("a", 0) * a
    score += matrix.get("d", 0) * d
    score += matrix.get("importance", 0) * importance
    score += matrix.get("recency", 0) * recency
    score += matrix.get("mention_count", 0) * min(mention_count / 5, 1)
    score += matrix.get("semantic_similarity", 0) * similarity
    score += matrix.get("vad_强度", 0) * (abs(v) * 0.5 + a * 0.3 + abs(d) * 0.2)
    score += matrix.get("type_偏好", 0) * (1.0 if meta.get("memory_type") == "偏好" else 0.0)
    score += matrix.get("vad_arousal", 0) * a

    # 交叉项
    score += matrix.get("v*a", 0) * v * a
    score += matrix.get("abs(v)*d", 0) * abs(v) * d
    score += matrix.get("v*importance", 0) * v * importance
    score += matrix.get("imp*recency", 0) * importance * recency
    score += matrix.get("sim*imp", 0) * similarity * importance

    # 随机抖动
    if "random_jitter" in matrix:
        score += matrix["random_jitter"] * (random.random() * 2 - 1)

    score += matrix.get("bias", 0)
    return max(-1.0, min(1.0, score))


class WeightsMixin:
    """情境矩阵权重与反馈回路微调（需要宿主提供 _matrices / _user_profile）。"""

    def _tune_matrices(self, situation: str, v: float):
        # 微调情境矩阵
        matrix = self._matrices.get(situation)
        if matrix:
            if v < -0.2:
                matrix["importance"] = max(0.0, matrix.get("importance", 0.3) * 0.95)
                matrix["bias"] = matrix.get("bias", 0) - 0.02
            elif v > 0.2:
                matrix["importance"] = min(1.0, matrix.get("importance", 0.3) * 1.02)
                matrix["bias"] = matrix.get("bias", 0) + 0.01

    def _update_profile(self, topic: str, v: float):
        # 更新用户画像
        if v > 0.3 and topic not in self._user_profile["positive_topics"]:
            self._user_profile["positive_topics"].append(topic)
        elif v < -0.3 and topic not in self._user_profile["negative_topics"]:
            self._user_profile["negative_topics"].append(topic)

