"""
子 Agent 管理 API
提供 Agent 配置的 CRUD 操作接口
"""
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局引用
_agent_config_manager = None


def set_agent_config_manager(mgr):
    global _agent_config_manager
    _agent_config_manager = mgr


# ─── Request Models ───

class CreateAgentRequest(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    avatar: str = "🤖"
    model_id: str = ""
    persona_id: str = ""
    knowledge_base_id: str = ""
    memory_enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    tools_enabled: list = []


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    model_id: Optional[str] = None
    persona_id: Optional[str] = None
    knowledge_base_id: Optional[str] = None
    memory_enabled: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    tools_enabled: Optional[list] = None
    enabled_for_workspace: Optional[bool] = None


# ─── API 端点 ───

@router.get("/agents")
async def list_agents():
    """列出所有已注册的 Agent 配置"""
    if not _agent_config_manager:
        return {"error": "Agent 配置系统未初始化"}
    agents = _agent_config_manager.list_agents()
    return {"agents": agents, "total": len(agents)}


@router.post("/agents")
async def create_agent(req: CreateAgentRequest):
    """创建新 Agent 配置（含重名检测）"""
    if not _agent_config_manager:
        return {"error": "Agent 配置系统未初始化"}

    agent = _agent_config_manager.create_agent(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        avatar=req.avatar,
        model_id=req.model_id,
        persona_id=req.persona_id,
        knowledge_base_id=req.knowledge_base_id,
        memory_enabled=req.memory_enabled,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        tools_enabled=req.tools_enabled,
    )
    if not agent:
        return {"error": f"创建失败，名称「{req.name}」不可用（系统保留或已存在）"}
    return {"agent": agent, "message": f"Agent「{req.name}」创建成功"}


@router.get("/agents/names")
async def get_agent_names(enabled_only: bool = False):
    """
    获取所有 Agent 名称列表（供前端下拉选择）

    Args:
        enabled_only: 为 true 时只返回启用了工作空间可用的 Agent
    """
    if not _agent_config_manager:
        return {"error": "Agent 配置系统未初始化"}
    names = _agent_config_manager.get_agent_names_with_ids(enabled_only=enabled_only)
    return {"agents": names}
@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """查看单个 Agent 配置详情"""
    if not _agent_config_manager:
        return {"error": "Agent 配置系统未初始化"}
    agent = _agent_config_manager.get_agent(agent_id)
    if not agent:
        return {"error": "Agent 不存在"}
    return {"agent": agent}


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, req: UpdateAgentRequest):
    """更新 Agent 配置"""
    if not _agent_config_manager:
        return {"error": "Agent 配置系统未初始化"}

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        return {"error": "没有需要更新的字段"}

    agent = _agent_config_manager.update_agent(agent_id, updates)
    if not agent:
        return {"error": "Agent 不存在或名称冲突"}
    return {"agent": agent, "message": "更新成功"}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """删除 Agent 配置"""
    if not _agent_config_manager:
        return {"error": "Agent 配置系统未初始化"}

    success = _agent_config_manager.delete_agent(agent_id)
    if not success:
        return {"error": "Agent 不存在"}
    return {"message": "Agent 已删除"}


