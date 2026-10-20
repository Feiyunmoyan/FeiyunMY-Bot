"""
主动推送执行

从 active_engine/scheduler.py 原样搬出（逻辑未改动）：
_push_to_ai_chat / push_system_event / _do_push_greeting / add_task

注意：_do_push_greeting 函数体内自带一句局部 import PushMessage（原样保留）；
其余三个方法依赖模块级 PushMessage，故此处必须导入。
"""
import logging
import time

from active_engine.push import PushMessage

logger = logging.getLogger(__name__)


class PushExecMixin:
    """推送执行：构造 PushMessage 交给 push_engine，并维护待发任务"""

    async def _do_push_greeting(self, content: str):
        """异步推送问候消息"""
        from active_engine.push import PushMessage
        msg = PushMessage(
            content=content,
            msg_type="active_push",
            priority="normal",
            source="系统",
            store_policy="memorable",
        )
        await self.push_engine.push(msg)
        self.adaptive.record_push(replied=False)

    async def _push_to_ai_chat(self, content_hint: str, source: str = ""):
        """推送给AI生成自然聊天内容"""
        if not content_hint:
            return

        msg = PushMessage(
            content=content_hint,
            msg_type="active_push",
            priority="normal",
            source=source,
            store_policy="memorable",
        )
        await self.push_engine.push(msg)
        self.adaptive.record_push(replied=False)

    async def push_system_event(self, content: str, priority: str = "normal", source: str = ""):
        """推送系统事件（不走AI生成）"""
        msg = PushMessage(
            content=content,
            msg_type="system_event",
            priority=priority,
            source=source,
            store_policy="ephemeral",
        )
        await self.push_engine.push(msg)

    def add_task(self, content: str, due_at: float):
        """添加一条定时任务（指令通道）"""
        self._pending_tasks.append({
            "content": content,
            "due_at": due_at,
            "created_at": time.time(),
        })
        logger.info(f"添加定时任务: {content[:40]}... 到期: {due_at}")
