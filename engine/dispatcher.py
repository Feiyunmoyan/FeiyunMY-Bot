"""
API 分发器（节流阀）
控制子 Agent 的并发执行，防止 API 被打爆
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class APIDispatcher:
    """
    API 分发器

    功能：
    - 限制最大并发请求数（默认 3）
    - 优先级调度：用户 > 主脑 > 子Agent
    - 排队等待，避免 API 过载
    """

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._active_count = 0
        self._queue = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def execute(self, agent_name: str, task_func, priority: int = 1) -> any:
        """
        提交任务到分发器执行

        Args:
            agent_name: 子 Agent 名称（仅用于日志）
            task_func: 异步任务函数
            priority: 优先级（0=用户, 1=主脑, 2=子Agent）

        Returns:
            任务返回值
        """
        future = asyncio.Future()

        await self._queue.put({
            "agent": agent_name,
            "func": task_func,
            "priority": priority,
            "future": future,
        })

        logger.info(f"分发器: [{agent_name}] 已排队 (优先级:{priority}, 队列长度:{self._queue.qsize()})")

        # 尝试处理队列
        asyncio.create_task(self._process_queue())

        return await future

    async def _process_queue(self):
        """处理队列中的任务"""
        async with self._lock:
            while not self._queue.empty() and self._active_count < self.max_concurrent:
                # 从队列中取最高优先级的任务
                task = await self._get_highest_priority()
                if task is None:
                    break

                self._active_count += 1
                asyncio.create_task(self._run_task(task))

    async def _get_highest_priority(self):
        """从队列中获取优先级最高的任务"""
        best = None
        temp = []
        
        while not self._queue.empty():
            item = await self._queue.get()
            if best is None or item["priority"] < best["priority"]:
                if best is not None:
                    temp.append(best)
                best = item
            else:
                temp.append(item)

        # 将剩余任务放回队列
        for item in temp:
            await self._queue.put(item)

        return best

    async def _run_task(self, task: dict):
        """执行单个任务"""
        agent_name = task["agent"]
        future = task["future"]
        try:
            logger.info(f"分发器: [{agent_name}] 开始执行 ({self._active_count}/{self.max_concurrent} 并发)")
            result = await task["func"]()
            future.set_result(result)
            logger.info(f"分发器: [{agent_name}] 执行完成")
        except Exception as e:
            logger.error(f"分发器: [{agent_name}] 执行失败: {e}")
            future.set_exception(e)
        finally:
            self._active_count -= 1
            # 继续处理队列
            asyncio.create_task(self._process_queue())

    @property
    def stats(self) -> dict:
        """获取分发器状态"""
        return {
            "active": self._active_count,
            "queued": self._queue.qsize(),
            "max_concurrent": self.max_concurrent,
        }
