"""
Memory 模块

MemoryBridge 是所有记忆后端必须实现的统一接口。
（原 memory/bridge.py 已并入此处：接口与唯一实现工厂不再分散在两个文件）
"""
from abc import ABC, abstractmethod


class MemoryBridge(ABC):
    """记忆系统统一接口"""

    @abstractmethod
    def add(self, role: str, content: str, metadata: dict = None) -> str:
        """添加记忆，返回记忆ID"""
        pass

    @abstractmethod
    def query(self, text: str, top_k: int = 5) -> list:
        """检索相关记忆"""
        pass

    @abstractmethod
    def get_recent(self, n: int = 10) -> list:
        """获取最近N条记忆"""
        pass

    @abstractmethod
    def get_by_id(self, memory_id: str) -> dict:
        """按ID获取记忆"""
        pass

    @abstractmethod
    def update(self, memory_id: str, data: dict) -> bool:
        """更新记忆"""
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        pass

    @abstractmethod
    def list_all(self, page: int = 1, page_size: int = 20) -> dict:
        """分页列出所有记忆"""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空所有记忆"""
        pass
