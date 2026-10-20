"""
网页内容提取工具
访问URL并提取可读文本内容，支持分段续读
使用 trafilatura（可选依赖）智能提取正文，降级为 HTML 解析
"""
import re
import logging
import httpx

logger = logging.getLogger(__name__)

# 尝试导入 trafilatura（可选）
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False
    logger.info("trafilatura 未安装，使用 HTML 解析降级方案")

WEB_EXTRACT_DEFINITION = {
    "type": "function",
    "function": {
        "name": "web_extract",
        "description": "读取网页内容，提取可读文本。当需要查看搜索到的链接、阅读文章、查看文档时使用。如果内容较长会自动分段，可通过 offset 参数继续读取后续内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要读取的网页 URL"},
                "offset": {"type": "integer", "description": "读取起始位置", "default": 0},
            },
            "required": ["url"],
        },
    },
}

CHUNK_SIZE = 50000
REQUEST_TIMEOUT = 30.0
MAX_TOTAL = 500000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


async def web_extract(url: str, offset: int = 0) -> str:
    """提取网页可读文本内容"""
    try:
        if offset < 0:
            offset = 0
        if offset > MAX_TOTAL:
            return f"已达到最大读取限制（{MAX_TOTAL}字符）"

        text = await _fetch_and_extract(url)
        if not text.strip():
            return "未能从该网页提取到可读内容"

        total_len = len(text)
        chunk = text[offset:offset + CHUNK_SIZE]
        lines = [f"页面内容（共{total_len}字符）:", "", chunk]

        next_offset = offset + CHUNK_SIZE
        if next_offset < total_len:
            remaining = total_len - next_offset
            lines.append("")
            lines.append(f"...（还有约{remaining}字符，可设置 offset={next_offset} 继续读取）")

        return "\n".join(lines)

    except httpx.TimeoutException:
        return f"访问超时：{url}"
    except httpx.HTTPStatusError as e:
        return f"HTTP {e.response.status_code}：{url}"
    except Exception as e:
        return f"读取失败：{str(e)}"


async def _fetch_and_extract(url: str) -> str:
    """获取网页并提取可读文本"""
    if HAS_TRAFILATURA:
        try:
            html = await _fetch_html(url)
            text = trafilatura.extract(html, include_comments=False, include_tables=True)
            if text and text.strip():
                return text.strip()
        except Exception as e:
            logger.warning(f"trafilatura 降级: {e}")

    html = await _fetch_html(url)
    return _extract_readable_text(html)


async def _fetch_html(url: str) -> str:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.text


def _extract_readable_text(html: str) -> str:
    """从 HTML 提取可读文本（降级方案）"""
    html = re.sub(r'<(script|style|nav|footer)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'</(p|div|h[1-6]|li|tr|blockquote|pre)>', '\n', html)
    text = re.sub(r'<[^>]+>', '', html)
    for e, c in [('&nbsp;',' '),('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#39;',"'")]:
        text = text.replace(e, c)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
