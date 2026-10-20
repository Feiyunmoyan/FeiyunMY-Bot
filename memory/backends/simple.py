"""简易记忆实现，支持 namespace 隔离（每个子 Agent 独立记忆）"""
import os
import json
import uuid
import time
import logging
from typing import List, Dict

from memory import MemoryBridge

logger = logging.getLogger(__name__)


class SimpleMemory(MemoryBridge):
    """简单记忆实现，支持 namespace 隔离"""

    def __init__(self, data_dir: str = None, namespace: str = ""):
        self._memories: List[Dict] = []
        self._namespace = namespace
        self._data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "memories"
        )
        os.makedirs(self._data_dir, exist_ok=True)
        if namespace:
            self._file_path = os.path.join(self._data_dir, f"memories_{namespace}.json")
        else:
            self._file_path = os.path.join(self._data_dir, "memories.json")
        self._load()

    def _load(self):
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    self._memories = json.load(f)
                tag = f" [{self._namespace}]" if self._namespace else ""
                logger.info(f"加载了 {len(self._memories)} 条记忆{tag}")
            except Exception as e:
                logger.error(f"加载记忆文件失败: {e}")
                self._memories = []

    def _save(self):
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(self._memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆文件失败: {e}")

    def add(self, role: str, content: str, metadata: dict = None) -> str:
        memory_id = str(uuid.uuid4())[:8]
        memory = {
            "id": memory_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "importance": 0.5,
            "created_at": time.time(),
        }
        self._memories.append(memory)
        self._save()
        return memory_id

    def query(self, text: str, top_k: int = 5) -> list:
        query_lower = text.lower()
        scored = []
        for m in self._memories:
            content_lower = m.get("content", "").lower()
            if query_lower in content_lower or content_lower in query_lower:
                scored.append(m)
            else:
                words = query_lower.split()
                match_count = sum(1 for w in words if w in content_lower)
                if match_count > 0:
                    scored.append(m)
        scored.sort(key=lambda x: x.get("importance", 0), reverse=True)
        return scored[:top_k]

    def get_recent(self, n: int = 10) -> list:
        return sorted(self._memories, key=lambda x: x.get("created_at", 0), reverse=True)[:n]

    def get_by_id(self, memory_id: str) -> dict:
        for m in self._memories:
            if m.get("id") == memory_id:
                return m
        return {}

    def update(self, memory_id: str, data: dict) -> bool:
        for i, m in enumerate(self._memories):
            if m.get("id") == memory_id:
                self._memories[i].update(data)
                self._memories[i]["updated_at"] = time.time()
                self._save()
                return True
        return False

    def delete(self, memory_id: str) -> bool:
        original_len = len(self._memories)
        self._memories = [m for m in self._memories if m.get("id") != memory_id]
        if len(self._memories) < original_len:
            self._save()
            return True
        return False

    def list_all(self, page: int = 1, page_size: int = 20) -> dict:
        sorted_memories = sorted(self._memories, key=lambda x: x.get("created_at", 0), reverse=True)
        total = len(sorted_memories)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": sorted_memories[start:end],
        }

    def clear(self) -> bool:
        self._memories.clear()
        self._save()
        return True
