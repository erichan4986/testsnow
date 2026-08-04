from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_narrative_card_synthesis_items import (
    load_periodic_narrative_card_synthesis_items,
)
from periodic_report_narrative_pack_store import (
    PeriodicNarrativePackStorageError,
    write_periodic_report_narrative_pack,
)


def _card(index: int) -> dict:
    block_id = f"block-{index}"
    excerpt = f"产品 {index} 完成客户验证。"
    return {
        "schema_version": "periodic_report_narrative_evidence_card.v2",
        "selection_version": "annual_argument_selection.v2",
        "source_type": "periodic_report_narrative_evidence",
        "card_id": f"annual-argument:{index:020d}",
        "argument_family": "technology_product_progress",
        "argument_complete": True,
        "title": f"产品进展 {index}",
        "report_year": 2025,
        "report_type": "annual",
        "source_block_id": block_id,
        "source_unit_ids": [f"{block_id}:u0"],
        "fact_anchors": ["客户验证"],
        "secondary_signals": ["operating_progress"],
        "source_excerpt": excerpt,
        "source_credit": 75,
        "quality_score": 6,
        "source_units": [{
            "unit_id": f"{block_id}:u0",
            "block_id": block_id,
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": len(excerpt),
            "text": excerpt,
        }],
        "score_parts": {"anchored_fact": 1, "argument_complete": 4},
        "selection_reason": "signal:technology_product_progress",
    }


def _write_pack(base: Path, count: int = 2) -> Path:
    cards = [_card(index) for index in range(count)]
    result = write_periodic_report_narrative_pack(
        stock_name="测试股",
        stock_code="000001",
        card_pack={
            "schema_version": "periodic_report_narrative_evidence_cards.v2",
            "selection_version": "annual_argument_selection.v2",
            "stock_code": "000001",
            "stock_name": "测试股",
            "report_year": 2025,
            "report_type": "annual",
            "cards": cards,
            "candidate_cards": cards,
            "diagnostics": {},
        },
        base_dir=base,
    )
    return result.pack_path


def test_loader_uses_validated_pack_by_default_and_caps_display_items(tmp_path: Path) -> None:
    _write_pack(tmp_path, count=4)

    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股", stock_code="000001", base_dir=tmp_path, max_cards=2
    )

    assert [item.extra["card_id"] for item in items] == [
        "annual-argument:00000000000000000000",
        "annual-argument:00000000000000000001",
    ]
    assert items[0].extra["argument_family"] == "technology_product_progress"
    assert items[0].extra["source_unit_ids"] == ["block-0:u0"]


def test_deprecated_use_pack_flag_cannot_restore_direct_note_loading(tmp_path: Path) -> None:
    _write_pack(tmp_path, count=1)

    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股",
        stock_code="000001",
        base_dir=tmp_path,
        use_pack=False,
    )

    assert [item.extra["card_id"] for item in items] == [
        "annual-argument:00000000000000000000"
    ]


def test_loader_propagates_typed_pack_storage_errors(tmp_path: Path) -> None:
    pack_path = _write_pack(tmp_path, count=1)
    pack_path.write_text("{", encoding="utf-8")

    with pytest.raises(PeriodicNarrativePackStorageError, match="invalid_json"):
        load_periodic_narrative_card_synthesis_items(
            stock_name="测试股", stock_code="000001", base_dir=tmp_path
        )
