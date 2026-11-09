"""管理 API 门面

原先这里是 911 行的巨型模块，现已按领域拆分：

    admin_state.py     依赖容器与 set_admin_deps
    admin_models.py    请求体模型
    admin_config.py    配置管理
    admin_search.py    搜索引擎
    admin_provider.py  Provider 管理与连通性测试
    admin_persona.py   人格管理
    admin_capability.py MCP / Skills / Shell 白名单
    admin_memory.py    记忆管理 / 记忆与工具开关
    admin_session.py   会话与文件上传
    admin_system.py    系统统计 / 日志 / 测试页

对外只暴露 router 与 set_admin_deps，main.py 无需改动。
"""
import logging

from fastapi import APIRouter

from .admin_capability import router as capability_router
from .admin_config import router as config_router
from .admin_memory import router as memory_router
from .admin_persona import router as persona_router
from .admin_provider import router as provider_router
from .admin_search import router as search_router
from .admin_session import router as session_router
from .admin_state import AdminDeps, set_admin_deps, state
from .admin_system import router as system_router

logger = logging.getLogger(__name__)

router = APIRouter()

# 挂载顺序与原文件保持一致，避免路径匹配行为发生变化
for _sub_router in (
    config_router,      # 配置
    provider_router,    # Provider
    persona_router,     # 人格
    search_router,      # 搜索引擎
    capability_router,  # MCP → Skills → Shell
    memory_router,      # 记忆
    session_router,     # 会话 → 文件
    system_router,      # 统计 → 日志 → /test
):
    router.include_router(_sub_router)

__all__ = ["AdminDeps", "router", "set_admin_deps", "state"]
