"""
系统资源监控工具
提供内存、CPU、磁盘、运行时间等系统信息
"""
import os
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_start_time = time.time()

# psutil 为可选依赖，导入失败时降级为简易模式
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil 未安装，系统监控将使用简易模式 (pip install psutil)")


def get_uptime() -> float:
    """获取服务运行时长（秒）"""
    return time.time() - _start_time


def get_memory_usage() -> Dict[str, Any]:
    """获取内存使用情况"""
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
        }
    return {"note": "需安装 psutil"}


def get_cpu_usage() -> Dict[str, Any]:
    """获取 CPU 使用情况"""
    if HAS_PSUTIL:
        return {
            "percent": psutil.cpu_percent(interval=0),
            "count": psutil.cpu_count(),
            "count_logical": psutil.cpu_count(logical=True),
        }
    return {"note": "需安装 psutil"}


def get_disk_usage() -> Dict[str, Any]:
    """获取磁盘使用情况"""
    if HAS_PSUTIL:
        path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        disk = psutil.disk_usage(path)
        return {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
            "path": path,
        }
    return {"note": "需安装 psutil"}


def get_system_stats() -> Dict[str, Any]:
    """获取完整的系统状态信息"""
    stats = {
        "uptime": get_uptime(),
        "uptime_str": _format_uptime(get_uptime()),
        "memory": get_memory_usage(),
        "cpu": get_cpu_usage(),
        "disk": get_disk_usage(),
    }
    if HAS_PSUTIL:
        stats["python"] = {
            "version": __import__("sys").version,
            "pid": os.getpid(),
        }
        stats["platform"] = {
            "system": __import__("platform").system(),
            "release": __import__("platform").release(),
        }
    return stats


def _format_uptime(seconds: float) -> str:
    """格式化运行时间为可读字符串"""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分")
    parts.append(f"{secs}秒")
    return "".join(parts)
