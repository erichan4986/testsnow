"""Build preview-only source packets from cached Xueqiu/Zhihu report inputs."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

try:
    from .curated_external_full_body_viewpoint_claims import (
        SOURCE_PACKET_SCHEMA_VERSION,
        normalized_hash,
    )
except ImportError:
    from curated_external_full_body_viewpoint_claims import (
        SOURCE_PACKET_SCHEMA_VERSION,
        normalized_hash,
    )


def build_social_source_packets(
    report_input_json: str | Path,
    *,
    stock_name: str,
    max_sources: int | None = None,
    max_source_chars: int | None = None,
    min_content_chars: int = 180,
) -> List[Dict[str, Any]]:
    """Convert cached report_input social materials to display-only source packets."""
    payload = _read_json(report_input_json)
    candidates = []
    candidates.extend(_xueqiu_like_candidates(payload, stock_name))
    candidates.extend(_zhihu_candidates(payload, stock_name))

    packets: List[Dict[str, Any]] = []
    seen_refs: Set[str] = set()
    for item in candidates:
        source_ref = str(item.get("source_ref") or item.get("url") or "").strip()
        if not source_ref or source_ref in seen_refs:
            continue
        seen_refs.add(source_ref)

        content = _clean_social_content(item.get("content"))
        if len(content) < min_content_chars:
            continue
        if max_source_chars and len(content) > max_source_chars:
            content = content[:max_source_chars]

        source_kind = str(item.get("source_kind") or "social").strip()
        profile = _social_source_profile(item, source_kind)
        packet = {
            "schema_version": SOURCE_PACKET_SCHEMA_VERSION,
            "source_id": _source_id(source_kind, source_ref),
            "stock_name": stock_name,
            "title": _normalize_text(item.get("title")),
            "account": _normalize_text(item.get("account") or item.get("author")),
            "publish_time": _normalize_text(item.get("publish_time")),
            "source_kind": source_kind,
            "source_platform": _normalize_text(item.get("source_platform")),
            "source_detail_type": profile["source_detail_type"],
            "source_label": profile["source_label"],
            "source_credit": profile["source_credit"],
            "source_ref": source_ref,
            "source_url": str(item.get("url") or source_ref),
            "content": content,
            "source_content_hash": normalized_hash(content),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
            "synthesis_eligible": True,
            "synthesis_display_only": True,
            "verification_status": "professional_observation",
        }
        packets.append(packet)
        if max_sources and len(packets) >= max_sources:
            break

    return packets


def _read_json(path: str | Path) -> Dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _xueqiu_like_candidates(payload: Dict[str, Any], stock_name: str) -> List[Dict[str, Any]]:
    posts = (payload.get("stocks_data") or {}).get(stock_name) or []
    if not isinstance(posts, list):
        return []
    candidates = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        source = str(post.get("source") or "xueqiu").strip().lower()
        source_kind = "social_xueqiu" if source == "xueqiu" else f"social_{source or 'community'}"
        candidates.append(
            {
                "title": post.get("title") or "",
                "content": post.get("content") or post.get("content_text") or "",
                "url": post.get("url") or "",
                "author": post.get("author") or post.get("user") or "",
                "publish_time": post.get("time") or post.get("publish_time") or "",
                "source_kind": source_kind,
                "source_platform": source or "xueqiu",
                "source_detail_type": post.get("source_detail_type") or "",
            }
        )
    return candidates


def _zhihu_candidates(payload: Dict[str, Any], stock_name: str) -> List[Dict[str, Any]]:
    zhihu = ((payload.get("raw_data") or {}).get(stock_name) or {}).get("zhihu") or {}
    items = zhihu.get("report_items") or []
    if not isinstance(items, list):
        return []
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidates.append(
            {
                "title": item.get("title") or "",
                "content": item.get("content") or item.get("content_text") or item.get("summary") or "",
                "url": item.get("url") or "",
                "author": item.get("author_name") or item.get("author") or "",
                "publish_time": _format_zhihu_time(item.get("edit_time") or item.get("publish_time")),
                "source_kind": "social_zhihu",
                "source_platform": "zhihu",
            }
        )
    return candidates


def _format_zhihu_time(value: Any) -> str:
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""
    return str(value or "")


def _clean_social_content(value: Any) -> str:
    text = _normalize_text(value)
    noise_terms = [
        "扫码下载雪球App",
        "购买雪球币",
        "账号余额",
        "可到钱包中进行查看",
        "展开",
    ]
    for term in noise_terms:
        text = text.replace(term, " ")
    text = re.sub(r"\$([^$]{1,40})\$", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    return _normalize_text(text)


def _social_source_profile(item: Dict[str, Any], source_kind: str) -> Dict[str, Any]:
    title = _normalize_text(item.get("title"))
    content = _normalize_text(item.get("content"))
    marker = f"{source_kind} {title} {content}".lower()
    if "social_xueqiu" in marker or "xueqiu" in marker:
        explicit_detail_type = _normalize_text(item.get("source_detail_type"))
        if explicit_detail_type == "xueqiu_column":
            return {
                "source_detail_type": "xueqiu_column",
                "source_label": "雪球专栏观察",
                "source_credit": 55,
            }
        if explicit_detail_type == "xueqiu_reply":
            return {
                "source_detail_type": "xueqiu_reply",
                "source_label": "雪球评论观察",
                "source_credit": 45,
            }
        if "回复@" in marker or "回复 @" in marker:
            return {
                "source_detail_type": "xueqiu_reply",
                "source_label": "雪球评论观察",
                "source_credit": 45,
            }
        if "专栏" in marker:
            return {
                "source_detail_type": "xueqiu_column",
                "source_label": "雪球专栏观察",
                "source_credit": 55,
            }
        return {
            "source_detail_type": "xueqiu_post",
            "source_label": "雪球精选观察",
            "source_credit": 50,
        }
    if "social_zhihu" in marker or "zhihu" in marker:
        return {
            "source_detail_type": "zhihu_article",
            "source_label": "知乎精选观察",
            "source_credit": 55,
        }
    if "eastmoney" in marker or "东方财富" in marker:
        return {
            "source_detail_type": "eastmoney_post",
            "source_label": "东方财富精选观察",
            "source_credit": 50,
        }
    return {
        "source_detail_type": "social_post",
        "source_label": "外部精选观察",
        "source_credit": 50,
    }


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _source_id(source_kind: str, source_ref: str) -> str:
    return f"social-source:{source_kind}:{normalized_hash(source_ref)[:16]}"
