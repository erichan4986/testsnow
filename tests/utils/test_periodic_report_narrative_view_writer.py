from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import periodic_report_narrative_view_writer as view_writer  # noqa: E402
from periodic_report_narrative_pack_store import (  # noqa: E402
    PeriodicNarrativePackStorageError,
    write_periodic_report_narrative_pack,
)
from periodic_report_narrative_view_writer import (  # noqa: E402
    PeriodicNarrativeViewError,
    build_periodic_report_narrative_view,
    write_periodic_report_narrative_view,
)


def _card(
    index: int,
    family: str,
    excerpt: str,
    *,
    complete: bool = True,
    score: float = 5,
) -> dict:
    block_id = f"block-{index}"
    unit_id = f"{block_id}:u0"
    return {
        "schema_version": "periodic_report_narrative_evidence_card.v2",
        "selection_version": "annual_argument_selection.v2",
        "card_id": f"annual-argument:{index:020d}",
        "argument_family": family,
        "argument_complete": complete,
        "title": f"材料 {index}",
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
        "fact_anchors": [f"事实 {index}"],
        "secondary_signals": [],
        "score_parts": {"anchored_fact": 1},
        "quality_score": score,
        "selection_reason": f"test:{family}",
        "source_type": "periodic_report_narrative_evidence",
        "source_credit": 75,
        "report_year": 2025,
        "report_type": "annual",
    }


def _pack(cards: list[dict]) -> dict:
    return {
        "schema_version": "periodic_report_narrative_evidence_cards.v2",
        "selection_version": "annual_argument_selection.v2",
        "stock_code": "300308",
        "stock_name": "中际旭创",
        "report_year": 2025,
        "report_type": "annual",
        "cards": cards,
        "candidate_cards": list(cards),
        "diagnostics": {"candidate_count": len(cards)},
    }


def _write_pack(tmp_path: Path, cards: list[dict]):
    return write_periodic_report_narrative_pack(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack(cards),
        base_dir=tmp_path,
    )


def test_build_view_reads_pack_and_renders_bounded_ranked_families(tmp_path: Path) -> None:
    duplicate = "公司主营业务 覆盖云数据中心客户。"
    cards = [
        _card(1, "business_structure", "低分但完整。", score=1),
        _card(2, "business_structure", "高分但不完整。", complete=False, score=99),
        _card(3, "business_structure", duplicate, score=8),
        _card(4, "business_structure", "公司主营业务  覆盖云数据中心客户。", score=7),
        _card(5, "business_structure", "第五条业务材料。", score=6),
        _card(6, "business_structure", "第六条业务材料。", score=5),
        _card(7, "technology_product_progress", "第一行技术事实。\n第二行仍完整保留。", score=9),
    ]
    pack_result = _write_pack(tmp_path, cards)
    before = {path: path.read_bytes() for path in (pack_result.pack_path, pack_result.manifest_path)}

    projection = build_periodic_report_narrative_view(
        stock_name="中际旭创",
        stock_code="300308",
        report_year=2025,
        report_type="annual",
        base_dir=tmp_path,
    )

    assert projection.pack_relative_path == "periodic_narrative_packs/2025-annual.json"
    assert projection.total_cards == 7
    assert projection.displayed_cards == 5
    assert projection.family_counts["business_structure"] == (6, 4)
    assert projection.family_counts["technology_product_progress"] == (1, 1)
    assert "generated_projection: true" in projection.markdown
    assert "family_business_structure_total: 6" in projection.markdown
    assert "## 业务结构（4 / 6）" in projection.markdown
    assert "## 经营变化（0 / 0）" in projection.markdown
    assert "低分但完整。" in projection.markdown
    assert "高分但不完整。" not in projection.markdown
    assert projection.markdown.count("云数据中心客户") == 1
    assert "> 第一行技术事实。\n> 第二行仍完整保留。" in projection.markdown
    assert "source_units" not in projection.markdown
    assert "Selection Diagnostics" not in projection.markdown
    assert not projection.view_path.exists()
    assert {path: path.read_bytes() for path in before} == before


def test_empty_pack_builds_all_empty_family_sections(tmp_path: Path) -> None:
    _write_pack(tmp_path, [])

    projection = build_periodic_report_narrative_view(
        stock_name="中际旭创",
        stock_code="300308",
        report_year=2025,
        report_type="annual",
        base_dir=tmp_path,
    )

    assert projection.total_cards == 0
    assert projection.displayed_cards == 0
    assert len(projection.family_counts) == 5
    assert all(counts == (0, 0) for counts in projection.family_counts.values())
    assert projection.markdown.count("（0 / 0）") == 5


def test_write_view_reports_created_unchanged_and_updated(tmp_path: Path) -> None:
    pack_result = _write_pack(tmp_path, [_card(1, "business_structure", "第一版业务材料。")])

    first = write_periodic_report_narrative_view(
        stock_name="中际旭创", stock_code="300308", report_year=2025,
        report_type="annual", base_dir=tmp_path,
    )
    first_bytes = first.view_path.read_bytes()
    second = write_periodic_report_narrative_view(
        stock_name="中际旭创", stock_code="300308", report_year=2025,
        report_type="annual", base_dir=tmp_path,
    )
    second_bytes = second.view_path.read_bytes()
    _write_pack(tmp_path, [_card(2, "business_structure", "第二版业务材料。")])
    third = write_periodic_report_narrative_view(
        stock_name="中际旭创", stock_code="300308", report_year=2025,
        report_type="annual", base_dir=tmp_path,
    )

    assert first.state == "created"
    assert second.state == "unchanged"
    assert second_bytes == first_bytes
    assert third.state == "updated"
    assert "第二版业务材料" in third.view_path.read_text(encoding="utf-8")
    assert pack_result.manifest_path.exists()


def test_missing_period_and_invalid_pack_fail_closed(tmp_path: Path) -> None:
    result = _write_pack(tmp_path, [_card(1, "business_structure", "业务材料。")])

    with pytest.raises(PeriodicNarrativeViewError, match="view_period_not_found"):
        build_periodic_report_narrative_view(
            stock_name="中际旭创", stock_code="300308", report_year=2024,
            report_type="annual", base_dir=tmp_path,
        )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    manifest["periods_sha256"] = "broken"
    result.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(PeriodicNarrativePackStorageError, match="invalid_manifest"):
        build_periodic_report_narrative_view(
            stock_name="中际旭创", stock_code="300308", report_year=2025,
            report_type="annual", base_dir=tmp_path,
        )


def test_build_view_uses_aligned_manifest_entry_path(monkeypatch, tmp_path: Path) -> None:
    card = _card(1, "business_structure", "业务材料。")
    envelope = {
        "report_year": 2025,
        "report_type": "annual",
        "cards": [card],
        "integrity": {"cards_sha256": "a" * 64},
    }
    monkeypatch.setattr(
        view_writer,
        "load_validated_periodic_narrative_pack_set",
        lambda **_kwargs: {
            "entries": [{"pack_path": "periodic_narrative_packs/custom-period.json"}],
            "packs": [envelope],
            "cards": [card],
        },
    )

    projection = build_periodic_report_narrative_view(
        stock_name="中际旭创", stock_code="300308", report_year=2025,
        report_type="annual", base_dir=tmp_path,
    )

    assert projection.pack_relative_path == "periodic_narrative_packs/custom-period.json"
    assert projection.view_path.name == "custom-period.md"
    assert 'pack_path: "periodic_narrative_packs/custom-period.json"' in projection.markdown


def test_atomic_write_failure_preserves_prior_view_and_removes_temp(
    monkeypatch, tmp_path: Path,
) -> None:
    _write_pack(tmp_path, [_card(1, "business_structure", "业务材料。")])
    result = write_periodic_report_narrative_view(
        stock_name="中际旭创", stock_code="300308", report_year=2025,
        report_type="annual", base_dir=tmp_path,
    )
    original = result.view_path.read_bytes()
    _write_pack(tmp_path, [_card(2, "business_structure", "更新材料。")])

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(PeriodicNarrativeViewError, match="view_write_failed"):
        write_periodic_report_narrative_view(
            stock_name="中际旭创", stock_code="300308", report_year=2025,
            report_type="annual", base_dir=tmp_path,
        )

    assert result.view_path.read_bytes() == original
    assert not result.view_path.with_name(f".{result.view_path.name}.tmp").exists()


def test_view_directory_creation_failure_is_typed(monkeypatch, tmp_path: Path) -> None:
    _write_pack(tmp_path, [_card(1, "business_structure", "业务材料。")])
    original_mkdir = Path.mkdir

    def fail_view_directory(self, *args, **kwargs):
        if self.name == view_writer.VIEW_DIRNAME:
            raise OSError("mkdir failed")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_view_directory)

    with pytest.raises(PeriodicNarrativeViewError, match="view_write_failed") as exc_info:
        write_periodic_report_narrative_view(
            stock_name="中际旭创", stock_code="300308", report_year=2025,
            report_type="annual", base_dir=tmp_path,
        )

    assert isinstance(exc_info.value.__cause__, OSError)


def test_existing_view_read_failure_is_typed(monkeypatch, tmp_path: Path) -> None:
    _write_pack(tmp_path, [_card(1, "business_structure", "业务材料。")])
    result = write_periodic_report_narrative_view(
        stock_name="中际旭创", stock_code="300308", report_year=2025,
        report_type="annual", base_dir=tmp_path,
    )
    original_read_bytes = Path.read_bytes

    def fail_view_read(self):
        if self == result.view_path:
            raise OSError("read failed")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fail_view_read)

    with pytest.raises(PeriodicNarrativeViewError, match="view_write_failed") as exc_info:
        write_periodic_report_narrative_view(
            stock_name="中际旭创", stock_code="300308", report_year=2025,
            report_type="annual", base_dir=tmp_path,
        )

    assert isinstance(exc_info.value.__cause__, OSError)
