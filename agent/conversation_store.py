"""
对话上下文管理器（SQLite 版）
维护每个 session 的对话历史，支持多会话管理
数据持久化到 SQLite 数据库 (data/feiyun.db)
"""
import logging
import time
import uuid
from typing import List, Dict

from db.database import FeiyunDatabase

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    管理多个会话的对话历史（SQLite 异步版）

    设计变更：
    - 原：JSON 文件存储 (data/conversations/)
    - 新：SQLite 数据库存储 (data/feiyun.db)

    兼容性：
    - 保持原有 API 接口不变（改为异步）
    - 数据格式保持一致 (list[dict] 消息历史)
    """

    def __init__(self, db: FeiyunDatabase, max_history: int = 50):
        self.db = db
        self._max_history = max_history
        # 内存缓存：session_id -> messages list
        self._cache: Dict[str, List[Dict]] = {}

    async def initialize(self) -> None:
        """初始化：加载缓存"""
        await self.db.initialize()
        await self._load_cache()
        logger.info(f"ConversationContext 初始化完成 (max_history={self._max_history})")

    async def close(self) -> None:
        """关闭数据库连接"""
        await self.db.close()

    async def _load_cache(self) -> None:
        """从数据库加载活跃会话的消息到缓存"""
        sessions = await self.db.list_sessions()
        for s in sessions:
            conv = await self.db.get_conversation(s["id"])
            if conv and conv.content:
                self._cache[s["id"]] = conv.content
        logger.info(f"加载了 {len(self._cache)} 个会话到缓存")

    async def _save_conversation(self, session_id: str) -> None:
        """保存单个会话到数据库"""
        messages = self._cache.get(session_id, [])
        await self.db.update_conversation(
            session_id=session_id,
            content=messages,
            message_count=len(messages),
        )
        # 同步更新会话的 updated_at，让列表显示最新活跃时间
        await self.db.update_session_timestamp(session_id)

    # ─── 会话管理（异步） ───

    async def create_session(self, name: str = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4()).replace("-", "")[:16]
        title = name or f"对话 {session_id[:4]}"
        await self.db.create_session(session_id, title)
        await self.db.create_conversation(session_id, content=[], title=title)
        self._cache[session_id] = []
        logger.info(f"创建新会话: {session_id}")
        return session_id

    async def list_sessions(self) -> List[dict]:
        """列出所有会话"""
        return await self.db.list_sessions()

    async def rename_session(self, session_id: str, name: str) -> bool:
        """重命名会话"""
        ok = await self.db.update_session_title(session_id, name)
        if ok:
            # 同时更新对话的 title
            await self.db.update_conversation(session_id, title=name)
        return ok

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id not in self._cache and not await self.db.get_session(session_id):
            return False
        self._cache.pop(session_id, None)
        ok = await self.db.delete_session(session_id)
        return ok

    # ─── 消息管理（异步） ───

    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """添加一条消息"""
        # 确保会话存在
        if session_id not in self._cache:
            existing = await self.db.get_session(session_id)
            if not existing:
                # 用指定的 session_id 创建，不用随机 UUID
                title = f"对话 {session_id[:4]}"
                await self.db.create_session(session_id, title)
                await self.db.create_conversation(session_id, content=[], title=title)
                logger.info(f"创建会话: {session_id}")
                self._cache[session_id] = []
            else:
                # 会话已存在，从 DB 加载历史消息
                conv = await self.db.get_conversation(session_id)
                if conv and conv.content:
                    self._cache[session_id] = list(conv.content)
                    logger.info(f"加载历史消息: {session_id} ({len(conv.content)}条)")
                else:
                    self._cache[session_id] = []

        self._cache[session_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            **kwargs,
        })

        # 截断超长历史
        if len(self._cache[session_id]) > self._max_history:
            self._cache[session_id] = self._cache[session_id][-self._max_history:]

        # 持久化
        await self._save_conversation(session_id)

    async def get_history(self, session_id: str) -> List[Dict]:
        """获取会话消息"""
        if session_id in self._cache:
            return self._cache[session_id]

        # 缓存未命中，从数据库加载
        conv = await self.db.get_conversation(session_id)
        if conv and conv.content:
            self._cache[session_id] = conv.content
            return conv.content
        return []

    async def clear(self, session_id: str = None) -> None:
        """清空会话"""
        if session_id:
            self._cache.pop(session_id, None)
            await self.db.delete_conversations_by_session(session_id)
        else:
            self._cache.clear()
            # 删除所有会话
            sessions = await self.db.list_sessions()
            for s in sessions:
                await self.db.delete_session(s["id"])

    async def get_message_count(self, session_id: str = None) -> int:
        """获取消息数"""
        if session_id:
            return len(self._cache.get(session_id, []))
        return await self.db.get_total_message_count()

    async def get_summary_text(self, session_id: str, max_turns: int = 3) -> str:
        """获取会话前几轮的摘要文本"""
        history = await self.get_history(session_id)
        turns = history[:max_turns * 2]  # user + assistant = 1 turn
        lines = []
        for msg in turns:
            role = "用户" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")[:80]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    # ─── 兼容同步接口（供非 async 代码调用） ───

    def add_message_sync(self, session_id: str, role: str, content: str) -> None:
        """同步版 add_message（写入缓存，延迟持久化）"""
        import time
        if session_id not in self._cache:
            self._cache[session_id] = []
        self._cache[session_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        if len(self._cache[session_id]) > self._max_history:
            self._cache[session_id] = self._cache[session_id][-self._max_history:]

    async def flush(self, session_id: str = None) -> None:
        """将缓存持久化到数据库"""
        if session_id:
            await self._save_conversation(session_id)
        else:
            for sid in list(self._cache.keys()):
                await self._save_conversation(sid)
