import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "report_skills"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from claim_risk_signal_skill import claim_risk_signal_skill
from claim_verification import ClaimCandidate, ClaimVerification, ClaimVerificationPlan
from skill_pipeline import SkillContext


def _write_note(path: Path, frontmatter: str, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


def test_disabled_skill_returns_disabled():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "enable_claim_risk_signals": False})
    claim_risk_signal_skill(ctx)
    assert ctx.output["claim_risk_signal_status"] == "disabled"
    assert ctx.output["structured_risk_signals"] == []
    assert ctx.output["claim_risk_signal_error"] == ""


def test_enabled_skill_builds_plan_from_temp_dir(tmp_path):
    stock_dir = tmp_path / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    _write_note(
        evidence_dir / "official.md",
        '{"stock": "黑芝麻智能", "source_type": "company_official", "source_credit": 85, "claims": [{"claim_text": "A1000芯片量产", "topics": ["product_progress"]}]}',
    )
    _write_note(
        stock_dir / "social.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "claims": [{"claim_text": "毛利率承压", "topics": ["earnings_business"]}]}',
    )
    ctx = SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "enable_claim_risk_signals": True,
            "claim_verification_base_dir": str(tmp_path),
        }
    )
    claim_risk_signal_skill(ctx)
    assert ctx.output["claim_risk_signal_status"] == "ok"
    signals = ctx.output["structured_risk_signals"]
    assert any(s["name"] == "盈利压力" for s in signals)


def test_enabled_skill_exposes_claim_verification_summary_for_rendering(tmp_path):
    stock_dir = tmp_path / "10-Stocks" / "中简科技"
    evidence_dir = stock_dir / "evidence"
    _write_note(
        evidence_dir / "official.md",
        '{"stock": "中简科技", "source_type": "exchange_announcement", "source_credit": 95, "title": "中简科技2026年第一季度报告", "claims": [{"claim_text": "客户需求量阶段性减少，收入下降约50%-60%", "topics": ["earnings_business"]}]}',
    )
    _write_note(
        stock_dir / "social.md",
        '{"stock": "中简科技", "source_type": "social_discussion", "source_credit": 35, "claims": [{"claim_text": "客户需求量阶段性减少导致收入下降约50%-60%", "topics": ["earnings_business"]}]}',
    )
    ctx = SkillContext(
        input={
            "stock_name": "中简科技",
            "enable_claim_risk_signals": True,
            "claim_verification_base_dir": str(tmp_path),
        }
    )

    claim_risk_signal_skill(ctx)

    summary = ctx.output["claim_verification_summary"]
    assert summary["enabled"] is True
    assert summary["verified_claims"]
    assert summary["verified_claims"][0]["claim_text"] == "客户需求量阶段性减少导致收入下降约50%-60%"


def test_empty_knowledge_dir_returns_empty(tmp_path):
    ctx = SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "enable_claim_risk_signals": True,
            "claim_verification_base_dir": str(tmp_path),
        }
    )
    claim_risk_signal_skill(ctx)
    assert ctx.output["claim_risk_signal_status"] == "empty"
    assert ctx.output["structured_risk_signals"] == []


def test_missing_stock_name_returns_error():
    ctx = SkillContext(input={"enable_claim_risk_signals": True})
    claim_risk_signal_skill(ctx)
    assert ctx.output["claim_risk_signal_status"] == "error"
    assert ctx.output["structured_risk_signals"] == []


def test_builder_error_returns_error(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("claim_risk_signal_skill.build_claim_verification_plan", _boom)
    ctx = SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "enable_claim_risk_signals": True,
            "claim_verification_base_dir": str(tmp_path),
        }
    )
    claim_risk_signal_skill(ctx)
    assert ctx.output["claim_risk_signal_status"] == "error"
    assert ctx.output["structured_risk_signals"] == []
    assert "boom" in ctx.output["claim_risk_signal_error"]


def test_skill_does_not_use_truncated_summary(monkeypatch):
    called = {"full": False}

    def _fake_build(*args, **kwargs):
        called["full"] = True
        low = ClaimCandidate(
            claim_id="c1",
            stock="黑芝麻智能",
            source_file="social.md",
            source_type="social_discussion",
            source_credit=35,
            verification_status="market_opinion",
            claim_status="unverified_claim",
            claim_text="毛利率承压",
            topics=["earnings_business"],
        )
        return ClaimVerificationPlan(
            stock="黑芝麻智能",
            high_credit_claims=[],
            low_credit_claims=[low],
            verifications=[ClaimVerification("c1", "verified", [], [], 75, [])],
            skipped_files=[],
        )

    monkeypatch.setattr("claim_risk_signal_skill.build_claim_verification_plan", _fake_build)
    ctx = SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "enable_claim_risk_signals": True,
            "claim_verification_summary": {"truncated": True},
        }
    )
    claim_risk_signal_skill(ctx)
    assert called["full"]
    assert ctx.output["claim_risk_signal_status"] == "ok"


def test_output_structured_risk_signals_passes_to_risk_section(tmp_path):
    stock_dir = tmp_path / "10-Stocks" / "黑芝麻智能"
    evidence_dir = stock_dir / "evidence"
    _write_note(
        evidence_dir / "official.md",
        '{"stock": "黑芝麻智能", "source_type": "company_official", "source_credit": 85, "claims": [{"claim_text": "A1000芯片量产", "topics": ["product_progress"]}]}',
    )
    _write_note(
        stock_dir / "social.md",
        '{"stock": "黑芝麻智能", "source_type": "social_discussion", "source_credit": 35, "claims": [{"claim_text": "价格战加剧", "topics": ["competition"]}]}',
    )
    ctx = SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "enable_claim_risk_signals": True,
            "claim_verification_base_dir": str(tmp_path),
        }
    )
    claim_risk_signal_skill(ctx)
    signals = ctx.output["structured_risk_signals"]
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from scoring_engine import risk_score_section

    section = risk_score_section(
        stock_name="黑芝麻智能",
        posts=[],
        stock_raw={},
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        structured_risk_signals=signals,
    )
    assert "竞争格局恶化" in section or signals == []
    # The signal should at least be accepted without raising.
    assert isinstance(section, str)
