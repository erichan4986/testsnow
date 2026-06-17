import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "report_skills"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from claim_risk_signal_skill import claim_risk_signal_skill
from skill_pipeline import SkillContext


def test_bridge_does_not_modify_synthesis_text_or_core_facts(tmp_path):
    """Enabling claim_risk_signals must not add Agent-Reach URLs/titles to synthesis or citations."""
    stock_dir = tmp_path / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "official.md").write_text(
        '---\n'
        '{"stock": "黑芝麻智能", "source_type": "company_official", "source_credit": 85, "title": "官方公告", "url": "https://blacksesame.com/news", "claims": [{"claim_text": "A1000芯片量产", "topics": ["product_progress"]}]}\n'
        '---\n',
        encoding="utf-8",
    )
    (stock_dir / "social.md").write_text(
        '---\n'
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "claims": [{"claim_text": "价格战压力", "topics": ["competition"]}]}\n'
        '---\n',
        encoding="utf-8",
    )

    ctx = SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "enable_claim_risk_signals": True,
            "claim_verification_base_dir": str(tmp_path),
            "synthesis_text": "现有合成文本",
            "core_facts": [{"fact": "base"}],
        }
    )
    claim_risk_signal_skill(ctx)

    assert ctx.output["claim_risk_signal_status"] == "ok"
    assert any(s["name"] == "竞争格局恶化" for s in ctx.output["structured_risk_signals"])
    # The bridge must only set structured_risk_signals.
    assert ctx.output.get("synthesis_text") is None
    assert ctx.output.get("core_facts") is None
    assert ctx.output.get("citations") is None
    # No Agent-Reach URL/title leaked into signals.
    for sig in ctx.output["structured_risk_signals"]:
        assert "blacksesame.com" not in sig["evidence_text"]
        assert "官方公告" not in sig["evidence_text"]
        assert sig["source"] == "claim_verification"
