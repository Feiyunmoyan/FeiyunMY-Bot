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

# 敏感字段 -> 环境变量名映射
# 配置文件里留空（或写 ${ENV_NAME} 占位）时，自动从环境变量注入
_ENV_SECRET_MAP = {
    ("provider", "api_key"): "FEIYUN_API_KEY",
    ("web_search", "api_key"): "TAVILY_API_KEY",
}

_PLACEHOLDER_PREFIX = "${"


def _resolve_placeholder(value):
    """把 "${ENV_NAME}" 形式的占位符替换为环境变量值"""
    if isinstance(value, str) and value.startswith(_PLACEHOLDER_PREFIX) and value.endswith("}"):
        return os.environ.get(value[2:-1], "")
    return value


def _walk_placeholders(node):
    """递归替换配置中所有 ${ENV_NAME} 占位符"""
    if isinstance(node, dict):
        return {k: _walk_placeholders(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk_placeholders(v) for v in node]
    return _resolve_placeholder(node)


def apply_env_overlay(cfg: dict) -> dict:
    """用环境变量覆盖配置中的敏感字段，避免密钥明文落盘"""
    if not isinstance(cfg, dict):
        return cfg

    cfg = _walk_placeholders(cfg)

    for path, env_name in _ENV_SECRET_MAP.items():
        env_value = os.environ.get(env_name, "").strip()
        if not env_value:
            continue
        section = cfg.get(path[0])
        if isinstance(section, dict) and not str(section.get(path[1]) or "").strip():
            section[path[1]] = env_value
            logger.info(f"配置项 {'.'.join(path)} 已从环境变量 {env_name} 注入")

    # 多 Provider 列表：按 id 匹配 FEIYUN_API_KEY_<ID>，否则回落到 FEIYUN_API_KEY
    providers = cfg.get("providers")
    if isinstance(providers, list):
        default_key = os.environ.get("FEIYUN_API_KEY", "").strip()
        for item in providers:
            if not isinstance(item, dict) or str(item.get("api_key") or "").strip():
                continue
            pid = str(item.get("id") or "").upper().replace("-", "_").replace(".", "_")
            per_key = os.environ.get(f"FEIYUN_API_KEY_{pid}", "").strip() if pid else ""
            if per_key:
                item["api_key"] = per_key
            elif default_key:
                item["api_key"] = default_key

    return cfg


def init_config(config_path: str) -> dict:
    """初始化配置缓存"""
    global _config_path, _config_cache
    _config_path = config_path
    _config_cache = load_config()
    return _config_cache


def load_config() -> dict:
    """从文件加载配置（自动叠加环境变量中的敏感字段）"""
    with open(_config_path, "r", encoding="utf-8") as f:
        return apply_env_overlay(yaml.safe_load(f) or {})


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
