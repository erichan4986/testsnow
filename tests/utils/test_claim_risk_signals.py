import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from claim_risk_signals import derive_structured_risk_signals_from_plan
from claim_verification import ClaimCandidate, ClaimVerification, ClaimVerificationPlan


def _candidate(claim_id, claim_text, source_credit=35):
    return ClaimCandidate(
        claim_id=claim_id,
        stock="黑芝麻智能",
        source_file=f"knowledge/10-Stocks/黑芝麻智能/{claim_id}.md",
        source_type="social_discussion",
        source_credit=source_credit,
        verification_status="market_opinion",
        claim_status="unverified_claim",
        claim_text=claim_text,
        topics=["market_sentiment"],
        url="",
        title="",
    )


def _plan_with_verifications(verifications):
    low_claims = [_candidate(v.claim_id, f"claim {v.claim_id}") for v in verifications]
    return ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=low_claims,
        verifications=verifications,
        skipped_files=[],
    )


def _make_verification(claim_id, action, confidence=0, reasons=None):
    return ClaimVerification(
        claim_id=claim_id,
        action=action,
        verified_by=[],
        conflicts_with=[],
        confidence=confidence,
        reasons=reasons or [],
    )


@pytest.mark.parametrize(
    "text",
    [
        "A2000U 获 ISO 26262 ASIL-D 最高功能安全认证",
        "华山A2000U通过ISO 26262功能安全认证",
        "黑芝麻智能获得ASIL-D认证",
        "技术突破：功能安全认证完成",
    ],
)
def test_official_certification_no_tech_route_risk(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "技术路线风险" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "地平线",
        "Mobileye",
        "竞品分析",
        "竞争对手包括地平线和Mobileye",
        "黑芝麻智能与竞品对比",
    ],
)
def test_bare_competitor_no_competition_risk(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "竞争格局恶化" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "毛利率提升",
        "毛利率改善",
        "亏损收窄",
        "亏损减少",
        "亏损改善",
        "费用率下降",
        "费用控制有效",
        "利润增长",
        "扭亏为盈",
    ],
)
def test_positive_profit_no_earnings_pressure(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "盈利压力" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "收入增长",
        "营收增长",
        "收入同比增长50%",
    ],
)
def test_positive_revenue_no_performance_downgrade(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "业绩预期下调" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "收入下降约50%-60%",
        "营收下降约50%",
        "客户需求量阶段性减少导致发货暂时减少",
    ],
)
def test_revenue_decline_true_positives(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "业绩预期下调" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "港股通纳入",
        "流动性改善",
        "资金净流入",
        "增持股份",
        "公司回购股票",
    ],
)
def test_positive_capital_no_outflow(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "资金流出" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "难以被替代",
        "不被替代",
        "未被替代",
        "护城河深厚，难以被替代",
    ],
)
def test_substitution_resistance_no_competition_risk(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "竞争格局恶化" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "未通过认证",
        "未通过 ISO 26262 认证",
        "未获认证",
        "未获 ASIL-D 认证",
        "未获得功能安全认证",
        "认证受阻",
        "技术路线不确定",
        "功能安全风险",
        "架构迭代风险",
        "技术替代风险",
    ],
)
def test_tech_route_risk_true_positives(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "技术路线风险" and s["status"] == "verified" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "毛利率承压",
        "毛利率下滑",
        "毛利压缩",
        "费用扩张侵蚀利润",
        "盈利压力加大",
        "亏损扩大",
    ],
)
def test_earnings_pressure_true_positives(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "盈利压力" and s["status"] == "verified" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "价格战",
        "竞争格局恶化",
        "竞争加剧",
        "降价压力",
        "份额下滑",
        "被对手替代",
        "竞品挤压",
    ],
)
def test_competition_risk_true_positives(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "竞争格局恶化" and s["status"] == "verified" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "资金净流出",
        "主力净流出",
        "减持压力",
        "做空压力",
        "外资用这一招做空",
        "退通风险",
        "港股通会直接退通",
        "流动性恶化",
    ],
)
def test_capital_outflow_true_positives(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "资金流出" and s["status"] == "verified" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "空单比例较低",
        "做空力量并未大规模介入",
        "港股通纳入后流动性改善",
    ],
)
def test_capital_outflow_positive_or_low_short_context_no_signal(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert not any(s["name"] == "资金流出" for s in signals)


@pytest.mark.parametrize(
    "text",
    [
        "没有40亿营收不可能盈利",
        "短期难以盈利",
        "盈利困难",
    ],
)
def test_profitability_pressure_true_positives(text):
    v = _make_verification("c1", "verified", 75)
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[v],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "盈利压力" for s in signals)


def test_dedup_prefers_verified():
    low1 = _candidate("c1", "毛利率承压")
    low2 = _candidate("c2", "毛利率下滑")
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low1, low2],
        verifications=[
            _make_verification("c1", "verified", 70),
            _make_verification("c2", "supported", 65),
        ],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    names = [s["name"] for s in signals]
    assert names.count("盈利压力") == 1
    winner = [s for s in signals if s["name"] == "盈利压力"][0]
    assert winner["status"] == "verified"
    assert winner["confidence"] == 70


def test_supported_half_score_status():
    low = _candidate("c1", "毛利率承压")
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[_make_verification("c1", "supported", 65)],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert any(s["name"] == "盈利压力" and s["status"] == "supported" for s in signals)


def test_unverified_observation_only():
    low = _candidate("c1", "毛利率承压")
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[_make_verification("c1", "unverified", 20)],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    sig = [s for s in signals if s["name"] == "盈利压力"][0]
    assert sig["status"] == "unverified"
    assert sig["confidence"] == 0


def test_max_signals_cap():
    phrases = [
        "毛利率承压",
        "价格战",
        "资金净流出",
        "技术路线不确定",
        "业绩不及预期",
        "毛利率下滑",
        "竞争加剧",
        "主力净流出",
        "认证受阻",
        "预期下调",
    ]
    claims = [_candidate(f"c{i}", phrases[i]) for i in range(10)]
    verifications = [_make_verification(f"c{i}", "verified", 70) for i in range(10)]
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=claims,
        verifications=verifications,
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan, max_signals=5)
    assert len(signals) == 5


def test_evidence_text_sanitization():
    text = "毛利率承压 https://example.com/path [1] /tmp/file.md rawid123"
    low = _candidate("c1", text)
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[_make_verification("c1", "verified", 75)],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    sig = signals[0]
    assert "http" not in sig["evidence_text"]
    assert "[1]" not in sig["evidence_text"]
    assert "/tmp/file.md" not in sig["evidence_text"]
    assert "rawid123" not in sig["evidence_text"]


def test_unknown_claim_no_signal():
    low = _candidate("c1", "公司发布新产品，市场前景广阔")
    plan = ClaimVerificationPlan(
        stock="黑芝麻智能",
        high_credit_claims=[],
        low_credit_claims=[low],
        verifications=[_make_verification("c1", "verified", 75)],
        skipped_files=[],
    )
    signals = derive_structured_risk_signals_from_plan(plan)
    assert signals == []
