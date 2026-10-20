"""
工作空间管理 API
提供工作空间的 CRUD、任务管理、Agent 管理等接口
"""
import logging
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局引用
_workspace_manager = None
_agent_config_manager = None
_provider_manager = None
_context = None
_agent_context = None
_agent_loop = None
_memory_selector = None
_persona_manager = None
_tool_registry = None
_main_config = None


def set_workspace_manager(mgr):
    global _workspace_manager
    _workspace_manager = mgr


def set_workspace_exec_deps(
    agent_config_manager=None, provider_manager=None,
    context=None, agent_context=None, memory=None, persona_manager=None,
    tool_registry=None, main_config=None, agent_loop=None,
):
    """注入子 Agent 执行所需的依赖"""
    global _agent_config_manager, _provider_manager, _context, _agent_context
    global _memory_selector, _persona_manager, _tool_registry, _main_config, _agent_loop
    _agent_config_manager = agent_config_manager
    _provider_manager = provider_manager
    _context = context
    _agent_context = agent_context
    _agent_loop = agent_loop
    _memory_selector = memory
    _persona_manager = persona_manager
    _tool_registry = tool_registry
    _main_config = main_config


# ─── Request Models ───

class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""
    shared_context: dict = {}
    agents: list = []
    agent_ref_ids: list = []


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    shared_context: Optional[dict] = None
    agents: Optional[list] = None


class AddTaskRequest(BaseModel):
    agent: str
    description: str
    depends_on: list = []


class UpdateTaskRequest(BaseModel):
    status: str          # pending / working / done / failed
    result: str = ""


class AddAgentRequest(BaseModel):
    agent_name: str
    agent_ref_id: str = ""


class UpdateAgentRequest(BaseModel):
    status: str = ""
    progress: str = ""
    result_summary: str = ""


# ─── API 端点 ───

@router.get("/workspaces")
async def list_workspaces(status: str = None):
    """列出所有工作空间"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    workspaces = _workspace_manager.list_workspaces(status=status)
    # 添加统计信息
    result = []
    for ws in workspaces:
        stats = _workspace_manager.get_workspace_stats(ws["workspace_id"])
        result.append(stats)
    return {"workspaces": result, "total": len(result)}


@router.post("/workspaces")
async def create_workspace(req: CreateWorkspaceRequest):
    """创建工作空间"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    ws = _workspace_manager.create_workspace(
        name=req.name,
        description=req.description,
        shared_context=req.shared_context,
        agents=req.agents,
        agent_ref_ids=req.agent_ref_ids,
    )
    return {"workspace": ws, "message": f"工作空间「{req.name}」创建成功"}


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str):
    """获取工作空间详情"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    ws = _workspace_manager.get_workspace(workspace_id)
    if not ws:
        return {"error": "工作空间不存在"}
    return {"workspace": ws}


@router.put("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, req: UpdateWorkspaceRequest):
    """更新工作空间"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    ws = _workspace_manager.update_workspace(workspace_id, updates)
    if not ws:
        return {"error": "工作空间不存在"}
    return {"workspace": ws, "message": "更新成功"}


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str, cleanup: bool = Query(True)):
    """删除工作空间"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    success = _workspace_manager.delete_workspace(workspace_id, cleanup_files=cleanup)
    if not success:
        return {"error": "工作空间不存在"}
    return {"message": "工作空间已删除"}


@router.get("/workspaces/{workspace_id}/stats")
async def get_workspace_stats(workspace_id: str):
    """获取工作空间统计"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    stats = _workspace_manager.get_workspace_stats(workspace_id)
    if not stats:
        return {"error": "工作空间不存在"}
    return {"stats": stats}


# ─── 任务管理 ───

@router.get("/workspaces/{workspace_id}/tasks")
async def list_tasks(workspace_id: str, status: str = None):
    """列出工作空间的任务"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    ws = _workspace_manager.get_workspace(workspace_id)
    if not ws:
        return {"error": "工作空间不存在"}

    tasks = ws.get("tasks", [])
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/workspaces/{workspace_id}/tasks")
async def add_task(workspace_id: str, req: AddTaskRequest):
    """添加任务"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    task_id = _workspace_manager.add_task(
        workspace_id, req.agent, req.description, req.depends_on
    )
    if not task_id:
        return {"error": "工作空间不存在"}
    return {"task_id": task_id, "message": "任务添加成功"}


@router.put("/workspaces/{workspace_id}/tasks/{task_id}")
async def update_task(workspace_id: str, task_id: str, req: UpdateTaskRequest):
    """更新任务状态"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    success = _workspace_manager.update_task_status(
        workspace_id, task_id, req.status, req.result
    )
    if not success:
        return {"error": "任务或工作空间不存在"}
    return {"message": f"任务已更新为 {req.status}"}


# ─── Agent 管理 ───

@router.get("/workspaces/{workspace_id}/agents")
async def list_agents(workspace_id: str):
    """查看工作空间内的 Agent 状态"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    ws = _workspace_manager.get_workspace(workspace_id)
    if not ws:
        return {"error": "工作空间不存在"}

    agents = ws.get("agents", [])
    return {"agents": agents, "total": len(agents)}


@router.post("/workspaces/{workspace_id}/agents")
async def add_agent_to_workspace(workspace_id: str, req: AddAgentRequest):
    """向工作空间添加 Agent"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    success = _workspace_manager.add_agent(
        workspace_id, req.agent_name, req.agent_ref_id
    )
    if not success:
        return {"error": "工作空间不存在或 Agent 已存在"}
    return {"message": f"Agent「{req.agent_name}」已添加到工作空间"}


@router.put("/workspaces/{workspace_id}/agents/{agent_name}")
async def update_agent_in_workspace(
    workspace_id: str, agent_name: str, req: UpdateAgentRequest
):
    """更新工作空间内 Agent 的状态"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    success = _workspace_manager.update_agent_status(
        workspace_id, agent_name, req.status, req.progress, req.result_summary
    )
    if not success:
        return {"error": "工作空间或 Agent 不存在"}
    return {"message": f"Agent「{agent_name}」状态已更新"}


@router.get("/workspaces/{workspace_id}/logs")
async def get_workspace_logs(
    workspace_id: str,
    agent: str = Query(None, description="按 Agent 筛选"),
    limit: int = Query(100, description="返回条数"),
):
    """获取工作空间的对话日志，可按 Agent 筛选"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    ws = _workspace_manager.get_workspace(workspace_id)
    if not ws:
        return {"error": "工作空间不存在"}

    # 从 agent_sessions 中获取各 Agent 的会话 ID
    agent_sessions = ws.get("agent_sessions", {})
    logs = []

    # 1. 读取主脑在工作空间中的对话（无 @ 的消息）
    ws_brain_session = f"ws_{workspace_id}"
    main_db = getattr(_workspace_manager, '_db', None)
    if main_db:
        conv = await main_db.get_conversation(ws_brain_session)
        if conv and conv.content:
            for msg in conv.content[-limit:]:
                msg["agent"] = "主脑"
                logs.append(msg)

    # 2. 读取 agent_data.db 中的子 Agent 对话（有 @ 的消息）
    agent_db = getattr(_workspace_manager, '_agent_db', None)
    if agent_db:
        for aname, sid in agent_sessions.items():
            if agent and aname != agent:
                continue
            conv = await agent_db.get_conversation(sid)
            if conv and conv.content:
                for msg in conv.content[-limit:]:
                    msg["agent"] = aname
                    logs.append(msg)
    elif main_db:
        # 降级：从主脑数据库查（兼容旧数据）
        for aname, sid in agent_sessions.items():
            if agent and aname != agent:
                continue
            conv = await main_db.get_conversation(sid)
            if conv and conv.content:
                for msg in conv.content[-limit:]:
                    msg["agent"] = aname
                    logs.append(msg)

    # 按时间排序（如果有 timestamp 字段）
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"logs": logs[:limit], "total": len(logs[:limit])}




@router.post("/workspaces/{workspace_id}/execute")
async def execute_workspace_command(workspace_id: str, data: dict):
    """
    在工作空间中执行 @ 命令，路由到子 Agent

    Body: {"message": "@code 帮我写个登录页"}
    """
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    message = data.get("message", "")
    if not message:
        return {"error": "消息不能为空"}

    from workspace.router import route_and_execute
    result = await route_and_execute(
        message=message,
        agent_config_manager=_agent_config_manager,
        workspace_manager=_workspace_manager,
        provider_manager=_provider_manager,
        context=_agent_context or _context,
        memory=_memory_selector,
        persona_manager=_persona_manager,
        tool_registry=_tool_registry,
        main_config=_main_config,
    )
    # 如果子 Agent 执行成功，通知主脑
    if result.get("routed") and result.get("target") and result.get("target") != "brain":
        target = result.get("target", "agent")
        reply = result.get("reply", "")
        
        # 主脑审核子 Agent 的执行结果
        review = ""
        if _agent_loop and hasattr(_agent_loop, 'provider'):
            try:
                task_desc = message[message.index(" ") + 1:] if " " in message else ""
                review_prompt = (
                    f"你是一个项目经理，请简要审核子Agent [{target}] 完成的工作。\n"
                    f"任务: {task_desc[:200]}\n"
                    f"执行结果: {reply[:500]}\n\n"
                    f"请用1-2句话给出评价，包括是否完成任务、有无问题、建议等。"
                )
                review_resp = await _agent_loop.provider.chat(
                    messages=[{"role": "user", "content": review_prompt}],
                    temperature=0.3,
                    max_tokens=200,
                )
                review = review_resp.get("content", "").strip()
                if review:
                    review = f"\n\n🧠 主脑审核: {review}"
            except Exception as e:
                logger.warning(f"主脑审核失败: {e}")

        full_reply = reply + review
        summary = f"[{target}] 在工作空间 [{workspace_id[:8]}...] 执行完成: {reply[:100]}" 
        if _context and hasattr(_context, 'add_message'):
            try:
                import asyncio
                # 写入工作空间会话（工作空间对话页可见）
                asyncio.ensure_future(_context.add_message(
                    f"ws_{workspace_id}", "system", summary
                ))
                # 写入主聊天默认会话（主脑能感知）
                asyncio.ensure_future(_context.add_message(
                    "default", "system", summary
                ))
            except Exception as e:
                logger.warning(f"通知主脑失败: {e}")

    # 只有真正没被路由的消息（未知的 @）才走主脑回复
    if not result.get("routed") and _agent_loop:
        # 去掉 @ 前缀再发给主脑，避免主脑看到 @ 感到困惑
        clean_message = message
        if message.startswith("@"):
            clean_message = message[message.index(" ") + 1:] if " " in message else ""
        if clean_message:
            try:
                session_id = f"ws_{workspace_id}"
                brain_result = await _agent_loop.run(clean_message, session_id)
                if brain_result and brain_result.get("reply"):
                    return {"routed": False, "target": "brain", "reply": brain_result["reply"]}
            except Exception as e:
                logger.warning(f"主脑回复失败: {e}")
        else:
            return {"routed": False, "target": "brain", "reply": "请说具体任务，或使用 @Agent名称 来指派给子 Agent"}
        # 如果有审核结果，附加到回复中
    if result.get("routed") and result.get("target") and result.get("target") != "brain":
        if review:
            result["reply"] = full_reply
            result["review"] = review
    return result

@router.get("/workspaces/{workspace_id}/files")
async def list_workspace_files(workspace_id: str):
    """列出工作空间 output 目录中的文件"""
    if not _workspace_manager:
        return {"error": "工作空间系统未初始化"}

    import os
    output_dir = _workspace_manager._output_dir(workspace_id)
    if not os.path.exists(output_dir):
        return {"files": [], "total": 0}

    files = []
    for fname in os.listdir(output_dir):
        filepath = os.path.join(output_dir, fname)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            files.append({
                "name": fname,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })

    files.sort(key=lambda f: f.get("modified", 0), reverse=True)
    return {"files": files, "total": len(files)}
