"""
精简版重要性评分器
从内容长度、关键词、结构化特征等维度评估记忆重要性
"""
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ImportanceScorer:
    """
    重要性评分器
    
    综合评分维度：
    1. 内容长度（适中为佳）
    2. 关键词密度（人名、地名、专业术语等）
    3. 结构化特征（列表、编号、问答等）
    4. 情感强度（情感越强烈通常越重要）
    """

    # 高价值关键词模式
    KEY_PATTERNS = {
        "人名": r"[\u4e00-\u9fa5]{2,4}(?:说|告诉|提到|介绍|推荐|认为|喜欢)",
        "地名": r"(?:在|去|来自|位于|来自)[\u4e00-\u9fa5]{2,6}(?:市|省|国|区|县|镇|村)",
        "时间": r"(?:\d{4}年|\d{1,2}月|\d{1,2}日|今天|明天|昨天|上周|下周|最近|将来|过去)",
        "数字": r"\d+(?:万|千|百|亿|%|元|个|次|倍)",
        "专业术语": r"(?:算法|模型|框架|系统|接口|协议|标准|规范|原理|方法|技术)",
        "动作指令": r"(?:请记住|记住|不要忘记|务必|一定|必须|需要|要求)",
    }

    def __init__(self, min_score: float = 0.3):
        """
        初始化
        
        Args:
            min_score: 最低存入分数阈值
        """
        self.min_score = min_score
        logger.info(f"重要性评分器初始化，最低分数：{min_score}")

    def score_semantic(self, text: str, emotion_intensity: float = 0.5) -> dict:
        """
        使用 BGE 语义模型评估重要性（作为规则法的补充）
        当语义模型不可用时 fallback 到规则法
        """
        try:
            from memory.backends.memoria import semantic_similarity, _get_sentence_transformer
            model = _get_sentence_transformer()
            if model is None:
                return self.score(text, emotion_intensity)

            important_templates = [
                "这是一个需要记住的重要信息",
                "这是用户的个人特征或偏好",
                "这是用户明确要求记住的内容",
                "这是一个有长期价值的知识点",
            ]
            unimportant_templates = [
                "这是日常闲聊",
                "这是一个简单的问候或寒暄",
                "这是毫无信息量的废话",
            ]

            important_scores = [semantic_similarity(text, t) for t in important_templates]
            unimportant_scores = [semantic_similarity(text, t) for t in unimportant_templates]

            semantic_score = max(important_scores) - max(unimportant_scores)
            semantic_score = max(0.0, min(1.0, (semantic_score + 1) / 2))

            rule_score = self.score(text, emotion_intensity)["overall_score"]
            combined = (rule_score + semantic_score) / 2

            return {"overall_score": combined, "rule_score": rule_score, "semantic_score": semantic_score}
        except Exception:
            return self.score(text, emotion_intensity)

    def score(self, text: str, emotion_intensity: float = 0.5) -> Dict[str, Any]:
        """
        计算文本重要性分数
        
        Args:
            text: 记忆文本
            emotion_intensity: 情感强度（外部传入）
            
        Returns:
            dict: 包含 overall_score 和各维度分数的结果
        """
        if not text or not text.strip():
            return {"overall_score": 0.0, "details": {}}

        # 各维度评分
        length_score = self._score_length(text)
        keyword_score = self._score_keywords(text)
        structure_score = self._score_structure(text)
        emotion_score = emotion_intensity * 0.8  # 情感作为辅助因子

        # 加权综合
        weights = {
            "length": 0.15,
            "keyword": 0.35,
            "structure": 0.20,
            "emotion": 0.30,
        }

        overall = (
            length_score * weights["length"]
            + keyword_score * weights["keyword"]
            + structure_score * weights["structure"]
            + emotion_score * weights["emotion"]
        )

        # 归一化到 0-1
        overall = min(1.0, max(0.0, overall))

        return {
            "overall_score": overall,
            "length_score": length_score,
            "keyword_score": keyword_score,
            "structure_score": structure_score,
            "emotion_score": emotion_score,
            "above_threshold": overall >= self.min_score,
        }

    def _score_length(self, text: str) -> float:
        """
        长度评分
        
        太短（<10字）或太长（>500字）都不理想
        最佳范围：20-200字
        """
        length = len(text)
        if length < 5:
            return 0.1
        elif length < 20:
            return 0.3 + (length - 5) * 0.02
        elif length <= 200:
            return 0.7
        elif length <= 500:
            return 0.7 - (length - 200) * 0.001
        else:
            return max(0.2, 0.5 - (length - 500) * 0.0005)

    def _score_keywords(self, text: str) -> float:
        """关键词密度评分"""
        total_matches = 0
        max_possible = len(self.KEY_PATTERNS)

        for category, pattern in self.KEY_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                total_matches += min(len(matches), 3)  # 每类最多算3个

        # 归一化
        density = total_matches / max_possible
        return min(1.0, density * 1.5)

    def _score_structure(self, text: str) -> float:
        """结构化特征评分"""
        score = 0.1  # 基础分

        # 检查结构化特征
        if re.search(r"\d+[\.\、\)]", text):  # 编号列表
            score += 0.2

        if re.search(r"(?:首先|其次|然后|最后|总结|因此|所以|因为)", text):  # 逻辑连接词
            score += 0.15

        if re.search(r"(?:如果|那么|否则|当|只要|除非)", text):  # 条件语句
            score += 0.15

        if re.search(r"(?:问题|答案|解答|解释|说明|步骤|方法)", text):  # 问答/说明特征
            score += 0.2

        # 换行/分段（表示内容组织良好）
        if text.count("\n") >= 2:
            score += 0.1

        return min(1.0, score)

    def should_store(self, text: str, emotion_intensity: float = 0.5) -> bool:
        """判断是否应该存入长期记忆"""
        result = self.score(text, emotion_intensity)
        return result["above_threshold"]
