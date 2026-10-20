"""
FeiyunMY-Bot 统一异常定义
提供标准化的错误类型，便于上层统一捕获和处理
"""


class FeiyunError(Exception):
    """所有自定义异常的基类"""
    code: str = "UNKNOWN"
    message: str = "未知错误"
    status_code: int = 500

    def __init__(self, message: str = None, detail: str = None):
        self.detail = detail
        super().__init__(message or self.message)


class ConfigError(FeiyunError):
    """配置错误（API Key 缺失、配置格式错误等）"""
    code = "CONFIG_ERROR"
    message = "配置错误"
    status_code = 500


class ProviderError(FeiyunError):
    """LLM Provider 调用错误（API 超时、返回异常等）"""
    code = "PROVIDER_ERROR"
    message = "AI 模型调用失败"
    status_code = 502


class ProviderRetryableError(ProviderError):
    """可重试的 Provider 错误（网络波动、临时限流等）"""
    code = "PROVIDER_RETRYABLE"


class ToolError(FeiyunError):
    """工具执行错误"""
    code = "TOOL_ERROR"
    message = "工具调用失败"
    status_code = 400


class ToolTimeoutError(ToolError):
    """工具执行超时"""
    code = "TOOL_TIMEOUT"
    message = "工具执行超时"


class SessionError(FeiyunError):
    """会话管理错误"""
    code = "SESSION_ERROR"
    message = "会话操作失败"
    status_code = 400


class DatabaseError(FeiyunError):
    """数据库错误"""
    code = "DATABASE_ERROR"
    message = "数据库操作失败"
    status_code = 500
