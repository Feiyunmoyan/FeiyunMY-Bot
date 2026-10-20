"""
MCP 服务器管理
支持自由增删 MCP 服务器配置
"""
import os
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

MCP_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mcp")


class MCPServer:
    def __init__(self, name: str, url: str = "", description: str = "", enabled: bool = True):
        self.name = name
        self.url = url
        self.description = description
        self.enabled = enabled

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "description": self.description,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MCPServer":
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
        )


class MCPManager:
    """MCP 服务器管理器"""

    def __init__(self):
        os.makedirs(MCP_DATA_DIR, exist_ok=True)
        self._file_path = os.path.join(MCP_DATA_DIR, "mcp_servers.json")
        self._servers: List[MCPServer] = []
        self._load()

    def _load(self):
        if os.path.exists(self._file_path):
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._servers = [MCPServer.from_dict(s) for s in data]
                logger.info(f"加载了 {len(self._servers)} 个 MCP 服务器")
            except Exception as e:
                logger.error(f"加载 MCP 配置失败: {e}")
                self._servers = []

    def _save(self):
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in self._servers], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 MCP 配置失败: {e}")

    def list_servers(self) -> List[dict]:
        return [s.to_dict() for s in self._servers]

    def get_server(self, name: str) -> Optional[dict]:
        for s in self._servers:
            if s.name == name:
                return s.to_dict()
        return None

    def add_server(self, name: str, url: str = "", description: str = "", enabled: bool = True) -> bool:
        for s in self._servers:
            if s.name == name:
                return False
        self._servers.append(MCPServer(name, url, description, enabled))
        self._save()
        return True

    def update_server(self, name: str, data: dict) -> bool:
        for s in self._servers:
            if s.name == name:
                if "url" in data:
                    s.url = data["url"]
                if "description" in data:
                    s.description = data["description"]
                if "enabled" in data:
                    s.enabled = data["enabled"]
                if "name" in data and data["name"] != name:
                    # 改名：删除旧的，添加新的
                    new_name = data["name"]
                    s.name = new_name
                    self._save()
                    return True
                self._save()
                return True
        return False

    def delete_server(self, name: str) -> bool:
        for i, s in enumerate(self._servers):
            if s.name == name:
                self._servers.pop(i)
                self._save()
                return True
        return False
