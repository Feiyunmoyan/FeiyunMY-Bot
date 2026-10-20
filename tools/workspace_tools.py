"""
工作空间工具集
合并为一个 workspace 工具，AI 通过 operation 参数实现 CRUD
"""
import logging

logger = logging.getLogger(__name__)

# 全局引用
_workspace_manager = None


def set_workspace_manager(mgr):
    global _workspace_manager
    _workspace_manager = mgr


# 每次工具调用粗略估算 token（AI 思考和响应的平均消耗）
ESTIMATED_TOOL_TOKEN_COST = 500


def _record_token(workspace_id: str, tokens: int = ESTIMATED_TOOL_TOKEN_COST):
    """记录 token 消耗到工作空间"""
    if _workspace_manager and workspace_id:
        _workspace_manager.add_token_usage(workspace_id, tokens)


# ─── 合并后的工具定义 ───

# 中文名映射定义
WORKSPACE_CN_DEFINITION = {
    "type": "function",
    "function": {
        "name": "工作空间",
        "description": "管理工作空间和任务。当用户提出需要多步骤协作的需求时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "创建", "list", "列表", "get", "查看", "update", "更新", "delete", "删除", "add_task", "添加任务", "update_task", "更新任务", "update_agent", "更新状态"],
                    "description": "操作类型"
                },
                "workspace_id": {"type": "string", "description": "工作空间 ID"},
                "name": {"type": "string", "description": "项目名称"},
                "description": {"type": "string", "description": "项目描述"},
                "agents": {"type": "array", "description": "Agent 名称列表", "items": {"type": "string"}},
                "shared_context": {"type": "string", "description": "项目上下文"},
                "agent": {"type": "string", "description": "Agent 名称"},
                "task_description": {"type": "string", "description": "任务描述"},
                "task_id": {"type": "string", "description": "任务 ID"},
                "task_status": {"type": "string", "enum": ["pending", "working", "done", "failed"], "description": "任务状态"},
                "task_result": {"type": "string", "description": "任务结果"},
                "depends_on": {"type": "array", "description": "依赖任务", "items": {"type": "string"}},
                "agent_name": {"type": "string", "description": "Agent 名称"},
                "agent_status": {"type": "string", "enum": ["working", "done", "failed", "paused"], "description": "Agent 状态"},
                "progress": {"type": "string", "description": "进度描述"}
            },
            "required": ["operation"]
        }
    }
}


WORKSPACE_DEFINITION = {
    "type": "function",
    "function": {
        "name": "workspace",
        "description": "管理工作空间和任务。当用户提出需要多步骤协作的需求（如搭建网站、开发应用、设计系统等）时，创建项目工作空间，然后添加任务派发给子 Agent，并跟踪各 Agent 的进度。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "create", "创建",
                        "list", "列表",
                        "get", "查看",
                        "update", "更新",
                        "delete", "删除",
                        "add_task", "添加任务",
                        "update_task", "更新任务",
                        "update_agent", "更新状态",
                    ],
                    "description": "操作类型：create/创建, list/列表, get/查看, update/更新, delete/删除, add_task/添加任务, update_task/更新任务, update_agent/更新状态"
                },
                # 通用参数
                "workspace_id": {
                    "type": "string",
                    "description": "工作空间 ID（get/update/delete/add_task/update_task/update_agent 时需要）"
                },
                "name": {
                    "type": "string",
                    "description": "工作空间名称（create 时需要）"
                },
                "description": {
                    "type": "string",
                    "description": "项目描述（create 时需要）"
                },
                "agents": {
                    "type": "array",
                    "description": "参与项目的 Agent 名称列表，如 ['code', 'design']（create 时可选）",
                    "items": {"type": "string"}
                },
                "shared_context": {
                    "type": "string",
                    "description": "项目全局上下文（create 时可选）"
                },
                # 任务相关
                "agent": {
                    "type": "string",
                    "description": "负责任务的 Agent 名称（add_task 时需要）"
                },
                "task_description": {
                    "type": "string",
                    "description": "任务描述（add_task 时需要）"
                },
                "task_id": {
                    "type": "string",
                    "description": "任务 ID（update_task 时需要）"
                },
                "task_status": {
                    "type": "string",
                    "enum": ["pending", "working", "done", "failed"],
                    "description": "任务状态（update_task 时需要）"
                },
                "task_result": {
                    "type": "string",
                    "description": "任务结果说明（update_task 时可选）"
                },
                "depends_on": {
                    "type": "array",
                    "description": "依赖的任务 ID 列表（add_task 时可选）",
                    "items": {"type": "string"}
                },
                # Agent 状态
                "agent_name": {
                    "type": "string",
                    "description": "Agent 名称（update_agent 时需要）"
                },
                "agent_status": {
                    "type": "string",
                    "enum": ["working", "done", "failed", "paused"],
                    "description": "Agent 状态（update_agent 时需要）"
                },
                "progress": {
                    "type": "string",
                    "description": "进度描述（update_agent 时可选），如「首页设计完成，正在做详情页」"
                }
            },
            "required": ["operation"]
        }
    }
}


# ─── 路由实现 ───

async def workspace(
    operation: str,
    workspace_id: str = "",
    name: str = "",
    description: str = "",
    agents: list = None,
    shared_context: str = "",
    agent: str = "",
    task_description: str = "",
    task_id: str = "",
    task_status: str = "",
    task_result: str = "",
    depends_on: list = None,
    agent_name: str = "",
    agent_status: str = "",
    progress: str = "",
) -> str:
    """统一的工作空间工具入口"""
    if not _workspace_manager:
        return "错误：工作空间系统未初始化"

    mgr = _workspace_manager

    # 中文操作名映射
    cn_map = {
        "创建": "create", "列表": "list", "查看": "get",
        "更新": "update", "删除": "delete",
        "添加任务": "add_task", "更新任务": "update_task",
        "更新状态": "update_agent",
    }
    operation = cn_map.get(operation, operation)

    if operation == "create":
        return await _op_create(mgr, name, description, agents or [], shared_context)

    elif operation == "list":
        return _op_list(mgr)

    elif operation == "get":
        return _op_get(mgr, workspace_id)

    elif operation == "update":
        return _op_update(mgr, workspace_id, name, description)

    elif operation == "delete":
        return _op_delete(mgr, workspace_id)

    elif operation == "add_task":
        return await _op_add_task(mgr, workspace_id, agent, task_description, depends_on or [])

    elif operation == "update_task":
        return _op_update_task(mgr, workspace_id, task_id, task_status, task_result)

    elif operation == "update_agent":
        return _op_update_agent(mgr, workspace_id, agent_name, agent_status, progress)

    return f"错误：未知操作「{operation}」"


# ─── 各操作实现 ───

async def _op_create(mgr, name, description, agents, shared_context):
    agent_list = [{"name": a, "agent_ref_id": ""} for a in agents]
    ctx = {"description": shared_context} if shared_context else {}

    ws = mgr.create_workspace(
        name=name,
        description=description,
        shared_context=ctx,
        agents=agent_list,
    )
    ws_id = ws["workspace_id"]
    return (
        f"工作空间已创建！\n"
        f"项目：{name}\n"
        f"ID：{ws_id[:8]}...\n"
        f"参与 Agent：{len(agent_list)} 个\n"
        f"描述：{description}\n\n"
        f"工作空间已就绪，可以开始分配任务了。"
    )


def _op_list(mgr):
    workspaces = mgr.list_workspaces()
    if not workspaces:
        return "暂无工作空间"

    lines = [f"共 {len(workspaces)} 个工作空间："]
    for ws in workspaces:
        status = ws.get("status", "?")
        name = ws.get("name", "?")
        wid = ws["workspace_id"][:8]
        tasks = len(ws.get("tasks", []))
        done = sum(1 for t in ws.get("tasks", []) if t.get("status") == "done")
        lines.append(f"  [{status}] {name} ({wid}...) - {done}/{tasks} 任务完成")
    return "\n".join(lines)


def _op_get(mgr, workspace_id):
    ws = mgr.get_workspace(workspace_id)
    if not ws:
        return "错误：工作空间不存在"

    stats = mgr.get_workspace_stats(workspace_id)
    tasks = ws.get("tasks", [])
    agents = ws.get("agents", [])

    lines = [
        f"项目：{ws.get('name', '?')}",
        f"状态：{ws.get('status', '?')}",
        f"描述：{ws.get('description', '')}",
        f"Token：{ws.get('token_usage', 0)}",
        f"任务：{stats.get('done_tasks', 0)}/{stats.get('total_tasks', 0)} 完成",
        f"Agent：{stats.get('active_agents', 0)}/{stats.get('total_agents', 0)} 活跃",
    ]

    if tasks:
        lines.append("\n任务列表：")
        for t in tasks:
            lines.append(f"  [{t.get('status', '?')}] {t.get('task_id', '?')} - {t.get('description', '')}")

    if agents:
        lines.append("\nAgent 状态：")
        for a in agents:
            p = f" - {a.get('progress', '')}" if a.get('progress') else ""
            lines.append(f"  [{a.get('status', '?')}] {a.get('name', '?')}{p}")

    return "\n".join(lines)


def _op_update(mgr, workspace_id, name, description):
    updates = {}
    if name:
        updates["name"] = name
    if description:
        updates["description"] = description

    if not updates:
        return "没有需要更新的内容"

    ws = mgr.update_workspace(workspace_id, updates)
    if not ws:
        return "错误：工作空间不存在"
    return "工作空间已更新"


def _op_delete(mgr, workspace_id):
    success = mgr.delete_workspace(workspace_id, cleanup_files=True)
    if not success:
        return "错误：工作空间不存在"
    return "工作空间已删除"


async def _op_add_task(mgr, workspace_id, agent, task_description, depends_on):
    if not workspace_id or not agent or not task_description:
        return "错误：缺少必填参数（workspace_id, agent, task_description）"

    task_id = mgr.add_task(workspace_id, agent, task_description, depends_on)
    _record_token(workspace_id)
    if not task_id:
        return "错误：工作空间不存在"

    dep_info = f"（依赖：{', '.join(depends_on)}）" if depends_on else ""
    return f"任务已创建：{task_id}\n{agent}：{task_description} {dep_info}"


def _op_update_task(mgr, workspace_id, task_id, task_status, task_result):
    if not workspace_id or not task_id or not task_status:
        return "错误：缺少必填参数（workspace_id, task_id, task_status）"

    success = mgr.update_task_status(workspace_id, task_id, task_status, task_result)
    _record_token(workspace_id)
    if not success:
        return "错误：任务或工作空间不存在"
    return f"任务 {task_id} 已更新为 {task_status}"


def _op_update_agent(mgr, workspace_id, agent_name, agent_status, progress):
    if not workspace_id or not agent_name or not agent_status:
        return "错误：缺少必填参数（workspace_id, agent_name, agent_status）"

    success = mgr.update_agent_status(workspace_id, agent_name, agent_status, progress)
    _record_token(workspace_id)
    if not success:
        return "错误：工作空间或 Agent 不存在"

    emojis = {"working": "🔄", "done": "✅", "failed": "❌", "paused": "⏸️"}
    emoji = emojis.get(agent_status, "•")
    prog = f" — {progress}" if progress else ""
    return f"{emoji} {agent_name}：{agent_status}{prog}"
