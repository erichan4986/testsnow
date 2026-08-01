"""Pipeline skill that merges Agent-Reach and Source Intake evidence buckets."""

import logging
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
    from ..source_adapter import SynthesisItem
else:
    from skill_pipeline import skill, SkillContext
    from source_adapter import SynthesisItem

logger = logging.getLogger(__name__)


def _canonical_url(item: SynthesisItem) -> str:
    url = (item.url or "").strip()
    if not url:
        return ""
    try:
        from urllib.parse import parse_qsl, urlencode, urlparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().lstrip("www.")
        path = (parsed.path or "").rstrip("/").lower()
        query_pairs = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() in {"announcementid", "infocode", "id", "code", "stockcode"}
        ]
        query = urlencode(sorted(query_pairs))
        return f"{host}{path}?{query}" if query else f"{host}{path}"
    except Exception:
        return url.lower().strip("/")


def _dedup_key(item: SynthesisItem) -> str:
    source_type = str(item.extra.get("source_type", "")).lower()
    canonical = _canonical_url(item)
    if source_type == "periodic_report_excerpt":
        excerpt_id = str(item.extra.get("periodic_report_excerpt_id", "")).strip()
        if excerpt_id:
            return f"periodic:{canonical or 'no-url'}#{excerpt_id}"
        fallback = "|".join([canonical, item.title or "", item.publish_time or ""])
        return f"periodic:fallback:{hash(fallback)}"
    return canonical or f"hash:{hash(item)}"


def _item_credit(item: SynthesisItem) -> int:
    try:
        return int(item.extra.get("source_credit", 0))
    except Exception:
        return 0


def _is_official_source_intake(item: SynthesisItem) -> bool:
    source_type = str(item.extra.get("source_type", "")).lower()
    return source_type == "exchange_announcement"


def _pick_preferred(existing: SynthesisItem, new: SynthesisItem) -> SynthesisItem:
    """Return the preferred item when two items share a canonical URL."""
    existing_credit = _item_credit(existing)
    new_credit = _item_credit(new)
    if new_credit > existing_credit:
        return new
    if existing_credit > new_credit:
        return existing
    if _is_official_source_intake(new) and not _is_official_source_intake(existing):
        return new
    return existing


def _to_bucket(item: SynthesisItem) -> str:
    """Map merged item to keep/demote/discard based on eligibility and action."""
    knowledge_eligible = bool(item.extra.get("knowledge_eligible", False))
    report_eligible = bool(item.extra.get("report_eligible", False))
    if not knowledge_eligible and not report_eligible:
        return "discard"

    action = str(item.extra.get("agent_reach_quality_action", "keep"))
    if action == "discard":
        return "discard"
    if action in ("demote",):
        return "demote"
    return "keep"


@skill(name="source_intake_merge")
def source_intake_merge_skill(ctx: SkillContext) -> SkillContext:
    """Normalize external evidence from Agent-Reach and/or Source Intake.

    Outputs:
      - external_evidence_keep_items
      - external_evidence_demote_items
      - external_evidence_discard_items
      - source_intake_merge_status
    """
    agent_reach_enabled = bool(ctx.get("agent_reach_enabled", False))
    source_intake_enabled = bool(ctx.get("source_intake_enabled", False))

    def _finish(status: str, buckets=None) -> SkillContext:
        buckets = buckets or {"keep": [], "demote": [], "discard": []}
        ctx.set("source_intake_merge_status", status)
        for name, items in buckets.items():
            ctx.set(f"external_evidence_{name}_items", items)
        return ctx

    if not agent_reach_enabled and not source_intake_enabled:
        return _finish("disabled")

    seen: Dict[str, SynthesisItem] = {}

    def _add_items(items: List[SynthesisItem]) -> None:
        for item in items or []:
            if not isinstance(item, SynthesisItem):
                continue
            key = _dedup_key(item)
            if key in seen:
                seen[key] = _pick_preferred(seen[key], item)
            else:
                seen[key] = item

    if agent_reach_enabled:
        _add_items(ctx.get("agent_reach_keep_items", []))
        _add_items(ctx.get("agent_reach_demote_items", []))
        # Discard items are intentionally excluded from merged keep/demote.

    if source_intake_enabled:
        _add_items(ctx.get("source_intake_items", []))

    buckets = {"keep": [], "demote": [], "discard": []}
    for item in seen.values():
        buckets[_to_bucket(item)].append(item)

    logger.info(
        f"[source_intake_merge] keep={len(buckets['keep'])} "
        f"demote={len(buckets['demote'])} discard={len(buckets['discard'])}"
    )
    return _finish("ok", buckets)
