from __future__ import annotations
import hashlib
import sys
from pathlib import Path
import json

import pytest

import annual_report_material_pack as material_pack_module

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from annual_report_material_pack import (
    build_annual_report_material_pack,
    selected_cards_to_synthesis_items,
)
from periodic_report_narrative_evidence_cards import build_periodic_report_narrative_evidence_cards
from periodic_report_narrative_pack_store import PeriodicNarrativePackStorageError, write_periodic_report_narrative_pack


def _cards_dir(base: Path, stock_name: str = "测试股") -> Path:
    return base / "10-Stocks" / stock_name / "periodic_narrative_cards"


def _write_note(
    base: Path,
    *,
    stock_name: str = "测试股",
    filename: str = "2025-annual-management-market-view-0.md",
    card_type: str = "management_market_view",
    title: str = "管理层市场判断",
    card_id: str | None = None,
    body_excerpt: str = "公司年报显示，AI 需求推动产品升级，毛利率承压但客户验证推进。",
    source_type: str = "periodic_report_narrative_evidence",
    report_year: str = "2025",
    report_type: str = "annual",
    source_block_id: str = "market_demand_outlook-0",
) -> Path:
    path = _cards_dir(base, stock_name) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if card_id is None:
        card_id = f"periodic:000001:2025:annual:narrative:{card_type}:0"
    path.write_text(
        "---\n"
        f"stock: {stock_name}\n"
        "code: 000001\n"
        f"source_type: {source_type}\n"
        f"card_id: {card_id}\n"
        "schema_version: periodic_report_narrative_evidence_card.v1\n"
        f"card_type: {card_type}\n"
        f"title: {title}\n"
        f"report_year: {report_year}\n"
        f"report_type: {report_type}\n"
        "source_credit: 75\n"
        f"source_block_id: {source_block_id}\n"
        "evidence_refs:\n"
        f"  - {source_block_id}\n"
        "source_excerpt_hash: \"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"\n"
        "knowledge_fact_status: narrative_evidence\n"
        "knowledge_eligible: false\n"
        "knowledge_persisted: true\n"
        "synthesis_eligible: false\n"
        "experimental: true\n"
        "---\n\n"
        f"# {stock_name} 2025 annual {card_type}\n\n"
        "## Narrative Evidence\n\n"
        f"> {body_excerpt}\n\n"
        "## Source\n\n"
        "- source_credit: 75\n",
        encoding="utf-8",
    )
    return path


def _write_v2_note(
    base: Path,
    *,
    filename: str,
    card_id: str,
    family: str = "technology_product_progress",
    source_block_id: str = "rd_product_progress-0",
    complete: bool = True,
    quality_score: int = 6,
    source_units: list[dict] | None = None,
    source_excerpt: str | None = None,
) -> Path:
    if source_units is None:
        text = f"产品 {card_id} 完成客户验证。"
        source_units = [{
            "unit_id": f"{source_block_id}:u0",
            "block_id": source_block_id,
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": len(text),
            "text": text,
        }]
    excerpt = source_excerpt if source_excerpt is not None else "".join(unit["text"] for unit in source_units)
    card = {
        "schema_version": "periodic_report_narrative_evidence_card.v2",
        "selection_version": "annual_argument_selection.v2",
        "source_type": "periodic_report_narrative_evidence",
        "card_id": card_id,
        "argument_family": family,
        "argument_complete": complete,
        "title": f"{family} title",
        "report_year": 2025,
        "report_type": "annual",
        "source_block_id": source_block_id,
        "source_unit_ids": [unit["unit_id"] for unit in source_units],
        "fact_anchors": ["客户验证"],
        "secondary_signals": ["market_competition_outlook"],
        "source_excerpt": excerpt,
        "source_credit": 75,
        "quality_score": quality_score,
        "source_units": source_units,
        "score_parts": {"anchored_fact": 1, "argument_complete": 4 if complete else 0},
        "selection_reason": f"signal:{family}",
    }
    path = _cards_dir(base) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "stock: 测试股\n"
        "code: 000001\n"
        "source_type: periodic_report_narrative_evidence\n"
        f"card_id: {card_id}\n"
        f"schema_version: {card['schema_version']}\n"
        f"selection_version: {card['selection_version']}\n"
        f"argument_family: {family}\n"
        f"argument_complete: {'true' if complete else 'false'}\n"
        f"title: {card['title']}\n"
        "report_year: 2025\n"
        "report_type: annual\n"
        "source_credit: 75\n"
        f"source_block_id: {source_block_id}\n"
        "source_unit_ids:\n"
        + "".join(f"  - {unit['unit_id']}\n" for unit in source_units)
        + "fact_anchors:\n  - 客户验证\n"
        + "secondary_signals:\n  - market_competition_outlook\n"
        + "quality_score: " + str(quality_score) + "\n"
        + "knowledge_fact_status: narrative_evidence\nknowledge_eligible: false\nknowledge_persisted: true\nsynthesis_eligible: false\nexperimental: true\n---\n\n"
        + f"# 测试股 2025 annual {family}\n\n## Narrative Evidence\n\n> {excerpt}\n\n"
        + "## Source Units\n\n```json\n"
        + json.dumps(source_units, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n\n## Selection Diagnostics\n\n```json\n"
        + json.dumps({"score_parts": card["score_parts"], "selection_reason": card["selection_reason"]}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    return path


def _unit_decision(block_id: str, unit_id: str, text: str, *, disposition="selected", reason="selected", card_id="current:1"):
    return {
        "source_block_id": block_id,
        "source_unit_id": unit_id,
        "source_text_hash": hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest(),
        "source_order": int(unit_id.rsplit("u", 1)[-1]) if ":u" in unit_id else 0,
        "disposition": disposition,
        "reason": reason,
        "selected_by_card_ids": [card_id] if disposition == "selected" else [],
    }


def test_classify_orphan_resolves_unique_reindexed_source_sequence(tmp_path):
    text = "A2000芯片已完成客户验证。"
    _write_v2_note(
        tmp_path,
        filename="old.md",
        card_id="old:1",
        source_block_id="old-block",
        source_units=[{
            "unit_id": "old-block:u9", "block_id": "old-block", "ordinal": 9,
            "start_pos": 0, "end_pos": len(text), "text": text,
        }],
    )

    result = material_pack_module.classify_periodic_narrative_v2_notes(
        stock_name="测试股",
        producer_cards=[{"card_id": "current:1", "source_unit_ids": ["new-block:u0"]}],
        source_unit_decisions=[_unit_decision("new-block", "new-block:u0", text)],
        base_dir=tmp_path,
    )

    assert result["stale_resolved_selected"][0]["mapped_source_unit_ids"] == ["new-block:u0"]
    assert result["stale_resolved_selected"][0]["source_unit_resolutions"] == [{
        "source_unit_id": "new-block:u0", "disposition": "selected",
        "reason": "selected", "selected_by_card_ids": ["current:1"],
    }]
    assert result["stale_source_ambiguous"] == []


def test_classify_orphan_fails_closed_on_ambiguous_source_sequence(tmp_path):
    text = "A2000芯片已完成客户验证。"
    _write_v2_note(
        tmp_path,
        filename="old.md",
        card_id="old:1",
        source_block_id="old-block",
        source_units=[{
            "unit_id": "old-block:u9", "block_id": "old-block", "ordinal": 9,
            "start_pos": 0, "end_pos": len(text), "text": text,
        }],
    )
    decisions = [
        _unit_decision("new-a", "new-a:u0", text, card_id="current:a"),
        _unit_decision("new-b", "new-b:u0", text, card_id="current:b"),
    ]

    result = material_pack_module.classify_periodic_narrative_v2_notes(
        stock_name="测试股", producer_cards=[], source_unit_decisions=decisions,
        base_dir=tmp_path,
    )

    assert [item["card_id"] for item in result["stale_source_ambiguous"]] == ["old:1"]


def test_classify_orphan_only_resolves_direct_archive_safe_rejection(tmp_path):
    text = "公司需遵守自律监管指引中的行业信息披露要求。"
    _write_v2_note(
        tmp_path,
        filename="old.md",
        card_id="old:1",
        source_block_id="regulatory",
        source_units=[{
            "unit_id": "regulatory:u0", "block_id": "regulatory", "ordinal": 0,
            "start_pos": 0, "end_pos": len(text), "text": text,
        }],
    )
    decision = _unit_decision(
        "regulatory", "regulatory:u0", text,
        disposition="rejected", reason="regulatory_disclosure", card_id="",
    )

    resolved = material_pack_module.classify_periodic_narrative_v2_notes(
        stock_name="测试股", producer_cards=[], source_unit_decisions=[decision],
        base_dir=tmp_path,
    )
    decision["reason"] = "audit_or_policy"
    blocked = material_pack_module.classify_periodic_narrative_v2_notes(
        stock_name="测试股", producer_cards=[], source_unit_decisions=[decision],
        base_dir=tmp_path,
    )

    assert [item["card_id"] for item in resolved["stale_resolved_structural"]] == ["old:1"]
    assert [item["card_id"] for item in blocked["stale_recovery_required"]] == ["old:1"]


def _write_producer_cards(base: Path, result: dict) -> None:
    for index, card in enumerate(result["cards"]):
        _write_v2_note(
            base,
            filename=f"producer-{index}.md",
            card_id=card["card_id"],
            family=card["argument_family"],
            complete=card["argument_complete"],
            source_block_id=card["source_block_id"],
            source_excerpt=card["source_excerpt"],
            source_units=card["source_units"],
            quality_score=card["quality_score"],
        )


def test_build_pack_reads_excerpt_from_body_blockquote(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        body_excerpt="这是正文 blockquote 里的真实摘录，不在 frontmatter 中。",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=16,
        per_type_limit=3,
    )

    assert pack["schema_version"] == "annual_report_material_pack.v1"
    assert pack["stock_name"] == "测试股"
    assert len(pack["selected_narrative_cards"]) == 1
    card = pack["selected_narrative_cards"][0]
    assert "真实摘录" in card["excerpt"]
    assert "source_excerpt_hash" not in card["excerpt"]
    assert card["source_type"] == "periodic_report_narrative_evidence"
    assert card["source_credit"] == 75
    assert card["synthesis_display_only"] is True


def test_build_pack_is_uncapped_and_preserves_v2_order_and_fields(tmp_path: Path) -> None:
    for index in range(14):
        _write_v2_note(
            tmp_path,
            filename=f"2025-annual-family-{index}.md",
            card_id=f"annual-argument:{index:020d}",
            family=("business_structure" if index % 2 else "technology_product_progress"),
            source_block_id=f"block-{index}",
            complete=index % 3 != 0,
            quality_score=index,
        )

    pack = build_annual_report_material_pack(
        stock_name="测试股", base_dir=tmp_path, max_cards=1, per_type_limit=1
    )
    cards = pack["selected_narrative_cards"]
    assert len(cards) == 14
    assert [card["card_id"] for card in cards] == [
        card["card_id"] for card in sorted(
            cards,
            key=lambda card: (
                card["argument_family"],
                -card["quality_score"],
                card["source_block_id"],
                tuple(card["source_unit_ids"]),
                card["card_id"],
            ),
        )
    ]
    assert all("card_type" not in card for card in cards)
    assert cards[0]["source_units"][0]["unit_id"] == cards[0]["source_unit_ids"][0]
    assert cards[0]["selection_diagnostics"]["selection_reason"].startswith("signal:")


def test_v2_note_shadows_matching_v1_note_without_adapter_use(tmp_path: Path) -> None:
    card_id = "annual-argument:shadowed-card"
    _write_note(
        tmp_path,
        filename="2025-annual-management-market-view-0.md",
        card_id=card_id,
        body_excerpt="旧版摘录不应被选中。",
    )
    _write_v2_note(
        tmp_path,
        filename="2025-annual-market-competition-outlook-0.md",
        card_id=card_id,
        family="market_competition_outlook",
        source_block_id="market_demand_outlook-0",
    )

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert [card["card_id"] for card in pack["selected_narrative_cards"]] == [card_id]
    assert pack["selected_narrative_cards"][0]["argument_family"] == "market_competition_outlook"
    assert pack["diagnostics"]["v1_adapter_use_count"] == 0


def test_v2_roundtrip_preserves_units_and_selection_diagnostics(tmp_path: Path) -> None:
    first = "研发投入18%。"
    second = "完成验证。"
    units = [
        {"unit_id": "block-rt:u0", "block_id": "block-rt", "ordinal": 0, "start_pos": 0, "end_pos": len(first), "text": first},
        {"unit_id": "block-rt:u1", "block_id": "block-rt", "ordinal": 1, "start_pos": len(first), "end_pos": len(first) + len(second), "text": second},
    ]
    _write_v2_note(
        tmp_path,
        filename="2025-annual-financial-quality-explanation-0.md",
        card_id="annual-argument:roundtrip",
        family="financial_quality_explanation",
        source_block_id="block-rt",
        source_units=units,
    )
    card = build_annual_report_material_pack(
        stock_name="测试股", base_dir=tmp_path
    )["selected_narrative_cards"][0]
    assert card["source_unit_ids"] == ["block-rt:u0", "block-rt:u1"]
    assert card["source_units"] == units
    assert card["argument_complete"] is True
    assert card["argument_family"] == "financial_quality_explanation"
    assert card["score_parts"] == {"anchored_fact": 1, "argument_complete": 4}
    assert card["selection_diagnostics"]["selection_reason"] == "signal:financial_quality_explanation"


def test_v2_empty_signal_list_roundtrips_and_malformed_units_are_rejected(tmp_path: Path) -> None:
    path = _write_v2_note(
        tmp_path,
        filename="2025-annual-empty-signals.md",
        card_id="annual-argument:empty-signals",
        source_block_id="empty",
        source_units=[{
            "unit_id": "empty:u0", "block_id": "empty", "ordinal": 0,
            "start_pos": 0, "end_pos": len("产品完成验证。"), "text": "产品完成验证。",
        }],
    )
    text = path.read_text(encoding="utf-8").replace(
        "secondary_signals:\n  - market_competition_outlook\n",
        "secondary_signals: []\n",
    )
    path.write_text(text, encoding="utf-8")

    valid = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert len(valid["selected_narrative_cards"]) == 1

    _write_v2_note(
        tmp_path,
        filename="2025-annual-malformed-units.md",
        card_id="annual-argument:malformed-units",
        source_units=[{
            "unit_id": "bad:u0", "block_id": "bad", "ordinal": 0,
            "start_pos": 999, "end_pos": 1001, "text": "伪造",
        }],
        source_excerpt="真实摘录。",
    )
    invalid = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert [card["card_id"] for card in invalid["selected_narrative_cards"]] == [
        "annual-argument:empty-signals",
    ]


def test_same_block_different_excerpt_does_not_shadow_v1(tmp_path: Path) -> None:
    _write_note(tmp_path, card_id="legacy:same-block", body_excerpt="公司主营高速光模块并服务云计算客户。")
    _write_v2_note(
        tmp_path,
        filename="2025-annual-market-competition-outlook-different.md",
        card_id="annual-argument:different-excerpt",
        family="market_competition_outlook",
        source_block_id="market_demand_outlook-0",
    )

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert len(pack["selected_narrative_cards"]) == 2
    assert pack["diagnostics"]["v1_adapter_use_count"] == 1


def test_build_pack_quality_prefers_specific_product_metric_cards(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-business-model-0.md",
        card_type="business_model",
        title="主营业务与产品",
        card_id="periodic:000001:2025:annual:narrative:business_model:0",
        body_excerpt="公司主营高速光模块并服务云计算客户。",
    )
    _write_note(
        tmp_path,
        filename="2025-annual-rd-product-progress-0.md",
        card_type="rd_product_progress",
        title="研发与产品进展",
        card_id="periodic:000001:2025:annual:narrative:rd_product_progress:0",
        body_excerpt="A2000 芯片已通过客户验证，毛利率同比提升 5 个百分点。",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=1,
        per_type_limit=3,
    )

    assert len(pack["selected_narrative_cards"]) == 2
    selected = next(
        card for card in pack["selected_narrative_cards"]
        if card["argument_family"] == "technology_product_progress"
    )
    assert selected["quality_score"] > 0
    assert "specific_metric" in selected["quality_reasons"] or "financial_term" in selected["quality_reasons"]


def test_build_pack_dedups_exact_duplicates(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-management-market-view-0.md",
        card_id="periodic:000001:2025:annual:narrative:management_market_view:0",
        body_excerpt="客户流失与净流出风险词只应进入 display synthesis。",
    )
    _write_note(
        tmp_path,
        filename="2025-annual-management-market-view-1.md",
        card_id="periodic:000001:2025:annual:narrative:management_market_view:1",
        body_excerpt="客户流失与净流出风险词只应进入 display synthesis。",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=16,
        per_type_limit=3,
    )

    assert pack["diagnostics"]["cards_seen"] == 2
    assert pack["diagnostics"]["cards_selected"] == 1


def test_build_pack_dedups_near_duplicate_high_jaccard(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-management-market-view-0.md",
        card_id="periodic:000001:2025:annual:narrative:management_market_view:0",
        body_excerpt="A2000 芯片已通过客户验证，毛利率同比提升 5 个百分点。",
    )
    _write_note(
        tmp_path,
        filename="2025-annual-management-market-view-1.md",
        card_id="periodic:000001:2025:annual:narrative:management_market_view:1",
        body_excerpt="A2000 芯片已通过客户验证，毛利率同比提升 5 个百分点",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=16,
        per_type_limit=3,
    )

    assert pack["diagnostics"]["cards_seen"] == 2
    assert pack["diagnostics"]["cards_selected"] == 1


def test_build_pack_type_balance_prevents_single_type_domination(tmp_path: Path) -> None:
    for i in range(6):
        _write_note(
            tmp_path,
            filename=f"2025-annual-business-model-{i}.md",
            card_type="business_model",
            title="主营业务与产品",
            card_id=f"periodic:000001:2025:annual:narrative:business_model:{i}",
            body_excerpt=f"公司主营业务模式产品线{i}并服务云计算客户。",
        )
    for i in range(2):
        _write_note(
            tmp_path,
            filename=f"2025-annual-rd-product-progress-{i}.md",
            card_type="rd_product_progress",
            title="研发与产品进展",
            card_id=f"periodic:000001:2025:annual:narrative:rd_product_progress:{i}",
            body_excerpt=f"A2000 芯片进展 {i}，毛利率提升。",
        )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=6,
        per_type_limit=2,
    )

    selected_families = [c["argument_family"] for c in pack["selected_narrative_cards"]]
    assert len(selected_families) == 8
    assert selected_families.count("technology_product_progress") == 2
    assert selected_families.count("business_structure") == 6


def test_build_pack_stable_ordering_is_repeatable(tmp_path: Path) -> None:
    for i in range(5):
        _write_note(
            tmp_path,
            filename=f"2025-annual-business-model-{i}.md",
            card_type="business_model",
            title="主营业务与产品",
            card_id=f"periodic:000001:2025:annual:narrative:business_model:{i}",
            body_excerpt=f"业务模式摘录 {i}。",
        )

    pack1 = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=6,
        per_type_limit=2,
    )
    pack2 = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=6,
        per_type_limit=2,
    )

    ids1 = [c["card_id"] for c in pack1["selected_narrative_cards"]]
    ids2 = [c["card_id"] for c in pack2["selected_narrative_cards"]]
    assert ids1 == ids2


def test_build_pack_uncategorized_participates_after_typed(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-rd-product-progress-0.md",
        card_type="rd_product_progress",
        title="研发与产品进展",
        card_id="periodic:000001:2025:annual:narrative:rd_product_progress:0",
        body_excerpt="A2000 芯片已通过验证。",
    )
    _write_note(
        tmp_path,
        filename="2025-annual-business-model-0.md",
        card_type="business_model",
        title="其他内容",
        card_id="periodic:000001:2025:annual:narrative:business_model:0",
        body_excerpt="公司主营独立补充产品并服务客户。",
    )

    pack_one = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=1,
        per_type_limit=3,
    )
    assert pack_one["selected_narrative_cards"][0]["argument_family"] == "business_structure"

    pack_two = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=2,
        per_type_limit=3,
    )
    families = [c["argument_family"] for c in pack_two["selected_narrative_cards"]]
    assert "technology_product_progress" in families
    assert "business_structure" in families


def test_build_pack_diagnostics_have_no_budget_skips(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-rd-product-progress-0.md",
        card_type="rd_product_progress",
        title="研发与产品进展",
        card_id="periodic:000001:2025:annual:narrative:rd_product_progress:0",
        body_excerpt="A2000 芯片已通过验证。",
    )
    _write_note(
        tmp_path,
        filename="2025-annual-market-outlook-0.md",
        card_type="market_outlook",
        title="市场前景判断",
        card_id="periodic:000001:2025:annual:narrative:market_outlook:0",
        body_excerpt="Robotaxi 市场预计快速增长。",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=1,
        per_type_limit=1,
    )

    assert len(pack["selected_narrative_cards"]) == 2
    assert "skipped_high_value" not in pack["diagnostics"]


def test_build_pack_no_cards_returns_empty_pack(tmp_path: Path) -> None:
    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=16,
        per_type_limit=3,
    )

    assert pack["selected_narrative_cards"] == []
    assert pack["diagnostics"]["cards_seen"] == 0
    assert pack["diagnostics"]["cards_selected"] == 0


def test_selected_cards_to_synthesis_items_preserves_display_only_metadata(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-rd-product-progress-0.md",
        card_type="rd_product_progress",
        title="研发与产品进展",
        card_id="periodic:000001:2025:annual:narrative:rd_product_progress:0",
        body_excerpt="A2000 芯片已通过验证。",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=16,
        per_type_limit=3,
    )
    items = selected_cards_to_synthesis_items(pack["selected_narrative_cards"])

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "定期报告叙事卡片"
    assert item.author == "公司年报"
    assert item.extra["source_type"] == "periodic_report_narrative_evidence"
    assert item.extra["source_credit"] == 75
    assert item.extra["verification_status"] == "professional_analysis"
    assert item.extra["claim_status"] == "professional_analysis"
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["synthesis_eligible"] is False
    assert item.extra["synthesis_display_only"] is True
    assert item.extra["experimental"] is True
    assert item.extra["argument_family"] == "technology_product_progress"


def test_public_note_reader_returns_the_validated_v2_card(tmp_path: Path) -> None:
    path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:0123456789abcdef0123",
    )

    card = material_pack_module.read_periodic_narrative_card_note(path)

    assert card is not None
    assert card["card_id"] == "annual-argument:0123456789abcdef0123"
    assert card["source_excerpt"] == "产品 annual-argument:0123456789abcdef0123 完成客户验证。"


def test_public_note_reader_preserves_quoted_numeric_anchor_as_string(tmp_path: Path) -> None:
    path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:numeric-anchor",
    )
    text = path.read_text(encoding="utf-8").replace(
        "fact_anchors:\n  - 客户验证\n", 'fact_anchors:\n  - "2025"\n',
    )
    path.write_text(text, encoding="utf-8")

    card = material_pack_module.read_periodic_narrative_card_note(path)

    assert card is not None
    assert card["fact_anchors"] == ["2025"]


def _producer_pack(card: dict) -> dict:
    return {
        "schema_version": "periodic_report_narrative_evidence_cards.v2",
        "selection_version": "annual_argument_selection.v2",
        "stock_code": "000001",
        "stock_name": "测试股",
        "report_year": 2025,
        "report_type": "annual",
        "cards": [card],
        "candidate_cards": [card],
        "diagnostics": {"source_units_seen": len(card["source_units"])},
    }


def test_classify_v2_notes_uses_fingerprint_and_writer_path_tiebreaker(tmp_path: Path) -> None:
    active_path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:classification",
    )
    card = material_pack_module.read_periodic_narrative_card_note(active_path)
    assert card is not None
    _write_v2_note(
        tmp_path,
        filename="duplicate.md",
        card_id="annual-argument:classification",
    )
    _write_v2_note(
        tmp_path,
        filename="reindexed.md",
        card_id="annual-argument:classification",
        quality_score=9,
    )
    _write_v2_note(
        tmp_path,
        filename="orphan.md",
        card_id="annual-argument:orphan",
        source_block_id="retired-source-0",
    )
    invalid_path = _cards_dir(tmp_path) / "invalid.md"
    invalid_path.write_text(
        "---\nsource_type: periodic_report_narrative_evidence\n"
        "schema_version: periodic_report_narrative_evidence_card.v2\n---\n",
        encoding="utf-8",
    )

    result = material_pack_module.classify_periodic_narrative_v2_notes(
        stock_name="测试股",
        producer_cards=[card],
        base_dir=tmp_path,
    )

    assert [Path(item["path"]).name for item in result["active_v2"]] == [active_path.name]
    assert [Path(item["path"]).name for item in result["stale_duplicate"]] == ["duplicate.md"]
    assert [Path(item["path"]).name for item in result["stale_reindexed"]] == ["reindexed.md"]
    assert [Path(item["path"]).name for item in result["stale_orphan"]] == ["orphan.md"]
    assert [Path(item["path"]).name for item in result["stale_invalid"]] == ["invalid.md"]
    assert result["missing_active_card_ids"] == []


def test_classify_v2_notes_marks_orphan_as_source_covered_when_units_survive(tmp_path: Path) -> None:
    units = [
        {
            "unit_id": "competitive_position-0:u3",
            "block_id": "competitive_position-0",
            "ordinal": 3,
            "start_pos": 0,
            "end_pos": len("产品矩阵。"),
            "text": "产品矩阵。",
        },
        {
            "unit_id": "competitive_position-0:u4",
            "block_id": "competitive_position-0",
            "ordinal": 4,
            "start_pos": len("产品矩阵。"),
            "end_pos": len("产品矩阵。客户覆盖。"),
            "text": "客户覆盖。",
        },
    ]
    canonical_path = _write_v2_note(
        tmp_path,
        filename="2025-annual-market-competition-outlook-0.md",
        card_id="annual-argument:11111111111111111111",
        family="market_competition_outlook",
        source_block_id="competitive_position-0",
        source_units=units,
    )
    canonical = material_pack_module.read_periodic_narrative_card_note(canonical_path)
    assert canonical is not None
    _write_v2_note(
        tmp_path,
        filename="covered-orphan.md",
        card_id="annual-argument:22222222222222222222",
        family="business_structure",
        source_block_id="competitive_position-0",
        source_units=[units[0]],
    )
    missing_unit = {**units[0], "unit_id": "competitive_position-0:u9", "ordinal": 9}
    _write_v2_note(
        tmp_path,
        filename="uncovered-orphan.md",
        card_id="annual-argument:33333333333333333333",
        source_block_id="competitive_position-0",
        source_units=[missing_unit],
    )

    result = material_pack_module.classify_periodic_narrative_v2_notes(
        stock_name="测试股",
        producer_cards=[canonical],
        base_dir=tmp_path,
    )

    assert [Path(item["path"]).name for item in result["stale_source_covered"]] == ["covered-orphan.md"]
    assert result["stale_source_covered"][0]["covered_by_card_ids"] == ["annual-argument:11111111111111111111"]
    assert [Path(item["path"]).name for item in result["stale_orphan"]] == ["uncovered-orphan.md"]


def test_pack_shadow_reuses_material_selection_and_v1_diagnostics(tmp_path: Path) -> None:
    path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:shadow",
    )
    card = material_pack_module.read_periodic_narrative_card_note(path)
    assert card is not None
    _write_note(
        tmp_path,
        filename="legacy.md",
        card_id="legacy:uncovered",
        body_excerpt="公司主营业务为高端光通信收发模块的研发、生产及销售。",
    )
    write_periodic_report_narrative_pack(
        stock_name="测试股",
        stock_code="000001",
        card_pack=_producer_pack(card),
        base_dir=tmp_path,
    )

    legacy = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    shadow = material_pack_module.build_annual_report_material_pack_from_pack_shadow(
        stock_name="测试股",
        stock_code="000001",
        base_dir=tmp_path,
    )

    assert shadow["selected_narrative_cards"] == legacy["selected_narrative_cards"]
    assert shadow["diagnostics"]["storage_mode"] == "pack_shadow"
    for key in material_pack_module._V1_DIAGNOSTIC_KEYS:
        assert shadow["diagnostics"][key] == legacy["diagnostics"][key]


def test_default_loader_prefers_validated_pack_over_v2_note_projections(tmp_path: Path) -> None:
    canonical_path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:canonical",
    )
    canonical = material_pack_module.read_periodic_narrative_card_note(canonical_path)
    assert canonical is not None
    _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-stale.md",
        card_id="annual-argument:stale",
    )
    write_periodic_report_narrative_pack(
        stock_name="测试股",
        stock_code="000001",
        card_pack=_producer_pack(canonical),
        base_dir=tmp_path,
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股", stock_code="000001", base_dir=tmp_path
    )

    assert pack["diagnostics"]["storage_mode"] == "pack_first"
    assert [card["card_id"] for card in pack["selected_narrative_cards"]] == [
        "annual-argument:canonical"
    ]


def test_default_loader_without_stock_code_keeps_legacy_v2_compatibility(tmp_path: Path) -> None:
    canonical_path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:canonical",
    )
    canonical = material_pack_module.read_periodic_narrative_card_note(canonical_path)
    assert canonical is not None
    _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-stale.md",
        card_id="annual-argument:stale",
    )
    write_periodic_report_narrative_pack(
        stock_name="测试股",
        stock_code="000001",
        card_pack=_producer_pack(canonical),
        base_dir=tmp_path,
    )

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)

    assert pack["diagnostics"].get("storage_mode") != "pack_first"
    assert {card["card_id"] for card in pack["selected_narrative_cards"]} == {
        "annual-argument:canonical", "annual-argument:stale"
    }


def test_pack_first_fails_closed_after_v2_projections_are_archived(tmp_path: Path) -> None:
    canonical_path = _write_v2_note(
        tmp_path,
        filename="2025-annual-technology-product-progress-0.md",
        card_id="annual-argument:canonical",
    )
    canonical = material_pack_module.read_periodic_narrative_card_note(canonical_path)
    assert canonical is not None
    write_periodic_report_narrative_pack(
        stock_name="测试股",
        stock_code="000001",
        card_pack=_producer_pack(canonical),
        base_dir=tmp_path,
    )
    canonical_path.unlink()
    pack_path = tmp_path / "10-Stocks" / "测试股" / "periodic_narrative_packs" / "2025-annual.json"
    pack_path.write_text("{", encoding="utf-8")

    with pytest.raises(PeriodicNarrativePackStorageError, match="invalid_json"):
        build_annual_report_material_pack(
            stock_name="测试股", stock_code="000001", base_dir=tmp_path
        )


def test_build_pack_quality_scores_analog_chip_company(tmp_path: Path) -> None:
    """圣邦股份-like analog chip vocabulary should score without hardcoded AI terms."""
    _write_note(
        tmp_path,
        filename="2025-annual-business-model-0.md",
        card_type="business_model",
        title="主营业务与产品",
        card_id="periodic:000001:2025:annual:narrative:business_model:0",
        body_excerpt="公司坚持高质量发展。",
    )
    _write_note(
        tmp_path,
        filename="2025-annual-rd-product-progress-0.md",
        card_type="rd_product_progress",
        title="研发与产品进展",
        card_id="periodic:000001:2025:annual:narrative:rd_product_progress:0",
        body_excerpt="高精度运放和电源管理芯片在工业与汽车领域获得批量订单，研发投入占比 18%。",
    )

    pack = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=1,
        per_type_limit=3,
    )

    selected = next(
        card for card in pack["selected_narrative_cards"]
        if card["argument_family"] == "technology_product_progress"
    )
    assert selected["quality_score"] > 0
    assert any(r in ("product_term", "specific_metric", "application_name", "rd_term") for r in selected["quality_reasons"])


def test_split_v2_source_units_cover_one_legacy_long_excerpt(tmp_path: Path) -> None:
    legacy = "公司拥有38大类6800余款可供销售产品。信号链类模拟芯片覆盖各类运算放大器。"
    _write_note(tmp_path, body_excerpt=legacy, filename="legacy.md")
    _write_v2_note(
        tmp_path, filename="v2.md", card_id="v2:products",
        source_block_id="market_demand_outlook-0", source_excerpt=f"{legacy}附加说明。",
        source_units=[
            {"unit_id": "market_demand_outlook-0:u0", "block_id": "market_demand_outlook-0", "ordinal": 0, "start_pos": 0, "end_pos": 21, "text": "公司拥有38大类6800余款可供销售产品。"},
            {"unit_id": "market_demand_outlook-0:u1", "block_id": "market_demand_outlook-0", "ordinal": 1, "start_pos": 21, "end_pos": len(legacy), "text": "信号链类模拟芯片覆盖各类运算放大器。"},
            {"unit_id": "market_demand_outlook-0:u2", "block_id": "market_demand_outlook-0", "ordinal": 2, "start_pos": len(legacy), "end_pos": len(legacy) + len("附加说明。"), "text": "附加说明。"},
        ],
    )
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert pack["diagnostics"]["v1_needs_recovery_count"] == 0
    assert pack["diagnostics"]["v1_unit_covered_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 0


def test_missing_legacy_fact_remains_adapted_with_recovery_diagnostic(tmp_path: Path) -> None:
    legacy = "公司主营业务为高端光通信收发模块的研发、生产及销售。"
    _write_note(tmp_path, body_excerpt=legacy, filename="legacy.md")
    _write_v2_note(tmp_path, filename="v2.md", card_id="v2:other",
                   source_block_id="market_demand_outlook-0",
                   source_excerpt="行业需求保持增长。")
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert pack["diagnostics"]["v1_needs_recovery_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 1
    assert "高端光通信收发模块" in pack["diagnostics"]["v1_recovery_examples"][0]["fragment"]
    assert (_cards_dir(tmp_path) / "legacy.md").exists()


def test_noncontiguous_v2_units_do_not_prove_one_legacy_fragment(tmp_path: Path) -> None:
    legacy = "公司产品覆盖高速光模块应用领域。"
    _write_note(tmp_path, body_excerpt=legacy, filename="legacy.md")
    _write_v2_note(
        tmp_path,
        filename="v2.md",
        card_id="v2:gapped",
        source_block_id="market_demand_outlook-0",
        source_excerpt=f"{legacy}附加说明。",
        source_units=[
            {
                "unit_id": "market_demand_outlook-0:u0",
                "block_id": "market_demand_outlook-0",
                "ordinal": 0,
                "start_pos": 0,
                "end_pos": 8,
                "text": "公司产品覆盖高速",
            },
            {
                "unit_id": "market_demand_outlook-0:u2",
                "block_id": "market_demand_outlook-0",
                "ordinal": 2,
                "start_pos": 8,
                "end_pos": len(legacy),
                "text": "光模块应用领域。",
            },
            {
                "unit_id": "market_demand_outlook-0:u3",
                "block_id": "market_demand_outlook-0",
                "ordinal": 3,
                "start_pos": len(legacy),
                "end_pos": len(legacy) + len("附加说明。"),
                "text": "附加说明。",
            },
        ],
    )

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)

    assert pack["diagnostics"]["v1_needs_recovery_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 1


def test_checkbox_prefix_is_covered_by_the_v2_complete_tail(tmp_path: Path) -> None:
    legacy = (
        "现金流变动情况 √适用 □不适用 2025年客户付款形式变更为电汇，"
        "主要系经营活动现金流增加所致。"
    )
    tail = "2025年客户付款形式变更为电汇，主要系经营活动现金流增加所致。"
    _write_note(tmp_path, body_excerpt=legacy, filename="legacy.md")
    _write_v2_note(
        tmp_path, filename="v2.md", card_id="v2:cash", family="financial_quality_explanation",
        source_block_id="market_demand_outlook-0", source_excerpt=tail,
        source_units=[{
            "unit_id": "market_demand_outlook-0:u0", "block_id": "market_demand_outlook-0",
            "ordinal": 0, "start_pos": 0, "end_pos": len(tail), "text": tail,
        }],
    )

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)

    assert pack["diagnostics"]["v1_covered_fragment_count"] == 1
    assert pack["diagnostics"]["v1_actionable_needs_recovery_count"] == 0
    assert pack["diagnostics"]["v1_needs_recovery_count"] == 0
    assert pack["diagnostics"]["v1_adapter_use_count"] == 0


def test_invalid_legacy_fragments_do_not_trigger_the_adapter(tmp_path: Path) -> None:
    _write_note(tmp_path, body_excerpt="产品已实现量产", filename="legacy.md")

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)

    assert pack["diagnostics"]["v1_invalid_legacy_fragment_count"] == 1
    assert pack["diagnostics"]["v1_actionable_needs_recovery_count"] == 0
    assert pack["diagnostics"]["v1_adapter_use_count"] == 0


def test_adapter_keeps_only_actionable_fragments_from_a_mixed_legacy_note(tmp_path: Path) -> None:
    actionable = "A2000芯片已进入客户验证阶段。"
    invalid = "产品已实现量产"
    _write_note(tmp_path, body_excerpt=actionable + invalid, filename="legacy.md")

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    adapted = next(card for card in pack["selected_narrative_cards"] if card["card_id"] == "periodic:000001:2025:annual:narrative:management_market_view:0")

    assert adapted["source_excerpt"] == actionable
    assert invalid not in adapted["source_excerpt"]
    assert pack["diagnostics"]["v1_actionable_needs_recovery_count"] == 1
    assert pack["diagnostics"]["v1_invalid_legacy_fragment_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 1


def test_duplicate_actionable_legacy_fragment_is_adapted_once(tmp_path: Path) -> None:
    excerpt = "A2000芯片已进入客户验证阶段。"
    _write_note(tmp_path, filename="legacy-0.md", card_id="legacy:0", body_excerpt=excerpt)
    _write_note(tmp_path, filename="legacy-1.md", card_id="legacy:1", body_excerpt=excerpt)

    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)

    assert pack["diagnostics"]["v1_actionable_needs_recovery_count"] == 1
    assert pack["diagnostics"]["v1_duplicate_legacy_fragment_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 1


def test_annual_coverage_boundary_uses_real_producer_output(tmp_path: Path) -> None:
    tail = "2025年四季度客户付款形式由航信变动为电汇支付，导致两者存在较大差异。"
    legacy = (
        "报告期内公司经营活动产生的现金净流量与本年度净利润存在重大差异的原因说明 "
        + tail
    )
    _write_note(
        tmp_path,
        filename="legacy.md",
        source_block_id="cash_flow_capex_table-0",
        body_excerpt=legacy,
    )
    producer_result = build_periodic_report_narrative_evidence_cards(
        stock_code="000777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack={"document_style": "a_share_annual", "blocks": [{
            "id": "cash_flow_capex_table-0",
            "usage": "cash_flow_capex_table",
            "text": legacy,
        }]},
    )
    _write_producer_cards(tmp_path, producer_result)

    diagnostics = build_annual_report_material_pack(
        stock_name="测试股", base_dir=tmp_path
    )["diagnostics"]

    assert any(
        unit["text"] == tail
        for card in producer_result["cards"]
        for unit in card["source_units"]
    )
    assert diagnostics["v1_covered_fragment_count"] == 1
    assert diagnostics["v1_actionable_needs_recovery_count"] == 0
    assert diagnostics["v1_adapter_use_count"] == 0


@pytest.mark.parametrize("excerpt", (
    "我们辅助驾驶产品的毛利率保持稳定，截至2025",
    "报告期内，公司投资建设年产2,000吨高性能材料项目，扩大生产规模并保障现有",
    "3、历经长周期验证的品质与品牌优势。",
    "部 分产品系列，如霍尔 高灵敏度磁传感器系 角度位置编码器、线 器、线性位置编码 分产品处于小批量生 传感器、TMR传感 列产品 性位置编码器、磁阻 器、磁阻开关传感器 产验证及送样阶段；",
    "EEPROM及DIMM EEPROM系列产品及 型、具有不同容量的 等产品已实现量产；",
    "某某股份有限公司2025年年度报告 障现有产品性能优化的同时增加新产品线研发，缩短成果转化周期。",
))
def test_malformed_legacy_fragments_do_not_trigger_recovery(tmp_path: Path, excerpt: str) -> None:
    _write_note(tmp_path, body_excerpt=excerpt, filename="legacy.md")

    diagnostics = build_annual_report_material_pack(
        stock_name="测试股", base_dir=tmp_path
    )["diagnostics"]

    assert diagnostics["v1_invalid_legacy_fragment_count"] == 1
    assert diagnostics["v1_actionable_needs_recovery_count"] == 0
    assert diagnostics["v1_adapter_use_count"] == 0


def test_each_legacy_fragment_uses_the_same_annual_source_tail_boundary(tmp_path: Path) -> None:
    tail = "因公司产品主要用于航空航天领域，产品性能参数在客户型号定型时即已确定。"
    _write_note(
        tmp_path,
        body_excerpt="2、生产模式 " + tail + "公",
        source_block_id="product_capacity_profile-0",
        filename="legacy.md",
    )
    producer_result = build_periodic_report_narrative_evidence_cards(
        stock_code="000777",
        stock_name="测试股",
        report_year=2025,
        report_type="annual",
        evidence_pack={"document_style": "a_share_annual", "blocks": [{
            "id": "product_capacity_profile-0",
            "usage": "product_capacity_profile",
            "text": "2、生产模式 " + tail,
        }]},
    )
    _write_producer_cards(tmp_path, producer_result)

    diagnostics = build_annual_report_material_pack(
        stock_name="测试股", base_dir=tmp_path
    )["diagnostics"]

    assert diagnostics["v1_covered_fragment_count"] == 1
    assert diagnostics["v1_invalid_legacy_fragment_count"] == 1
    assert diagnostics["v1_actionable_needs_recovery_count"] == 0
    assert diagnostics["v1_adapter_use_count"] == 0
