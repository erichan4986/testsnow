from __future__ import annotations

import sys
from pathlib import Path

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

    assert len(pack["selected_narrative_cards"]) == 1
    selected = pack["selected_narrative_cards"][0]
    assert selected["card_type"] == "rd_product_progress"
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

    selected_types = [c["card_type"] for c in pack["selected_narrative_cards"]]
    assert selected_types.count("rd_product_progress") >= 2
    assert selected_types.count("business_model") <= 4


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
        filename="2025-annual-uncategorized-0.md",
        card_type="",
        title="其他内容",
        card_id="periodic:000001:2025:annual:narrative:uncategorized:0",
        body_excerpt="一段补充描述。",
    )

    pack_one = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=1,
        per_type_limit=3,
    )
    assert pack_one["selected_narrative_cards"][0]["card_type"] == "rd_product_progress"

    pack_two = build_annual_report_material_pack(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=2,
        per_type_limit=3,
    )
    types = [c["card_type"] for c in pack_two["selected_narrative_cards"]]
    assert "rd_product_progress" in types
    assert "uncategorized" in types


def test_build_pack_diagnostics_skipped_high_value(tmp_path: Path) -> None:
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

    skipped = pack["diagnostics"].get("skipped_high_value", [])
    assert skipped
    terms = {s["term"] for s in skipped}
    assert "Robotaxi" in terms or "A2000" in terms


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
    assert item.extra["card_type"] == "rd_product_progress"


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

    selected = pack["selected_narrative_cards"][0]
    assert selected["card_type"] == "rd_product_progress"
    assert selected["quality_score"] > 0
    assert any(r in ("product_term", "specific_metric", "application_name", "rd_term") for r in selected["quality_reasons"])
