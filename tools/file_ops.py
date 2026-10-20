"""
文件操作工具（全局限定版）
基于黑名单的安全策略，除了系统核心路径外，其他文件均可读取
"""
import os
import re
import fnmatch
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 工具定义
FILE_OPS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "file_ops",
        "description": "读取、写入、列出、搜索、删除本地文件。当用户要求「读取文件」「写入文件」「保存到文件」「创建文件」「列出文件夹」「搜索文件」「删除文件」等操作时使用。用户上传的文件保存在 data/uploads/ 目录下，可以先 list 查看有哪些文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "search", "info", "grep", "delete"],
                    "description": "操作类型：read(读取文件), write(写入文件), list(列出目录), search(搜索文件), info(文件信息), grep(在文件内容中搜索关键词), delete(删除文件)",
                },
                "path": {
                    "type": "string",
                    "description": "文件或目录路径（绝对路径或相对路径）。read/info 操作填文件路径，list 操作填目录路径",
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（仅 search 操作需要），如 *.txt、*.md、*.json",
                },
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（仅 grep 操作需要），在文件内容中搜索",
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码（仅 read 操作可选），默认 utf-8",
                },
            },
            "required": ["operation", "path"],
        },
    },
}

# ════════════════════════════════════════
# 安全黑名单：禁止访问的路径
# ════════════════════════════════════════

BLACKLIST_DIRS = [
    # Windows 系统目录
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\System Volume Information",
    r"C:\$Recycle.Bin",
    r"C:\Recovery",
    r"C:\ProgramData",
    r"C:\Config.Msi",
    # Linux 系统目录（兼容）
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "/var",
    "/lib",
    "/lib64",
    "/root",
    "/run",
]

BLACKLIST_FILES = [
    # Windows 核心文件
    r"C:\boot.ini",
    r"C:\pagefile.sys",
    r"C:\swapfile.sys",
    r"C:\hiberfil.sys",
    r"C:\autoexec.bat",
    r"C:\config.sys",
    r"C:\Windows\*",
    r"C:\Program Files\*",
    r"C:\Program Files (x86)\*",
    # 数据库文件（二进制，不可读）
    "*.db",
    "*.db-wal",
    "*.db-shm",
    "*.sqlite",
    # 二进制文件
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.bin",
    "*.pyc",
    "*.pyd",
    "*.o",
    "*.class",
    # 图片/媒体
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.bmp",
    "*.ico",
    "*.svg",
    "*.mp3",
    "*.mp4",
    "*.avi",
    "*.mov",
    "*.wav",
    "*.flac",
    "*.zip",
    "*.rar",
    "*.7z",
    "*.tar",
    "*.gz",
]

# 文件大小限制（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024

# 文本文件扩展名（安全可读的）
TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log",
    ".xml", ".html", ".htm", ".css", ".js", ".py", ".java",
    ".cpp", ".c", ".h", ".hpp", ".rs", ".go", ".ts", ".tsx",
    ".jsx", ".vue", ".svelte", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".gitignore", ".dockerfile", ".bat", ".sh", ".ps1",
    ".sql", ".r", ".lua", ".rb", ".php", ".pl", ".swift", ".kt",
}


def _is_blacklisted(filepath: str) -> bool:
    """检查路径是否在黑名单中"""
    abs_path = os.path.abspath(filepath)

    # 检查黑名单目录
    for black_dir in BLACKLIST_DIRS:
        if abs_path.lower().startswith(black_dir.lower()):
            return True

    # 检查黑名单文件模式
    filename = os.path.basename(abs_path)
    for pattern in BLACKLIST_FILES:
        if fnmatch.fnmatch(abs_path, pattern) or fnmatch.fnmatch(filename, pattern):
            return True

    return False


# 全局安全模式开关
_full_access = True  # True=黑名单模式，False=仅data目录

# 工作空间作用域（当设置时，文件操作限定在 data/workspaces/{workspace_id}/ 内）
_workspace_scope = ""  # 为空表示不限制


def set_full_access(enabled: bool):
    """设置文件访问权限模式"""
    global _full_access
    _full_access = enabled
    logger.info(f"文件访问模式: {'全盘' if enabled else '仅 data 目录'}")


def set_workspace_scope(workspace_id: str):
    """设置工作空间作用域，限定文件操作范围"""
    global _workspace_scope
    _workspace_scope = workspace_id
    if workspace_id:
        logger.info(f"文件操作已限定到工作空间: {workspace_id[:8]}...")
    else:
        logger.info("文件操作作用域已清除（恢复全局模式）")


def _safe_path(path: str) -> str:
    """规范化路径并检查安全性"""
    abs_path = os.path.abspath(os.path.normpath(path))

    # 工作空间作用域优先（最严格）
    if _workspace_scope:
        ws_base = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "workspaces", _workspace_scope
        )
        ws_base = os.path.normpath(ws_base)
        if not abs_path.lower().startswith(ws_base.lower()):
            raise PermissionError(
                f"当前处于工作空间 [{_workspace_scope[:8]}...] 作用域，"
                f"只能访问 data/workspaces/{_workspace_scope[:8]}.../ 目录: {path}"
            )
        # 工作空间模式下，如果是 list 操作没有指定子路径，自动指向 output 目录
        return abs_path

    # 全盘模式：无限制
    if not _full_access:
        allowed_base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        allowed_base = os.path.normpath(allowed_base)
        if not abs_path.lower().startswith(allowed_base.lower()):
            raise PermissionError(f"受限模式下只能访问 data/ 目录: {path}")

    return abs_path


async def file_ops(operation: str, path: str, pattern: str = "", keyword: str = "", content: str = "", encoding: str = "utf-8") -> str:
    """执行文件操作"""
    try:
        if operation == "read":
            return await _read_file(path, encoding)
        elif operation == "write":
            return await _write_file(path, content)
        elif operation == "list":
            return await _list_directory(path)
        elif operation == "search":
            return await _search_files(path, pattern)
        elif operation == "grep":
            return await _grep_content(path, keyword)
        elif operation == "info":
            return await _file_info(path)
        elif operation == "delete":
            return await _delete_file(path)
        else:
            return f"未知操作: {operation}"
    except PermissionError as e:
        return f"权限不足: {str(e)}"
    except FileNotFoundError as e:
        return f"文件未找到: {str(e)}"
    except Exception as e:
        return f"文件操作失败: {str(e)}"


async def _read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容"""
    safe = _safe_path(path)

    if not os.path.exists(safe):
        return f"文件不存在: {path}"

    if not os.path.isfile(safe):
        return f"不是文件: {path}"

    # 检查文件扩展名是否可读
    ext = os.path.splitext(safe)[1].lower()
    if ext and ext not in TEXT_EXTENSIONS and ext != "":
        return f"不支持读取 {ext} 类型的文件（二进制文件）"

    # 检查文件大小
    size = os.path.getsize(safe)
    if size > MAX_FILE_SIZE:
        return f"文件过大（{size / 1024 / 1024:.1f}MB），超过限制（10MB）"

    # 尝试多种编码读取
    for enc in [encoding, "utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            with open(safe, "r", encoding=enc) as f:
                content = f.read()
            # 限制返回长度
            if len(content) > 50000:
                content = content[:50000] + f"\n\n...（内容过长，仅显示前50000字符，文件共{len(content)}字符）"
            return content
        except UnicodeDecodeError:
            continue

    return f"无法解码文件，请尝试指定其他 encoding 参数"


async def _list_directory(path: str) -> str:
    """列出目录内容"""
    safe = _safe_path(path)

    if not os.path.exists(safe):
        return f"目录不存在: {path}"

    if not os.path.isdir(safe):
        return f"不是目录: {path}"

    try:
        items = os.listdir(safe)
    except PermissionError:
        return f"没有权限访问目录: {path}"

    # 分类排序
    dirs = []
    files_list = []
    for item in sorted(items):
        full = os.path.join(safe, item)
        if os.path.isdir(full):
            dirs.append(f"  [DIR]  {item}/")
        else:
            size = os.path.getsize(full)
            size_str = _format_size(size)
            files_list.append(f"  [FILE] {item}  ({size_str})")

    result = [f"📁 {path} 的目录列表:"]
    if dirs:
        result.append(f"\n子目录 ({len(dirs)}):")
        result.extend(dirs)
    if files_list:
        result.append(f"\n文件 ({len(files_list)}):")
        result.extend(files_list)

    total = len(dirs) + len(files_list)
    result.append(f"\n共 {total} 项")

    return "\n".join(result)


async def _search_files(path: str, pattern: str) -> str:
    """搜索匹配的文件"""
    safe = _safe_path(path)

    if not os.path.exists(safe):
        return f"路径不存在: {path}"

    if not pattern:
        return "请提供搜索模式，如 *.txt"

    matches = []
    for root, dirs, files in os.walk(safe):
        # 跳过黑名单目录
        dirs[:] = [d for d in dirs if not _is_blacklisted(os.path.join(root, d))]
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                full = os.path.join(root, f)
                if not _is_blacklisted(full):
                    matches.append(full)

    if not matches:
        return f"在 {path} 中未找到匹配 {pattern} 的文件"

    # 限制显示数量
    MAX_SHOW = 50
    shown = matches[:MAX_SHOW]
    result = [f"在 {path} 中找到 {len(matches)} 个匹配 {pattern} 的文件:"]
    for m in shown:
        result.append(f"  {m}")
    if len(matches) > MAX_SHOW:
        result.append(f"... 以及另外 {len(matches) - MAX_SHOW} 个")

    return "\n".join(result)


async def _file_info(path: str) -> str:
    """获取文件/目录信息"""
    safe = _safe_path(path)

    if not os.path.exists(safe):
        return f"路径不存在: {path}"

    is_dir = os.path.isdir(safe)
    type_str = "目录" if is_dir else "文件"

    info = [f"📄 {path} 的信息:"]
    info.append(f"  类型: {type_str}")
    info.append(f"  绝对路径: {os.path.abspath(safe)}")

    if not is_dir:
        size = os.path.getsize(safe)
        info.append(f"  大小: {_format_size(size)}")

    mtime = os.path.getmtime(safe)
    info.append(f"  修改时间: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(info)


async def _write_file(path: str, content: str) -> str:
    """写入文件"""
    if not content:
        return "写入内容不能为空"
    safe = _safe_path(path)
    try:
        os.makedirs(os.path.dirname(safe), exist_ok=True)
        with open(safe, "w", encoding="utf-8") as f:
            f.write(content)
        return f"文件已写入: {path}（{len(content)}字符）"
    except Exception as e:
        return f"写入失败: {str(e)}"


async def _delete_file(path: str) -> str:
    """删除文件"""
    safe = _safe_path(path)
    if not os.path.exists(safe):
        return f"文件不存在: {path}"
    if os.path.isdir(safe):
        return "不能删除目录（为防止误删，仅支持删除文件）: " + path
    try:
        os.remove(safe)
        return f"文件已删除: {path}"
    except Exception as e:
        return f"删除失败: {str(e)}"


def _format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MB"
    else:
        return f"{size / 1024 / 1024 / 1024:.2f} GB"


async def _grep_content(path: str, keyword: str) -> str:
    """在文件内容中搜索关键词"""
    if not keyword:
        return "请提供搜索关键词"

    safe = _safe_path(path)

    if not os.path.exists(safe):
        return f"路径不存在: {path}"

    matches = []
    MAX_MATCHES = 50
    MAX_FILE_SIZE = 1024 * 1024  # 只搜索 1MB 以内的文件

    for root, dirs, files in os.walk(safe):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            filepath = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXTENSIONS and ext not in ('.py', '.js', '.ts', '.html', '.css', '.vue'):
                continue
            if os.path.getsize(filepath) > MAX_FILE_SIZE:
                continue

            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                    for line_no, line in enumerate(fp, 1):
                        if keyword.lower() in line.lower():
                            rel_path = os.path.relpath(filepath, safe)
                            snippet = line.strip()[:100]
                            matches.append(f"  {rel_path}:{line_no}  {snippet}")
                            if len(matches) >= MAX_MATCHES:
                                break
            except Exception:
                continue
            if len(matches) >= MAX_MATCHES:
                break
        if len(matches) >= MAX_MATCHES:
            break

    if not matches:
        return f"在 {path} 中未找到包含 \"{keyword}\" 的内容"

    result = [f"在 {path} 中找到 {len(matches)} 处 \"{keyword}\":"]
    result.extend(matches[:50])
    if len(matches) > 50:
        result.append(f"... 以及另外 {len(matches) - 50} 处")

    return "\n".join(result)
