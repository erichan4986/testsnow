"""Human-readable projection of validated periodic narrative packs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

try:
    from .annual_argument_schema import CANONICAL_FAMILIES, FAMILY_LABELS
    from .periodic_report_narrative_pack_store import (
        load_validated_periodic_narrative_pack_set,
        normalized_source_excerpt_hash,
        periodic_narrative_stock_root,
    )
except ImportError:  # pragma: no cover - script-style imports
    from annual_argument_schema import CANONICAL_FAMILIES, FAMILY_LABELS
    from periodic_report_narrative_pack_store import (
        load_validated_periodic_narrative_pack_set,
        normalized_source_excerpt_hash,
        periodic_narrative_stock_root,
    )


VIEW_DIRNAME = "periodic_narrative_views"
_FAMILY_LIMIT = 4


class PeriodicNarrativeViewError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PeriodicNarrativeViewProjection:
    markdown: str
    view_path: Path
    pack_relative_path: str
    cards_sha256: str
    total_cards: int
    displayed_cards: int
    family_counts: Dict[str, tuple[int, int]]


@dataclass(frozen=True)
class PeriodicNarrativeViewWriteResult:
    state: str
    view_path: Path
    pack_relative_path: str
    cards_sha256: str
    total_cards: int
    displayed_cards: int
    family_counts: Dict[str, tuple[int, int]]


def build_periodic_report_narrative_view(
    *, stock_name: str, stock_code: str, report_year: int,
    report_type: str, base_dir: str | Path,
) -> PeriodicNarrativeViewProjection:
    loaded = load_validated_periodic_narrative_pack_set(
        stock_name=stock_name, stock_code=stock_code, base_dir=base_dir,
    )
    matches = [
        (entry, pack)
        for entry, pack in zip(loaded["entries"], loaded["packs"])
        if pack["report_year"] == int(report_year) and pack["report_type"] == str(report_type)
    ]
    if not matches:
        raise PeriodicNarrativeViewError("view_period_not_found")
    if len(matches) != 1:
        raise PeriodicNarrativeViewError("view_period_ambiguous")

    entry, pack = matches[0]
    cards = pack["cards"]
    family_cards = {family: [] for family in CANONICAL_FAMILIES}
    for index, card in enumerate(cards):
        family_cards[card["argument_family"]].append((index, card))

    selected, counts = {}, {}
    for family in CANONICAL_FAMILIES:
        ranked = sorted(
            family_cards[family],
            key=lambda pair: (
                not pair[1]["argument_complete"],
                -float(pair[1]["quality_score"]),
                -len(pair[1]["source_unit_ids"]),
                pair[0],
                pair[1]["card_id"],
            ),
        )
        unique, seen = [], set()
        for _, card in ranked:
            excerpt_hash = normalized_source_excerpt_hash(card["source_excerpt"])
            if excerpt_hash not in seen:
                unique.append(card)
                seen.add(excerpt_hash)
        selected[family] = unique[:_FAMILY_LIMIT]
        counts[family] = (len(family_cards[family]), len(selected[family]))

    pack_path = str(entry["pack_path"])
    view_path = (
        periodic_narrative_stock_root(base_dir, stock_name)
        / VIEW_DIRNAME
        / f"{Path(pack_path).stem}.md"
    )
    displayed = sum(len(value) for value in selected.values())
    cards_sha256 = str(pack["integrity"]["cards_sha256"])
    markdown = _render_view(
        stock_name=stock_name,
        stock_code=stock_code,
        report_year=int(report_year),
        report_type=str(report_type),
        pack_path=pack_path,
        cards_sha256=cards_sha256,
        total_cards=len(cards),
        displayed_cards=displayed,
        family_counts=counts,
        selected=selected,
    )
    return PeriodicNarrativeViewProjection(
        markdown, view_path, pack_path, cards_sha256, len(cards), displayed, counts,
    )


def write_periodic_report_narrative_view(
    *, stock_name: str, stock_code: str, report_year: int,
    report_type: str, base_dir: str | Path,
) -> PeriodicNarrativeViewWriteResult:
    projection = build_periodic_report_narrative_view(
        stock_name=stock_name, stock_code=stock_code, report_year=report_year,
        report_type=report_type, base_dir=base_dir,
    )
    encoded = projection.markdown.encode("utf-8")
    path = projection.view_path
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        exists = path.exists()
        if exists and path.read_bytes() == encoded:
            state = "unchanged"
        else:
            state = "updated" if exists else "created"
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(encoded)
            temporary.replace(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise PeriodicNarrativeViewError("view_write_failed") from exc
    return PeriodicNarrativeViewWriteResult(
        state, path, projection.pack_relative_path, projection.cards_sha256,
        projection.total_cards, projection.displayed_cards, projection.family_counts,
    )


def _render_view(
    *, stock_name: str, stock_code: str, report_year: int, report_type: str,
    pack_path: str, cards_sha256: str, total_cards: int, displayed_cards: int,
    family_counts: Dict[str, tuple[int, int]], selected: Dict[str, list[dict]],
) -> str:
    lines = [
        "---",
        "generated_projection: true",
        f"stock_name: {json.dumps(stock_name, ensure_ascii=False)}",
        f"stock_code: {json.dumps(stock_code, ensure_ascii=False)}",
        f"report_year: {report_year}",
        f"report_type: {json.dumps(report_type, ensure_ascii=False)}",
        f"pack_path: {json.dumps(pack_path, ensure_ascii=False)}",
        f"cards_sha256: {json.dumps(cards_sha256)}",
        f"total_cards: {total_cards}",
        f"displayed_cards: {displayed_cards}",
    ]
    for family in CANONICAL_FAMILIES:
        total, visible = family_counts[family]
        lines.extend((f"family_{family}_total: {total}", f"family_{family}_displayed: {visible}"))
    lines.extend(("---", "", f"# {stock_name} {report_year} {report_type} 材料视图", ""))
    for family in CANONICAL_FAMILIES:
        total, visible = family_counts[family]
        lines.extend((f"## {FAMILY_LABELS[family]}（{visible} / {total}）", ""))
        for card in selected[family]:
            lines.extend((
                f"### {card['title']}",
                "",
                f"- card_id: `{card['card_id']}`",
                f"- source_block_id: `{card['source_block_id']}`",
                "- source_unit_ids: " + ", ".join(f"`{item}`" for item in card["source_unit_ids"]),
                "",
                *(f"> {line}" for line in card["source_excerpt"].split("\n")),
                "",
            ))
    return "\n".join(lines).rstrip() + "\n"
