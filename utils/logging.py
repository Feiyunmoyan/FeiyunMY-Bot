"""
平台日志与对话日志工具

- 平台日志：写入文件，并提供 API 读取接口（原 utils/platform_logger.py）
- 对话日志：每轮对话按日期追加到 data/logs/conversations_YYYY-MM-DD.jsonl（原 utils/conversation_logger.py）
"""
import os
import logging
from logging.handlers import RotatingFileHandler

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件路径
LOG_FILE = os.path.join(LOG_DIR, "platform.log")

# 最近的日志缓存（在内存中保留最近 N 条）
_log_cache = []
_MAX_CACHE = 500


class CacheHandler(logging.Handler):
    """将日志同时缓存到内存中，供 API 读取"""
    def emit(self, record):
        global _log_cache
        msg = self.format(record)
        _log_cache.append(msg)
        if len(_log_cache) > _MAX_CACHE:
            _log_cache = _log_cache[-_MAX_CACHE:]


def setup_logging():
    """配置日志：同时输出到控制台、文件和内存缓存"""
    root_logger = logging.getLogger()

    # 防止热重载时重复添加
    if any(isinstance(h, (RotatingFileHandler, CacheHandler)) for h in root_logger.handlers):
        return root_logger

    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件日志（每天最多 10MB，保留 5 个历史文件）
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 内存缓存日志
    cache_handler = CacheHandler()
    cache_handler.setFormatter(formatter)
    root_logger.addHandler(cache_handler)

    return root_logger


def get_recent_logs(lines: int = 100, level: str = "", keyword: str = "") -> list:
    """
    获取最近的日志

    Args:
        lines: 返回条数
        level: 过滤级别（INFO / WARNING / ERROR）
        keyword: 关键词过滤

    Returns:
        list: 日志行列表
    """
    logs = _log_cache[-lines:] if _log_cache else []

    # 从文件补充（如果缓存不够）
    if len(logs) < lines and os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                file_logs = f.readlines()
            file_logs = [l.strip() for l in file_logs if l.strip()]
            logs = file_logs[-lines:]
        except Exception:
            pass

    # 过滤级别
    if level:
        level_upper = level.upper()
        logs = [l for l in logs if f"[{level_upper}]" in l]

    # 过滤关键词
    if keyword:
        logs = [l for l in logs if keyword.lower() in l.lower()]

    return logs[-lines:]


def get_log_stats() -> dict:
    """获取日志统计信息"""
    total = len(_log_cache)
    levels = {"INFO": 0, "WARNING": 0, "ERROR": 0, "DEBUG": 0}
    for log in _log_cache:
        for lv in levels:
            if f"[{lv}]" in log:
                levels[lv] += 1
                break

    file_size = 0
    if os.path.exists(LOG_FILE):
        file_size = os.path.getsize(LOG_FILE)

    return {
        "cache_count": total,
        "levels": levels,
        "file_size": file_size,
        "file_path": LOG_FILE,
    }


# ===================== 对话日志 =====================

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")


class ConversationLogger:
    """对话日志记录器"""

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)

    def log(
        self,
        session_id: str,
        user_message: str,
        reply: str,
        persona: str = "",
        tools_used: list = None,
        reasoning: str = None,
        memories_used: list = None,
        metadata: dict = None,
    ):
        """记录一轮对话"""
        try:
            record = {
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "persona": persona,
                "user_message": user_message,
                "reply": reply,
                "tools_used": tools_used or [],
                "reasoning": reasoning,
                "memories_count": len(memories_used or []),
                "metadata": metadata or {},
            }

            # 按日期分文件
            date_str = datetime.now().strftime("%Y-%m-%d")
            file_path = os.path.join(LOG_DIR, f"conversations_{date_str}.jsonl")

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.error(f"写入对话日志失败: {e}")

    def get_recent(self, limit: int = 10) -> list:
        """获取最近的对话记录"""
        try:
            all_records = []
            for fname in sorted(os.listdir(LOG_DIR), reverse=True):
                if fname.startswith("conversations_") and fname.endswith(".jsonl"):
                    fpath = os.path.join(LOG_DIR, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                all_records.append(json.loads(line))
                    if len(all_records) >= limit:
                        break

            return all_records[-limit:]

        except Exception as e:
            logger.error(f"读取对话日志失败: {e}")
            return []
