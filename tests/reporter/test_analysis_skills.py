import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from report_skills.analysis_skills import cross_source_consolidation_skill, scoring_skill


def test_cross_source_consolidation_empty():
    ctx = SkillContext(input={
        "keep_posts": [],
        "stock_raw": {},
    })
    result = cross_source_consolidation_skill(ctx)
    assert result.get("consolidated") is not None
    assert result.get("cross_source_summary") == ""


def test_scoring_skill_basic():
    ctx = SkillContext(input={
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {"composite_score": 7, "trend": "多头"},
                },
            },
        },
        "keep_posts": [
            {"title": "t1", "like": 100, "comment": 50, "content": "c1"},
        ],
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "ps": None,
    })
    result = scoring_skill(ctx)
    pillar = result.get("pillar_scores")
    assert pillar is not None
    assert "valuation" in pillar
    assert "technical" in pillar
    assert result.get("total_score") is not None
