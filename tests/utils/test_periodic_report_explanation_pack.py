import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_explanation_pack import build_formal_financial_explanation_pack


SAMPLE_ANNUAL_TEXT = """
复旦微电 2025年年度报告

二、经营情况讨论与分析

营业收入变动原因说明：主要系报告期内公司的安全与识别芯片、智能电表芯片及FPGA销售额增加所致。

归属于上市公司股东的净利润变动原因说明：主要系产品结构变化及研发投入增加影响利润表现。

研发投入情况：公司持续推进高端 FPGA、MCU 及非易失存储产品研发。

订单客户与经营计划：公司将继续拓展工业控制、智能电表、汽车电子等客户应用。

四、风险因素

营业收入可能受到市场竞争加剧、客户需求不及预期等风险影响。
"""


def test_build_explanation_pack_extracts_financial_change_reasons():
    pack = build_formal_financial_explanation_pack(
        SAMPLE_ANNUAL_TEXT,
        stock_name="复旦微电",
        source_doc="2025年年度报告",
    )

    topics = {row["topic"] for row in pack["rows"]}
    assert pack["schema"] == "formal_financial_explanation_pack.v1"
    assert "revenue_change" in topics
    assert "profit_change" in topics
    assert "expense_rnd" in topics
    assert "orders_customers_guidance" in topics
    revenue = next(row for row in pack["rows"] if row["topic"] == "revenue_change")
    assert "安全与识别芯片" in revenue["excerpt"]
    assert revenue["source_doc"] == "2025年年度报告"
    assert revenue["confidence"] >= 0.8
    assert revenue["excerpt_hash"]


def test_build_explanation_pack_excludes_risk_factor_matches():
    pack = build_formal_financial_explanation_pack(
        SAMPLE_ANNUAL_TEXT,
        stock_name="复旦微电",
        source_doc="2025年年度报告",
    )

    combined = "\n".join(row["excerpt"] for row in pack["rows"])
    assert "市场竞争加剧" not in combined
    assert "客户需求不及预期" not in combined


def test_build_explanation_pack_prefers_explicit_change_reason_over_table_noise():
    raw_text = """
研发投入占营业收入的比例（%） 26.88 31.80 减少4.92个百分点
工艺、新产品开发力度；同时受国际贸易环境变化影响，供应链及客户需求发生变动。

营业收入变动原因说明：主要系报告期内公司的安全与识别芯片、智能电表芯片及FPGA销售额增
加所致。
研发费用变动原因说明：主要系报告期内部分资本化研发项目撇销计入研发费用。
"""

    pack = build_formal_financial_explanation_pack(
        raw_text,
        stock_name="复旦微电",
        source_doc="2025年年度报告",
    )

    revenue = next(row for row in pack["rows"] if row["topic"] == "revenue_change")
    assert "安全与识别芯片" in revenue["excerpt"]
    assert "研发投入占营业收入的比例" not in revenue["excerpt"]
    assert revenue["confidence"] >= 0.9
