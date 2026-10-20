"""
消息模型

简单的消息 dataclass，替代裸 dict。
主要解决：
1. role 写错不报错的问题
2. tool/reasoning 混入 system 的问题
"""
from dataclasses import dataclass, asdict
from typing import List, Optional, Any


VALID_ROLES = {"system", "user", "assistant", "tool"}


@dataclass
class Message:
    """消息体"""
    role: str
    content: str
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None

    def __post_init__(self):
        if self.role not in VALID_ROLES:
            raise ValueError(f"无效的 role: {self.role}，合法值: {VALID_ROLES}")

    def to_dict(self) -> dict:
        """转成 API 所需的 dict"""
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @staticmethod
    def from_dict(d: dict) -> "Message":
        """从 dict 创建"""
        return Message(
            role=d.get("role", "user"),
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls"),
            tool_call_id=d.get("tool_call_id"),
        )

    @staticmethod
    def from_dict_list(dicts: List[dict]) -> List["Message"]:
        """批量从 dict 创建"""
        return [Message.from_dict(d) for d in dicts]

    @staticmethod
    def to_dict_list(messages: List["Message"]) -> List[dict]:
        """批量转 dict"""
        return [m.to_dict() for m in messages]
