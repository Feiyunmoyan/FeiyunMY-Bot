"""
通知历史 API
提供系统通知的分页查询接口
"""
import logging
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()

_db = None


def set_database(db):
    global _db
    _db = db


@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    msg_type: str = Query(None, description="筛选类型：active_push / system_event / agent_report"),
):
    """分页查询通知历史"""
    if not _db:
        return {"error": "数据库未初始化"}
    return await _db.list_notifications(page=page, page_size=page_size, msg_type=msg_type)
