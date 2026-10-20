"""
Agent 配置管理器
负责子 Agent 配置的 CRUD、重名检测、与工作空间的关联
"""
import os
import json
import uuid
import time
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Agent 配置数据目录
AGENTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "agents"
)

# 主脑保留名称（子 Agent 不能使用）
RESERVED_NAMES = {"主脑", "大脑", "brain"}


class AgentConfigManager:
    """
    Agent 配置管理器

    职责：
    - 子 Agent 配置的 CRUD
    - 重名检测（不能和主脑重名、不能和其他 Agent 重名）
    - 配置持久化
    """

    def __init__(self, agents_dir: str = None):
        self._agents_dir = agents_dir or AGENTS_DIR
        os.makedirs(self._agents_dir, exist_ok=True)
        self._cache: Dict[str, dict] = {}
        self._load_all()

    def _file_path(self, agent_id: str) -> str:
        return os.path.join(self._agents_dir, f"{agent_id}.json")

    def _load_all(self):
        """加载所有 Agent 配置到缓存"""
        if not os.path.exists(self._agents_dir):
            return
        for fname in os.listdir(self._agents_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._agents_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "agent_id" in data and "name" in data:
                    self._cache[data["agent_id"]] = data
            except Exception as e:
                logger.warning(f"加载 Agent 配置失败 {fname}: {e}")
        logger.info(f"加载了 {len(self._cache)} 个 Agent 配置")

    def _save(self, agent_id: str):
        """持久化单个 Agent 配置"""
        data = self._cache.get(agent_id)
        if not data:
            return
        path = self._file_path(agent_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _delete_file(self, agent_id: str):
        """删除 Agent 配置文件"""
        path = self._file_path(agent_id)
        if os.path.exists(path):
            os.remove(path)

    # ─── 校验 ───

    def _check_name_available(self, name: str, exclude_id: str = "") -> Optional[str]:
        """
        检查名称是否可用

        Returns:
            None 表示可用，str 表示不可用的原因
        """
        if not name or not name.strip():
            return "名称不能为空"

        name = name.strip()

        if name.lower() in {n.lower() for n in RESERVED_NAMES}:
            return f"「{name}」是系统保留名称（主脑别名），不能用作子 Agent 名称"

        for aid, agent in self._cache.items():
            if aid == exclude_id:
                continue
            if agent.get("name", "").lower() == name.lower():
                return f"Agent 名称「{name}」已存在"

        return None

    # ─── CRUD ───

    def create_agent(self, name: str, display_name: str = "",
                     description: str = "", avatar: str = "🤖",
                     model_id: str = "", persona_id: str = "",
                     knowledge_base_id: str = "",
                     memory_enabled: bool = True,
                     max_tokens: int = 4096,
                     temperature: float = 0.7,
                     tools_enabled: list = None,
                     enabled_for_workspace: bool = True) -> Optional[dict]:
        """
        创建新的 Agent 配置

        Args:
            name: Agent 名称（用于 @ 路由，不能和主脑/其他 Agent 重名）
            display_name: 显示名称
            description: 描述
            avatar: 头像 emoji
            model_id: 引用的模型 ID
            persona_id: 引用的角色人格 ID
            knowledge_base_id: 引用的知识库 ID（可选）
            memory_enabled: 是否启用长期记忆
            max_tokens: 最大 Token 数
            temperature: 温度参数
            tools_enabled: 启用的工具列表
            enabled_for_workspace: 是否在工作空间中可用

        Returns:
            创建的 Agent 配置，失败返回 None（含错误信息）
        """
        # 重名检测
        err = self._check_name_available(name)
        if err:
            logger.warning(f"创建 Agent 失败: {err}")
            return None

        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        now = time.time()

        agent = {
            "agent_id": agent_id,
            "name": name.strip(),
            "display_name": display_name or name,
            "description": description,
            "avatar": avatar,
            "model_id": model_id,
            "persona_id": persona_id,
            "knowledge_base_id": knowledge_base_id,
            "memory_enabled": memory_enabled,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tools_enabled": tools_enabled or [],
            "enabled_for_workspace": enabled_for_workspace,
            "created_at": now,
            "updated_at": now,
        }

        self._cache[agent_id] = agent
        self._save(agent_id)

        logger.info(f"创建 Agent: {name} ({agent_id[:12]}...)")
        return agent

    def get_agent(self, agent_id: str) -> Optional[dict]:
        """获取 Agent 配置"""
        return self._cache.get(agent_id)

    def get_agent_by_name(self, name: str) -> Optional[dict]:
        """通过名称查找 Agent 配置"""
        name_lower = name.strip().lower()
        for agent in self._cache.values():
            if agent.get("name", "").lower() == name_lower:
                return agent
        return None

    def list_agents(self) -> list:
        """列出所有 Agent 配置"""
        agents = list(self._cache.values())
        agents.sort(key=lambda a: a.get("created_at", 0), reverse=True)
        return agents

    def update_agent(self, agent_id: str, updates: dict) -> Optional[dict]:
        """
        更新 Agent 配置

        Args:
            agent_id: Agent ID
            updates: 要更新的字段

        Returns:
            更新后的 Agent 配置，失败返回 None
        """
        agent = self._cache.get(agent_id)
        if not agent:
            logger.warning(f"更新失败，Agent 不存在: {agent_id}")
            return None

        # 不允许修改的字段
        for key in ["agent_id", "created_at"]:
            updates.pop(key, None)

        # 如果修改了名称，检查重名
        if "name" in updates:
            err = self._check_name_available(updates["name"], exclude_id=agent_id)
            if err:
                logger.warning(f"更新 Agent 失败: {err}")
                return None

        agent.update(updates)
        agent["updated_at"] = time.time()
        self._save(agent_id)

        logger.info(f"更新 Agent: {agent.get('name')} ({agent_id[:12]}...), 字段: {list(updates.keys())}")
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        """
        删除 Agent 配置

        注意：此操作不会删除 ChromaDB 中的长期记忆数据。
        如需清理记忆，需要额外调用记忆管理接口。
        """
        if agent_id not in self._cache:
            logger.warning(f"删除失败，Agent 不存在: {agent_id}")
            return False

        name = self._cache[agent_id].get("name", "")
        del self._cache[agent_id]
        self._delete_file(agent_id)

        # 清理对应的长期记忆文件
        import os
        memories_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "memories"
        )
        memory_file = os.path.join(memories_dir, f"memories_agent_{name}.json")
        if os.path.exists(memory_file):
            try:
                os.remove(memory_file)
                logger.info(f"已清理 Agent [{name}] 的长期记忆文件: {memory_file}")
            except Exception as e:
                logger.warning(f"清理长期记忆文件失败: {e}")

        # 清理 agent_data.db 中该 Agent 的所有会话
        agent_db_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "agent_data.db"
        )
        if os.path.exists(agent_db_path):
            try:
                import sqlite3
                conn = sqlite3.connect(agent_db_path)
                cursor = conn.cursor()
                # 查找该 agent 的所有会话
                cursor.execute(
                    "SELECT session_id FROM sessions WHERE title LIKE ?",
                    (f"[{name}]%",)
                )
                sessions = cursor.fetchall()
                for (sid,) in sessions:
                    cursor.execute("DELETE FROM conversations WHERE user_id = ?", (sid,))
                    cursor.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
                conn.commit()
                conn.close()
                if sessions:
                    logger.info(f"已清理 Agent [{name}] 的 {len(sessions)} 个会话")
            except Exception as e:
                logger.warning(f"清理 Agent 会话失败: {e}")

        logger.info(f"删除 Agent: {name} ({agent_id[:12]}...)")
        return True

    def get_all_agent_names(self) -> set:
        """获取所有 Agent 名称的集合（用于 @ 路由校验）"""
        return {a.get("name", "") for a in self._cache.values()}

    def get_agent_names_with_ids(self, enabled_only: bool = False) -> list:
        """
        获取 Agent 名称和 ID 的映射列表

        Args:
            enabled_only: 是否只返回 enabled_for_workspace=True 的 Agent
        """
        items = self._cache.items()
        if enabled_only:
            items = [(aid, a) for aid, a in items if a.get("enabled_for_workspace", True)]
        return [
            {"agent_id": aid, "name": a.get("name", ""),
             "display_name": a.get("display_name", ""),
             "enabled_for_workspace": a.get("enabled_for_workspace", True)}
            for aid, a in items
        ]
