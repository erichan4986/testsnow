"""Load persisted periodic-report narrative cards as display-only synthesis items."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


NARRATIVE_CARD_SOURCE_TYPE = "periodic_report_narrative_evidence"

_CARD_TYPE_TITLES = {
    "business_model": "主营业务与产品",
    "operation_update": "经营进展",
    "management_market_view": "管理层市场判断",
    "market_outlook": "市场前景判断",
    "margin_competitiveness": "毛利率与竞争力",
    "technology_platform": "技术平台与研发能力",
    "rd_product_progress": "研发与产品进展",
    "financial_note": "财务备注",
}


def load_periodic_narrative_card_synthesis_items(
    *,
    stock_name: str,
    base_dir: str | Path,
    max_cards: int = 12,
) -> List[SynthesisItem]:
    """Read narrative-card Knowledge notes and convert them to display items.

    The reader is intentionally read-only. It parses current note-writer output:
    metadata comes from frontmatter, while source excerpts come from the
    ``## Narrative Evidence`` blockquote in the note body.
    """
    notes_dir = (
        Path(base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "periodic_narrative_cards"
    )
    if not notes_dir.exists():
        return []

    items: List[SynthesisItem] = []
    for path in sorted(notes_dir.glob("*.md")):
        item = _read_note_as_item(path)
        if item is None:
            continue
        items.append(item)
        if len(items) >= max_cards:
            break
    return items


def _read_note_as_item(path: Path) -> Optional[SynthesisItem]:
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
    title = str(frontmatter.get("title") or _CARD_TYPE_TITLES.get(card_type) or "年报叙事卡片")
    report_year = str(frontmatter.get("report_year") or "").strip()
    report_type = str(frontmatter.get("report_type") or "").strip()
    source_credit = _as_int(frontmatter.get("source_credit"), 75)

    return SynthesisItem(
        title=f"{report_year} {report_type} | {title}".strip(),
        content=excerpt,
        author="公司年报",
        source_platform="定期报告叙事卡片",
        url="",
        publish_time=report_year,
        interaction_score=0,
        extra={
            "source_type": NARRATIVE_CARD_SOURCE_TYPE,
            "source_credit": source_credit,
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "synthesis_eligible": False,
            "synthesis_display_only": True,
            "experimental": True,
            "card_type": card_type,
            "card_id": str(frontmatter.get("card_id") or ""),
            "source_block_id": str(frontmatter.get("source_block_id") or ""),
            "report_year": _as_int(report_year, report_year),
            "report_type": report_type,
        },
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
