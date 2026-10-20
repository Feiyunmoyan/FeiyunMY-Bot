"""
对话日志记录器
每次对话自动存入 data/logs/
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

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
