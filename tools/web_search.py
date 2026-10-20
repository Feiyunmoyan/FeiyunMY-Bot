"""
网页搜索工具
支持多个搜索提供商：百度(免费)、DuckDuckGo、SerpAPI、Tavily、Bing
"""
import logging
import re
import httpx
from urllib.parse import quote

logger = logging.getLogger(__name__)

WEB_SEARCH_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索互联网获取最新信息。当用户需要「搜索」「查一下」「找找看」「最新消息」等需要网络资讯时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    },
}

_search_config = {"provider": "baidu", "api_key": ""}


def set_search_config(config: dict):
    global _search_config
    _search_config = config
    logger.info(f"搜索配置已更新: provider={config.get('provider')}")


async def web_search(query: str) -> str:
    provider = _search_config.get("provider", "baidu")
    api_key = _search_config.get("api_key", "")

    if provider == "baidu":
        return await _search_baidu(query)
    elif provider == "duckduckgo":
        return await _search_duckduckgo(query)
    elif provider == "serpapi":
        return await _search_serpapi(query, api_key)
    elif provider == "tavily":
        return await _search_tavily(query, api_key)
    elif provider == "bing":
        return await _search_bing(query, api_key)
    else:
        return f"搜索提供商 '{provider}' 未支持"


async def _search_baidu(query: str) -> str:
    """百度搜索（免费，国内可用）"""
    try:
        url = "https://www.baidu.com/s?wd=" + quote(query) + "&rn=5"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            text = resp.text

        results = []
        items = re.findall(r'<h3[^>]*>.*?<a[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', text, re.DOTALL)
        for link, title in items[:5]:
            title = re.sub(r'<[^>]+>', '', title).strip()
            if title:
                results.append(title + "\n  " + link)

        if not results:
            results.append("未找到 '" + query + "' 的相关结果")

        return "\n\n".join(results)

    except Exception as e:
        return "百度搜索失败: " + str(e)


async def _search_duckduckgo(query: str) -> str:
    """DuckDuckGo 搜索（免费，国内可能被墙）"""
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        results = []
        abstract = data.get("AbstractText", "")
        if abstract:
            results.append("[摘要] " + abstract)

        related = data.get("RelatedTopics", [])
        for item in related[:5]:
            if "Text" in item:
                results.append("- " + item["Text"])
            elif "Topics" in item:
                for sub in item["Topics"][:3]:
                    if "Text" in sub:
                        results.append("- " + sub["Text"])

        return "\n".join(results) if results else "未找到结果"

    except Exception as e:
        return "DuckDuckGo 搜索失败: " + str(e)


async def _search_serpapi(query: str, api_key: str) -> str:
    """SerpAPI 搜索（需要 API Key）"""
    if not api_key:
        return "请先配置 SerpAPI API Key"
    try:
        url = "https://serpapi.com/search"
        params = {"q": query, "api_key": api_key, "hl": "zh-cn"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()

        results = []
        for item in data.get("organic_results", [])[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            results.append(title + "\n  " + snippet + "\n  " + link)

        return "\n\n".join(results) if results else "未找到结果"

    except Exception as e:
        return "SerpAPI 搜索失败: " + str(e)


async def _search_tavily(query: str, api_key: str) -> str:
    """Tavily 搜索（需要 API Key）"""
    if not api_key:
        return "请先配置 Tavily API Key"
    try:
        url = "https://api.tavily.com/search"
        payload = {"api_key": api_key, "query": query, "max_results": 5}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()

        results = []
        for item in data.get("results", []):
            title = item.get("title", "")
            content = item.get("content", "")[:200]
            url = item.get("url", "")
            results.append(title + "\n  " + content + "\n  " + url)

        return "\n\n".join(results) if results else "未找到结果"

    except Exception as e:
        return "Tavily 搜索失败: " + str(e)


async def _search_bing(query: str, api_key: str) -> str:
    """Bing Search API（需要 API Key）"""
    if not api_key:
        return "请先配置 Bing API Key"
    try:
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {"q": query, "count": 5, "mkt": "zh-CN"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            data = resp.json()

        results = []
        for item in data.get("webPages", {}).get("value", [])[:5]:
            name = item.get("name", "")
            snippet = item.get("snippet", "")
            url = item.get("url", "")
            results.append(name + "\n  " + snippet + "\n  " + url)

        return "\n\n".join(results) if results else "未找到结果"

    except Exception as e:
        return "Bing 搜索失败: " + str(e)
