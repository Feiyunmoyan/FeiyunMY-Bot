"""
知识库管理器
管理文档存储、检索与挂载
"""
import os
import json
import uuid
import time
import shutil
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 知识库数据目录
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "knowledge_bases"
)


class KnowledgeBaseManager:
    """
    知识库管理器

    职责：
    - 知识库 CRUD
    - 文档上传与管理
    - 知识库挂载到 Agent
    """

    def __init__(self, knowledge_dir: str = None):
        self._knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        os.makedirs(self._knowledge_dir, exist_ok=True)
        self._cache: Dict[str, dict] = {}
        self._load_all()

    def _kb_path(self, kb_id: str) -> str:
        return os.path.join(self._knowledge_dir, kb_id)

    def _meta_path(self, kb_id: str) -> str:
        return os.path.join(self._knowledge_dir, kb_id, "meta.json")

    def _docs_dir(self, kb_id: str) -> str:
        return os.path.join(self._knowledge_dir, kb_id, "docs")

    def _load_all(self):
        """加载所有知识库到缓存"""
        if not os.path.exists(self._knowledge_dir):
            return
        for name in os.listdir(self._knowledge_dir):
            kb_dir = os.path.join(self._knowledge_dir, name)
            if not os.path.isdir(kb_dir):
                continue
            meta_path = os.path.join(kb_dir, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "kb_id" in data:
                        self._cache[data["kb_id"]] = data
                except Exception as e:
                    logger.warning(f"加载知识库失败 {name}: {e}")
        logger.info(f"加载了 {len(self._cache)} 个知识库")

    def _save_meta(self, kb_id: str):
        """保存知识库元数据"""
        data = self._cache.get(kb_id)
        if not data:
            return
        kb_dir = self._kb_path(kb_id)
        os.makedirs(kb_dir, exist_ok=True)
        with open(self._meta_path(kb_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ─── CRUD ───

    def create_knowledge_base(
        self, name: str, description: str = "", tags: list = None
    ) -> dict:
        """创建知识库"""
        kb_id = f"kb_{uuid.uuid4().hex[:8]}"
        now = time.time()

        kb = {
            "kb_id": kb_id,
            "name": name,
            "description": description,
            "tags": tags or [],
            "document_count": 0,
            "documents": [],
            "created_at": now,
            "updated_at": now,
        }

        self._cache[kb_id] = kb
        os.makedirs(self._docs_dir(kb_id), exist_ok=True)
        self._save_meta(kb_id)

        logger.info(f"创建知识库: {name} ({kb_id[:12]}...)")
        return kb

    def get_knowledge_base(self, kb_id: str) -> Optional[dict]:
        """获取知识库详情"""
        return self._cache.get(kb_id)

    def list_knowledge_bases(self) -> list:
        """列出所有知识库"""
        kbs = list(self._cache.values())
        kbs.sort(key=lambda k: k.get("created_at", 0), reverse=True)
        return kbs

    def update_knowledge_base(self, kb_id: str, updates: dict) -> Optional[dict]:
        """更新知识库"""
        kb = self._cache.get(kb_id)
        if not kb:
            return None
        for key in ["kb_id", "created_at"]:
            updates.pop(key, None)
        kb.update(updates)
        kb["updated_at"] = time.time()
        self._save_meta(kb_id)
        return kb

    def delete_knowledge_base(self, kb_id: str) -> bool:
        """删除知识库"""
        if kb_id not in self._cache:
            return False
        del self._cache[kb_id]
        kb_dir = self._kb_path(kb_id)
        if os.path.exists(kb_dir):
            shutil.rmtree(kb_dir, ignore_errors=True)
        logger.info(f"删除知识库: {kb_id[:12]}...")
        return True

    # ─── 文档管理 ───

    def upload_document(self, kb_id: str, filename: str, content: str) -> Optional[str]:
        """
        上传文档到知识库

        Args:
            kb_id: 知识库 ID
            filename: 文档文件名
            content: 文档内容

        Returns:
            文档 ID，失败返回 None
        """
        kb = self._cache.get(kb_id)
        if not kb:
            return None

        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        doc_dir = self._docs_dir(kb_id)
        os.makedirs(doc_dir, exist_ok=True)

        # 保存文档内容
        doc_path = os.path.join(doc_dir, f"{doc_id}_{filename}")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 更新元数据
        doc_info = {
            "doc_id": doc_id,
            "filename": filename,
            "size": len(content),
            "uploaded_at": time.time(),
        }
        kb["documents"].append(doc_info)
        kb["document_count"] = len(kb["documents"])
        kb["updated_at"] = time.time()
        self._save_meta(kb_id)

        logger.info(f"上传文档到 {kb_id[:12]}...: {filename} ({len(content)} 字符)")
        return doc_id

    def list_documents(self, kb_id: str) -> list:
        """列出知识库中的文档"""
        kb = self._cache.get(kb_id)
        if not kb:
            return []
        return kb.get("documents", [])

    def get_document_content(self, kb_id: str, doc_id: str) -> Optional[str]:
        """获取文档内容"""
        kb = self._cache.get(kb_id)
        if not kb:
            return None

        doc_dir = self._docs_dir(kb_id)
        if not os.path.exists(doc_dir):
            return None

        for fname in os.listdir(doc_dir):
            if fname.startswith(doc_id):
                filepath = os.path.join(doc_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"读取文档失败: {e}")
                    return None
        return None

    def delete_document(self, kb_id: str, doc_id: str) -> bool:
        """删除文档"""
        kb = self._cache.get(kb_id)
        if not kb:
            return False

        doc_dir = self._docs_dir(kb_id)
        if os.path.exists(doc_dir):
            for fname in os.listdir(doc_dir):
                if fname.startswith(doc_id):
                    os.remove(os.path.join(doc_dir, fname))
                    break

        kb["documents"] = [d for d in kb["documents"] if d.get("doc_id") != doc_id]
        kb["document_count"] = len(kb["documents"])
        kb["updated_at"] = time.time()
        self._save_meta(kb_id)
        return True

    # ─── 检索 ───

    def search(self, kb_id: str, keyword: str) -> list:
        """
        在知识库中搜索文档（简单关键词匹配）

        Args:
            kb_id: 知识库 ID
            keyword: 搜索关键词

        Returns:
            匹配的文档列表 [{doc_id, filename, snippet}]
        """
        results = []
        doc_dir = self._docs_dir(kb_id)
        if not os.path.exists(doc_dir):
            return results

        keyword_lower = keyword.lower()
        for fname in os.listdir(doc_dir):
            if not fname.startswith("doc_"):
                continue
            filepath = os.path.join(doc_dir, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read(5000)  # 只读前5000字符
                if keyword_lower in content.lower():
                    # 提取匹配片段
                    idx = content.lower().find(keyword_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(keyword) + 50)
                    snippet = content[start:end]

                    doc_id = fname.split("_", 1)[0]
                    doc_id = doc_id.split("_", 1)[1] if "_" in doc_id else doc_id
                    # 从文件名获取实际 doc_id
                    # fname 格式: doc_xxx_filename.txt
                    parts = fname.split("_", 2)
                    actual_doc_id = parts[1] if len(parts) > 1 else ""

                    results.append({
                        "doc_id": actual_doc_id,
                        "filename": fname,
                        "snippet": snippet.strip(),
                    })
            except Exception:
                continue

        return results
