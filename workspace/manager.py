"""
工作空间管理器
负责工作空间的 CRUD、持久化、状态恢复
"""
import os
import json
import uuid
import time
import shutil
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 工作空间数据根目录
WORKSPACES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "workspaces"
)

# 默认状态
DEFAULT_STATUS = "active"       # active / paused / completed / failed


def _ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def _atomic_write(filepath: str, data: dict):
    """原子写入 JSON 文件"""
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, filepath)  # 原子替换


def _read_json(filepath: str) -> Optional[dict]:
    """安全读取 JSON 文件"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取 JSON 失败 {filepath}: {e}")
        return None


class WorkspaceManager:
    """
    工作空间管理器

    职责：
    - 工作空间 CRUD
    - 原子写入持久化
    - 重启时状态恢复
    - Token 消耗跟踪
    """

    def __init__(self, workspaces_dir: str = None, agent_config_manager=None):
        self._workspaces_dir = workspaces_dir or WORKSPACES_DIR
        _ensure_dir(self._workspaces_dir)
        self._agent_config_manager = agent_config_manager

        # 内存缓存: workspace_id -> workspace_data
        self._cache: Dict[str, dict] = {}

        # 启动时加载已有工作空间
        self._load_all()
        self._db = None  # SQLite 引用，由外部注入
        self._agent_db = None  # 子 Agent 独立数据库引用

    def set_agent_config_manager(self, mgr):
        """注入 Agent 配置管理器引用"""
        self._agent_config_manager = mgr

    def get_agent_config(self, agent_name: str) -> Optional[dict]:
        """通过 Agent 名称获取完整配置（从 AgentConfigManager 查询）"""
        if not self._agent_config_manager:
            return None
        agent = self._agent_config_manager.get_agent_by_name(agent_name)
        if not agent:
            return None
        return {
            "agent_id": agent.get("agent_id", ""),
            "name": agent.get("name", ""),
            "display_name": agent.get("display_name", ""),
            "avatar": agent.get("avatar", "🤖"),
            "model_id": agent.get("model_id", ""),
            "persona_id": agent.get("persona_id", ""),
            "knowledge_base_id": agent.get("knowledge_base_id", ""),
            "memory_enabled": agent.get("memory_enabled", True),
            "max_tokens": agent.get("max_tokens", 4096),
            "temperature": agent.get("temperature", 0.7),
            "tools_enabled": agent.get("tools_enabled", []),
        }

    # ─── 内部方法 ───

    def _workspace_path(self, workspace_id: str) -> str:
        """获取工作空间目录路径"""
        return os.path.join(self._workspaces_dir, workspace_id)

    def _state_file_path(self, workspace_id: str) -> str:
        """获取工作空间状态文件路径"""
        return os.path.join(self._workspaces_dir, workspace_id, "workspace.json")

    def _output_dir(self, workspace_id: str) -> str:
        """获取工作空间输出目录路径"""
        return os.path.join(self._workspaces_dir, workspace_id, "output")

    def _load_all(self):
        """扫描目录，加载所有工作空间到缓存"""
        if not os.path.exists(self._workspaces_dir):
            return

        for name in os.listdir(self._workspaces_dir):
            ws_dir = os.path.join(self._workspaces_dir, name)
            if not os.path.isdir(ws_dir):
                continue
            state_file = os.path.join(ws_dir, "workspace.json")
            data = _read_json(state_file)
            if data and "workspace_id" in data:
                self._cache[data["workspace_id"]] = data
                logger.info(f"加载工作空间: {data.get('name', name)} ({data['workspace_id'][:8]}...), 状态: {data.get('status', 'unknown')}")

        logger.info(f"共加载 {len(self._cache)} 个工作空间")

    def _save(self, workspace_id: str):
        """将指定工作空间写入磁盘（原子写入）"""
        data = self._cache.get(workspace_id)
        if not data:
            return
        ws_dir = self._workspace_path(workspace_id)
        _ensure_dir(ws_dir)
        _ensure_dir(self._output_dir(workspace_id))
        _atomic_write(self._state_file_path(workspace_id), data)

    # ─── CRUD ───

    def create_workspace(
        self,
        name: str,
        description: str = "",
        shared_context: dict = None,
        agents: list = None,
        agent_ref_ids: list = None,
    ) -> dict:
        """
        创建工作空间

        Args:
            name: 项目名称
            description: 项目描述
            shared_context: 项目全局上下文
            agents: 初始 Agent 列表 [{"name": "code", "agent_ref_id": "..."}, ...]
            agent_ref_ids: 从 AgentConfigManager 引用的 ID 列表，自动拉取配置

        Returns:
            workspace_data: 工作空间数据字典
        """
        workspace_id = uuid.uuid4().hex[:12]
        now = time.time()

        # 如果传了 agent_ref_ids，从 AgentConfigManager 拉取完整配置
        resolved_agents = list(agents or [])
        if agent_ref_ids and self._agent_config_manager:
            for ref_id in agent_ref_ids:
                # 尝试通过 ID 查找
                agent = self._agent_config_manager.get_agent(ref_id)
                if not agent:
                    # 尝试通过名称查找
                    agent = self._agent_config_manager.get_agent_by_name(ref_id)
                if agent:
                    resolved_agents.append({
                        "name": agent.get("name", ""),
                        "agent_ref_id": agent.get("agent_id", ""),
                        "status": "pending",
                        "progress": "",
                        "result_summary": "",
                    })

        workspace = {
            "workspace_id": workspace_id,
            "name": name,
            "description": description,
            "status": DEFAULT_STATUS,
            "created_at": now,
            "updated_at": now,
            "token_usage": 0,
            "shared_context": shared_context or {},
            "agents": resolved_agents,
            "tasks": [],
            "agent_sessions": {},       # agent_name -> session_id（引用 SQLite 会话）
        }

        self._cache[workspace_id] = workspace
        self._save(workspace_id)

        logger.info(f"创建工作空间: {name} ({workspace_id[:8]}...)")
        return workspace

    def get_workspace(self, workspace_id: str) -> Optional[dict]:
        """获取工作空间详情"""
        return self._cache.get(workspace_id)

    def list_workspaces(self, status: str = None) -> list:
        """
        列出工作空间

        Args:
            status: 按状态筛选，None 表示全部
        """
        workspaces = list(self._cache.values())
        if status:
            workspaces = [w for w in workspaces if w.get("status") == status]
        # 按更新时间降序
        workspaces.sort(key=lambda w: w.get("updated_at", 0), reverse=True)
        return workspaces

    def update_workspace(self, workspace_id: str, updates: dict) -> Optional[dict]:
        """
        更新工作空间

        Args:
            workspace_id: 工作空间 ID
            updates: 要更新的字段

        Returns:
            更新后的工作空间，失败返回 None
        """
        workspace = self._cache.get(workspace_id)
        if not workspace:
            logger.warning(f"工作空间不存在: {workspace_id}")
            return None

        # 不允许修改 workspace_id 和 created_at
        forbidden = ["workspace_id", "created_at"]
        for key in forbidden:
            updates.pop(key, None)

        workspace.update(updates)
        workspace["updated_at"] = time.time()
        self._save(workspace_id)

        logger.info(f"更新工作空间: {workspace.get('name')} ({workspace_id[:8]}...), 字段: {list(updates.keys())}")
        return workspace

    def delete_workspace(self, workspace_id: str, cleanup_files: bool = True) -> bool:
        """
        删除工作空间

        Args:
            workspace_id: 工作空间 ID
            cleanup_files: 是否清理文件目录

        Returns:
            是否成功删除
        """
        if workspace_id not in self._cache:
            logger.warning(f"工作空间不存在，无法删除: {workspace_id}")
            return False

        # 先标记为 completed
        self._cache[workspace_id]["status"] = "completed"
        self._cache[workspace_id]["updated_at"] = time.time()

        # 记录该工作空间的 agent 会话（清理 agent_data.db 用）
        agent_sessions = dict(self._cache[workspace_id].get("agent_sessions", {}))

        # 从缓存移除
        del self._cache[workspace_id]

        # 清理子 Agent 独立数据库中的会话
        if cleanup_files and self._agent_db:
            import asyncio
            for agent_name, session_id in agent_sessions.items():
                try:
                    # 删除会话和对应的对话记录
                    asyncio.ensure_future(self._agent_db.delete_session(session_id))
                    logger.info(f"已清理 Agent [{agent_name}] 会话: {session_id}")
                except Exception as e:
                    logger.warning(f"清理 Agent 会话失败 {session_id}: {e}")

        # 清理文件
        if cleanup_files:
            ws_dir = self._workspace_path(workspace_id)
            if os.path.exists(ws_dir):
                shutil.rmtree(ws_dir, ignore_errors=True)
                logger.info(f"已清理工作空间文件目录: {ws_dir}")
        else:
            # 保留文件但标记删除
            state_file = self._state_file_path(workspace_id)
            data = _read_json(state_file)
            if data:
                data["status"] = "deleted"
                data["updated_at"] = time.time()
                _atomic_write(state_file, data)

        logger.info(f"删除工作空间: {workspace_id[:8]}...")
        return True

    # ─── 任务管理 ───

    def add_task(self, workspace_id: str, agent: str, description: str,
                 depends_on: list = None) -> Optional[str]:
        """
        向工作空间添加任务

        Args:
            workspace_id: 工作空间 ID
            agent: 负责的 Agent 名称
            description: 任务描述
            depends_on: 依赖的任务 ID 列表

        Returns:
            任务 ID，失败返回 None
        """
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return None

        task_id = f"t{len(workspace['tasks']) + 1:03d}"
        task = {
            "task_id": task_id,
            "agent": agent,
            "description": description,
            "status": "pending",        # pending / working / done / failed
            "result": None,
            "depends_on": depends_on or [],
            "created_at": time.time(),
            "completed_at": None,
        }
        workspace["tasks"].append(task)
        workspace["updated_at"] = time.time()
        self._save(workspace_id)
        return task_id

    def update_task_status(self, workspace_id: str, task_id: str,
                           status: str, result: str = None) -> bool:
        """更新任务状态"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return False

        for task in workspace["tasks"]:
            if task["task_id"] == task_id:
                task["status"] = status
                if result:
                    task["result"] = result
                if status in ("done", "failed"):
                    task["completed_at"] = time.time()
                workspace["updated_at"] = time.time()
                self._save(workspace_id)
                return True
        return False

    def get_pending_tasks(self, workspace_id: str) -> list:
        """获取待处理的任务（依赖已满足的 pending 任务）"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return []

        ready = []
        for task in workspace["tasks"]:
            if task["status"] != "pending":
                continue
            # 检查依赖是否全部完成
            deps_met = all(
                any(t["task_id"] == dep and t["status"] == "done"
                    for t in workspace["tasks"])
                for dep in task["depends_on"]
            )
            if deps_met:
                ready.append(task)
        return ready

    # ─── Agent 管理 ───

    def add_agent(self, workspace_id: str, agent_name: str,
                  agent_ref_id: str = "") -> bool:
        """向工作空间添加 Agent"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return False

        # 检查是否已存在同名 Agent
        for a in workspace["agents"]:
            if a["name"] == agent_name:
                return False

        workspace["agents"].append({
            "name": agent_name,
            "agent_ref_id": agent_ref_id,
            "status": "pending",        # pending / working / done / failed
            "progress": "",
            "result_summary": "",
        })
        workspace["updated_at"] = time.time()
        self._save(workspace_id)
        return True

    def update_agent_status(self, workspace_id: str, agent_name: str,
                            status: str, progress: str = "",
                            result_summary: str = "") -> bool:
        """更新 Agent 状态"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return False

        for agent in workspace["agents"]:
            if agent["name"] == agent_name:
                agent["status"] = status
                if progress:
                    agent["progress"] = progress
                if result_summary:
                    agent["result_summary"] = result_summary
                workspace["updated_at"] = time.time()
                self._save(workspace_id)
                return True
        return False

    def get_agent_session(self, workspace_id: str, agent_name: str) -> Optional[str]:
        """获取 Agent 的会话 ID（用于关联 SQLite 中的对话历史）"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return None
        return workspace.get("agent_sessions", {}).get(agent_name)

    def set_agent_session(self, workspace_id: str, agent_name: str,
                          session_id: str) -> bool:
        """设置 Agent 的会话 ID"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return False
        if "agent_sessions" not in workspace:
            workspace["agent_sessions"] = {}
        workspace["agent_sessions"][agent_name] = session_id
        workspace["updated_at"] = time.time()
        self._save(workspace_id)
        return True

    # ─── Token 跟踪 ───

    def add_token_usage(self, workspace_id: str, tokens: int) -> bool:
        """增加 Token 消耗计数"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return False
        workspace["token_usage"] = workspace.get("token_usage", 0) + tokens
        workspace["updated_at"] = time.time()
        self._save(workspace_id)
        return True

    def get_token_usage(self, workspace_id: str) -> int:
        """获取当前 Token 消耗"""
        workspace = self._cache.get(workspace_id)
        if not workspace:
            return 0
        return workspace.get("token_usage", 0)

    # ─── 状态恢复（重启时调用） ───

    def recover_workspaces(self) -> list:
        """
        重启时恢复工作空间状态

        扫描所有 active 工作空间，检查其中的任务：
        - 全部 done → 标记 completed
        - 有 pending/working → 标记 paused

        Returns:
            需要通知用户的工作空间列表（被标记为 paused 的）
        """
        paused_workspaces = []

        for ws_id, ws in self._cache.items():
            if ws.get("status") != "active":
                continue

            tasks = ws.get("tasks", [])
            if not tasks:
                continue

            # 检查所有任务状态
            all_done = all(t.get("status") == "done" for t in tasks)
            has_unfinished = any(
                t.get("status") in ("pending", "working") for t in tasks
            )

            if all_done:
                # 全部完成，自动归档
                ws["status"] = "completed"
                ws["updated_at"] = time.time()
                self._save(ws_id)
                logger.info(f"工作空间 [{ws.get('name')}] 所有任务已完成，标记为 completed")

            elif has_unfinished:
                # 有未完成的任务 → 标记 paused
                ws["status"] = "paused"
                ws["updated_at"] = time.time()

                # 同时标记所有 working 的 Agent 为 paused
                for agent in ws.get("agents", []):
                    if agent.get("status") == "working":
                        agent["status"] = "paused"

                self._save(ws_id)
                paused_workspaces.append(ws)
                logger.info(f"工作空间 [{ws.get('name')}] 有未完成的任务，标记为 paused")

        return paused_workspaces

    def get_workspace_stats(self, workspace_id: str) -> dict:
        """获取工作空间统计信息"""
        ws = self._cache.get(workspace_id)
        if not ws:
            return {}

        tasks = ws.get("tasks", [])
        agents = ws.get("agents", [])

        return {
            "workspace_id": ws.get("workspace_id", ""),
            "name": ws.get("name", ""),
            "description": ws.get("description", ""),
            "status": ws.get("status", ""),
            "total_tasks": len(tasks),
            "done_tasks": sum(1 for t in tasks if t.get("status") == "done"),
            "pending_tasks": sum(1 for t in tasks if t.get("status") == "pending"),
            "working_tasks": sum(1 for t in tasks if t.get("status") == "working"),
            "failed_tasks": sum(1 for t in tasks if t.get("status") == "failed"),
            "total_agents": len(agents),
            "active_agents": sum(1 for a in agents if a.get("status") == "working"),
            "token_usage": ws.get("token_usage", 0),
            "created_at": ws.get("created_at", 0),
            "updated_at": ws.get("updated_at", 0),
        }
