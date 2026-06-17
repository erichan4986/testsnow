"""Tests for periodic_report_llm_analysis_v2 helper."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack
from periodic_report_llm_analysis_v2 import (
    SCHEMA_VERSION,
    PeriodicReportLLMv2Error,
    build_periodic_report_llm_v2_prompt,
    render_periodic_report_llm_v2_markdown,
    summarize_periodic_report_with_llm_v2,
    validate_periodic_report_llm_v2_output,
)


SAMPLE_REPORT = """
第三节 管理层讨论与分析
一、报告期内公司从事的主要业务
公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。产品主要应用于航空航天、轨道交通、新能源等领域。

二、主营业务分析
1、营业收入构成
分产品            营业收入（元）  营业成本（元）  毛利率  营业收入同比增减  毛利率同比增减
碳纤维            500,000,000.00  350,000,000.00  30.00%      -10.00%          -2.00%
碳纤维织物        600,000,000.00  360,000,000.00  40.00%       15.00%           3.00%
合计            1,100,000,000.00  710,000,000.00  35.45%

3、前五名客户合计销售
客户名称      销售额（元）    占年度销售总额比例
客户 A        600,000,000.00          48.60%
客户 B        200,000,000.00          16.20%
合计        1,080,000,000.00          87.48%

第十节 财务报告
三、财务报表附注
（一）应收账款
1 年以内应收账款占比 85.00%，1-2 年应收账款占比 12.00%。
（二）在建工程
四期项目投入 345,678,901.23 元，工程进度 78.00%。
"""


class FakeChatClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def chat(self, prompt: str) -> str:
        return self.response_text


class FakeCompletionClient:
    def __init__(self, response_text: str):
        self.response_text = response_text

    class _Completions:
        def __init__(self, response_text: str):
            self.response_text = response_text

        def create(self, **kwargs):
            return {"choices": [{"message": {"content": self.response_text}}]}

    @property
    def chat(self):
        return self._Wrapper(self._Completions(self.response_text))

    class _Wrapper:
        def __init__(self, completions):
            self.completions = completions


def _valid_llm_response() -> str:
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {
            "summary": "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。",
            "evidence_refs": ["business_overview-0"],
        },
        "cards": [
            {
                "card_type": "financial_snapshot_card",
                "title": "财务快照",
                "bullets": [
                    "营业收入 1,100,000,000.00 元，分产品表显示碳纤维和碳纤维织物是主要收入来源。"
                ],
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 80,
            }
        ],
        "sections": [
            {
                "usage": "business_model",
                "title": "主营业务结构",
                "summary": "年报分产品表显示碳纤维和碳纤维织物是主要收入来源。",
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [
            {
                "risk_type": "customer_concentration",
                "summary": "前五名客户合计销售占比较高，需关注客户集中风险。",
                "evidence_refs": ["customer_supplier_table-0"],
                "severity": "high",
                "confidence": 85,
            }
        ],
        "follow_up_questions": [
            {
                "question": "四期项目转固后产能消化情况如何？",
                "evidence_refs": ["capex_cip_note-0"],
            }
        ],
    })


def _make_evidence_pack():
    return build_periodic_report_evidence_pack(SAMPLE_REPORT)


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------


def test_prompt_contains_evidence_ids_and_usage_labels():
    pack = _make_evidence_pack()
    prompt = build_periodic_report_llm_v2_prompt(pack)
    user = prompt["user"]
    assert "business_overview-0" in user
    assert "segment_margin_table-0" in user
    assert "customer_supplier_table-0" in user
    assert "usage" in user
    assert "metric_rule" in user


def test_prompt_caps_blocks_and_total_size():
    pack = _make_evidence_pack()
    prompt = build_periodic_report_llm_v2_prompt(pack, max_blocks=2)
    item_map = prompt["item_map"]
    assert len(item_map) <= 2


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


def test_validator_accepts_valid_v2_json():
    pack = _make_evidence_pack()
    raw = _valid_llm_response()
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["company_profile"]["summary"]
    assert len(result["cards"]) == 1
    assert result["cards"][0]["card_type"] == "financial_snapshot_card"
    assert len(result["sections"]) == 1
    assert len(result["financial_risks"]) == 1
    assert len(result["follow_up_questions"]) == 1


def test_validator_rejects_v1_schema():
    pack = _make_evidence_pack()
    raw = json.dumps({"schema_version": "periodic_report_llm_analysis.v1"})
    with pytest.raises(PeriodicReportLLMv2Error, match="schema_version mismatch"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_invalid_refs():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "x", "evidence_refs": ["missing-ref"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="invalid evidence_refs"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_invalid_refs_in_sections():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "business_model",
                "title": "valid",
                "summary": "碳纤维和碳纤维织物是主要收入来源。",
                "evidence_refs": ["missing-ref"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="invalid evidence_refs"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_invalid_refs_in_financial_risks():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [
            {
                "risk_type": "customer_concentration",
                "summary": "客户集中度较高。",
                "evidence_refs": ["missing-ref"],
                "severity": "high",
                "confidence": 85,
            }
        ],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="invalid evidence_refs"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_invalid_refs_in_follow_up_questions():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [
            {"question": "后续如何？", "evidence_refs": ["missing-ref"]}
        ],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="invalid evidence_refs"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_raw_urls():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "see https://example.com", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="raw URL"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_citation_markers():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text[^1]", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="citation marker"):
        validate_periodic_report_llm_v2_output(raw, pack)


@pytest.mark.parametrize("bad", ["confirmed_fact", "fact_candidate", "核心事实", "已证实"])
def test_validator_rejects_illegal_status_markers(bad: str):
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": bad, "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="illegal content"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_drops_invented_number_section():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "business_model",
                "title": " invented number ",
                "summary": "碳纤维营收 999.00 亿元，远超去年。",
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 0


def test_validator_drops_invented_percentage_section():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "business_model",
                "title": "invented percentage",
                "summary": "碳纤维毛利率同比下降 99pct。",
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 0


def test_validator_allows_contextual_report_year():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "2024 年度报告期间公司经营正常。", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert result["company_profile"]["summary"]


def test_validator_allows_simple_unit_normalization():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "碳纤维营收 5.00 亿元。", "evidence_refs": ["segment_margin_table-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert result["company_profile"]["summary"]


def test_validator_allows_rounded_yuan_unit_conversion():
    pack = _make_evidence_pack()
    pack["blocks"].append({
        "id": "segment_margin_table-1",
        "usage": "segment_margin_table",
        "section": "主营业务分析",
        "title": "分产品收入与毛利率",
        "text": "其中：碳纤维 443,494,353.42 198,630,573.93 55.21% -19.59%。碳纤维织物 402,520,846.01 98,780,474.86 75.46% 54.60%。",
        "source_span": {"start": 0, "end": 100},
    })
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "segment_performance",
                "title": "rounded amount",
                "summary": "碳纤维收入约 4.43 亿元，碳纤维织物收入约 4.03 亿元。",
                "evidence_refs": ["segment_margin_table-1"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 1


def test_validator_ignores_numbers_inside_product_codes():
    pack = _make_evidence_pack()
    pack["blocks"].append({
        "id": "rd_table-0",
        "usage": "rd_table",
        "section": "管理层讨论与分析",
        "title": "主要研发项目名称",
        "text": "T1100 碳纤维项目目标已达成。ZM40X 碳纤维具备工程化制备能力。ZT8E-12K 已完成工艺调试。",
        "source_span": {"start": 0, "end": 80},
    })
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "rd_progress",
                "title": "R&D progress",
                "summary": "T1100 项目目标已达成，ZM40X 具备工程化制备能力，ZT8E-12K 已完成工艺调试。",
                "evidence_refs": ["rd_table-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 1


def test_validator_allows_derived_growth_rate_when_operands_exist():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "segment_performance",
                "title": "derived growth",
                "summary": "碳纤维织物营收同比增长 15.00%。",
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 1


def test_validator_allows_percentage_point_wording_when_evidence_has_percent_delta():
    pack = _make_evidence_pack()
    pack["blocks"].append({
        "id": "segment_margin_table-1",
        "usage": "segment_margin_table",
        "section": "主营业务分析",
        "title": "分产品收入与毛利率",
        "text": "碳纤维织物 402,520,846.01 98,780,474.86 75.46% 54.60% 0.04% 13.38%",
        "source_span": {"start": 0, "end": 80},
    })
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "margin_driver",
                "title": "毛利率变化",
                "summary": "碳纤维织物毛利率为 75.46%，同比提升 13.38 个百分点。",
                "evidence_refs": ["segment_margin_table-1"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 1


def test_validator_drops_invented_product_customer_name():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "customer_concentration",
                "title": "invented customer",
                "summary": "公司客户华为占比显著。",
                "evidence_refs": ["customer_supplier_table-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 0


def test_validator_rejects_cross_evidence_misattribution():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "business_model",
                "title": "misattributed",
                "summary": "碳纤维营收 500,000,000.00 元。",
                "evidence_refs": ["business_overview-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 0


def test_validator_avoids_completing_truncated_table_numbers():
    pack = _make_evidence_pack()
    # Simulate a truncated segment table block by crafting a pack directly.
    pack["blocks"].append({
        "id": "segment_margin_table-1",
        "usage": "segment_margin_table",
        "section": "主营业务分析",
        "title": "分产品收入与毛利率（截断）",
        "text": "碳纤维营收 12…",
        "source_span": {"start": 0, "end": 20},
    })
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "segment_performance",
                "title": "truncated completion",
                "summary": "碳纤维营收 123456789.00 元。",
                "evidence_refs": ["segment_margin_table-1"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 0


# ---------------------------------------------------------------------------
# End-to-end helper tests
# ---------------------------------------------------------------------------


def test_summarize_returns_credit_and_status_metadata():
    pack = _make_evidence_pack()
    client = FakeChatClient(_valid_llm_response())
    result = summarize_periodic_report_with_llm_v2(pack, client)
    assert result["source_type"] == "periodic_report_analysis"
    assert result["source_credit"] == 75
    assert result["verification_status"] == "professional_analysis"
    assert result["claim_status"] == "professional_analysis"
    assert result["knowledge_eligible"] is False
    assert result["report_eligible"] is True


def test_summarize_returns_empty_analysis_for_empty_pack():
    empty_pack = {"schema_version": "periodic_report_evidence_pack.v1", "report_type": "unknown", "audit_status": "unknown", "blocks": []}
    client = FakeChatClient(_valid_llm_response())
    result = summarize_periodic_report_with_llm_v2(empty_pack, client)
    assert result["cards"] == []
    assert result["sections"] == []
    assert result["financial_risks"] == []
    assert result["follow_up_questions"] == []
    assert result["source_credit"] == 75


def test_render_markdown_contains_no_numbered_citations():
    pack = _make_evidence_pack()
    result = summarize_periodic_report_with_llm_v2(pack, FakeChatClient(_valid_llm_response()))
    md = render_periodic_report_llm_v2_markdown(result)
    assert "定期报告证据摘要" in md
    assert "## 材料卡片" in md
    assert "财务快照" in md
    assert "[^" not in md
    assert "[1]" not in md


def test_render_markdown_declares_intermediate_digest_scope():
    pack = _make_evidence_pack()
    result = summarize_periodic_report_with_llm_v2(pack, FakeChatClient(_valid_llm_response()))
    md = render_periodic_report_llm_v2_markdown(result)
    assert "中间素材" in md
    assert "不直接给出估值结论、买卖建议或仓位建议" in md


def test_prompt_contains_strict_schema_example():
    pack = _make_evidence_pack()
    prompt = build_periodic_report_llm_v2_prompt(pack)
    system = prompt["system"]
    assert "schema 示例" in system
    assert '"company_profile"' in system
    assert '"cards"' in system
    assert '"card_type"' in system
    assert '"bullets"' in system
    assert '"sections"' in system
    assert '"financial_risks"' in system
    assert '"follow_up_questions"' in system
    assert "summary" in system and "evidence_refs" in system
    assert "question" in system
    assert "禁止字符串数组" in system


def test_prompt_requires_numeric_metric_retention_for_core_tables():
    pack = _make_evidence_pack()
    pack["blocks"].append({
        "id": "financial_summary_table-0",
        "usage": "financial_summary_table",
        "section": "公司简介和主要财务指标",
        "title": "主要会计数据和财务指标",
        "text": "营业收入（元） 3,898,054,583.68 3,346,983,120.66 16.46%。归属于上市公司股东的净利润（元） 547,059,403.97 500,247,943.10 9.36%。扣除非经常性损益的净利润（元） 427,582,529.58 451,159,069.34 -5.23%。",
        "source_span": {"start": 0, "end": 120},
    })
    prompt = build_periodic_report_llm_v2_prompt(pack)
    system = prompt["system"]
    user = prompt["user"]
    assert "不得只写增长、下降、提升、承压" in system
    assert "收入金额" in system
    assert "同比增减" in system
    assert "毛利率" in system
    assert "segment_margin_table" in user
    assert "分产品收入金额、收入同比、毛利率、毛利率同比增减" in user
    assert "financial_summary_table" in user
    assert "归母净利润" in user
    assert "扣非归母净利润" in user


def test_prompt_frames_output_as_intermediate_evidence_digest_not_final_report():
    pack = _make_evidence_pack()
    prompt = build_periodic_report_llm_v2_prompt(pack)
    system = prompt["system"]
    assert "定期报告证据摘要" in system
    assert "中间素材" in system
    assert "不得给出买卖建议" in system
    assert "不得给出估值结论" in system
    assert "年报事实 + 管理层解释 + 可跟踪问题" in system


def test_prompt_requires_evidence_cards_for_final_report_materials():
    pack = _make_evidence_pack()
    prompt = build_periodic_report_llm_v2_prompt(pack)
    system = prompt["system"]
    assert "材料卡片" in system
    assert "company_profile_card" in system
    assert "financial_snapshot_card" in system
    assert "segment_card" in system
    assert "rd_card" in system
    assert "channel_supplier_card" in system
    assert "risk_card" in system


def test_prompt_lists_expanded_annual_report_usage_and_risk_types():
    pack = _make_evidence_pack()
    prompt = build_periodic_report_llm_v2_prompt(pack)
    system = prompt["system"]
    assert "product_capacity_profile" in system
    assert "production_inventory_signal" in system
    assert "rd_investment" in system
    assert "cash_flow_capex" in system
    assert "governance_signal" in system
    assert "ar_customer_concentration" in system
    assert "asset_impairment" in system
    assert "cash_flow_sustainability" in system
    assert "audit_key_matter" in system


def test_validator_rejects_top_level_unsupported_field():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "summary": "extra top-level summary",
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="unsupported top-level field"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_rejects_invalid_refs_in_cards():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "cards": [
            {
                "card_type": "segment_card",
                "title": "业务结构",
                "bullets": ["碳纤维收入 500,000,000.00 元。"],
                "evidence_refs": ["missing-ref"],
                "confidence": 80,
            }
        ],
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="invalid evidence_refs"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_drops_card_with_invented_number():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "cards": [
            {
                "card_type": "segment_card",
                "title": "业务结构",
                "bullets": ["碳纤维收入 999,999,999.00 元。"],
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 80,
            }
        ],
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert result["cards"] == []


def test_validator_drops_section_with_unsupported_content_field():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [
            {
                "usage": "business_model",
                "title": "unsupported field",
                "content": "this is not allowed",
                "description": "also not allowed",
                "evidence_refs": ["business_overview-0"],
                "confidence": 80,
            }
        ],
        "financial_risks": [],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert len(result["sections"]) == 0


def test_validator_rejects_string_list_follow_up_questions():
    pack = _make_evidence_pack()
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {"summary": "text", "evidence_refs": ["business_overview-0"]},
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": ["question one", "question two"],
    })
    with pytest.raises(PeriodicReportLLMv2Error, match="follow_up_questions must be object list"):
        validate_periodic_report_llm_v2_output(raw, pack)


def test_validator_accepts_expanded_annual_report_usages_and_risks():
    pack = _make_evidence_pack()
    pack["blocks"].extend([
        {
            "id": "product_capacity_profile-0",
            "usage": "product_capacity_profile",
            "section": "管理层讨论与分析",
            "title": "产品和产能",
            "text": "公司可规模化生产 ZT7、ZT8、ZT9 系列以及 ZM40X 等产品，已建有 2000 吨级生产线。",
            "source_span": {"start": 0, "end": 80},
        },
        {
            "id": "production_sales_inventory_table-0",
            "usage": "production_sales_inventory_table",
            "section": "管理层讨论与分析",
            "title": "产销存",
            "text": "销售量 315,326.80 kg，生产量 388,277.44 kg，库存量 94,938.11 kg，同比增长 150.95%。",
            "source_span": {"start": 0, "end": 80},
        },
        {
            "id": "rd_investment_table-0",
            "usage": "rd_investment_table",
            "section": "管理层讨论与分析",
            "title": "研发投入",
            "text": "研发人员数量 75 人，研发投入金额 117,500,000.00 元，研发投入占营业收入比例 13.89%，研发投入资本化金额 0.00 元。",
            "source_span": {"start": 0, "end": 80},
        },
        {
            "id": "cash_flow_capex_table-0",
            "usage": "cash_flow_capex_table",
            "section": "财务报告",
            "title": "现金流与资本开支",
            "text": "经营活动产生的现金流量净额 880,000,000.00 元，购建固定资产、无形资产和其他长期资产支付的现金 585,000,000.00 元。",
            "source_span": {"start": 0, "end": 80},
        },
        {
            "id": "audit_key_matters-0",
            "usage": "audit_key_matters",
            "section": "财务报告",
            "title": "关键审计事项",
            "text": "收入确认和应收账款减值是关键审计事项。",
            "source_span": {"start": 0, "end": 80},
        },
        {
            "id": "governance_dissent-0",
            "usage": "governance_dissent",
            "section": "公司治理",
            "title": "董事异议",
            "text": "董事温月芳对财务报告、内部控制、项目投资、关联方认定、资金往来等多个议案提出异议。",
            "source_span": {"start": 0, "end": 80},
        },
    ])
    raw = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {
            "summary": "公司可规模化生产 ZT7、ZT8、ZT9 系列以及 ZM40X 等产品，已建有 2000 吨级生产线。",
            "evidence_refs": ["product_capacity_profile-0"],
        },
        "sections": [
            {
                "usage": "production_inventory_signal",
                "title": "产销存信号",
                "summary": "销售量 315,326.80 kg，生产量 388,277.44 kg，库存量 94,938.11 kg，同比增长 150.95%。",
                "evidence_refs": ["production_sales_inventory_table-0"],
                "confidence": 80,
            },
            {
                "usage": "rd_investment",
                "title": "研发投入",
                "summary": "研发人员数量 75 人，研发投入金额约 1.18 亿元，研发投入占营业收入比例 13.89%，研发投入资本化金额 0.00 元。",
                "evidence_refs": ["rd_investment_table-0"],
                "confidence": 80,
            },
            {
                "usage": "cash_flow_capex",
                "title": "现金流与资本开支",
                "summary": "经营活动产生的现金流量净额约 8.80 亿元，购建固定资产、无形资产和其他长期资产支付的现金约 5.85 亿元。",
                "evidence_refs": ["cash_flow_capex_table-0"],
                "confidence": 80,
            },
            {
                "usage": "governance_signal",
                "title": "治理信号",
                "summary": "董事温月芳对财务报告、内部控制、项目投资、关联方认定、资金往来等多个议案提出异议。",
                "evidence_refs": ["governance_dissent-0"],
                "confidence": 75,
            },
        ],
        "financial_risks": [
            {
                "risk_type": "cash_flow_sustainability",
                "summary": "经营活动产生的现金流量净额约 8.80 亿元，但资本开支现金流出约 5.85 亿元，需要跟踪持续性。",
                "evidence_refs": ["cash_flow_capex_table-0"],
                "severity": "medium",
                "confidence": 80,
            },
            {
                "risk_type": "audit_key_matter",
                "summary": "收入确认和应收账款减值是关键审计事项。",
                "evidence_refs": ["audit_key_matters-0"],
                "severity": "medium",
                "confidence": 80,
            },
            {
                "risk_type": "governance_signal",
                "summary": "董事温月芳对财务报告、内部控制、项目投资、关联方认定、资金往来等多个议案提出异议。",
                "evidence_refs": ["governance_dissent-0"],
                "severity": "medium",
                "confidence": 75,
            },
        ],
        "follow_up_questions": [],
    })
    result = validate_periodic_report_llm_v2_output(raw, pack)
    assert {section["usage"] for section in result["sections"]} >= {
        "production_inventory_signal",
        "rd_investment",
        "cash_flow_capex",
        "governance_signal",
    }
    assert {risk["risk_type"] for risk in result["financial_risks"]} >= {
        "cash_flow_sustainability",
        "audit_key_matter",
        "governance_signal",
    }


# ---------------------------------------------------------------------------
# Import independence
# ---------------------------------------------------------------------------


def test_import_does_not_require_openai_or_deepseek():
    helper_path = Path(__file__).parent.parent.parent / "scripts" / "utils"
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(helper_path)!r})\n"
        "sys.modules['openai'] = None\n"
        "sys.modules['deepseek'] = None\n"
        "import periodic_report_llm_analysis_v2\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout
