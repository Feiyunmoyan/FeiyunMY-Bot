"""
代码执行工具（简单沙箱）
使用 exec 执行 Python 代码，带有基本的安全限制
"""
import logging
import sys
from io import StringIO

logger = logging.getLogger(__name__)

# 工具定义
CODE_EXEC_DEFINITION = {
    "type": "function",
    "function": {
        "name": "code_exec",
        "description": "在安全沙箱中执行 Python 代码。当用户要求「写代码」「运行代码」「执行Python」「写个脚本」「编程」等需要编程的任务时使用。注意：不能导入 os、subprocess、socket 等系统模块。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的 Python 代码"},
            },
            "required": ["code"],
        },
    },
}

# 黑名单模块
BANNED_MODULES = ["os", "subprocess", "socket", "requests"]


async def code_exec(code: str) -> str:
    """在受限环境中执行 Python 代码"""
    # 安全检查
    for mod in BANNED_MODULES:
        if f"import {mod}" in code or f"from {mod}" in code:
            return f"安全限制：不允许导入 '{mod}' 模块"

    # 捕获输出
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = StringIO()
    sys.stderr = StringIO()

    try:
        # 受限的全局命名空间
        safe_globals = {"__builtins__": __builtins__}
        exec(code, safe_globals, {})
        stdout_val = sys.stdout.getvalue()
        stderr_val = sys.stderr.getvalue()
        result = stdout_val if stdout_val else "(无输出)"
        if stderr_val:
            result = result + "\n[stderr] " + stderr_val
        return result
    except Exception as e:
        return f"代码执行错误: {str(e)}"
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
