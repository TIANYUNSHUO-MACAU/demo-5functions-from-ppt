# 联网搜索服务 - 为简历优化检索同类简历范例 / 写法最佳实践
# 默认对接 Tavily（https://tavily.com，有免费额度），OpenAI 兼容式的简单 HTTP 调用。
#
# 合规说明：不直连、不爬取 LinkedIn 等需登录的站点；仅通过搜索 API 获取公开网页内容，
# 作为大模型改写简历时的"写作参考"。

import os
import httpx

from services.ai_service import _parse_env_file

# 与 ai_service 共用同一个 .env 路径
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)

# Tavily 检索端点；如需换 SerpAPI 等，可通过 SEARCH_API_BASE 覆盖
DEFAULT_TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _get_search_key() -> str:
    """优先读环境变量（运行时由配置面板写入），回退解析 .env 文件。"""
    key = os.environ.get("SEARCH_API_KEY", "").strip()
    if key:
        return key
    return (_parse_env_file(_ENV_PATH).get("SEARCH_API_KEY", "") or "").strip()


def search_resume_references(query: str, max_results: int = 5) -> list:
    """检索与目标岗位相关的简历范例 / 写法参考。

    :param query: 目标岗位 + 行业关键词（如 "前端工程师 互联网"）
    :param max_results: 返回条数
    :return: [{"title", "url", "content"}]；无 Key 或任何异常时返回 []（让上层回退）
    """
    key = _get_search_key()
    if not key or not (query or "").strip():
        return []

    endpoint = (
        os.environ.get("SEARCH_API_BASE", "").strip() or DEFAULT_TAVILY_ENDPOINT
    )
    # 在岗位关键词后补充检索意图，提升对"简历范例/写法"的召回
    search_query = f"{query.strip()} 简历 范例 项目经历 技能 写法"

    try:
        resp = httpx.post(
            endpoint,
            json={
                "api_key": key,
                "query": search_query,
                "max_results": max_results,
                "search_depth": "basic",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # 网络错误 / 超时 / Key 失效 / 解析失败 —— 一律静默回退
        return []

    results = []
    for item in (data.get("results") or [])[:max_results]:
        content = (item.get("content") or "").strip()
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip() or url
        if not content and not url:
            continue
        results.append({"title": title, "url": url, "content": content})
    return results
