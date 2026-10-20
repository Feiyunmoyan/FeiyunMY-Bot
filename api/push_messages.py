"""
普通消息持久化 API
存储 AI 主动推送的消息 + 用户回复消息 + FIFO清理
存储分离：使用独立的 push_messages 表，与 context 的 conversations 表解耦
"""
import uuid
import time
import logging
import json
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局引用
_db = None
_runner = None
_scheduler = None

# 普通消息固定频道 ID（用于 runner 调用的会话标识）
PUSH_CHANNEL_ID = "__push_channel__"
MAX_MESSAGES = 1000

# 记录最近一条 AI 主动推送的消息 ID（用于阈值计算）
_last_push_msg_id = None


def set_push_store_deps(db, memory_selector=None, provider=None):
    global _db
    _db = db


def set_runner(runner):
    global _runner
    _runner = runner


def set_scheduler(scheduler):
    global _scheduler
    _scheduler = scheduler


def set_last_push_id(msg_id: str):
    """记录最后一条主动推送的ID（用于阈值计算）"""
    global _last_push_msg_id
    _last_push_msg_id = msg_id


class PushChatRequest(BaseModel):
    message: str


# ─── 频道管理 ───

async def add_to_push_channel(role: str, content: str, metadata: dict = None):
    """
    向普通消息频道添加一条消息（存储到独立的 push_messages 表）
    
    Args:
        role: "user" | "assistant"
        content: 消息内容
        metadata: 可选元数据，支持 source, msg_type, priority 等
    """
    if not _db:
        return
    
    meta = metadata or {}
    msg_data = {
        "id": uuid.uuid4().hex[:12],
        "role": role,
        "content": content,
        "type": meta.get("msg_type", "chat_reply"),
        "priority": meta.get("priority", "normal"),
        "source": meta.get("source", ""),
        "created_at": time.time(),
    }
    await _db.add_push_message(msg_data)


async def get_push_channel_messages(page: int = 1, page_size: int = 60) -> dict:
    """获取推送频道消息（默认最近60条，支持分页翻查更早，过滤日摘要和旧主动推送）"""
    if not _db:
        return {"total": 0, "items": []}
    
    import time
    now = time.time()
    three_days_ago = now - 259200  # 3天
    
    result = await _db.list_push_messages(page=page, page_size=page_size)
    # 过滤掉 daily_summary 类型 + 超过3天的 active_push
    filtered = []
    for m in result.get("items", []):
        if m.get("type") == "daily_summary":
            continue
        if m.get("type") == "active_push" and m.get("created_at", 0) < three_days_ago:
            continue
        filtered.append(m)
    # 前端会做 reverse 转成 ASC（最早在上），后端保持 DESC 不变
    return {"total": result["total"], "page": page, "page_size": page_size, "items": filtered}


# ─── API 端点 ───

@router.get("/push/messages")
async def list_push_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    """获取推送频道消息"""
    if not _db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    return await get_push_channel_messages(page=page, page_size=page_size)


@router.post("/push/chat")
async def push_chat(req: PushChatRequest):
    """在推送频道中回复消息（非流式）"""
    if not _runner:
        raise HTTPException(status_code=503, detail="对话引擎未初始化")
    if not _db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    
    # 0. 记录用户回复了主动推送（阈值计算），先标记
    global _last_push_msg_id
    need_record = False
    if _last_push_msg_id and _scheduler:
        need_record = True
    
    # 1. 调用 AI 回复（runner.run 内部会管理 context 的存储）
    try:
        result = await _runner.run(req.message, PUSH_CHANNEL_ID)
        reply = result.get("reply", "")
        reasoning = result.get("reasoning", "")
        tools_used = result.get("tools_used", [])
    except Exception as e:
        logger.error(f"推送频道回复失败: {e}")
        reply = f"回复失败: {e}"
        reasoning = ""
        tools_used = []
    
    # 2. AI回复完成后，再存消息到 push_messages 表（展示用）
    #    避免 _build_push_context 重复读到当前消息
    await add_to_push_channel("user", req.message, {"msg_type": "chat_reply"})
    
    metadata = {"priority": "normal"}
    if reasoning:
        metadata["reasoning"] = reasoning
    await add_to_push_channel("assistant", reply, metadata=metadata)
    
    # 3. 记录用户回复了主动推送（阈值计算）
    if need_record:
        try:
            await _scheduler.record_user_reply(_last_push_msg_id, req.message)
        except Exception as e:
            logger.debug(f"记录回复失败: {e}")
        _last_push_msg_id = None
    
    return {
        "reply": reply,
        "reasoning": reasoning,
        "tools_used": tools_used,
    }


@router.post("/push/chat/stream")
async def push_chat_stream(req: PushChatRequest):
    """在推送频道中回复消息（流式）"""
    if not _runner:
        raise HTTPException(status_code=503, detail="对话引擎未初始化")
    if not _db:
        raise HTTPException(status_code=503, detail="数据库未初始化")

    # 先标记需要记录用户回复（阈值计算），等AI回复完成后再执行
    global _last_push_msg_id
    need_record = False
    if _last_push_msg_id and _scheduler:
        need_record = True

    async def event_generator():
        # 嵌套函数内对 _last_push_msg_id 有赋值，必须显式声明 global，
        # 否则它会被当作局部变量，第 202 行引用时抛 UnboundLocalError
        global _last_push_msg_id
        full_reply = ""
        try:
            async for event in _runner.run_stream(req.message, PUSH_CHANNEL_ID):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] == "text":
                    full_reply += event.get("content", "")
                elif event["type"] == "done":
                    reasoning = event.get("reasoning", "")
                    metadata = {"priority": "normal"}
                    if reasoning:
                        metadata["reasoning"] = reasoning
                    # AI回复完成后，再存消息到 push_messages 表（展示用）
                    # 避免 _build_push_context 重复读到当前消息
                    await add_to_push_channel("user", req.message, {"msg_type": "chat_reply"})
                    await add_to_push_channel("assistant", full_reply, metadata=metadata)
                    # 记录用户回复了主动推送（阈值计算）
                    if need_record:
                        try:
                            await _scheduler.record_user_reply(_last_push_msg_id, req.message)
                        except Exception as e:
                            logger.debug(f"记录回复失败: {e}")
                        _last_push_msg_id = None
        except Exception as e:
            logger.error(f"推送频道流式回复失败: {e}")
            # 异常时也尝试保存已收到的内容
            if full_reply:
                try:
                    await add_to_push_channel("user", req.message, {"msg_type": "chat_reply"})
                    await add_to_push_channel("assistant", full_reply + "\n[回复被中断]", metadata={"priority": "normal"})
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.delete("/push/messages")
async def clear_push_messages():
    """清空推送频道"""
    if not _db:
        raise HTTPException(status_code=503, detail="数据库未初始化")
    # 清空 push_messages 表
    await _db.delete_oldest_push_messages(keep=0)
    return {"status": "ok", "message": "已清空"}


@router.get("/push/messages/count")
async def get_push_message_count():
    """获取推送频道消息数"""
    if not _db:
        return {"total": 0}
    count = await _db.count_push_messages()
    return {"total": count}


# ===================== 通知历史（原 api/notifications.py）=====================


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
