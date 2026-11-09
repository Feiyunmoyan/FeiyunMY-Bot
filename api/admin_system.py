"""系统统计 / 日志 / 测试页"""
import logging
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 系统统计 ───

@router.get("/api/stats")
async def get_stats():
    uptime = time.time() - state.start_time
    web_search_enabled = state.config.get("web_search", {}).get("enabled", False)
    persona_enabled = state.config.get("persona", {}).get("enabled", True)
    keep_thinking = state.config.get("features", {}).get("keep_thinking", False)
    memory_enabled = state.config.get("memory", {}).get("enabled", False)
    mcp_enabled = state.config.get("mcp", {}).get("enabled", False)
    skills_enabled = state.config.get("skills", {}).get("enabled", False)

    mcp_count = len(state.mcp_manager.list_servers()) if state.mcp_manager else 0
    skills_count = len(state.skills_manager.list_skills()) if state.skills_manager else 0

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
    for t in state.tool_registry.list_tools():
        t["name"] = _tool_cn_names.get(t["name"], t["name"])
        tools_display.append(t)

    return {
        "uptime_seconds": round(uptime, 1),
        "memory_count": state.memory_selector.list_all(1, 1)["total"],
        "persona_count": len(state.persona_manager.list_personas()),
        "active_persona": state.persona_manager.active_name,
        "memory_mode": state.memory_selector.mode,
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
    from utils.logging import get_recent_logs, get_log_stats
    logs = get_recent_logs(lines=min(lines, 500), level=level, keyword=keyword)
    stats = get_log_stats()
    return {"logs": logs, "total": len(logs), "stats": stats}


# ─── 测试页面 ───

@router.get("/test", response_class=HTMLResponse)
async def test_page():
    from api.test_page import TEST_PAGE_HTML

    return HTMLResponse(TEST_PAGE_HTML)
