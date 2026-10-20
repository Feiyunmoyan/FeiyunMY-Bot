"""
主动推送模块
SSE 推送 + 消息持久化 + 断连补推
"""
import os
import json
import uuid
import time
import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# 主动消息持久化目录
ACTIVE_MESSAGES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "active_messages"
)


class PushMessage:
    """主动推送消息"""

    def __init__(
        self,
        content: str,
        msg_type: str = "active_push",
        priority: str = "normal",
        source: str = "",
        store_policy: str = "ephemeral",
        metadata: dict = None,
    ):
        """
        Args:
            content: 消息内容
            msg_type: 消息类型（active_push / system_event / agent_report）
            priority: 优先级（urgent / important / normal / low）
            source: 来源描述（如"定时提醒""记忆跟进"）
            store_policy: 存储策略（ephemeral / memorable）
            metadata: 附加元数据
        """
        self.id = uuid.uuid4().hex[:12]
        self.content = content
        self.msg_type = msg_type
        self.priority = priority
        self.source = source
        self.store_policy = store_policy
        self.metadata = metadata or {}
        self.created_at = time.time()

    def to_dict(self) -> dict:
        # 根据消息类型决定推送目标
        if self.msg_type in ("system_event", "agent_report"):
            target = "notification"
        elif self.msg_type == "active_push":
            target = "session"
        else:
            target = "notification"

        return {
            "id": self.id,
            "content": self.content,
            "type": self.msg_type,
            "target": target,           # "notification" 弹网页通知 / "session" 插入对话
            "priority": self.priority,
            "source": self.source,
            "store_policy": self.store_policy,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    def to_sse(self) -> str:
        """转为 SSE 格式"""
        return f"data: {json.dumps(self.to_dict(), ensure_ascii=False)}\n\n"


class PushEngine:
    """
    推送引擎
    管理 SSE 连接、消息队列、消息持久化
    """

    def __init__(self, db=None):
        """
        Args:
            db: 可选，FeiyunDatabase 实例，用于持久化通知到 SQLite
        """
        os.makedirs(ACTIVE_MESSAGES_DIR, exist_ok=True)
        self.db = db

        # 消息队列：主动引擎产生的消息放进这里，SSE 从这里取
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        # SSE 连接状态
        self._connected = False
        self._last_event_time = time.time()
        self._store_callback = None  # 消息存储回调

    def set_store_callback(self, callback):
        """设置消息存储回调（可在初始化后注入）"""
        self._store_callback = callback

        # SSE 连接状态
        self._connected = False
        self._last_event_time = time.time()

    async def push(self, message: PushMessage):
        """
        推送一条消息

        1. ephemeral 消息：只走SSE推送，不存数据库
        2. memorable 消息：持久化到磁盘 + 存SQLite + SSE推送
        """
        # ephemeral 消息不持久化，只走SSE
        if message.store_policy != "ephemeral":
            # 持久化到磁盘
            self._persist(message)

            # 调用存储回调（存SQLite）
            if self._store_callback:
                try:
                    self._store_callback(message.to_dict())
                except Exception as e:
                    logger.error(f"存储回调失败: {e}")

        # 入队（所有消息都走SSE推送）
        try:
            await self.queue.put(message)
            self._last_event_time = time.time()
            logger.debug(f"推送消息: [{message.priority}] {message.content[:40]}...")
        except asyncio.QueueFull:
            logger.warning("推送队列已满，消息被丢弃")

    def _persist(self, message: PushMessage):
        """持久化消息到磁盘"""
        filepath = os.path.join(ACTIVE_MESSAGES_DIR, f"{message.id}.json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(message.to_dict(), f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"持久化推送消息失败: {e}")

    def get_messages_since(self, since: float, limit: int = 50) -> list:
        """
        获取指定时间戳之后的消息（用于断连补推）

        Args:
            since: 时间戳，只返回这个时间之后的消息
            limit: 最多返回条数

        Returns:
            消息列表
        """
        if not os.path.exists(ACTIVE_MESSAGES_DIR):
            return []

        messages = []
        for fname in os.listdir(ACTIVE_MESSAGES_DIR):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(ACTIVE_MESSAGES_DIR, fname)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("created_at", 0) > since:
                    messages.append(data)
            except Exception:
                continue

        # 按时间排序
        messages.sort(key=lambda m: m.get("created_at", 0))
        return messages[-limit:] if len(messages) > limit else messages

    def cleanup_old_messages(self, keep_hours: int = 24):
        """清理超过指定时长的消息"""
        if not os.path.exists(ACTIVE_MESSAGES_DIR):
            return 0

        cutoff = time.time() - keep_hours * 3600
        count = 0
        for fname in os.listdir(ACTIVE_MESSAGES_DIR):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(ACTIVE_MESSAGES_DIR, fname)
            try:
                if os.path.getmtime(filepath) < cutoff:
                    os.remove(filepath)
                    count += 1
            except Exception:
                continue

        if count:
            logger.info(f"清理了 {count} 条过期推送消息")
        return count

    async def sse_generator(self) -> AsyncGenerator[str, None]:
        """SSE 事件生成器（供 FastAPI StreamingResponse 使用）"""
        self._connected = True
        logger.info("SSE 客户端已连接")

        # 客户端连接时推送启动消息（仅首次）
        if not hasattr(self, '_startup_pushed'):
            self._startup_pushed = True
            startup_msg = PushMessage(
                content="绯璃已上线，随时可以找我聊天~",
                msg_type="system_event",
                priority="normal",
                source="系统",
                store_policy="ephemeral",
            )
            await self.push(startup_msg)

        try:
            while True:
                try:
                    message = await asyncio.wait_for(self.queue.get(), timeout=30.0)
                    yield message.to_sse()
                except asyncio.TimeoutError:
                    # 发送心跳，保持连接
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            logger.info("SSE 客户端断开连接")
        finally:
            self._connected = False

    def get_status(self) -> dict:
        """获取推送引擎状态"""
        return {
            "connected": self._connected,
            "queue_size": self.queue.qsize(),
            "last_event_time": self._last_event_time,
        }
