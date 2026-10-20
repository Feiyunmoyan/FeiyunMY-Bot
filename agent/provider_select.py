"""
Provider 选择
根据子 Agent 配置选择 provider 实例（从 agent/runner.py 抽出）。
"""
from provider import BaseProvider


class ProviderSelectMixin:
    """宿主类需提供 self.provider / self.provider_manager。"""

    def get_provider_for_agent(self, agent_config: dict = None) -> BaseProvider:
        """
        根据 Agent 配置获取对应的 provider 实例
        如果传了 agent_config 且有 model_id，则尝试从 ProviderManager 获取
        """
        if agent_config and agent_config.get("model_id") and self.provider_manager:
            model_provider = self.provider_manager.get_provider_for_agent(agent_config)
            if model_provider:
                return model_provider
        return self.provider
