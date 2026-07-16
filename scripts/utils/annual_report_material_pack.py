"""Annual Report Material Pack.

Deterministic selection, ranking, and deduplication of periodic-report
narrative cards for display-only synthesis.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

if __package__:
    from .source_adapter import SynthesisItem
    from .annual_argument_schema import ANNUAL_CHECKBOX_MARKER_RUN_RE, CARD_SCHEMA_VERSION, adapt_v1_card, annual_source_tail, validate_card_v2
    from .annual_argument_schema import has_concrete_annual_anchor, normalize_annual_source_text
    from .periodic_report_narrative_card_note_writer import narrative_card_note_path
    from .periodic_report_narrative_pack_store import MANIFEST_FILENAME, PACK_DIRNAME, PeriodicNarrativePackStorageError, load_validated_periodic_narrative_pack_set, normalized_source_excerpt_hash, v2_note_card_fingerprint
else:
    from source_adapter import SynthesisItem
    from annual_argument_schema import ANNUAL_CHECKBOX_MARKER_RUN_RE, CARD_SCHEMA_VERSION, adapt_v1_card, annual_source_tail, validate_card_v2
    from annual_argument_schema import has_concrete_annual_anchor, normalize_annual_source_text
    from periodic_report_narrative_card_note_writer import narrative_card_note_path
    from periodic_report_narrative_pack_store import MANIFEST_FILENAME, PACK_DIRNAME, PeriodicNarrativePackStorageError, load_validated_periodic_narrative_pack_set, normalized_source_excerpt_hash, v2_note_card_fingerprint


SCHEMA_VERSION = "annual_report_material_pack.v1"
NARRATIVE_CARD_SOURCE_TYPE = "periodic_report_narrative_evidence"
_V1_DIAGNOSTIC_KEYS = ("v1_exact_shadowed_count", "v1_unit_covered_count", "v1_needs_recovery_count", "v1_adapter_use_count", "v1_covered_fragment_count", "v1_actionable_needs_recovery_count", "v1_invalid_legacy_fragment_count", "v1_duplicate_legacy_fragment_count")

# Default high-interest terms for diagnostics. These are examples / cross-domain
# signals, not a company-specific whitelist or dominant ranking feature.
DEFAULT_HIGH_VALUE_TERMS = {
    # AI / auto / tech hardware examples
    "A2000", "Robotaxi", "SesameX", "CPO", "硅光", "Chiplet", "HBM",
    "800G", "1.6T", "AI眼镜", "端侧AI", "端侧",
    # Analog / general semiconductor examples
    "运放", "电源管理", "高精度", "信号链", "模拟芯片",
    # Generic product / application signals
    "量产", "客户验证", "定点", "批量订单",
}

_FINANCIAL_TERMS = {
    "毛利率", "净利率", "同比提升", "同比下降", "收入增长", "营收增长",
    "净利润", "归母净利润", "扣非净利润", "研发投入", "研发费用",
    "现金流", "经营性现金流", "减值", "存货", "应收账款", "资产负债率",
    "roe", "roe", "eps", "摊薄", "净资产收益率",
}

_APPLICATION_TERMS = {
    "汽车", "工业", "手机", "通信", "数据中心", "云计算", "ai", "人工智能",
    "消费电子", "物联网", "医疗", "能源", "光伏", "储能", "新能源",
}

_RD_TERMS = {
    "研发", "验证", "量产", "流片", "样品", "测试", "导入", "定点",
    "商业化", "推出", "发布", "迭代", "升级", "新一代",
}

_STRATEGY_TERMS = {
    "预计", "计划", "目标", "规划", "路线图", "roadmap", "2026", "2027",
    "2028", "未来三年", "五年规划",
}

# Patterns that suggest a concrete product / technology / project name.
_PRODUCT_PATTERNS = [
    re.compile(r"[A-Za-z]{1,3}\d{2,}"),          # A2000, H100, X86
    re.compile(r"\d{2,}[GT]"),                   # 800G, 1.6T
    re.compile(r"[A-Z][a-zA-Z]+\d+[a-zA-Z]*"),   # SesameX style
]


class _CardRecord:
    __slots__ = (
        "path",
        "card",
        "card_id",
        "argument_family",
        "title",
        "report_year",
        "report_type",
        "excerpt",
        "source_credit",
        "source_block_id",
        "quality_score",
        "quality_reasons",
        "is_v2",
    )

    def __init__(
        self,
        *,
        path: Path,
        card: Dict[str, Any],
        card_id: str,
        argument_family: str,
        title: str,
        report_year: str,
        report_type: str,
        excerpt: str,
        source_credit: int,
        source_block_id: str,
        quality_score: float,
        quality_reasons: List[str],
        is_v2: bool,
    ) -> None:
        self.path = path
        self.card = card
        self.card_id = card_id
        self.argument_family = argument_family
        self.title = title
        self.report_year = report_year
        self.report_type = report_type
        self.excerpt = excerpt
        self.source_credit = source_credit
        self.source_block_id = source_block_id
        self.quality_score = quality_score
        self.quality_reasons = quality_reasons
        self.is_v2 = is_v2


def build_annual_report_material_pack(
    *,
    stock_name: str,
    base_dir: str | Path,
    stock_code: str = "",
    **_legacy_options: Any,
) -> Dict[str, Any]:
    """Build a deterministic, display-only annual-report material pack.

    The pack only reads narrative-card Knowledge notes. It does not call LLMs,
    fetch data, or modify Knowledge.
    """
    del _legacy_options

    if stock_code and _has_pack_storage(stock_name, base_dir):
        try:
            result = build_annual_report_material_pack_from_pack_shadow(
                stock_name=stock_name,
                stock_code=stock_code,
                base_dir=base_dir,
            )
            result["diagnostics"]["storage_mode"] = "pack_first"
            return result
        except PeriodicNarrativePackStorageError as exc:
            if not _has_v2_note_projections(stock_name, base_dir):
                raise
            fallback = _build_legacy_material_pack(stock_name, base_dir)
            fallback["diagnostics"].update({
                "storage_mode": "legacy_fallback",
                "pack_validation_errors": [exc.code],
            })
            return fallback

    return _build_legacy_material_pack(stock_name, base_dir)


def _build_legacy_material_pack(stock_name: str, base_dir: str | Path) -> Dict[str, Any]:
    """Read legacy Markdown projections when no validated pack is available."""

    notes_dir = _narrative_cards_dir(stock_name, base_dir)

    if not notes_dir.exists():
        return _empty_pack(stock_name)

    records: List[_CardRecord] = []
    for path in sorted(notes_dir.glob("*.md")):
        record = _read_note_as_record(path, adapt_legacy=False)
        if record is None:
            continue
        records.append(record)

    return _build_material_pack_from_records(stock_name, records)


def _has_pack_storage(stock_name: str, base_dir: str | Path) -> bool:
    root = _narrative_cards_dir(stock_name, base_dir).parent
    return (root / MANIFEST_FILENAME).exists() or (root / PACK_DIRNAME).exists()


def _has_v2_note_projections(stock_name: str, base_dir: str | Path) -> bool:
    notes_dir = _narrative_cards_dir(stock_name, base_dir)
    return any(_is_v2_note_projection(path) for path in notes_dir.glob("*.md")) if notes_dir.exists() else False


def build_annual_report_material_pack_from_pack_shadow(
    *, stock_name: str, stock_code: str, base_dir: str | Path,
) -> Dict[str, Any]:
    """Build a read-only migration shadow from validated packs plus legacy v1 notes."""
    loaded = load_validated_periodic_narrative_pack_set(
        stock_name=stock_name, stock_code=stock_code, base_dir=base_dir,
    )
    records = [
        _record_from_card(Path(f"pack-{index}.json"), card, is_v2=True)
        for index, card in enumerate(loaded["cards"])
    ]
    notes_dir = _narrative_cards_dir(stock_name, base_dir)
    for path in sorted(notes_dir.glob("*.md")) if notes_dir.exists() else []:
        record = _read_note_as_record(path, adapt_legacy=False)
        if record is not None and not record.is_v2:
            records.append(record)
    result = _build_material_pack_from_records(stock_name, records, storage_mode="pack_shadow")
    pack_count = len(loaded["packs"])
    result["diagnostics"].update({
        "packs_seen": pack_count, "packs_loaded": pack_count,
        "v2_markdown_ignored_count": sum(
            1 for path in notes_dir.glob("*.md") if _is_v2_note_projection(path)
        ) if notes_dir.exists() else 0,
    })
    return result


def classify_periodic_narrative_v2_notes(
    *, stock_name: str, producer_cards: List[Dict[str, Any]], base_dir: str | Path,
    source_unit_decisions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Classify persisted v2 note projections against canonical producer cards."""
    expected = {str(card.get("card_id") or ""): card for card in producer_cards}
    current_cards_by_unit: Dict[str, Set[str]] = {}
    for card in producer_cards:
        card_id = str(card.get("card_id") or "")
        for unit_id in card.get("source_unit_ids") or []:
            if isinstance(unit_id, str) and unit_id and card_id:
                current_cards_by_unit.setdefault(unit_id, set()).add(card_id)
    matches: Dict[str, List[tuple[Path, Dict[str, Any]]]] = {}
    states = (
        "active_v2", "stale_duplicate", "stale_reindexed", "stale_source_covered", "stale_orphan", "stale_invalid",
        "stale_resolved_selected", "stale_resolved_structural", "stale_resolved_mixed", "stale_recovery_required", "stale_source_missing", "stale_source_ambiguous",
    )
    result: Dict[str, Any] = {key: [] for key in states}
    notes_dir = _narrative_cards_dir(stock_name, base_dir)
    for path in sorted(notes_dir.glob("*.md")) if notes_dir.exists() else []:
        if not _is_v2_note_projection(path):
            continue
        record = _read_note_as_record(path, adapt_legacy=False)
        if record is None:
            result["stale_invalid"].append(_classification_item(path))
            continue
        card = record.card
        card_id = str(card.get("card_id") or "")
        canonical = expected.get(card_id)
        if canonical is None:
            covered_by = _covering_current_card_ids(card, current_cards_by_unit)
            if covered_by:
                result["stale_source_covered"].append(_classification_item(path, card_id, covered_by))
            elif source_unit_decisions is None:
                result["stale_orphan"].append(_classification_item(path, card_id))
            else:
                target, details = _resolve_stale_source_units(card, source_unit_decisions)
                result[target].append(_classification_item(path, card_id, details=details))
        elif v2_note_card_fingerprint(card) != v2_note_card_fingerprint(canonical):
            result["stale_reindexed"].append(_classification_item(path, card_id))
        else:
            matches.setdefault(card_id, []).append((path, card))

    for index, card in enumerate(producer_cards):
        card_id = str(card.get("card_id") or "")
        candidates = matches.get(card_id) or []
        if not candidates:
            continue
        expected_path = narrative_card_note_path(
            stock_name=stock_name, card=card, base_dir=base_dir, index=index,
        )
        candidates.sort(key=lambda item: (item[0] != expected_path, str(item[0])))
        active_path, _active_card = candidates[0]
        result["active_v2"].append(_classification_item(active_path, card_id))
        result["stale_duplicate"].extend(
            _classification_item(path, card_id) for path, _card in candidates[1:]
        )
    active_ids = {item["card_id"] for item in result["active_v2"]}
    result["missing_active_card_ids"] = [str(card.get("card_id") or "") for card in producer_cards
                                         if str(card.get("card_id") or "") not in active_ids]
    return result


def _covering_current_card_ids(
    card: Dict[str, Any], current_cards_by_unit: Dict[str, Set[str]],
) -> List[str]:
    """Return current cards only when every persisted source unit still exists."""
    unit_ids = card.get("source_unit_ids") or []
    if not unit_ids or any(unit_id not in current_cards_by_unit for unit_id in unit_ids):
        return []
    return sorted({card_id for unit_id in unit_ids for card_id in current_cards_by_unit[unit_id]})


_ARCHIVE_SAFE_REASONS = frozenset({"section_label", "regulatory_disclosure", "audit_procedure", "accounting_policy_definition", "checkbox_or_page_marker", "definition_or_hash"})


def _resolve_stale_source_units(card: Dict[str, Any], decisions: List[Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
    old_units = card.get("source_units") or []
    hashes = [normalized_source_excerpt_hash(unit.get("text")) for unit in old_units if isinstance(unit, dict)]
    if not hashes or len(hashes) != len(old_units):
        return "stale_source_missing", {}
    exact = []
    for unit, text_hash in zip(old_units, hashes):
        matches = [item for item in decisions if item.get("source_block_id") == unit.get("block_id")
                   and item.get("source_unit_id") == unit.get("unit_id") and item.get("source_text_hash") == text_hash]
        if len(matches) != 1:
            exact = []
            break
        exact.append(matches[0])
    candidates = [exact] if exact else []
    if not candidates:
        by_block: Dict[str, List[Dict[str, Any]]] = {}
        for item in decisions:
            by_block.setdefault(str(item.get("source_block_id") or ""), []).append(item)
        for block_items in by_block.values():
            ordered = sorted(block_items, key=lambda item: int(item.get("source_order") or 0))
            candidates.extend(ordered[index:index + len(hashes)] for index in range(len(ordered) - len(hashes) + 1)
                              if [item.get("source_text_hash") for item in ordered[index:index + len(hashes)]] == hashes)
        same_block = [items for items in candidates if items[0].get("source_block_id") == old_units[0].get("block_id")]
        candidates = same_block or candidates
    if len(candidates) != 1:
        return ("stale_source_ambiguous" if candidates else "stale_source_missing"), {}
    mapped = candidates[0]
    reasons = [str(item.get("reason") or "") for item in mapped if item.get("disposition") != "selected"]
    details = {
        "mapped_source_unit_ids": [str(item.get("source_unit_id") or "") for item in mapped], "archive_safe_reasons": reasons,
        "covered_by_card_ids": sorted({card_id for item in mapped for card_id in item.get("selected_by_card_ids") or []}), "source_unit_resolutions": [
            {key: item.get(key) for key in ("source_unit_id", "disposition", "reason", "selected_by_card_ids")} for item in mapped],
    }
    if any(reason not in _ARCHIVE_SAFE_REASONS for reason in reasons):
        return "stale_recovery_required", details
    selected = sum(item.get("disposition") == "selected" for item in mapped)
    return ("stale_resolved_selected" if selected == len(mapped)
            else "stale_resolved_structural" if not selected else "stale_resolved_mixed"), details


def _narrative_cards_dir(stock_name: str, base_dir: str | Path) -> Path:
    return Path(base_dir) / "10-Stocks" / _safe_dir_segment(stock_name) / "periodic_narrative_cards"


def _is_v2_note_projection(path: Path) -> bool:
    try:
        frontmatter = _parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return (frontmatter.get("source_type") == NARRATIVE_CARD_SOURCE_TYPE
            and str(frontmatter.get("schema_version") or "") == CARD_SCHEMA_VERSION)


def _classification_item(
    path: Path, card_id: str = "", covered_by_card_ids: Optional[List[str]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {"path": str(path), "card_id": card_id}
    if covered_by_card_ids:
        item["covered_by_card_ids"] = covered_by_card_ids
    item.update(details or {})
    return item


def _build_material_pack_from_records(
    stock_name: str, records: List[_CardRecord], *, storage_mode: str = "",
) -> Dict[str, Any]:
    if not records:
        result = _empty_pack(stock_name)
        if storage_mode:
            result["diagnostics"]["storage_mode"] = storage_mode
        return result

    cards_seen = len(records)
    v2_records = [record for record in records if record.is_v2]
    v2_identity_keys = {key for record in v2_records for key in _record_identity_keys(record)}
    adapted_legacy: List[_CardRecord] = []
    diagnostics_counts = dict.fromkeys(_V1_DIAGNOSTIC_KEYS, 0)
    v1_recovery_examples: List[Dict[str, Any]] = []
    seen_actionable_fragments: Set[str] = set()
    for record in records:
        if record.is_v2:
            continue
        if _record_identity_keys(record) & v2_identity_keys:
            diagnostics_counts["v1_exact_shadowed_count"] += 1
            diagnostics_counts["v1_unit_covered_count"] += 1
            continue
        fragments = _classify_legacy_fragments(record.excerpt, record.source_block_id, v2_records)
        actionable = []
        for fragment in fragments:
            status = fragment["status"]
            if status == "covered":
                diagnostics_counts["v1_covered_fragment_count"] += 1
                continue
            if status == "invalid_legacy":
                diagnostics_counts["v1_invalid_legacy_fragment_count"] += 1
                continue
            key = f"{record.source_block_id}\0{fragment['normalized']}"
            if key in seen_actionable_fragments:
                diagnostics_counts["v1_duplicate_legacy_fragment_count"] += 1
                continue
            seen_actionable_fragments.add(key)
            actionable.append(fragment)
        if not actionable:
            diagnostics_counts["v1_unit_covered_count"] += int(any(
                fragment["status"] == "covered" for fragment in fragments
            ))
            continue
        diagnostics_counts["v1_actionable_needs_recovery_count"] += len(actionable)
        diagnostics_counts["v1_needs_recovery_count"] += len(actionable)
        v1_recovery_examples.append({"fragment": actionable[0]["original"]})
        try:
            legacy_card = dict(record.card)
            legacy_card["source_excerpt"] = "".join(fragment["original"] for fragment in actionable)
            adapted = adapt_v1_card(legacy_card)
        except (TypeError, ValueError):
            continue
        adapted_legacy.append(_record_from_card(record.path, adapted, is_v2=False))
        diagnostics_counts["v1_adapter_use_count"] += 1

    # Canonical v2 cards are already source-unit-owned and must all survive.
    # Keep the historical duplicate filtering only for adapted v1 notes.
    selected = v2_records + _deduplicate_records(adapted_legacy)
    selected.sort(key=_record_sort_key)

    result = {
        "schema_version": SCHEMA_VERSION,
        "stock_name": stock_name,
        "selected_narrative_cards": [_record_to_dict(r) for r in selected],
        "diagnostics": {
            "cards_seen": cards_seen,
            "cards_selected": len(selected),
            "by_family_seen": _count_by_family(records),
            "by_family_selected": _count_by_family(selected),
            "v1_recovery_examples": v1_recovery_examples,
            **diagnostics_counts,
        },
    }
    if storage_mode:
        result["diagnostics"]["storage_mode"] = storage_mode
    return result


def selected_cards_to_synthesis_items(
    selected_cards: List[Dict[str, Any]],
) -> List[SynthesisItem]:
    """Convert pack-selected card records to display-only SynthesisItems."""
    items: List[SynthesisItem] = []
    for card in selected_cards:
        report_year = str(card.get("report_year") or "")
        report_type = str(card.get("report_type") or "")
        title = str(card.get("title") or "年报叙事卡片")
        extra = {
            "source_type": NARRATIVE_CARD_SOURCE_TYPE,
            "source_credit": int(card.get("source_credit") or 75),
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "synthesis_eligible": False,
            "synthesis_display_only": True,
            "experimental": True,
            "card_id": str(card.get("card_id") or ""),
            "source_block_id": str(card.get("source_block_id") or ""),
            "report_year": _as_int(report_year, report_year),
            "report_type": report_type,
        }
        for key in (
            "argument_family",
            "argument_complete",
            "schema_version",
            "selection_version",
            "source_unit_ids",
            "source_units",
            "fact_anchors",
            "secondary_signals",
            "score_parts",
            "quality_score",
            "selection_reason",
            "selection_diagnostics",
        ):
            if key in card:
                extra[key] = card[key]
        items.append(
            SynthesisItem(
                title=f"{report_year} {report_type} | {title}".strip(),
                content=str(card.get("excerpt") or ""),
                author="公司年报",
                source_platform="定期报告叙事卡片",
                url="",
                publish_time=report_year,
                interaction_score=0,
                extra=extra,
            )
        )
    return items


def _empty_pack(stock_name: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stock_name": stock_name,
        "selected_narrative_cards": [],
        "diagnostics": {
            "cards_seen": 0,
            "cards_selected": 0,
            "by_family_seen": {},
            "by_family_selected": {},
            **dict.fromkeys(_V1_DIAGNOSTIC_KEYS, 0),
            "v1_recovery_examples": [],
        },
    }


def _read_note_as_record(
    path: Path,
    *,
    adapt_legacy: bool = True,
) -> Optional[_CardRecord]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = _parse_frontmatter(text)
    if frontmatter.get("source_type") != NARRATIVE_CARD_SOURCE_TYPE:
        return None

    excerpt = _extract_narrative_evidence_excerpt(text)
    if not excerpt:
        return None

    is_v2 = str(frontmatter.get("schema_version") or "") == CARD_SCHEMA_VERSION
    if is_v2:
        source_units = _extract_json_section(text, "Source Units")
        diagnostics = _extract_json_section(text, "Selection Diagnostics")
        if not isinstance(source_units, list) or not isinstance(diagnostics, dict):
            return None
        card = dict(frontmatter)
        card.update({
            "source_excerpt": excerpt,
            "source_units": source_units,
            "score_parts": diagnostics.get("score_parts") or {},
            "selection_reason": diagnostics.get("selection_reason") or "",
            "selection_diagnostics": diagnostics,
        })
        if validate_card_v2(card) or not _source_units_match_excerpt(source_units, excerpt):
            return None
        return _record_from_card(path, card, is_v2=True)

    card = dict(frontmatter)
    card["source_excerpt"] = excerpt
    if adapt_legacy:
        try:
            card = adapt_v1_card(card)
        except (TypeError, ValueError):
            return None
    return _record_from_card(path, card, is_v2=False)


def read_periodic_narrative_card_note(path: str | Path) -> Optional[Dict[str, Any]]:
    """Parse one valid persisted narrative note without adapting legacy fields."""
    record = _read_note_as_record(Path(path), adapt_legacy=False)
    return dict(record.card) if record is not None else None


def _record_from_card(path: Path, card: Dict[str, Any], *, is_v2: bool) -> _CardRecord:
    excerpt = str(card.get("source_excerpt") or "")
    family = str(card.get("argument_family") or "")
    score_value = card.get("quality_score")
    try:
        score = float(score_value)
    except (TypeError, ValueError):
        score = _score_excerpt(excerpt)[0]
    if is_v2:
        reasons = [str(card.get("selection_reason") or "")]
    else:
        score, reasons = _score_excerpt(excerpt)
    return _CardRecord(
        path=path,
        card=dict(card),
        card_id=str(card.get("card_id") or path.stem),
        argument_family=family,
        title=str(card.get("title") or "年报叙事卡片"),
        report_year=card.get("report_year") or "",
        report_type=str(card.get("report_type") or ""),
        excerpt=excerpt,
        source_credit=_as_int(card.get("source_credit"), 75),
        source_block_id=str(card.get("source_block_id") or ""),
        quality_score=score,
        quality_reasons=reasons,
        is_v2=is_v2,
    )


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}

    data: Dict[str, Any] = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line or raw_line.startswith(" ") or ":" not in raw_line:
            index += 1
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            index += 1
            continue
        if value == "":
            items: List[Any] = []
            cursor = index + 1
            while cursor < len(lines) and lines[cursor].startswith("  - "):
                items.append(_clean_scalar(lines[cursor][4:].strip()))
                cursor += 1
            data[key] = items
            index = cursor
            continue
        data[key] = _clean_scalar(value)
        index += 1
    return data


def _extract_json_section(text: str, heading: str) -> Any:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*\n+```(?:json)?\s*\n?(?P<body>.*?)\n```",
        text,
    )
    if not match:
        return None
    try:
        return json.loads(match.group("body"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _extract_narrative_evidence_excerpt(text: str) -> str:
    match = re.search(
        r"(?ms)^## Narrative Evidence\s*\n+(?P<body>.*?)(?:\n## |\Z)",
        text,
    )
    if not match:
        return ""

    lines = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            lines.append(stripped.lstrip(">").strip())
        elif lines and stripped:
            break
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _source_units_match_excerpt(source_units: List[Dict[str, Any]], excerpt: str) -> bool:
    """Validate persisted block-relative positions against the visible slice."""
    if not source_units or not excerpt:
        return False
    try:
        base = int(source_units[0]["start_pos"])
        for unit in source_units:
            start = int(unit["start_pos"]) - base
            end = int(unit["end_pos"]) - base
            if start < 0 or end > len(excerpt) or excerpt[start:end] != unit["text"]:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _score_excerpt(excerpt: str) -> tuple[float, List[str]]:
    score = 5.0
    reasons: List[str] = []
    penalties: List[str] = []

    norm = excerpt.lower()

    if _has_metric(excerpt):
        score += 1.5
        reasons.append("specific_metric")

    if _has_financial_term(norm):
        score += 1.0
        reasons.append("financial_term")

    if _has_product_term(norm):
        score += 1.0
        reasons.append("product_term")

    if _has_application_term(norm):
        score += 0.5
        reasons.append("application_name")

    if _has_rd_term(norm):
        score += 0.5
        reasons.append("rd_term")

    if _has_strategy_term(norm):
        score += 0.5
        reasons.append("concrete_strategy")

    if _is_complete_sentence(excerpt):
        score += 0.5
        reasons.append("complete_sentence")

    # Penalties
    if _is_boilerplate(norm):
        score -= 1.5
        penalties.append("boilerplate")

    if _is_table_fragment(excerpt):
        score -= 1.5
        penalties.append("table_fragment")

    if _is_dangling(excerpt):
        score -= 0.5
        penalties.append("dangling_snippet")

    if len(excerpt) < 15:
        score -= 1.0
        penalties.append("too_short")

    if len(excerpt) > 300:
        score -= 0.5
        penalties.append("too_long")

    score = max(0.0, min(10.0, score))
    return round(score, 2), reasons + penalties


def _has_metric(text: str) -> bool:
    return bool(
        re.search(
            r"\d+(?:\.\d+)?\s*(?:[%％‰]|个?百分点|倍)",
            text,
        )
        or re.search(
            r"\d+(?:\.\d+)?\s*(?:亿元?|万元?|万|亿|只|颗|台|套|个|件)",
            text,
        )
    )


def _has_financial_term(text: str) -> bool:
    return any(term in text for term in _FINANCIAL_TERMS)


def _has_product_term(text: str) -> bool:
    lowered = text.lower()
    if any(term.lower() in lowered for term in DEFAULT_HIGH_VALUE_TERMS):
        return True
    for pattern in _PRODUCT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _has_application_term(text: str) -> bool:
    return any(term in text for term in _APPLICATION_TERMS)


def _has_rd_term(text: str) -> bool:
    return any(term in text for term in _RD_TERMS)


def _has_strategy_term(text: str) -> bool:
    return any(term in text for term in _STRATEGY_TERMS)


def _is_complete_sentence(text: str) -> bool:
    return len(text) >= 15 and text[-1] in (".", "?", "!", "。", "？", "！")


def _is_boilerplate(text: str) -> bool:
    if "适用" in text or "不适用" in text:
        return True
    # Generic slogans without concrete numbers are penalized.
    if "核心竞争力" in text and not re.search(r"\d", text):
        return True
    return False


def _is_table_fragment(text: str) -> bool:
    return text.count("|") >= 3 or "\t" in text


def _is_dangling(text: str) -> bool:
    return not _is_complete_sentence(text) and len(text) < 40


def _normalize_for_similarity(text: str) -> str:
    """Lowercase ASCII and replace punctuation with spaces for near-duplicate ranking."""
    lowered = text.lower()
    # Keep word characters (including CJK) and whitespace.
    normalized = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def _token_set(text: str) -> Set[str]:
    return set(_normalize_for_similarity(text).split())


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _deduplicate_records(records: List[_CardRecord]) -> List[_CardRecord]:
    """Drop exact duplicates and near-duplicates (token Jaccard >= 0.85)."""
    sorted_records = sorted(
        records,
        key=lambda r: (-r.quality_score, r.card_id),
    )
    kept: List[_CardRecord] = []
    seen_normalizations: Set[str] = set()

    for record in sorted_records:
        normalized = _normalize_for_similarity(record.excerpt)
        if normalized in seen_normalizations:
            continue
        seen_normalizations.add(normalized)

        tokens = _token_set(record.excerpt)
        is_near_dup = False
        for other in kept:
            if _jaccard(tokens, _token_set(other.excerpt)) >= 0.85:
                is_near_dup = True
                break
        if not is_near_dup:
            kept.append(record)

    return sorted(kept, key=_record_sort_key)


def _record_identity_keys(record: _CardRecord) -> Set[str]:
    card_id = str(record.card.get("card_id") or "").strip()
    return {f"card:{card_id}"} if card_id else set()


_ACTIONABLE_SHORT_RELATIONS = (
    "量产", "量產", "验证", "驗證", "认证", "認證", "交付", "供货", "供貨", "导入", "導入",
    "定点", "定點", "发布", "發佈", "签订合同", "簽訂合同", "回款", "采购", "採購", "销售", "銷售",
    "出货", "出貨", "投产", "主要系", "由于", "由於", "所致", "因此", "从而",
)
_TABLE_HEADERS = ("项目", "单位", "变动比例", "研发人员", "期初", "期末", "学历", "年龄构成", "资本化")
_FRAGMENT_ENDINGS = ("及", "和", "或", "、", "，", ":", "：", "项目", "方面", "比例")


def _classify_legacy_fragments(excerpt: str, source_block_id: str, v2_records: List[_CardRecord]) -> List[Dict[str, Any]]:
    text = normalize_annual_source_text(excerpt)
    tail = annual_source_tail(text)
    fragments = [tail] if tail else [match.group(0).strip() for match in re.finditer(r".+?(?:[。；;！？!?]|$)", text)]
    result = []
    for raw_fragment in filter(None, fragments):
        fragment = annual_source_tail(raw_fragment) or raw_fragment
        normalized = normalize_annual_source_text(fragment)
        reason = _invalid_legacy_reason(fragment)
        proof = [] if reason else _proof_unit_ids(normalized, source_block_id, v2_records)
        result.append({"original": fragment, "normalized": normalized, "status": "covered" if proof else "invalid_legacy" if reason else "actionable_uncovered", "proof_unit_ids": proof, "reason": "exact_source_units" if proof else reason or "uncovered_anchor"})
    return result


def _proof_unit_ids(fragment: str, source_block_id: str, v2_records: List[_CardRecord]) -> List[str]:
    source, units, previous = "", [], None
    for unit in sorted((unit for record in v2_records if record.source_block_id == source_block_id for unit in record.card.get("source_units", []) or []), key=lambda unit: (unit.get("ordinal", 0), unit.get("start_pos", 0))):
        if previous is not None and unit["ordinal"] != previous + 1:
            source, units = "", []
        previous = unit["ordinal"]
        text = normalize_annual_source_text(unit.get("text", ""))
        source += text
        units.append((str(unit.get("unit_id") or ""), len(text)))
        start = source.find(fragment)
        if start >= 0:
            end, offset, proof = start + len(fragment), 0, []
            for unit_id, length in units:
                if offset < end and offset + length > start:
                    proof.append(unit_id)
                offset += length
            return proof
    return []


def _invalid_legacy_reason(fragment: str) -> str | None:
    compact = re.sub(r"\s+", "", fragment)
    terminal = fragment.endswith(("。", "；", ";", "！", "？", "!", "?"))
    if not compact or (ANNUAL_CHECKBOX_MARKER_RUN_RE.search(fragment) and not annual_source_tail(fragment)):
        return "incomplete_checkbox"
    if re.match(r"^年\d{1,2}\s*月", fragment) or "…" in fragment or (
        not terminal and not _actionable_short_clause(compact)
    ):
        return "truncated_fragment"
    if re.fullmatch(r"\d+[、.．][^，,；;:：]{2,30}[。.]?", compact):
        return "section_label"
    if re.search(r"年度报告(?:全文)?障", compact):
        return "ocr_splice"
    seams = len(re.findall(r"[一-鿿]\s+[一-鿿]", fragment))
    if seams >= 4 and seams / max(len(compact), 1) > 0.05:
        return "table_fragment"
    latin = re.findall(r"[A-Z]{2,}", fragment)
    if seams >= 2 and len(latin) != len(set(latin)) and re.search(r"(?:系列产品及型|的等产品)", compact):
        return "table_fragment"
    if sum(header in fragment for header in _TABLE_HEADERS) >= 3 and len(re.findall(r"\d+(?:[,.]\d+)*", fragment)) >= 6:
        return "table_fragment"
    if re.match(r"^[，、:：;；和及或但]", compact) and not (re.search(r"(?:公司|本公司|集团|集團|[A-Za-z]{1,3}\d{2,}|\d(?:\.\d)?[GT])", compact) or _has_metric(compact)):
        return "dangling_lead"
    if not fragment.endswith(("。", "；", ";", "！", "？", "!", "?")) and compact.endswith(_FRAGMENT_ENDINGS) and not _actionable_short_clause(compact):
        return "dangling_tail"
    if len(compact) < 12 and not _actionable_short_clause(compact):
        return "underspecified_short"
    return None if has_concrete_annual_anchor(compact) else "no_concrete_anchor"
def _actionable_short_clause(text: str) -> bool:
    relation = any(token in text for token in _ACTIONABLE_SHORT_RELATIONS)
    named_product = any(pattern.search(text) for pattern in _PRODUCT_PATTERNS)
    return relation and (named_product or (_has_metric(text) and any(token in text for token in ("主要系", "由于", "由於", "所致"))) or ("公司" in text or "客户" in text))


def _record_sort_key(record: _CardRecord) -> tuple[Any, ...]:
    return (
        record.argument_family,
        -record.quality_score,
        _natural_text_key(record.source_block_id),
        tuple(str(item) for item in (record.card.get("source_unit_ids") or [])),
        record.card_id,
        record.path.name,
    )


def _natural_text_key(value: str) -> tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", str(value))
    )


def _count_by_family(records: List[_CardRecord]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        family = record.argument_family or "unknown"
        counts[family] = counts.get(family, 0) + 1
    return counts


def _record_to_dict(record: _CardRecord) -> Dict[str, Any]:
    payload = dict(record.card)
    payload.update({
        "card_id": record.card_id,
        "title": record.title,
        "excerpt": record.excerpt,
        "quality_score": (
            record.card.get("quality_score")
            if record.is_v2 and "quality_score" in record.card
            else record.quality_score
        ),
        "quality_reasons": list(record.quality_reasons),
        "source_type": NARRATIVE_CARD_SOURCE_TYPE,
        "source_credit": record.source_credit,
        "synthesis_display_only": True,
        "report_year": record.report_year,
        "report_type": record.report_type,
        "source_block_id": record.source_block_id,
    })
    if record.is_v2:
        payload["selection_diagnostics"] = dict(
            record.card.get("selection_diagnostics") or {
                "score_parts": record.card.get("score_parts") or {},
                "selection_reason": record.card.get("selection_reason") or "",
            }
        )
    payload.pop("card_type", None)
    return payload


def _clean_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _as_int(value: Any, default: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_dir_segment(value: str) -> str:
    cleaned = re.sub(r"[\\/:\*\?\"<>\|\r\n\t]+", "_", str(value or "")).strip(" ._")
    return cleaned or "unknown"
