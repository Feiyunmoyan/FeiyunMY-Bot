"""
Memoria 检索与召回

向量检索 + 排序打分 + 访问计数回流 + 云层迁跃激活，
以及按时间/ID/分页的读取入口。
（方法原样搬自 memory/backends/memoria/__init__.py 的 MemoriaMemory）
"""
import time
import math
import logging

# 与原模块共用同名 logger，保证拆分后日志输出完全一致
logger = logging.getLogger("memory.backends.memoria")


class RetrievalMixin:
    """MemoriaMemory 的检索/召回职责切片（不单独实例化，由主类组合）"""

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
