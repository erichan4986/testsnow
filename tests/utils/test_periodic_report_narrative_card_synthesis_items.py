from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_narrative_card_synthesis_items import (
    load_periodic_narrative_card_synthesis_items,
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
    source_type: str = "periodic_report_narrative_evidence",
    body_excerpt: str = "公司年报显示，AI 需求推动产品升级，毛利率承压但客户验证推进。",
) -> Path:
    path = _cards_dir(base, stock_name) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"stock: {stock_name}\n"
        "code: 000001\n"
        f"source_type: {source_type}\n"
        f"card_id: periodic:000001:2025:annual:narrative:{card_type}:0\n"
        "schema_version: periodic_report_narrative_evidence_card.v1\n"
        f"card_type: {card_type}\n"
        f"title: {title}\n"
        "report_year: 2025\n"
        "report_type: annual\n"
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
        "# 测试股 2025 annual management_market_view\n\n"
        "## Narrative Evidence\n\n"
        f"> {body_excerpt}\n\n"
        "## Source\n\n"
        "- source_credit: 75\n",
        encoding="utf-8",
    )
    return path


def test_loads_narrative_card_note_as_display_synthesis_item(tmp_path: Path) -> None:
    _write_note(tmp_path)

    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "定期报告叙事卡片"
    assert item.title == "2025 annual | 管理层市场判断"
    assert "AI 需求推动产品升级" in item.content
    assert item.extra["source_type"] == "periodic_report_narrative_evidence"
    assert item.extra["source_credit"] == 75
    assert item.extra["verification_status"] == "professional_analysis"
    assert item.extra["claim_status"] == "professional_analysis"
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["report_eligible"] is False
    assert item.extra["synthesis_display_only"] is True
    assert item.extra["synthesis_eligible"] is False
    assert item.extra["card_type"] == "management_market_view"
    assert item.extra["source_block_id"] == "market_demand_outlook-0"


def test_loads_excerpt_from_body_blockquote_not_frontmatter(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        body_excerpt="这是正文 blockquote 里的真实摘录，不在 frontmatter 中。",
    )

    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )

    assert len(items) == 1
    assert "真实摘录" in items[0].content
    assert "source_excerpt_hash" not in items[0].content


def test_skips_non_narrative_or_missing_body_excerpt_notes(tmp_path: Path) -> None:
    _write_note(
        tmp_path,
        filename="2025-annual-filing-fact.md",
        source_type="periodic_report_filing_fact",
    )
    bad = _cards_dir(tmp_path) / "2025-annual-empty.md"
    bad.write_text(
        "---\n"
        "source_type: periodic_report_narrative_evidence\n"
        "card_type: business_model\n"
        "title: 空摘录\n"
        "report_year: 2025\n"
        "report_type: annual\n"
        "source_credit: 75\n"
        "---\n\n"
        "## Narrative Evidence\n\n"
        "没有 blockquote。\n",
        encoding="utf-8",
    )

    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )

    assert items == []


def test_reader_is_read_only_and_caps_order_deterministically(tmp_path: Path) -> None:
    older = _write_note(
        tmp_path,
        filename="2025-annual-business-model-0.md",
        card_type="business_model",
        title="主营业务与产品",
        body_excerpt="业务模式摘录。",
    )
    newer = _write_note(
        tmp_path,
        filename="2025-annual-rd-product-progress-1.md",
        card_type="rd_product_progress",
        title="研发与产品进展",
        body_excerpt="研发进展摘录。",
    )
    before = {
        path: path.read_text(encoding="utf-8")
        for path in (older, newer)
    }

    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
        max_cards=1,
    )

    assert len(items) == 1
    assert items[0].extra["card_type"] == "business_model"
    after = {
        path: path.read_text(encoding="utf-8")
        for path in (older, newer)
    }
    assert after == before
