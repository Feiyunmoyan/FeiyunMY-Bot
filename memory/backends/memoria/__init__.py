"""
MemoriaDB 长期记忆后端
集成：情感分析 + 重要性评分 + ChromaDB向量检索 + 艾宾浩斯遗忘曲线
"""
import os
import uuid
import time
import logging
from typing import List, Dict, Any, Optional

import chromadb
import math
import random

from memory import MemoryBridge
from memory.backends.memoria.emotion import EmotionAnalyzer
from memory.backends.memoria.emotion_fusion import EmotionFusion
from memory.backends.memoria.importance import ImportanceScorer
from memory.backends.memoria.ebbinghaus import EbbinghausManager
from memory.backends.memoria.cloud import CloudLayer

logger = logging.getLogger(__name__)

# ─── BGE 语义模型 Embedding ───

BGE_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "memoria", "bge-model"
)

_SENTENCE_TRANSFORMER = None


def _get_sentence_transformer():
    """懒加载 BGE 模型（只加载一次）"""
    global _SENTENCE_TRANSFORMER
    if _SENTENCE_TRANSFORMER is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SENTENCE_TRANSFORMER = SentenceTransformer(
                BGE_MODEL_PATH,
                device="cpu",
                local_files_only=True,
            )
            logger.info(f"BGE 语义模型加载完成: {BGE_MODEL_PATH}")
        except Exception as e:
            logger.warning(f"BGE 模型加载失败，使用默认 embedding: {e}")
            return None
    return _SENTENCE_TRANSFORMER


class BGEEmbeddingFunction:
    """BGE 中文 Embedding 函数（用于 ChromaDB）"""
    def __init__(self):
        self.model = _get_sentence_transformer()

    def __call__(self, texts):
        if self.model is None:
            return None  # ChromaDB 会使用默认 embedding
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def is_available(self) -> bool:
        return self.model is not None


def semantic_similarity(text1: str, text2: str) -> float:
    """计算两段文本的语义相似度（使用 BGE 模型）"""
    model = _get_sentence_transformer()
    if model is None:
        return 0.0
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        emb = model.encode([text1, text2], normalize_embeddings=True)
        return float(cosine_similarity([emb[0]], [emb[1]])[0][0])
    except Exception:
        return 0.0


class MemoriaMemory(MemoryBridge):
    """
    MemoriaDB 长期记忆后端
    
    功能：
    - 情感分析：自动分析记忆的情感类型、强度、极性
    - 重要性评分：评估记忆的重要性 (0-1)
    - 向量存储：使用 ChromaDB 存储和检索
    - 遗忘曲线：基于艾宾浩斯曲线定时清理低保留率记忆
    """

    def __init__(
        self,
        chromadb_path: str = None,
        retrieval_top_k: int = 5,
        ebbinghaus_config: Optional[Dict[str, Any]] = None,
        emotion_enabled: bool = True,
        min_importance_score: float = 0.3,
    ):
        if chromadb_path is None:
            chromadb_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "data", "memoria", "chromadb"
            )
        os.makedirs(chromadb_path, exist_ok=True)

        logger.info(f"ChromaDB 路径: {chromadb_path}")

        # 使用 BGE 中文 embedding（如果可用）
        self.bge_embedding = BGEEmbeddingFunction()
        embedding_func = self.bge_embedding if self.bge_embedding.is_available else None

        self.chroma_client = chromadb.PersistentClient(path=chromadb_path)
        self.collection_name = "memories"
        self.collection = self._get_or_create_collection(embedding_func)

        self.retrieval_top_k = retrieval_top_k
        self.emotion_enabled = emotion_enabled
        self.min_importance_score = min_importance_score

        self.emotion_analyzer = EmotionAnalyzer() if emotion_enabled else None
        self.emotion_fusion = EmotionFusion() if emotion_enabled else None
        self.importance_scorer = ImportanceScorer(min_score=min_importance_score)

        eb_config = ebbinghaus_config or {}
        self.ebbinghaus = EbbinghausManager(
            default_retention=eb_config.get("default_retention", 0.8),
            decay_factor=eb_config.get("decay_factor", 0.1),
            cleanup_threshold=eb_config.get("cleanup_threshold", 0.3),
            target_capacity=eb_config.get("target_capacity", 750000),
        )

        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._load_metadata_cache()

        # V2 云层初始化（混沌域）
        cloud_path = os.path.join(
            os.path.dirname(chromadb_path), "cloud.json"
        )
        self.cloud = CloudLayer(
            cloud_path=cloud_path,
            on_graduate=self._cloud_on_graduate,
        )
        logger.info(f"云层初始化完成，当前 {self.cloud.get_cloud_count()} 条记忆")

        logger.info(
            f"Memoria 记忆后端初始化完成: "
            f"emotion={emotion_enabled}, top_k={retrieval_top_k}, "
            f"chroma_docs={self.collection.count()}"
        )

    def _get_or_create_collection(self, embedding_function=None):
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            logger.info(f"加载已有 ChromaDB 集合: {self.collection_name}")
        except Exception:
            collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_function,
            )
            logger.info(f"创建新 ChromaDB 集合: {self.collection_name}")
        return collection

    def _load_metadata_cache(self):
        try:
            results = self.collection.get(include=["metadatas"])
            if results and results.get("metadatas"):
                for i, meta in enumerate(results["metadatas"]):
                    mem_id = meta.get("memory_id", "")
                    if mem_id:
                        self._metadata_cache[mem_id] = meta
                logger.info(f"加载 {len(self._metadata_cache)} 条元数据缓存")
        except Exception as e:
            logger.warning(f"加载元数据缓存失败: {e}")

    def _dedup_threshold(self, content: str) -> float:
        """动态去重阈值：短文本严格，长文本宽松"""
        length = len(content)
        if length < 20:
            threshold = 0.95 - (length / 20) * 0.03
        elif length < 100:
            threshold = 0.89 - (length / 100) * 0.09
        else:
            threshold = 0.80
        
        # 包含关键实体（数字/人名等）→ 提高阈值，防止误合并
        import re
        if re.search(r'\d+|[\u4e00-\u9fa5]{2,4}(?:说|告诉|提到)', content):
            threshold += 0.03
        
        return threshold

    def _dynamic_threshold(self, v=0.0, a=0.0, d=0.0, memory_type="未知", created_at=0.0) -> float:
        """动态阈值准入：VAD偏移 + 类型偏移 + 时间震荡 + 年龄惩罚"""
        BASE = 0.35
        AMPLITUDE = 0.15
        PERIOD = 2 * math.pi / 3600  # 周期1小时
        
        # 日期驱动的随机相位（同一天一致，每天不同）
        day_seed = int(time.time() / 86400)
        start_phase = (day_seed * 0.618) % (2 * math.pi)
        
        # VAD连续偏移
        vad_offset = (-v * 0.08 - a * 0.06 - d * 0.04)
        
        # 类型偏移
        type_offset = {"偏好": -0.08, "事实": -0.04, "状态": 0.0,
                       "事件": 0.05, "查询": 0.10}.get(memory_type, 0.0)
        
        # 时间震荡（会话内运行时间 + 每日随机相位）
        time_wave = AMPLITUDE * math.sin(time.time() * PERIOD + start_phase)
        
        # 年龄惩罚
        age_days = max(0, (time.time() - created_at) / 86400) if created_at > 0 else 0
        age_penalty = min(0.1, age_days * 0.005)
        
        threshold = BASE + vad_offset + type_offset + time_wave + age_penalty
        return max(0.2, min(0.7, threshold))

    def add(self, role: str, content: str, metadata: dict = None) -> str:
        if not content or not content.strip():
            logger.warning("跳过空记忆")
            return ""

        # ─── 第0层：去重检测 ───
        try:
            similar = self.collection.query(
                query_texts=[content],
                n_results=1,
                include=["metadatas", "distances"],
            )
            if similar and similar.get("distances") and similar["distances"][0]:
                distance = similar["distances"][0][0]
                similarity = 1.0 - distance
                
                # 动态阈值：短文本严格，长文本宽松
                threshold = self._dedup_threshold(content)
                
                if similarity >= threshold:
                    # 高度相似 → 更新旧记录
                    old_meta = similar["metadatas"][0][0]
                    old_id = old_meta.get("memory_id", "")
                    
                    if old_id and old_id in self._metadata_cache:
                        old_meta["content_preview"] = content[:200]
                        old_meta["updated_at"] = time.time()
                        old_meta["mention_count"] = old_meta.get("mention_count", 0) + 1
                        old_meta["importance"] = min(1.0, old_meta.get("importance", 0.5) + 0.02)
                        self._metadata_cache[old_id] = old_meta
                        
                        # 同步写回 ChromaDB（防止重启后丢失）
                        try:
                            self.collection.update(
                                ids=[old_id],
                                metadatas=[old_meta]
                            )
                        except Exception as e:
                            logger.warning(f"去重合并写回失败: {e}")
                        
                        logger.info(f"去重合并: id={old_id}, 提及+1, 相似度={similarity:.3f}")
                        return old_id
        except Exception as e:
            logger.debug(f"去重检测失败（不影响正常存储）: {e}")

        memory_id = str(uuid.uuid4())[:12]
        now = time.time()

        # ─── 第1层：记忆类型识别 ───
        memory_type = "未知"
        type_confidence = 0.0
        try:
            from memory.backends.memoria.memory_type import classify_by_bge, classify_by_keywords
            if self.bge_embedding.is_available:
                from memory.backends.memoria import semantic_similarity
                memory_type, type_confidence = classify_by_bge(content, semantic_similarity)
            else:
                memory_type, type_confidence = classify_by_keywords(content)
        except Exception as e:
            logger.debug(f"类型识别失败: {e}")

        emotion_result = None
        emotion_data = {}
        if self.emotion_enabled and self.emotion_analyzer:
            # 用用户原文做情感分析（更准确），没有则用总结文本
            emotion_text = (metadata or {}).get("user_message", content)

            # BGE 语义情感分析（可用时），否则 fallback 到词典法
            if self.bge_embedding.is_available:
                emotion_result = self.emotion_analyzer.analyze_semantic(emotion_text)
            else:
                emotion_result = self.emotion_analyzer.analyze(emotion_text)
            emotion_data = emotion_result.to_dict()

            # 多轮情感融合：结合历史情感偏置修正当前情感
            session_id = (metadata or {}).get("session_id", "")
            if session_id and self.emotion_fusion:
                fused = self.emotion_fusion.fuse(
                    session_id=session_id,
                    emotion_type=emotion_data["emotion_type"],
                    intensity=emotion_data["intensity"],
                    polarity=emotion_data["polarity"],
                    text=emotion_text,
                )
                emotion_data = {
                    "emotion_type": fused["emotion_type"],
                    "intensity": fused["intensity"],
                    "polarity": fused["polarity"],
                    "confidence": fused["confidence"],
                    "conflict_detected": fused["conflict_detected"],
                }
        else:
            emotion_data = {"emotion_type": "neutral", "emotion_label_cn": "中性", 
                            "intensity": 0.5, "polarity": 0, "confidence": 0.5,
                            "v": 0.0, "a": 0.0, "d": 0.0}

        # ─── 第3层：重要性计算 ───
        try:
            # 1. 获取语义分和规则分
            if self.bge_embedding.is_available:
                imp = self.importance_scorer.score_semantic(content, emotion_intensity=0.5)
            else:
                imp = self.importance_scorer.score(content, emotion_intensity=0.5)
            semantic_score = imp.get("semantic_score", imp.get("overall_score", 0.3))
            rule_score = imp.get("rule_score", imp.get("overall_score", 0.3))

            # 2. 类型基准值
            type_base = {"偏好": 0.7, "事实": 0.6, "状态": 0.5, "事件": 0.4, "查询": 0.2, "未知": 0.15}
            base = type_base.get(memory_type, 0.3)

            # 3. VAD情感加权
            v = emotion_data.get("v", 0.0)
            a = emotion_data.get("a", 0.0)
            d = emotion_data.get("d", 0.0)
            vad_weight = abs(v) * 0.4 + a * 0.3 + abs(d) * 0.3

            # 4. 提及次数加权
            mention_count = 1
            mention_weight = 0.1 * math.log(mention_count + 1)

            # 5. 综合计算
            if self.bge_embedding.is_available:
                importance_score = base * 0.3 + semantic_score * 0.4 + vad_weight * 0.2 + mention_weight * 0.1
            else:
                importance_score = base * 0.4 + rule_score * 0.4 + vad_weight * 0.1 + mention_weight * 0.1

            # 6. 时效性降权（查询/事件类）
            if memory_type in ("查询", "事件"):
                importance_score *= 0.7

            importance_score = min(1.0, max(0.0, importance_score))
        except Exception as e:
            logger.warning(f"重要性计算失败，使用默认值: {e}")
            importance_score = 0.3

        # ─── 第4层：动态阈值准入 ───
        try:
            threshold = self._dynamic_threshold(
                v=v, a=a, d=d,
                memory_type=memory_type,
                created_at=now,
            )
            
            # 存储判断
            if importance_score >= threshold:
                pass  # 通过
            elif semantic_score > 0.3 and random.random() < (importance_score / threshold) * 0.15:
                importance_score = max(0.3, importance_score * 0.9)
                logger.info(f"随机存入: importance={importance_score:.3f} < threshold={threshold:.3f}")
            else:
                # V4: 送入云层（不丢弃）
                self.cloud.add(
                    content=content,
                    importance=importance_score,
                    memory_type=memory_type,
                    v=emotion_data.get("v", 0.0),
                    a=emotion_data.get("a", 0.0),
                    d=emotion_data.get("d", 0.0),
                    emotion_type=emotion_data.get("emotion_type", "neutral"),
                    emotion_label_cn=emotion_data.get("emotion_label_cn", "中性"),
                    emotion_intensity=emotion_data.get("intensity", 0.5),
                    role=role,
                    session_id=(metadata or {}).get("session_id", ""),
                    original_metadata=(metadata or {}),
                    source_note="阈值拦截",
                )
                logger.info(f"阈值拦截 -> 送入云层: importance={importance_score:.3f} < threshold={threshold:.3f}")
                return ""
        except Exception as e:
            logger.debug(f"动态阈值判断失败（不影响存储）: {e}")

        initial_retention = self.ebbinghaus.calculate_retention(
            now, importance_score,
            emotion_intensity=emotion_data.get("intensity", 0.5),
            total_memories=len(self._metadata_cache),
            v=emotion_data.get("v", 0.0),
            a=emotion_data.get("a", 0.0),
            d=emotion_data.get("d", 0.0),
            memory_type=memory_type,
            mention_count=1,
        )

        full_metadata = {
            "memory_id": memory_id,
            "role": role,
            "content_preview": content[:200],
            "created_at": now,
            "updated_at": now,
            "importance": importance_score,
            "initial_retention": initial_retention,
            "access_count": 0,
            "mention_count": 1,
            "memory_type": memory_type,
            "emotion_type": emotion_data.get("emotion_type", "neutral"),
            "emotion_label_cn": emotion_data.get("emotion_label_cn", "中性"),
            "emotion_intensity": emotion_data.get("intensity", 0.5),
            "v": emotion_data.get("v", 0.0),
            "a": emotion_data.get("a", 0.0),
            "d": emotion_data.get("d", 0.0),
            "emotion_polarity": emotion_data.get("polarity", 0),
            "emotion_confidence": emotion_data.get("confidence", 0.5),
            "session_id": (metadata or {}).get("session_id", ""),
        }

        try:
            self.collection.add(
                documents=[content],
                metadatas=[full_metadata],
                ids=[memory_id],
            )
            self._metadata_cache[memory_id] = full_metadata
            logger.info(
                f"记忆已存储: id={memory_id}, importance={importance_score:.3f}, "
                f"emotion={emotion_data.get('emotion_type')}, "
                f"retention={initial_retention:.3f}, access=0"
            )
        except Exception as e:
            logger.error(f"存储记忆失败: {e}")
            return ""

        return memory_id

    def cleanup_expired(self) -> int:
        """清理过期记忆（retention < threshold）"""
        try:
            results = self.collection.get(include=["metadatas"])
            if not results or not results.get("metadatas"):
                return 0

            now = time.time()
            count = 0
            to_delete = []

            for meta in results["metadatas"]:
                mem_id = meta.get("memory_id", "")
                created_at = meta.get("created_at", now)
                importance = meta.get("importance", 0.5)
                access_count = meta.get("access_count", 0)
                memory_type = meta.get("memory_type", "")
                mention_count = meta.get("mention_count", 1)
                v = meta.get("v", 0.0)
                a = meta.get("a", 0.0)
                d = meta.get("d", 0.0)
                emotion_intensity = meta.get("emotion_intensity", 0.5)

                if self.ebbinghaus.should_cleanup(
                    created_at, importance, access_count, emotion_intensity,
                    len(self._metadata_cache),
                    v=v, a=a, d=d,
                    memory_type=memory_type,
                    mention_count=mention_count,
                ):
                    to_delete.append(mem_id)
                    count += 1

            if to_delete:
                # V4: 删除前获取完整文档，送入云层
                try:
                    docs_result = self.collection.get(
                        ids=to_delete,
                        include=["documents", "metadatas"]
                    )
                    cloud_count = 0
                    for i, mid in enumerate(to_delete):
                        doc_content = ""
                        if docs_result and docs_result.get("documents"):
                            try:
                                doc_content = docs_result["documents"][i]
                            except (IndexError, TypeError):
                                doc_content = ""
                        meta = self._metadata_cache.get(mid, {})
                        if doc_content:
                            self.cloud.add(
                                content=doc_content,
                                importance=meta.get("importance", 0.3),
                                memory_type=meta.get("memory_type", "未知"),
                                v=meta.get("v", 0.0),
                                a=meta.get("a", 0.0),
                                d=meta.get("d", 0.0),
                                emotion_type=meta.get("emotion_type", "neutral"),
                                emotion_label_cn=meta.get("emotion_label_cn", "中性"),
                                emotion_intensity=meta.get("emotion_intensity", 0.5),
                                role=meta.get("role", "user"),
                                session_id=meta.get("session_id", ""),
                                original_metadata=meta,
                                source_note="艾宾浩斯清理",
                            )
                            cloud_count += 1
                except Exception as e:
                    logger.warning(f"艾宾浩斯清理-云层保存失败: {e}")
                    cloud_count = 0
                
                log_items = []
                for mid in to_delete:
                    meta = self._metadata_cache.get(mid, {})
                    preview = meta.get("content_preview", "")[:40]
                    imp = meta.get("importance", 0)
                    mem_type = meta.get("memory_type", "?")
                    log_items.append(f"  {mid} (type={mem_type}, imp={imp:.2f}, {preview})")
                
                # 执行删除
                self.collection.delete(ids=to_delete)
                for mid in to_delete:
                    self._metadata_cache.pop(mid, None)
                
                logger.info(
                    "艾宾浩斯清理: ChromaDB 删除 "
                    + str(count) + " 条"
                    + "（其中 " + str(cloud_count) + " 条送入云层）\n"
                    + "\n".join(log_items)
                )

            return count
        except Exception as e:
            logger.warning(f"清理过期记忆失败: {e}")
            return 0

    def query(self, text: str, top_k: int = 5) -> list:
        if not text or not text.strip():
            return []

        try:
            results = self.collection.query(
                query_texts=[text],
                n_results=min(top_k * 2, max(self.collection.count(), 1)),
                include=["metadatas", "documents", "distances"],
            )

            if not results or not results.get("documents") or not results["documents"][0]:
                return []

            memories = []
            query_preview = text[:80].replace("\n", " ")
            logger.info(f"检索记忆: \"{query_preview}\" (top_k={top_k})")
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                distance = results["distances"][0][i] if results.get("distances") else 1.0
                relevance = max(0, 1.0 - distance)

                mem_id = meta.get("memory_id", "")
                if mem_id and mem_id in self._metadata_cache:
                    self._metadata_cache[mem_id]["access_count"] = (
                        self._metadata_cache[mem_id].get("access_count", 0) + 1
                    )
                    self._metadata_cache[mem_id]["last_accessed"] = time.time()
                    # 同步写回 ChromaDB（防止重启后 access_count 归零导致大量误删）
                    try:
                        self.collection.update(
                            ids=[mem_id],
                            metadatas=[self._metadata_cache[mem_id]]
                        )
                    except Exception as e:
                        logger.debug(f"访问计数写回失败: {e}")

                importance = meta.get("importance", 0.5)
                updated_at = meta.get("updated_at", meta.get("created_at", 0))
                age_days = max(0, (time.time() - updated_at) / 86400)
                time_penalty = math.exp(-age_days * 0.1)
                rank_score = importance * relevance * time_penalty

                memories.append({
                    "id": meta.get("memory_id", ""),
                    "role": meta.get("role", ""),
                    "content": doc,
                    "metadata": meta,
                    "relevance": round(relevance, 3),
                    "importance": importance,
                    "memory_type": meta.get("memory_type", ""),
                    "rank_score": round(rank_score, 4),
                    "created_at": meta.get("created_at", 0),
                    "updated_at": updated_at,
                })

            # 按 rank_score 重新排序
            memories.sort(key=lambda m: m["rank_score"], reverse=True)
            memories = memories[:top_k]

            if memories:
                detail = "; ".join([f"[r={m['rank_score']:.2f}] {m['content'][:40]}" for m in memories])
                logger.info(f"检索到 {len(memories)} 条记忆: {detail}")
            else:
                logger.info("未检索到相关记忆")
            
            # V4: 云层检索（迁跃激活）
            try:
                cloud_candidates = self.cloud.query(text, top_k=2)
                activated = 0
                for cm in cloud_candidates:
                    if self.cloud.should_activate(cm, text):
                        activated_mem = self.cloud.activate(cm)
                        activated_mem["rank_score"] = max(
                            activated_mem.get("rank_score", 0),
                            cm.get("cloud_score", 0)
                        )
                        memories.append(activated_mem)
                        activated += 1
                
                if activated > 0:
                    # 重新按 rank_score 排序
                    memories.sort(key=lambda m: m["rank_score"], reverse=True)
                    memories = memories[:top_k]
                    logger.info(f"云层迁跃激活 {activated} 条，合并后共 {len(memories)} 条")
            except Exception as e:
                logger.debug(f"云层检索失败: {e}")
            
            return memories

        except Exception as e:
            logger.error(f"检索记忆失败: {e}")
            return []

    def _cloud_on_graduate(self, cloud_entry):
        """
        云层毕业回调：将云层中频繁激活的记忆写入内层 ChromaDB
        
        当 cloud.activate() 检测到 activated_count >= 3 时触发
        """
        try:
            memory_id = str(uuid.uuid4())[:12]
            now = time.time()
            
            meta = cloud_entry.original_metadata or {}
            full_metadata = {
                "memory_id": memory_id,
                "role": cloud_entry.role,
                "content_preview": cloud_entry.content[:200],
                "created_at": cloud_entry.created_at,
                "updated_at": now,
                "importance": min(1.0, cloud_entry.importance + 0.1),
                "initial_retention": 0.9,
                "access_count": cloud_entry.activated_count,
                "mention_count": cloud_entry.activated_count,
                "memory_type": cloud_entry.memory_type,
                "emotion_type": cloud_entry.emotion_type,
                "emotion_label_cn": cloud_entry.emotion_label_cn,
                "emotion_intensity": cloud_entry.emotion_intensity,
                "v": cloud_entry.v,
                "a": cloud_entry.a,
                "d": cloud_entry.d,
                "emotion_polarity": 0,
                "emotion_confidence": 0.7,
                "session_id": cloud_entry.session_id,
                "_source": "cloud_graduated",
            }
            
            self.collection.add(
                documents=[cloud_entry.content],
                metadatas=[full_metadata],
                ids=[memory_id],
            )
            self._metadata_cache[memory_id] = full_metadata
            
            logger.info(
                f"云层毕业 -> 中层: id={memory_id}, "
                f"content='{cloud_entry.content[:40]}', "
                f"activated_count={cloud_entry.activated_count}"
            )
            return memory_id
        except Exception as e:
            logger.error(f"云层毕业写入失败: {e}")
            return ""

    def get_recent(self, n: int = 10) -> list:
        if not self._metadata_cache:
            return []

        sorted_memories = sorted(
            self._metadata_cache.values(),
            key=lambda x: x.get("created_at", 0),
            reverse=True,
        )[:n]

        result = []
        for meta in sorted_memories:
            mem_id = meta.get("memory_id", "")
            try:
                doc_result = self.collection.get(ids=[mem_id], include=["documents"])
                content = doc_result["documents"][0] if doc_result.get("documents") else ""
            except Exception:
                content = meta.get("content_preview", "")

            result.append({
                "id": mem_id,
                "role": meta.get("role", ""),
                "content": content,
                "metadata": meta,
            })

        return result

    def get_by_id(self, memory_id: str) -> dict:
        if memory_id not in self._metadata_cache:
            return {}

        meta = self._metadata_cache[memory_id]
        try:
            doc_result = self.collection.get(ids=[memory_id], include=["documents"])
            content = doc_result["documents"][0] if doc_result.get("documents") else ""
        except Exception:
            content = meta.get("content_preview", "")

        return {
            "id": memory_id,
            "role": meta.get("role", ""),
            "content": content,
            "metadata": meta,
        }

    def update(self, memory_id: str, data: dict) -> bool:
        if memory_id not in self._metadata_cache:
            return False

        meta = self._metadata_cache[memory_id]
        meta.update(data)
        meta["updated_at"] = time.time()

        try:
            self.collection.update(
                ids=[memory_id],
                metadatas=[meta],
                documents=[data.get("content", meta.get("content_preview", ""))],
            )
            return True
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False

    def delete(self, memory_id: str) -> bool:
        try:
            self.collection.delete(ids=[memory_id])
            self._metadata_cache.pop(memory_id, None)
            return True
        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False

    def list_all(self, page: int = 1, page_size: int = 20) -> dict:
        total = len(self._metadata_cache)
        start = (page - 1) * page_size
        end = start + page_size

        sorted_items = sorted(
            self._metadata_cache.values(),
            key=lambda x: x.get("created_at", 0),
            reverse=True,
        )

        page_items = []
        for meta in sorted_items[start:end]:
            mem_id = meta.get("memory_id", "")
            page_items.append({
                "id": mem_id,
                "role": meta.get("role", ""),
                "content": meta.get("content_preview", ""),
                "metadata": meta,
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": page_items,
        }

    def clear(self) -> bool:
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self._get_or_create_collection(self.bge_embedding if self.bge_embedding.is_available else None)
            self._metadata_cache.clear()
            logger.info("所有记忆已清空")
            return True
        except Exception as e:
            logger.error(f"清空记忆失败: {e}")
            return False


    def run_cleanup_if_needed(self, last_cleanup_time: float = 0, interval: int = 86400) -> int:
        now = time.time()
        if now - last_cleanup_time < interval:
            return 0
        return self.cleanup_expired()

    def get_stats(self) -> Dict[str, Any]:
        ebbinghaus_stats = self.ebbinghaus.get_all_stats(total_memories=len(self._metadata_cache))

        emotion_dist = {}
        importance_dist = {"high": 0, "medium": 0, "low": 0}
        for meta in self._metadata_cache.values():
            etype = meta.get("emotion_type", "中性")
            emotion_dist[etype] = emotion_dist.get(etype, 0) + 1
            imp = meta.get("importance", 0.5)
            if imp >= 0.7:
                importance_dist["high"] += 1
            elif imp >= 0.4:
                importance_dist["medium"] += 1
            else:
                importance_dist["low"] += 1

        return {
            "total_memories": len(self._metadata_cache),
            "emotion_distribution": emotion_dist,
            "importance_distribution": importance_dist,
            "ebbinghaus": ebbinghaus_stats,
        }


__all__ = ["MemoriaMemory", "EmotionAnalyzer", "EmotionFusion", "EbbinghausManager", "ImportanceScorer"]
