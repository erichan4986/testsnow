"""Annual Report Material Pack.

Deterministic selection, ranking, and deduplication of periodic-report
narrative cards for display-only synthesis.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


SCHEMA_VERSION = "annual_report_material_pack.v1"
NARRATIVE_CARD_SOURCE_TYPE = "periodic_report_narrative_evidence"

# High-value card types are balanced first during selection.
HIGH_VALUE_CARD_TYPES = [
    "rd_product_progress",
    "market_outlook",
    "margin_competitiveness",
    "technology_platform",
    "management_market_view",
]

# Fallback ordering for other known card types.
OTHER_KNOWN_CARD_TYPES = [
    "operation_update",
    "business_model",
    "financial_note",
]

_CARD_TYPE_TITLES = {
    "business_model": "主营业务与产品",
    "operation_update": "经营进展",
    "management_market_view": "管理层市场判断",
    "market_outlook": "市场前景判断",
    "margin_competitiveness": "毛利率与竞争力",
    "technology_platform": "技术平台与研发能力",
    "rd_product_progress": "研发与产品进展",
    "financial_note": "财务备注",
    "uncategorized": "其他年报内容",
}

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
        "card_id",
        "card_type",
        "title",
        "report_year",
        "report_type",
        "excerpt",
        "source_credit",
        "source_block_id",
        "quality_score",
        "quality_reasons",
    )

    def __init__(
        self,
        *,
        path: Path,
        card_id: str,
        card_type: str,
        title: str,
        report_year: str,
        report_type: str,
        excerpt: str,
        source_credit: int,
        source_block_id: str,
        quality_score: float,
        quality_reasons: List[str],
    ) -> None:
        self.path = path
        self.card_id = card_id
        self.card_type = card_type
        self.title = title
        self.report_year = report_year
        self.report_type = report_type
        self.excerpt = excerpt
        self.source_credit = source_credit
        self.source_block_id = source_block_id
        self.quality_score = quality_score
        self.quality_reasons = quality_reasons


def build_annual_report_material_pack(
    *,
    stock_name: str,
    base_dir: str | Path,
    max_cards: int = 16,
    per_type_limit: int = 3,
    high_value_terms: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Build a deterministic, display-only annual-report material pack.

    The pack only reads narrative-card Knowledge notes. It does not call LLMs,
    fetch data, or modify Knowledge.
    """
    max_cards = max(0, int(max_cards))
    per_type_limit = max(1, int(per_type_limit))
    high_value_terms = high_value_terms or DEFAULT_HIGH_VALUE_TERMS
    term_canonical = {t.lower(): t for t in high_value_terms}

    notes_dir = (
        Path(base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "periodic_narrative_cards"
    )

    if not notes_dir.exists():
        return _empty_pack(stock_name)

    records: List[_CardRecord] = []
    for path in sorted(notes_dir.glob("*.md")):
        record = _read_note_as_record(path)
        if record is None:
            continue
        records.append(record)

    if not records:
        return _empty_pack(stock_name)

    by_type_seen: Dict[str, int] = {}
    for r in records:
        by_type_seen[r.card_type] = by_type_seen.get(r.card_type, 0) + 1

    cards_seen = len(records)
    records = _deduplicate_records(records)
    selected = _select_records(
        records,
        max_cards=max_cards,
        per_type_limit=per_type_limit,
    )

    by_type_selected: Dict[str, int] = {}
    for r in selected:
        by_type_selected[r.card_type] = by_type_selected.get(r.card_type, 0) + 1

    skipped_high_value = _build_skipped_high_value(
        records, selected, term_canonical
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "stock_name": stock_name,
        "selected_narrative_cards": [_record_to_dict(r) for r in selected],
        "diagnostics": {
            "cards_seen": cards_seen,
            "cards_selected": len(selected),
            "by_type_seen": by_type_seen,
            "by_type_selected": by_type_selected,
            "skipped_high_value": skipped_high_value,
            "skipped": [],
        },
    }


def selected_cards_to_synthesis_items(
    selected_cards: List[Dict[str, Any]],
) -> List[SynthesisItem]:
    """Convert pack-selected card records to display-only SynthesisItems."""
    items: List[SynthesisItem] = []
    for card in selected_cards:
        report_year = str(card.get("report_year") or "")
        report_type = str(card.get("report_type") or "")
        card_type = str(card.get("card_type") or "")
        title = str(card.get("title") or _CARD_TYPE_TITLES.get(card_type) or "年报叙事卡片")
        items.append(
            SynthesisItem(
                title=f"{report_year} {report_type} | {title}".strip(),
                content=str(card.get("excerpt") or ""),
                author="公司年报",
                source_platform="定期报告叙事卡片",
                url="",
                publish_time=report_year,
                interaction_score=0,
                extra={
                    "source_type": NARRATIVE_CARD_SOURCE_TYPE,
                    "source_credit": int(card.get("source_credit") or 75),
                    "verification_status": "professional_analysis",
                    "claim_status": "professional_analysis",
                    "knowledge_eligible": False,
                    "report_eligible": False,
                    "synthesis_eligible": False,
                    "synthesis_display_only": True,
                    "experimental": True,
                    "card_type": card_type,
                    "card_id": str(card.get("card_id") or ""),
                    "source_block_id": str(card.get("source_block_id") or ""),
                    "report_year": _as_int(report_year, report_year),
                    "report_type": report_type,
                },
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
            "by_type_seen": {},
            "by_type_selected": {},
            "skipped_high_value": [],
            "skipped": [],
        },
    }


def _read_note_as_record(path: Path) -> Optional[_CardRecord]:
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

    card_type = str(frontmatter.get("card_type") or "").strip()
    if not card_type:
        card_type = "uncategorized"

    title = str(frontmatter.get("title") or "").strip()
    report_year = str(frontmatter.get("report_year") or "").strip()
    report_type = str(frontmatter.get("report_type") or "").strip()
    card_id = str(frontmatter.get("card_id") or path.stem)
    source_credit = _as_int(frontmatter.get("source_credit"), 75)
    source_block_id = str(frontmatter.get("source_block_id") or "")

    score, reasons = _score_excerpt(excerpt, card_type)

    return _CardRecord(
        path=path,
        card_id=card_id,
        card_type=card_type,
        title=title,
        report_year=report_year,
        report_type=report_type,
        excerpt=excerpt,
        source_credit=source_credit,
        source_block_id=source_block_id,
        quality_score=score,
        quality_reasons=reasons,
    )


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}

    data: Dict[str, Any] = {}
    for raw_line in match.group(1).splitlines():
        if not raw_line or raw_line.startswith(" ") or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or value == "":
            continue
        data[key] = _clean_scalar(value)
    return data


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


def _score_excerpt(excerpt: str, card_type: str) -> tuple[float, List[str]]:
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

    if card_type in HIGH_VALUE_CARD_TYPES:
        score += 1.0
        reasons.append("card_type_bonus")

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


def _normalize_text(text: str) -> str:
    """Lowercase ASCII and replace punctuation with spaces."""
    lowered = text.lower()
    # Keep word characters (including CJK) and whitespace.
    normalized = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def _token_set(text: str) -> Set[str]:
    return set(_normalize_text(text).split())


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
        normalized = _normalize_text(record.excerpt)
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

    # Return in deterministic order: quality desc, then card_id asc.
    return sorted(kept, key=lambda r: (-r.quality_score, r.card_id))


def _select_records(
    records: List[_CardRecord],
    *,
    max_cards: int,
    per_type_limit: int,
) -> List[_CardRecord]:
    if max_cards <= 0 or not records:
        return []

    type_priority = {t: i for i, t in enumerate(HIGH_VALUE_CARD_TYPES)}
    for i, t in enumerate(OTHER_KNOWN_CARD_TYPES):
        type_priority.setdefault(t, len(HIGH_VALUE_CARD_TYPES) + i)
    type_priority.setdefault("uncategorized", len(HIGH_VALUE_CARD_TYPES) + len(OTHER_KNOWN_CARD_TYPES))

    by_type: Dict[str, List[_CardRecord]] = {}
    for r in records:
        by_type.setdefault(r.card_type, []).append(r)

    for group in by_type.values():
        group.sort(key=lambda r: (-r.quality_score, r.card_id))

    type_order = sorted(
        by_type.keys(),
        key=lambda t: (type_priority.get(t, 999), t),
    )

    selected: List[_CardRecord] = []
    selected_counts: Dict[str, int] = {t: 0 for t in by_type}
    selected_ids: Set[str] = set()

    # Round 1: balanced round-robin up to per_type_limit.
    while len(selected) < max_cards:
        added_any = False
        for card_type in type_order:
            if selected_counts[card_type] >= per_type_limit:
                continue
            for record in by_type[card_type]:
                if record.card_id in selected_ids:
                    continue
                selected.append(record)
                selected_ids.add(record.card_id)
                selected_counts[card_type] += 1
                added_any = True
                break
            if len(selected) >= max_cards:
                break
        if not added_any:
            break

    # Round 2: fill remaining budget with highest-quality unselected cards.
    if len(selected) < max_cards:
        remaining = sorted(
            [r for r in records if r.card_id not in selected_ids],
            key=lambda r: (-r.quality_score, r.card_id),
        )
        selected.extend(remaining[: max_cards - len(selected)])

    return selected


def _build_skipped_high_value(
    records: List[_CardRecord],
    selected: List[_CardRecord],
    term_canonical: Dict[str, str],
) -> List[Dict[str, str]]:
    selected_ids = {r.card_id for r in selected}
    skipped: List[Dict[str, str]] = []
    for record in records:
        if record.card_id in selected_ids:
            continue
        norm = _normalize_text(record.excerpt)
        for lower_term, canonical_term in term_canonical.items():
            if lower_term in norm:
                skipped.append({
                    "term": canonical_term,
                    "reason": "budget_exhausted",
                    "card_id": record.card_id,
                })
                break
    return skipped


def _record_to_dict(record: _CardRecord) -> Dict[str, Any]:
    return {
        "card_id": record.card_id,
        "card_type": record.card_type,
        "title": record.title,
        "excerpt": record.excerpt,
        "quality_score": record.quality_score,
        "quality_reasons": record.quality_reasons,
        "source_type": NARRATIVE_CARD_SOURCE_TYPE,
        "source_credit": record.source_credit,
        "synthesis_display_only": True,
        "report_year": record.report_year,
        "report_type": record.report_type,
        "source_block_id": record.source_block_id,
    }


def _clean_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        value = value[1:-1]
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
