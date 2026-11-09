"""会话与文件上传"""
import logging
import os

from fastapi import APIRouter, File, UploadFile

from .admin_models import (
    SessionCreate,
    SessionRename,

)
from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 会话管理 ───

@router.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    if not state.agent_loop or not state.agent_loop.context:
        return {"sessions": []}
    sessions = await state.agent_loop.context.list_sessions()
    return {"sessions": sessions}


@router.post("/api/sessions")
async def create_session(data: SessionCreate = None):
    """创建新会话"""
    if not state.agent_loop or not state.agent_loop.context:
        return {"status": "fail"}
    name = data.name if data and data.name else ""
    session_id = await state.agent_loop.context.create_session(name or None)
    return {"status": "ok", "session_id": session_id, "name": name or f"对话 {session_id[:4]}"}


@router.put("/api/sessions/{session_id}")
async def rename_session(session_id: str, data: SessionRename):
    """重命名会话"""
    if not state.agent_loop or not state.agent_loop.context:
        return {"status": "fail"}
    ok = await state.agent_loop.context.rename_session(session_id, data.name)
    return {"status": "ok" if ok else "fail"}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if not state.agent_loop or not state.agent_loop.context:
        return {"status": "fail"}
    ok = await state.agent_loop.context.delete_session(session_id)
    return {"status": "ok" if ok else "fail"}


@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息"""
    if not state.agent_loop or not state.agent_loop.context:
        return {"messages": []}
    messages = await state.agent_loop.context.get_history(session_id)
    return {"messages": messages, "count": len(messages)}


@router.post("/api/sessions/{session_id}/autoname")
async def auto_name_session(session_id: str):
    """根据对话内容自动生成会话标题"""
    if not state.agent_loop or not state.agent_loop.context:
        return {"status": "fail", "reason": "系统未初始化"}
    
    summary = await state.agent_loop.context.get_summary_text(session_id, max_turns=3)
    if not summary:
        return {"status": "fail", "reason": "对话为空"}
    
    try:
        prompt = f"根据以下对话内容，生成一个简短的标题（10字以内，不要标点）：{summary}"
        result = await state.agent_loop.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=30,
        )
        title = result.get("content", "").strip().strip('"').strip("'")
        if not title:
            title = f"对话 {session_id[:4]}"
        
        await state.agent_loop.context.rename_session(session_id, title)
        return {"status": "ok", "name": title}
    except Exception as e:
        return {"status": "fail", "reason": str(e)}


# ─── 文件上传管理 ───

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _do_upload(file: UploadFile) -> dict:
    """内部：执行文件上传，返回结果字典"""
    allowed = {".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log", ".xml", ".html", ".py", ".js", ".ts", ".css", ".docx"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext and ext not in allowed:
        return {"status": "fail", "reason": f"不支持的文件类型: {ext}"}

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return {"status": "fail", "reason": "文件过大，最大支持 10MB"}

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    counter = 1
    while os.path.exists(save_path):
        name, ext = os.path.splitext(file.filename)
        save_path = os.path.join(UPLOAD_DIR, f"{name}_{counter}{ext}")
        counter += 1

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"文件上传成功: {os.path.basename(save_path)} ({len(content)} bytes)")
    return {"status": "ok", "filename": os.path.basename(save_path), "size": len(content)}


@router.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件，返回 file_id 供后续对话使用"""
    result = await _do_upload(file)
    if result.get("status") != "ok":
        return result
    return {
        "status": "ok",
        "file_id": result["filename"],  # 前端在发消息时带上这个
        "filename": result["filename"],
        "size": result["size"],
    }


@router.post("/api/files/upload-and-notify")
async def upload_and_notify(file: UploadFile = File(...), session_id: str = ""):
    """上传文件，将文件内容注入到对话中供 AI 直接读取"""
    try:
        result = await _do_upload(file)
        if result.get("status") != "ok":
            return result

        filename = result["filename"]

        # 读取文件内容，注入到对话消息中
        if session_id and state.agent_loop and state.agent_loop.context:
            filepath = os.path.join(UPLOAD_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    file_content = f.read()
                # 限制内容长度
                if len(file_content) > 5000:
                    file_content = file_content[:5000] + "\n...（内容过长，仅显示前5000字）"
                msg = f"[上传文件] {filename}\n{file_content}"
            except Exception:
                msg = f"我上传了一个文件：{filename}（无法读取内容，可能是二进制文件）"

            await state.agent_loop.context.add_message(session_id, "system", msg)
            logger.info(f"已通知 AI 读取上传文件: {filename}")

        return {"status": "ok", "filename": filename, "size": result["size"], "notified": bool(session_id)}
    except Exception as e:
        logger.error(f"上传并通知失败: {e}")
        return {"status": "fail", "reason": str(e)}


@router.get("/api/files")
async def list_files():
    """列出已上传的文件"""
    if not os.path.exists(UPLOAD_DIR):
        return {"files": []}

    files = []
    for f in sorted(os.listdir(UPLOAD_DIR), key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x)), reverse=True):
        fp = os.path.join(UPLOAD_DIR, f)
        if os.path.isfile(fp):
            files.append({
                "name": f,
                "size": os.path.getsize(fp),
                "time": os.path.getmtime(fp),
            })
    return {"files": files}


@router.delete("/api/files/{filename}")
async def delete_file(filename: str):
    """删除已上传的文件"""
    safe_path = os.path.normpath(os.path.join(UPLOAD_DIR, filename))
    if not safe_path.startswith(UPLOAD_DIR):
        return {"status": "fail", "reason": "路径不安全"}
    if os.path.exists(safe_path):
        os.remove(safe_path)
        return {"status": "ok"}
    return {"status": "fail", "reason": "文件不存在"}
