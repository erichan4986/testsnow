from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from broker_research_digest_synthesis_items import (
    load_broker_research_digest_synthesis_items,
)
from source_adapter import SynthesisItem


def _write_broker_note(
    base_dir: Path,
    stock_name: str = "测试股",
    code: str = "000001",
    viewpoint_cluster: str = "business_driver_product_mix",
    card_type: str = "broker_core_view",
    title: str = "测试研报",
    report_title: str = "测试报告",
    institution: str = "测试证券",
    publish_time: str = "2026-06-01",
    excerpt: str = "核心观点测试摘录。",
    display_only: bool = False,
    source_type: str = "broker_research",
    confirmed_fact: bool = False,
    scoring_eligible: bool = False,
    risk_score_eligible: bool = False,
    source_credit: int = 72,
    claim_status: str = "professional_analysis",
) -> Path:
    notes_dir = base_dir / "10-Stocks" / stock_name / "broker_research_digest"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / f"{publish_time}-{institution}-{card_type}.md"
    path.write_text(
        "---\n"
        f"stock: {stock_name}\n"
        f"code: {code}\n"
        f"source_type: {source_type}\n"
        f"card_type: {card_type}\n"
        f"title: {title}\n"
        f"report_title: {report_title}\n"
        f"institution: {institution}\n"
        f"publish_time: {publish_time}\n"
        f"source_credit: {source_credit}\n"
        f"claim_status: {claim_status}\n"
        f"confirmed_fact: {'true' if confirmed_fact else 'false'}\n"
        f"scoring_eligible: {'true' if scoring_eligible else 'false'}\n"
        f"risk_score_eligible: {'true' if risk_score_eligible else 'false'}\n"
        f"display_only: {'true' if display_only else 'false'}\n"
        f"viewpoint_cluster: {viewpoint_cluster}\n"
        f"report_length_class: short\n"
        "---\n\n"
        f"# {stock_name} broker research digest\n\n"
        "## Broker Research Excerpt\n\n"
        f"> {excerpt}\n\n"
        "## Source\n\n"
        f"- institution: {institution}\n",
        encoding="utf-8",
    )
    return path


def test_reader_parses_broker_digest_note_into_synthesis_item(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        excerpt="我们预计公司2026年营收增长30%。",
        institution="国信证券",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, SynthesisItem)
    assert "营收增长30%" in item.content
    assert item.author == "国信证券"
    assert item.source_platform == "券商研报"
    assert item.publish_time == "2026-06-01"
    assert item.extra.get("source_type") == "broker_research"
    assert item.extra.get("source_credit") == 72
    assert item.extra.get("claim_status") == "professional_analysis"
    assert item.extra.get("confirmed_fact") is False
    assert item.extra.get("scoring_eligible") is False
    assert item.extra.get("risk_score_eligible") is False
    assert item.extra.get("synthesis_display_only") is True
    assert item.extra.get("viewpoint_cluster") == "business_driver_product_mix"


def test_reader_rejects_non_broker_source_type(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        source_type="periodic_report_narrative_evidence",
        excerpt="年报摘录。",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []


def test_reader_rejects_note_missing_guardrail_frontmatter(tmp_path: Path) -> None:
    notes_dir = tmp_path / "10-Stocks" / "测试股" / "broker_research_digest"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / "missing-guardrails.md").write_text(
        "---\n"
        "source_type: broker_research\n"
        "card_type: broker_core_view\n"
        "title: 测试研报\n"
        "report_title: 测试报告\n"
        "institution: 测试证券\n"
        "publish_time: 2026-06-01\n"
        "source_credit: 72\n"
        "claim_status: professional_analysis\n"
        "confirmed_fact: false\n"
        "---\n\n"
        "## Broker Research Excerpt\n\n"
        "> 缺少 scoring/risk/display guardrail 的 note 不应进入。\n",
        encoding="utf-8",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []


def test_reader_rejects_note_with_guardrail_flag_true(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        confirmed_fact=True,
        excerpt="不应进入。",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []


def test_reader_rejects_display_only_notes(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        display_only=True,
        excerpt="仅展示用，不应进入。",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []


def test_reader_dedupes_by_viewpoint_cluster(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        publish_time="2026-06-01",
        institution="券商A",
        viewpoint_cluster="business_driver_product_mix",
        excerpt="A观点。",
    )
    _write_broker_note(
        tmp_path,
        publish_time="2026-06-02",
        institution="券商B",
        viewpoint_cluster="business_driver_product_mix",
        excerpt="B观点（同cluster）。",
    )
    _write_broker_note(
        tmp_path,
        publish_time="2026-06-03",
        institution="券商C",
        viewpoint_cluster="earnings_forecast",
        excerpt="C观点（不同cluster）。",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
        max_items=5,
    )

    clusters = [item.extra.get("viewpoint_cluster") for item in items]
    assert clusters.count("business_driver_product_mix") == 1
    assert "earnings_forecast" in clusters


def test_reader_respects_max_display_items(tmp_path: Path) -> None:
    for i in range(7):
        _write_broker_note(
            tmp_path,
            publish_time=f"2026-06-{i+1:02d}",
            institution=f"券商{i}",
            viewpoint_cluster=f"cluster_{i}",
            excerpt=f"观点{i}。",
        )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
        max_items=5,
    )

    assert len(items) == 5


def test_reader_returns_empty_when_notes_dir_missing(tmp_path: Path) -> None:
    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []


def test_reader_skips_notes_with_wrong_source_credit(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        source_credit=95,
        excerpt="高信用不应进入。",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []


def test_reader_skips_notes_with_scoring_eligible_true(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        scoring_eligible=True,
        excerpt="评分eligible不应进入。",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )
    assert items == []
