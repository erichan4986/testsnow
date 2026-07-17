"""Deterministic freshness policy for display-only external observations."""
from __future__ import annotations
import re
from datetime import date
from typing import Any, Iterable

try:
    from .synthesis_credit import citation_identity
except ImportError:
    from synthesis_credit import citation_identity

FRESH_DAYS = 120
_DATE_FIELDS = ("published_at", "publish_time", "announcement_date", "report_date", "date")
_DATE_PATTERNS = tuple(re.compile(p) for p in (r"^(\d{4})-(\d{1,2})-(\d{1,2})", r"^(\d{4})/(\d{1,2})/(\d{1,2})", r"^(\d{4})年(\d{1,2})月(\d{1,2})日"))
_TOPICS = (("product_validation", ("验证", "认证", "导入", "量产")), ("order_customer", ("订单", "客户", "中标", "签约")), ("capacity_delivery", ("产能", "交付", "供应链", "供应", "物料")), ("margin_cost", ("毛利", "成本", "费用", "售价", "产品价格", "原料价格", "价格压力")), ("demand_cycle", ("需求", "景气", "周期", "资本开支")))
_CONFIRM = ("公司已", "已确认", "订单已", "客户已", "订单落地", "客户导入", "量产", "批量出货", "预计贡献收入", "有望提升", "获得认证", "获认证", "中标", "签约")
_NEGATED = (r"不(?:等同于|替代|代表)官方确认", r"非官方确认", r"未经官方确认", r"官方未确认", r"未确认")

def parse_explicit_date(value: Any) -> date | None:
    for pattern in _DATE_PATTERNS:
        match = pattern.match(str(value or "").strip())
        if match:
            try:
                return date(*(int(part) for part in match.groups()))
            except ValueError:
                return None
    return None

def source_date(value: Any) -> date | None:
    if isinstance(value, dict):
        fields = dict(value.get("extra") or {}); fields.update(value)
    else:
        fields = {key: getattr(value, key, "") for key in _DATE_FIELDS}; fields.update(getattr(value, "extra", {}) or {})
    return next((parsed for key in _DATE_FIELDS if (parsed := parse_explicit_date(fields.get(key)))), None)

def canonical_dynamic_topic(raw_topic: Any) -> str:
    text = str(raw_topic or "").strip()
    return next((key for key, tokens in _TOPICS if any(token in text for token in tokens)), "other")

def has_unnegated_strong_confirmation(text: Any) -> bool:
    value = str(text or "")
    for pattern in _NEGATED:
        value = re.sub(pattern, "", value)
    return any(term in value for term in _CONFIRM)

def assess_layer(items: Iterable[Any], *, as_of_date: date, layer: str = "external") -> dict:
    dated, uncertain = [], False
    for item in items or ():
        current = source_date(item)
        if current is None or current > as_of_date:
            uncertain = True
        else:
            dated.append(current)
    latest = max(dated).isoformat() if dated else None
    status = "unknown" if uncertain or not dated else "fresh" if any((as_of_date - current).days <= FRESH_DAYS for current in dated) else "stale"
    return {"latest_date": latest, "status": status}

def _bounded(text: Any, limit: int = 160) -> str:
    raw = str(text or "").strip(); value = re.sub(r"\s+", " ", raw)[:limit]
    if len(raw) <= limit and value.endswith(("。", "！", "？", ".", "!", "?")):
        return value
    end = max(value.rfind(mark) for mark in ("。", "！", "？", ".", "!", "?"))
    return value[:end + 1] if end >= 20 else ""

def _candidate(paragraph: dict, citations: dict, as_of: date) -> dict | None:
    topics = [str(topic) for topic in paragraph.get("topic_keys") or () if str(topic) != "other"]
    if not topics:
        return None
    refs, seen, dates = [], set(), []
    for raw_ref in paragraph.get("citation_refs") or ():
        try:
            ref = int(raw_ref)
        except (TypeError, ValueError):
            return None
        meta = citations.get(ref) or citations.get(str(ref))
        if not isinstance(meta, dict):
            return None
        credit, current = meta.get("source_credit"), source_date(meta)
        valid = (meta.get("synthesis_display_only") is True and meta.get("scoring_eligible") is False and meta.get("risk_score_eligible") is False and meta.get("quality_action") == "preview_only" and meta.get("verification_status") == "professional_observation" and not isinstance(credit, bool) and isinstance(credit, (int, float)) and credit >= 55 and current is not None and current <= as_of and (as_of - current).days <= FRESH_DAYS)
        if not valid:
            return None
        identity = citation_identity(meta, fallback_ref=ref)
        if identity in seen:
            continue
        seen.add(identity); refs.append((ref, meta)); dates.append(current)
    claim = _bounded(paragraph.get("text"))
    if not refs or not claim or has_unnegated_strong_confirmation(claim):
        return None
    return {"paragraph_index": int(paragraph.get("paragraph_index", 0)), "citation_refs": [ref for ref, _ in refs], "citation_identities": [citation_identity(meta, fallback_ref=ref) for ref, meta in refs], "topic": topics[0], "claim": claim, "oldest_supporting_date": min(dates).isoformat(), "minimum_source_credit": min(float(meta.get("source_credit", 0)) for _, meta in refs)}

def build_freshness_overlay(*, profile: str, as_of_date: date, official_items: Iterable[Any], broker_items: Iterable[Any], external_display: dict) -> dict:
    official = assess_layer(official_items, as_of_date=as_of_date, layer="official")
    def broker_is_eligible(item: Any) -> bool:
        extra = item.get("extra", {}) if isinstance(item, dict) else getattr(item, "extra", {})
        return (extra or {}).get("card_type") != "broker_risk_note"
    broker = assess_layer((item for item in broker_items or () if broker_is_eligible(item)), as_of_date=as_of_date, layer="broker")
    overlay = {"schema": "evidence_freshness.v1", "as_of_date": as_of_date.isoformat(), "official": official, "broker": broker, "external": {"latest_date": None, "status": "unknown"}, "dynamic_topics": {}, "summary_candidate": None, "preface": False, "reason_codes": []}
    if profile not in {"formal_medium", "formal_thin_external_rich"}:
        return overlay
    display = external_display or {}; citations = display.get("citations") or {}; candidates = []
    cards = display.get("_curated_external_argument_cards") or []
    topic_map = {"capacity_delivery": "capacity_delivery", "demand_customer": "order_customer", "technology_product": "product_validation", "financial_quality": "margin_cost"}
    paragraphs = [
        {"paragraph_index": index,
         "text": " ".join(str(unit.get("text") or "") for unit in card.get("evidence_units") or []),
         "topic_keys": [
             topic_map.get(str(family), "other")
             for family in card.get("coverage_families") or []
         ],
         "citation_refs": card.get("citation_refs") or []}
        for index, card in enumerate(cards) if isinstance(card, dict)
    ]
    for paragraph in paragraphs:
        for topic in paragraph.get("topic_keys") or ():
            if str(topic) != "other":
                overlay["dynamic_topics"][str(topic)] = "needs_recent_support"
        if candidate := _candidate(paragraph, citations, as_of_date):
            candidates.append(candidate)
    external_items = [citations.get(ref) or citations.get(str(ref)) for paragraph in paragraphs for ref in paragraph.get("citation_refs") or ()]
    overlay["external"] = assess_layer(external_items, as_of_date=as_of_date, layer="external")
    if official["status"] == "stale" and broker["status"] in {"stale", "unknown"} and candidates:
        candidates.sort(key=lambda row: (-parse_explicit_date(row["oldest_supporting_date"]).toordinal(), -row["minimum_source_credit"], -len(row["claim"]), row["paragraph_index"]))
        overlay["summary_candidate"], overlay["preface"] = candidates[0], True
        overlay["summary_candidate"]["reason_code"] = "official_stale_broker_stale_external_fresh" if broker["status"] == "stale" else "official_stale_broker_missing_external_fresh"
    if official["status"] == "unknown":
        overlay["reason_codes"].append("official_date_unknown")
    elif official["status"] == "stale":
        overlay["reason_codes"].append("official_stale")
    if broker["status"] == "unknown":
        overlay["reason_codes"].append("broker_unknown")
    return overlay
