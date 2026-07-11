"""Schema validation and legacy adaptation for annual narrative arguments."""

from __future__ import annotations

import hashlib
from typing import Any


CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v2"
ENVELOPE_SCHEMA_VERSION = "periodic_report_narrative_evidence_cards.v2"
SELECTION_VERSION = "annual_argument_selection.v2"

CANONICAL_FAMILIES = (
    "business_structure",
    "operating_progress",
    "market_competition_outlook",
    "technology_product_progress",
    "financial_quality_explanation",
)

FAMILY_LABELS = {
    "business_structure": "业务结构",
    "operating_progress": "经营变化",
    "market_competition_outlook": "管理层判断与行业展望",
    "technology_product_progress": "技术与产品进展",
    "financial_quality_explanation": "财务质量与变化原因",
}

_SOURCE_UNIT_FIELDS = ("unit_id", "block_id", "ordinal", "start_pos", "end_pos", "text")
_CARD_FIELDS = (
    "schema_version",
    "selection_version",
    "card_id",
    "argument_family",
    "argument_complete",
    "title",
    "source_block_id",
    "source_unit_ids",
    "source_units",
    "source_excerpt",
    "fact_anchors",
    "secondary_signals",
    "score_parts",
    "quality_score",
    "selection_reason",
    "source_type",
    "source_credit",
    "report_year",
    "report_type",
)
_V1_FAMILY_MAP = {
    "business_model": "business_structure",
    "operation_update": "operating_progress",
    "management_market_view": "market_competition_outlook",
    "market_outlook": "market_competition_outlook",
    "technology_platform": "technology_product_progress",
    "rd_product_progress": "technology_product_progress",
    "financial_note": "financial_quality_explanation",
}
_FINANCIAL_METRIC_TOKENS = (
    "毛利率",
    "净利率",
    "净利润",
    "营业收入",
    "营业利润",
    "营业成本",
    "营收",
    "现金流",
    "应收账款",
    "存货",
    "资产减值",
    "减值损失",
    "费用率",
    "期间费用",
    "利润总额",
    "每股收益",
)
_CAUSAL_TOKENS = ("主要系", "由于", "所致", "影响")


def validate_source_unit(unit: dict) -> tuple[str, ...]:
    """Return deterministic validation errors for one source-unit record."""
    if not isinstance(unit, dict):
        return ("invalid_source_unit",)

    errors = []
    if any(key not in unit or unit.get(key) in (None, "") for key in _SOURCE_UNIT_FIELDS):
        errors.append("missing_source_unit_field")

    ordinal = unit.get("ordinal")
    if not _is_int(ordinal):
        errors.append("invalid_source_unit_ordinal")

    start_pos = unit.get("start_pos")
    end_pos = unit.get("end_pos")
    if not _is_int(start_pos) or not _is_int(end_pos):
        errors.append("invalid_source_unit_position")
    elif start_pos < 0 or end_pos <= start_pos:
        errors.append("invalid_source_unit_range")

    return tuple(dict.fromkeys(errors))


def validate_card_v2(card: dict) -> tuple[str, ...]:
    """Return deterministic validation errors for a v2 annual argument card."""
    if not isinstance(card, dict):
        return ("invalid_card",)

    errors = []
    if any(key not in card or card.get(key) is None for key in _CARD_FIELDS):
        errors.append("missing_card_field")
    if card.get("schema_version") != CARD_SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    if card.get("selection_version") != SELECTION_VERSION:
        errors.append("invalid_selection_version")
    if card.get("argument_family") not in CANONICAL_FAMILIES:
        errors.append("invalid_argument_family")
    if not isinstance(card.get("argument_complete"), bool):
        errors.append("invalid_argument_complete")

    raw_units = card.get("source_units")
    units = raw_units if isinstance(raw_units, list) else []
    if raw_units is not None and not isinstance(raw_units, list):
        errors.append("invalid_source_units")

    source_unit_ids = card.get("source_unit_ids")
    expected_ids = list(source_unit_ids) if isinstance(source_unit_ids, (list, tuple)) else []
    actual_ids = [unit.get("unit_id") if isinstance(unit, dict) else None for unit in units]
    if actual_ids != expected_ids:
        errors.append("source_unit_ids_mismatch")

    positions = []
    for unit in units:
        unit_errors = validate_source_unit(unit)
        errors.extend(unit_errors)
        if not unit_errors:
            positions.append((unit["ordinal"], unit["start_pos"], unit["end_pos"]))

    if any(
        right[0] <= left[0] or right[1] <= left[1] or right[2] <= left[2]
        for left, right in zip(positions, positions[1:])
    ):
        errors.append("non_monotonic_source_units")

    positions_by_start = sorted(positions, key=lambda item: (item[1], item[2], item[0]))
    if any(left[2] > right[1] for left, right in zip(positions_by_start, positions_by_start[1:])):
        errors.append("overlapping_source_units")

    return tuple(dict.fromkeys(errors))


def adapt_v1_card(card: dict) -> dict:
    """Adapt one legacy card in memory without ranking, filtering, or writing."""
    legacy = dict(card)
    excerpt = str(legacy.get("source_excerpt") or "")
    block_id = str(legacy.get("source_block_id") or "legacy")
    normalized_excerpt = " ".join(excerpt.split())
    excerpt_hash = hashlib.sha256(normalized_excerpt.encode("utf-8")).hexdigest()
    unit_id = f"{block_id}:legacy:{excerpt_hash}"
    family = _legacy_family(str(legacy.get("card_type") or ""), excerpt)

    adapted = dict(legacy)
    adapted.pop("card_type", None)
    adapted.update({
        "schema_version": CARD_SCHEMA_VERSION,
        "selection_version": SELECTION_VERSION,
        "card_id": legacy.get("card_id") or unit_id,
        "argument_family": family,
        "argument_complete": False,
        "title": legacy.get("title") or FAMILY_LABELS[family],
        "source_block_id": block_id,
        "source_unit_ids": [unit_id],
        "source_units": [{
            "unit_id": unit_id,
            "block_id": block_id,
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": len(excerpt),
            "text": excerpt,
        }],
        "source_excerpt": excerpt,
        "fact_anchors": _value_or_default(legacy.get("fact_anchors"), []),
        "secondary_signals": _value_or_default(legacy.get("secondary_signals"), []),
        "score_parts": _value_or_default(legacy.get("score_parts"), {}),
        "quality_score": _value_or_default(legacy.get("quality_score"), 0),
        "selection_reason": "legacy_v1_adapter",
        "source_type": "periodic_report_narrative_evidence",
        "source_credit": 75,
        "report_year": _value_or_default(legacy.get("report_year"), 0),
        "report_type": legacy.get("report_type") or "annual",
    })
    return adapted


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _legacy_family(card_type: str, excerpt: str) -> str:
    if card_type == "margin_competitiveness":
        if _has_financial_metric(excerpt) and any(token in excerpt for token in _CAUSAL_TOKENS):
            return "financial_quality_explanation"
        return "market_competition_outlook"
    try:
        return _V1_FAMILY_MAP[card_type]
    except KeyError as exc:
        raise ValueError(f"unsupported v1 card_type: {card_type or '<empty>'}") from exc


def _has_financial_metric(excerpt: str) -> bool:
    return any(token in excerpt for token in _FINANCIAL_METRIC_TOKENS)


def _value_or_default(value: Any, default: Any) -> Any:
    return default if value is None else value
