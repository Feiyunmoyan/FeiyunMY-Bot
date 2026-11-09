"""MCP / Skills / Shell 白名单"""
import logging

from fastapi import APIRouter, File, UploadFile

from .admin_models import (
    MCPServerCreate,
    MCPServerUpdate,
    SkillCreate,
    SkillUpdate,

)
from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── MCP 服务器管理 ───

@router.get("/api/mcp/servers")
async def list_mcp_servers():
    if not state.mcp_manager:
        return {"servers": []}
    return {"servers": state.mcp_manager.list_servers()}


@router.post("/api/mcp/servers")
async def add_mcp_server(s: MCPServerCreate):
    if not state.mcp_manager:
        return {"status": "fail", "reason": "MCP 未初始化"}
    ok = state.mcp_manager.add_server(s.name, s.url, s.description, s.enabled)
    return {"status": "ok" if ok else "fail", "servers": state.mcp_manager.list_servers()}


@router.put("/api/mcp/servers/{name}")
async def update_mcp_server(name: str, update: MCPServerUpdate):
    if not state.mcp_manager:
        return {"status": "fail", "reason": "MCP 未初始化"}
    data = {}
    if update.name is not None:
        data["name"] = update.name
    if update.url is not None:
        data["url"] = update.url
    if update.description is not None:
        data["description"] = update.description
    if update.enabled is not None:
        data["enabled"] = update.enabled
    ok = state.mcp_manager.update_server(name, data)
    return {"status": "ok" if ok else "fail", "servers": state.mcp_manager.list_servers()}


@router.delete("/api/mcp/servers/{name}")
async def delete_mcp_server(name: str):
    if not state.mcp_manager:
        return {"status": "fail"}
    ok = state.mcp_manager.delete_server(name)
    return {"status": "ok" if ok else "fail", "servers": state.mcp_manager.list_servers()}


# ─── Skills 管理 ───

@router.get("/api/skills")
async def list_skills():
    if not state.skills_manager:
        return {"skills": []}
    return {"skills": state.skills_manager.list_skills()}


@router.post("/api/skills")
async def add_skill(s: SkillCreate):
    if not state.skills_manager:
        return {"status": "fail", "reason": "Skills 未初始化"}
    ok = state.skills_manager.add_skill(s.name, s.description, s.prompt, s.enabled)
    return {"status": "ok" if ok else "fail", "skills": state.skills_manager.list_skills()}


@router.put("/api/skills/{name}")
async def update_skill(name: str, update: SkillUpdate):
    if not state.skills_manager:
        return {"status": "fail"}
    data = {}
    if update.name is not None:
        data["name"] = update.name
    if update.description is not None:
        data["description"] = update.description
    if update.prompt is not None:
        data["prompt"] = update.prompt
    if update.enabled is not None:
        data["enabled"] = update.enabled
    ok = state.skills_manager.update_skill(name, data)
    return {"status": "ok" if ok else "fail", "skills": state.skills_manager.list_skills()}


@router.delete("/api/skills/{name}")
async def delete_skill(name: str):
    if not state.skills_manager:
        return {"status": "fail"}
    ok = state.skills_manager.delete_skill(name)
    return {"status": "ok" if ok else "fail", "skills": state.skills_manager.list_skills()}


@router.post("/api/skills/install")
async def install_skill_zip():
    """从 zip 文件安装技能（上传安装）"""
    if not state.skills_manager:
        return {"status": "fail", "reason": "Skills 未初始化"}
    
    # 读取上传的文件
    
    # 这个端点使用 multipart/form-data，需要单独处理
    # 我们使用临时文件方式
    return {"status": "fail", "reason": "请使用 POST /api/skills/install/upload 上传文件"}


@router.post("/api/skills/install/upload")
async def upload_skill_zip(file: UploadFile = File(...)):
    """上传并安装技能 zip 包"""
    if not state.skills_manager:
        return {"status": "fail", "reason": "Skills 未初始化"}
    
    import tempfile
    try:
        # 保存上传的文件
        suffix = ".zip" if file.filename.endswith(".zip") else ".tar"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 安装
        result = state.skills_manager.install_from_zip(tmp_path)
        return result
    except Exception as e:
        return {"status": "fail", "reason": str(e)}


# ─── Shell 白名单管理 ───

@router.get("/api/shell/whitelist")
async def get_shell_whitelist():
    wl = state.config.get("shell_whitelist", {})
    return wl


@router.post("/api/shell/whitelist/commands")
async def add_shell_command(data: dict):
    command = data.get("command", "").strip()
    if not command:
        return {"status": "fail", "reason": "命令不能为空"}
    wl = state.config.get("shell_whitelist", {"enabled": True, "commands": []})
    if command in wl["commands"]:
        return {"status": "fail", "reason": "命令已存在"}
    wl["commands"].append(command)
    state.config["shell_whitelist"] = wl
    # 动态更新
    from tools.agent_tools import set_shell_whitelist
    set_shell_whitelist(wl["commands"])
    state.save_config()
    return {"status": "ok", "whitelist": wl}


@router.delete("/api/shell/whitelist/commands/{command:path}")
async def delete_shell_command(command: str):
    wl = state.config.get("shell_whitelist", {"enabled": True, "commands": []})
    wl["commands"] = [c for c in wl["commands"] if c != command]
    state.config["shell_whitelist"] = wl
    from tools.agent_tools import set_shell_whitelist
    set_shell_whitelist(wl["commands"])
    state.save_config()
    return {"status": "ok", "whitelist": wl}


@router.put("/api/shell/whitelist/toggle")
async def toggle_shell_whitelist(data: dict):
    enabled = data.get("enabled", True)
    state.config["shell_whitelist"]["enabled"] = enabled
    state.save_config()
    return {"status": "ok", "enabled": enabled}
