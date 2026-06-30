"""Central source-boundary policy for report synthesis.

This module is deterministic and side-effect free.  It decides which source
families may enter canonical 4.1-4.3 synthesis, which may enrich formal display
analysis, and which must remain 4.4 / bridge-only material.
"""

from __future__ import annotations

from typing import Any, Dict

try:
    from .source_adapter import SynthesisItem
    from .synthesis_credit import derive_synthesis_usage
except ImportError:
    from source_adapter import SynthesisItem
    from synthesis_credit import derive_synthesis_usage


SOCIAL_SOURCE_TOKENS = (
    "雪球",
    "知乎",
    "微信公众号",
    "微信精选",
    "微信",
    "精选外部",
    "东方财富精选观察",
)

EXTERNAL_VIEWPOINT_SOURCE_TYPES = {
    "curated_external_analysis_evidence",
    "social_viewpoint_analysis_evidence",
}

BRIDGE_SUMMARY_SOURCE_TYPES = {
    "verified_social_bridge_summary",
    "supported_social_bridge_summary",
    "social_bridge_summary",
}

CANONICAL_SOURCE_TYPES = {
    "exchange_announcement",
    "company_ir",
    "company_official",
    "announcement",
    "official",
    "confirmed_fact",
    "broker_research",
    "mainstream_media",
    "industry_research",
}

FORMAL_DISPLAY_SOURCE_TYPES = {
    "periodic_report_fulltext_analysis",
    "periodic_report_narrative_evidence",
    "periodic_report_narrative_card",
    "broker_research",
    "broker_research_digest",
    "broker_research_digest_note",
    "industry_research",
    "mainstream_media",
}

CANONICAL_USAGES = {
    "core_fact_allowed",
    "professional_observation",
    "quantitative_observation",
}


def classify_synthesis_source(item_or_meta: SynthesisItem | Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a stable source-boundary decision for one source item/citation."""
    meta = _extract_meta(item_or_meta)
    source = meta["source"]
    source_type = meta["source_type"]
    verification_status = meta["verification_status"]
    display_only = meta["synthesis_display_only"]
    is_social = _is_social_source(source, source_type)

    if source_type in BRIDGE_SUMMARY_SOURCE_TYPES or verification_status in {
        "verified_discussion",
        "supported_discussion",
    }:
        return _policy(
            layer="bridge_summary",
            source_family="social_bridge" if is_social else "bridge",
            canonical=False,
            formal_display=False,
            external_viewpoint=False,
            bridge=True,
        )

    if source_type in EXTERNAL_VIEWPOINT_SOURCE_TYPES or is_social:
        return _policy(
            layer="external_viewpoint",
            source_family="social_or_external",
            canonical=False,
            formal_display=False,
            external_viewpoint=True,
            bridge=False,
        )

    if source_type in FORMAL_DISPLAY_SOURCE_TYPES and display_only:
        return _policy(
            layer="formal_display",
            source_family="formal_professional",
            canonical=False,
            formal_display=True,
            external_viewpoint=False,
            bridge=False,
        )

    usage = derive_synthesis_usage(item_or_meta or {})
    usage_name = str(usage.get("usage") or "")
    if source_type in CANONICAL_SOURCE_TYPES or usage_name in CANONICAL_USAGES:
        return _policy(
            layer="canonical",
            source_family="formal_professional",
            canonical=True,
            formal_display=True,
            external_viewpoint=False,
            bridge=False,
        )

    if source_type in FORMAL_DISPLAY_SOURCE_TYPES or usage_name == "annual_report_material":
        return _policy(
            layer="formal_display",
            source_family="formal_professional",
            canonical=False,
            formal_display=True,
            external_viewpoint=False,
            bridge=False,
        )

    return _policy(
        layer="excluded",
        source_family="unknown",
        canonical=False,
        formal_display=False,
        external_viewpoint=False,
        bridge=False,
    )


def is_canonical_synthesis_source(item_or_meta: SynthesisItem | Dict[str, Any] | None) -> bool:
    return bool(classify_synthesis_source(item_or_meta)["canonical_synthesis_allowed"])


def is_formal_display_source(item_or_meta: SynthesisItem | Dict[str, Any] | None) -> bool:
    return bool(classify_synthesis_source(item_or_meta)["formal_display_allowed"])


def is_external_viewpoint_source(item_or_meta: SynthesisItem | Dict[str, Any] | None) -> bool:
    return bool(classify_synthesis_source(item_or_meta)["external_viewpoint_only"])


def is_bridge_summary_source(item_or_meta: SynthesisItem | Dict[str, Any] | None) -> bool:
    return bool(classify_synthesis_source(item_or_meta)["bridge_summary_allowed"])


def _policy(
    *,
    layer: str,
    source_family: str,
    canonical: bool,
    formal_display: bool,
    external_viewpoint: bool,
    bridge: bool,
) -> Dict[str, Any]:
    return {
        "layer": layer,
        "source_family": source_family,
        "canonical_synthesis_allowed": canonical,
        "formal_display_allowed": formal_display,
        "external_viewpoint_only": external_viewpoint,
        "bridge_summary_allowed": bridge,
    }


def _extract_meta(item_or_meta: SynthesisItem | Dict[str, Any] | None) -> Dict[str, Any]:
    source = ""
    source_type = ""
    verification_status = ""
    synthesis_display_only = False
    extra: Dict[str, Any] = {}

    if isinstance(item_or_meta, SynthesisItem):
        source = item_or_meta.source_platform or ""
        extra = item_or_meta.extra or {}
    elif isinstance(item_or_meta, dict):
        source = item_or_meta.get("source", item_or_meta.get("source_platform", "")) or ""
        extra = item_or_meta.get("extra", {}) or {}
        if not isinstance(extra, dict):
            extra = {}
        source_type = str(item_or_meta.get("source_type") or "").strip()
        verification_status = str(item_or_meta.get("verification_status") or "").strip()
        synthesis_display_only = bool(
            item_or_meta.get("synthesis_display_only")
            or item_or_meta.get("display_only")
        )

    if not source_type:
        source_type = str(extra.get("source_type") or "").strip()
    if not verification_status:
        verification_status = str(extra.get("verification_status") or "").strip()
    synthesis_display_only = bool(
        synthesis_display_only
        or extra.get("synthesis_display_only")
        or extra.get("display_only")
    )

    return {
        "source": str(source or "").strip(),
        "source_type": source_type,
        "verification_status": verification_status,
        "synthesis_display_only": synthesis_display_only,
    }


def _is_social_source(source: str, source_type: str) -> bool:
    if source_type in EXTERNAL_VIEWPOINT_SOURCE_TYPES:
        return True
    return any(token in str(source or "") for token in SOCIAL_SOURCE_TOKENS)
