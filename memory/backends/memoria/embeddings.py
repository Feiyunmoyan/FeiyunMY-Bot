"""
Memoria 语义向量层

BGE 中文模型懒加载、ChromaDB embedding 函数、语义相似度计算。
（原样搬自 memory/backends/memoria/__init__.py，逻辑未改动）
"""
import os
import logging

# 与原模块共用同名 logger，保证拆分后日志输出完全一致
logger = logging.getLogger("memory.backends.memoria")


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
