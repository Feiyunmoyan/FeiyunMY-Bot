"""
普通消息按天压缩模块
每天启动时总结昨天的对话，生成日摘要存入摘要表，滚动保留10条
不再删除原始消息，不再清空 conversations 表
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# 摘要滚动上限（保留最近N天的摘要，新的挤掉旧的）
SUMMARY_MAX_COUNT = 10


async def compress_push_messages(db, provider, persona_name="AI"):
    """
    每天启动时：总结昨天的对话，生成日摘要
    
    Args:
        db: FeiyunDatabase 实例
        provider: LLM Provider 实例（用于生成摘要）
        persona_name: AI人格名称，用于摘要中替代"AI"
    """
    now = datetime.now(timezone.utc).timestamp()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_dt = datetime.now(timezone.utc) - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
    
    # 1. 获取当天日期字符串，判断是否已存在昨天的摘要
    summaries = await db.get_push_messages_by_type("daily_summary")
    has_yesterday_summary = False
    for s in summaries:
        ds = _ts_to_date_str(s.get("created_at", 0))
        if ds == yesterday_str:
            has_yesterday_summary = True
            break
    
    if has_yesterday_summary:
        logger.info("昨日的摘要已存在，跳过")
        # 但仍执行滚动清理
        await _roll_summaries(db, summaries)
        return
    
    # 2. 获取昨天的原始消息
    yesterday_start = datetime.strptime(yesterday_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    yesterday_end = yesterday_start + timedelta(days=1)
    
    yesterday_msgs = await db.get_push_messages_in_range(
        yesterday_start.timestamp(), yesterday_end.timestamp(),
        msg_type="chat_reply"
    )
    
    if len(yesterday_msgs) < 3:
        logger.info(f"昨日仅{len(yesterday_msgs)}条消息，跳过摘要生成")
        return
    
    if not provider:
        logger.warning("无provider，跳过压缩")
        return
    
    # 3. 生成摘要（全部压缩，不保留原始消息的副本）
    logger.info(f"生成昨日摘要: {yesterday_str}, {len(yesterday_msgs)}条消息")
    summary = await _generate_summary(yesterday_msgs, provider, yesterday_str, persona_name)
    if not summary:
        logger.warning(f"{yesterday_str}: 摘要为空，跳过")
        return
    
    # 4. 存入摘要表
    await db.add_push_message({
        "id": f"daily_summary_{yesterday_str}",
        "role": "system",
        "content": summary,
        "type": "daily_summary",
        "priority": "normal",
        "source": "daily_compress",
        "created_at": yesterday_start.timestamp(),
    })
    logger.info(f"昨日摘要已存入: {yesterday_str}")
    
    # 5. 滚动清理：超过上限时删除最早的摘要
    summaries = await db.get_push_messages_by_type("daily_summary")
    await _roll_summaries(db, summaries)
    
    logger.info("按天压缩完成")


async def _roll_summaries(db, summaries):
    """摘要滚动：超过上限时删除最早的"""
    if len(summaries) <= SUMMARY_MAX_COUNT:
        return
    
    # 按时间排序，保留最新的 SUMMARY_MAX_COUNT 条
    summaries.sort(key=lambda s: s.get("created_at", 0))
    to_delete = summaries[:-SUMMARY_MAX_COUNT]
    delete_ids = [s["id"] for s in to_delete if s.get("id")]
    
    if delete_ids:
        await db.delete_push_messages_by_ids(delete_ids)
        logger.info(f"摘要滚动: 删除了 {len(delete_ids)} 条最早的摘要，保留 {SUMMARY_MAX_COUNT} 条")


def _ts_to_date_str(ts: float) -> Optional[str]:
    """将时间戳转为日期字符串"""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return None


async def _generate_summary(msgs: list, provider, date_str: str, persona_name: str = "AI") -> Optional[str]:
    """用LLM生成某天的对话摘要，使用人格名称替代'AI'"""
    lines = []
    for m in msgs:
        role = "用户" if m.get("role") == "user" else persona_name
        content = m.get("content", "")
        if not content:
            continue
        if len(content) > 500:
            content = content[:500] + "…"
        lines.append(f"{role}: {content}")
    
    conversation_text = "\n".join(lines)
    
    max_chars = 8000
    if len(conversation_text) > max_chars:
        conversation_text = "…（前略）\n" + conversation_text[-max_chars:]
    
    prompt = (
        f"以下是 {date_str} 的用户与{persona_name}对话记录，请生成一段简洁的摘要（200字以内）。\n"
        "要求：\n"
        "1. 保留用户表达的核心需求、偏好、情绪变化和重要结论\n"
        f"2. 保留{persona_name}给出的关键建议或信息\n"
        "3. 去掉寒暄、重复和工具调用细节\n"
        "4. 用中文连贯描述，按话题排列\n\n"
        f"对话记录：\n{conversation_text}\n\n摘要："
    )
    
    try:
        resp = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        summary = resp.get("content", "").strip()
        if len(summary) < 10:
            return None
        return f"【{date_str}】{summary}"
    except Exception as e:
        logger.error(f"生成摘要失败 {date_str}: {e}")
        return None
