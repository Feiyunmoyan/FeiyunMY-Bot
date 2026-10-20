"""
FeiyunMY-Bot SQLite 数据库操作层
基于 SQLModel + aiosqlite 实现异步数据库操作
"""
import logging
import os
import time
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, select, delete, update, col, func
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from db.models import Conversation, Session, Notification, PushMessageRecord, AppConfig

logger = logging.getLogger(__name__)


class FeiyunDatabase:
    """
    异步 SQLite 数据库管理类

    设计参考 AstrBot SQLiteDatabase：
    - 使用 aiosqlite 实现异步操作
    - 使用 SQLModel 定义 ORM 模型
    - WAL 模式提升并发性能
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"
        self._engine = None
        self._session_factory = None
        self._initialized = False

    async def initialize(self) -> None:
        """初始化数据库连接并创建表"""
        if self._initialized:
            return

        self._engine = create_async_engine(
            self.DATABASE_URL,
            echo=False,
            future=True,
            connect_args={"timeout": 30},  # SQLite busy timeout
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            # 优化 SQLite 性能
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=20000"))
            await conn.execute(text("PRAGMA temp_store=MEMORY"))
            
            # 迁移：检查 push_messages 表是否有 role 列，没有则添加
            try:
                result = await conn.execute(text("PRAGMA table_info(push_messages)"))
                columns = {row[1] for row in result.fetchall()}
                if 'role' not in columns:
                    await conn.execute(text("ALTER TABLE push_messages ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'assistant'"))
                    logger.info("数据库迁移: push_messages 表添加了 role 列")
            except Exception as e:
                logger.debug(f"检查 push_messages 表结构时跳过: {e}")

        self._initialized = True
        logger.info(f"数据库初始化完成: {self.db_path}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._initialized = False
            logger.info("数据库连接已关闭")

    async def get_db_session(self) -> AsyncSession:
        """获取数据库会话"""
        if not self._initialized:
            await self.initialize()
        return self._session_factory()

    # ─── Session 操作 ───

    async def create_session(self, session_id: str, title: str = "新对话") -> Session:
        """创建新会话"""
        session = await self.get_db_session()
        async with session.begin():
                new_session = Session(
                    session_id=session_id,
                    title=title,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(new_session)
                await session.flush()
                await session.refresh(new_session)
                return new_session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话信息"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(Session).where(col(Session.session_id) == session_id)
            )
            return result.scalar_one_or_none()

    async def list_sessions(self) -> list[dict]:
        """列出所有会话（按更新时间降序）"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(Session)
                .where(col(Session.is_active) == True)
                .order_by(col(Session.updated_at).desc())
            )
            sessions = result.scalars().all()

            # 同时获取消息数
            session_list = []
            for s in sessions:
                count_result = await session.execute(
                    select(func.coalesce(func.sum(col(Conversation.message_count)), 0)).where(
                        col(Conversation.user_id) == s.session_id
                    )
                )
                msg_count = count_result.scalar_one()
                session_list.append({
                    "id": s.session_id,
                    "name": s.title,
                    "created_at": s.created_at.isoformat() + "+00:00",
                    "updated_at": s.updated_at.isoformat() + "+00:00",
                    "message_count": msg_count,
                })
            return session_list

    async def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        session = await self.get_db_session()
        async with session.begin():
                result = await session.execute(
                    update(Session)
                    .where(col(Session.session_id) == session_id)
                    .values(title=title, updated_at=datetime.utcnow())
                )
                return result.rowcount > 0

    async def update_session_timestamp(self, session_id: str) -> bool:
        """更新会话的活跃时间戳"""
        session = await self.get_db_session()
        async with session.begin():
                result = await session.execute(
                    update(Session)
                    .where(col(Session.session_id) == session_id)
                    .values(updated_at=datetime.utcnow())
                )
                return result.rowcount > 0

    async def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有对话"""
        session = await self.get_db_session()
        async with session.begin():
                # 先删除关联的对话
                await session.execute(
                    delete(Conversation).where(
                        col(Conversation.user_id) == session_id
                    )
                )
                # 再删除会话
                result = await session.execute(
                    delete(Session).where(col(Session.session_id) == session_id)
                )
                return result.rowcount > 0

    # ─── Conversation 操作 ───

    async def get_conversation(self, session_id: str) -> Optional[Conversation]:
        """获取会话的对话记录"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(Conversation)
                .where(col(Conversation.user_id) == session_id)
                .order_by(col(Conversation.updated_at).desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def create_conversation(
        self,
        session_id: str,
        content: list = None,
        title: str = None,
    ) -> Conversation:
        """创建新对话"""
        session = await self.get_db_session()
        async with session.begin():
                now = datetime.utcnow()
                new_conv = Conversation(
                    user_id=session_id,
                    content=content or [],
                    title=title,
                    message_count=len(content) if content else 0,
                    created_at=now,
                    updated_at=now,
                )
                session.add(new_conv)
                await session.flush()
                await session.refresh(new_conv)
                return new_conv

    async def update_conversation(
        self,
        session_id: str,
        content: list = None,
        title: str = None,
        message_count: int = None,
        token_usage: int = None,
    ) -> Optional[Conversation]:
        """更新对话（不存在则创建）"""
        existing = await self.get_conversation(session_id)
        if existing:
            # 更新已有记录
            session = await self.get_db_session()
            async with session.begin():
                    values = {"updated_at": datetime.utcnow()}
                    if content is not None:
                        values["content"] = content
                    if title is not None:
                        values["title"] = title
                    if message_count is not None:
                        values["message_count"] = message_count
                    if token_usage is not None:
                        values["token_usage"] = token_usage

                    await session.execute(
                        update(Conversation)
                        .where(col(Conversation.conversation_id) == existing.conversation_id)
                        .values(**values)
                    )
        else:
            # 不存在则创建
            await self.create_conversation(
                session_id=session_id,
                content=content or [],
                title=title or f"对话 {session_id[:4]}",
            )

        return await self.get_conversation(session_id)

    async def delete_conversations_by_session(self, session_id: str) -> int:
        """删除指定会话的所有对话"""
        session = await self.get_db_session()
        async with session.begin():
                result = await session.execute(
                    delete(Conversation).where(
                        col(Conversation.user_id) == session_id
                    )
                )
                return result.rowcount

    async def get_total_message_count(self) -> int:
        """获取所有会话的总消息数"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(func.sum(col(Conversation.message_count)))
            )
            total = result.scalar_one()
            return total or 0

    async def get_session_count(self) -> int:
        """获取活跃会话数"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(func.count(col(Session.session_id))).where(
                    col(Session.is_active) == True
                )
            )
            return result.scalar_one()

    async def cleanup_old_sessions(self, keep_days: int = 30) -> int:
        """清理指定天数前的非活跃会话（软删除标记）"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        session = await self.get_db_session()
        async with session.begin():
            result = await session.execute(
                update(Session)
                .where(
                    col(Session.updated_at) < cutoff,
                    col(Session.is_active) == True,
                )
                .values(is_active=False, updated_at=datetime.utcnow())
            )
            cleaned = result.rowcount or 0
            if cleaned:
                logger.info(f"已清理 {cleaned} 个过期会话（{keep_days}天前）")
            return cleaned

    # ─── Notification 操作 ───

    async def add_notification(self, notif_data: dict) -> str:
        """添加一条通知"""
        session = await self.get_db_session()
        async with session.begin():
            notif = Notification(
                id=notif_data.get("id", ""),
                content=notif_data.get("content", ""),
                msg_type=notif_data.get("type", "system_event"),
                priority=notif_data.get("priority", "normal"),
                source=notif_data.get("source", ""),
                target=notif_data.get("target", "notification"),
                created_at=notif_data.get("created_at", time.time()),
            )
            session.add(notif)
            return notif.id

    async def list_notifications(self, page: int = 1, page_size: int = 50,
                                  msg_type: str = None) -> dict:
        """分页列出通知"""
        session = await self.get_db_session()
        async with session:
            query = select(Notification).order_by(col(Notification.created_at).desc())
            if msg_type:
                query = query.where(col(Notification.msg_type) == msg_type)

            # 先查总数
            count_query = select(func.count()).select_from(Notification)
            if msg_type:
                count_query = count_query.where(col(Notification.msg_type) == msg_type)
            total_result = await session.execute(count_query)
            total = total_result.scalar_one() or 0

            # 分页
            offset = (page - 1) * page_size
            result = await session.execute(query.offset(offset).limit(page_size))
            items = [n.to_dict() for n in result.scalars().all()]

            return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def cleanup_old_notifications(self, max_count: int = 200) -> int:
        """超过最大条数时，删除最旧的通知"""
        session = await self.get_db_session()
        async with session.begin():
            # 查总数
            count_result = await session.execute(
                select(func.count()).select_from(Notification)
            )
            total = count_result.scalar_one() or 0

            if total <= max_count:
                return 0

            # 需要删除的条数
            to_delete = total - max_count

            # 找到最旧的 N 条 ID
            subq = select(Notification.id).order_by(
                col(Notification.created_at).asc()
            ).limit(to_delete)
            result = await session.execute(subq)
            old_ids = [row[0] for row in result]

            # 删除
            await session.execute(
                delete(Notification).where(col(Notification.id).in_(old_ids))
            )
            logger.info(f"通知清理: 删除了 {len(old_ids)} 条旧通知（共 {total} 条，保留 {max_count} 条）")
            return len(old_ids)

    # ─── KV 配置存储 ───

    async def get_config(self, key: str, default: str = "") -> str:
        """获取应用配置"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(AppConfig).where(AppConfig.key == key)
            )
            config = result.scalar_one_or_none()
            return config.value if config else default

    async def set_config(self, key: str, value: str):
        """设置应用配置"""
        session = await self.get_db_session()
        async with session:
            config = await session.get(AppConfig, key)
            if config:
                config.value = value
                config.updated_at = time.time()
            else:
                session.add(AppConfig(key=key, value=value, updated_at=time.time()))
            await session.commit()

    # ─── PushMessage 操作 ───

    async def add_push_message(self, msg_data: dict) -> str:
        """添加一条普通消息"""
        session = await self.get_db_session()
        async with session.begin():
            record = PushMessageRecord(
                id=msg_data.get("id", ""),
                role=msg_data.get("role", "assistant"),
                content=msg_data.get("content", ""),
                msg_type=msg_data.get("type", "active_push"),
                priority=msg_data.get("priority", "normal"),
                source=msg_data.get("source", ""),
                created_at=msg_data.get("created_at", 0),
            )
            session.add(record)
            return record.id

    async def list_push_messages(self, page: int = 1, page_size: int = 50) -> dict:
        """分页列出普通消息（倒序：最新的在前）"""
        session = await self.get_db_session()
        async with session:
            query = select(PushMessageRecord).order_by(col(PushMessageRecord.created_at).desc())
            count_query = select(func.count()).select_from(PushMessageRecord)

            total_result = await session.execute(count_query)
            total = total_result.scalar_one()

            offset = (page - 1) * page_size
            result = await session.execute(query.offset(offset).limit(page_size))
            items = [row.to_dict() for row in result.scalars().all()]

            return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def count_push_messages(self) -> int:
        """获取普通消息总数"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(select(func.count()).select_from(PushMessageRecord))
            return result.scalar_one()

    async def delete_oldest_push_messages(self, keep: int = 100) -> int:
        """删除最早的普通消息，只保留最近 keep 条"""
        session = await self.get_db_session()
        async with session.begin():
            count_result = await session.execute(select(func.count()).select_from(PushMessageRecord))
            total = count_result.scalar_one()
            if total <= keep:
                return 0

            delete_count = total - keep
            # 找到最早的 delete_count 条 ID
            subq = select(PushMessageRecord.id).order_by(
                col(PushMessageRecord.created_at).asc()
            ).limit(delete_count)
            result = await session.execute(subq)
            old_ids = [row[0] for row in result]

            await session.execute(
                delete(PushMessageRecord).where(col(PushMessageRecord.id).in_(old_ids))
            )
            logger.info(f"普通消息清理: 删除了 {len(old_ids)} 条旧消息（共 {total} 条，保留 {keep} 条）")
            return len(old_ids)

    async def get_push_messages_by_type(self, msg_type: str) -> list:
        """按类型查询普通消息"""
        session = await self.get_db_session()
        async with session:
            result = await session.execute(
                select(PushMessageRecord)
                .where(col(PushMessageRecord.msg_type) == msg_type)
                .order_by(col(PushMessageRecord.created_at).asc())
            )
            return [row.to_dict() for row in result.scalars().all()]

    async def get_push_messages_in_range(self, start_ts: float, end_ts: float, msg_type: str = None) -> list:
        """按时间范围查询普通消息，可选过滤类型"""
        session = await self.get_db_session()
        async with session:
            query = select(PushMessageRecord).where(
                col(PushMessageRecord.created_at) >= start_ts,
                col(PushMessageRecord.created_at) < end_ts,
            )
            if msg_type:
                query = query.where(col(PushMessageRecord.msg_type) == msg_type)
            query = query.order_by(col(PushMessageRecord.created_at).asc())
            result = await session.execute(query)
            return [row.to_dict() for row in result.scalars().all()]

    async def delete_push_messages_by_ids(self, ids: list) -> int:
        """按ID列表删除普通消息"""
        if not ids:
            return 0
        session = await self.get_db_session()
        async with session.begin():
            result = await session.execute(
                delete(PushMessageRecord).where(col(PushMessageRecord.id).in_(ids))
            )
            return result.rowcount

    async def delete_push_messages_before(self, before_ts: float, msg_type: str = None) -> int:
        """删除指定时间点前的消息，可选过滤类型"""
        session = await self.get_db_session()
        async with session.begin():
            query = delete(PushMessageRecord).where(
                col(PushMessageRecord.created_at) < before_ts
            )
            if msg_type:
                query = query.where(col(PushMessageRecord.msg_type) == msg_type)
            result = await session.execute(query)
            return result.rowcount
