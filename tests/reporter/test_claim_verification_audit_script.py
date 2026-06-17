import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from claim_verification import ClaimCandidate, ClaimVerification, ClaimVerificationPlan


SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke_claim_verification_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_claim_verification_audit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate(claim_id, text, credit=30, source_file="low.md", title=""):
    return ClaimCandidate(
        claim_id=claim_id,
        stock="中简科技",
        source_file=source_file,
        source_type="social_discussion" if credit < 55 else "company_announcement",
        source_credit=credit,
        verification_status="market_opinion" if credit < 55 else "confirmed_fact",
        claim_status="unverified_claim" if credit < 55 else "confirmed_fact",
        claim_text=text,
        topics=["market_sentiment"],
        title=title,
    )


def _plan():
    high = _candidate("h1", "公告确认研发费用同比增长", credit=90, source_file="official.md", title="2026 Q1 公告")
    verified_low = _candidate("l1", "我认为中简科技研发费用增长", source_file="fresh.md")
    unverified_low = _candidate("l2", "股吧帖子：中简科技护城河很深", source_file="fresh.md")
    return ClaimVerificationPlan(
        stock="中简科技",
        high_credit_claims=[high],
        low_credit_claims=[verified_low, unverified_low],
        verifications=[
            ClaimVerification(
                claim_id="l1",
                action="verified",
                verified_by=["h1"],
                conflicts_with=[],
                confidence=84,
                reasons=["specific terms: 研发费用, 同比"],
            ),
            ClaimVerification(
                claim_id="l2",
                action="unverified",
                verified_by=[],
                conflicts_with=[],
                confidence=20,
                reasons=["no high or medium credit source with matching topic and terms"],
            ),
        ],
        skipped_files=[],
    )


def test_render_claim_verification_audit_markdown_groups_actions():
    module = _load_module()
    text = module.render_claim_verification_audit(_plan())

    assert "# 中简科技 Claim Verification Audit" in text
    assert "| high_credit_claims | 1 |" in text
    assert "| low_credit_claims | 2 |" in text
    assert "## Verified" in text
    assert "Max Credit" in text
    assert "Source Count" in text
    assert "我认为中简科技研发费用增长" in text
    assert "2026 Q1 公告" in text
    assert "## Unverified" in text
    assert "股吧帖子：中简科技护城河很深" in text
    assert "[^1]" not in text


def test_render_claim_verification_audit_preserves_merged_source_files():
    module = _load_module()
    plan = _plan()
    plan.low_credit_claims[0] = _candidate(
        "l1",
        "我认为中简科技研发费用增长",
        source_file="knowledge/10-Stocks/中简科技/a.md, knowledge/10-Stocks/中简科技/b.md",
    )

    text = module.render_claim_verification_audit(plan)

    assert "a.md, b.md" in text


def test_render_claim_verification_audit_shows_structured_provenance_fields():
    module = _load_module()
    plan = _plan()
    plan.low_credit_claims[0] = _candidate(
        "l1",
        "我认为中简科技研发费用增长",
        source_file="knowledge/10-Stocks/中简科技/a.md",
    )
    plan.low_credit_claims[0] = ClaimCandidate(
        **{
            **plan.low_credit_claims[0].__dict__,
            "source_files": ["knowledge/10-Stocks/中简科技/a.md", "knowledge/10-Stocks/中简科技/b.md"],
            "source_types": ["social_discussion", "eastmoney_guba"],
            "source_credits": [30, 35],
            "max_source_credit": 35,
            "source_count": 2,
        }
    )

    text = module.render_claim_verification_audit(plan)

    assert "a.md, b.md" in text
    assert "| 35 | 2 |" in text


def test_run_audit_writes_markdown(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "build_claim_verification_plan", lambda stock, base_dir: _plan())

    out = tmp_path / "audit.md"
    result = module.run_audit(stock="中简科技", base_dir=str(tmp_path), output=str(out))

    assert result["status"] == "written"
    assert result["path"] == str(out)
    written = out.read_text(encoding="utf-8")
    assert "Claim Verification Audit" in written
    assert "unverified_claim" not in written
