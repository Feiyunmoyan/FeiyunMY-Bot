"""
Provider 抽象基类
定义所有 LLM Provider 必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator


class BaseProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
    ) -> Dict[str, Any]:
        """发送对话请求到 LLM（非流式）"""
        pass

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 1.0,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式对话"""
        result = await self.chat(messages, tools, temperature, max_tokens, top_p, presence_penalty, frequency_penalty)
        yield {"type": "done", **result}
