"""
Agent 专属工具集
HTTP请求、笔记、数据处理、Shell 执行（动态白名单）
"""
import os
import json
import csv
import io
import uuid
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


# ====== 1. HTTP 请求工具 ======

HTTP_REQUEST_DEFINITION = {
    "type": "function",
    "function": {
        "name": "http_request",
        "description": "发送 HTTP 请求获取网页内容或调用 API。当用户说「帮我请求这个网址」「看看这个API」「抓取网页」「调接口」等需要从网络获取数据时使用。支持 GET 和 POST 方法，可以自定义请求头和请求体。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "请求的 URL 地址"},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "请求方法",
                },
                "headers": {
                    "type": "string",
                    "description": "请求头，JSON 格式字符串，例如: {\"Authorization\": \"Bearer xxx\"}",
                },
                "body": {
                    "type": "string",
                    "description": "POST 请求体（JSON 字符串）",
                },
            },
            "required": ["url"],
        },
    },
}

async def http_request(url: str, method: str = "GET", headers: str = "", body: str = "") -> str:
    """发送 HTTP 请求"""
    import httpx
    try:
        req_headers = {}
        if headers:
            req_headers = json.loads(headers)

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "POST":
                req_body = {}
                if body:
                    req_body = json.loads(body)
                response = await client.post(url, headers=req_headers, json=req_body)
            else:
                response = await client.get(url, headers=req_headers)

            result = response.text[:3000]
            return f"状态码: {response.status_code}\n响应:\n{result}"

    except Exception as e:
        return f"HTTP 请求失败: {str(e)}"


# ====== 2. AI 笔记工具 ======

NOTE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "note_taking",
        "description": "AI 笔记管理：记录、读取、搜索笔记，跨会话保留。当用户说「帮我记一下」「记住这个」时调用 write 保存。同时你也可以主动判断：当用户分享个人信息（姓名、年龄、爱好、宠物等）、重要偏好、关键需求时，主动调用 write 记录下来，方便以后回忆。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["write", "read", "list", "delete", "search"],
                    "description": "操作: write(写), read(读), list(列表), delete(删), search(搜索)",
                },
                "title": {"type": "string", "description": "笔记标题（write/read/delete 时需要）"},
                "content": {"type": "string", "description": "笔记内容（write 时需要）"},
                "tags": {"type": "string", "description": "标签，逗号分隔（write 可选）"},
                "keyword": {"type": "string", "description": "搜索关键词（search 时需要）"},
            },
            "required": ["operation"],
        },
    },
}

_NOTES = None

def _get_notes():
    global _NOTES
    if _NOTES is None:
        notes_dir = os.path.join(DATA_DIR, "notes")
        os.makedirs(notes_dir, exist_ok=True)
        notes_file = os.path.join(notes_dir, "ai_notes.json")
        if os.path.exists(notes_file):
            try:
                with open(notes_file, "r", encoding="utf-8") as f:
                    _NOTES = json.load(f)
            except:
                _NOTES = []
        else:
            _NOTES = []
    return _NOTES

def _save_notes(notes):
    notes_dir = os.path.join(DATA_DIR, "notes")
    os.makedirs(notes_dir, exist_ok=True)
    notes_file = os.path.join(notes_dir, "ai_notes.json")
    with open(notes_file, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

async def note_taking(operation: str = "list", title: str = "", content: str = "", tags: str = "", keyword: str = "") -> str:
    """AI 笔记管理"""
    notes = _get_notes()

    if operation == "write":
        if not title:
            return "请提供笔记标题"
        note = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "content": content,
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "created_at": datetime.now().isoformat(),
        }
        notes.insert(0, note)
        _save_notes(notes)
        return f"笔记已保存: {title} (id: {note['id']})"

    elif operation == "read":
        for n in notes:
            if n["title"] == title or n["id"] == title:
                result = f"标题: {n['title']}\n标签: {', '.join(n.get('tags', []))}\n时间: {n['created_at']}\n内容:\n{n['content']}"
                return result
        return f"未找到笔记: {title}"

    elif operation == "list":
        if not notes:
            return "暂无笔记"
        result = f"共 {len(notes)} 条笔记:\n"
        for i, n in enumerate(notes[:20], 1):
            tags_str = ", ".join(n.get("tags", [])) if n.get("tags") else ""
            result += f"{i}. [{n['id']}] {n['title']} {f'({tags_str})' if tags_str else ''}\n"
        return result

    elif operation == "delete":
        for i, n in enumerate(notes):
            if n["title"] == title or n["id"] == title:
                deleted = notes.pop(i)
                _save_notes(notes)
                return f"已删除笔记: {deleted['title']}"
        return f"未找到笔记: {title}"

    elif operation == "search":
        if not keyword:
            return "请提供搜索关键词"
        keyword_lower = keyword.lower()
        results = []
        for n in notes:
            if (keyword_lower in n["title"].lower() or
                keyword_lower in n["content"].lower() or
                any(keyword_lower in t.lower() for t in n.get("tags", []))):
                results.append(n)
        if not results:
            return f"未找到包含 '{keyword}' 的笔记"
        result = f"找到 {len(results)} 条笔记:\n"
        for i, n in enumerate(results[:10], 1):
            result += f"{i}. [{n['id']}] {n['title']}\n"
        return result

    return "未知操作"


# ====== 3. JSON/CSV 数据处理工具 ======

JSON_PROCESS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "json_process",
        "description": "处理 JSON 或 CSV 数据：解析、查询、过滤、转换。当用户给出 JSON 字符串或 CSV 表格数据要求「解析」「提取」「查询」「过滤」「分析」时使用。支持点路径查询(如 data.items[0].name)、条件过滤(如 age>18)、CSV列提取。",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "要处理的 JSON 或 CSV 字符串"},
                "query": {
                    "type": "string",
                    "description": "查询表达式: 点路径(如 data.items[0].name), filter条件(如 age>18), csv列名",
                },
                "format": {
                    "type": "string",
                    "enum": ["json", "csv", "auto"],
                    "description": "输入数据格式",
                },
                "output": {
                    "type": "string",
                    "enum": ["text", "json", "csv"],
                    "description": "输出格式",
                },
            },
            "required": ["data", "query"],
        },
    },
}

async def json_process(data: str, query: str = "", format: str = "auto", output: str = "text") -> str:
    """JSON/CSV 数据处理"""
    try:
        if format == "auto":
            stripped = data.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                format = "json"
            elif "," in stripped and "\n" in stripped:
                format = "csv"
            else:
                format = "json"

        parsed = None
        if format == "csv":
            reader = csv.DictReader(io.StringIO(data))
            parsed = [row for row in reader]
        else:
            parsed = json.loads(data)

        if not query:
            return f"解析结果:\n{json.dumps(parsed, ensure_ascii=False, indent=2)[:2000]}"

        if query.startswith("data.") or query.startswith("["):
            parts = query.replace("data.", "").split(".")
            current = parsed
            for part in parts:
                if "[" in part and "]" in part:
                    name, idx_str = part.split("[")
                    idx = int(idx_str.rstrip("]"))
                    current = current[name][idx] if isinstance(current, dict) else current[idx]
                elif isinstance(current, dict):
                    current = current.get(part, "未找到")
                elif isinstance(current, list):
                    try:
                        current = current[int(part)]
                    except:
                        current = f"无法解析路径: {query}"
                        break
            return f"查询结果:\n{json.dumps(current, ensure_ascii=False, indent=2)[:2000]}"

        if ">" in query or "<" in query or "=" in query or "!=" in query:
            if isinstance(parsed, list):
                import re
                match = re.match(r"(\w+)\s*(>=?|<=?|==|!=)\s*(.+)", query)
                if match:
                    key, op, val = match.groups()
                    val = val.strip().strip("'\"")
                    results = []
                    for item in parsed:
                        if isinstance(item, dict) and key in item:
                            item_val = item[key]
                            try:
                                if eval(f"'{item_val}' {op} '{val}'"):
                                    results.append(item)
                            except:
                                try:
                                    if eval(f"{float(item_val)} {op} {float(val)}"):
                                        results.append(item)
                                except:
                                    pass
                    return json.dumps(results[:20], ensure_ascii=False, indent=2)[:2000]

        if format == "csv" and isinstance(parsed, list) and parsed:
            if query in parsed[0]:
                values = [row[query] for row in parsed]
                return f"列 '{query}' 的值 ({len(values)} 条):\n" + "\n".join(str(v) for v in values[:50])

        return f"查询完成 ({len(parsed) if isinstance(parsed, list) else 1} 条)"

    except Exception as e:
        return f"数据处理失败: {str(e)}"


# ====== 4. Shell 命令执行工具（动态白名单） ======

SHELL_EXEC_DEFINITION = {
    "type": "function",
    "function": {
        "name": "shell_exec",
        "description": "在受限安全环境中执行 Windows Shell 命令。仅允许执行白名单内的命令（如 dir、echo、type、find 等）。当用户要求「执行命令」「运行cmd」「查看目录」「列出文件」等时使用。注意：只能执行白名单中已有的命令。",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 Shell 命令"},
                "timeout": {
                    "type": "number",
                    "description": "超时时间（秒）",
                },
            },
            "required": ["command"],
        },
    },
}

# 动态白名单（由 main.py 注入）
_shell_whitelist = []

def set_shell_whitelist(whitelist: list):
    """设置动态白名单"""
    global _shell_whitelist
    _shell_whitelist = whitelist

def _is_command_allowed(command: str) -> bool:
    """检查命令是否在白名单中"""
    if not _shell_whitelist:
        return False
    cmd_lower = command.lower().strip()
    for allowed in _shell_whitelist:
        if cmd_lower == allowed.lower().strip() or cmd_lower.startswith(allowed.lower().strip() + " "):
            return True
    if cmd_lower.startswith("python ") and ".." not in cmd_lower:
        return True
    return False

async def shell_exec(command: str, timeout: int = 15) -> str:
    """在受限环境中执行 Shell 命令"""
    if not _is_command_allowed(command):
        whitelist_str = ", ".join(_shell_whitelist[:10])
        if len(_shell_whitelist) > 10:
            whitelist_str += "..."
        return (
            f"安全限制：命令不在白名单内。\n"
            f"当前白名单 ({len(_shell_whitelist)} 条): {whitelist_str}"
        )

    dangerous = ["rm ", "del ", "rd ", "format ", "shutdown", "taskkill"]
    for d in dangerous:
        if d in command.lower():
            return f"安全限制：不允许执行危险命令 ({d})"

    try:
        import subprocess
        proc = await asyncio.to_thread(
            subprocess.run, command,
            capture_output=True, encoding='gbk', errors='replace', shell=True,
            timeout=timeout
        )
        result = proc.stdout[:2000] if proc.stdout else ""
        if proc.stderr:
            result += f"\n[stderr] {proc.stderr[:500]}"
        return result if result else "(无输出)"
    except Exception as e:
        import traceback
        logger.error(f"Shell执行异常 [{type(e).__name__}]: {e}\
{traceback.format_exc()}")
        return f"Shell 执行失败: [{type(e).__name__}] {str(e)}"


# ====== 5. 记忆查询工具 ======
MEMORY_QUERY_DEFINITION = {
    "type": "function",
    "function": {
        "name": "memory_query",
        "description": "查询长期记忆库，获取与当前话题相关的历史记忆。当你觉得需要回忆之前的对话内容时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要搜索的内容，尽量具体"},
                "top_k": {"type": "integer", "description": "返回结果数量", "default": 5}
            },
            "required": ["query"]
        }
    }
}


# ====== 7. 历史摘要查询工具 ======
SUMMARY_QUERY_DEFINITION = {
    "type": "function",
    "function": {
        "name": "summary_query",
        "description": "查询每日对话摘要，获取某天的对话概览。用于回忆超过5天前的历史对话内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "要查询的日期，格式 YYYY-MM-DD。留空则列出最近10天的摘要"},
                "keyword": {"type": "string", "description": "按关键词筛选摘要（可选）"}
            },
            "required": []
        }
    }
}


async def summary_query(date: str = "", keyword: str = "") -> str:
    """查询每日对话摘要"""
    if not _session_context:
        return "错误：系统未初始化"
    try:
        db = _session_context.db
        summaries = await db.get_push_messages_by_type("daily_summary")
        if not summaries:
            return "暂无历史摘要"
        
        # 按时间排序（最新在前）
        summaries.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        
        result = []
        for s in summaries:
            content = s.get("content", "")
            created = s.get("created_at", 0)
            from datetime import datetime
            date_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if created else "未知日期"
            
            if date and date not in date_str:
                continue
            if keyword and keyword not in content:
                continue
            
            result.append(f"[{date_str}] {content[:300]}")
        
        if not result:
            return "未找到匹配的摘要"
        
        return "\n\n".join(result[:10])
    except Exception as e:
        return f"查询摘要失败: {e}"

# ====== 6. 会话管理工具 ======
MANAGE_SESSION_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_session",
        "description": "管理对话会话。创建新会话用于区分不同话题，或查看现有会话列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "info"],
                    "description": "操作类型：create=新建会话，list=列出所有，info=查看当前"
                },
                "name": {"type": "string", "description": "新建会话时的标题（可选）"}
            },
            "required": ["action"]
        }
    }
}

# 全局引用注入
_memory_selector = None
_session_context = None

def set_memory_selector(ms):
    global _memory_selector
    _memory_selector = ms

def set_session_context(ctx):
    global _session_context
    _session_context = ctx

async def memory_query(query: str, top_k: int = 5) -> str:
    """查询长期记忆库"""
    if not _memory_selector:
        return "记忆系统未初始化"
    try:
        # memory_selector.query 通常是同步的
        results = _memory_selector.query(query, top_k=top_k)
        if not results:
            return "未找到相关记忆"
        lines = [f"[{r.get('relevance', 0):.2f}] {r.get('content', '')}" for r in results]
        return "\n".join(lines)
    except Exception as e:
        return f"记忆查询失败: {str(e)}"

async def manage_session(action: str = "list", name: str = None) -> str:
    """管理会话"""
    if not _session_context:
        return "会话系统未初始化"
    try:
        if action == "create":
            sid = await _session_context.create_session(name)
            return f"已创建新会话: {sid}"
        elif action == "list":
            sessions = await _session_context.list_sessions()
            return "\n".join([f"[{s['id'][:8]}] {s['name']} ({s.get('message_count', 0)}条)" for s in sessions])
        elif action == "info":
            return "当前会话信息查询功能待实现"
        return f"未知操作: {action}"
    except Exception as e:
        return f"会话管理失败: {str(e)}"


# ====== 7. 合并执行工具（Python 代码 + Shell 命令） ======

EXECUTE_DEFINITION = {
    "type": "function",
    "function": {
        "name": "execute",
        "description": "执行工具：运行 Python 代码或执行系统命令。当需要写代码运行、执行命令时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["python", "shell"],
                    "description": "python=运行Python代码, shell=执行系统命令"
                },
                "code": {"type": "string", "description": "Python 代码（python 时需要）"},
                "command": {"type": "string", "description": "系统命令（shell 时需要）"},
            },
            "required": ["operation"]
        }
    }
}

async def execute(operation: str, code: str = "", command: str = "") -> str:
    """执行工具路由：Python/Shell"""
    if operation == "python":
        # 动态导入避免循环依赖
        from tools.code_exec import code_exec
        return await code_exec(code)
    elif operation == "shell":
        return await shell_exec(command)
    return "未知操作"
