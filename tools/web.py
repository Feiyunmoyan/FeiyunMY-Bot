"""
互联网工具：搜索网络信息、读取网页内容
合并了 web_search 和 web_extract
"""
from tools.web_search import web_search, WEB_SEARCH_DEFINITION
from tools.web_extract import web_extract, WEB_EXTRACT_DEFINITION

WEB_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web",
        "description": "互联网工具：搜索网络信息、读取网页内容。当需要查资料、看新闻、访问链接时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["search", "extract"],
                    "description": "search=搜索, extract=读取网页"
                },
                "query": {"type": "string", "description": "搜索关键词（search 时需要）"},
                "url": {"type": "string", "description": "网页地址（extract 时需要）"},
                "offset": {"type": "integer", "description": "读取偏移（extract 续读时用）"},
            },
            "required": ["operation"]
        }
    }
}

async def web(operation: str, query: str = "", url: str = "", offset: int = 0) -> str:
    """互联网工具路由：搜索/提取"""
    if operation == "search":
        return await web_search(query)
    elif operation == "extract":
        return await web_extract(url, offset)
    return "未知操作"
