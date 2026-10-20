"""
配置热加载工具
支持在不重启服务的情况下重载部分配置
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

_config_cache = {}
_config_path = None


def init_config(config_path: str) -> dict:
    """初始化配置缓存"""
    global _config_path, _config_cache
    _config_path = config_path
    _config_cache = load_config()
    return _config_cache


def load_config() -> dict:
    """从文件加载配置"""
    with open(_config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_config() -> dict:
    """获取当前配置（从缓存读取）"""
    return _config_cache


def reload_config() -> dict:
    """重载配置，返回新旧配置的差异摘要"""
    global _config_cache
    old = _config_cache
    new = load_config()
    changes = []

    # 检测变化
    for key in ["provider", "persona", "memory"]:
        if old.get(key) != new.get(key):
            changes.append(key)

    tools_old = old.get("tools", {})
    tools_new = new.get("tools", {})
    for name in set(list(tools_old.keys()) + list(tools_new.keys())):
        if tools_old.get(name) != tools_new.get(name):
            changes.append(f"tools.{name}")

    _config_cache = new
    logger.info(f"配置已重载，变更: {', '.join(changes) if changes else '无'}")

    return {
        "status": "ok",
        "changes": changes,
        "message": f"已重载配置，检测到 {len(changes)} 项变更" if changes else "配置无变化",
    }
