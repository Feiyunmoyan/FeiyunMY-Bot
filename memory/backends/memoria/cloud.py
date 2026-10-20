"""
云层记忆管理（V2 混沌域）
负责存储低重要性记忆的"混沌域"，支持概率云检索和迁跃激活。

设计原则：
- 混沌域：记忆位置由概率分布描述，不是精确坐标
- 星体粒子流：入口算好 expire_at，自然消失，不占算力
- 清除曲线 = 1/(天数 + 偏移)：快速筛选，渐进衰减
- 差分规则：直接进入 vs 中层降级，不同清除曲线
- 懒加载：只加载未过期的记忆
"""
import os
import json
import time
import math
import random
import logging
from typing import List

logger = logging.getLogger(__name__)

# ─── 默认路径 ───
CLOUD_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "memoria"
)
CLOUD_FILE = os.path.join(CLOUD_DATA_DIR, "cloud.json")

# ─── 云层配置 ───
MAX_CLOUD_SIZE = 20000       # 云层最大容量
ACTIVATION_TOP_K = 3        # 每次检索最多从云层激活几条
CLOUD_QUERY_TOP_K = 10      # 云层检索候选数

# 清除曲线参数
CLEAR_BASE_DAYS = 30        # 基准存活天数（importance=0.3, 中性情感）
CLEAR_MAX_DAYS = 90         # 最长存活天数（情感极强或反复激活）
CLEAR_PROB_BASE = 1.0       # 清除概率公式分子
CLEAR_OFFSET_DIRECT = 1     # 直接进入的偏移量（快速筛选）
CLEAR_OFFSET_FROM_INNER = 3 # 中层降级的偏移量（多给机会）

# 类型衰减因子（同 ebbinghaus.py）
TYPE_DECAY = {
    "偏好": 0.6, "事实": 0.8, "状态": 1.0,
    "事件": 1.2, "查询": 2.0, "未知": 1.5,
}


class CloudEntry:
    """云层中的一条记忆"""
    
    def __init__(
        self,
        content: str,
        importance: float = 0.3,
        memory_type: str = "未知",
        v: float = 0.0,
        a: float = 0.0,
        d: float = 0.0,
        emotion_type: str = "neutral",
        emotion_label_cn: str = "中性",
        emotion_intensity: float = 0.5,
        role: str = "user",
        session_id: str = "",
        original_metadata: dict = None,
        source_note: str = "阈值拦截",
    ):
        now = time.time()
        self.cloud_id = f"cloud_{int(now)}_{random.randint(1000,9999)}"
        self.content = content
        self.importance = importance
        self.memory_type = memory_type
        self.v = v
        self.a = a
        self.d = d
        self.emotion_type = emotion_type
        self.emotion_label_cn = emotion_label_cn
        self.emotion_intensity = emotion_intensity
        self.role = role
        self.session_id = session_id
        self.original_metadata = original_metadata or {}
        self.source_note = source_note
        self.created_at = now
        self.updated_at = now
        self.activated_count = {"total": 0, "per_session": {}}
        self.last_activated = 0
        self.expire_at = self._calc_expire_at(importance, memory_type, v, a, d)

    @staticmethod
    def _calc_expire_at(importance, memory_type, v, a, d):
        """
        根据清除曲线计算 expire_at
        
        公式：
          1. 类型衰减因子 type_mod
          2. VAD 情感强度（模长）→ 情感因子
          3. 基准存活天数 = CLEAR_BASE_DAYS x importance
          4. 实际天数 = 基准 / (type_mod x emotion_mod)
          5. 截断到 [7, CLEAR_MAX_DAYS]
        
        返回值：过期时间戳（秒）
        """
        type_mod = TYPE_DECAY.get(memory_type, 1.5)
        vad_mag = math.sqrt(v*v + a*a + d*d)
        emotion_mod = 1.0 + vad_mag * 0.8  # 情感强 → 衰减慢 → 留更久
        
        # 重要性和类型为主导，情感为辅助
        base_days = CLEAR_BASE_DAYS * importance * 2.5
        base_days = max(5, base_days)
        # 类型衰减：查询类寿命短(÷2)，偏好类寿命长(÷0.6)
        # 情感增强：情感强烈的记忆活得久
        actual_days = base_days / (type_mod * 0.6) * emotion_mod
        actual_days = max(3, min(CLEAR_MAX_DAYS, actual_days))
        
        return time.time() + actual_days * 86400
    
    def to_dict(self) -> dict:
        return {
            "cloud_id": self.cloud_id,
            "content": self.content,
            "importance": self.importance,
            "memory_type": self.memory_type,
            "v": self.v,
            "a": self.a,
            "d": self.d,
            "emotion_type": self.emotion_type,
            "emotion_label_cn": self.emotion_label_cn,
            "emotion_intensity": self.emotion_intensity,
            "role": self.role,
            "session_id": self.session_id,
            "original_metadata": self.original_metadata,
            "source_note": self.source_note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "activated_count": self.activated_count["total"] if isinstance(self.activated_count, dict) else self.activated_count,
            "activated_per_session": self.activated_count["per_session"] if isinstance(self.activated_count, dict) else {},
            "last_activated": self.last_activated,
            "expire_at": self.expire_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CloudEntry":
        entry = cls(
            content=data.get("content", ""),
            importance=data.get("importance", 0.3),
            memory_type=data.get("memory_type", "未知"),
            v=data.get("v", 0.0),
            a=data.get("a", 0.0),
            d=data.get("d", 0.0),
            emotion_type=data.get("emotion_type", "neutral"),
            emotion_label_cn=data.get("emotion_label_cn", "中性"),
            emotion_intensity=data.get("emotion_intensity", 0.5),
            role=data.get("role", "user"),
            session_id=data.get("session_id", ""),
            original_metadata=data.get("original_metadata", {}),
            source_note=data.get("source_note", "阈值拦截"),
        )
        entry.cloud_id = data.get("cloud_id", entry.cloud_id)
        entry.created_at = data.get("created_at", entry.created_at)
        entry.updated_at = data.get("updated_at", entry.updated_at)
        entry.activated_count = data.get("activated_count", 0)
        entry.last_activated = data.get("last_activated", 0)
        entry.expire_at = data.get("expire_at", entry.expire_at)
        return entry


class CloudLayer:
    """
    云层管理器
    
    职责：
    1. 存储低重要性记忆（阈值拦截 / 艾宾浩斯清理）
    2. 按语义关键词 + 情感 + 时间检索可激活的候选
    3. 执行迁跃判断（should_activate）
    4. 管理云层容量（FIFO 淘汰最旧的）
    """
    
    def __init__(self, cloud_path: str = None, on_graduate=None):
        """
        Args:
            cloud_path: 云层 JSON 文件路径
            on_graduate: 毕业回调函数(cloud_entry) -> None
                         当一条记忆被激活次数 >= 3 时调用，写入内层 ChromaDB
        """
        self.cloud_path = cloud_path or CLOUD_FILE
        self._on_graduate = on_graduate
        self._entries: List[CloudEntry] = []
        self._load()
    
    # ─── 持久化 ───
    
    def _load(self):
        """从 JSON 文件加载云层（懒加载：只保留未过期的）"""
        try:
            if os.path.exists(self.cloud_path):
                with open(self.cloud_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                now = time.time()
                # 懒加载：只保留未过期的
                all_entries = [CloudEntry.from_dict(item) for item in data]
                self._entries = [e for e in all_entries if e.expire_at > now]
                expired_count = len(all_entries) - len(self._entries)
                if expired_count > 0:
                    logger.info(f"云层懒加载: 过滤 {expired_count} 条过期记忆，保留 {len(self._entries)} 条")
                    self._save()  # 清理过期文件
                else:
                    logger.info(f"云层加载完成: {len(self._entries)} 条记忆")
            else:
                os.makedirs(os.path.dirname(self.cloud_path), exist_ok=True)
                self._entries = []
                logger.info("云层为空，已创建新云层")
        except Exception as e:
            logger.warning(f"云层加载失败，使用空云层: {e}")
            self._entries = []
    
    def _save(self):
        """保存云层到 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(self.cloud_path), exist_ok=True)
            with open(self.cloud_path, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self._entries], f,
                          ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"云层保存失败: {e}")
    
    # ─── 核心操作 ───
    
    def add(self, content: str, importance: float = 0.3,
            memory_type: str = "未知",
            v: float = 0.0, a: float = 0.0, d: float = 0.0,
            emotion_type: str = "neutral",
            emotion_label_cn: str = "中性",
            emotion_intensity: float = 0.5,
            role: str = "user",
            session_id: str = "",
            original_metadata: dict = None,
            source_note: str = "阈值拦截") -> str:
        """
        向云层添加一条记忆
        
        根据清除曲线计算 expire_at：
        - 直接进入（阈值拦截）：快速筛选（偏移=1）
        - 中层降级（艾宾浩斯）：多给机会（偏移=3）
        
        Returns:
            cloud_id: 云层记忆 ID
        """
        entry = CloudEntry(
            content=content,
            importance=importance,
            memory_type=memory_type,
            v=v, a=a, d=d,
            emotion_type=emotion_type,
            emotion_label_cn=emotion_label_cn,
            emotion_intensity=emotion_intensity,
            role=role,
            session_id=session_id,
            original_metadata=original_metadata or {},
            source_note=source_note,
        )
        
        self._entries.append(entry)
        
        # 容量管理：超出时淘汰最旧的
        if len(self._entries) > MAX_CLOUD_SIZE:
            self._entries.sort(key=lambda e: e.expire_at)
            self._entries = self._entries[:MAX_CLOUD_SIZE]
            logger.info(f"云层容量超限，按 expire_at 淘汰 {len(self._entries)} 条")
        
        self._save()
        
        logger.info(
            f"云层新增: id={entry.cloud_id}, "
            f"importance={importance:.3f}, type={memory_type}, "
            f"source={source_note}"
        )
        return entry.cloud_id
    
    def query(self, query_text: str, top_k: int = CLOUD_QUERY_TOP_K) -> List[dict]:
        """
        在云层中检索可激活的候选记忆
        
        当前使用关键词匹配 + VAD 情感距离 + 时间新鲜度
        （后续可升级为 BGE 轻量语义检索）
        
        Returns:
            候选列表，每条包含内容、情感、时间等
        """
        if not self._entries:
            return []
        
        # 关键词分词（简单按空格/逗号分割）
        query_words = set()
        for sep in [" ", "，", "。", "？", "！", "的", "了", "是", "在", "有",
                     "我", "你", "他", "她", "它", "们", "不", "也", "就", "都"]:
            parts = query_text.split(sep)
            for p in parts:
                p = p.strip()
                if len(p) >= 2:  # 只保留长度 >= 2 的词汇
                    query_words.add(p.lower())
        
        scored = []
        now_ts = time.time()
        for entry in self._entries:
            # 自然过期检查：清除概率 = 1/(天数 + 偏移)
            age_days = max(0, (now_ts - entry.created_at) / 86400)
            offset = CLEAR_OFFSET_DIRECT if entry.source_note != "艾宾浩斯清理" else CLEAR_OFFSET_FROM_INNER
            clear_prob = CLEAR_PROB_BASE / (age_days + offset)
            # 如果随机命中清除概率，跳过这条（自然消失）
            if random.random() < min(0.95, clear_prob * 0.1):  # 10% 缩放避免过于激进
                continue
            
            # 计算时间衰减（越新的候选权重越高）
            time_score = math.exp(-age_days * 0.15)  # 半衰期约 4.6 天
            
            # 计算关键词匹配分
            content_lower = entry.content.lower()
            keyword_matches = sum(1 for w in query_words if w in content_lower)
            keyword_score = min(1.0, keyword_matches / max(len(query_words), 1) * 3)
            
            # 计算情感距离（VAD 模长越大 = 情感越强烈）
            vad_magnitude = math.sqrt(entry.v**2 + entry.a**2 + entry.d**2)
            emotion_score = min(1.0, vad_magnitude * 1.5)
            
            # 综合分 = 关键词 × 0.5 + 情感 × 0.3 + 时间 × 0.2
            # 关键词命中是强信号，情感强度是辅助，时间是背景
            combined = keyword_score * 0.5 + emotion_score * 0.3 + time_score * 0.2
            
            # 已被激活过的记忆权重略降（防止同一条反复激活）
            ac_total = entry.activated_count["total"]
            if ac_total > 0:
                combined *= max(0.5, 1.0 - ac_total * 0.1)
            
            if combined > 0:
                scored.append({
                    "entry": entry,
                    "score": combined,
                    "keyword_score": keyword_score,
                    "emotion_score": emotion_score,
                    "time_score": time_score,
                })
        
        # 按综合分排序，取 top_k
        scored.sort(key=lambda x: x["score"], reverse=True)
        candidates = scored[:top_k]
        
        results = []
        for c in candidates:
            entry = c["entry"]
            results.append({
                "id": entry.cloud_id,
                "content": entry.content,
                "metadata": {
                    "memory_id": entry.cloud_id,
                    "role": entry.role,
                    "content_preview": entry.content[:200],
                    "created_at": entry.created_at,
                    "importance": entry.importance,
                    "memory_type": entry.memory_type,
                    "emotion_type": entry.emotion_type,
                    "emotion_label_cn": entry.emotion_label_cn,
                    "v": entry.v, "a": entry.a, "d": entry.d,
                    "emotion_intensity": entry.emotion_intensity,
                    "session_id": entry.session_id,
                },
                "cloud_score": round(c["score"], 3),
                "keyword_score": round(c["keyword_score"], 3),
                "emotion_score": round(c["emotion_score"], 3),
                "time_score": round(c["time_score"], 3),
                "_source": "cloud",
            })
        
        return results
    
    def should_activate(self, cloud_mem: dict, query_text: str) -> bool:
        """
        判断一条云层记忆是否应该被激活（迁跃回内层）
        
        激活条件（四维交叉）：
        1. 语义关键词匹配 >= 1 个 → 强激活信号
        2. 情感强度高（VAD 模长 > 0.5）→ 辅助激活
        3. 时间新鲜（7 天内）→ 加分
        4. 随机机遇（~5%）→ 让"弱连接"也有机会
        """
        # 条件 1：关键词匹配
        keyword_hit = cloud_mem.get("keyword_score", 0) > 0
        
        # 条件 2：情感强度
        meta = cloud_mem.get("metadata", {})
        v = meta.get("v", 0)
        a = meta.get("a", 0)
        d = meta.get("d", 0)
        vad_mag = math.sqrt(v**2 + a**2 + d**2)
        strong_emotion = vad_mag > 0.5
        
        # 条件 3：时间新鲜度
        created_at = meta.get("created_at", 0)
        age_days = max(0, (time.time() - created_at) / 86400)
        is_recent = age_days < 7
        
        # 条件 4：总评分 > 阈值
        cloud_score = cloud_mem.get("cloud_score", 0)
        score_ok = cloud_score > 0.15
        
        # —— 激活判断 ——
        # 强激活：有关键词匹配 + 情感强 + 时间近
        if keyword_hit and strong_emotion and is_recent and score_ok:
            return True
        
        # 中等激活：有关键词匹配 + 时间近
        if keyword_hit and is_recent and score_ok:
            return True
        
        # 弱激活：只有情感强（无关键词匹配），小概率
        if strong_emotion and score_ok and random.random() < 0.1:
            return True
        
        # 随机机遇：纯"弱连接"（日常碎片被偶然想起）
        if score_ok and random.random() < 0.03:
            return True
        
        return False
    
    def activate(self, cloud_mem: dict) -> dict:
        """
        执行迁跃：从云层激活一条记忆，返回可注入内层的格式
        
        如果 activated_count >= 3，触发毕业回调：
        - 将记忆写入内层 ChromaDB
        - 从云层移除
        
        Returns:
            和 query() 返回格式一致的记忆字典（带 _source 标记）
        """
        entry_id = cloud_mem.get("id", "")
        entry_obj = None
        
        # 更新云层中的激活计数
        for entry in self._entries:
            if entry.cloud_id == entry_id:
                session_id = cloud_mem.get("metadata", {}).get("session_id", "default")
                entry.activated_count["total"] += 1
                entry.activated_count["per_session"][session_id] = (
                    entry.activated_count["per_session"].get(session_id, 0) + 1
                )
                entry.last_activated = time.time()
                entry_obj = entry
                break
        
        # 毕业判断：
        #   - 同会话激活 >= 3 次
        #   - 或跨会话激活（不同会话 >= 2 个）
        if entry_obj and (
            entry_obj.activated_count["total"] >= 3
            or len(entry_obj.activated_count["per_session"]) >= 2
        ):
            if self._on_graduate:
                logger.info(
                    f"云层毕业: id={entry_id}, "
                    f"content='{entry_obj.content[:40]}', "
                    f"激活次数={entry_obj.activated_count['total']}, 跨会话={len(entry_obj.activated_count['per_session'])}"
                )
                self._on_graduate(entry_obj)
                # 从云层移除
                self._entries = [e for e in self._entries if e.cloud_id != entry_id]
                self._save()
            
            # 返回激活格式（标记为毕业）
            meta = cloud_mem.get("metadata", {})
            result = {
                "id": meta.get("memory_id", entry_id),
                "role": meta.get("role", "user"),
                "content": cloud_mem.get("content", ""),
                "metadata": meta,
                "relevance": cloud_mem.get("cloud_score", 0.3),
                "importance": meta.get("importance", 0.3),
                "memory_type": meta.get("memory_type", "未知"),
                "rank_score": cloud_mem.get("cloud_score", 0.3) + 0.2,
                "created_at": meta.get("created_at", 0),
                "updated_at": meta.get("created_at", 0),
                "_source": "cloud_graduated",
            }
            logger.info(f"云层毕业完成: id={entry_id}, 已写入中层")
            return result
        
        self._save()
        
        meta = cloud_mem.get("metadata", {})
        result = {
            "id": meta.get("memory_id", entry_id),
            "role": meta.get("role", "user"),
            "content": cloud_mem.get("content", ""),
            "metadata": meta,
            "relevance": cloud_mem.get("cloud_score", 0.3),
            "importance": meta.get("importance", 0.3),
            "memory_type": meta.get("memory_type", "未知"),
            "rank_score": cloud_mem.get("cloud_score", 0.3),
            "created_at": meta.get("created_at", 0),
            "updated_at": meta.get("created_at", 0),
            "_source": "cloud_activated",
        }
        
        activated_count = 0
        for e in self._entries:
            if e.cloud_id == entry_id:
                activated_count = e.activated_count
                break
        
        logger.info(
            f"云层迁跃激活: id={entry_id}, "
            f"content=\"{cloud_mem.get('content', '')[:40]}\", "
            f"score={cloud_mem.get('cloud_score', 0):.3f}, "
            f"激活次数={activated_count}"
        )
        
        return result
    
    def get_cloud_count(self) -> int:
        """获取云层中的记忆数量"""
        return len(self._entries)
    
    def cleanup_expired(self, max_age_days: float = None) -> int:
        """
        统一清理入口：清除概率 + expire_at 双机制
        
        两阶段设计：
        稳定期 (expire_at 之前)：
          - 只走清除概率曲线
          - 清除概率 P = 1/(天数 + 偏移)
          - 直接进入偏移=1（快速筛选）
          - 中层降级偏移=3（多给机会）
        
        结束期 (expire_at 之后)：
          - 清除概率 + expire_at 双机制并行
          - 谁先到听谁的
          - 最多再活 7 天
        
        Returns:
            清理条数
        """
        before = len(self._entries)
        now_ts = time.time()
        
        still_alive = []
        removed_count = 0
        for entry in self._entries:
            age_days = max(0, (now_ts - entry.created_at) / 86400)
            offset = CLEAR_OFFSET_DIRECT if entry.source_note != "艾宾浩斯清理" else CLEAR_OFFSET_FROM_INNER
            clear_prob = CLEAR_PROB_BASE / (age_days + offset)
            
            if entry.expire_at <= now_ts:
                # 结束期：双机制并行
                # 清除概率已较高，且 expire_at 已到
                end_stage_days = (now_ts - entry.expire_at) / 86400
                if end_stage_days >= 7 or random.random() < clear_prob * 0.3:
                    removed_count += 1
                else:
                    still_alive.append(entry)
            else:
                # 稳定期：只走清除概率
                if random.random() < clear_prob * 0.03:  # 3% 缩放，温和筛选
                    removed_count += 1
                else:
                    still_alive.append(entry)
        
        self._entries = still_alive
        if removed_count > 0:
            self._save()
            logger.info(f"云层清理: 移除 {removed_count} 条，剩余 {len(self._entries)} 条")
        return removed_count
    
    def get_recent(self, n: int = 10) -> List[dict]:
        """获取云层中最新的 N 条记忆（用于外部查看）"""
        sorted_entries = sorted(
            self._entries, key=lambda e: e.created_at, reverse=True
        )[:n]
        return [e.to_dict() for e in sorted_entries]
    
    def clear(self):
        """清空云层"""
        self._entries = []
        self._save()
        logger.info("云层已清空")
