"""
记忆类型识别器
将记忆文本分为5种类型：偏好/事实/状态/事件/查询
BGE语义匹配为主，字典法留作降级端口
"""
import logging

logger = logging.getLogger(__name__)

# BGE语义模板（主方案）
TYPE_TEMPLATES = {
    "偏好": [
        "这是用户的个人喜好或兴趣",
        "用户表达了对某事物的偏好",
        "这是用户喜欢或不喜欢的东西",
        "用户对某事物有强烈的感受",
    ],
    "事实": [
        "这是关于用户的一个事实性信息",
        "用户陈述了一个客观事实",
        "这是用户的个人信息或属性",
        "这是一个客观存在的状况",
    ],
    "状态": [
        "这是用户当前的状态或感受",
        "用户正在经历某种状态",
        "这是用户近期的情绪或身体状况",
        "用户描述了当下的体验",
    ],
    "事件": [
        "这是用户经历或做过的事情",
        "这是已经发生的一个事件",
        "用户参与了某项活动",
        "这是一个过去发生的具体事情",
    ],
    "查询": [
        "这是用户的一次信息查询或搜索",
        "用户询问了某个信息",
        "这是用户临时性的查询需求",
        "用户了解某个具体信息",
    ],
    "未知": [
        "这是一句简单的日常寒暄",
        "这是没有具体信息的客套话",
    ],
}

# 字典法（降级用）
TYPE_KEYWORDS = {
    "偏好": ["喜欢", "爱", "讨厌", "不喜欢", "感兴趣", "最爱", "推荐"],
    "事实": ["住在", "是", "在", "有", "毕业于", "今年", "岁", "工作"],
    "状态": ["最近", "正在", "感觉", "觉得", "有点", "好累", "好烦"],
    "事件": ["去了", "做了", "买了", "看了", "吃了", "玩了", "遇到"],
    "查询": ["查了", "问了", "搜了", "查一下", "想知道", "什么是"],
}


def classify_by_keywords(content: str) -> tuple:
    """字典法快速分类（降级用）"""
    scores = {t: 0 for t in TYPE_TEMPLATES}
    for type_name, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in content:
                scores[type_name] = scores.get(type_name, 0) + 1
    if max(scores.values()) == 0:
        return "未知", 0.0
    best = max(scores, key=scores.get)
    confidence = min(1.0, scores[best] / 3)
    return best, confidence


def classify_by_bge(content: str, similarity_func) -> tuple:
    """BGE语义匹配（主方案）"""
    best_type = "未知"
    best_score = 0.0
    
    for type_name, templates in TYPE_TEMPLATES.items():
        # 取该类下所有模板的最高分
        type_score = max(similarity_func(content, t) for t in templates)
        if type_score > best_score:
            best_score = type_score
            best_type = type_name
    
    confidence = min(1.0, best_score * 1.2)
    return best_type, confidence
