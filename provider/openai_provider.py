"""
OpenAI 兼容 Provider
支持所有兼容 OpenAI API 格式的服务（DeepSeek、OpenAI、Groq 等）
支持流式输出 (SSE) 和环境变量 API Key

改用 openai 官方 SDK，替换手写 httpx 实现，
由 SDK 内部管理连接池、重试、超时等。
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

logger = logging.getLogger(__name__)

from provider.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI API 兼容的 Provider 实现（基于 openai 官方 SDK）"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        # 优先使用环境变量 FEIYUN_API_KEY，避免 API Key 明文存储在配置文件中
        self.api_key = os.environ.get("FEIYUN_API_KEY") or api_key
        if os.environ.get("FEIYUN_API_KEY"):
            logger.info("Provider 使用环境变量 FEIYUN_API_KEY")
        self.model = model

        # 使用 openai 官方 SDK，接管连接池、重试、超时
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=f"{self.base_url}/v1",
            timeout=120.0,
            max_retries=3,  # SDK 内置重试 3 次
        )

    def _parse_usage(self, completion: ChatCompletion) -> dict:
        """将 SDK 的 CompletionUsage 转为 dict"""
        usage = completion.usage
        if usage is None:
            return {}
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }

    def _parse_tool_calls(self, completion: ChatCompletion) -> Optional[List[dict]]:
        """将 SDK 的 tool_calls 转为 dict 列表"""
        msg = completion.choices[0].message
        if not msg.tool_calls:
            return None
        result = []
        for tc in msg.tool_calls:
            result.append({
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })
        return result

    async def chat(
        self,
        messages,
        tools=None,
        temperature=0.7,
        max_tokens=2048,
        top_p=1.0,
        presence_penalty=0.0,
        frequency_penalty=0.0,
        model=None,
    ):
        """非流式调用（SDK 内部自动处理重试和连接管理）"""
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            completion: ChatCompletion = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f"API 调用失败: {e}")
            raise

        choice = completion.choices[0]
        msg = choice.message

        # 提取内容
        content = msg.content or ""

        # 提取 reasoning_content（DeepSeek 等模型的扩展字段）
        reasoning_content = None
        try:
            rc = getattr(msg, "reasoning_content", None)
            if rc:
                reasoning_content = rc
        except Exception:
            pass
        if not reasoning_content:
            try:
                rc = getattr(msg, "reasoning", None)
                if rc:
                    reasoning_content = rc
            except Exception:
                pass

        # 提取工具调用
        tool_calls = self._parse_tool_calls(completion)

        # 提取用量
        usage = self._parse_usage(completion)

        return {
            "content": content,
            "tool_calls": tool_calls,
            "reasoning_content": reasoning_content,
            "usage": usage,
        }

    async def chat_stream(
        self,
        messages,
        tools=None,
        temperature=0.7,
        max_tokens=2048,
        top_p=1.0,
        presence_penalty=0.0,
        frequency_penalty=0.0,
    ):
        """流式调用（SSE），SDK 内部自动处理重试和连接管理"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        content_buffer = ""
        reasoning_buffer = ""
        tool_calls_buffer = {}  # index -> {id, type, function: {name, arguments}}

        try:
            stream = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f"流式 API 调用失败: {e}")
            raise

        async for chunk in stream:
            if not isinstance(chunk, ChatCompletionChunk):
                continue

            choices = chunk.choices
            if not choices:
                # usage chunk（流末尾）
                if chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
                continue

            delta = choices[0].delta

            # 文本片段
            if delta.content:
                content_buffer += delta.content
                yield {"type": "text", "content": delta.content}

            # 思考内容（DeepSeek 等模型的扩展字段）
            try:
                reasoning = getattr(delta, "reasoning_content", None) or ""
            except Exception:
                reasoning = ""
            if reasoning:
                reasoning_buffer += reasoning
                yield {"type": "reasoning", "content": reasoning}

            # 工具调用（流式分块到达，需要合并）
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_buffer[idx]["id"] = tc.id
                    if tc.type:
                        tool_calls_buffer[idx]["type"] = tc.type
                    if tc.function:
                        if tc.function.name:
                            tool_calls_buffer[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments

        # 发送结束信号
        result = {
            "type": "done",
            "content": content_buffer,
            "reasoning_content": reasoning_buffer or None,
        }
        if tool_calls_buffer:
            result["tool_calls"] = [v for _, v in sorted(tool_calls_buffer.items())]

        yield result

    async def close(self):
        """关闭 SDK 客户端"""
        await self.client.close()
