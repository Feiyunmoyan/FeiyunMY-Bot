"""Provider 管理与连通性测试"""
import logging

from fastapi import APIRouter

from .admin_models import (
    ProviderTestRequest,

)
from .admin_state import state

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 多提供商管理 ───

@router.get("/api/providers")
async def get_providers():
    """获取所有提供商列表"""
    return {
        "providers": state.config.get("providers", []),
        "active_id": state.config.get("active_provider_id", ""),
    }


@router.post("/api/providers")
async def save_providers(data: dict):
    """保存所有提供商列表"""
    providers = data.get("providers", [])
    if not isinstance(providers, list):
        return {"status": "fail", "reason": "providers must be a list"}
    state.config["providers"] = providers
    state.config["active_provider_id"] = data.get("active_id", "")
    state.save_config()
    logger.info(f"提供商列表已更新: {len(state.config['providers'])} 个")
    return {"status": "ok"}


@router.post("/api/providers/switch")
async def switch_provider(data: dict):
    """切换当前使用的提供商"""
    provider_id = data.get("provider_id", "")
    providers = state.config.get("providers", [])
    for p in providers:
        if p.get("id") == provider_id:
            # 使用 ProviderManager 切换
            if state.provider_manager:
                state.provider_manager.switch_active(provider_id)
                # 同步更新主脑执行器的 provider 实例
                new_provider = state.provider_manager.get_provider(provider_id)
                if new_provider and state.agent_loop:
                    state.agent_loop.provider = new_provider
                    logger.info(f"主脑执行器已切换到新 Provider: {provider_id}")
            # 选第一个启用的模型
            enabled_models = [m for m in p.get("models", []) if m.get("enabled")]
            if enabled_models:
                state.config["provider"]["model"] = enabled_models[0]["id"]
            state.save_config()
            logger.info(f"提供商已切换: {p.get('name', provider_id)}")
            return {"status": "ok", "provider": p}
    return {"status": "fail", "reason": "提供商未找到"}


# ─── Provider 测试与模型搜索 ───

@router.post("/api/provider/test")
async def test_provider(req: ProviderTestRequest):
    """测试 API 连接是否正常"""
    import httpx
    try:
        # 归一化 URL：去掉末尾的 /v1（如果有），统一拼 /v1/chat/completions
        base = req.base_url.rstrip('/')
        if base.endswith('/v1'):
            base = base[:-3]
        url = f"{base}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {req.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": req.model or "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                return {"status": "ok", "message": "连接成功"}
            else:
                try:
                    data = resp.json()
                    error_msg = data.get("error", {}).get("message", str(resp.status_code))
                except Exception:
                    error_msg = f"HTTP {resp.status_code}"
                return {"status": "fail", "message": error_msg}
    except httpx.TimeoutException:
        return {"status": "fail", "message": "连接超时，请检查 API 地址是否正确"}
    except Exception as e:
        return {"status": "fail", "message": str(e)}


@router.post("/api/provider/models")
async def list_provider_models(req: ProviderTestRequest):
    """获取指定提供商的可选模型列表"""
    import httpx
    try:
        # 归一化 URL
        base = req.base_url.rstrip('/')
        if base.endswith('/v1'):
            base = base[:-3]
        url = f"{base}/v1/models"
        headers = {"Authorization": f"Bearer {req.api_key}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                model_ids = sorted(set(m.get("id", "") for m in models if m.get("id")))
                return {"status": "ok", "models": model_ids, "count": len(model_ids)}
            else:
                return {"status": "fail", "message": f"获取模型列表失败 (HTTP {resp.status_code})，该 API 可能不支持 /v1/models 接口，请手动添加模型"}
    except httpx.TimeoutException:
        return {"status": "fail", "message": "连接超时，请检查 API 地址是否正确"}
    except Exception as e:
        return {"status": "fail", "message": str(e)}
