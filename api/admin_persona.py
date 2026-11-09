"""人格管理"""
import logging

from fastapi import APIRouter

from .admin_models import (
    PersonaCreate,
    PersonaUpdate,

)
from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 人格管理 ───

@router.get("/api/personas")
async def list_personas():
    return state.persona_manager.list_personas()


@router.get("/api/personas/{name}")
async def get_persona_detail(name: str):
    p = state.persona_manager.get_persona_detail(name)
    if not p:
        return {"status": "fail", "reason": "not found"}
    return p


@router.post("/api/personas")
async def create_persona(p: PersonaCreate):
    if p.name in state.persona_manager._personas:
        return {"status": "fail", "reason": "名称已存在"}
    ok = state.persona_manager.create_persona(p.name, p.prompt, {
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
    ok = state.persona_manager.update_persona(name, data)
    return {"status": "ok" if ok else "fail"}


@router.delete("/api/personas/{name}")
async def delete_persona(name: str):
    ok = state.persona_manager.delete_persona(name)
    return {"status": "ok" if ok else "fail"}


@router.post("/api/personas/{name}/activate")
async def activate_persona(name: str):
    ok = state.persona_manager.activate(name)
    if ok:
        state.config["persona"]["active"] = name
        state.save_config()
    return {"status": "ok" if ok else "fail"}


@router.post("/api/personas/reload")
async def reload_personas():
    """重载人格（从 YAML 文件重新加载）"""
    state.persona_manager.reload_personas()
    active = state.persona_manager.active_name
    state.config["persona"]["active"] = active
    return {"status": "ok", "active": active, "count": len(state.persona_manager.list_personas())}
