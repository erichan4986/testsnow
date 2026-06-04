import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from unittest.mock import MagicMock
from skill_pipeline import SkillContext
from report_skills.synthesis_skills import SynthesisSkill


def test_synthesis_skill_basic():
    mock_llm = MagicMock()
    mock_llm.chat.return_value = {
        "industry_logic": "行业逻辑",
        "fundamentals": "基本面",
        "valuation_debate": "估值多空",
        "funding_sentiment": "资金情绪",
        "events_catalysts": "事件催化",
    }

    skill = SynthesisSkill(llm_client=mock_llm)
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_raw": {
            "technical": {"indicators": {"_resonance": {"composite_score": 7}}},
            "reports": [],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })
    result = skill.run(ctx)
    synthesis = result.get("synthesis")
    assert synthesis is not None
    assert "industry_logic" in synthesis
