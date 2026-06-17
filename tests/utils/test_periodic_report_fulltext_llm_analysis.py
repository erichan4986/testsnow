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
    render_periodic_report_fulltext_markdown,
    summarize_periodic_report_fulltext_with_llm,
    validate_periodic_report_fulltext_output,
)
from periodic_report_evidence_pack import build_periodic_report_evidence_pack
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
    assert "financial_risks 必须输出 5-9 条" in prompt["system"]
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
