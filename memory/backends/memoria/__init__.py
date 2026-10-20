"""
MemoriaDB 长期记忆后端
集成：情感分析 + 重要性评分 + ChromaDB向量检索 + 艾宾浩斯遗忘曲线

本文件只负责组装：初始化各组件并组合下面三个职责模块的方法切片，
具体实现见 store.py / retrieval.py / lifecycle.py / embeddings.py。
"""
import os
import logging
from typing import Dict, Any, Optional

import chromadb

from memory import MemoryBridge
from memory.backends.memoria.emotion import EmotionAnalyzer
from memory.backends.memoria.emotion_fusion import EmotionFusion
from memory.backends.memoria.importance import ImportanceScorer
from memory.backends.memoria.ebbinghaus import EbbinghausManager
from memory.backends.memoria.cloud import CloudLayer
from memory.backends.memoria.embeddings import (
    BGE_MODEL_PATH,
    BGEEmbeddingFunction,
    _get_sentence_transformer,
    semantic_similarity,
)
from memory.backends.memoria.store import StoreMixin
from memory.backends.memoria.retrieval import RetrievalMixin
from memory.backends.memoria.lifecycle import LifecycleMixin

logger = logging.getLogger(__name__)


class MemoriaMemory(StoreMixin, RetrievalMixin, LifecycleMixin, MemoryBridge):
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


__all__ = ["MemoriaMemory", "EmotionAnalyzer", "EmotionFusion", "EbbinghausManager", "ImportanceScorer"]
