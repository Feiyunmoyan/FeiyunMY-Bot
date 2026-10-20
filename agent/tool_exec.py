"""
工具调用执行

原 agent/runner.py 中 run 与 run_stream 里逐字节相同的 exec_one + asyncio.gather 段，
抽出复用，消除重复。

注意：工具结果的**后处理**两边不同，必须留在各自循环里：
  - run        : role="system"，tools_used 含 result 字段，截断 200
  - run_stream : role="tool"，  tools_used 不含 result，截断 200 + yield 截断 300
"""
import asyncio
import json


class ToolExecMixin:
    """工具调用并发执行"""

    async def _exec_tool_calls(self, tcs):
        """并发执行一轮 tool_calls，返回 [(tc, name, args, result), ...]"""

        async def exec_one(tc):
            name = tc.get("function", {}).get("name", "")
            try:
                args = json.loads(tc.get("function", {}).get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            r = await self.tool_registry.execute(name, args)
            return tc, name, args, r

        return await asyncio.gather(*[exec_one(tc) for tc in tcs])
