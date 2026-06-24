"""iwencai industry-research preview helpers.

This module intentionally stays metadata/snippet only. iwencai semantic search
is useful for discovering industry reports, but the results are not verified
facts and should remain display-only unless a later task adds a stronger
download + digest pipeline.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional


DEFAULT_IWENCAI_BASE_URL = "https://openapi.iwencai.com"
DEFAULT_IWENCAI_QUERIES = [
    "半导体 行业研究报告",
    "半导体 产业链 深度报告",
    "电子行业 中期策略 半导体",
    "模拟芯片 行业研究报告",
    "模拟IC 国产替代 研究报告",
    "AI芯片 行业研究报告",
    "AI算力 产业链 深度报告",
    "光模块 800G CPO 行业研究报告",
    "光通信 产业链 深度报告",
    "存储芯片 行业研究报告",
    "存储芯片 产业链 深度报告",
    "人形机器人 产业链 研究报告",
    "人形机器人 白皮书",
    "汽车芯片 行业研究报告",
    "车规芯片 产业链 深度报告",
]

_DISPLAY_ONLY_META = {
    "source_type": "industry_research",
    "source_credit": 70,
    "verification_status": "professional_observation",
    "knowledge_eligible": False,
    "report_eligible": True,
    "scoring_eligible": False,
    "risk_score_eligible": False,
}

_THEME_TERMS = [
    "半导体",
    "模拟芯片",
    "模拟IC",
    "模拟 IC",
    "模拟集成电路",
    "AI芯片",
    "AI 芯片",
    "AI算力",
    "光模块",
    "光通信",
    "硅光",
    "800G",
    "1.6T",
    "CPO",
    "存储芯片",
    "存储",
    "人形机器人",
    "具身智能",
    "机器人",
    "汽车芯片",
    "车规芯片",
    "算力",
]

_INDUSTRY_TITLE_TERMS = [
    "行业",
    "产业链",
    "策略",
    "白皮书",
    "蓝皮书",
    "深度",
    "系列",
    "周期",
    "跟踪",
    "专题",
    "点评",
    "研究报告",
    "调研报告",
    "市场发展",
    "投资价值",
    "国产替代",
    "国产化",
    "竞争格局",
    "趋势",
    "展望",
]

_LOW_VALUE_TITLE_TERMS = [
    "A股日评",
    "港股日评",
    "市场日评",
    "晨会纪要",
    "晨报",
    "早报",
]

_THEME_ALIASES = {
    "模拟芯片": ["模拟芯片", "模拟IC", "模拟 IC", "模拟集成电路"],
    "模拟IC": ["模拟芯片", "模拟IC", "模拟 IC", "模拟集成电路"],
    "AI芯片": ["AI芯片", "AI 芯片", "ASIC", "GPU", "算力芯片"],
    "AI算力": ["AI算力", "算力", "算力基建", "算力产业链"],
    "光模块": ["光模块", "光通信", "800G", "1.6T", "CPO", "硅光"],
    "光通信": ["光模块", "光通信", "800G", "1.6T", "CPO", "硅光"],
    "存储芯片": ["存储芯片", "存储", "DRAM", "NAND", "HBM"],
    "人形机器人": ["人形机器人", "具身智能"],
    "机器人": ["人形机器人", "具身智能", "机器人"],
    "汽车芯片": ["汽车芯片", "车规芯片", "车载芯片", "车规"],
    "车规芯片": ["汽车芯片", "车规芯片", "车载芯片", "车规"],
}

_STOCK_CODE_RE = re.compile(r"(?<!\d)(?:[0368]\d{5})(?!\d)|[（(][A-Z]?\d{5,6}[）)]")


def build_x_claw_headers(api_key: str, *, trace_id: Optional[str] = None) -> Dict[str, str]:
    """Build the SkillHub 2.0 headers required by iwencai report-search."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Claw-Call-Type": "normal",
        "X-Claw-Skill-Id": "report-search",
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": trace_id or secrets.token_hex(32),
    }


def fetch_iwencai_reports(
    query: str,
    *,
    api_key: str,
    base_url: str = DEFAULT_IWENCAI_BASE_URL,
    size: int = 50,
    post: Optional[Callable[..., Any]] = None,
    trace_id: Optional[str] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch raw iwencai report-search rows for one natural-language query."""
    if not api_key:
        raise RuntimeError("IWENCAI_API_KEY is required")
    if post is None:
        import requests

        post = requests.post

    endpoint = base_url.rstrip("/") + "/v1/comprehensive/search"
    payload = {
        "channels": ["report"],
        "app_id": "AIME_SKILL",
        "query": query,
        "size": int(size),
    }
    response = post(
        endpoint,
        json=payload,
        headers=build_x_claw_headers(api_key, trace_id=trace_id),
        timeout=timeout,
    )
    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code != 200:
        body = getattr(response, "text", "")
        raise RuntimeError(f"iwencai HTTP {status_code}: {str(body)[:200]}")
    data = response.json()
    if int(data.get("status_code", 0) or 0) != 0:
        raise RuntimeError(f"iwencai error: {data.get('status_msg', '')}")
    rows = data.get("data") or []
    return [row for row in rows if isinstance(row, dict)]


def _score(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _date_key(row: Dict[str, Any]) -> str:
    return str(row.get("publish_date") or row.get("publishDate") or row.get("date") or "")


def deduplicate_iwencai_reports(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate by uid, or title/date when uid is absent."""
    best: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        uid = str(row.get("uid") or "").strip()
        key = uid or f"{row.get('title', '')}|{_date_key(row)}"
        if not key:
            continue
        if key not in best or _score(row) > _score(best[key]):
            best[key] = dict(row)
    return sorted(best.values(), key=lambda row: (_date_key(row), _score(row)), reverse=True)


def _parse_extra(row: Dict[str, Any]) -> Dict[str, Any]:
    extra = row.get("extra") or {}
    if isinstance(extra, dict):
        return extra
    if isinstance(extra, str):
        try:
            parsed = json.loads(extra)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def normalize_iwencai_report(row: Dict[str, Any], *, query: str = "") -> Dict[str, Any]:
    """Return a stable subset of fields used by preview selection and Markdown."""
    extra = _parse_extra(row)
    title = _first_text(row.get("title"), row.get("name"), extra.get("title"))
    publish_date = _first_text(
        row.get("publish_date"),
        row.get("publishDate"),
        row.get("date"),
        extra.get("publish_date"),
        extra.get("publishDate"),
    )[:10]
    organization = _first_text(
        row.get("organization"),
        row.get("org_name"),
        row.get("orgSName"),
        extra.get("organization"),
        extra.get("org_name"),
        extra.get("orgSName"),
    )
    url = _first_text(row.get("url"), row.get("link"), extra.get("url"), extra.get("link"))
    summary = _first_text(
        row.get("summary"),
        row.get("snippet"),
        row.get("content"),
        row.get("abstract"),
        extra.get("summary"),
        extra.get("snippet"),
        extra.get("abstract"),
    )
    return {
        "uid": _first_text(row.get("uid"), f"{title}|{publish_date}"),
        "query": query,
        "title": title,
        "publish_date": publish_date,
        "organization": organization,
        "url": url,
        "summary": summary,
        "score": _score(row),
        **_DISPLAY_ONLY_META,
    }


def _parse_date(value: str) -> Optional[date]:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_old(publish_date: str, today: date) -> Optional[int]:
    parsed = _parse_date(publish_date)
    if parsed is None:
        return None
    return (today - parsed).days


def _query_theme_terms(query: str) -> List[str]:
    terms: List[str] = []
    for term in _THEME_TERMS:
        if term not in query:
            continue
        for alias in _THEME_ALIASES.get(term, [term]):
            if alias not in terms:
                terms.append(alias)
    return terms


def _has_theme(text: str, query: str) -> bool:
    terms = _query_theme_terms(query)
    return any(term in text for term in terms) if terms else True


def _looks_stock_specific_title(title: str) -> bool:
    return bool(_STOCK_CODE_RE.search(title))


def _classify_drop_reason(item: Dict[str, Any], *, query: str) -> str:
    title = item.get("title", "")
    summary = item.get("summary", "")
    combined = f"{title} {summary}"
    if not title:
        return "missing_title"
    if _looks_stock_specific_title(title):
        return "stock_specific_or_code_title"
    if any(term in title for term in _LOW_VALUE_TITLE_TERMS):
        return "low_value_market_roundup"
    if not _has_theme(title, query):
        return "theme_mismatch"
    if not any(term in combined for term in _INDUSTRY_TITLE_TERMS):
        return "weak_industry_title"
    return ""


def _select_with_window(
    candidates: List[Dict[str, Any]],
    *,
    today: date,
    window_days: int,
    max_items: int,
) -> List[Dict[str, Any]]:
    in_window = []
    for item in candidates:
        age = _days_old(item.get("publish_date", ""), today)
        if age is None or age < 0 or age > window_days:
            continue
        in_window.append(item)
    return sorted(
        in_window,
        key=lambda item: (item.get("publish_date", ""), float(item.get("score", 0) or 0)),
        reverse=True,
    )[:max_items]


def select_iwencai_industry_reports(
    rows: Iterable[Dict[str, Any]],
    *,
    query: str,
    today: Optional[date] = None,
    recent_days: int = 90,
    fallback_days: int = 180,
    min_recent_items: int = 3,
    max_items: int = 5,
) -> Dict[str, Any]:
    """Select display-only industry reports with deterministic filters."""
    today = today or date.today()
    normalized = [normalize_iwencai_report(row, query=query) for row in rows]
    candidates: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    for item in normalized:
        reason = _classify_drop_reason(item, query=query)
        if reason:
            dropped.append({**item, "drop_reason": reason})
            continue
        candidates.append({**item, "quality_action": "display_only"})

    selected = _select_with_window(candidates, today=today, window_days=recent_days, max_items=max_items)
    window_days = recent_days
    if len(selected) < min_recent_items and fallback_days > recent_days:
        selected = _select_with_window(candidates, today=today, window_days=fallback_days, max_items=max_items)
        window_days = fallback_days

    return {
        "query": query,
        "window_days": window_days,
        "selected": selected,
        "dropped": dropped,
    }


def build_iwencai_industry_preview(
    *,
    queries: Iterable[str] = DEFAULT_IWENCAI_QUERIES,
    api_key: str,
    base_url: str = DEFAULT_IWENCAI_BASE_URL,
    size: int = 50,
    today: Optional[date] = None,
    recent_days: int = 90,
    fallback_days: int = 180,
    min_recent_items: int = 3,
    max_items_per_query: int = 5,
    post: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Fetch, dedupe, select, and summarize iwencai industry report metadata."""
    query_summaries = []
    for query in queries:
        raw_rows = fetch_iwencai_reports(
            query,
            api_key=api_key,
            base_url=base_url,
            size=size,
            post=post,
        )
        deduped = deduplicate_iwencai_reports(raw_rows)
        selected = select_iwencai_industry_reports(
            deduped,
            query=query,
            today=today,
            recent_days=recent_days,
            fallback_days=fallback_days,
            min_recent_items=min_recent_items,
            max_items=max_items_per_query,
        )
        query_summaries.append(
            {
                "query": query,
                "raw_count": len(raw_rows),
                "dedup_count": len(deduped),
                **selected,
            }
        )
    return {
        "source": "iwencai",
        "source_type": "industry_research",
        "display_only": True,
        "queries": query_summaries,
    }


def build_iwencai_industry_preview_markdown(summary: Dict[str, Any]) -> str:
    """Render a deterministic Markdown preview for manual review."""
    lines = [
        "# iwencai 行业研报 Preview",
        "",
        "- source_type: `industry_research`",
        "- source_credit: `70`",
        "- verification_status: `professional_observation`",
        "- knowledge_eligible: `false`",
        "- report_eligible: `true`",
        "- scoring_eligible: `false`",
        "- risk_score_eligible: `false`",
        "",
    ]

    for query_summary in summary.get("queries", []):
        query = query_summary.get("query", "")
        lines.extend(
            [
                f"## {query}",
                "",
                f"- raw: `{query_summary.get('raw_count', 0)}`",
                f"- dedup: `{query_summary.get('dedup_count', 0)}`",
                f"- selected_window_days: `{query_summary.get('window_days', '')}`",
                f"- selected: `{len(query_summary.get('selected', []) or [])}`",
                f"- dropped: `{len(query_summary.get('dropped', []) or [])}`",
                "",
            ]
        )
        for index, item in enumerate(query_summary.get("selected", []) or [], start=1):
            lines.extend(
                [
                    f"### {index}. {item.get('title', '')}",
                    "",
                    f"- 日期: `{item.get('publish_date', '')}`",
                    f"- 机构: `{item.get('organization', '')}`",
                    f"- score: `{item.get('score', 0)}`",
                    f"- action: `{item.get('quality_action', 'display_only')}`",
                    f"- url: {item.get('url', '')}",
                    "",
                    (item.get("summary") or "").strip(),
                    "",
                ]
            )
        dropped = query_summary.get("dropped", []) or []
        if dropped:
            lines.extend(["#### dropped examples", ""])
            for item in dropped[:5]:
                lines.append(f"- `{item.get('drop_reason', '')}`: {item.get('title', '')}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
