"""
管理 API 接口
提供配置、人格、记忆、搜索、MCP、Skills 的 CRUD 操作
"""
import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi import UploadFile, File
from pydantic import BaseModel
from typing import Optional
import yaml
import os
import time

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局引用
_config = None
_persona_manager = None
_memory_selector = None
_tool_registry = None
_mcp_manager = None
_skills_manager = None
_start_time = None
_agent_loop = None
_provider_manager = None


def set_admin_deps(cfg, pm, ms, tr, mcp_mgr=None, skills_mgr=None, agent_loop=None, provider_manager=None):
    global _config, _persona_manager, _memory_selector, _tool_registry, _mcp_manager, _skills_manager, _start_time, _agent_loop, _provider_manager
    _config = cfg
    _persona_manager = pm
    _memory_selector = ms
    _tool_registry = tr
    _mcp_manager = mcp_mgr
    _skills_manager = skills_mgr
    _agent_loop = agent_loop
    _provider_manager = provider_manager
    _start_time = time.time()


def _save_config():
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.dump(_config, f, allow_unicode=True, default_flow_style=False)


# ─── Request Models ───

class ConfigUpdate(BaseModel):
    provider: Optional[dict] = None
    memory: Optional[dict] = None
    persona: Optional[dict] = None
    tools: Optional[dict] = None
    web_search: Optional[dict] = None
    features: Optional[dict] = None
    mcp: Optional[dict] = None
    skills: Optional[dict] = None
    shell_whitelist: Optional[dict] = None


class PersonaCreate(BaseModel):
    name: str
    prompt: str = ""
    description: str = ""
    preset_conversations: list = []


class PersonaUpdate(BaseModel):
    prompt: Optional[str] = None
    description: Optional[str] = None
    preset_conversations: Optional[list] = None


class SearchEngineCreate(BaseModel):
    name: str
    type: str = "web"
    enabled: bool = True


class SearchEngineUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None


class MCPServerCreate(BaseModel):
    name: str
    url: str = ""
    description: str = ""
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    prompt: str = ""
    enabled: bool = True


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    enabled: Optional[bool] = None


class ProviderTestRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str = ""


class SessionCreate(BaseModel):
    name: str = ""


class SessionRename(BaseModel):
    name: str = ""


# ─── 配置管理 ───

@router.get("/api/config")
async def get_config():
    import copy
    safe_config = copy.deepcopy(_config)
    # 过滤敏感字段，不暴露给前端
    if "web_search" in safe_config:
        safe_config["web_search"]["api_key"] = ""
    if "provider" in safe_config and "api_key" in safe_config["provider"]:
        safe_config["provider"]["api_key"] = ""
    return safe_config


@router.post("/api/config")
async def update_config(update: ConfigUpdate):
    if update.provider:
        _config["provider"].update(update.provider)
    if update.memory:
        _config["memory"].update(update.memory)
        # 记忆开关同步到 mode
        if "enabled" in update.memory:
            _config["memory"]["mode"] = "memoria" if update.memory["enabled"] else "simple"
    if update.persona:
        _config["persona"].update(update.persona)
    if update.tools:
        _config["tools"].update(update.tools)
    if update.web_search:
        _config["web_search"].update(update.web_search)
        # 动态更新搜索配置
        from tools.web_search import set_search_config
        ws = _config["web_search"]
        set_search_config({"provider": ws.get("provider", "duckduckgo"), "api_key": ws.get("api_key", "")})
    if update.features:
        _config["features"].update(update.features)
    if update.mcp:
        _config["mcp"].update(update.mcp)
    if update.skills:
        _config["skills"].update(update.skills)
    if update.shell_whitelist:
        _config["shell_whitelist"].update(update.shell_whitelist)
        # 动态更新白名单
        from tools.agent_tools import set_shell_whitelist
        set_shell_whitelist(_config["shell_whitelist"].get("commands", []))

    _save_config()
    return {"status": "ok", "config": _config}


@router.post("/api/config/reload")
async def reload_config():
    """热加载配置文件（从磁盘重新读取 config.yaml）"""
    try:
        from utils.config_reloader import reload_config as do_reload
        result = do_reload()
        # 更新全局配置引用
        from utils.config_reloader import get_config
        global _config
        _config = get_config()
        # 动态更新工具开关
        tools_cfg = _config.get("tools", {})
        for name, enabled in tools_cfg.items():
            _tool_registry.set_enabled(name, enabled)
        logger.info(f"配置热加载完成: {result['message']}")
        return result
    except Exception as e:
        logger.error(f"配置热加载失败: {e}")
        return {"status": "fail", "message": str(e)}


# ─── 多提供商管理 ───

@router.get("/api/providers")
async def get_providers():
    """获取所有提供商列表"""
    return {
        "providers": _config.get("providers", []),
        "active_id": _config.get("active_provider_id", ""),
    }


@router.post("/api/providers")
async def save_providers(data: dict):
    """保存所有提供商列表"""
    providers = data.get("providers", [])
    if not isinstance(providers, list):
        return {"status": "fail", "reason": "providers must be a list"}
    _config["providers"] = providers
    _config["active_provider_id"] = data.get("active_id", "")
    _save_config()
    logger.info(f"提供商列表已更新: {len(_config['providers'])} 个")
    return {"status": "ok"}


@router.post("/api/providers/switch")
async def switch_provider(data: dict):
    """切换当前使用的提供商"""
    provider_id = data.get("provider_id", "")
    providers = _config.get("providers", [])
    for p in providers:
        if p.get("id") == provider_id:
            # 使用 ProviderManager 切换
            if _provider_manager:
                _provider_manager.switch_active(provider_id)
                # 同步更新主脑执行器的 provider 实例
                new_provider = _provider_manager.get_provider(provider_id)
                if new_provider and _agent_loop:
                    _agent_loop.provider = new_provider
                    logger.info(f"主脑执行器已切换到新 Provider: {provider_id}")
            # 选第一个启用的模型
            enabled_models = [m for m in p.get("models", []) if m.get("enabled")]
            if enabled_models:
                _config["provider"]["model"] = enabled_models[0]["id"]
            _save_config()
            logger.info(f"提供商已切换: {p.get('name', provider_id)}")
            return {"status": "ok", "provider": p}
    return {"status": "fail", "reason": "提供商未找到"}


# ─── Provider 测试与模型搜索 ───

@router.post("/api/provider/test")
async def test_provider(req: ProviderTestRequest):
    """测试 API 连接是否正常"""
    import httpx
    try:
        # 归一化 URL：去掉末尾的 /v1（如果有），统一拼 /v1/chat/completions
        base = req.base_url.rstrip('/')
        if base.endswith('/v1'):
            base = base[:-3]
        url = f"{base}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {req.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": req.model or "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                return {"status": "ok", "message": "连接成功"}
            else:
                try:
                    data = resp.json()
                    error_msg = data.get("error", {}).get("message", str(resp.status_code))
                except Exception:
                    error_msg = f"HTTP {resp.status_code}"
                return {"status": "fail", "message": error_msg}
    except httpx.TimeoutException:
        return {"status": "fail", "message": "连接超时，请检查 API 地址是否正确"}
    except Exception as e:
        return {"status": "fail", "message": str(e)}


@router.post("/api/provider/models")
async def list_provider_models(req: ProviderTestRequest):
    """获取指定提供商的可选模型列表"""
    import httpx
    try:
        # 归一化 URL
        base = req.base_url.rstrip('/')
        if base.endswith('/v1'):
            base = base[:-3]
        url = f"{base}/v1/models"
        headers = {"Authorization": f"Bearer {req.api_key}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                model_ids = sorted(set(m.get("id", "") for m in models if m.get("id")))
                return {"status": "ok", "models": model_ids, "count": len(model_ids)}
            else:
                return {"status": "fail", "message": f"获取模型列表失败 (HTTP {resp.status_code})，该 API 可能不支持 /v1/models 接口，请手动添加模型"}
    except httpx.TimeoutException:
        return {"status": "fail", "message": "连接超时，请检查 API 地址是否正确"}
    except Exception as e:
        return {"status": "fail", "message": str(e)}


# ─── 人格管理 ───

@router.get("/api/personas")
async def list_personas():
    return _persona_manager.list_personas()


@router.get("/api/personas/{name}")
async def get_persona_detail(name: str):
    p = _persona_manager.get_persona_detail(name)
    if not p:
        return {"status": "fail", "reason": "not found"}
    return p


@router.post("/api/personas")
async def create_persona(p: PersonaCreate):
    if p.name in _persona_manager._personas:
        return {"status": "fail", "reason": "名称已存在"}
    ok = _persona_manager.create_persona(p.name, p.prompt, {
        "description": p.description,
        "preset_conversations": p.preset_conversations,
    })
    return {"status": "ok" if ok else "fail", "name": p.name}


@router.put("/api/personas/{name}")
async def update_persona(name: str, p: PersonaUpdate):
    data = {}
    if p.prompt is not None:
        data["prompt"] = p.prompt
    if p.description is not None:
        data["description"] = p.description
    if p.preset_conversations is not None:
        data["preset_conversations"] = p.preset_conversations
    ok = _persona_manager.update_persona(name, data)
    return {"status": "ok" if ok else "fail"}


@router.delete("/api/personas/{name}")
async def delete_persona(name: str):
    ok = _persona_manager.delete_persona(name)
    return {"status": "ok" if ok else "fail"}


@router.post("/api/personas/{name}/activate")
async def activate_persona(name: str):
    ok = _persona_manager.activate(name)
    if ok:
        _config["persona"]["active"] = name
        _save_config()
    return {"status": "ok" if ok else "fail"}


@router.post("/api/personas/reload")
async def reload_personas():
    """重载人格（从 YAML 文件重新加载）"""
    _persona_manager.reload_personas()
    active = _persona_manager.active_name
    _config["persona"]["active"] = active
    return {"status": "ok", "active": active, "count": len(_persona_manager.list_personas())}


# ─── 搜索引擎管理 ───

@router.get("/api/search/engines")
async def list_search_engines():
    engines = _config.get("web_search", {}).get("engines", [])
    return {"engines": engines, "enabled": _config.get("web_search", {}).get("enabled", False)}


@router.post("/api/search/engines")
async def add_search_engine(engine: SearchEngineCreate):
    engines = _config.get("web_search", {}).get("engines", [])
    for e in engines:
        if e["name"] == engine.name:
            return {"status": "fail", "reason": "名称已存在"}
    engines.append({"name": engine.name, "type": engine.type, "enabled": engine.enabled})
    _save_config()
    return {"status": "ok", "engines": engines}


@router.put("/api/search/engines/{name}")
async def update_search_engine(name: str, update: SearchEngineUpdate):
    engines = _config.get("web_search", {}).get("engines", [])
    for e in engines:
        if e["name"] == name:
            if update.name is not None:
                e["name"] = update.name
            if update.type is not None:
                e["type"] = update.type
            if update.enabled is not None:
                e["enabled"] = update.enabled
            _save_config()
            return {"status": "ok", "engines": engines}
    return {"status": "fail", "reason": "未找到"}


@router.delete("/api/search/engines/{name}")
async def delete_search_engine(name: str):
    engines = _config.get("web_search", {}).get("engines", [])
    _config["web_search"]["engines"] = [e for e in engines if e["name"] != name]
    _save_config()
    return {"status": "ok", "engines": _config["web_search"]["engines"]}


# ─── MCP 服务器管理 ───

@router.get("/api/mcp/servers")
async def list_mcp_servers():
    if not _mcp_manager:
        return {"servers": []}
    return {"servers": _mcp_manager.list_servers()}


@router.post("/api/mcp/servers")
async def add_mcp_server(s: MCPServerCreate):
    if not _mcp_manager:
        return {"status": "fail", "reason": "MCP 未初始化"}
    ok = _mcp_manager.add_server(s.name, s.url, s.description, s.enabled)
    return {"status": "ok" if ok else "fail", "servers": _mcp_manager.list_servers()}


@router.put("/api/mcp/servers/{name}")
async def update_mcp_server(name: str, update: MCPServerUpdate):
    if not _mcp_manager:
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
    ok = _mcp_manager.update_server(name, data)
    return {"status": "ok" if ok else "fail", "servers": _mcp_manager.list_servers()}


@router.delete("/api/mcp/servers/{name}")
async def delete_mcp_server(name: str):
    if not _mcp_manager:
        return {"status": "fail"}
    ok = _mcp_manager.delete_server(name)
    return {"status": "ok" if ok else "fail", "servers": _mcp_manager.list_servers()}


# ─── Skills 管理 ───

@router.get("/api/skills")
async def list_skills():
    if not _skills_manager:
        return {"skills": []}
    return {"skills": _skills_manager.list_skills()}


@router.post("/api/skills")
async def add_skill(s: SkillCreate):
    if not _skills_manager:
        return {"status": "fail", "reason": "Skills 未初始化"}
    ok = _skills_manager.add_skill(s.name, s.description, s.prompt, s.enabled)
    return {"status": "ok" if ok else "fail", "skills": _skills_manager.list_skills()}


@router.put("/api/skills/{name}")
async def update_skill(name: str, update: SkillUpdate):
    if not _skills_manager:
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
    ok = _skills_manager.update_skill(name, data)
    return {"status": "ok" if ok else "fail", "skills": _skills_manager.list_skills()}


@router.delete("/api/skills/{name}")
async def delete_skill(name: str):
    if not _skills_manager:
        return {"status": "fail"}
    ok = _skills_manager.delete_skill(name)
    return {"status": "ok" if ok else "fail", "skills": _skills_manager.list_skills()}


@router.post("/api/skills/install")
async def install_skill_zip():
    """从 zip 文件安装技能（上传安装）"""
    import tempfile
    if not _skills_manager:
        return {"status": "fail", "reason": "Skills 未初始化"}
    
    # 读取上传的文件
    from fastapi import UploadFile, File
    import shutil
    
    # 这个端点使用 multipart/form-data，需要单独处理
    # 我们使用临时文件方式
    return {"status": "fail", "reason": "请使用 POST /api/skills/install/upload 上传文件"}


@router.post("/api/skills/install/upload")
async def upload_skill_zip(file: UploadFile = File(...)):
    """上传并安装技能 zip 包"""
    if not _skills_manager:
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
        result = _skills_manager.install_from_zip(tmp_path)
        return result
    except Exception as e:
        return {"status": "fail", "reason": str(e)}


# ─── Shell 白名单管理 ───

@router.get("/api/shell/whitelist")
async def get_shell_whitelist():
    wl = _config.get("shell_whitelist", {})
    return wl


@router.post("/api/shell/whitelist/commands")
async def add_shell_command(data: dict):
    command = data.get("command", "").strip()
    if not command:
        return {"status": "fail", "reason": "命令不能为空"}
    wl = _config.get("shell_whitelist", {"enabled": True, "commands": []})
    if command in wl["commands"]:
        return {"status": "fail", "reason": "命令已存在"}
    wl["commands"].append(command)
    _config["shell_whitelist"] = wl
    # 动态更新
    from tools.agent_tools import set_shell_whitelist
    set_shell_whitelist(wl["commands"])
    _save_config()
    return {"status": "ok", "whitelist": wl}


@router.delete("/api/shell/whitelist/commands/{command:path}")
async def delete_shell_command(command: str):
    wl = _config.get("shell_whitelist", {"enabled": True, "commands": []})
    wl["commands"] = [c for c in wl["commands"] if c != command]
    _config["shell_whitelist"] = wl
    from tools.agent_tools import set_shell_whitelist
    set_shell_whitelist(wl["commands"])
    _save_config()
    return {"status": "ok", "whitelist": wl}


@router.put("/api/shell/whitelist/toggle")
async def toggle_shell_whitelist(data: dict):
    enabled = data.get("enabled", True)
    _config["shell_whitelist"]["enabled"] = enabled
    _save_config()
    return {"status": "ok", "enabled": enabled}


# ─── 记忆管理 ───

@router.get("/api/memories")
async def list_memories(page: int = 1, page_size: int = 20):
    return _memory_selector.list_all(page, page_size)


@router.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    ok = _memory_selector.delete(memory_id)
    return {"status": "ok" if ok else "fail"}


@router.post("/api/memories/clear")
async def clear_memories():
    ok = _memory_selector.clear()
    return {"status": "ok" if ok else "fail"}


@router.post("/api/memory/switch")
async def switch_memory_mode(data: dict):
    """切换记忆模式（直接指定 simple/memoria）"""
    mode = data.get("mode", "simple")
    ok = _memory_selector.switch_mode(mode)
    if ok:
        _config["memory"]["mode"] = mode
        _config["memory"]["enabled"] = (mode == "memoria")
        _save_config()
    return {"status": "ok" if ok else "fail", "mode": mode}


@router.post("/api/memory/toggle")
async def toggle_memory(data: dict):
    """记忆开关：false=simple, true=memoria"""
    enabled = data.get("enabled", False)
    mode = "memoria" if enabled else "simple"
    ok = _memory_selector.switch_mode(mode)
    if ok:
        _config["memory"]["mode"] = mode
        _config["memory"]["enabled"] = enabled
        _save_config()
    return {"status": "ok" if ok else "fail", "enabled": enabled, "mode": mode}


@router.post("/api/tools/toggle")
async def toggle_tool(data: dict):
    """切换工具开关"""
    tool_name = data.get("name", "")
    enabled = data.get("enabled", False)
    if not tool_name:
        return {"status": "fail", "reason": "工具名不能为空"}

    # 旧工具名 → 合并工具名映射（向前兼容）
    NAME_MAP = {
        "shell_exec": "execute", "code_exec": "execute",
        "web_search": "web", "web_extract": "web",
        "get_datetime": "common_utils", "calculator": "common_utils", "random_utils": "common_utils",
    }
    tool_name = NAME_MAP.get(tool_name, tool_name)

    # 如果是 file_ops 切换，同时更新访问模式
    if tool_name == "file_ops":
        full_access = data.get("full_access", True)
        from tools.file_ops import set_full_access as set_fo_full_access
        set_fo_full_access(full_access)
        if _config:
            _config.setdefault("tools", {})["file_ops_full_access"] = full_access
            _save_config()

    _tool_registry.set_enabled(tool_name, enabled)
    return {"status": "ok", "name": tool_name, "enabled": enabled}


# ─── 会话管理 ───

@router.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    if not _agent_loop or not _agent_loop.context:
        return {"sessions": []}
    sessions = await _agent_loop.context.list_sessions()
    return {"sessions": sessions}


@router.post("/api/sessions")
async def create_session(data: SessionCreate = None):
    """创建新会话"""
    if not _agent_loop or not _agent_loop.context:
        return {"status": "fail"}
    name = data.name if data and data.name else ""
    session_id = await _agent_loop.context.create_session(name or None)
    return {"status": "ok", "session_id": session_id, "name": name or f"对话 {session_id[:4]}"}


@router.put("/api/sessions/{session_id}")
async def rename_session(session_id: str, data: SessionRename):
    """重命名会话"""
    if not _agent_loop or not _agent_loop.context:
        return {"status": "fail"}
    ok = await _agent_loop.context.rename_session(session_id, data.name)
    return {"status": "ok" if ok else "fail"}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if not _agent_loop or not _agent_loop.context:
        return {"status": "fail"}
    ok = await _agent_loop.context.delete_session(session_id)
    return {"status": "ok" if ok else "fail"}


@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息"""
    if not _agent_loop or not _agent_loop.context:
        return {"messages": []}
    messages = await _agent_loop.context.get_history(session_id)
    return {"messages": messages, "count": len(messages)}


@router.post("/api/sessions/{session_id}/autoname")
async def auto_name_session(session_id: str):
    """根据对话内容自动生成会话标题"""
    if not _agent_loop or not _agent_loop.context:
        return {"status": "fail", "reason": "系统未初始化"}
    
    summary = await _agent_loop.context.get_summary_text(session_id, max_turns=3)
    if not summary:
        return {"status": "fail", "reason": "对话为空"}
    
    try:
        import json
        prompt = f"根据以下对话内容，生成一个简短的标题（10字以内，不要标点）：{summary}"
        result = await _agent_loop.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=30,
        )
        title = result.get("content", "").strip().strip('"').strip("'")
        if not title:
            title = f"对话 {session_id[:4]}"
        
        await _agent_loop.context.rename_session(session_id, title)
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
        if session_id and _agent_loop and _agent_loop.context:
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

            await _agent_loop.context.add_message(session_id, "system", msg)
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


# ─── 系统统计 ───

@router.get("/api/stats")
async def get_stats():
    uptime = time.time() - _start_time
    web_search_enabled = _config.get("web_search", {}).get("enabled", False)
    persona_enabled = _config.get("persona", {}).get("enabled", True)
    keep_thinking = _config.get("features", {}).get("keep_thinking", False)
    memory_enabled = _config.get("memory", {}).get("enabled", False)
    mcp_enabled = _config.get("mcp", {}).get("enabled", False)
    skills_enabled = _config.get("skills", {}).get("enabled", False)

    mcp_count = len(_mcp_manager.list_servers()) if _mcp_manager else 0
    skills_count = len(_skills_manager.list_skills()) if _skills_manager else 0

    # 工具名中文映射（仅前端展示用，AI 仍使用英文名）
    _tool_cn_names = {
        "workspace": "工作空间", "web": "网页搜索", "file_ops": "文件操作",
        "common_utils": "常用工具", "note_taking": "笔记", "json_process": "数据处理",
        "memory_query": "记忆查询", "manage_session": "会话管理",
        "execute": "代码执行", "http_request": "HTTP请求",
        "web_search": "网页搜索(旧)", "web_extract": "网页读取(旧)",
        "code_exec": "代码执行(旧)", "shell_exec": "Shell执行(旧)",
        "get_datetime": "时间查询(旧)", "calculator": "计算器(旧)", "random_utils": "随机工具(旧)",
    }
    tools_display = []
    for t in _tool_registry.list_tools():
        t["name"] = _tool_cn_names.get(t["name"], t["name"])
        tools_display.append(t)

    return {
        "uptime_seconds": round(uptime, 1),
        "memory_count": _memory_selector.list_all(1, 1)["total"],
        "persona_count": len(_persona_manager.list_personas()),
        "active_persona": _persona_manager.active_name,
        "memory_mode": _memory_selector.mode,
        "memory_enabled": memory_enabled,
        "tools": tools_display,
        "web_search_enabled": web_search_enabled,
        "persona_enabled": persona_enabled,
        "keep_thinking": keep_thinking,
        "mcp_enabled": mcp_enabled,
        "mcp_count": mcp_count,
        "skills_enabled": skills_enabled,
        "skills_count": skills_count,
    }


@router.get("/api/system/stats")
async def get_system_stats():
    """获取系统资源监控信息"""
    from utils.monitor import get_system_stats
    return get_system_stats()


@router.get("/api/logs")
async def get_logs(lines: int = 100, level: str = "", keyword: str = ""):
    """获取平台日志"""
    from utils.platform_logger import get_recent_logs, get_log_stats
    logs = get_recent_logs(lines=min(lines, 500), level=level, keyword=keyword)
    stats = get_log_stats()
    return {"logs": logs, "total": len(logs), "stats": stats}


# ─── 测试页面 ───

@router.get("/test", response_class=HTMLResponse)
async def test_page():
    return HTMLResponse(TEST_PAGE_HTML)


TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FeiyunMY-Bot 测试面板</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
body{background:#f5f3ff;color:#1e1b2e;padding:20px;max-width:1100px;margin:0 auto}
h1{font-size:22px;margin-bottom:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.card{background:#fff;border-radius:14px;padding:20px;margin-bottom:16px;border:1px solid #e8e4f4}
.card h3{font-size:14px;margin-bottom:12px;color:#6b6580;text-transform:uppercase;letter-spacing:.5px}
.row{display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap}
.row label{font-size:14px;min-width:100px}
.toggle{width:40px;height:22px;border-radius:11px;border:none;cursor:pointer;position:relative;transition:.25s;background:#d1d5db}
.toggle.on{background:#7c5cfc}
.toggle::after{content:'';position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#fff;transition:.25s;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.toggle.on::after{transform:translateX(18px)}
.btn{padding:8px 18px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;transition:.2s}
.btn:active{transform:scale(.97)}
.btn-p{background:#7c5cfc;color:#fff}
.btn-p:hover{background:#6d4ef0}
.btn-d{background:#fee2e2;color:#dc2626}
.btn-s{background:#d1fae5;color:#059669}
.btn-o{background:transparent;border:1.5px solid #e8e4f4;color:#6b6580}
input,select,textarea{padding:8px 12px;border:1.5px solid #e8e4f4;border-radius:8px;font-size:13px;font-family:inherit}
input:focus,select:focus,textarea:focus{outline:none;border-color:#7c5cfc}
textarea{min-height:60px;resize:vertical;width:100%}
.tag{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;background:#ede9fe;color:#7c5cfc;margin:2px}
.tag-g{background:#d1fae5;color:#059669}
.tag-r{background:#fee2e2;color:#dc2626}
.chat-box{height:300px;overflow-y:auto;padding:14px;background:#faf9ff;border-radius:10px;border:1px solid #e8e4f4;margin-bottom:10px}
.msg{margin-bottom:12px;display:flex}
.msg.right{justify-content:flex-end}
.msg .b{max-width:80%;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.5;white-space:pre-wrap}
.msg.right .b{background:#7c5cfc;color:#fff;border-bottom-right-radius:3px}
.msg.left .b{background:#fff;border:1px solid #e8e4f4;border-bottom-left-radius:3px}
.msg .reason{font-size:11px;color:#9b95b0;margin-top:4px;padding:0 4px;font-style:italic}
.chat-in{display:flex;gap:8px}
.chat-in input{flex:1}
.status{font-size:12px;color:#9b95b0;margin-left:8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tri{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.desc{font-size:12px;color:#9b95b0;margin:4px 0 8px 0;line-height:1.4}
.label-hint{font-size:10px;color:#9b95b0;margin-left:4px;font-weight:normal}
@media(max-width:600px){.grid,.tri{grid-template-columns:1fr}}
</style>
</head>
<body>
<div id="app">
  <h1>☁️ FeiyunMY-Bot 测试面板 <span class="status">{{ status }}</span></h1>

  <div class="tri">
    <div class="card">
      <h3>⚙️ 功能开关</h3>
      <div class="row"><label>人格系统</label><button class="toggle" :class="{on:cfg.persona?.enabled}" @click="toggle('persona.enabled')"></button><span>{{ cfg.persona?.enabled?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>联网搜索</label><button class="toggle" :class="{on:cfg.web_search?.enabled}" @click="toggle('web_search.enabled')"></button><span>{{ cfg.web_search?.enabled?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>保留思考</label><button class="toggle" :class="{on:cfg.features?.keep_thinking}" @click="toggle('features.keep_thinking')"></button><span>{{ cfg.features?.keep_thinking?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>记忆开关</label><button class="toggle" :class="{on:cfg.memory?.enabled}" @click="toggleMemory()"></button><span>{{ cfg.memory?.enabled?'Memoria':'Simple' }}</span></div>
      <div class="row"><label>MCP 服务</label><button class="toggle" :class="{on:cfg.mcp?.enabled}" @click="toggle('mcp.enabled')"></button><span>{{ cfg.mcp?.enabled?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>Skills 技能</label><button class="toggle" :class="{on:cfg.skills?.enabled}" @click="toggle('skills.enabled')"></button><span>{{ cfg.skills?.enabled?'已开启':'已关闭' }}</span></div>
    </div>

    <div class="card">
      <h3>👤 人格 <span class="label-hint">关闭后使用默认提示词</span></h3>
      <div class="row" v-if="cfg.persona?.enabled">
        <select v-model="activePersona" @change="switchPersona" style="flex:1">
          <option v-for="p in personas" :key="p.name" :value="p.name">{{ p.name }} {{ p.is_active?'(使用中)':'' }}</option>
        </select>
      </div>
      <div v-else style="color:#9b95b0;font-size:13px">人格系统已关闭</div>

      <div style="margin-top:10px">
        <div class="row"><input v-model="newPersonaName" placeholder="人格名称" style="flex:1"><button class="btn btn-s" @click="addPersona">+ 新建</button></div>
        <div class="desc">提示：名称即 identity，prompt 决定对话风格和回答方式。</div>
      </div>
    </div>

    <div class="card">
      <h3>🔍 搜索引擎 <span class="label-hint">点击切换开关</span></h3>
      <div class="row"><input v-model="newEngineName" placeholder="引擎名称" style="flex:1"><button class="btn btn-s" @click="addEngine">+ 添加</button></div>
      <div><span v-for="e in engines" :key="e.name" class="tag" :class="e.enabled?'tag-g':'tag-r'" style="cursor:pointer;margin:4px" @click="toggleEngine(e)">{{ e.name }} {{ e.enabled?'●':'○' }}</span><span v-if="!engines.length" style="color:#9b95b0;font-size:13px">暂无</span></div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h3>🔌 MCP 服务 <span class="label-hint">自由增删</span></h3>
      <div class="row">
        <input v-model="mcpForm.name" placeholder="名称" style="flex:1">
        <input v-model="mcpForm.url" placeholder="地址" style="flex:1">
        <button class="btn btn-s" @click="addMCP">+</button>
      </div>
      <div v-for="s in mcpServers" :key="s.name" class="tag" :class="s.enabled?'tag-g':''" style="cursor:pointer;margin:4px;display:inline-flex;align-items:center;gap:4px" @click="toggleMCP(s)">{{ s.name }} {{ s.enabled?'●':'○' }} <span style="cursor:pointer;color:#dc2626" @click.stop="deleteMCP(s.name)">✕</span></span>
      <div v-if="!mcpServers.length" style="color:#9b95b0;font-size:13px">暂无 MCP 服务</div>
    </div>

    <div class="card">
      <h3>🧩 Skills <span class="label-hint">自由增删</span></h3>
      <div class="row">
        <input v-model="skillForm.name" placeholder="名称" style="flex:1">
        <input v-model="skillForm.desc" placeholder="描述" style="flex:1">
        <button class="btn btn-s" @click="addSkill">+</button>
      </div>
      <div v-for="s in skills" :key="s.name" class="tag" :class="s.enabled?'tag-g':''" style="cursor:pointer;margin:4px;display:inline-flex;align-items:center;gap:4px" @click="toggleSkill(s)">{{ s.name }} {{ s.enabled?'●':'○' }} <span style="cursor:pointer;color:#dc2626" @click.stop="deleteSkill(s.name)">✕</span></span>
      <div v-if="!skills.length" style="color:#9b95b0;font-size:13px">暂无 Skills</div>
    </div>
  </div>

  <div class="card">
    <h3>💬 对话测试</h3>
    <div class="chat-box" ref="chatBox">
      <div v-for="(m,i) in chat" :key="i" class="msg" :class="m.role==='user'?'right':'left'">
        <div>
          <div class="b">{{ m.content }}</div>
          <div class="reason" v-if="m.reasoning && cfg.features?.keep_thinking">💭 {{ m.reasoning.slice(0,200) }}{{ m.reasoning.length>200?'...':'' }}</div>
        </div>
      </div>
      <div v-if="loading" class="msg left"><div class="b" style="color:#9b95b0">思考中...</div></div>
    </div>
    <div class="chat-in">
      <input v-model="chatInput" @keyup.enter="sendChat" placeholder="输入消息..." :disabled="loading">
      <button class="btn btn-p" @click="sendChat" :disabled="!chatInput.trim()||loading">{{ loading?'...':'发送' }}</button>
      <button class="btn btn-o" @click="chat=[]">清屏</button>
    </div>
    <div v-if="lastTools?.length" style="margin-top:8px;font-size:12px;color:#9b95b0">🔧 工具: {{ lastTools.join(', ') }}</div>
  </div>
</div>

<script>
const {createApp}=Vue;
createApp({
  data:()=>({
    cfg:{persona:{enabled:true},web_search:{enabled:false,engines:[]},features:{keep_thinking:false},memory:{enabled:false},mcp:{enabled:false},skills:{enabled:false}},
    personas:[],engines:[],mcpServers:[],skills:[],
    activePersona:'',newPersonaName:'',newEngineName:'',
    mcpForm:{name:'',url:''},skillForm:{name:'',desc:''},
    chat:[],chatInput:'',loading:false,lastTools:[],sid:'test_'+Date.now(),status:'加载中...',
  }),
  mounted(){this.loadAll()},
  methods:{
    async api(path,opts={}){
      try{const r=await fetch(path,{headers:{'Content-Type':'application/json'},...opts,body:opts.body?JSON.stringify(opts.body):undefined});return await r.json()}catch{return null}
    },
    async loadAll(){
      const s=await this.api('/api/stats');if(s)this.status='运行中 '+Math.floor(s.uptime_seconds)+'s';
      const c=await this.api('/api/config');if(c){this.cfg=c;this.activePersona=c.persona?.active||'default';}
      const p=await this.api('/api/personas');if(Array.isArray(p))this.personas=p;
      const e=await this.api('/api/search/engines');if(e){this.engines=e.engines||[];if(this.cfg.web_search)this.cfg.web_search.enabled=e.enabled;}
      const m=await this.api('/api/mcp/servers');if(m)this.mcpServers=m.servers||[];
      const sk=await this.api('/api/skills');if(sk)this.skills=sk.skills||[];
    },
    async toggle(path){
      const parts=path.split('.');let obj=this.cfg;
      for(let i=0;i<parts.length-1;i++)obj=obj[parts[i]];
      obj[parts[parts.length-1]]=!obj[parts[parts.length-1]];
      const body={};
      if(path.startsWith('persona'))body.persona=this.cfg.persona;
      else if(path.startsWith('web_search'))body.web_search=this.cfg.web_search;
      else if(path.startsWith('features'))body.features=this.cfg.features;
      else if(path.startsWith('mcp'))body.mcp=this.cfg.mcp;
      else if(path.startsWith('skills'))body.skills=this.cfg.skills;
      await this.api('/api/config',{method:'POST',body});
    },
    async toggleMemory(){
      const enabled=!this.cfg.memory?.enabled;
      const r=await this.api('/api/memory/toggle',{method:'POST',body:{enabled}});
      if(r?.status==='ok'){this.cfg.memory.enabled=r.enabled;this.cfg.memory.mode=r.mode;}
    },
    async switchPersona(){const r=await this.api('/api/personas/'+this.activePersona+'/activate',{method:'POST'});if(r?.status==='ok')this.loadAll();},
    async addPersona(){
      if(!this.newPersonaName.trim())return;
      const r=await this.api('/api/personas',{method:'POST',body:{name:this.newPersonaName.trim(),prompt:'你是一个AI助手。',description:'',preset_conversations:[]}});
      if(r?.status==='ok'){this.newPersonaName='';this.loadAll();}
    },
    async addEngine(){
      if(!this.newEngineName.trim())return;
      const r=await this.api('/api/search/engines',{method:'POST',body:{name:this.newEngineName.trim(),type:'web',enabled:true}});
      if(r?.engines){this.engines=r.engines;this.newEngineName='';}
    },
    async toggleEngine(e){e.enabled=!e.enabled;await this.api('/api/search/engines/'+e.name,{method:'PUT',body:{enabled:e.enabled}});},
    async addMCP(){
      if(!this.mcpForm.name.trim())return;
      const r=await this.api('/api/mcp/servers',{method:'POST',body:{name:this.mcpForm.name.trim(),url:this.mcpForm.url.trim(),description:'',enabled:true}});
      if(r?.servers){this.mcpServers=r.servers;this.mcpForm={name:'',url:''};}
    },
    async toggleMCP(s){s.enabled=!s.enabled;await this.api('/api/mcp/servers/'+s.name,{method:'PUT',body:{enabled:s.enabled}});},
    async deleteMCP(name){await this.api('/api/mcp/servers/'+name,{method:'DELETE'});const r=await this.api('/api/mcp/servers');if(r)this.mcpServers=r.servers||[];},
    async addSkill(){
      if(!this.skillForm.name.trim())return;
      const r=await this.api('/api/skills',{method:'POST',body:{name:this.skillForm.name.trim(),description:this.skillForm.desc.trim(),prompt:'',enabled:true}});
      if(r?.skills){this.skills=r.skills;this.skillForm={name:'',desc:''};}
    },
    async toggleSkill(s){s.enabled=!s.enabled;await this.api('/api/skills/'+s.name,{method:'PUT',body:{enabled:s.enabled}});},
    async deleteSkill(name){await this.api('/api/skills/'+name,{method:'DELETE'});const r=await this.api('/api/skills');if(r)this.skills=r.skills||[];},
    async sendChat(){
      const msg=this.chatInput.trim();if(!msg||this.loading)return;
      this.chat.push({role:'user',content:msg});this.chatInput='';this.loading=true;
      this.$nextTick(()=>this.scroll());
      const r=await this.api('/api/chat',{method:'POST',body:{message:msg,session_id:this.sid}});
      this.loading=false;
      if(r){this.chat.push({role:'assistant',content:r.reply||'（无回复）',reasoning:r.reasoning||null});this.lastTools=(r.tools_used||[]).map(t=>t.name);}
      this.$nextTick(()=>this.scroll());
    },
    scroll(){const el=this.$refs.chatBox;if(el)el.scrollTop=el.scrollHeight;}
  }
}).mount('#app');
</script>
</body>
</html>"""

# 注意：测试页面已独立为 webui/index.html，此处的 TEST_PAGE_HTML 保留用于 /test 端点
# 前端页面可通过 http://localhost:8765/admin 或 http://localhost:8765/test 访问
