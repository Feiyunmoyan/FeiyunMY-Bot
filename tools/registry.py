"""
工具注册中心
管理所有可用工具的注册与执行
"""
import asyncio
import logging
from typing import Dict, Any, List, Callable, Optional

logger = logging.getLogger(__name__)

# 默认工具执行超时（秒）
DEFAULT_TOOL_TIMEOUT = 60


class ToolRegistry:
    """工具注册与执行中心"""

    def __init__(self, default_timeout: int = DEFAULT_TOOL_TIMEOUT):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._timeouts: Dict[str, int] = {}
        self.default_timeout = default_timeout

    def register(self, name: str, func: Callable, definition: dict, enabled: bool = True, timeout: Optional[int] = None) -> None:
        """注册一个工具（自动防重复）"""
        if name in self._tools:
            return  # 已注册，跳过
        self._tools[name] = {
            "func": func,
            "definition": definition,
            "enabled": enabled,
        }
        if timeout is not None:
            self._timeouts[name] = timeout
        logger.info(f"注册工具: {name}")

    def set_enabled(self, name: str, enabled: bool) -> None:
        """设置工具启用状态"""
        if name in self._tools:
            self._tools[name]["enabled"] = enabled

    def get_tool_definitions(self) -> List[dict]:
        """获取所有已启用工具的 OpenAI function calling 格式定义"""
        return [
            t["definition"]
            for t in self._tools.values()
            if t["enabled"]
        ]

    async def execute(self, name: str, args: dict) -> Any:
        """执行指定工具（带超时控制 + 参数校验）"""
        if name not in self._tools:
            return f"错误：未找到工具 '{name}'"

        tool = self._tools[name]
        if not tool["enabled"]:
            return f"错误：工具 '{name}' 未启用"

        # 参数校验：检查必填参数
        definition = tool["definition"].get("function", {})
        params = definition.get("parameters", {}).get("properties", {})
        required = definition.get("parameters", {}).get("required", [])
        missing = [p for p in required if p not in args]
        if missing:
            msg = f"工具 '{name}' 缺少必填参数: {', '.join(missing)}"
            logger.warning(msg)
            return f"错误：{msg}"

        timeout = self._timeouts.get(name, self.default_timeout)

        logger.info(f"调用工具: {name}, 参数: {args}, 超时: {timeout}s")
        try:
            result = await asyncio.wait_for(tool["func"](**args), timeout=timeout)
            logger.info(f"工具返回: {name} -> {str(result)[:100]}")
            return result
        except asyncio.TimeoutError:
            msg = f"工具 '{name}' 执行超时（{timeout}s）"
            logger.error(msg)
            return f"错误：{msg}"
        except Exception as e:
            logger.error(f"工具执行失败 {name}: {e}")
            return f"工具执行出错: {str(e)}"

    def list_tools(self) -> List[dict]:
        """列出所有工具状态"""
        return [
            {"name": name, "enabled": t["enabled"], "description": t["definition"]["function"].get("description", "")}
            for name, t in self._tools.items()
        ]
