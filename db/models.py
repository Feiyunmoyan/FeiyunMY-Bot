"""
数据库模型定义
参考 AstrBot 的 ConversationV2 设计，简化适配 FeiyunMY-Bot
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON, DateTime, Text


class TimestampMixin:
    """时间戳混合类，提供 created_at 和 updated_at 字段"""
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
        ),
    )


class Conversation(SQLModel, table=True):
    """
    对话模型 - 存储每个会话的消息历史

    设计参考 AstrBot ConversationV2：
    - content 字段以 list[dict]（OpenAI 格式）存储对话内容
    - conversation_id 作为主键（UUID）
    - 支持 title、token_usage 等扩展字段
    """

    __tablename__ = "conversations"

    conversation_id: str = Field(
        primary_key=True,
        default_factory=lambda: uuid.uuid4().hex[:16],
        max_length=32,
        description="对话唯一标识（16位hex）",
    )
    user_id: str = Field(
        max_length=64,
        nullable=False,
        index=True,
        description="会话/用户标识，对应 session_id",
    )
    content: Optional[list] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="对话消息列表，每个元素为 {role, content, timestamp} 格式",
    )
    title: Optional[str] = Field(
        default=None, max_length=255, description="对话标题"
    )
    message_count: int = Field(default=0, nullable=False, description="消息总数")
    token_usage: int = Field(default=0, nullable=False, description="Token 使用量")

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
        ),
    )


class Notification(SQLModel, table=True):
    """系统通知模型 - 存储主动引擎推送的通知"""
    __tablename__ = "notifications"

    id: str = Field(primary_key=True, max_length=32)
    content: str = Field(sa_column=Column(Text, nullable=False))
    msg_type: str = Field(max_length=32)       # active_push / system_event / agent_report
    priority: str = Field(max_length=16)       # urgent / important / normal / low
    source: str = Field(max_length=64, default="")
    target: str = Field(max_length=16)         # notification / session
    created_at: float = Field(default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "type": self.msg_type,
            "priority": self.priority,
            "source": self.source,
            "target": self.target,
            "created_at": self.created_at,
        }


class PushMessageRecord(SQLModel, table=True):
    """普通消息记录 - 存储普通消息频道中的所有消息（用户/AI/主动推送）"""
    __tablename__ = "push_messages"

    id: str = Field(primary_key=True, max_length=32)
    role: str = Field(max_length=16, default="assistant")  # user / assistant
    content: str = Field(sa_column=Column(Text, nullable=False))
    msg_type: str = Field(max_length=32)       # active_push / chat_reply / system_event
    priority: str = Field(max_length=16)       # urgent / important / normal / low
    source: str = Field(max_length=64, default="")
    created_at: float = Field(default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "type": self.msg_type,
            "priority": self.priority,
            "source": self.source,
            "created_at": self.created_at,
        }


class AppConfig(SQLModel, table=True):
    """应用配置键值存储"""
    __tablename__ = "app_config"

    key: str = Field(primary_key=True, max_length=64)
    value: str = Field(default="", max_length=256)
    updated_at: float = Field(default=0)


class Session(SQLModel, table=True):
    """
    会话模型 - 存储会话元信息

    与 Conversation 是一对多关系：一个会话可以有多个对话（未来扩展）
    当前版本中，一个 session_id 对应一条 Conversation 记录
    """

    __tablename__ = "sessions"

    session_id: str = Field(
        primary_key=True,
        max_length=32,
        description="会话唯一标识",
    )
    title: str = Field(default="新对话", max_length=255, description="会话标题/名称")
    is_active: bool = Field(default=True, nullable=False, description="是否活跃")

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, default=datetime.utcnow),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
        ),
    )
