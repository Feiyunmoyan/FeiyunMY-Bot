"""
精简版情感分析器
从 MemoriaDB 提取核心逻辑，适配 FeiyunMY-Bot
GoEmotions 28类细粒度情感 + VAD三维坐标（效价/唤醒/支配）
"""
import os
import json
import logging
import math
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# ─── VAD 情感坐标映射 ───
# GoEmotions 28类 → [效价(Valence), 唤醒(Arousal), 支配(Dominance)]
# 取值范围：-1 ~ 1
VAD_MAP = {
    "admiration":       [ 0.7,  0.3,  0.5],  # 钦佩
    "amusement":        [ 0.6,  0.6,  0.4],  # 娱乐
    "anger":            [-0.8,  0.7,  0.6],  # 愤怒
    "annoyance":        [-0.5,  0.4,  0.3],  # 烦恼
    "approval":         [ 0.5,  0.2,  0.3],  # 认可
    "caring":           [ 0.6,  0.1,  0.2],  # 关怀
    "confusion":        [-0.2,  0.3, -0.4],  # 困惑
    "curiosity":        [ 0.3,  0.5,  0.1],  # 好奇
    "desire":           [ 0.5,  0.6,  0.4],  # 渴望
    "disappointment":   [-0.6, -0.2, -0.4],  # 失望
    "disapproval":      [-0.5,  0.2,  0.2],  # 不赞同
    "disgust":          [-0.7,  0.5,  0.3],  # 厌恶
    "embarrassment":    [-0.3,  0.4, -0.5],  # 尴尬
    "excitement":       [ 0.7,  0.8,  0.5],  # 兴奋
    "fear":             [-0.7,  0.8, -0.5],  # 恐惧
    "gratitude":        [ 0.7,  0.3,  0.2],  # 感激
    "grief":            [-0.8, -0.3, -0.5],  # 悲痛
    "joy":              [ 0.8,  0.6,  0.5],  # 快乐
    "love":             [ 0.8,  0.5,  0.3],  # 爱
    "nervousness":      [-0.4,  0.7, -0.4],  # 紧张
    "neutral":          [ 0.0,  0.0,  0.0],  # 中性
    "optimism":         [ 0.6,  0.4,  0.4],  # 乐观
    "pride":            [ 0.6,  0.4,  0.6],  # 自豪
    "realization":      [ 0.2,  0.5,  0.3],  # 领悟
    "relief":           [ 0.5, -0.3,  0.3],  # 解脱
    "remorse":          [-0.6, -0.1, -0.3],  # 懊悔
    "sadness":          [-0.6, -0.3, -0.4],  # 悲伤
    "surprise":         [ 0.2,  0.7,  0.1],  # 惊讶
}

# 语义模板（BGE匹配用）
EMOTION_TEMPLATES = {
    "admiration":     "这件事让人感到很钦佩，值得赞赏",
    "amusement":      "这件事让人觉得很有趣很好笑",
    "anger":          "这件事让人感到很愤怒，无法接受",
    "annoyance":      "这件事让人有点烦躁，不太舒服",
    "approval":       "这件事让人很认可很赞同",
    "caring":         "这件事让人感到很温暖很关怀",
    "confusion":      "这件事让人感到很困惑不太明白",
    "curiosity":      "这件事让人很好奇想了解更多",
    "desire":         "这件事让人很渴望很想要",
    "disappointment": "这件事让人很失望，和预期不一样",
    "disapproval":    "这件事让人不认同，觉得不太对",
    "disgust":        "这件事让人很厌恶很反感",
    "embarrassment":  "这件事让人很尴尬很不好意思",
    "excitement":     "这件事让人很兴奋很期待",
    "fear":           "这件事让人感到很害怕很担心",
    "gratitude":      "这件事让人很感激很感谢",
    "grief":          "这件事让人很悲痛很难过",
    "joy":            "这件事让人很开心很愉快",
    "love":           "这件事让人很喜爱很珍惜",
    "nervousness":    "这件事让人感到紧张不安",
    "neutral":        "这是一个普通的事实陈述",
    "optimism":       "这件事让人很乐观，充满希望",
    "pride":          "这件事让人很自豪很骄傲",
    "realization":    "这件事让人恍然大悟，突然明白了",
    "relief":         "这件事让人松了一口气，放心了",
    "remorse":        "这件事让人很懊悔很后悔",
    "sadness":        "这件事让人很悲伤很难受",
    "surprise":       "这件事让人很惊讶很意外",
}


@dataclass
class EmotionResult:
    """情感分析结果"""
    emotion_type: str = "neutral"
    emotion_label_cn: str = "中性"
    intensity: float = 0.5
    polarity: int = 0       # -1: 消极, 0: 中性, 1: 积极
    valence: float = 0.0    # VAD: 效价
    arousal: float = 0.0    # VAD: 唤醒
    dominance: float = 0.0  # VAD: 支配
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion_type": self.emotion_type,
            "emotion_label_cn": self.emotion_label_cn,
            "intensity": self.intensity,
            "polarity": self.polarity,
            "v": self.valence,
            "a": self.arousal,
            "d": self.dominance,
            "confidence": self.confidence,
        }
    
    def vad_tuple(self) -> Tuple[float, float, float]:
        return (self.valence, self.arousal, self.dominance)


class EmotionAnalyzer:
    """
    中文情感分析器
    
    基于词典匹配，支持：
    - 情感词识别
    - 程度副词加权
    - 否定词反转
    - 表情符号/网络用语识别
    """

    # 情感极性分类
    POSITIVE_EMOTIONS = {"喜", "乐", "爱", "惊喜", "快乐", "感激", "自豪", "期待", "理解", "领悟"}
    NEGATIVE_EMOTIONS = {"怒", "哀", "恶", "愤怒", "悲伤", "恐惧", "焦虑", "愧疚", "嫉妒", "羞愧", "困惑", "迷茫"}

    def __init__(self):
        # 加载词典
        self.emotion_dict: Dict[str, Dict] = {}
        self.intensity_dict: Dict[str, float] = {}
        self.emoji_dict: Dict[str, Dict] = {}
        self.slang_dict: Dict[str, Dict] = {}
        self.negation_words = ["不", "没", "无", "非", "未", "别", "莫", "勿", "没有", "不是", "不能", "不会"]

        self._load_dicts()
        logger.info("情感分析器初始化完成")

    def _load_dicts(self):
        """加载情感词典"""
        try:
            # 加载情感词
            emotion_path = os.path.join(DATA_DIR, "emotion_dict.json")
            if os.path.exists(emotion_path):
                with open(emotion_path, "r", encoding="utf-8") as f:
                    self.emotion_dict = json.load(f)
                logger.info(f"加载情感词典：{len(self.emotion_dict)} 个词")
            else:
                self._init_builtin_emotion_dict()

            # 加载程度副词
            intensity_path = os.path.join(DATA_DIR, "intensity_dict.json")
            if os.path.exists(intensity_path):
                with open(intensity_path, "r", encoding="utf-8") as f:
                    self.intensity_dict = json.load(f)
                logger.info(f"加载程度副词：{len(self.intensity_dict)} 个")
            else:
                self._init_builtin_intensity_dict()

            # 加载表情符号
            emoji_path = os.path.join(DATA_DIR, "emoji_dict.json")
            if os.path.exists(emoji_path):
                with open(emoji_path, "r", encoding="utf-8") as f:
                    self.emoji_dict = json.load(f)
                logger.info(f"加载表情词典：{len(self.emoji_dict)} 个")
            else:
                self._init_builtin_emoji_dict()

            # 加载网络用语
            slang_path = os.path.join(DATA_DIR, "slang_dict.json")
            if os.path.exists(slang_path):
                with open(slang_path, "r", encoding="utf-8") as f:
                    self.slang_dict = json.load(f)
                logger.info(f"加载网络用语：{len(self.slang_dict)} 个")
            else:
                self._init_builtin_slang_dict()

        except Exception as e:
            logger.warning(f"加载词典失败，使用内置词典：{e}")
            self._init_builtin_emotion_dict()
            self._init_builtin_intensity_dict()
            self._init_builtin_emoji_dict()
            self._init_builtin_slang_dict()

    def _init_builtin_emotion_dict(self):
        """内置基础情感词"""
        self.emotion_dict = {
            "高兴": {"emotion_type": "喜", "base_intensity": 0.7, "polarity": 1},
            "开心": {"emotion_type": "乐", "base_intensity": 0.6, "polarity": 1},
            "快乐": {"emotion_type": "乐", "base_intensity": 0.6, "polarity": 1},
            "兴奋": {"emotion_type": "喜", "base_intensity": 0.8, "polarity": 1},
            "惊喜": {"emotion_type": "惊喜", "base_intensity": 0.9, "polarity": 1},
            "生气": {"emotion_type": "怒", "base_intensity": 0.7, "polarity": -1},
            "愤怒": {"emotion_type": "怒", "base_intensity": 0.9, "polarity": -1},
            "伤心": {"emotion_type": "哀", "base_intensity": 0.7, "polarity": -1},
            "难过": {"emotion_type": "哀", "base_intensity": 0.6, "polarity": -1},
            "悲伤": {"emotion_type": "哀", "base_intensity": 0.8, "polarity": -1},
            "痛苦": {"emotion_type": "哀", "base_intensity": 0.8, "polarity": -1},
            "绝望": {"emotion_type": "哀", "base_intensity": 0.9, "polarity": -1},
            "失望": {"emotion_type": "哀", "base_intensity": 0.6, "polarity": -1},
            "爱": {"emotion_type": "爱", "base_intensity": 0.8, "polarity": 1},
            "喜欢": {"emotion_type": "爱", "base_intensity": 0.6, "polarity": 1},
            "热爱": {"emotion_type": "爱", "base_intensity": 0.8, "polarity": 1},
            "感激": {"emotion_type": "感激", "base_intensity": 0.7, "polarity": 1},
            "感谢": {"emotion_type": "感激", "base_intensity": 0.6, "polarity": 1},
            "讨厌": {"emotion_type": "恶", "base_intensity": 0.6, "polarity": -1},
            "厌恶": {"emotion_type": "恶", "base_intensity": 0.8, "polarity": -1},
            "嫉妒": {"emotion_type": "嫉妒", "base_intensity": 0.7, "polarity": -1},
            "好奇": {"emotion_type": "好奇", "base_intensity": 0.5, "polarity": 1},
            "困惑": {"emotion_type": "困惑", "base_intensity": 0.4, "polarity": -1},
            "怀疑": {"emotion_type": "怀疑", "base_intensity": 0.5, "polarity": -1},
            "愧疚": {"emotion_type": "愧疚", "base_intensity": 0.6, "polarity": -1},
            "自豪": {"emotion_type": "自豪", "base_intensity": 0.6, "polarity": 1},
            "恐惧": {"emotion_type": "恐惧", "base_intensity": 0.8, "polarity": -1},
            "害怕": {"emotion_type": "恐惧", "base_intensity": 0.7, "polarity": -1},
            "焦虑": {"emotion_type": "焦虑", "base_intensity": 0.7, "polarity": -1},
            "担忧": {"emotion_type": "焦虑", "base_intensity": 0.6, "polarity": -1},
            "期待": {"emotion_type": "期待", "base_intensity": 0.6, "polarity": 1},
            "迷茫": {"emotion_type": "迷茫", "base_intensity": 0.5, "polarity": -1},
        }

    def _init_builtin_intensity_dict(self):
        """内置程度副词"""
        self.intensity_dict = {
            "极其": 2.0, "极度": 2.0, "特别": 1.8, "非常": 1.5,
            "十分": 1.4, "格外": 1.4, "很": 1.3, "挺": 1.2,
            "相当": 1.2, "比较": 1.1, "有点": 0.7, "有些": 0.7,
            "稍微": 0.6, "略微": 0.5,
        }

    def _init_builtin_emoji_dict(self):
        """内置表情符号"""
        self.emoji_dict = {
            "😄": {"emotion_type": "乐", "intensity": 0.8, "polarity": 1},
            "😊": {"emotion_type": "喜", "intensity": 0.6, "polarity": 1},
            "😍": {"emotion_type": "爱", "intensity": 0.9, "polarity": 1},
            "😢": {"emotion_type": "哀", "intensity": 0.7, "polarity": -1},
            "😭": {"emotion_type": "哀", "intensity": 0.9, "polarity": -1},
            "😠": {"emotion_type": "怒", "intensity": 0.7, "polarity": -1},
            "😡": {"emotion_type": "怒", "intensity": 0.9, "polarity": -1},
            "😨": {"emotion_type": "恐惧", "intensity": 0.7, "polarity": -1},
            "👍": {"emotion_type": "喜", "intensity": 0.6, "polarity": 1},
            "👎": {"emotion_type": "恶", "intensity": 0.6, "polarity": -1},
            "❤️": {"emotion_type": "爱", "intensity": 0.8, "polarity": 1},
            "💔": {"emotion_type": "哀", "intensity": 0.9, "polarity": -1},
        }

    def _init_builtin_slang_dict(self):
        """内置网络用语"""
        self.slang_dict = {
            "666": {"emotion_type": "喜", "intensity": 0.8, "polarity": 1},
            "牛逼": {"emotion_type": "喜", "intensity": 0.8, "polarity": 1},
            "yyds": {"emotion_type": "喜", "intensity": 0.9, "polarity": 1},
            "绝了": {"emotion_type": "喜", "intensity": 0.8, "polarity": 1},
            "无语": {"emotion_type": "恶", "intensity": 0.5, "polarity": -1},
            "破防": {"emotion_type": "哀", "intensity": 0.8, "polarity": -1},
            "裂开": {"emotion_type": "哀", "intensity": 0.8, "polarity": -1},
            "emmm": {"emotion_type": "困惑", "intensity": 0.3, "polarity": 0},
            "吃瓜": {"emotion_type": "好奇", "intensity": 0.4, "polarity": 0},
        }

    def analyze_semantic(self, text: str) -> EmotionResult:
        """
        使用 BGE 语义模型分析情感（GoEmotions 28类）
        当语义模型不可用时 fallback 到词典法
        """
        try:
            from memory.backends.memoria import _get_sentence_transformer, semantic_similarity
            model = _get_sentence_transformer()
            if model is None:
                return self.analyze(text)

            # 匹配28类情感模板
            scores = {}
            for emotion, template in EMOTION_TEMPLATES.items():
                scores[emotion] = semantic_similarity(text, template)

            best = max(scores, key=scores.get)
            best_score = scores[best]

            if best_score < 0.25:
                best = "neutral"
                best_score = 0.5

            # 查VAD坐标
            vad = VAD_MAP.get(best, [0.0, 0.0, 0.0])
            v, a, d = vad

            # 计算强度和极性
            intensity = min(1.0, best_score * 1.5)
            polarity = 1 if v > 0.2 else (-1 if v < -0.2 else 0)

            # 英文转中文标签
            label_map = {
                "admiration": "钦佩", "amusement": "娱乐", "anger": "愤怒",
                "annoyance": "烦恼", "approval": "认可", "caring": "关怀",
                "confusion": "困惑", "curiosity": "好奇", "desire": "渴望",
                "disappointment": "失望", "disapproval": "不赞同", "disgust": "厌恶",
                "embarrassment": "尴尬", "excitement": "兴奋", "fear": "恐惧",
                "gratitude": "感激", "grief": "悲痛", "joy": "快乐",
                "love": "爱", "nervousness": "紧张", "neutral": "中性",
                "optimism": "乐观", "pride": "自豪", "realization": "领悟",
                "relief": "解脱", "remorse": "懊悔", "sadness": "悲伤",
                "surprise": "惊讶",
            }

            return EmotionResult(
                emotion_type=best,
                emotion_label_cn=label_map.get(best, "中性"),
                intensity=intensity,
                polarity=polarity,
                valence=v,
                arousal=a,
                dominance=d,
                confidence=best_score,
            )
        except Exception:
            return self.analyze(text)  # fallback

    def analyze(self, text: str) -> EmotionResult:
        """
        分析文本情感（词典法）
        
        Args:
            text: 输入文本
            
        Returns:
            EmotionResult: 情感分析结果
        """
        if not text or not text.strip():
            return EmotionResult()

        # 1. 匹配情感词
        emotion_scores = {}  # emotion_type -> score
        matched_words = []

        for word, word_data in self.emotion_dict.items():
            if word in text:
                etype = word_data["emotion_type"]
                intensity = word_data["base_intensity"]
                polarity = word_data["polarity"]
                emotion_scores[etype] = emotion_scores.get(etype, 0) + intensity
                matched_words.append((word, intensity, polarity))

        # 2. 匹配表情符号
        for emoji, emoji_data in self.emoji_dict.items():
            if emoji in text:
                etype = emoji_data["emotion_type"]
                intensity = emoji_data["intensity"]
                polarity = emoji_data["polarity"]
                emotion_scores[etype] = emotion_scores.get(etype, 0) + intensity

        # 3. 匹配网络用语
        for slang, slang_data in self.slang_dict.items():
            if slang in text:
                etype = slang_data["emotion_type"]
                intensity = slang_data["intensity"]
                polarity = slang_data["polarity"]
                emotion_scores[etype] = emotion_scores.get(etype, 0) + intensity

        # 4. 确定情感类型（得分最高的）
        if not emotion_scores:
            return EmotionResult(emotion_type="中性", intensity=0.5, polarity=0, confidence=0.3)

        primary_emotion = max(emotion_scores, key=emotion_scores.get)
        total_score = sum(emotion_scores.values())

        # 5. 计算情感强度
        raw_intensity = total_score / len(emotion_scores) if emotion_scores else 0.5

        # 应用程度副词
        degree_factor = self._get_degree_factor(text)
        raw_intensity *= degree_factor

        # 应用标点符号增强
        punctuation_factor = self._get_punctuation_factor(text)
        raw_intensity *= punctuation_factor

        # 归一化到 0-1
        intensity = self._normalize_intensity(raw_intensity)

        # 6. 计算情感极性
        polarity = self._calculate_polarity(text, matched_words)

        # 7. 计算置信度
        confidence = self._calculate_confidence(len(matched_words), intensity)

        return EmotionResult(
            emotion_type=primary_emotion,
            intensity=intensity,
            polarity=polarity,
            confidence=confidence,
        )

    def _get_degree_factor(self, text: str) -> float:
        """获取程度副词因子"""
        max_factor = 1.0
        for adverb, factor in self.intensity_dict.items():
            if adverb in text:
                max_factor = max(max_factor, factor)
        return max_factor

    def _get_punctuation_factor(self, text: str) -> float:
        """获取标点符号增强因子"""
        factor = 1.0
        exclamation = text.count("!") + text.count("！")
        factor += exclamation * 0.15
        return min(factor, 1.5)

    def _normalize_intensity(self, raw: float) -> float:
        """归一化强度到 0-1"""
        if raw <= 0.5:
            return max(0.1, raw * 0.6)
        elif raw <= 1.5:
            return 0.3 + (raw - 0.5) * 0.4
        else:
            return min(0.95, 0.7 + (raw - 1.5) * 0.1)

    def _calculate_polarity(self, text: str, matched_words: list) -> int:
        """计算情感极性"""
        positive_score = 0.0
        negative_score = 0.0

        for _, intensity, polarity in matched_words:
            if polarity > 0:
                positive_score += intensity
            elif polarity < 0:
                negative_score += intensity

        # 检查否定词
        negation_count = sum(1 for nw in self.negation_words if nw in text)
        if negation_count % 2 == 1:  # 奇数个否定词，极性反转
            positive_score, negative_score = negative_score, positive_score

        # 判断极性
        threshold = 0.2
        if positive_score > negative_score * (1 + threshold):
            return 1
        elif negative_score > positive_score * (1 + threshold):
            return -1
        return 0

    def _calculate_confidence(self, word_count: int, intensity: float) -> float:
        """计算置信度"""
        confidence = 0.3  # 基础置信度
        confidence += min(word_count * 0.15, 0.4)  # 匹配词越多越可信
        if intensity > 0.7:
            confidence += 0.1
        return min(confidence, 1.0)
