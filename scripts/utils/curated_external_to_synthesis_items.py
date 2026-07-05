"""Preview adapter: curated external candidates → synthesis display-only items.

Reads curated external candidate JSONL/JSON exports, keeps only preview-safe
candidates, and emits display-only synthesis items that are explicitly **not**
fed into canonical Knowledge / scoring / risk paths.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from .curated_external_candidate_discovery import (
        _has_unsafe_eligibility,
        _read_json_or_jsonl,
    )
else:
    from curated_external_candidate_discovery import (
        _has_unsafe_eligibility,
        _read_json_or_jsonl,
    )


SOURCE_TYPE = "curated_external_analysis"
VERIFICATION_STATUS = "professional_observation"
QUALITY_ACTION = "preview_only"

TOPIC_ORDER = [
    "industry_logic",
    "commercialization",
    "product_roadmap",
    "cycle_price",
    "earnings_context",
    "certification_policy",
    "capital_market_context",
    "other_observation",
]

_TOPIC_SET = set(TOPIC_ORDER)

_SOURCE_KIND_TO_TOPIC = {
    "wechat_high_quality_analysis": "industry_logic",
    "wechat_customer_order_or_design_win": "commercialization",
    "wechat_capacity_supply_chain_signal": "commercialization",
    "wechat_industry_cycle_price_signal": "cycle_price",
    "wechat_earnings_financial_context": "earnings_context",
    "wechat_certification_policy_standard": "certification_policy",
    "wechat_product_signal": "product_roadmap",
    "wechat_product_or_event_signal": "product_roadmap",
    "wechat_capital_market_context": "capital_market_context",
}


def map_source_kind_to_topic(source_kind: str, raw_item: Dict[str, Any]) -> str:
    """Map a candidate source_kind to a synthesis topic.

    Explicit `topic`/`category` fields on the raw item take precedence.
    Known WeChat source kinds map to the required taxonomy.
    Everything else defaults to `industry_logic` so that Jina/local curated
    long-form material lands in the industry-logic bucket by default.
    """
    for key in ("topic", "category"):
        value = str(raw_item.get(key) or "").strip()
        if value and value in _TOPIC_SET:
            return value
    return _SOURCE_KIND_TO_TOPIC.get(source_kind, "industry_logic")


def build_curated_external_synthesis_items(
    candidate_jsonl_path: str | Path,
    *,
    stock_name: str = "",
    max_items: int = 0,
) -> Dict[str, Any]:
    """Convert a curated external candidate JSONL/JSON into display-only synthesis items."""
    raw_items = _read_candidates(candidate_jsonl_path)

    items: List[Dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        if _has_unsafe_eligibility(raw):
            continue
        if str(raw.get("quality_action") or "") != QUALITY_ACTION:
            continue
        item = _to_display_item(raw)
        if item:
            items.append(item)

    items = _sort_items(items)
    if max_items and max_items > 0:
        items = items[:max_items]

    counts = dict(Counter(item["topic"] for item in items))
    return {
        "status": "ok" if items else "empty",
        "stock_name": stock_name,
        "items": items,
        "counts": counts,
    }


def build_curated_external_synthesis_markdown(summary: Dict[str, Any]) -> str:
    """Render a Markdown preview of display-only synthesis items grouped by topic."""
    stock_name = summary.get("stock_name") or ""
    items = summary.get("items", []) or []
    counts = summary.get("counts", {}) or {}

    lines = [
        f"# Curated External → Synthesis Display Preview：{stock_name}" if stock_name else "# Curated External → Synthesis Display Preview",
        "",
        "> 进入 synthesis 前的材料预览（display-only）。",
        "> 不写 Knowledge，不接 canonical synthesis，不进入评分/风险/最终建议。",
        "> 以下条目仅供展示，不是事实确认。",
        "",
        "## Summary",
        "",
        f"- status: `{summary.get('status', '')}`",
        f"- items: `{len(items)}`",
    ]
    for topic in TOPIC_ORDER:
        if topic in counts:
            lines.append(f"- {topic}: `{counts[topic]}`")
    lines.append("")

    if items:
        lines.extend(["## Display Items", ""])
        for index, item in enumerate(items, start=1):
            lines.extend(_render_item_lines(index, item))

    return "\n".join(lines).rstrip() + "\n"


def _to_display_item(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    source_kind = str(raw.get("source_kind") or raw.get("source_type") or "").strip()
    if not source_kind:
        return None

    topic = map_source_kind_to_topic(source_kind, raw)
    title = _clean_text(str(raw.get("title") or raw.get("url") or "curated-external"))
    content = _clean_text(str(raw.get("content") or raw.get("content_preview") or ""))
    url = str(raw.get("url") or "").strip()
    account = _clean_text(str(raw.get("account") or ""))
    publish_time = str(raw.get("publish_time") or "").strip()
    source_ref = _source_ref(raw, source_kind=source_kind, title=title, url=url)

    return {
        "source_type": SOURCE_TYPE,
        "source_kind": source_kind,
        "verification_status": VERIFICATION_STATUS,
        "knowledge_eligible": False,
        "synthesis_eligible": True,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "quality_action": QUALITY_ACTION,
        "title": title,
        "content": content,
        "url": url,
        "account": account,
        "publish_time": publish_time,
        "source_ref": source_ref,
        "topic": topic,
    }


def _sort_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(item: Dict[str, Any]) -> tuple[int, int, str]:
        topic = item.get("topic", "")
        topic_index = TOPIC_ORDER.index(topic) if topic in _TOPIC_SET else len(TOPIC_ORDER)
        score = 0
        try:
            score = int(item.get("discovery_score") or 0)
        except (TypeError, ValueError):
            score = 0
        publish_date = _date_sort_value(str(item.get("publish_time") or ""))
        return (topic_index, -score, publish_date)

    return sorted(items, key=sort_key)


def _source_ref(raw: Dict[str, Any], *, source_kind: str, title: str, url: str) -> str:
    existing = str(raw.get("source_ref") or "").strip()
    if existing:
        return existing
    if url:
        return url
    path = str(raw.get("path") or "").strip()
    if path:
        return path
    return f"{source_kind}:{title}"


def _date_sort_value(value: str) -> int:
    try:
        return -date.fromisoformat(value[:10]).toordinal()
    except ValueError:
        return 0


def _render_item_lines(index: int, item: Dict[str, Any]) -> List[str]:
    lines = [
        f"### {index}. {item.get('title', '')}",
        "",
        f"- topic: `{item.get('topic', '')}`",
        f"- source_kind: `{item.get('source_kind', '')}`",
        f"- source_type: `{item.get('source_type', '')}`",
        f"- verification_status: `{item.get('verification_status', '')}`",
        f"- synthesis_display_only: `{str(bool(item.get('synthesis_display_only'))).lower()}`",
        f"- knowledge_eligible: `{str(bool(item.get('knowledge_eligible'))).lower()}`",
        f"- scoring_eligible: `{str(bool(item.get('scoring_eligible'))).lower()}`",
        f"- risk_score_eligible: `{str(bool(item.get('risk_score_eligible'))).lower()}`",
    ]
    if item.get("account"):
        lines.append(f"- account: `{item.get('account')}`")
    if item.get("publish_time"):
        lines.append(f"- publish_time: `{item.get('publish_time')}`")
    if item.get("url"):
        lines.append(f"- url: {item.get('url')}")
    if item.get("source_ref"):
        lines.append(f"- source_ref: `{item.get('source_ref')}`")
    if item.get("content"):
        lines.extend(["", item.get("content", ""), ""])
    else:
        lines.append("")
    return lines


def _read_candidates(path: str | Path) -> List[Any]:
    candidate_path = Path(path)
    if not candidate_path.exists():
        return []
    payload = _read_json_or_jsonl(candidate_path)
    if isinstance(payload, dict):
        return payload.get("items", []) if isinstance(payload.get("items"), list) else []
    if isinstance(payload, list):
        return payload
    return []


def _clean_text(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", str(text or "")).strip()
