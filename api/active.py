"""
主动引擎 API
提供 SSE 推送、配置管理、状态查询等接口
"""
import logging
import time
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局引用
_user_focus = {"view": "chat", "session_id": "", "updated_at": 0}
_push_engine = None
_active_scheduler = None


def set_active_engine_deps(push_engine, scheduler):
    global _push_engine, _active_scheduler
    _push_engine = push_engine
    _active_scheduler = scheduler


# ─── Request Models ───

class ActiveConfigUpdate(BaseModel):
    chatter_mode: Optional[str] = None        # high / medium / low / off
    quiet_hours_start: Optional[int] = None   # 免打扰开始小时
    quiet_hours_end: Optional[int] = None     # 免打扰结束小时
    routing: Optional[dict] = None            # 推送路由配置


# ─── API 端点 ───

@router.get("/events")
async def sse_events():
    """SSE 长连接，后端主动推送给前端"""
    if not _push_engine:
        return {"error": "推送引擎未初始化"}

    return StreamingResponse(
        _push_engine.sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/active/messages")
async def get_active_messages(
    since: float = Query(0, description="时间戳，只返回此时间之后的消息"),
    limit: int = Query(50, description="最多返回条数"),
):
    """获取历史主动推送消息（用于断连补推）"""
    if not _push_engine:
        return {"error": "推送引擎未初始化"}

    messages = _push_engine.get_messages_since(since=since, limit=limit)
    return {"messages": messages, "total": len(messages)}


@router.post("/user/status")
async def report_user_status(data: dict):
    """
    用户状态上报接口
    前端每 30 秒上报键盘频率、页面焦点等

    Request body:
    {
        "keyboard_freq": 0.0,     # 键盘活动频率 0~100
        "cpu_usage": 0.0,         # CPU 使用率 0~100
        "gpu_usage": 0.0,         # GPU 使用率 0~100
        "screen_focused": true,   # 页面是否聚焦
        "view": "chat",           # 用户当前视图（chat/push/notification）
        "session_id": "xxx"       # 当前活跃会话ID（如有）
    }
    """
    # 存储用户焦点信息供主动引擎使用
    global _user_focus
    _user_focus = {
        "view": data.get("view", "chat"),
        "session_id": data.get("session_id", ""),
        "updated_at": time.time(),
    }
    logger.debug(f"用户状态上报: view={_user_focus['view']}, session={_user_focus['session_id'][:8] if _user_focus['session_id'] else '无'}")
    return {"status": "ok"}


@router.get("/user/focus")
async def get_user_focus():
    """获取用户当前焦点（供主动引擎使用）"""
    return _user_focus


@router.get("/active/config")
async def get_active_config():
    """获取主动引擎配置"""
    if not _active_scheduler:
        return {"error": "主动引擎未初始化"}
    config = _active_scheduler.get_config()
    # 加入默认路由配置（前端可修改）
    config["routing"] = {
        "active_push": {"target": "session", "session_id": "default"},
        "system_event": {"target": "notification"},
        "agent_report": {"target": "notification"},
    }
    return config


@router.put("/active/config")
async def update_active_config(req: ActiveConfigUpdate):
    """更新主动引擎配置"""
    if not _active_scheduler:
        return {"error": "主动引擎未初始化"}

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    _active_scheduler.update_config(updates)
    return {"message": "配置已更新", "config": _active_scheduler.get_config()}


@router.get("/active/stats")
async def get_active_stats():
    """获取主动推送统计"""
    if not _active_scheduler:
        return {"error": "主动引擎未初始化"}

    push_status = _push_engine.get_status() if _push_engine else {}
    adaptive_stats = _active_scheduler.adaptive.get_stats()

    return {
        "push_engine": push_status,
        "adaptive": adaptive_stats,
        "chatter_mode": _active_scheduler.chatter_mode,
    }
