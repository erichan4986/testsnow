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
    selection_diagnostics: bool = False,
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
    if selection_diagnostics:
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\n## Selection Diagnostics\n\n"
            "- heading=`核心观点`; score=88; status=selected; reason=selected\n",
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


def test_reader_repairs_common_pdf_ocr_artifacts_from_existing_notes(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        excerpt=(
            "受益于终端客户对算力基础设施的强劲投入，2025 年公司 品出货较快增长，"
            "随着产 方案不断优化，公司营业收入与净利 均同比实现大幅增长，"
            "预计 20 2027 年 800G 光模块需求持续增长，1.6T 光模块需求将迎 强劲增长。"
        ),
        institution="华鑫证券",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )

    assert len(items) == 1
    assert "公司产品出货较快增长" in items[0].content
    assert "产品方案不断优化" in items[0].content
    assert "营业收入与净利润均同比实现大幅增长" in items[0].content
    assert "预计2027年800G光模块需求持续增长" in items[0].content
    assert "1.6T光模块需求将迎来强劲增长" in items[0].content
    assert "公司 品" not in items[0].content
    assert "产 方案" not in items[0].content
    assert "净利 均" not in items[0].content


def test_reader_cleans_legacy_note_without_fabricating_missing_broker_values(
    tmp_path: Path,
) -> None:
    _write_broker_note(
        tmp_path,
        excerpt=(
            "受益于终端 对算力基础设施的投入，销售回款 持续增强。"
            "其中 及1.6T光模块快速放量。"
            "公司实现营收195. 环比分别增长192.1%、47.3%；"
            "实现归母净利润57.3亿元，同比增长262.3%。"
            "公司单季度销售毛利率为46.1%，创下历史新高。"
        ),
        institution="山西证券",
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
    )

    assert len(items) == 1
    content = items[0].content
    assert "终端对算力基础设施" in content
    assert "销售回款持续增强" in content
    assert "其中及1.6T" not in content
    assert "营收195" not in content
    assert "归母净利润57.3亿元，同比增长262.3%" in content
    assert "销售毛利率为46.1%" in content


def test_reader_rejects_legacy_excerpt_with_unclosed_quotation() -> None:
    from broker_research_digest import clean_broker_research_excerpt_text

    damaged = (
        "公司围绕数据中心需求构建产品体系。"
        "业务呈现“存量高景气与结构升级驱动的格局。"
        "公司产品服务于云计算客户。"
    )

    assert clean_broker_research_excerpt_text(
        damaged,
        repair_legacy_artifacts=True,
    ) == ""


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


def test_reader_preserves_same_viewpoint_cluster_across_institutions(tmp_path: Path) -> None:
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
        publish_time="2026-06-04",
        institution="券商B",
        viewpoint_cluster="business_driver_product_mix",
        excerpt="B观点重复。",
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
    assert clusters.count("business_driver_product_mix") == 2
    assert "earnings_forecast" in clusters


def test_reader_prefers_diagnostic_notes_over_stale_same_institution_notes(tmp_path: Path) -> None:
    _write_broker_note(
        tmp_path,
        publish_time="2026-06-01",
        institution="测试证券",
        viewpoint_cluster="",
        excerpt="旧摘录。",
    )
    _write_broker_note(
        tmp_path,
        publish_time="2026-06-02",
        institution="测试证券",
        viewpoint_cluster="business_driver_product_mix",
        excerpt="新摘录，包含更完整的高速光模块论点。",
        selection_diagnostics=True,
    )

    items = load_broker_research_digest_synthesis_items(
        stock_name="测试股",
        base_dir=tmp_path,
        max_items=5,
    )

    text = "\n".join(item.content for item in items)
    assert "新摘录" in text
    assert "旧摘录" not in text


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
