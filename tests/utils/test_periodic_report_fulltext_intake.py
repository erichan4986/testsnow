"""Tests for periodic_report_fulltext_intake_skill helper-only integration.

These tests verify that the annual/semiannual full-text experimental path can be
wrapped as Source Intake material-layer items without entering the core pipeline,
scoring, or knowledge base.
"""

import inspect
import importlib
import os
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import report_skills.periodic_report_fulltext_intake_skill as intake_skill
from report_skills.periodic_report_fulltext_intake_skill import (
    _build_stable_fulltext_id,
    _find_latest_periodic_report_cache_file,
    _find_periodic_report_cache_files,
    build_periodic_report_metric_series_from_cache,
    build_periodic_report_fulltext_intake_item,
    build_periodic_report_fulltext_intake_items_from_cache,
)
from source_adapter import SynthesisItem


SAMPLE_FULLTEXT_REPORT = """
第一节 重要提示
本公司及董事会全体成员保证年度报告内容真实、准确、完整。

第二节 公司简介和主要财务指标
营业收入（元） 3,898,054,583.68 3,346,983,120.66 16.46%
归属于上市公司股东的净利润（元） 547,059,403.97 500,247,943.10 9.36%
归属于上市公司股东的扣除非经常性损益的净利润（元） 427,582,529.58 451,159,069.34 -5.23%
经营活动产生的现金流量净额（元） 466,319,946.20 549,337,594.89 -15.11%

第三节 管理层讨论与分析
一、报告期内公司从事的主要业务
公司产品覆盖信号链、电源管理、传感器三大方向，拥有38大类6,800余款可供销售产品。
公司采用“经销为主、直销为辅”的销售模式。公司与经销商的关系属于买断式销售关系。

二、主营业务分析
分产品 营业收入 营业成本 毛利率 营业收入同比增减 毛利率同比增减
信号链产品 1,471,022,875.27 615,285,480.40 58.17% 26.23% -0.13%
电源管理产品 2,379,833,746.57 1,276,179,316.39 46.38% 9.08% -1.43%
前五名客户销售额占年度销售总额 33.13%，第一大客户占比 7.79%。

第十节 财务报告
存货账面价值 1,448,216,300.11 元，占总资产 20.83%。
资产减值损失 -170,237,600.06 元，主要为存货跌价准备。
"""


def _financial_report(revenue: str, net_profit: str, operating_cash_flow: str) -> str:
    return f"""
主要会计数据和财务指标
营业收入 {revenue} 900,000,000.00 11.11%
归属于上市公司股东的净利润 {net_profit} 80,000,000.00 25.00%
经营活动产生的现金流量净额 {operating_cash_flow} 50,000,000.00 20.00%
"""


class SpyChatClient:
    """Records whether it was called."""

    def __init__(self, response_text: str = ""):
        self.response_text = response_text
        self.called = False
        self.prompt = ""

    def chat(self, prompt: str) -> str:
        self.called = True
        self.prompt = prompt
        return self.response_text


def test_intake_skill_uses_public_fulltext_helpers_not_private_ones():
    source = inspect.getsource(intake_skill)
    assert "_build_item_map" not in source
    assert "_empty_fulltext_analysis" not in source
    assert "_backfill_sections_from_product_project_evidence" not in source


def test_builds_item_from_raw_text_without_llm():
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
        publish_time="2026-04-15",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300661&announcementId=1225000001",
    )

    assert isinstance(item, SynthesisItem)
    assert item.title
    assert "定期报告全文" in item.title or "年报" in item.title
    assert item.content
    assert "# 定期报告全文判断摘要" in item.content
    assert "## 必备经营指标摘录" in item.content
    assert "## 必备财务风险指标摘录" in item.content
    assert item.source_platform == "定期报告全文"
    assert item.url
    assert item.publish_time == "2026-04-15"


def test_item_has_fixed_credit_and_status():
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )

    assert item.extra["source_type"] == "periodic_report_fulltext_analysis"
    assert item.extra["source_credit"] == 75
    assert item.extra["verification_status"] == "professional_analysis"
    assert item.extra["claim_status"] == "professional_analysis"
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["report_eligible"] is False
    assert item.extra["experimental"] is True


def test_stable_id_is_deterministic():
    item_a = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )
    item_b = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )
    assert item_a.extra["periodic_report_fulltext_id"] == item_b.extra["periodic_report_fulltext_id"]
    assert item_a.extra["periodic_report_fulltext_id"]


def test_stable_id_differs_by_stock_or_announcement():
    item_a = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )
    item_b = build_periodic_report_fulltext_intake_item(
        stock_code="300777",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )
    item_c = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000002",
    )
    assert item_a.extra["periodic_report_fulltext_id"] != item_b.extra["periodic_report_fulltext_id"]
    assert item_a.extra["periodic_report_fulltext_id"] != item_c.extra["periodic_report_fulltext_id"]


def test_cache_missing_returns_empty_list(tmp_path):
    missing_dir = tmp_path / "no_such_dir"
    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code="300661",
        cache_dir=str(missing_dir),
        report_type="annual_report",
    )
    assert items == []


def test_no_llm_call_by_default():
    client = SpyChatClient(response_text="{}")
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
        llm_client=client,
    )
    assert isinstance(item, SynthesisItem)
    assert client.called is False


def test_llm_call_only_when_explicitly_enabled():
    """When enable_llm=True with a client that returns valid JSON, LLM is used."""
    from periodic_report_fulltext_llm_analysis import (
        FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        FIXED_ANALYSIS_SECTION_TITLES,
    )

    sections_payload = [
        {"title": title, "judgments": []}
        for title in FIXED_ANALYSIS_SECTION_TITLES
    ]
    response = {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "sections": sections_payload,
        "financial_risks": [],
    }
    import json

    client = SpyChatClient(response_text=json.dumps(response, ensure_ascii=False))
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
        enable_llm=True,
        llm_client=client,
    )
    assert isinstance(item, SynthesisItem)
    assert client.called is True


def test_item_is_not_confirmed_fact_or_fact_candidate():
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )
    assert item.extra["verification_status"] != "confirmed_fact"
    assert item.extra.get("claim_status") != "fact_candidate"
    assert "confirmed_fact" not in item.content
    assert "fact_candidate" not in item.content


def test_content_includes_profile_and_rd_backfill():
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="1225000001",
    )
    assert "公司画像" in item.content or "必备经营指标摘录" in item.content
    assert "信号链" in item.content or "电源管理" in item.content


def test_build_items_from_cache_reads_local_file(tmp_path):
    cache_file = tmp_path / "300661_2025_annual_jina.txt"
    cache_file.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")

    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code="300661",
        cache_dir=str(tmp_path),
        report_type="annual_report",
    )
    assert len(items) == 1
    assert items[0].extra["source_type"] == "periodic_report_fulltext_analysis"
    assert items[0].extra["source_credit"] == 75


def test_build_items_from_cache_supports_stock_name_prefixed_files(tmp_path):
    cache_file = tmp_path / "圣邦股份_2025_annual_jina.txt"
    cache_file.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")

    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code="300661",
        stock_name="圣邦股份",
        cache_dir=str(tmp_path),
        report_type="annual_report",
    )

    assert len(items) == 1
    assert items[0].extra["source_type"] == "periodic_report_fulltext_analysis"


def test_build_items_from_cache_supports_hk_subdir_language_suffix(tmp_path):
    hk_dir = tmp_path / "hk"
    hk_dir.mkdir()
    cache_file = hk_dir / "02533_2025_annual_zh_jina.txt"
    cache_file.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")

    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code="02533",
        cache_dir=str(tmp_path),
        report_type="annual_report",
    )

    assert len(items) == 1
    assert items[0].extra["source_type"] == "periodic_report_fulltext_analysis"
    assert items[0].extra["source_domain"] == "hkexnews.hk"


def test_build_item_allows_hk_source_domain():
    item = build_periodic_report_fulltext_intake_item(
        stock_code="02533",
        raw_text=SAMPLE_FULLTEXT_REPORT,
        report_type="annual_report",
        announcement_id="02533_2025_annual_zh_jina",
        source_domain="hkexnews.hk",
    )

    assert item.extra["source_domain"] == "hkexnews.hk"


def test_build_items_prefers_latest_when_multiple_cache_files(tmp_path):
    old = tmp_path / "300661_2025_annual_jina.txt"
    new = tmp_path / "300661_2025_annual_jina-1.txt"
    old.write_text("旧缓存", encoding="utf-8")
    new.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")

    items = build_periodic_report_fulltext_intake_items_from_cache(
        stock_code="300661",
        cache_dir=str(tmp_path),
        report_type="annual_report",
    )
    assert len(items) == 1
    assert "信号链" in items[0].content


def test_cache_history_finder_deduplicates_overlapping_patterns_and_sorts_by_year(tmp_path):
    old = tmp_path / "测试股份_2024_annual_jina.txt"
    new = tmp_path / "测试股份_2025_annual_jina.txt"
    old.write_text(_financial_report("1,000,000,000.00", "100,000,000.00", "80,000,000.00"), encoding="utf-8")
    new.write_text(_financial_report("1,100,000,000.00", "110,000,000.00", "90,000,000.00"), encoding="utf-8")

    files = _find_periodic_report_cache_files(
        stock_code="300001",
        stock_name="测试股份",
        cache_dir=tmp_path,
        report_type="annual_report",
    )

    assert files == [old, new]


def test_builds_metric_series_from_all_local_cache_years(tmp_path):
    (tmp_path / "测试股份_2024_annual_jina.txt").write_text(
        _financial_report("1,000,000,000.00", "100,000,000.00", "80,000,000.00"),
        encoding="utf-8",
    )
    (tmp_path / "测试股份_2025_annual_jina.txt").write_text(
        _financial_report("1,100,000,000.00", "110,000,000.00", "90,000,000.00"),
        encoding="utf-8",
    )

    pack = build_periodic_report_metric_series_from_cache(
        stock_code="300001",
        stock_name="测试股份",
        cache_dir=tmp_path,
        report_type="annual_report",
    )

    revenue = next(row for row in pack["series"] if row["metric_key"] == "revenue")
    assert [point["report_year"] for point in revenue["points"]] == [2024, 2025]
    assert revenue["changes"][0]["growth_rate"] == "10.00%"
    assert pack["source_pack_count"] == 2


def test_metric_series_cache_adapter_returns_well_formed_empty_pack(tmp_path):
    pack = build_periodic_report_metric_series_from_cache(
        stock_code="300001",
        stock_name="测试股份",
        cache_dir=tmp_path,
        report_type="annual_report",
    )

    assert pack["schema_version"] == "periodic_report_metric_series_pack.v1"
    assert pack["source_pack_count"] == 0
    assert pack["series"] == []
    assert pack["derived_series"] == []


def test_metric_series_cache_adapter_isolates_one_cache_processing_failure(tmp_path, monkeypatch):
    good = tmp_path / "测试股份_2024_annual_jina.txt"
    bad = tmp_path / "测试股份_2025_annual_jina.txt"
    good.write_text(
        _financial_report("1,000,000,000.00", "100,000,000.00", "80,000,000.00"),
        encoding="utf-8",
    )
    bad.write_text("BROKEN CACHE", encoding="utf-8")
    intake_module = importlib.import_module(
        "report_skills.periodic_report_fulltext_intake_skill"
    )
    original = intake_module.build_periodic_report_evidence_pack

    def _build_or_raise(text, **kwargs):
        if "BROKEN CACHE" in text:
            raise ValueError("synthetic parser failure")
        return original(text, **kwargs)

    monkeypatch.setattr(intake_module, "build_periodic_report_evidence_pack", _build_or_raise)

    pack = build_periodic_report_metric_series_from_cache(
        stock_code="300001",
        stock_name="测试股份",
        cache_dir=tmp_path,
        report_type="annual_report",
    )

    assert pack["source_pack_count"] == 1
    assert any(row["code"] == "cache_processing_failed" for row in pack["diagnostics"])


def test_latest_cache_selection_remains_mtime_based(tmp_path):
    newer_year_older_mtime = tmp_path / "测试股份_2025_annual_jina.txt"
    older_year_newer_mtime = tmp_path / "测试股份_2024_annual_jina.txt"
    newer_year_older_mtime.write_text("2025", encoding="utf-8")
    older_year_newer_mtime.write_text("2024", encoding="utf-8")
    os.utime(newer_year_older_mtime, ns=(1_000_000_000, 1_000_000_000))
    os.utime(older_year_newer_mtime, ns=(2_000_000_000, 2_000_000_000))

    latest = _find_latest_periodic_report_cache_file(
        stock_code="300001",
        stock_name="测试股份",
        cache_dir=tmp_path,
        report_type="annual_report",
    )

    assert latest == older_year_newer_mtime


def test_latest_cache_selection_breaks_equal_mtime_ties_by_path(tmp_path):
    left = tmp_path / "300001_2025_annual_jina-a.txt"
    right = tmp_path / "300001_2025_annual_jina-b.txt"
    left.write_text("left", encoding="utf-8")
    right.write_text("right", encoding="utf-8")
    os.utime(left, ns=(1_000_000_000, 1_000_000_000))
    os.utime(right, ns=(1_000_000_000, 1_000_000_000))

    assert _find_latest_periodic_report_cache_file(
        stock_code="300001", cache_dir=tmp_path,
    ) == right


def test_empty_raw_text_returns_empty_item():
    item = build_periodic_report_fulltext_intake_item(
        stock_code="300661",
        raw_text="",
        report_type="annual_report",
        announcement_id="1225000001",
    )
    assert isinstance(item, SynthesisItem)
    assert item.extra["source_type"] == "periodic_report_fulltext_analysis"
    assert item.extra["source_credit"] == 75


def test_stable_id_helper_is_pure():
    assert _build_stable_fulltext_id("300661", "1225000001", "annual_report") == _build_stable_fulltext_id("300661", "1225000001", "annual_report")
    assert _build_stable_fulltext_id("300661", "1225000001", "annual_report") != _build_stable_fulltext_id("300661", "1225000001", "semiannual_report")


def test_skill_wrapper_exists():
    from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill

    assert hasattr(periodic_report_fulltext_intake_skill, "__name__")
    assert periodic_report_fulltext_intake_skill.__name__ == "periodic_report_fulltext_intake_skill"


def test_skill_reads_ctx_overrides(tmp_path):
    from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill
    from skill_pipeline import SkillContext

    cache_dir = tmp_path / "custom_cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "300661_2025_semiannual_jina.txt"
    cache_file.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")

    ctx = SkillContext(input={
        "stock_name": "圣邦股份",
        "stock_codes": {"圣邦股份": "300661"},
        "periodic_report_fulltext_cache_dir": str(cache_dir),
        "periodic_report_fulltext_report_type": "semiannual_report",
    })
    result = periodic_report_fulltext_intake_skill(ctx)
    items = result.get("periodic_report_fulltext_items", [])
    assert len(items) == 1
    assert result.get("periodic_report_fulltext_status") == "ok"


def test_skill_builds_filing_core_facts_from_cache(tmp_path):
    from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill
    from skill_pipeline import SkillContext

    cache_dir = tmp_path / "custom_cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "300661_2025_annual_jina.txt"
    cache_file.write_text(
        """
主要会计数据和财务指标
营业收入 3,898,054,583.68 3,346,983,120.66 16.46%
归属于上市公司股东的净利润 547,059,403.97 500,247,943.10 9.36%
经营活动产生的现金流量净额 466,319,946.20 549,337,594.89 -15.11%
""",
        encoding="utf-8",
    )

    ctx = SkillContext(input={
        "stock_name": "圣邦股份",
        "stock_codes": {"圣邦股份": "300661"},
        "periodic_report_fulltext_cache_dir": str(cache_dir),
        "periodic_report_fulltext_report_type": "annual_report",
    })
    result = periodic_report_fulltext_intake_skill(ctx)

    core_facts = result.get("periodic_report_filing_core_facts")
    assert [fact["fact"] for fact in core_facts] == [
        "营业收入",
        "归母净利润",
        "经营现金流量净额",
    ]
    assert core_facts[0]["data"] == "38.98亿元"
    assert core_facts[0]["provenance_status"] == "supported"
    assert core_facts[0]["evidence_type"] == "periodic_report_filing_fact"
    metric_series = result.get("periodic_report_metric_series_pack")
    assert metric_series["schema_version"] == "periodic_report_metric_series_pack.v1"
    assert metric_series["source_pack_count"] == 1
    assert metric_series["report_eligible"] is False
    financial_scan = result.get("periodic_report_financial_scan_pack")
    assert financial_scan["schema_version"] == "periodic_report_financial_scan_pack.v1"
    assert financial_scan["status"] in {"partial", "ready"}
    assert financial_scan["report_eligible"] is False
    assert financial_scan["scoring_eligible"] is False


def test_skill_reads_and_builds_each_cache_material_once_per_run(tmp_path, monkeypatch):
    intake_module = importlib.import_module(
        "report_skills.periodic_report_fulltext_intake_skill"
    )
    cache_dir = tmp_path / "custom_cache"
    cache_dir.mkdir()
    older = cache_dir / "300661_2024_annual_jina.txt"
    latest = cache_dir / "300661_2025_annual_jina.txt"
    older.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")
    latest.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(latest, ns=(2_000_000_000, 2_000_000_000))

    read_counts = Counter()
    evidence_report_types = []
    original_read_text = Path.read_text
    original_evidence_builder = intake_module.build_periodic_report_evidence_pack

    def counted_read_text(path, *args, **kwargs):
        if path.parent == cache_dir:
            read_counts[path.name] += 1
        return original_read_text(path, *args, **kwargs)

    def counted_evidence_builder(text, *, report_type="auto"):
        evidence_report_types.append(report_type)
        return original_evidence_builder(text, report_type=report_type)

    monkeypatch.setattr(Path, "read_text", counted_read_text)
    monkeypatch.setattr(
        intake_module,
        "build_periodic_report_evidence_pack",
        counted_evidence_builder,
    )

    result = intake_module.periodic_report_fulltext_intake_skill(
        intake_module.SkillContext(input={
            "stock_name": "圣邦股份",
            "stock_codes": {"圣邦股份": "300661"},
            "periodic_report_fulltext_cache_dir": str(cache_dir),
            "periodic_report_fulltext_report_type": "annual_report",
        })
    )

    assert result.get("periodic_report_fulltext_status") == "ok"
    assert read_counts == Counter({older.name: 1, latest.name: 1})
    assert Counter(evidence_report_types) == Counter({"annual": 2, "annual_report": 1})


def test_direct_latest_only_cache_wrapper_does_not_read_history(tmp_path, monkeypatch):
    older = tmp_path / "300661_2024_annual_jina.txt"
    latest = tmp_path / "300661_2025_annual_jina.txt"
    older.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")
    latest.write_text(SAMPLE_FULLTEXT_REPORT, encoding="utf-8")
    os.utime(older, ns=(1_000_000_000, 1_000_000_000))
    os.utime(latest, ns=(2_000_000_000, 2_000_000_000))
    reads = Counter()
    original_read_text = Path.read_text

    def counted_read_text(path, *args, **kwargs):
        if path.parent == tmp_path:
            reads[path.name] += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted_read_text)

    items = build_periodic_report_fulltext_intake_items_from_cache(
        "300661", tmp_path, stock_name="圣邦股份",
    )

    assert len(items) == 1
    assert reads == Counter({latest.name: 1})


def test_metric_series_keeps_valid_history_when_one_cache_read_fails(tmp_path, monkeypatch):
    good = tmp_path / "300001_2024_annual_jina.txt"
    bad = tmp_path / "300001_2025_annual_jina.txt"
    good.write_text(_financial_report("1,000,000,000.00", "100,000,000.00", "80,000,000.00"), encoding="utf-8")
    bad.write_text("unreadable", encoding="utf-8")
    original_read_text = Path.read_text

    def fail_one_read(path, *args, **kwargs):
        if path == bad:
            raise OSError("synthetic read failure")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_one_read)
    pack = build_periodic_report_metric_series_from_cache(
        stock_code="300001", stock_name="测试股份", cache_dir=tmp_path,
    )

    assert pack["source_pack_count"] == 1
    assert any(row["code"] == "cache_read_failed" for row in pack["diagnostics"])


def test_skill_publishes_well_formed_empty_financial_scan_without_cache(tmp_path):
    from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill
    from skill_pipeline import SkillContext

    result = periodic_report_fulltext_intake_skill(SkillContext(input={
        "stock_name": "圣邦股份",
        "stock_codes": {"圣邦股份": "300661"},
        "periodic_report_fulltext_cache_dir": str(tmp_path),
        "periodic_report_fulltext_report_type": "annual_report",
    }))

    scan = result.get("periodic_report_financial_scan_pack")
    assert scan["schema_version"] == "periodic_report_financial_scan_pack.v1"
    assert scan["status"] == "empty"
    assert scan["source_series_count"] == 0
    assert scan["findings"] == []


def test_skill_skips_when_stock_code_missing():
    from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill
    from skill_pipeline import SkillContext

    ctx = SkillContext(input={
        "stock_name": "Unknown",
        "stock_codes": {},
    })
    result = periodic_report_fulltext_intake_skill(ctx)
    assert result.get("periodic_report_fulltext_items") == []
    assert result.get("periodic_report_fulltext_status") == "skipped_no_stock_code"
    assert "periodic_report_financial_scan_pack" not in result.output


def test_skill_does_not_pollute_external_evidence():
    from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill
    from skill_pipeline import SkillContext

    ctx = SkillContext(input={
        "stock_name": "圣邦股份",
        "stock_codes": {"圣邦股份": "300661"},
    })
    result = periodic_report_fulltext_intake_skill(ctx)
    assert "external_evidence_keep_items" not in result.output
    assert "external_evidence_demote_items" not in result.output


def test_skill_uses_default_cache_dir_when_no_override():
    from report_skills.periodic_report_fulltext_intake_skill import (
        periodic_report_fulltext_intake_skill,
        _DEFAULT_CACHE_DIR,
    )
    from skill_pipeline import SkillContext

    ctx = SkillContext(input={
        "stock_name": "圣邦股份",
        "stock_codes": {"圣邦股份": "300661"},
    })
    result = periodic_report_fulltext_intake_skill(ctx)
    items = result.get("periodic_report_fulltext_items")
    assert isinstance(items, list)
    assert result.get("periodic_report_fulltext_status") in ("ok", "empty")
    assert _DEFAULT_CACHE_DIR.parts[-3:] == ("data", "raw", "periodic_reports")
