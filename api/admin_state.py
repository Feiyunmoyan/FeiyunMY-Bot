"""管理 API 的运行时依赖容器

原先 api/admin.py 里散着 9 个模块级全局变量，任何函数都能直接摸到。
拆分后统一收进 AdminDeps，子路由通过 state.xxx 显式访问。
"""
import os
import time

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")


class AdminDeps:
    """管理 API 依赖容器"""

    def __init__(self):
        self.config = None
        self.persona_manager = None
        self.memory_selector = None
        self.tool_registry = None
        self.mcp_manager = None
        self.skills_manager = None
        self.agent_loop = None
        self.provider_manager = None
        self.start_time = None

    def bind(self, cfg, pm, ms, tr, mcp_mgr=None, skills_mgr=None,
             agent_loop=None, provider_manager=None):
        self.config = cfg
        self.persona_manager = pm
        self.memory_selector = ms
        self.tool_registry = tr
        self.mcp_manager = mcp_mgr
        self.skills_manager = skills_mgr
        self.agent_loop = agent_loop
        self.provider_manager = provider_manager
        self.start_time = time.time()

    def save_config(self):
        """把内存中的配置写回 config.yaml"""
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)


state = AdminDeps()


def set_admin_deps(cfg, pm, ms, tr, mcp_mgr=None, skills_mgr=None,
                   agent_loop=None, provider_manager=None):
    """兼容原 api.admin.set_admin_deps 的调用签名（main.py 里调用两次）"""
    state.bind(cfg, pm, ms, tr, mcp_mgr, skills_mgr, agent_loop, provider_manager)
