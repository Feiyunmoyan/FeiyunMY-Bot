"""
知识库管理 API
提供知识库 CRUD、文档上传、搜索等接口
"""
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局引用
_knowledge_manager = None


def set_knowledge_manager(mgr):
    global _knowledge_manager
    _knowledge_manager = mgr


# ─── Request Models ───

class CreateKBRequest(BaseModel):
    name: str
    description: str = ""
    tags: list = []


class UpdateKBRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list] = None


# ─── API 端点 ───

@router.get("/knowledge_bases")
async def list_knowledge_bases():
    """列出所有知识库"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    kbs = _knowledge_manager.list_knowledge_bases()
    return {"knowledge_bases": kbs, "total": len(kbs)}


@router.post("/knowledge_bases")
async def create_knowledge_base(req: CreateKBRequest):
    """创建知识库"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    kb = _knowledge_manager.create_knowledge_base(
        name=req.name, description=req.description, tags=req.tags
    )
    return {"knowledge_base": kb, "message": f"知识库「{req.name}」创建成功"}


@router.get("/knowledge_bases/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """查看知识库详情"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    kb = _knowledge_manager.get_knowledge_base(kb_id)
    if not kb:
        return {"error": "知识库不存在"}
    return {"knowledge_base": kb}


@router.put("/knowledge_bases/{kb_id}")
async def update_knowledge_base(kb_id: str, req: UpdateKBRequest):
    """更新知识库"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    kb = _knowledge_manager.update_knowledge_base(kb_id, updates)
    if not kb:
        return {"error": "知识库不存在"}
    return {"knowledge_base": kb, "message": "更新成功"}


@router.delete("/knowledge_bases/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """删除知识库"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    success = _knowledge_manager.delete_knowledge_base(kb_id)
    if not success:
        return {"error": "知识库不存在"}
    return {"message": "知识库已删除"}


# ─── 文档管理 ───

@router.get("/knowledge_bases/{kb_id}/documents")
async def list_documents(kb_id: str):
    """列出知识库中的文档"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    docs = _knowledge_manager.list_documents(kb_id)
    return {"documents": docs, "total": len(docs)}


@router.post("/knowledge_bases/{kb_id}/upload")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
):
    """上传文档到知识库"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}

    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content.decode("gbk")
        except UnicodeDecodeError:
            return {"error": "不支持的文件编码，请上传 UTF-8 或 GBK 编码的文本文件"}

    doc_id = _knowledge_manager.upload_document(
        kb_id=kb_id, filename=file.filename, content=text_content
    )
    if not doc_id:
        return {"error": "知识库不存在"}
    return {"doc_id": doc_id, "message": f"文档「{file.filename}」上传成功"}


@router.get("/knowledge_bases/{kb_id}/documents/{doc_id}")
async def get_document(kb_id: str, doc_id: str):
    """获取文档内容"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    content = _knowledge_manager.get_document_content(kb_id, doc_id)
    if content is None:
        return {"error": "文档不存在"}
    return {"doc_id": doc_id, "content": content[:50000]}


@router.delete("/knowledge_bases/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str):
    """删除文档"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    success = _knowledge_manager.delete_document(kb_id, doc_id)
    if not success:
        return {"error": "文档或知识库不存在"}
    return {"message": "文档已删除"}


@router.get("/knowledge_bases/{kb_id}/search")
async def search_knowledge_base(kb_id: str, keyword: str):
    """搜索知识库中的文档"""
    if not _knowledge_manager:
        return {"error": "知识库系统未初始化"}
    results = _knowledge_manager.search(kb_id, keyword)
    return {"results": results, "total": len(results)}
