from __future__ import annotations

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from annual_report_material_pack import (
    build_annual_report_material_pack,
    selected_cards_to_synthesis_items,
)


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
        "source_block_id: market_demand_outlook-0\n"
        "evidence_refs:\n"
        "  - market_demand_outlook-0\n"
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
    _write_note(tmp_path, card_id="legacy:same-block", body_excerpt="旧版摘录保留。")
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
        body_excerpt="公司坚持高质量发展，持续提升核心竞争力。",
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
            body_excerpt=f"业务模式摘录 {i}。",
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
        body_excerpt="一段补充描述。",
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
        source_block_id="market_demand_outlook-0", source_excerpt=legacy,
        source_units=[
            {"unit_id": "market_demand_outlook-0:u0", "block_id": "market_demand_outlook-0", "ordinal": 0, "start_pos": 0, "end_pos": 21, "text": "公司拥有38大类6800余款可供销售产品。"},
            {"unit_id": "market_demand_outlook-0:u1", "block_id": "market_demand_outlook-0", "ordinal": 1, "start_pos": 21, "end_pos": len(legacy), "text": "信号链类模拟芯片覆盖各类运算放大器。"},
        ],
    )
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
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
