from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack
from periodic_report_required_financial_metrics import build_required_financial_risk_metrics
from periodic_report_structured_facts import build_periodic_report_structured_fact_pack


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


SIGNED_CASHFLOW_TEXT = """
主要会计数据和财务指标
营业收入 1,000,000,000.00 900,000,000.00 11.11%
归属于上市公司股东的净利润 100,000,000.00 80,000,000.00 25.00%
经营活动产生的现金流量净额 -20,000,000.00 50,000,000.00 -140.00%
"""


HK_REPORT_WITH_CURRENT_STATEMENTS = """
黑芝麻智能股份有限公司
2025 年報

業務回顧
公司在智能汽車場景實現收入增長，其他收入不作為主營收入指標。

綜合損益表
截至 2025 年 12 月 31 日止年度
人民幣千元 人民幣千元
2025 年 2024 年
收入 822,328 535,539
銷售成本 (627,000) (500,000)
毛利 195,328 35,539
年內虧損 (1,200,000) (2,000,000)

綜合現金流量表
截至 2025 年 12 月 31 日止年度
人民幣千元 人民幣千元
2025 年 2024 年
經營活動所用現金淨額 (985,373) (1,300,000)
投資活動所用現金淨額 (10,000) (20,000)
"""


def _fact_pack(raw_text: str, *, stock_code: str = "300000"):
    evidence_pack = build_periodic_report_evidence_pack(raw_text, report_type="annual")
    financial_metrics = build_required_financial_risk_metrics(evidence_pack, raw_text=raw_text)
    return build_periodic_report_structured_fact_pack(
        stock_code=stock_code,
        stock_name="测试股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        required_financial_metrics=financial_metrics,
    )


def test_builds_phase_a_filing_facts_with_evidence_refs() -> None:
    pack = _fact_pack(SIGNED_CASHFLOW_TEXT, stock_code="300001")

    facts = {fact["metric_key"]: fact for fact in pack["filing_facts"]}
    assert set(facts) == {"revenue", "net_profit", "operating_cash_flow"}

    revenue = facts["revenue"]
    assert revenue["schema_version"] == "periodic_report_structured_fact.v1"
    assert revenue["source_type"] == "periodic_report_filing_fact"
    assert revenue["fact_id"] == "periodic:300001:2025:annual:revenue"
    assert revenue["normalized_value"] == "100000.00万元"
    assert revenue["value_basis"] == "as_reported"
    assert revenue["confidence"] == "high"
    assert revenue["source_credit"] == 75
    assert revenue["knowledge_eligible"] is False
    assert revenue["source_block_id"]
    assert revenue["evidence_refs"] == [revenue["source_block_id"]]
    assert "营业收入" in revenue["source_excerpt"]


def test_filing_facts_include_stable_excerpt_and_block_hashes() -> None:
    pack = _fact_pack(SIGNED_CASHFLOW_TEXT, stock_code="300001")

    facts = {fact["metric_key"]: fact for fact in pack["filing_facts"]}
    revenue = facts["revenue"]
    assert re.fullmatch(r"[0-9a-f]{64}", revenue["source_excerpt_hash"])
    assert re.fullmatch(r"[0-9a-f]{64}", revenue["source_block_hash"])
    assert revenue["source_excerpt_hash"] == _normalized_hash(revenue["source_excerpt"])

    evidence_pack = build_periodic_report_evidence_pack(SIGNED_CASHFLOW_TEXT, report_type="annual")
    block_text = next(
        block["text"]
        for block in evidence_pack["blocks"]
        if block["id"] == revenue["source_block_id"]
    )
    assert revenue["source_block_hash"] == _normalized_hash(block_text)


def test_unanchored_required_value_is_skipped_with_diagnostic() -> None:
    evidence_pack = build_periodic_report_evidence_pack("", report_type="annual")
    financial_metrics = build_required_financial_risk_metrics(evidence_pack, raw_text=SIGNED_CASHFLOW_TEXT)

    pack = build_periodic_report_structured_fact_pack(
        stock_code="300002",
        stock_name="测试股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        required_financial_metrics=financial_metrics,
    )

    assert pack["filing_facts"] == []
    assert any(
        diagnostic["code"] == "unanchored_filing_fact"
        and diagnostic["metric_key"] == "revenue"
        for diagnostic in pack["diagnostics"]
    )


def test_signed_cashflow_ratio_preserves_negative_operating_cash_flow() -> None:
    pack = _fact_pack(SIGNED_CASHFLOW_TEXT)

    derived = {
        fact["metric_key"]: fact for fact in pack["derived_facts"]
    }
    ratio = derived["operating_cash_flow_to_net_profit"]
    assert ratio["value"] == "-20.00%"
    assert ratio["signed_value"] == "-20.00%"
    assert ratio["unit"] == "pct"
    assert ratio["knowledge_eligible"] is False
    assert ratio["calculation"] == "operating_cash_flow / abs(net_profit)"
    assert ratio["input_refs"] == [
        "periodic:300000:2025:annual:operating_cash_flow",
        "periodic:300000:2025:annual:net_profit",
    ]


def test_cashflow_quality_signal_fires_for_negative_ocf_positive_profit() -> None:
    pack = _fact_pack(SIGNED_CASHFLOW_TEXT)

    signals = pack["filing_risk_signals"]
    assert len(signals) == 1
    signal = signals[0]
    assert signal["signal_type"] == "cashflow_quality_weak"
    assert signal["severity"] == "medium"
    assert signal["scoring_eligible"] is False
    assert "经营现金流为负" in signal["rationale"]
    assert signal["input_refs"] == [
        "periodic:300000:2025:annual:operating_cash_flow_to_net_profit"
    ]


def test_no_healthy_ratio_when_net_profit_is_non_positive() -> None:
    raw_text = """
主要会计数据和财务指标
营业收入 1,000,000,000.00 900,000,000.00 11.11%
归属于上市公司股东的净利润 -100,000,000.00 -80,000,000.00 不适用
经营活动产生的现金流量净额 20,000,000.00 50,000,000.00 -60.00%
"""

    pack = _fact_pack(raw_text)

    assert pack["derived_facts"] == []
    assert pack["filing_risk_signals"] == []
    assert any(
        diagnostic["code"] == "non_positive_net_profit_for_cashflow_ratio"
        for diagnostic in pack["diagnostics"]
    )


def test_anchor_matches_labels_split_by_jina_table_spacing() -> None:
    raw_text = """
主要会计数据和财务指标
营业收入 1,000,000,000.00 900,000,000.00 11.11%
归属于上市公司股东的净利润 100,000,000.00 80,000,000.00 25.00%
经营活动产生的现金流量净额 27,420,497.61 233,896,798.98 -88.28%
"""
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "financial_summary_table-0",
                "usage": "financial_summary_table",
                "text": (
                    "主要会计数据和财务指标\n"
                    "营 业 收 入 1,000,000,000.00 900,000,000.00 11.11%\n"
                    "归 属 于 上 市 公 司 股 东 的 净 利 润 100,000,000.00 80,000,000.00 25.00%\n"
                    "经 营 活 动 产 生 的 现 金 流 量 净 额 27,420,497.61 233,896,798.98 -88.28%\n"
                ),
            }
        ],
    }
    financial_metrics = build_required_financial_risk_metrics(
        evidence_pack,
        raw_text=raw_text,
    )

    pack = build_periodic_report_structured_fact_pack(
        stock_code="688209",
        stock_name="英集芯",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        required_financial_metrics=financial_metrics,
    )

    facts = {fact["metric_key"]: fact for fact in pack["filing_facts"]}
    assert facts["operating_cash_flow"]["source_block_id"] == "financial_summary_table-0"
    assert "经 营 活 动" in facts["operating_cash_flow"]["source_excerpt"]


def test_missing_net_profit_uses_missing_diagnostic_not_non_positive() -> None:
    evidence_pack = build_periodic_report_evidence_pack(SIGNED_CASHFLOW_TEXT, report_type="annual")
    financial_metrics = build_required_financial_risk_metrics(evidence_pack, raw_text=SIGNED_CASHFLOW_TEXT)
    financial_metrics["profit_quality"].pop("net_profit", None)

    pack = build_periodic_report_structured_fact_pack(
        stock_code="300003",
        stock_name="测试股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        required_financial_metrics=financial_metrics,
    )

    codes = {diagnostic["code"] for diagnostic in pack["diagnostics"]}
    assert "missing_net_profit_for_cashflow_ratio" in codes
    assert "non_positive_net_profit_for_cashflow_ratio" not in codes


def test_hk_revenue_and_negative_ocf_anchor_to_statement_blocks_without_net_profit() -> None:
    pack = _fact_pack(HK_REPORT_WITH_CURRENT_STATEMENTS, stock_code="02533")

    facts = {fact["metric_key"]: fact for fact in pack["filing_facts"]}

    assert set(facts) == {"revenue", "operating_cash_flow"}
    assert facts["revenue"]["source_block_id"] == "hk_income_statement_table-0"
    assert facts["revenue"]["normalized_value"] == "82232.80万元"
    assert "收入 822,328" in facts["revenue"]["source_excerpt"]
    assert "收入增長" not in facts["revenue"]["source_excerpt"]

    assert facts["operating_cash_flow"]["source_block_id"] == "hk_cash_flow_table-0"
    assert facts["operating_cash_flow"]["normalized_value"] == "-98537.30万元"
    assert "經營活動所用現金淨額" in facts["operating_cash_flow"]["source_excerpt"]

    assert pack["derived_facts"] == []
    assert pack["filing_risk_signals"] == []
    codes = {diagnostic["code"] for diagnostic in pack["diagnostics"]}
    assert "missing_required_metric" in codes
    assert "missing_net_profit_for_cashflow_ratio" in codes
