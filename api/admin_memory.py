"""记忆管理 / 记忆与工具开关"""
import logging

from fastapi import APIRouter

from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 记忆管理 ───

@router.get("/api/memories")
async def list_memories(page: int = 1, page_size: int = 20):
    return state.memory_selector.list_all(page, page_size)


@router.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str):
    ok = state.memory_selector.delete(memory_id)
    return {"status": "ok" if ok else "fail"}


@router.post("/api/memories/clear")
async def clear_memories():
    ok = state.memory_selector.clear()
    return {"status": "ok" if ok else "fail"}


@router.post("/api/memory/switch")
async def switch_memory_mode(data: dict):
    """切换记忆模式（直接指定 simple/memoria）"""
    mode = data.get("mode", "simple")
    ok = state.memory_selector.switch_mode(mode)
    if ok:
        state.config["memory"]["mode"] = mode
        state.config["memory"]["enabled"] = (mode == "memoria")
        state.save_config()
    return {"status": "ok" if ok else "fail", "mode": mode}


@router.post("/api/memory/toggle")
async def toggle_memory(data: dict):
    """记忆开关：false=simple, true=memoria"""
    enabled = data.get("enabled", False)
    mode = "memoria" if enabled else "simple"
    ok = state.memory_selector.switch_mode(mode)
    if ok:
        state.config["memory"]["mode"] = mode
        state.config["memory"]["enabled"] = enabled
        state.save_config()
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
        if state.config:
            state.config.setdefault("tools", {})["file_ops_full_access"] = full_access
            state.save_config()

    state.tool_registry.set_enabled(tool_name, enabled)
    return {"status": "ok", "name": tool_name, "enabled": enabled}
