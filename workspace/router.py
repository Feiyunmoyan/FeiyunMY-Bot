"""
@ 路由解析器
解析消息中的 @ 前缀，路由到目标 Agent 或主脑
"""
import logging
from typing import Optional, NamedTuple

logger = logging.getLogger(__name__)

# 主脑的特殊名称（不可用作子 Agent 名）
BRAIN_ALIASES = {"主脑", "大脑", "brain"}


class RouteResult(NamedTuple):
    """路由解析结果"""
    target: Optional[str]      # None = 路由到主脑, "code" = 路由到 code_agent
    content: str               # 去除 @ 前缀后的实际消息内容
    is_route: bool             # 是否是路由指令


def parse_route(message: str, known_agents: set = None) -> RouteResult:
    """
    解析消息中的 @ 路由指令

    规则：
    - 消息以 @ 开头 → 尝试解析为路由指令
    - @ 不在开头 → 当作普通文本

    Args:
        message: 用户/Agent 发送的原始消息
        known_agents: 已知的子 Agent 名称集合

    Returns:
        RouteResult(target, content, is_route)

    示例：
        "@code 帮我写登录页" → RouteResult("code", "帮我写登录页", True)
        "@主脑 任务完成"     → RouteResult(None, "任务完成", True)  # None = 主脑
        "发邮件到 user@example.com" → RouteResult(None, "...", False)
        "普通消息"           → RouteResult(None, "普通消息", False)
    """
    if not message or not message.startswith("@"):
        return RouteResult(target=None, content=message, is_route=False)

    # 解析 @ 后面的内容
    rest = message[1:].strip()
    if not rest:
        # 只有 @ 没有内容，当作普通文本
        return RouteResult(target=None, content=message, is_route=False)

    # 分割 Agent 名和实际内容
    parts = rest.split(" ", 1)
    agent_name = parts[0].strip()
    content = parts[1].strip() if len(parts) > 1 else ""

    # 检查是否是主脑别名
    if agent_name.lower() in BRAIN_ALIASES:
        return RouteResult(target=None, content=content, is_route=True)

    # 检查是否是已知的 Agent
    if known_agents and agent_name in known_agents:
        return RouteResult(target=agent_name, content=content, is_route=True)

    # 不知道这个 @ 对象，当作普通文本
    logger.debug(f"未知的 @ 目标: {agent_name}，已知 Agent: {known_agents}")
    return RouteResult(target=None, content=message, is_route=False)


def is_brain_alias(name: str) -> bool:
    """检查是否是主脑别名"""
    return name.lower() in BRAIN_ALIASES


def get_known_agents_from_workspace(workspace_manager) -> set:
    """
    从工作空间管理器获取所有已知的 Agent 名称

    Args:
        workspace_manager: WorkspaceManager 实例

    Returns:
        set: 所有 Agent 名称的集合
    """
    agents = set()
    for ws in workspace_manager.list_workspaces():
        for agent in ws.get("agents", []):
            agents.add(agent.get("name", ""))
    return agents


async def route_and_execute(
    message: str,
    agent_config_manager=None,
    workspace_manager=None,
    provider_manager=None,
    context=None,
    agent_context=None,
    memory=None,
    persona_manager=None,
    tool_registry=None,
    main_config=None,
) -> dict:
    """
    解析 @ 路由并执行子 Agent

    Args:
        message: 用户消息（可能以 @ 开头）
        ... 各依赖注入

    Returns:
        {"routed": bool, "target": str, "result": dict, "reply": str}
    """
    from agent.agent_runner import SubAgentExecutor

    # 获取已知 Agent 名称
    known = set()
    if agent_config_manager:
        known = agent_config_manager.get_all_agent_names()

    logger.info(f"route_and_execute: message={message[:60]}, known_agents={known}")

    # 解析路由
    route = parse_route(message, known)
    logger.info(f"parse_route: is_route={route.is_route}, target={route.target}, content={route.content[:30] if route.content else ''}")

    if not route.is_route:
        logger.warning(f"@ 路由未识别: {message[:60]}, known={known}")
        return {"routed": False, "target": None, "result": None, "reply": message}

    # 路由到主脑 -> 标记为已路由，让调用方知道是主脑
    if route.target is None:
        return {"routed": True, "target": "brain", "result": None, "reply": route.content}

    # 路由到子 Agent
    agent_name = route.target
    task_content = route.content

    logger.info(f"路由到子 Agent [{agent_name}]: {task_content[:50]}...")

    # 查找 Agent 配置
    agent_config = None
    if agent_config_manager:
        agent_config = agent_config_manager.get_agent_by_name(agent_name)

    if not agent_config:
        return {
            "routed": True, "target": agent_name,
            "result": None,
            "reply": f"未找到 Agent [{agent_name}] 的配置，请先在仪表盘创建。"
        }

    # 创建工作空间（如果没有活跃的工作空间）
    workspace_id = None
    if workspace_manager:
        workspaces = workspace_manager.list_workspaces(status="active")
        if workspaces:
            workspace_id = workspaces[0]["workspace_id"]
        else:
            ws = workspace_manager.create_workspace(
                name=f"@{agent_name} 任务",
                description=f"由 @{agent_name} 触发的任务: {task_content[:50]}",
                agents=[{"name": agent_name, "agent_ref_id": agent_config.get("agent_id", "")}],
            )
            workspace_id = ws["workspace_id"]

    # 执行子 Agent
    executor = SubAgentExecutor(
        agent_config=agent_config,
        task_description=task_content,
        workspace_id=workspace_id or "",
        provider_manager=provider_manager,
        context=agent_context or context,
        memory=memory,
        persona_manager=persona_manager,
        tool_registry=tool_registry,
        workspace_manager=workspace_manager,
        main_config=main_config,
    )

    result = await executor.run()

    reply = f"🤖 **{agent_config.get('display_name', agent_name)}** 已完成任务！\n\n{result.get('reply', '无输出')}"
    if result.get("tools_used"):
        reply += f"\n\n📌 使用了工具: {', '.join(result['tools_used'])}"

    return {
        "routed": True,
        "target": agent_name,
        "result": result,
        "reply": reply,
    }
