import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from report_skills.periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill


def test_periodic_report_fulltext_intake_sets_explanation_pack_from_cache(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    cache_file = cache_dir / "000001_2025_annual_jina.txt"
    cache_file.write_text(
        """
2025年年度报告

二、经营情况讨论与分析

营业收入变动原因说明：主要系公司FPGA与MCU产品销售额增加所致。

订单客户与经营计划：公司将继续拓展工业控制和智能电表客户应用。
""",
        encoding="utf-8",
    )
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "000001"},
        "periodic_report_fulltext_cache_dir": str(cache_dir),
    })

    result = periodic_report_fulltext_intake_skill(ctx)

    pack = result.get("periodic_report_explanation_pack")
    topics = {row["topic"] for row in pack["rows"]}
    assert pack["schema"] == "formal_financial_explanation_pack.v1"
    assert "revenue_change" in topics
    assert "orders_customers_guidance" in topics
    assert pack["source_doc"] == "000001_2025_annual_jina.txt"
