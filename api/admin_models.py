"""管理 API 的请求体模型"""
from typing import Optional

from pydantic import BaseModel


# ─── Request Models ───

class ConfigUpdate(BaseModel):
    provider: Optional[dict] = None
    memory: Optional[dict] = None
    persona: Optional[dict] = None
    tools: Optional[dict] = None
    web_search: Optional[dict] = None
    features: Optional[dict] = None
    mcp: Optional[dict] = None
    skills: Optional[dict] = None
    shell_whitelist: Optional[dict] = None


class PersonaCreate(BaseModel):
    name: str
    prompt: str = ""
    description: str = ""
    preset_conversations: list = []


class PersonaUpdate(BaseModel):
    prompt: Optional[str] = None
    description: Optional[str] = None
    preset_conversations: Optional[list] = None


class SearchEngineCreate(BaseModel):
    name: str
    type: str = "web"
    enabled: bool = True


class SearchEngineUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None


class MCPServerCreate(BaseModel):
    name: str
    url: str = ""
    description: str = ""
    enabled: bool = True


class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    prompt: str = ""
    enabled: bool = True


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    enabled: Optional[bool] = None


class ProviderTestRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str = ""


class SessionCreate(BaseModel):
    name: str = ""


class SessionRename(BaseModel):
    name: str = ""
