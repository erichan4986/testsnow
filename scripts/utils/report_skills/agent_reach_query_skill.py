"""Agent-Reach deterministic query generation skill (Phase 0).

Phase 0 targets:
- rss (default)
- web (only when explicit URLs are provided)

Detection-only platforms (youtube, exa_search, wechat) are never targeted by default.
Unsupported platforms (twitter, reddit, bilibili, xiaohongshu, etc.) are removed.
"""

import os
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
else:
    from skill_pipeline import skill, SkillContext


# Phase 0B: empty default RSS feeds. Users must provide feeds via ctx override.
_DEFAULT_RSS_FEEDS: List[str] = []

# 竞品映射（预留，后续可从配置扩展）
_COMPETITOR_MAP: dict = {}

# Common suffixes to strip for short-name derivation.
_SHORT_NAME_SUFFIXES = ["智能", "科技", "股份", "集团", "公司", "电子", "通信"]


def _derive_short_name(stock_name: str) -> str:
    """Derive a safe short-name variant by stripping common suffixes.

    Returns empty string if the result would be too short (<=1 char).
    """
    if not stock_name:
        return ""
    short = stock_name
    for suffix in _SHORT_NAME_SUFFIXES:
        if short.endswith(suffix):
            short = short[: -len(suffix)]
            break
    if len(short) <= 1:
        return ""
    return short


def _build_rss_filter_terms(
    stock_name: str,
    code: str = "",
    competitors: Optional[List[str]] = None,
    override_terms: Optional[List[str]] = None,
) -> List[str]:
    """Build conservative filter terms for RSS entry matching.

    Identity-only: stock_name, code, competitors, short-name variant.
    Industry keywords are NOT injected automatically (Phase 0B).
    """
    if override_terms is not None:
        return [t for t in override_terms if t]

    terms = []
    if stock_name:
        terms.append(stock_name)
        short = _derive_short_name(stock_name)
        if short and short not in terms:
            terms.append(short)
    if code:
        terms.append(code)
    if competitors:
        for comp in competitors:
            if comp and comp not in terms:
                terms.append(comp)
    return [term for term in terms if term]


def generate_agent_reach_queries(
    stock_name: str,
    code: str = "",
    competitors: List[str] = None,
    ctx: Optional[SkillContext] = None,
) -> List[dict]:
    """Produce deterministic search queries without env/LLM/subprocess calls.

    Args:
        stock_name: 股票名称，如 "黑芝麻智能"
        code: 股票代码，如 "02533"
        competitors: 竞争对手列表，可选
        ctx: Optional SkillContext for feed/URL overrides (backward-compatible).

    Returns:
        list[dict]，每个 dict 包含 query, target_platforms, rationale 及平台特定字段
    """
    queries = []

    # --- RSS query (default Phase 0 target) ---
    feeds = _DEFAULT_RSS_FEEDS[:]
    filter_override = None
    if ctx is not None:
        override_feeds = ctx.get("agent_reach_rss_feeds")
        if override_feeds:
            feeds = override_feeds
        filter_override = ctx.get("agent_reach_rss_filter_terms")

    filter_terms = _build_rss_filter_terms(stock_name, code, competitors, override_terms=filter_override)

    # Only generate RSS query if feeds are provided and filter terms are non-empty.
    if feeds and filter_terms:
        queries.append(
            {
                "query": "rss_poll",
                "target_platforms": ["rss"],
                "rationale": "行业 RSS 订阅",
                "rss_feeds": feeds,
                "rss_limit": 5,
                "rss_filter_terms": filter_terms,
            }
        )

    # --- Web query (only when URLs are explicitly provided) ---
    web_urls = []
    official_domains = []
    if ctx is not None:
        web_urls = ctx.get("agent_reach_urls", []) or ctx.get("agent_reach_web_urls", [])
        official_domains = ctx.get("agent_reach_official_domains", []) or []

    if web_urls:
        query_spec = {
            "query": "web_read",
            "target_platforms": ["web"],
            "rationale": "读取已知网页",
            "urls": web_urls,
            "timeout": 15,
            "user_provided_url": True,
        }
        if official_domains:
            query_spec["official_domains"] = official_domains
        queries.append(query_spec)

    return queries


@skill(name="agent_reach_query")
def agent_reach_query_skill(ctx: SkillContext) -> SkillContext:
    """Generate deterministic Agent-Reach search queries when enabled."""
    stock_name = ctx.get("stock_name", "")
    stock_codes = ctx.get("stock_codes", {})
    code = stock_codes.get(stock_name, "")

    env_enabled = os.environ.get("ENABLE_AGENT_REACH", "") in ("1", "true", "True")
    input_enabled = ctx.get("enable_agent_reach", False)
    agent_reach_enabled = env_enabled or input_enabled

    ctx.set("agent_reach_enabled", agent_reach_enabled)

    if not agent_reach_enabled:
        ctx.set("agent_reach_status", "disabled")
        ctx.set("search_queries", [])
        return ctx

    competitors = _COMPETITOR_MAP.get(stock_name, [])
    search_queries = generate_agent_reach_queries(stock_name, code, competitors, ctx=ctx)
    ctx.set("search_queries", search_queries)
    return ctx
