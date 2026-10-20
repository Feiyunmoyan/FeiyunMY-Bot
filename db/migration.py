"""
JSON → SQLite 数据迁移脚本
将 data/conversations/ 目录下的 JSON 文件迁移到 SQLite 数据库
"""
import json
import logging
import os
import shutil

logger = logging.getLogger(__name__)


async def migrate_json_to_sqlite(db, data_dir: str = None) -> dict:
    """
    将现有 JSON 会话数据迁移到 SQLite 数据库

    Args:
        db: FeiyunDatabase 实例
        data_dir: JSON 数据目录，默认为 data/conversations/

    Returns:
        dict: 迁移统计信息 {"sessions": n, "messages": n, "skipped": n}
    """
    if data_dir is None:
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "conversations"
        )

    if not os.path.exists(data_dir):
        logger.info("JSON 数据目录不存在，跳过迁移")
        return {"sessions": 0, "messages": 0, "skipped": 0}

    sessions_file = os.path.join(data_dir, "sessions.json")
    if not os.path.exists(sessions_file):
        logger.info("sessions.json 不存在，跳过迁移")
        return {"sessions": 0, "messages": 0, "skipped": 0}

    # 加载 sessions.json
    try:
        with open(sessions_file, "r", encoding="utf-8") as f:
            sessions_data = json.load(f)
    except Exception as e:
        logger.error(f"加载 sessions.json 失败: {e}")
        return {"sessions": 0, "messages": 0, "skipped": 0}

    sessions_meta = sessions_data.get("sessions", {})
    if not sessions_meta:
        logger.info("没有会话数据需要迁移")
        return {"sessions": 0, "messages": 0, "skipped": 0}

    migrated_sessions = 0
    migrated_messages = 0
    skipped = 0

    logger.info(f"开始迁移 {len(sessions_meta)} 个会话...")

    for session_id, meta in sessions_meta.items():
        try:
            # 读取消息文件
            msg_file = os.path.join(data_dir, f"{session_id}.json")
            messages = []
            if os.path.exists(msg_file):
                with open(msg_file, "r", encoding="utf-8") as f:
                    messages = json.load(f)

            # 检查是否已存在
            existing = await db.get_session(session_id)
            if existing:
                logger.debug(f"会话 {session_id} 已存在，跳过")
                skipped += 1
                continue

            # 创建会话
            title = meta.get("name", f"对话 {session_id[:4]}")
            await db.create_session(session_id, title)

            # 创建对话
            if messages:
                await db.create_conversation(
                    session_id=session_id,
                    content=messages,
                    title=title,
                )

            migrated_sessions += 1
            migrated_messages += len(messages)
            logger.debug(f"迁移会话: {session_id} ({len(messages)} 条消息)")

        except Exception as e:
            logger.error(f"迁移会话 {session_id} 失败: {e}")
            skipped += 1

    # 迁移完成后，备份原 JSON 文件
    _backup_json_files(data_dir)

    logger.info(
        f"迁移完成: {migrated_sessions} 个会话, "
        f"{migrated_messages} 条消息, {skipped} 个跳过"
    )
    return {
        "sessions": migrated_sessions,
        "messages": migrated_messages,
        "skipped": skipped,
    }


def _backup_json_files(data_dir: str) -> None:
    """备份原 JSON 文件到 .backup 目录"""
    backup_dir = os.path.join(data_dir, "json_backup")
    os.makedirs(backup_dir, exist_ok=True)

    for filename in os.listdir(data_dir):
        if filename.endswith(".json"):
            src = os.path.join(data_dir, filename)
            dst = os.path.join(backup_dir, filename)
            try:
                shutil.copy2(src, dst)
                logger.debug(f"备份: {filename} -> json_backup/")
            except Exception as e:
                logger.warning(f"备份 {filename} 失败: {e}")
