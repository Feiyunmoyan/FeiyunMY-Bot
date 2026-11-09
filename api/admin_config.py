"""配置管理"""
import logging

from fastapi import APIRouter

from .admin_models import (
    ConfigUpdate,
)
from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 配置管理 ───

@router.get("/api/config")
async def get_config():
    import copy
    safe_config = copy.deepcopy(state.config)
    # 过滤敏感字段，不暴露给前端
    if "web_search" in safe_config:
        safe_config["web_search"]["api_key"] = ""
    if "provider" in safe_config and "api_key" in safe_config["provider"]:
        safe_config["provider"]["api_key"] = ""
    return safe_config


@router.post("/api/config")
async def update_config(update: ConfigUpdate):
    if update.provider:
        state.config["provider"].update(update.provider)
    if update.memory:
        state.config["memory"].update(update.memory)
        # 记忆开关同步到 mode
        if "enabled" in update.memory:
            state.config["memory"]["mode"] = "memoria" if update.memory["enabled"] else "simple"
    if update.persona:
        state.config["persona"].update(update.persona)
    if update.tools:
        state.config["tools"].update(update.tools)
    if update.web_search:
        state.config["web_search"].update(update.web_search)
        # 动态更新搜索配置
        from tools.web_search import set_search_config
        ws = state.config["web_search"]
        set_search_config({"provider": ws.get("provider", "duckduckgo"), "api_key": ws.get("api_key", "")})
    if update.features:
        state.config["features"].update(update.features)
    if update.mcp:
        state.config["mcp"].update(update.mcp)
    if update.skills:
        state.config["skills"].update(update.skills)
    if update.shell_whitelist:
        state.config["shell_whitelist"].update(update.shell_whitelist)
        # 动态更新白名单
        from tools.agent_tools import set_shell_whitelist
        set_shell_whitelist(state.config["shell_whitelist"].get("commands", []))

    state.save_config()
    return {"status": "ok", "config": state.config}


@router.post("/api/config/reload")
async def reload_config():
    """热加载配置文件（从磁盘重新读取 config.yaml）"""
    try:
        from utils.config_reloader import reload_config as do_reload
        result = do_reload()
        # 更新全局配置引用
        from utils.config_reloader import get_config
        state.config = get_config()
        # 动态更新工具开关
        tools_cfg = state.config.get("tools", {})
        for name, enabled in tools_cfg.items():
            state.tool_registry.set_enabled(name, enabled)
        logger.info(f"配置热加载完成: {result['message']}")
        return result
    except Exception as e:
        logger.error(f"配置热加载失败: {e}")
        return {"status": "fail", "message": str(e)}
