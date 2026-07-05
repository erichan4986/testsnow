"""Deterministic planning helpers for safe Xueqiu detail-page selection.

This module contains no Playwright or network code. It only decides which
already-collected list posts should be attempted in a bounded detail fetch.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

try:
    from .content_quality import content_score
except ImportError:
    from content_quality import content_score

try:
    from .curated_external_full_body_viewpoint_claims import normalized_hash
except ImportError:
    from curated_external_full_body_viewpoint_claims import normalized_hash


GENERIC_BUCKETS: Dict[str, Sequence[str]] = {
    "valuation": (
        "估值",
        "PE",
        "PS",
        "市值",
        "合理估值",
        "目标价",
        "A/H",
        "AH",
        "港股",
        "折价",
        "可比公司",
        "紫光国微",
    ),
    "earnings": (
        "净利",
        "利润",
        "营收",
        "毛利率",
        "半年报",
        "一季报",
        "Q1",
        "Q2",
        "业绩快报",
        "预告",
        "归母",
    ),
    "risk": (
        "风险",
        "价格战",
        "订单不及预期",
        "存货跌价",
        "竞争",
        "下修",
        "亏损",
        "不及预期",
    ),
    "catalyst": (
        "政策",
        "中标",
        "订单",
        "客户",
        "产能",
        "价格上行",
        "补贴",
        "并购",
        "导入",
    ),
    "industry_trend": (
        "行业景气",
        "周期",
        "供需",
        "国产替代",
        "产业链",
        "竞争格局",
        "涨价",
    ),
}


EXTENSION_BUCKETS: Dict[str, Dict[str, Sequence[str]]] = {
    "semiconductor_product": {
        "semiconductor_product": (
            "FPGA",
            "FPAI",
            "MCU",
            "EEPROM",
            "NAND",
            "存储",
            "PSoC",
            "RFSoC",
            "芯片",
        )
    },
    "aerospace": {
        "aerospace": (
            "航天",
            "卫星",
            "G60",
            "千帆",
            "星链",
            "抗辐照",
            "宇航",
        )
    },
}

DEFAULT_CONFIG = {
    "first_batch_size": 15,
    "refill_batch_size": 8,
    "max_detail_pages_total": 25,
    "min_usable_details": 5,
    "max_drop_rate": 0.40,
    "min_topic_coverage": 2,
    "enabled_extension_buckets": (),
    "required_detail_topics": (),
    "min_detail_content_chars": 60,
}

NON_TOPIC_BUCKETS = {"sentiment_only"}


def classify_detail_topics(post: Dict[str, Any], config: Dict[str, Any] | None = None) -> List[str]:
    """Infer normalized detail-topic buckets from list or detail text."""
    cfg = _config(config)
    text = _post_text(post).lower()
    buckets: List[str] = []
    for bucket, keywords in GENERIC_BUCKETS.items():
        if _matches_any(text, keywords):
            buckets.append(bucket)
    for extension_name in cfg["enabled_extension_buckets"]:
        for bucket, keywords in EXTENSION_BUCKETS.get(str(extension_name), {}).items():
            if _matches_any(text, keywords):
                buckets.append(bucket)
    if not buckets and _looks_sentiment_only(text):
        buckets.append("sentiment_only")
    return _dedupe_preserve_order(buckets)


def build_detail_plan(posts: List[Dict[str, Any]], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build the first bounded detail-fetch batch from cached list posts."""
    cfg = _config(config)
    candidates = [_candidate(post, cfg) for post in posts if _has_url(post)]
    candidates = _dedupe_candidates(candidates)
    candidates.sort(key=lambda item: item["detail_score"], reverse=True)

    populated_buckets = _populated_non_sentiment_buckets(candidates)
    effective_min_topic_coverage = _effective_topic_coverage(cfg, populated_buckets)
    first_batch = _select_with_topic_quota(
        candidates,
        batch_size=cfg["first_batch_size"],
        preferred_buckets=populated_buckets,
    )

    return {
        "first_batch": first_batch,
        "candidates": candidates,
        "audit": {
            "populated_topic_buckets": populated_buckets,
            "effective_min_topic_coverage": effective_min_topic_coverage,
            "first_batch_size": len(first_batch),
            "candidate_count": len(candidates),
        },
    }


def evaluate_detail_attempts(
    attempts: List[Dict[str, Any]],
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Classify attempted detail pages and decide whether one refill is needed."""
    cfg = _config(config)
    usable: List[Dict[str, Any]] = []
    drop_reasons: Dict[str, str] = {}
    seen_content_hashes: set[str] = set()
    duplicate_count = 0

    for attempt in attempts:
        url = str(attempt.get("url") or "")
        status = str(attempt.get("status") or "").strip().lower()
        explicit_drop = str(attempt.get("drop_reason") or "").strip()
        content = _normalize(attempt.get("content"))
        if status == "usable":
            reason = ""
        elif explicit_drop:
            reason = explicit_drop
        elif len(content) < cfg["min_detail_content_chars"]:
            reason = "too_short"
        elif _looks_sentiment_only(content):
            reason = "sentiment_only"
        else:
            reason = ""

        if reason:
            drop_reasons[url] = reason
            continue

        content_key = _content_key(attempt)
        if content_key in seen_content_hashes:
            duplicate_count += 1
            drop_reasons[url] = "duplicate"
            continue
        seen_content_hashes.add(content_key)

        enriched = dict(attempt)
        enriched["status"] = "usable"
        enriched["topics"] = _attempt_topics(enriched, cfg)
        enriched["content_hash"] = content_key
        usable.append(enriched)

    attempted_count = len(attempts)
    dropped_count = attempted_count - len(usable)
    drop_rate = dropped_count / attempted_count if attempted_count else 0.0
    covered_topics = _covered_topics(usable)

    populated = cfg.get("populated_non_sentiment_candidate_buckets") or covered_topics
    effective_min_topic_coverage = _effective_topic_coverage(cfg, list(populated))
    required_topics = [
        topic
        for topic in cfg["required_detail_topics"]
        if topic in set(populated) and topic not in set(covered_topics)
    ]
    missing_topics = [
        topic
        for topic in list(populated)
        if topic not in set(covered_topics) and topic not in NON_TOPIC_BUCKETS
    ]

    refill_reasons: List[str] = []
    if len(usable) < cfg["min_usable_details"]:
        refill_reasons.append("usable_below_minimum")
    if attempted_count and drop_rate > cfg["max_drop_rate"]:
        refill_reasons.append("drop_rate_above_threshold")
    if len(covered_topics) < effective_min_topic_coverage:
        refill_reasons.append("topic_coverage_below_minimum")
    if required_topics:
        refill_reasons.append("required_topics_missing")

    return {
        "attempted_count": attempted_count,
        "usable_count": len(usable),
        "duplicate_count": duplicate_count,
        "dropped_count": dropped_count,
        "drop_rate": drop_rate,
        "covered_topic_buckets": covered_topics,
        "effective_min_topic_coverage": effective_min_topic_coverage,
        "missing_topics": missing_topics,
        "drop_reasons": drop_reasons,
        "usable_attempts": usable,
        "should_refill": bool(refill_reasons),
        "refill_reasons": refill_reasons,
    }


def build_refill_plan(
    candidates: List[Dict[str, Any]],
    attempts: List[Dict[str, Any]],
    evaluation: Dict[str, Any],
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the single allowed refill batch from remaining candidates."""
    cfg = _config(config)
    if cfg.get("refill_already_used") or not evaluation.get("should_refill"):
        return {"should_refill": False, "refill_batch": [], "audit": {"reason": "not_needed_or_already_used"}}

    attempted_urls = {str(attempt.get("url") or "") for attempt in attempts}
    attempted_hashes = {_content_key(attempt) for attempt in attempts if _normalize(attempt.get("content"))}
    remaining_capacity = max(0, cfg["max_detail_pages_total"] - len(attempts))
    batch_size = min(cfg["refill_batch_size"], remaining_capacity)
    if batch_size <= 0:
        return {"should_refill": False, "refill_batch": [], "audit": {"reason": "cap_reached", "remaining_capacity": 0}}

    missing_topics = [topic for topic in evaluation.get("missing_topics", []) if topic not in NON_TOPIC_BUCKETS]
    remaining = []
    for candidate in candidates:
        if candidate.get("url") in attempted_urls:
            continue
        if candidate.get("dedupe_key") in attempted_hashes:
            continue
        if _non_sentiment_topics(candidate):
            remaining.append(candidate)

    selected = _select_with_topic_quota(
        remaining,
        batch_size=batch_size,
        preferred_buckets=missing_topics or _populated_non_sentiment_buckets(remaining),
    )

    return {
        "should_refill": bool(selected),
        "refill_batch": selected,
        "audit": {
            "remaining_capacity": remaining_capacity,
            "refill_batch_size": len(selected),
            "missing_topics": missing_topics,
            "refill_reasons": list(evaluation.get("refill_reasons") or []),
        },
    }


def to_stocks_data_posts(attempts: List[Dict[str, Any]], stock_name: str) -> Dict[str, Any]:
    """Convert usable detail attempts into report_input stocks_data shape."""
    posts: List[Dict[str, Any]] = []
    for attempt in attempts:
        content = _normalize(attempt.get("content"))
        if not content:
            continue
        topics = list(attempt.get("topics") or attempt.get("detail_topic_buckets") or [])
        posts.append(
            {
                "title": _normalize(attempt.get("title")),
                "content": content,
                "url": str(attempt.get("url") or ""),
                "author": _normalize(attempt.get("author")),
                "time": _normalize(attempt.get("publish_time") or attempt.get("time")),
                "source": "xueqiu",
                "_track": "featured",
                "source_detail_type": attempt.get("source_detail_type") or "xueqiu_column",
                "selection_audit": {
                    "batch": attempt.get("attempt_batch") or attempt.get("batch") or "first",
                    "topics": topics,
                    "content_hash": attempt.get("content_hash") or _content_key(attempt),
                },
            }
        )
    return {"stocks_data": {stock_name: posts}}


def _candidate(post: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(post)
    topics = classify_detail_topics(result, cfg)
    result["detail_topic_buckets"] = topics
    result["detail_candidate_reason"] = _candidate_reasons(result, topics)
    result["dedupe_key"] = _content_key(result)
    result["detail_score"] = float(content_score(result)) + _topic_bonus(topics) + _reason_bonus(result["detail_candidate_reason"])
    return result


def _candidate_reasons(post: Dict[str, Any], topics: List[str]) -> List[str]:
    text = _post_text(post)
    reasons = []
    if "..." in text or "…" in text or "展开" in text:
        reasons.append("truncated_long_post")
    for topic in topics:
        if topic not in NON_TOPIC_BUCKETS:
            reasons.append(f"{topic}_topic")
    if _as_int(post.get("like_count")) + _as_int(post.get("comment_count")) > 10:
        reasons.append("high_interaction")
    return _dedupe_preserve_order(reasons)


def _select_with_topic_quota(
    candidates: List[Dict[str, Any]],
    *,
    batch_size: int,
    preferred_buckets: Iterable[str],
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    selected_urls: set[str] = set()
    sorted_candidates = sorted(candidates, key=lambda item: item.get("detail_score", 0), reverse=True)

    for bucket in preferred_buckets:
        if len(selected) >= batch_size:
            break
        for candidate in sorted_candidates:
            if candidate.get("url") in selected_urls:
                continue
            if bucket in _non_sentiment_topics(candidate):
                selected.append(candidate)
                selected_urls.add(candidate.get("url"))
                break

    for candidate in sorted_candidates:
        if len(selected) >= batch_size:
            break
        if candidate.get("url") in selected_urls:
            continue
        selected.append(candidate)
        selected_urls.add(candidate.get("url"))

    return selected


def _dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_key: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        key = str(candidate.get("dedupe_key") or candidate.get("url") or "")
        current = best_by_key.get(key)
        if current is None or candidate.get("detail_score", 0) > current.get("detail_score", 0):
            best_by_key[key] = candidate
    return list(best_by_key.values())


def _populated_non_sentiment_buckets(candidates: List[Dict[str, Any]]) -> List[str]:
    buckets: List[str] = []
    for candidate in candidates:
        buckets.extend(_non_sentiment_topics(candidate))
    return sorted(set(buckets))


def _covered_topics(attempts: List[Dict[str, Any]]) -> List[str]:
    buckets: List[str] = []
    for attempt in attempts:
        buckets.extend(_attempt_topics(attempt, {}))
    return sorted(set(topic for topic in buckets if topic not in NON_TOPIC_BUCKETS))


def _attempt_topics(attempt: Dict[str, Any], cfg: Dict[str, Any]) -> List[str]:
    explicit = attempt.get("topics") or attempt.get("detail_topic_buckets")
    if isinstance(explicit, list) and explicit:
        return [str(topic) for topic in explicit]
    return classify_detail_topics(attempt, cfg)


def _non_sentiment_topics(post: Dict[str, Any]) -> List[str]:
    return [topic for topic in post.get("detail_topic_buckets", []) if topic not in NON_TOPIC_BUCKETS]


def _effective_topic_coverage(cfg: Dict[str, Any], populated_buckets: List[str]) -> int:
    populated_count = len([bucket for bucket in populated_buckets if bucket not in NON_TOPIC_BUCKETS])
    return min(int(cfg["min_topic_coverage"]), populated_count)


def _topic_bonus(topics: List[str]) -> float:
    return 0.75 * len([topic for topic in topics if topic not in NON_TOPIC_BUCKETS])


def _reason_bonus(reasons: List[str]) -> float:
    bonus = 0.0
    if "truncated_long_post" in reasons:
        bonus += 1.0
    if "high_interaction" in reasons:
        bonus += 0.5
    return bonus


def _content_key(post: Dict[str, Any]) -> str:
    content = _normalize(post.get("content"))
    if len(content) >= 20:
        return normalized_hash(content)
    return normalized_hash(f"{post.get('title') or ''} {post.get('url') or ''}")


def _post_text(post: Dict[str, Any]) -> str:
    return _normalize(f"{post.get('title') or ''} {post.get('content') or post.get('content_text') or ''}")


def _looks_sentiment_only(text: str) -> bool:
    normalized = _normalize(text)
    if len(normalized) < 80:
        return True
    sentiment_terms = ("涨停", "跌停", "抄底", "加仓", "冲啊", "牛", "亏麻", "割肉")
    return any(term in normalized for term in sentiment_terms) and not any(
        keyword.lower() in normalized.lower()
        for keywords in GENERIC_BUCKETS.values()
        for keyword in keywords
    )


def _matches_any(text: str, keywords: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(str(keyword).lower() in lowered for keyword in keywords)


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").split())


def _has_url(post: Dict[str, Any]) -> bool:
    return bool(str(post.get("url") or "").strip())


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _config(config: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if config:
        merged.update(config)
    merged["first_batch_size"] = int(merged["first_batch_size"])
    merged["refill_batch_size"] = int(merged["refill_batch_size"])
    merged["max_detail_pages_total"] = int(merged["max_detail_pages_total"])
    merged["min_usable_details"] = int(merged["min_usable_details"])
    merged["max_drop_rate"] = float(merged["max_drop_rate"])
    merged["min_topic_coverage"] = int(merged["min_topic_coverage"])
    return merged
