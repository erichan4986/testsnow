"""Tests for experimental full-text periodic report LLM path."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_fulltext_llm_analysis import (
    FIXED_ANALYSIS_SECTION_TITLES,
    FULLTEXT_ANALYSIS_SCHEMA_VERSION,
    FINANCIAL_RISK_CANDIDATE_TYPES,
    PeriodicReportFulltextError,
    build_periodic_report_fulltext_pack,
    build_periodic_report_fulltext_prompt,
    render_periodic_report_fulltext_audit_markdown,
    render_periodic_report_fulltext_markdown,
    summarize_periodic_report_fulltext_with_llm,
    validate_periodic_report_fulltext_output,
)
from periodic_report_evidence_pack import build_periodic_report_evidence_pack
from periodic_report_required_financial_metrics import build_required_financial_risk_metrics
from periodic_report_required_metrics import build_required_business_metrics


LONG_MARKET_TEXT = "航空航天高端需求持续增长。" * 220


SAMPLE_FULLTEXT_REPORT = f"""
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

二、行业情况
{LONG_MARKET_TEXT}
下游汽车电子、工业控制、机器人和数据中心需求扩张，管理层引用资料称模拟芯片市场预计 CAGR 为 12.3%。

三、主营业务分析
分产品 营业收入 营业成本 毛利率 营业收入同比增减 毛利率同比增减
信号链产品 1,471,022,875.27 615,285,480.40 58.17% 26.23% -0.13%
电源管理产品 2,379,833,746.57 1,276,179,316.39 46.38% 9.08% -1.43%
前五名客户销售额占年度销售总额 33.13%，第一大客户占比 7.79%。

第十节 财务报告
存货账面价值 1,448,216,300.11 元，占总资产 20.83%。
资产减值损失 -170,237,600.06 元，主要为存货跌价准备。
合同纠纷诉讼冻结资金 4,400 万元。
"""

RD_FULLTEXT_REPORT = """
第三节 管理层讨论与分析
一、核心技术与研发进展
报告期内，公司研发投入为 22,421.94 万元，占营业收入比例为 27.77%。
2025 年公司率先量产了 Phase8L 方案的全集成 L-PAMiD，RedCap 方案也实现规模量产。

第十节 财务报告
费用化研发投入 224,219,358.36 248,420,315.08 -9.74
资本化研发投入 0 0 0
截至 2025 年12月31日，公司及子公司共拥有 171 项发明专利、24 项实用新 型专利、180 项集成电路布图设计专有权。
研发人员的数量（人）150 166
研发人员数量占公司总人数的比例（%）61.48 64.34
"""

HUIZHIWEI_LIKE_FULLTEXT_REPORT = """
第一节 重要提示、目录和释义
本公司及董事会全体成员保证年度报告内容真实、准确、完整。

第二节 公司简介和主要财务指标
2025 年公司实现营业收入 80,727.37 万元，较上年同期增长 54.06%。

第三节 管理层讨论与分析
一、报告期内公司从事的主要业务
射频前端芯片作为无线通信设备的核心器件，公司产品系列覆盖 2G、3G、4G、5G 重耕频段、5G UHB 等蜂窝通信频段和 Wi-Fi 通信等。
公司的射频前端产品应用于三星、vivo、小米、OPPO、荣耀等国内外智能手机品牌机型，并进入华勤通讯和龙旗科技等一线移动终端设备 ODM 厂商和移远通信、广和通、日海智能等头部无线通信模组厂商。

3、销售模式
公司采用“经销为主、直销为辅”的销售模式。公司与经销商的关系属于买断式销售关系。

二、经营情况讨论与分析
公司紧跟射频方案高集成化、高端化演进趋势推进产品迭代。
2025 年公司率先量产了 Phase8L 方案的全集成 L-PAMiD，RedCap 方案也实现规模量产。
公司 5G UHB 频段 L-PAMiF 模组已在三星自研体系规模商用。
公司部分产品已经通过车规可靠性的测试，获得 AEC-Q104 车规认证，并在客户端推广。

第十节 财务报告
费用化研发投入 224,219,358.36 248,420,315.08 -9.74
资本化研发投入 0 0 0
截至 2025 年12月31日，公司及子公司共拥有 171 项发明专利、24 项实用新型专利、180 项集成电路布图设计专有权。
"""

HK_BLACK_SESAME_LIKE_REPORT = """
目錄
主要摘要 ........................................................ 2
董事長致辭 ...................................................... 6
管理層討論及分析 ................................................ 9
企業管治報告 .................................................... 68
獨立核數師報告 .................................................. 101
綜合財務報表附註 ................................................ 110

主要摘要
收入 822,328 千元，毛利率為 41.0%，全年經營性虧損同比收窄。

董事長致辭
公司聚焦汽車級智能車計算 SoC 及基於 SoC 的解決方案。

管理層討論及分析
華山 A2000 是面向高階智能駕駛的高算力芯片，採用 7nm 工藝，已完成回片。
武當 C1200 系列芯片在 2025 年實現從定點到量產。
SesameX 平台已在具身智能、Robotaxi 和智能影像場景推進商業化落地。

企業管治報告
董事會持續監督內部控制及風險管理制度。

獨立核數師報告
我們認為，綜合財務報表已真實而中肯地反映集團財務狀況。

綜合財務報表附註
年內經營活動所用現金淨額為 985,373 千元，經調整虧損淨額為 1,075,674 千元。
"""


class FakeChatClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.prompt = ""

    def chat(self, prompt: str) -> str:
        self.prompt = prompt
        return self.response_text


def test_fulltext_pack_preserves_long_market_context_and_late_cagr():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    joined = "\n".join(block["text"] for block in pack["blocks"])
    assert "管理层讨论与分析" in joined
    assert "汽车电子、工业控制、机器人和数据中心" in joined
    assert "12.3%" in joined
    assert "信号链产品 1,471,022,875.27" in joined


def test_fulltext_pack_skips_table_of_contents_headings():
    text = """
第一节 重要提示、目录和释义 ................................ ............. 2
第二节 公司简介和主要财务指标 ................................ ............ 6
第三节 管理层讨论与分析 ................................ ............... 12

第一节 重要提示、目录和释义
本公司提示投资者关注风险。

第三节 管理层讨论与分析
公司客户A销售额 740,000,000 元，占年度销售总额 87.49%。
"""
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=2000, max_chunks=8)
    headings = [block["section"] for block in pack["blocks"]]
    assert not any("..." in heading for heading in headings)
    assert "客户A销售额 740,000,000" in "\n".join(block["text"] for block in pack["blocks"])


def test_fulltext_pack_splits_hk_traditional_chinese_sections():
    """HK annual reports use headings like 管理層討論及分析 instead of 第三节."""
    pack = build_periodic_report_fulltext_pack(
        HK_BLACK_SESAME_LIKE_REPORT,
        chunk_chars=4000,
        max_chunks=12,
    )

    sections = [block["section"] for block in pack["blocks"]]
    usages = {block["section"]: block["usage"] for block in pack["blocks"]}
    assert "管理層討論及分析" in sections
    assert usages["管理層討論及分析"] == "fulltext_management_discussion"
    assert usages["企業管治報告"] == "fulltext_governance"
    assert usages["獨立核數師報告"] == "fulltext_financial_notes"
    assert usages["綜合財務報表附註"] == "fulltext_financial_notes"
    assert not any("..." in section for section in sections)


def test_fulltext_pack_keeps_hk_business_review_before_auditor_section():
    text = """
目錄
公司資料 財務業績摘要 業務回顧及前景 管理層討論與分析 董事會報告 獨立核數師報告

於 2025 年，本公司錄得收入人民幣 3,758 百萬元，同比增長 57.7%，綜合毛利率達 64.5%。
Horizon SuperDrive（HSD）正式量產，為中國首個量產的基於一段式端到端技術的智能駕駛大模型。
於報告期間，HSD 已獲得 10 家 OEM 品牌累計 20 餘款車型定點。
產品及解決方案收入達至人民幣 1,622 百萬元，授權及服務業務收入達人民幣 1,935 百萬元。

獨立核數師報告
關鍵審計事項 汽車解決方案授權及服務業務的收入確認。
"""
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=3000, max_chunks=6)
    joined = "\n".join(block["text"] for block in pack["blocks"])

    assert "Horizon SuperDrive" in joined
    assert "10 家 OEM" in joined
    assert "產品及解決方案收入達至人民幣 1,622 百萬元" in joined


def test_fulltext_prompt_marks_experimental_path_and_allows_large_context():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    prompt = build_periodic_report_fulltext_prompt(pack, max_prompt_chars=50000)
    assert "全文/大块年报实验路径" in prompt["system"]
    assert "允许在证据范围内做判断" in prompt["system"]
    assert "judgments" in prompt["system"]
    assert "客户与订单结构" in prompt["system"]
    assert "不得为空" in prompt["system"]
    assert "financial_risks" in prompt["system"]
    assert "other_material_risk" in prompt["system"]
    assert "候选池不是上限" in prompt["system"]
    assert "inventory_impairment" in prompt["system"]
    assert "不为凑数硬写" in prompt["system"]
    assert "必要时可以超过 9 条" in prompt["system"]
    assert "不能只写在“财务风险与跟踪指标”正文段里" in prompt["system"]
    for title in FIXED_ANALYSIS_SECTION_TITLES:
        assert title in prompt["system"]
    assert "12.3%" in prompt["user"]
    assert len(prompt["user"]) > 3000


def test_fulltext_prompt_includes_required_metrics_but_forbids_pack_refs():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    evidence_pack = build_periodic_report_evidence_pack(SAMPLE_FULLTEXT_REPORT)
    required_metrics = build_required_business_metrics(evidence_pack, raw_text=SAMPLE_FULLTEXT_REPORT)
    prompt = build_periodic_report_fulltext_prompt(
        pack,
        required_metrics=required_metrics,
        max_prompt_chars=50000,
    )
    assert "required_business_metrics" in prompt["system"]
    assert "segment_margin_table-0" in prompt["system"]
    assert "evidence_refs 只能引用 fulltext-* id" in prompt["system"]
    assert "required_business_metrics" in prompt["user"]
    assert "segment_rows" in prompt["user"]
    assert "fulltext-2-0" in prompt["user"]


def test_fulltext_prompt_includes_required_financial_metrics_without_schema_field():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    evidence_pack = build_periodic_report_evidence_pack(SAMPLE_FULLTEXT_REPORT)
    required_financial_metrics = build_required_financial_risk_metrics(
        evidence_pack,
        raw_text=SAMPLE_FULLTEXT_REPORT,
    )
    prompt = build_periodic_report_fulltext_prompt(
        pack,
        required_financial_metrics=required_financial_metrics,
        max_prompt_chars=50000,
    )
    assert "required_financial_risk_metrics" in prompt["system"]
    assert "不得把 required_financial_risk_metrics 作为 LLM 输出顶层字段" in prompt["system"]
    assert "required_financial_risk_metrics" in prompt["user"]
    assert "inventory_risk" in prompt["user"]
    assert "cash_flow_quality" in prompt["user"]
    assert "允许顶层字段只有：schema_version、sections、financial_risks" in prompt["system"]


def test_fulltext_prompt_places_ground_truth_before_raw_metrics_and_fulltext_blocks():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    required_metrics = {
        "schema_version": "test",
        "segment_rows": [
            {
                "label": "经销",
                "revenue": {"text": "360,991.14", "unit": "万元", "normalized": "360991.14万元"},
                "source_block_id": "segment_margin_table-0",
            }
        ],
        "normalized_values": ["360991.14万元"],
    }
    required_financial_metrics = {
        "profit_quality": {
            "revenue": {"text": "3,898,054,583.68", "unit": "万元", "normalized": "389805.46万元"}
        },
        "inventory_risk": {
            "inventory_balance": {"text": "1,448,216,300.11", "unit": "万元", "normalized": "144821.63万元"}
        },
    }

    prompt = build_periodic_report_fulltext_prompt(
        pack,
        required_metrics=required_metrics,
        required_financial_metrics=required_financial_metrics,
        max_prompt_chars=50000,
    )

    user = prompt["user"]
    ground_truth_pos = user.index("Ground Truth")
    raw_metrics_pos = user.index("required_business_metrics")
    fulltext_pos = user.index("id: fulltext-")
    ground_truth_block = user[ground_truth_pos:raw_metrics_pos]
    assert ground_truth_pos < raw_metrics_pos < fulltext_pos
    assert "360991.14万元" in ground_truth_block
    assert "389805.46万元" in ground_truth_block
    assert "144821.63万元" in ground_truth_block
    assert "segment_margin_table-0" not in ground_truth_block


def test_fulltext_prompt_adds_financial_number_hard_rule():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    prompt = build_periodic_report_fulltext_prompt(pack, max_prompt_chars=50000)

    assert "财务数字只能来自 Ground Truth 或 fulltext-* 证据原文" in prompt["system"]
    assert "禁止引用训练数据、旧报告或外部记忆中的数字" in prompt["system"]


def test_fulltext_prompt_separates_sales_mode_ratio_from_customer_descriptions():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    prompt = build_periodic_report_fulltext_prompt(pack, max_prompt_chars=50000)

    assert "销售模式占比" in prompt["system"]
    assert "只写“直销收入占比 X%”" in prompt["system"]
    assert "不要把客户定性、产品描述和销售模式表数字混在同一条 judgment" in prompt["system"]
    assert "若要写客户/产品描述，必须引用包含该描述的 fulltext 块，单独成句" in prompt["system"]


def test_fulltext_summarize_returns_fixed_judgment_sections_and_metadata():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    raw = _fixed_section_response(include_risks=True)
    client = FakeChatClient(raw)
    result = summarize_periodic_report_fulltext_with_llm(pack, client)
    assert result["source_type"] == "periodic_report_fulltext_analysis"
    assert result["source_credit"] == 75
    assert result["schema_version"] == FULLTEXT_ANALYSIS_SCHEMA_VERSION
    assert [section["title"] for section in result["sections"]] == list(FIXED_ANALYSIS_SECTION_TITLES)
    assert result["sections"][0]["judgments"][0]["evidence_refs"] == ["fulltext-2-0"]
    assert "判断" in result["sections"][0]["judgments"][0]["judgment"]
    assert result["financial_risks"][0]["risk_type"] == "inventory_impairment"
    assert result["financial_risks"][1]["risk_type"] == "other_material_risk"
    assert result["financial_risks"][1]["custom_label"] == "平台型产品扩张转化风险"
    assert "全文/大块年报实验路径" in client.prompt


def test_fulltext_validator_rejects_missing_or_invalid_judgment_refs():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response())
    parsed["sections"][0]["judgments"][0]["evidence_refs"] = ["missing-ref"]
    with pytest.raises(PeriodicReportFulltextError, match="invalid evidence_refs"):
        validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)


def test_fulltext_validator_rejects_evidence_pack_refs_in_judgments():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response())
    parsed["sections"][0]["judgments"][0]["evidence_refs"] = ["segment_margin_table-0"]
    with pytest.raises(PeriodicReportFulltextError, match="invalid evidence_refs"):
        validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)


def test_fulltext_validator_rejects_invalid_refs_in_financial_risks():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0]["evidence_refs"] = ["missing-ref"]
    with pytest.raises(PeriodicReportFulltextError, match="invalid evidence_refs"):
        validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)


def test_fulltext_validator_rejects_unknown_risk_type_without_other_label():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0]["risk_type"] = "random_new_risk"
    with pytest.raises(PeriodicReportFulltextError, match="unsupported risk_type"):
        validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)


def test_fulltext_validator_accepts_json_fenced_response():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    raw = "```json\n" + _fixed_section_response() + "\n```"
    result = validate_periodic_report_fulltext_output(raw, pack)
    assert result["schema_version"] == FULLTEXT_ANALYSIS_SCHEMA_VERSION
    assert [section["title"] for section in result["sections"]] == list(FIXED_ANALYSIS_SECTION_TITLES)


def test_fulltext_validator_treats_missing_section_judgments_as_empty():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["sections"][2].pop("judgments")
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    assert result["sections"][2]["title"] == "客户与订单结构"
    assert result["sections"][2]["judgments"] == []
    assert result["financial_risks"]


def test_fulltext_validator_backfills_customer_order_section_from_required_metrics():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["sections"][2]["judgments"] = []
    required_metrics = {
        "customer_concentration": {
            "present": True,
            "top_five_percentage": {"text": "33.13%", "unit": "%", "normalized": "33.13%"},
            "largest_percentage": {"text": "7.79%", "unit": "%", "normalized": "7.79%"},
        },
        "supplier_concentration": {
            "present": True,
            "top_five_percentage": {"text": "90.99%", "unit": "%", "normalized": "90.99%"},
            "largest_percentage": {"text": "39.61%", "unit": "%", "normalized": "39.61%"},
        },
        "sales_mode_rows": [
            {
                "label": "经销",
                "revenue": {"text": "3,609,911,439.81", "unit": "万元", "normalized": "360991.14万元"},
                "revenue_yoy": {"text": "20.37%", "unit": "%", "normalized": "20.37%"},
            }
        ],
    }
    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_metrics=required_metrics,
    )
    customer_section = result["sections"][2]
    assert customer_section["title"] == "客户与订单结构"
    assert customer_section["judgments"]
    assert "前五名客户" in customer_section["judgments"][0]["judgment"]
    assert "90.99%" in customer_section["judgments"][0]["judgment"]


def test_fulltext_validator_does_not_infer_risk_from_customer_order_backfill():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    required_metrics = {
        "customer_concentration": {
            "present": True,
            "top_five_percentage": {"text": "33.13%", "unit": "%", "normalized": "33.13%"},
            "largest_percentage": {"text": "7.79%", "unit": "%", "normalized": "7.79%"},
        },
        "supplier_concentration": {
            "present": True,
            "top_five_percentage": {"text": "90.99%", "unit": "%", "normalized": "90.99%"},
            "largest_percentage": {"text": "39.61%", "unit": "%", "normalized": "39.61%"},
        },
        "sales_mode_rows": [
            {
                "label": "经销",
                "revenue": {"text": "3,609,911,439.81", "unit": "万元", "normalized": "360991.14万元"},
                "revenue_yoy": {"text": "20.37%", "unit": "%", "normalized": "20.37%"},
            }
        ],
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_metrics=required_metrics,
    )

    assert result["sections"][2]["judgments"]
    assert result["financial_risks"] == []


def test_fulltext_validator_backfills_high_supplier_concentration_from_required_financial_metrics():
    text = SAMPLE_FULLTEXT_REPORT + "\n前五名供应商采购额 97080.28万元，占年度采购总额 73.45%；第一大供应商采购额 43030.34万元，占比 32.56%。\n"
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    required_financial_metrics = {
        "supplier_concentration": {
            "top_five_amount": {"text": "97080.28", "unit": "万元", "normalized": "97080.28万元"},
            "top_five_percentage": {"text": "73.45%", "unit": "%", "normalized": "73.45%"},
            "largest_amount": {"text": "43030.34", "unit": "万元", "normalized": "43030.34万元"},
            "largest_percentage": {"text": "32.56%", "unit": "%", "normalized": "32.56%"},
        }
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_financial_metrics=required_financial_metrics,
    )

    risks = result["financial_risks"]
    assert [risk["risk_type"] for risk in risks] == ["supplier_concentration"]
    assert risks[0]["importance"] == "high"
    assert "73.45%" in risks[0]["summary"]
    assert "32.56%" in risks[0]["summary"]


def test_fulltext_validator_does_not_duplicate_existing_supplier_concentration_backfill():
    text = SAMPLE_FULLTEXT_REPORT + "\n前五名供应商采购额 97080.28万元，占年度采购总额 73.45%；第一大供应商采购额 43030.34万元，占比 32.56%。\n"
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["financial_risks"] = [
        {
            "risk_type": "supplier_concentration",
            "importance": "high",
            "summary": "前五名供应商采购额 97080.28万元，占年度采购总额 73.45%。",
            "mechanism": "关键供应商价格、产能或交付变化会影响成本、交付和毛利率。",
            "tracking_indicators": ["前五名供应商采购额", "前五名供应商占比"],
            "evidence_refs": ["fulltext-3-0"],
            "confidence": 85,
        }
    ]
    required_financial_metrics = {
        "supplier_concentration": {
            "top_five_amount": {"text": "97080.28", "unit": "万元", "normalized": "97080.28万元"},
            "top_five_percentage": {"text": "73.45%", "unit": "%", "normalized": "73.45%"},
            "largest_percentage": {"text": "32.56%", "unit": "%", "normalized": "32.56%"},
        }
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_financial_metrics=required_financial_metrics,
    )

    risk_types = [risk["risk_type"] for risk in result["financial_risks"]]
    assert risk_types.count("supplier_concentration") == 1


def test_fulltext_validator_does_not_backfill_low_supplier_concentration_from_required_financial_metrics():
    text = SAMPLE_FULLTEXT_REPORT + "\n前五名供应商采购额 10000万元，占年度采购总额 30.46%；第一大供应商采购额 2000万元，占比 6.73%。\n"
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    required_financial_metrics = {
        "supplier_concentration": {
            "top_five_percentage": {"text": "30.46%", "unit": "%", "normalized": "30.46%"},
            "largest_percentage": {"text": "6.73%", "unit": "%", "normalized": "6.73%"},
        }
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_financial_metrics=required_financial_metrics,
    )

    assert result["financial_risks"] == []


def test_fulltext_validator_uses_required_business_supplier_detail_for_financial_backfill():
    text = SAMPLE_FULLTEXT_REPORT + "\n前五名供应商采购额 97080.28万元，占年度采购总额 73.45%；第一大供应商采购额 43030.34万元，占比 32.56%。\n"
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    required_financial_metrics = {
        "supplier_concentration": {
            "top_five_amount": {"text": "97080.28", "unit": "万元", "normalized": "97080.28万元"},
            "top_five_percentage": {"text": "73.45%", "unit": "%", "normalized": "73.45%"},
        }
    }
    required_metrics = {
        "supplier_concentration": {
            "present": True,
            "largest_amount": {"text": "43030.34", "unit": "万元", "normalized": "43030.34万元"},
            "largest_percentage": {"text": "32.56%", "unit": "%", "normalized": "32.56%"},
        }
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_metrics=required_metrics,
        required_financial_metrics=required_financial_metrics,
    )

    assert "32.56%" in result["financial_risks"][0]["summary"]


def test_fulltext_validator_backfills_rd_section_from_fulltext_when_llm_misses_it():
    pack = build_periodic_report_fulltext_pack(RD_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    for section in parsed["sections"]:
        for judgment in section.get("judgments") or []:
            judgment["evidence_refs"] = ["fulltext-0-0"]
    parsed["financial_risks"] = []
    parsed["sections"][3]["judgments"] = []

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    rd_section = result["sections"][3]
    assert rd_section["title"] == "研发与技术进展"
    assert rd_section["judgments"]
    judgment = rd_section["judgments"][0]
    assert "研发投入为 22,421.94 万元" in judgment["judgment"]
    assert "占营业收入比例为 27.77%" in judgment["judgment"]
    assert "资本化研发投入 0" in judgment["judgment"]
    assert "发明专利 171 项" in judgment["judgment"]
    assert judgment["evidence_refs"]


def test_fulltext_rd_backfill_does_not_treat_report_year_as_staff_count():
    text = """
    第三节 管理层讨论与分析
    报告期内，EDA 领域研发投入 85,917.51 万元。
    截至 2025 年 12 月 31 日，公司已获得授权专利 402 项和软件著作权 186 项。
    公司拥有员工 1,460 人，其中研发技术人员 1,077 人，占员工总数 74%。
    研发技术人员1077人，硕士以上学历占比较高。
    """
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    for section in parsed["sections"]:
        for judgment in section.get("judgments") or []:
            judgment["evidence_refs"] = ["fulltext-0-0"]
    parsed["financial_risks"] = []
    parsed["sections"][3]["judgments"] = []

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    rd_section = result["sections"][3]
    judgment_text = " ".join(j["judgment"] for j in rd_section["judgments"])
    assert "研发人员数量 1,077 人" in judgment_text
    assert "研发人员数量 2025 人" not in judgment_text
    assert "研发人员数量 72 人" not in judgment_text
    assert judgment_text.count("研发人员数量") == 1
    assert "授权专利 402 项" in judgment_text or "软件著作权 186 项" in judgment_text


def test_fulltext_rd_backfill_deduplicates_same_staff_count_across_blocks():
    from periodic_report_fulltext_llm_analysis import _rd_judgment_from_fulltext

    item_map = {
        "fulltext-0-0": {
            "text": "公司拥有员工 1,460 人，其中研发技术人员 1,077 人，占员工总数 74%。"
        },
        "fulltext-0-1": {
            "text": "研发技术人员1077人，研发队伍保持稳定。"
        },
    }

    judgment, refs = _rd_judgment_from_fulltext(item_map)

    assert judgment.count("研发人员数量") == 1
    assert "研发人员数量 1,077 人" in judgment or "研发人员数量 1077 人" in judgment
    assert refs


def test_fulltext_validator_backfills_company_profile_with_customer_chain_and_sales_model():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = []
    parsed["sections"][0]["judgments"] = []

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    profile_section = result["sections"][0]
    assert profile_section["title"] == "公司画像"
    assert profile_section["judgments"]
    judgment = profile_section["judgments"][0]
    assert "三星" in judgment["judgment"]
    assert any(brand in judgment["judgment"] for brand in ("vivo", "小米", "OPPO", "荣耀"))
    assert any(channel in judgment["judgment"] for channel in ("华勤", "龙旗", "移远"))
    assert "买断式" in judgment["judgment"] or "经销" in judgment["judgment"]
    assert "2G" in judgment["judgment"]
    assert "5G" in judgment["judgment"]
    assert all(ref.startswith("fulltext-") for ref in judgment["evidence_refs"])


def test_fulltext_validator_backfills_rd_section_with_product_project_statuses():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = []
    parsed["sections"][3]["judgments"] = []

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    rd_section = result["sections"][3]
    assert rd_section["title"] == "研发与技术进展"
    assert rd_section["judgments"]
    combined = " ".join(j["judgment"] for j in rd_section["judgments"])
    assert any(product in combined for product in ("L-PAMiD", "L-PAMiF", "RedCap", "AEC-Q104"))
    assert any(status in combined for status in ("量产", "规模量产", "规模商用", "认证", "预量产"))
    for judgment in rd_section["judgments"]:
        assert all(ref.startswith("fulltext-") for ref in judgment["evidence_refs"])


def test_fulltext_validator_does_not_backfill_profile_when_llm_already_covers_it():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = []
    parsed["sections"][0]["judgments"] = [
        {
            "judgment": "公司画像判断：产品覆盖 2G/3G/4G/5G 和 Wi-Fi，应用于三星、vivo、小米、OPPO、荣耀等品牌，并进入华勤通讯、龙旗科技等 ODM 和移远通信等模组厂商，采用经销为主、买断式销售模式。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 85,
        }
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    profile_section = result["sections"][0]
    assert len(profile_section["judgments"]) == 1
    assert "公司画像判断" in profile_section["judgments"][0]["judgment"]


def test_fulltext_validator_profile_backfill_is_idempotent_on_revalidation():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = []
    parsed["sections"][0]["judgments"] = []

    first = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    second_payload = {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "sections": first["sections"],
        "financial_risks": first["financial_risks"],
    }
    second = validate_periodic_report_fulltext_output(
        json.dumps(second_payload, ensure_ascii=False),
        pack,
    )

    profile_judgments = second["sections"][0]["judgments"]
    assert len(profile_judgments) == len(first["sections"][0]["judgments"])


def test_fulltext_validator_deduplicates_identical_judgments_within_section():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = []
    duplicate = {
        "judgment": "公司画像判断：产品覆盖 2G/3G/4G/5G 和 Wi-Fi，应用于三星、vivo、小米、OPPO、荣耀等品牌，并进入华勤通讯、龙旗科技等 ODM 和移远通信等模组厂商，采用经销为主、买断式销售模式。",
        "evidence_refs": ["fulltext-2-0"],
        "confidence": 72,
    }
    parsed["sections"][0]["judgments"] = [duplicate, dict(duplicate)]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    profile_judgments = result["sections"][0]["judgments"]
    assert len(profile_judgments) == 1


def test_fulltext_validator_backfills_keep_professional_analysis_metadata():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = []
    parsed["sections"][0]["judgments"] = []
    parsed["sections"][3]["judgments"] = []

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    # Validation output itself does not carry source_credit; summarization wrapper does.
    assert result["schema_version"] == FULLTEXT_ANALYSIS_SCHEMA_VERSION
    assert result["sections"][0]["judgments"]
    assert result["sections"][3]["judgments"]


def test_fulltext_validator_ignores_judgment_importance_field():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["sections"][0]["judgments"][0]["importance"] = "high"
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    assert "importance" not in result["sections"][0]["judgments"][0]
    assert result["sections"][0]["judgments"][0]["judgment"]


def test_fulltext_validator_ignores_placeholder_custom_label():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0]["custom_label"] = "None"
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    assert "custom_label" not in result["financial_risks"][0]
    assert result["financial_risks"][0]["risk_type"] == "inventory_impairment"


def test_fulltext_validator_backfills_risks_from_section_judgments():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    parsed["sections"][2]["judgments"] = [
        {
            "judgment": "客户集中风险判断：前五名客户销售额占年度销售总额 33.13%，第一大客户占比 7.79%，后续需要跟踪主要客户订单变化。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]
    parsed["sections"][5]["judgments"] = [
        {
            "judgment": "存货风险判断：存货账面价值 1,448,216,300.11 元，占总资产 20.83%，资产减值损失 -170,237,600.06 元，主要为存货跌价准备。",
            "evidence_refs": ["fulltext-3-0"],
            "confidence": 85,
        }
    ]
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    risk_types = [risk["risk_type"] for risk in result["financial_risks"]]
    assert "customer_concentration" in risk_types
    assert "inventory_impairment" in risk_types
    for risk in result["financial_risks"]:
        assert "该风险已在年报证据中出现" not in risk.get("mechanism", "")


def test_fulltext_validator_remaps_cashflow_mislabeled_as_revenue_recognition():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0] = {
        "risk_type": "revenue_recognition",
        "importance": "medium",
        "summary": "经营活动现金流量净额 466,319,946.20 元，同比下降 15.11%，低于净利润 547,059,403.97 元。",
        "mechanism": "经营现金流与净利润背离会影响盈利质量判断。",
        "tracking_indicators": ["经营活动现金流量净额", "净利润"],
        "evidence_refs": ["fulltext-1-0"],
        "confidence": 85,
    }
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    assert result["financial_risks"][0]["risk_type"] == "cash_flow_quality"


def test_fulltext_validator_remaps_cashflow_mislabeled_as_inventory_and_deduplicates():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    cashflow_risk = {
        "risk_type": "cash_flow_quality",
        "importance": "high",
        "summary": "经营活动现金流量净额 466,319,946.20 元，同比下降 15.11%，低于净利润 547,059,403.97 元。",
        "mechanism": "经营现金流与净利润背离会影响盈利质量判断。",
        "tracking_indicators": ["经营活动现金流量净额", "净利润"],
        "evidence_refs": ["fulltext-1-0"],
        "confidence": 85,
    }
    mislabeled_risk = {
        **cashflow_risk,
        "risk_type": "inventory_impairment",
        "importance": "medium",
    }
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["financial_risks"] = [cashflow_risk, mislabeled_risk]
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    risk_types = [risk["risk_type"] for risk in result["financial_risks"]]
    assert risk_types.count("cash_flow_quality") == 1
    assert "inventory_impairment" not in risk_types


def test_fulltext_validator_remaps_dealer_price_adjustment_mislabeled_as_inventory():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0] = {
        "risk_type": "inventory_impairment",
        "importance": "medium",
        "summary": "经销模式存在价格调整政策，管理层需估计价格调整金额并冲减收入。",
        "mechanism": "若终端价格下行，价格调整估计可能影响收入确认准确性。",
        "tracking_indicators": ["经销收入占比", "价格调整金额", "冲减收入"],
        "evidence_refs": ["fulltext-2-0"],
        "confidence": 85,
    }
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    assert result["financial_risks"][0]["risk_type"] == "revenue_recognition"


def test_fulltext_validator_remaps_model_governance_alias_to_existing_risk_type():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0] = {
        "risk_type": "governance_risk",
        "importance": "medium",
        "summary": "审计意见和内部控制事项需要持续关注，治理透明度可能影响投资者判断。",
        "mechanism": "审计、内控和治理信号会影响财务信息质量和信息透明度。",
        "tracking_indicators": ["审计意见", "内部控制", "治理事项"],
        "evidence_refs": ["fulltext-3-0"],
        "confidence": 80,
    }

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    assert result["financial_risks"][0]["risk_type"] == "audit_internal_control"


def test_fulltext_validator_remaps_supplier_summary_mislabeled_as_customer_risk():
    text = SAMPLE_FULLTEXT_REPORT + "\n前五名供应商采购额占比73.45%，第一大供应商占比32.56%。\n"
    pack = build_periodic_report_fulltext_pack(text, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["financial_risks"] = [
        {
            "risk_type": "customer_concentration",
            "importance": "medium",
            "summary": "前五名供应商采购额占比73.45%，第一大供应商占比32.56%，供应商集中度较高。",
            "mechanism": "若供应商产能或价格出现不利变动，将对公司成本端形成直接压力。",
            "tracking_indicators": ["前五名供应商采购额占比", "第一大供应商占比"],
            "evidence_refs": ["fulltext-3-0"],
            "confidence": 85,
        }
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    assert result["financial_risks"][0]["risk_type"] == "supplier_concentration"


def test_fulltext_validator_deduplicates_overlapping_audit_and_governance_risks():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    for section in parsed["sections"]:
        section["judgments"] = []
    base = {
        "importance": "high",
        "summary": "公司因信息披露违法违规被监管处罚，管理层相关人员受到处罚，需关注内控整改。",
        "mechanism": "信披、监管处罚和内控整改会影响财务信息质量和公司治理透明度。",
        "tracking_indicators": ["监管处罚", "内部控制", "整改进展"],
        "evidence_refs": ["fulltext-3-0"],
        "confidence": 90,
    }
    parsed["financial_risks"] = [
        {"risk_type": "audit_internal_control", **base},
        {"risk_type": "related_party_governance", **base},
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    risk_types = [risk["risk_type"] for risk in result["financial_risks"]]
    assert risk_types == ["audit_internal_control"]


def test_fulltext_validator_drops_positive_profit_quality_observation_without_risk_mechanism():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["financial_risks"] = [
        {
            "risk_type": "profit_quality",
            "importance": "medium",
            "summary": "营业收入同比增长16.46%，归母净利润同比增长9.36%，盈利质量改善。",
            "mechanism": "收入和利润均实现增长，体现经营改善。",
            "tracking_indicators": ["收入增速", "净利润增速", "毛利率", "经营现金流"],
            "evidence_refs": ["fulltext-1-0"],
            "confidence": 90,
        }
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    assert result["financial_risks"] == []


def test_fulltext_validator_replaces_generic_risk_mechanism_and_tracking_indicators():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"][0] = {
        "risk_type": "profit_quality",
        "importance": "medium",
        "summary": "营业收入 3,898,054,583.68 元，同比增长 16.46%，扣非净利润 427,582,529.58 元，同比下降 -5.23%。",
        "mechanism": "该风险已在年报证据中出现，需要在后续报告中关注其变化。",
        "tracking_indicators": ["相关风险证据", "后续披露变化"],
        "evidence_refs": ["fulltext-1-0"],
        "confidence": 80,
    }
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    risk = result["financial_risks"][0]
    assert risk["risk_type"] == "profit_quality"
    assert "该风险已在年报证据中出现" not in risk["mechanism"]
    assert "利润增速" in risk["mechanism"]
    assert risk["tracking_indicators"] == ["收入增速", "扣非净利润", "毛利率", "经营现金流"]


def test_fulltext_validator_deduplicates_other_material_same_as_candidate():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = [
        {
            "risk_type": "other_material_risk",
            "custom_label": "重大诉讼风险",
            "importance": "medium",
            "summary": "重大诉讼风险：合同纠纷诉讼冻结资金 4,400 万元。",
            "mechanism": "诉讼可能影响现金流。",
            "tracking_indicators": ["诉讼进展", "冻结资金"],
            "evidence_refs": ["fulltext-3-0"],
            "confidence": 75,
        },
    ]
    parsed["sections"][5]["judgments"] = [
        {
            "judgment": "诉讼风险判断：合同纠纷诉讼冻结资金 4,400 万元，需要跟踪诉讼进展。",
            "evidence_refs": ["fulltext-3-0"],
            "confidence": 75,
        }
    ]
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    labels = [
        risk.get("custom_label") if risk.get("risk_type") == "other_material_risk" else risk.get("risk_type")
        for risk in result["financial_risks"]
    ]
    assert labels.count("重大诉讼风险") == 1
    assert "litigation_contingency" not in labels


def test_fulltext_validator_deduplicates_cashflow_and_collection_when_same_evidence():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    parsed["financial_risks"] = [
        {
            "risk_type": "cash_flow_quality",
            "importance": "high",
            "summary": "经营活动现金流量净额 466,319,946.20 元，同比下降 15.11%，低于净利润 547,059,403.97 元。",
            "mechanism": "经营现金流与净利润背离会影响盈利质量判断。",
            "tracking_indicators": ["经营活动现金流量净额", "净利润"],
            "evidence_refs": ["fulltext-1-0"],
            "confidence": 85,
        },
        {
            "risk_type": "receivables_collection",
            "importance": "medium",
            "summary": "经营活动现金流量净额 466,319,946.20 元，同比下降 15.11%，低于净利润 547,059,403.97 元。",
            "mechanism": "回款变化会影响经营现金流稳定性。",
            "tracking_indicators": ["经营活动现金流量净额", "净利润"],
            "evidence_refs": ["fulltext-1-0"],
            "confidence": 80,
        },
    ]
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    risk_types = [risk["risk_type"] for risk in result["financial_risks"]]
    assert "cash_flow_quality" in risk_types
    assert "receivables_collection" not in risk_types


def test_fulltext_validator_deduplicates_identical_risk_text_across_types():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=True))
    for section in parsed["sections"]:
        section["judgments"] = []
    duplicate_summary = "综合毛利率下降，营业成本同比上升，技术服务成本增加，盈利质量需要跟踪。"
    duplicate_mechanism = "利润增速、毛利率或扣非利润变化会影响盈利质量和持续性判断。"
    parsed["financial_risks"] = [
        {
            "risk_type": "cash_flow_quality",
            "importance": "medium",
            "summary": duplicate_summary,
            "mechanism": duplicate_mechanism,
            "tracking_indicators": ["收入增速", "扣非净利润", "毛利率", "经营现金流"],
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 85,
        },
        {
            "risk_type": "profit_quality",
            "importance": "medium",
            "summary": duplicate_summary,
            "mechanism": duplicate_mechanism,
            "tracking_indicators": ["收入增速", "扣非净利润", "毛利率", "经营现金流"],
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 85,
        },
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    assert len(result["financial_risks"]) == 1
    assert result["financial_risks"][0]["risk_type"] == "cash_flow_quality"


def test_fulltext_validator_does_not_backfill_supplier_from_generic_fabless_text():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    parsed["sections"][0]["judgments"] = [
        {
            "judgment": "公司采用Fabless模式，将晶圆制造与封装测试外包，同时拥有38大类6,800余款可供销售产品。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    risk_types = [risk["risk_type"] for risk in result["financial_risks"]]
    assert "supplier_concentration" not in risk_types


def test_fulltext_validator_drops_judgment_with_invented_number():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response())
    parsed["sections"][1]["judgments"] = [
        {
            "judgment": "主营业务表现判断：营业收入达到 999.99 亿元，说明规模远超证据。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]
    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)
    assert result["sections"][1]["title"] == "主营业务表现"
    assert result["sections"][1]["judgments"] == []


def test_fulltext_validator_allows_ground_truth_number_not_in_fulltext_block():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response())
    parsed["sections"][1]["judgments"] = [
        {
            "judgment": "主营业务表现判断：确定性指标显示经销收入 360991.14万元，说明渠道规模需要单独跟踪。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]
    required_metrics = {
        "schema_version": "test",
        "sales_mode_rows": [
            {
                "label": "经销",
                "revenue": {"text": "360,991.14", "unit": "万元", "normalized": "360991.14万元"},
            }
        ],
        "normalized_values": ["360991.14万元"],
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_metrics=required_metrics,
    )

    judgments = result["sections"][1]["judgments"]
    assert any("360991.14万元" in item["judgment"] for item in judgments)


def test_fulltext_validator_allows_multiple_ground_truth_numbers_without_concatenating():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response())
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["sections"][1]["judgments"] = [
        {
            "judgment": "主营业务表现判断：直销收入占比98.69%，约377.39亿元，说明收入主要来自直销模式。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]
    required_metrics = {
        "schema_version": "test",
        "sales_mode_rows": [
            {
                "label": "直销",
                "revenue": {"text": "3,773,895.11", "unit": "万元", "normalized": "3773895.11万元"},
                "revenue_ratio": {"text": "98.69", "unit": "%", "normalized": "98.69%"},
            }
        ],
        "normalized_values": ["3773895.11万元", "98.69%"],
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_metrics=required_metrics,
    )

    judgments = result["sections"][1]["judgments"]
    assert any("377.39亿元" in item["judgment"] for item in judgments)


def test_fulltext_validator_filters_financial_risk_with_untraceable_number():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["financial_risks"] = [
        {
            "risk_type": "inventory_impairment",
            "importance": "high",
            "summary": "存货金额达到 999.99 亿元，远高于证据和确定性指标。",
            "mechanism": "若存货规模继续扩大，可能压制毛利率。",
            "tracking_indicators": ["存货金额 999.99 亿元", "毛利率"],
            "evidence_refs": ["fulltext-3-0"],
            "confidence": 85,
        }
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    assert all("999.99" not in risk.get("summary", "") for risk in result["financial_risks"])


def test_fulltext_validator_allows_financial_risk_ground_truth_number_not_in_fulltext_block():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["financial_risks"] = [
        {
            "risk_type": "profit_quality",
            "importance": "medium",
            "summary": "确定性指标显示经销收入 360991.14万元，渠道收入占比需要跟踪。",
            "mechanism": "经销渠道变化可能影响收入确认节奏和毛利率。",
            "tracking_indicators": ["经销收入 360991.14万元", "毛利率"],
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]
    required_metrics = {
        "schema_version": "test",
        "sales_mode_rows": [
            {
                "label": "经销",
                "revenue": {"text": "360,991.14", "unit": "万元", "normalized": "360991.14万元"},
            }
        ],
        "normalized_values": ["360991.14万元"],
    }

    result = validate_periodic_report_fulltext_output(
        json.dumps(parsed, ensure_ascii=False),
        pack,
        required_metrics=required_metrics,
    )

    assert any("360991.14万元" in risk["summary"] for risk in result["financial_risks"])


def test_fulltext_validator_keeps_product_model_numbers_and_certification_codes():
    pack = build_periodic_report_fulltext_pack(HUIZHIWEI_LIKE_FULLTEXT_REPORT, chunk_chars=9000)
    parsed = json.loads(_fixed_section_response(include_risks=False))
    for section in parsed["sections"]:
        section["judgments"] = []
    parsed["sections"][3]["judgments"] = [
        {
            "judgment": "研发与技术进展判断：5G UHB L-PAMiF、RedCap 与 AEC-Q104 认证均来自年报原文，说明产品导入仍是跟踪重点。",
            "evidence_refs": ["fulltext-2-0"],
            "confidence": 80,
        }
    ]

    result = validate_periodic_report_fulltext_output(json.dumps(parsed, ensure_ascii=False), pack)

    assert any("AEC-Q104" in item["judgment"] for item in result["sections"][3]["judgments"])


def test_fulltext_markdown_renders_fixed_sections_and_refs():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    result = validate_periodic_report_fulltext_output(_fixed_section_response(include_risks=True), pack)
    markdown = render_periodic_report_fulltext_markdown({
        **result,
        "source_type": "periodic_report_fulltext_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
    })
    assert "# 定期报告全文判断摘要" in markdown
    assert "## 管理层市场判断" in markdown
    assert "### 重点财务风险清单" in markdown
    assert "inventory_impairment" in markdown
    assert "平台型产品扩张转化风险" in markdown
    assert "依据：fulltext-2-0" in markdown
    assert "12.3%" in markdown


def test_fulltext_markdown_renders_required_metrics_section():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    result = validate_periodic_report_fulltext_output(_fixed_section_response(include_risks=True), pack)
    evidence_pack = build_periodic_report_evidence_pack(SAMPLE_FULLTEXT_REPORT)
    required_metrics = build_required_business_metrics(evidence_pack, raw_text=SAMPLE_FULLTEXT_REPORT)
    markdown = render_periodic_report_fulltext_markdown(
        {
            **result,
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
        },
        required_metrics=required_metrics,
    )
    assert "## 必备经营指标摘录" in markdown
    assert "### 分产品/业务毛利率" in markdown
    assert "信号链产品" in markdown
    assert "147102.29万元" in markdown
    assert "58.17%" in markdown
    assert "### 客户/供应商集中度" in markdown


def test_fulltext_markdown_renders_required_financial_metrics_section():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    result = validate_periodic_report_fulltext_output(_fixed_section_response(include_risks=True), pack)
    evidence_pack = build_periodic_report_evidence_pack(SAMPLE_FULLTEXT_REPORT)
    required_financial_metrics = build_required_financial_risk_metrics(
        evidence_pack,
        raw_text=SAMPLE_FULLTEXT_REPORT,
    )
    markdown = render_periodic_report_fulltext_markdown(
        {
            **result,
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
        },
        required_financial_metrics=required_financial_metrics,
    )
    assert "## 必备财务风险指标摘录" in markdown
    assert "### 盈利质量与现金流" in markdown
    assert "经营现金流" in markdown
    assert "46631.99万元" in markdown
    assert "### 存货与减值" in markdown
    assert "144821.63万元" in markdown


def test_fulltext_markdown_renders_hk_required_financial_metrics_fields():
    pack = build_periodic_report_fulltext_pack(HK_BLACK_SESAME_LIKE_REPORT, chunk_chars=9000)
    result = validate_periodic_report_fulltext_output(_fixed_section_response(include_risks=True), pack)
    required_financial_metrics = {
        "profit_quality": {
            "revenue": {"text": "822,328", "unit": "千元", "normalized": "82232.80万元"},
            "revenue_yoy": {"text": "73.4%", "unit": "%", "normalized": "73.4%"},
            "gross_profit": {"text": "337,089", "unit": "千元", "normalized": "33708.90万元"},
            "gross_margin": {"text": "41.0%", "unit": "%", "normalized": "41.0%"},
            "operating_loss": {"text": "-1,448,320", "unit": "千元", "normalized": "-144832.00万元"},
            "adjusted_net_loss": {"text": "-1,075,674", "unit": "千元", "normalized": "-107567.40万元"},
            "rd_expense": {"text": "-1,417,423", "unit": "千元", "normalized": "-141742.30万元"},
        },
        "cash_flow_quality": {
            "operating_cash_flow": {"text": "-985,373", "unit": "千元", "normalized": "-98537.30万元"},
        },
        "financial_assets": {
            "fair_value_financial_assets": {"text": "231,308", "unit": "千元", "normalized": "23130.80万元"},
        },
        "leverage_liquidity": {
            "borrowings": {"text": "739,892", "unit": "千元", "normalized": "73989.20万元"},
        },
        "government_grants": {
            "government_grants_current": {"text": "99,762", "unit": "千元", "normalized": "9976.20万元"},
        },
        "corporate_actions": {
            "placing_net_proceeds": {"text": "1,142.1", "unit": "百万元", "normalized": "114210.00万元"},
            "acquisition_consideration": {"text": "478.02", "unit": "百万元", "normalized": "47802.00万元"},
        },
    }
    markdown = render_periodic_report_fulltext_markdown(
        {
            **result,
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
        },
        required_financial_metrics=required_financial_metrics,
    )

    assert "毛利 33708.90万元" in markdown
    assert "毛利率 41.0%" in markdown
    assert "经营亏损 -144832.00万元" in markdown
    assert "经调整亏损 -107567.40万元" in markdown
    assert "研发开支 -141742.30万元" in markdown
    assert "经营现金流 -98537.30万元" in markdown
    assert "公允价值金融资产 23130.80万元" in markdown
    assert "借款 73989.20万元" in markdown
    assert "政府补助 9976.20万元" in markdown
    assert "配售募资 114210.00万元" in markdown
    assert "收购对价 47802.00万元" in markdown


def test_fulltext_markdown_renders_derived_financial_metrics_section():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    result = validate_periodic_report_fulltext_output(_fixed_section_response(include_risks=True), pack)
    required_financial_metrics = {
        "derived_financial_metrics": {
            "rd_expense_to_revenue": {"text": "172.37%", "unit": "%", "normalized": "172.37%"},
            "rd_expense_to_gross_profit": {"text": "420.49%", "unit": "%", "normalized": "420.49%"},
            "operating_cash_outflow_to_cash": {"text": "68.11%", "unit": "%", "normalized": "68.11%"},
            "receivables_to_revenue": {"text": "68.01%", "unit": "%", "normalized": "68.01%"},
            "acquisition_to_cash_and_fv_assets": {"text": "28.49%", "unit": "%", "normalized": "28.49%"},
        }
    }
    markdown = render_periodic_report_fulltext_markdown(
        {
            **result,
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
        },
        required_financial_metrics=required_financial_metrics,
    )

    assert "### 派生风险比例" in markdown
    assert "研发开支/收入" in markdown
    assert "172.37%" in markdown
    assert "研发开支/毛利" in markdown
    assert "420.49%" in markdown
    assert "经营现金净流出/现金" in markdown
    assert "68.11%" in markdown
    assert "贸易应收款项及应收票据/收入" in markdown
    assert "68.01%" in markdown
    assert "收购对价/(现金+公允价值金融资产)" in markdown
    assert "28.49%" in markdown


def test_fulltext_audit_markdown_expands_referenced_source_blocks():
    pack = build_periodic_report_fulltext_pack(SAMPLE_FULLTEXT_REPORT, chunk_chars=9000)
    result = validate_periodic_report_fulltext_output(_fixed_section_response(include_risks=True), pack)
    audit = render_periodic_report_fulltext_audit_markdown(result, pack, max_excerpt_chars=260)
    assert "# 定期报告全文判断证据审计" in audit
    assert "## 公司画像" in audit
    assert "公司画像判断" in audit
    assert "### 证据 fulltext-2-0" in audit
    assert "公司产品覆盖信号链、电源管理、传感器三大方向" in audit
    assert "## 财务风险证据" in audit
    assert "inventory_impairment" in audit
    assert "### 证据 fulltext-3-0" in audit
    assert "存货账面价值 1,448,216,300.11 元" in audit


def test_import_does_not_require_openai_or_network_clients():
    helper_path = Path(__file__).parent.parent.parent / "scripts" / "utils"
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(helper_path)!r})\n"
        "sys.modules['openai'] = None\n"
        "import periodic_report_fulltext_llm_analysis\n"
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


def _fixed_section_response(*, include_risks: bool = False) -> str:
    section_payloads = {
        "公司画像": "公司画像判断：公司产品覆盖信号链、电源管理、传感器三大方向，拥有38大类6,800余款可供销售产品，说明它更像平台型模拟芯片公司而非单品类公司。",
        "主营业务表现": "主营业务表现判断：信号链产品收入 1,471,022,875.27 元、毛利率 58.17%，电源管理产品收入 2,379,833,746.57 元、毛利率 46.38%，说明两条主线盈利结构不同。",
        "客户与订单结构": "客户与订单结构判断：年报文本显示下游汽车电子、工业控制、机器人和数据中心需求扩张，后续要跟踪这些场景是否转化为订单。",
        "研发与技术进展": "研发与技术进展判断：公司拥有38大类6,800余款可供销售产品，说明研发和产品扩张是公司平台化的关键支撑。",
        "管理层市场判断": "管理层市场判断：管理层引用资料称模拟芯片市场预计 CAGR 为 12.3%，下游包括汽车电子、工业控制、机器人和数据中心，这一判断可作为需求侧假设但不是外部确认事实。",
        "财务风险与跟踪指标": "财务风险判断：存货账面价值 1,448,216,300.11 元、占总资产 20.83%，资产减值损失 -170,237,600.06 元，后续要跟踪库存消化和跌价准备。",
    }
    payload = {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "sections": [
            {
                "title": title,
                "judgments": [
                    {
                        "judgment": section_payloads[title],
                        "evidence_refs": ["fulltext-2-0"],
                        "confidence": 80,
                    }
                ],
            }
            for title in FIXED_ANALYSIS_SECTION_TITLES
        ],
    }
    if include_risks:
        payload["financial_risks"] = [
            {
                "risk_type": "inventory_impairment",
                "importance": "high",
                "summary": "存货账面价值 1,448,216,300.11 元，占总资产 20.83%，资产减值损失 -170,237,600.06 元，主要为存货跌价准备。",
                "mechanism": "库存和跌价准备会影响后续毛利率与利润释放，若需求转弱可能继续计提减值。",
                "tracking_indicators": ["存货账面价值", "资产减值损失", "毛利率"],
                "evidence_refs": ["fulltext-3-0"],
                "confidence": 90,
            },
            {
                "risk_type": "other_material_risk",
                "custom_label": "平台型产品扩张转化风险",
                "importance": "medium",
                "summary": "公司拥有38大类6,800余款可供销售产品，产品覆盖信号链、电源管理、传感器三大方向。",
                "mechanism": "产品线扩张需要持续研发和客户导入，若新产品放量不及预期，研发投入可能继续压制利润。",
                "tracking_indicators": ["研发投入", "新产品收入贡献", "客户导入进度"],
                "evidence_refs": ["fulltext-2-0"],
                "confidence": 80,
            },
        ]
    return json.dumps(payload, ensure_ascii=False)
