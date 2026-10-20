"""
Memoria 生命周期维护

艾宾浩斯过期清理（清理前送入云层）、定时清理入口、统计信息。
（方法原样搬自 memory/backends/memoria/__init__.py 的 MemoriaMemory）
"""
import time
import logging
from typing import Dict, Any

# 与原模块共用同名 logger，保证拆分后日志输出完全一致
logger = logging.getLogger("memory.backends.memoria")


class LifecycleMixin:
    """MemoriaMemory 的生命周期维护职责切片（不单独实例化，由主类组合）"""

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
