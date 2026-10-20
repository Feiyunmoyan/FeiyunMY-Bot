"""
对话 API 接口
POST /chat       - 非流式对话
POST /chat/stream - 流式对话 (SSE)
"""
import os
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()

_runner = None
_conversation_logger = None
_agent_config_manager = None
_provider_manager = None
_agent_context = None
_memory_selector = None
_persona_manager = None
_tool_registry = None
_main_config = None


def set_runner(runner):
    global _runner
    _runner = runner


def set_chat_agent_deps(
    agent_config_manager=None, provider_manager=None,
    agent_context=None, memory=None, persona_manager=None,
    tool_registry=None, main_config=None,
):
    """注入子 Agent 路由所需的依赖"""
    global _agent_config_manager, _provider_manager, _agent_context
    global _memory_selector, _persona_manager, _tool_registry, _main_config
    _agent_config_manager = agent_config_manager
    _provider_manager = provider_manager
    _agent_context = agent_context
    _memory_selector = memory
    _persona_manager = persona_manager
    _tool_registry = tool_registry
    _main_config = main_config


def set_conversation_logger(logger):
    global _conversation_logger
    _conversation_logger = logger


def _inject_file_content(message: str, file_ids: list = None) -> str:
    """将上传文件的内容注入到用户消息中（AstrBot 方式）"""
    if not file_ids:
        return message

    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
    parts = [message]

    for fid in file_ids:
        filepath = os.path.normpath(os.path.join(upload_dir, fid))
        # 安全检查
        if not filepath.startswith(os.path.normpath(upload_dir)):
            continue
        if not os.path.exists(filepath):
            parts.append(f"\n[文件不存在: {fid}]")
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if len(content) > 5000:
                content = content[:5000] + "\n...（内容过长，仅显示前5000字）"
            parts.append(f"\n\n[文件: {fid}]\n{content}")
        except Exception:
            parts.append(f"\n\n[文件: {fid}]（无法读取内容，可能是二进制文件）")

    return "".join(parts)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    file_ids: Optional[list] = None  # 上传文件的 ID 列表（AstrBot 兼容）


class ChatResponse(BaseModel):
    reply: str
    reasoning: Optional[str] = None
    memories_used: list = []
    tools_used: list = []


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """非流式对话（支持 @ 路由到子 Agent）"""
    if not _runner:
        return ChatResponse(reply="系统未初始化")

    message = _inject_file_content(req.message, req.file_ids)

    # @ 路由拦截：消息以 @ 开头时交给子 Agent 执行器
    if message.startswith("@") and _agent_config_manager:
        from workspace.router import route_and_execute
        route_result = await route_and_execute(
            message=message,
            agent_config_manager=_agent_config_manager,
            workspace_manager=None,
            provider_manager=_provider_manager,
            context=_agent_context,
            memory=_memory_selector,
            persona_manager=_persona_manager,
            tool_registry=_tool_registry,
            main_config=_main_config,
        )
        if route_result.get("routed"):
            reply = route_result.get("reply", "")
            target = route_result.get("target", "agent")
            
            # 主脑审核子 Agent 的执行结果
            review = ""
            if _runner and hasattr(_runner, 'provider'):  
                try:
                    task_msg = req.message
                    task_desc = task_msg[task_msg.index(" ") + 1:] if " " in task_msg else ""
                    review_prompt = (
                        "你是一个项目经理，请简要审核子Agent [" + target + "] 完成的工作。\n"
                        "任务: " + task_desc[:200] + "\n"
                        "执行结果: " + reply[:500] + "\n\n"
                        "请用1-2句话给出评价，包括是否完成任务、有无问题、建议等。"
                    )
                    review_resp = await _runner.provider.chat(
                        messages=[{"role": "user", "content": review_prompt}],
                        temperature=0.3,
                        max_tokens=200,
                    )
                    review_text = review_resp.get("content", "").strip()
                    if review_text:
                        review = "\n\n🧠 主脑审核: " + review_text
                except Exception as e:
                    logger.warning(f"主脑审核失败: {e}")

            full_reply = reply + review

            # 把子 Agent 的执行结果写入主脑上下文
            if _runner and hasattr(_runner, 'context'):
                try:
                    await _runner.context.add_message(
                        req.session_id, "system",
                        f"[{target}] 接受了任务并完成了: {reply[:200]}"
                    )
                except Exception as e:
                    logger.warning(f"写入主脑上下文失败: {e}")
            return ChatResponse(reply=full_reply)

    # 非 @ 消息走正常主脑对话
    result = await _runner.run(message, req.session_id)

    if _conversation_logger:
        _conversation_logger.log(
            session_id=req.session_id,
            user_message=req.message,
            reply=result.get("reply", ""),
            persona=_runner.persona_manager.active_name if hasattr(_runner, 'persona_manager') else "",
            tools_used=result.get("tools_used", []),
            reasoning=result.get("reasoning"),
            memories_used=result.get("memories_used", []),
        )

    return ChatResponse(
        reply=result.get("reply", ""),
        reasoning=result.get("reasoning"),
        memories_used=result.get("memories_used", []),
        tools_used=result.get("tools_used", []),
    )


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """流式对话 (SSE，支持 @ 路由到子 Agent)"""
    if not _runner:
        return ChatResponse(reply="系统未初始化")

    message = _inject_file_content(req.message, req.file_ids)

    # @ 路由拦截
    if message.startswith("@") and _agent_config_manager:
        from workspace.router import route_and_execute
        route_result = await route_and_execute(
            message=message,
            agent_config_manager=_agent_config_manager,
            workspace_manager=None,
            provider_manager=_provider_manager,
            context=_agent_context,
            memory=_memory_selector,
            persona_manager=_persona_manager,
            tool_registry=_tool_registry,
            main_config=_main_config,
        )
        if route_result.get("routed"):
            reply = route_result.get("reply", "")
            target = route_result.get("target", "agent")
            
            # 主脑审核
            review = ""
            if _runner and hasattr(_runner, 'provider'):
                try:
                    task_msg = req.message
                    task_desc = task_msg[task_msg.index(" ") + 1:] if " " in task_msg else ""
                    review_prompt = (
                        "你是一个项目经理，请简要审核子Agent [" + target + "] 完成的工作。\n"
                        "任务: " + task_desc[:200] + "\n"
                        "执行结果: " + reply[:500] + "\n\n"
                        "请用1-2句话给出评价。"
                    )
                    review_resp = await _runner.provider.chat(
                        messages=[{"role": "user", "content": review_prompt}],
                        temperature=0.3, max_tokens=200,
                    )
                    review_text = review_resp.get("content", "").strip()
                    if review_text:
                        review = "\n\n🧠 主脑审核: " + review_text
                except Exception as e:
                    logger.warning(f"主脑审核失败: {e}")

            full_reply = reply + review

            if _runner and hasattr(_runner, 'context'):
                try:
                    await _runner.context.add_message(
                        req.session_id, "system",
                        f"[{target}] 接受了任务并完成了: {reply[:200]}"
                    )
                except Exception as e:
                    logger.warning(f"写入主脑上下文失败: {e}")
            async def gen():
                yield f"data: {json.dumps({'type': 'text', 'content': full_reply}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'content': full_reply}, ensure_ascii=False)}\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")

    async def event_generator():
        try:
            async for event in _runner.run_stream(message, req.session_id):
                if event["type"] in ("text", "reasoning", "tool_used"):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                elif event["type"] == "done":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    # 记录日志
                    if _conversation_logger:
                        _conversation_logger.log(
                            session_id=req.session_id,
                            user_message=req.message,
                            reply=event.get("reply", ""),
                            persona=_runner.persona_manager.active_name if hasattr(_runner, 'persona_manager') else "",
                            reasoning=event.get("reasoning"),
                            tools_used=event.get("tools_used", []),
                            memories_used=event.get("memories_used", []),
                        )
        except Exception as e:
            import traceback
            logger.error(f"流式对话异常: {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
