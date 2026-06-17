"""Agent-Reach deterministic quality gate skill."""

import re
from typing import Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
    from ..source_adapter import SynthesisItem
else:
    from skill_pipeline import skill, SkillContext
    from source_adapter import SynthesisItem


# Default thresholds for backward-compatible social-post scoring.
_KEEP_THRESHOLD = 60
_DEMOTE_THRESHOLD = 35

# Positive signals
_DATA_PATTERNS = [r"\d+[%％]", r"\d+\.\d+", r"\d+亿", r"\d+万", r"\d+元", r"\d{4}年"]
_EVIDENCE_KEYWORDS = [
    "量产", "定点", "客户", "订单", "交付", "出货", "收入", "营收", "利润",
    "增长", "同比", "环比", "占比", "份额", "市占率", "产能", "良率",
    "芯片", "自动驾驶", "ADAS", "NOA", "域控", "传感器", "雷达", "摄像头",
]
_OFFICIAL_INDICATORS = ["official", "verified", "认证", "官方"]
_PUMPING_SIGNALS = [
    "涨停", "跌停", "必涨", "必跌", "暴涨", "暴跌", "翻倍", "十倍",
    "绝对", "必然", "一定", "毫无疑问", "铁定", "稳赚", "梭哈", "冲啊",
    "赶紧买", "赶紧卖", "清仓", "满仓",
]
_SPAM_SIGNALS = ["点击", "链接", "优惠", "免费", "领取", "扫码", "加群", "私信"]

# Source-specific scoring profiles (Phase 0B).
_SCORING_PROFILES = {
    "social": {
        "keep_threshold": 60,
        "demote_threshold": 35,
        "interaction_weight": 1.0,
        "author_bonus": 5,
        "content_long": 200,
        "content_medium": 50,
        "data_bonus": 4,
        "spam_penalty": 5,
        "pump_penalty": 5,
        "portal_penalty": 0,
    },
    "rss": {
        "keep_threshold": 50,
        "demote_threshold": 30,
        "interaction_weight": 0.0,
        "author_bonus": 3,
        "content_long": 150,
        "content_medium": 30,
        "data_bonus": 5,
        "spam_penalty": 3,
        "pump_penalty": 3,
        "portal_penalty": 0,
    },
    "web": {
        "keep_threshold": 50,
        "demote_threshold": 30,
        "interaction_weight": 0.0,
        "author_bonus": 0,
        "content_long": 300,
        "content_medium": 80,
        "data_bonus": 5,
        "spam_penalty": 3,
        "pump_penalty": 3,
        "portal_penalty": -15,
    },
}


def _detect_source_type(item: SynthesisItem) -> str:
    """Detect source type from source_platform string."""
    platform = item.source_platform.lower()
    if "rss" in platform:
        return "rss"
    elif "web" in platform:
        return "web"
    return "social"


def _is_portal_page(item: SynthesisItem) -> bool:
    """Detect homepage/portal/navigation pages from Web content."""
    content = item.content
    if not content:
        return False

    signals = 0

    # Signal 1: high link density
    link_count = content.count("http://") + content.count("https://")
    lines = [l for l in content.splitlines() if l.strip()]
    if lines and link_count / len(lines) > 0.5:
        signals += 1

    # Signal 2: short average line length
    avg_len = sum(len(l) for l in lines) / max(len(lines), 1)
    if avg_len < 40:
        signals += 1

    # Signal 3: presence of multiple portal keywords
    portal_kws = ["首页", "导航", "网站地图", "sitemap", "友情链接", "所有分类", "更多"]
    if sum(1 for kw in portal_kws if kw in content) >= 2:
        signals += 1

    # Signal 4: generic title
    generic_titles = ["首页", "首页_", "_首页", "主页", "home", "首页 -", "- 首页", "title:"]
    if any(item.title.lower().startswith(gt.lower()) for gt in generic_titles):
        signals += 1

    return signals >= 2


def _extract_query_terms(search_queries: List[dict]) -> List[str]:
    terms = []
    for q in search_queries or []:
        query_text = q.get("query", "")
        if query_text:
            terms.append(query_text)
            for part in re.split(r"\s+", query_text):
                if part and part not in terms:
                    terms.append(part)
    return terms


def _score_relevance(item: SynthesisItem, stock_name: str, query_terms: List[str]) -> tuple:
    score = 0
    reasons = []
    text = f"{item.title} {item.content}"

    if stock_name and stock_name in text:
        score += 15
        reasons.append("包含股票名称")

    matched_terms = 0
    for term in query_terms:
        if term in text:
            matched_terms += 1
    if matched_terms > 0:
        score += min(matched_terms * 5, 10)
        reasons.append(f"匹配 {matched_terms} 个查询词")

    evidence_count = sum(1 for kw in _EVIDENCE_KEYWORDS if kw in text)
    if evidence_count > 0:
        score += min(evidence_count * 2, 10)
        reasons.append(f"含 {evidence_count} 个业务关键词")

    return min(score, 25), reasons


def _score_credibility(item: SynthesisItem, profile: dict) -> tuple:
    score = 0
    reasons = []
    raw = item.extra.get("raw") or {}

    for indicator in _OFFICIAL_INDICATORS:
        if raw.get(indicator) or raw.get("account_type") == "official" or raw.get("source_type") == "official":
            score += 15
            reasons.append("官方/认证来源")
            break

    # Official seed URL: explicit user-provided official domain.
    if raw.get("official_seed_url") is True:
        score += 10
        reasons.append("官方种子来源")

    if item.author and len(item.author) > 0:
        score += profile.get("author_bonus", 5)
        reasons.append("有作者信息")

    if item.url and len(item.url) > 0:
        score += 5
        reasons.append("有URL")

    return min(score, 25), reasons


def _is_official_seed_portal(item: SynthesisItem) -> bool:
    """Return True if item is an official seed URL and portal-like (navigation noise)."""
    raw = item.extra.get("raw") or {}
    return raw.get("official_seed_url") is True and _is_portal_page(item)


def _apply_official_seed_portal_penalty(item: SynthesisItem, score: int, reasons: List[str], profile: dict) -> tuple:
    """Apply reduced portal penalty for official seed URLs with navigation noise."""
    reduced_penalty = -5
    score = max(0, score + reduced_penalty)
    reasons = [r for r in reasons if "内容价值低" not in r]
    reasons.append("官方页面含导航噪音，已保守降权")
    return score, reasons


def _score_evidence(item: SynthesisItem, profile: dict) -> tuple:
    score = 0
    reasons = []
    text = f"{item.title} {item.content}"

    data_count = sum(1 for p in _DATA_PATTERNS if re.search(p, text))
    if data_count > 0:
        score += min(data_count * profile.get("data_bonus", 4), 12)
        reasons.append(f"含 {data_count} 类数据指标")

    date_matches = len(re.findall(r"\d{4}[-/年]\d{1,2}[-/月]", text))
    if date_matches > 0:
        score += min(date_matches * 2, 8)
        reasons.append(f"含 {date_matches} 个日期")

    return min(score, 20), reasons


def _score_substance(item: SynthesisItem, profile: dict) -> tuple:
    score = 0
    reasons = []

    title_len = len(item.title)
    content_len = len(item.content)

    if title_len >= 10:
        score += 5
        reasons.append("标题充实")

    if content_len >= profile.get("content_long", 200):
        score += 10
        reasons.append("内容较长")
    elif content_len >= profile.get("content_medium", 50):
        score += 5
        reasons.append("内容中等")

    if content_len >= 50 and title_len >= 5:
        score += 5
        reasons.append("标题+内容完整")

    # Negative signals
    text = f"{item.title} {item.content}"
    pump_count = sum(1 for s in _PUMPING_SIGNALS if s in text)
    if pump_count > 0:
        score -= min(pump_count * profile.get("pump_penalty", 5), 15)
        reasons.append(f"含 {pump_count} 个炒作信号")

    spam_count = sum(1 for s in _SPAM_SIGNALS if s in text)
    if spam_count > 0:
        score -= min(spam_count * profile.get("spam_penalty", 5), 15)
        reasons.append(f"含 {spam_count} 个垃圾信息信号")

    # Empty content penalty
    if content_len == 0 and title_len == 0:
        score -= 20
        reasons.append("标题和内容均为空")

    return max(min(score, 20), -20), reasons


def _score_engagement(item: SynthesisItem, profile: dict) -> tuple:
    score = 0
    reasons = []

    if profile.get("interaction_weight", 1.0) == 0.0:
        return score, reasons

    interaction = item.interaction_score

    if interaction >= 100:
        score += 10
        reasons.append("高互动")
    elif interaction >= 20:
        score += 6
        reasons.append("中等互动")
    elif interaction >= 5:
        score += 3
        reasons.append("基础互动")

    return min(score, 10), reasons


def score_agent_reach_item(
    item: SynthesisItem,
    stock_name: str = "",
    search_queries: List[dict] = None,
) -> dict:
    """Deterministic quality scoring for a single Agent-Reach SynthesisItem.

    Returns dict with keys: score, action, reasons
    """
    source_type = _detect_source_type(item)
    profile = _SCORING_PROFILES[source_type]

    query_terms = _extract_query_terms(search_queries)

    rel_score, rel_reasons = _score_relevance(item, stock_name, query_terms)
    cred_score, cred_reasons = _score_credibility(item, profile)
    evi_score, evi_reasons = _score_evidence(item, profile)
    sub_score, sub_reasons = _score_substance(item, profile)
    eng_score, eng_reasons = _score_engagement(item, profile)

    total_score = rel_score + cred_score + evi_score + sub_score + eng_score
    total_score = max(0, min(total_score, 100))

    all_reasons = rel_reasons + cred_reasons + evi_reasons + sub_reasons + eng_reasons

    # Portal-page penalty (Web-only)
    portal_penalty = profile.get("portal_penalty", 0)
    if portal_penalty and source_type == "web" and _is_portal_page(item):
        if _is_official_seed_portal(item):
            # Official seed URLs: reduced penalty, calibrated reason.
            total_score, all_reasons = _apply_official_seed_portal_penalty(item, total_score, all_reasons, profile)
        else:
            total_score = max(0, total_score + portal_penalty)
            all_reasons.append("疑似门户/导航页，内容价值低")

            # For generic (non-explicit) Web pages, cap below demote to force discard.
            # For explicit user-provided URLs, keep the penalized score so data-rich
            # pages can still reach keep/demote.
            raw_meta = (item.extra.get("raw") or {}) if item.extra else {}
            if not raw_meta.get("user_provided_url"):
                total_score = min(
                    total_score,
                    profile.get("demote_threshold", _DEMOTE_THRESHOLD) - 1,
                )

    keep_threshold = profile.get("keep_threshold", _KEEP_THRESHOLD)
    demote_threshold = profile.get("demote_threshold", _DEMOTE_THRESHOLD)

    if total_score >= keep_threshold:
        action = "keep"
    elif total_score >= demote_threshold:
        action = "demote"
    else:
        action = "discard"

    return {
        "score": total_score,
        "action": action,
        "reasons": all_reasons,
    }


def _to_compact_result(result: dict) -> dict:
    """Return a compact, content-free audit result dict."""
    compact = {
        "title": result.get("title", ""),
        "source": result.get("source", ""),
        "url": result.get("url", ""),
        "action": result.get("action", ""),
        "score": result.get("score", 0),
        "reasons": result.get("reasons", []),
        "fetch_status": result.get("fetch_status", ""),
        "quality_status": result.get("quality_status", ""),
    }
    # Preserve official-seed metadata if present.
    if "official_seed_url" in result:
        compact["official_seed_url"] = result["official_seed_url"]
    if "source_type" in result:
        compact["source_type"] = result["source_type"]
    if "query_type" in result:
        compact["query_type"] = result["query_type"]
    return compact


def _to_quality_result_dict(
    item: SynthesisItem,
    result: dict,
    fetch_status: str,
) -> dict:
    audit = {
        "title": item.title,
        "source": item.source_platform,
        "action": result["action"],
        "score": result["score"],
        "reasons": result["reasons"],
        "url": item.url,
        "fetch_status": fetch_status,
        "quality_status": "ok",
    }
    raw = item.extra.get("raw") or {} if item.extra else {}
    if raw.get("official_seed_url") is True:
        audit["official_seed_url"] = True
    if raw.get("source_type"):
        audit["source_type"] = raw.get("source_type")
    if raw.get("query_type"):
        audit["query_type"] = raw.get("query_type")
    return audit


def _annotate_item_quality(item: SynthesisItem, result: dict) -> None:
    """Attach quality-gate metadata for downstream evidence-note writing."""
    if item.extra is None:
        item.extra = {}
    item.extra["agent_reach_quality_score"] = int(result.get("score", 0))
    item.extra["agent_reach_quality_action"] = result.get("action", "")
    item.extra["agent_reach_quality_reasons"] = list(result.get("reasons", []) or [])


def _build_compact_queries(search_queries: List[dict]) -> List[dict]:
    """Return query metadata without full content."""
    compact = []
    for q in search_queries or []:
        meta = {
            "query": q.get("query", ""),
            "target_platforms": q.get("target_platforms", []),
        }
        if "urls" in q:
            meta["url_count"] = len(q.get("urls", []))
            meta["urls"] = q.get("urls", [])
        if "rss_feeds" in q:
            meta["rss_feed_count"] = len(q.get("rss_feeds", []))
            meta["rss_feeds"] = q.get("rss_feeds", [])
        if "official_domains" in q:
            meta["official_domains"] = q.get("official_domains", [])
        compact.append(meta)
    return compact


@skill(name="agent_reach_quality")
def agent_reach_quality_skill(ctx: SkillContext) -> SkillContext:
    """Deterministic quality gate for Agent-Reach SynthesisItem records.

    Outputs only to ctx; never mutates stock_raw or raw_data.
    """
    stock_name = ctx.get("stock_name", "")
    date_str = ctx.get("date_str", "")
    agent_reach_enabled = ctx.get("agent_reach_enabled", False)
    fetch_status = ctx.get("agent_reach_status", "")
    items = ctx.get("agent_reach_items", [])
    search_queries = ctx.get("search_queries", [])

    def _write_summary(quality_status: str, counts: dict, warnings: list = None, results: list = None):
        summary = {
            "stock_name": stock_name,
            "date_str": date_str,
            "enabled": agent_reach_enabled,
            "fetch_status": fetch_status,
            "quality_status": quality_status,
            "queries": _build_compact_queries(search_queries),
            "counts": counts,
            "warnings": warnings or [],
            "results": results or [],
        }
        ctx.set("agent_reach_run_summary", summary)

    if not agent_reach_enabled:
        ctx.set("agent_reach_quality_status", "disabled")
        ctx.set("agent_reach_keep_items", [])
        ctx.set("agent_reach_demote_items", [])
        ctx.set("agent_reach_discard_items", [])
        ctx.set("agent_reach_quality_results", [])
        ctx.set("agent_reach_quality_summary", {
            "keep": 0, "demote": 0, "discard": 0, "total": 0,
            "fetch_status": "", "quality_status": "disabled",
        })
        _write_summary("disabled", {"total": 0, "keep": 0, "demote": 0, "discard": 0})
        return ctx

    # Skipped states: missing_binary, error, or timeout with zero items
    if fetch_status in ("missing_binary", "error") or (fetch_status == "timeout" and not items):
        ctx.set("agent_reach_quality_status", "skipped")
        ctx.set("agent_reach_keep_items", [])
        ctx.set("agent_reach_demote_items", [])
        ctx.set("agent_reach_discard_items", [])
        ctx.set("agent_reach_quality_results", [])
        ctx.set("agent_reach_quality_summary", {
            "keep": 0, "demote": 0, "discard": 0, "total": 0,
            "fetch_status": fetch_status, "quality_status": "skipped",
        })
        _write_summary("skipped", {"total": 0, "keep": 0, "demote": 0, "discard": 0}, warnings=ctx.get("agent_reach_warnings", []))
        return ctx

    if not items:
        ctx.set("agent_reach_quality_status", "empty")
        ctx.set("agent_reach_keep_items", [])
        ctx.set("agent_reach_demote_items", [])
        ctx.set("agent_reach_discard_items", [])
        ctx.set("agent_reach_quality_results", [])
        ctx.set("agent_reach_quality_summary", {
            "keep": 0, "demote": 0, "discard": 0, "total": 0,
            "fetch_status": fetch_status, "quality_status": "empty",
        })
        _write_summary("empty", {"total": 0, "keep": 0, "demote": 0, "discard": 0}, warnings=ctx.get("agent_reach_warnings", []))
        return ctx

    keep_items = []
    demote_items = []
    discard_items = []
    quality_results = []

    for item in items:
        result = score_agent_reach_item(item, stock_name, search_queries)
        _annotate_item_quality(item, result)
        action = result["action"]

        if action == "keep":
            keep_items.append(item)
        elif action == "demote":
            demote_items.append(item)
        else:
            discard_items.append(item)

        quality_results.append(_to_quality_result_dict(item, result, fetch_status))

    summary = {
        "keep": len(keep_items),
        "demote": len(demote_items),
        "discard": len(discard_items),
        "total": len(items),
        "fetch_status": fetch_status,
        "quality_status": "ok",
    }

    ctx.set("agent_reach_quality_status", "ok")
    ctx.set("agent_reach_keep_items", keep_items)
    ctx.set("agent_reach_demote_items", demote_items)
    ctx.set("agent_reach_discard_items", discard_items)
    ctx.set("agent_reach_quality_results", quality_results)
    ctx.set("agent_reach_quality_summary", summary)
    _write_summary(
        "ok",
        summary,
        warnings=ctx.get("agent_reach_warnings", []),
        results=[_to_compact_result(r) for r in quality_results],
    )
    return ctx
