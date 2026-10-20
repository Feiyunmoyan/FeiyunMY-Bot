"""
Provider 管理器
统一管理多模型提供商实例的生命周期，支持懒加载、运行时切换、抽象工厂
"""
import logging
from typing import Dict, Optional, Any

from provider import BaseProvider
from provider.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    多 Provider 管理器

    职责：
    - 根据配置懒加载 provider 实例
    - 支持运行时切换活跃 provider
    - 抽象工厂：根据 type 字段创建对应 Provider 实例
    - 统一管理生命周期（创建/获取/关闭）
    """

    def __init__(self, config: dict):
        self._config = config
        self._instances: Dict[str, BaseProvider] = {}
        self._active_id = config.get("active_provider_id", "")

        # 如果活跃 ID 为空，尝试从 provider 配置推断
        if not self._active_id:
            providers = config.get("providers", [])
            if providers:
                self._active_id = providers[0].get("id", "")
            else:
                self._active_id = "default"

    # ─── 抽象工厂 ───

    def _create_provider(self, provider_config: dict) -> BaseProvider:
        """
        根据 provider 配置创建对应类型的实例

        Args:
            provider_config: 提供商配置，包含 type/base_url/api_key/models 等

        Returns:
            BaseProvider 实例
        """
        provider_type = provider_config.get("type", "openai")
        model_id = ""
        models = provider_config.get("models", [])
        if models:
            # 取第一个启用的模型
            for m in models:
                if m.get("enabled", True):
                    model_id = m.get("id", "")
                    break
            if not model_id and models:
                model_id = models[0].get("id", "")

        if provider_type == "openai":
            return OpenAIProvider(
                base_url=provider_config.get("base_url", ""),
                api_key=provider_config.get("api_key", ""),
                model=model_id or provider_config.get("model", "deepseek-chat"),
            )
        # 未来可扩展：anthropic, google, groq 等
        # elif provider_type == "anthropic":
        #     return AnthropicProvider(...)

        logger.warning(f"不支持的 Provider 类型: {provider_type}，回退到 OpenAI 兼容模式")
        return OpenAIProvider(
            base_url=provider_config.get("base_url", ""),
            api_key=provider_config.get("api_key", ""),
            model=model_id or "deepseek-chat",
        )

    def _find_config(self, provider_id: str) -> Optional[dict]:
        """在配置中查找指定 provider_id 的配置"""
        providers = self._config.get("providers", [])
        for p in providers:
            if p.get("id") == provider_id:
                return p
        return None

    # ─── 实例管理 ───

    def get_provider(self, provider_id: str = None) -> Optional[BaseProvider]:
        """
        获取指定 provider 的实例（懒加载）

        Args:
            provider_id: 提供商 ID，为 None 时返回活跃 provider

        Returns:
            BaseProvider 实例，失败返回 None
        """
        pid = provider_id or self._active_id
        if not pid:
            return None

        # 缓存命中
        if pid in self._instances:
            return self._instances[pid]

        # 从 providers 列表查找配置
        config = self._find_config(pid)
        if config:
            instance = self._create_provider(config)
            self._instances[pid] = instance
            logger.info(f"Provider 已加载: {config.get('name', pid)} ({pid})")
            return instance

        # 降级：从主 provider 配置创建
        if pid == self._active_id or pid == "default":
            provider_cfg = self._config.get("provider", {})
            instance = OpenAIProvider(
                base_url=provider_cfg.get("base_url", ""),
                api_key=provider_cfg.get("api_key", ""),
                model=provider_cfg.get("model", "deepseek-chat"),
            )
            self._instances[pid] = instance
            logger.info(f"Provider 已加载 (降级): {pid}")
            return instance

        logger.warning(f"Provider 未找到: {pid}")
        return None

    def get_active_provider(self) -> Optional[BaseProvider]:
        """获取当前活跃 provider 实例"""
        return self.get_provider(self._active_id)

    @property
    def active_id(self) -> str:
        return self._active_id

    # ─── 切换 ───

    def switch_active(self, provider_id: str) -> bool:
        """
        切换活跃 provider

        会创建新实例并替换，而非修改现有实例的属性。
        旧实例会被关闭并从缓存中移除。

        Args:
            provider_id: 目标 provider ID

        Returns:
            是否切换成功
        """
        config = self._find_config(provider_id)
        if not config:
            logger.warning(f"切换失败，Provider 不存在: {provider_id}")
            return False

        # 关闭旧实例（如果存在且不是同一个）
        old_instance = self._instances.get(self._active_id)
        if old_instance and self._active_id != provider_id:
            import asyncio
            try:
                asyncio.ensure_future(old_instance.close())
            except Exception as e:
                logger.warning(f"关闭旧 Provider 实例失败: {e}")
            # 从缓存移除旧实例（但保留当前活跃的以备回退）
            self._instances.pop(self._active_id, None)

        # 创建或获取新实例
        if provider_id not in self._instances:
            instance = self._create_provider(config)
            self._instances[provider_id] = instance

        # 更新配置
        old_active = self._active_id
        self._active_id = provider_id
        self._config["active_provider_id"] = provider_id
        if "provider" in self._config:
            self._config["provider"]["base_url"] = config.get("base_url", "")
            self._config["provider"]["api_key"] = config.get("api_key", "")

        logger.info(f"Provider 已切换: {config.get('name', provider_id)} ({old_active} -> {provider_id})")
        return True

    # ─── 工具方法 ───

    def get_provider_for_agent(self, agent_config: dict) -> Optional[BaseProvider]:
        """
        根据 Agent 配置获取对应的 provider

        Args:
            agent_config: Agent 配置，应包含 model_id 字段

        Returns:
            最适合的 BaseProvider 实例
        """
        model_id = agent_config.get("model_id", "")
        if not model_id:
            return self.get_active_provider()

        # 遍历所有已加载的 provider，查找能提供该模型的
        for pid, instance in self._instances.items():
            if hasattr(instance, 'model') and instance.model == model_id:
                return instance

        # 在配置中查找包含该模型的提供商
        providers = self._config.get("providers", [])
        for p in providers:
            models = p.get("models", [])
            for m in models:
                if m.get("id") == model_id:
                    # 找到匹配的提供商，获取其实例
                    return self.get_provider(p.get("id", ""))

        # 降级：返回活跃 provider
        logger.info(f"Agent 模型 {model_id} 未找到匹配提供商，使用活跃 provider")
        return self.get_active_provider()

    async def close_all(self):
        """关闭所有 provider 实例"""
        for pid, instance in self._instances.items():
            try:
                await instance.close()
                logger.info(f"Provider 已关闭: {pid}")
            except Exception as e:
                logger.warning(f"关闭 Provider {pid} 失败: {e}")
        self._instances.clear()
        logger.info("所有 Provider 实例已关闭")
