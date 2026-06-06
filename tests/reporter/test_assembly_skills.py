import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.skill_pipeline import SkillContext
from utils.report_skills.assembly_skills import ReportAssemblySkill


def test_report_assembly_skill(tmp_path):
    skill = ReportAssemblySkill()
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "date_str": "20260604",
        "output_dir": str(tmp_path),
        "pillar_scores": {
            "valuation": 7.0,
            "technical": 6.0,
            "sentiment": 5.0,
            "fundamental": 6.0,
            "fundflow": 5.0,
        },
        "total_score": 5.8,
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "synthesis": {
            "industry_logic": "行业逻辑",
            "fundamentals": "基本面",
            "valuation_debate": "估值多空",
            "funding_sentiment": "资金情绪",
            "events_catalysts": "事件催化",
        },
        "keep_posts": [],
        "cross_source_summary": "",
    })
    result = skill.run(ctx)
    md_path = result.get("md_path")
    html_path = result.get("html_path")
    assert md_path is not None
    assert html_path is not None
    assert Path(md_path).exists()
    assert Path(html_path).exists()
