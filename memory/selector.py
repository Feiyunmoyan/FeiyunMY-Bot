"""
记忆选择器
支持运行时切换记忆模式（simple / memoria）
"""
import logging
from memory.bridge import MemoryBridge
from memory.backends.simple import SimpleMemory
from memory.backends.memoria import MemoriaMemory

logger = logging.getLogger(__name__)


class MemorySelector:
    """记忆模式选择器"""

    def __init__(self, mode: str = "simple", config: dict = None):
        self._mode = mode
        self._config = config or {}
        self._backends = {
            "simple": SimpleMemory(),
            "memoria": self._create_memoria_backend(),
        }
        self._active = self._backends.get(mode, self._backends["simple"])
        logger.info(f"记忆系统初始化，模式: {mode}")

    def _create_memoria_backend(self) -> MemoriaMemory:
        """创建配置化的 Memoria 后端"""
        memoria_config = self._config.get("memoria", {})
        ebbinghaus_config = memoria_config.get("ebbinghaus", {})
        
        return MemoriaMemory(
            chromadb_path=memoria_config.get("chromadb_path"),
            retrieval_top_k=memoria_config.get("retrieval_top_k", 5),
            ebbinghaus_config=ebbinghaus_config,
            emotion_enabled=memoria_config.get("emotion_analysis", {}).get("enabled", True),
            min_importance_score=memoria_config.get("importance", {}).get("min_score", 0.3),
        )

    @property
    def mode(self) -> str:
        return self._mode

    def switch_mode(self, mode: str) -> bool:
        """切换到指定记忆模式"""
        if mode not in self._backends:
            logger.warning(f"不支持的记忆模式: {mode}")
            return False
        
        self._mode = mode
        self._active = self._backends[mode]
        logger.info(f"记忆模式已切换为: {mode}")
        return True

    def get_backend(self) -> MemoryBridge:
        """获取当前活跃的记忆后端"""
        return self._active

    # 代理方法，直接转发到当前后端
    def add(self, role: str, content: str, metadata: dict = None) -> str:
        return self._active.add(role, content, metadata)

    def query(self, text: str, top_k: int = 5) -> list:
        return self._active.query(text, top_k)

    def get_recent(self, n: int = 10) -> list:
        return self._active.get_recent(n)

    def get_by_id(self, memory_id: str) -> dict:
        return self._active.get_by_id(memory_id)

    def update(self, memory_id: str, data: dict) -> bool:
        return self._active.update(memory_id, data)

    def delete(self, memory_id: str) -> bool:
        return self._active.delete(memory_id)

    def list_all(self, page: int = 1, page_size: int = 20) -> dict:
        return self._active.list_all(page, page_size)

    def clear(self) -> bool:
        return self._active.clear()
