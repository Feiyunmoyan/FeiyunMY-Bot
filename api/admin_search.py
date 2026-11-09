"""搜索引擎管理"""
import logging

from fastapi import APIRouter

from .admin_models import (
    SearchEngineCreate,
    SearchEngineUpdate,
)
from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 搜索引擎管理 ───

@router.get("/api/search/engines")
async def list_search_engines():
    engines = state.config.get("web_search", {}).get("engines", [])
    return {"engines": engines, "enabled": state.config.get("web_search", {}).get("enabled", False)}


@router.post("/api/search/engines")
async def add_search_engine(engine: SearchEngineCreate):
    engines = state.config.get("web_search", {}).get("engines", [])
    for e in engines:
        if e["name"] == engine.name:
            return {"status": "fail", "reason": "名称已存在"}
    engines.append({"name": engine.name, "type": engine.type, "enabled": engine.enabled})
    state.save_config()
    return {"status": "ok", "engines": engines}


@router.put("/api/search/engines/{name}")
async def update_search_engine(name: str, update: SearchEngineUpdate):
    engines = state.config.get("web_search", {}).get("engines", [])
    for e in engines:
        if e["name"] == name:
            if update.name is not None:
                e["name"] = update.name
            if update.type is not None:
                e["type"] = update.type
            if update.enabled is not None:
                e["enabled"] = update.enabled
            state.save_config()
            return {"status": "ok", "engines": engines}
    return {"status": "fail", "reason": "未找到"}


@router.delete("/api/search/engines/{name}")
async def delete_search_engine(name: str):
    engines = state.config.get("web_search", {}).get("engines", [])
    state.config["web_search"]["engines"] = [e for e in engines if e["name"] != name]
    state.save_config()
    return {"status": "ok", "engines": state.config["web_search"]["engines"]}
