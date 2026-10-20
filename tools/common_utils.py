"""
常用时间/计算工具
"""
import logging
import math
import random as _random
from datetime import datetime

logger = logging.getLogger(__name__)

# ====== 时间工具 ======

DATETIME_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_datetime",
        "description": "获取当前的准确日期和时间。当用户问「现在几点」「今天几号」「星期几」等时间相关问题时，必须调用此工具获取真实时间，不要自己编造。",
        "parameters": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["full", "date", "time", "weekday"],
                    "description": "时间格式: full(完整日期时间), date(仅日期), time(仅时间), weekday(星期几)",
                },
            },
            "required": [],
        },
    },
}

async def get_datetime(format: str = "full") -> str:
    """获取当前时间"""
    now = datetime.now()
    formats = {
        "full": now.strftime("%Y-%m-%d %H:%M:%S (%A)"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][now.weekday()],
    }
    return formats.get(format, formats["full"])


# ====== 计算器工具 ======

CALCULATOR_DEFINITION = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "计算数学表达式。当用户问「等于多少」「算一下」「计算」等需要精确计算的问题时使用。支持加(+)、减(-)、乘(*)、除(/)、取余(%)、幂(**)、括号等运算。例如计算 (3.5+4)*2 或 2**10。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，例如: (3.5 + 4) * 2",
                },
            },
            "required": ["expression"],
        },
    },
}

async def calculator(expression: str) -> str:
    """安全计算数学表达式"""
    allowed = set("0123456789.+-*/()%** ")
    for c in expression:
        if c not in allowed:
            return f"表达式包含非法字符: '{c}'"
    try:
        result = eval(expression, {"__builtins__": {}}, {"math": math})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# ====== 随机工具 ======

RANDOM_DEFINITION = {
    "type": "function",
    "function": {
        "name": "random_utils",
        "description": "生成随机数或做随机选择。当用户说「随机」「随便选一个」「抽一个」「扔骰子」「随机数」等时使用。支持生成指定范围的随机数，或从多个选项中随机选一个。",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["number", "choice"],
                    "description": "类型: number(随机数), choice(随机选择)",
                },
                "min": {"type": "number", "description": "最小值（number模式）"},
                "max": {"type": "number", "description": "最大值（number模式）"},
                "choices": {
                    "type": "string",
                    "description": "选项列表（choice模式），用逗号分隔",
                },
            },
            "required": ["type"],
        },
    },
}

async def random_utils(type: str = "number", min: float = 0, max: float = 100, choices: str = "") -> str:
    """随机工具"""
    if type == "number":
        result = _random.uniform(min, max)
        return f"随机数 ({min}~{max}): {result:.2f}"
    elif type == "choice":
        if not choices:
            return "请提供选项列表"
        items = [c.strip() for c in choices.split(",") if c.strip()]
        if not items:
            return "选项列表为空"
        chosen = _random.choice(items)
        return f"随机选择: {chosen}"
    return f"未知类型: {type}"


# ====== 合并工具（通用路由） ======

COMMON_UTILS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "common_utils",
        "description": "通用工具：获取当前日期时间、数学计算、生成随机数。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["datetime", "calculate", "random"],
                    "description": "操作类型"
                },
                "expression": {"type": "string", "description": "数学表达式（calculate 时需要），如 2+3*4"},
                "n": {"type": "integer", "description": "随机生成个数（random 时需要）"},
                "min_val": {"type": "integer", "description": "随机最小值"},
                "max_val": {"type": "integer", "description": "随机最大值"},
            },
            "required": ["operation"]
        }
    }
}

async def common_utils(operation: str, expression: str = "", n: int = 1, min_val: int = 0, max_val: int = 100) -> str:
    """通用工具路由：时间/计算/随机"""
    if operation == "datetime":
        return await get_datetime()
    elif operation == "calculate":
        if not expression:
            return "请提供数学表达式"
        return await calculator(expression)
    elif operation == "random":
        return await random_utils(type="number", min=min_val, max=max_val)
    return "未知操作"
