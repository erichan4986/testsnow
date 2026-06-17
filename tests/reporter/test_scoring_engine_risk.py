"""Tests for risk_score_section structured risk signal behavior."""

import re

import pytest
from scripts.utils.report_quality import STRONG_RECOMMENDATION_PATTERNS
from scripts.utils.reporter.scoring_engine import _entry_quality_guardrail, risk_score_section


MINIMAL_STOCK_RAW = {"technical": {"indicators": {}}}


def _base_call(**kwargs):
    return risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=MINIMAL_STOCK_RAW,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        **kwargs,
    )


def test_quantitative_risks_still_score():
    """Technical breakdown and liquidity risks continue to score."""
    stock_raw = {
        "technical": {
            "indicators": {
                "close": 10.0,
                "ma_20": 15.0,
                "avg_amount_yi": 2.0,
            }
        }
    }
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )
    assert "技术破位" in result
    assert "流动性差" in result
    assert "2.0" in result


def test_keyword_match_does_not_score_by_default():
    result = _base_call(synthesis_text="价格战加剧，降价压力大")
    assert "竞争格局恶化" in result
    assert "LLM文本风险观察（不计分）" in result
    # No '+1.5' in main risk table for keyword-only signal
    assert "| 竞争格局恶化 | LLM 合成文本识别 | +1.5 |" not in result
    # Total risk should be 0 (no quantitative triggers)
    assert "风险等级: 0.0/10" in result


def test_keyword_match_renders_observation_table():
    result = _base_call(synthesis_text="价格战")
    assert "### LLM文本风险观察（不计分）" in result
    assert "自由文本命中，仅提示人工复核" in result
    assert "价格战" in result


def test_score_llm_keyword_risks_true_restores_scoring():
    result = _base_call(synthesis_text="价格战", score_llm_keyword_risks=True)
    assert "竞争格局恶化" in result
    assert "LLM关键词命中: 价格战" in result
    assert "+1.5" in result
    assert "风险等级: 1.5/10" in result


def test_verified_structured_signal_adds_full_score():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "竞争格局恶化" in result
    assert "verified" in result
    assert "+1.5" in result
    assert "风险等级: 1.5/10" in result
    assert "### 结构化风险观察\n" in result
    assert "### 结构化风险观察（不计分）" not in result


def test_supported_structured_signal_adds_half_score():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "supported",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "竞争格局恶化" in result
    assert "supported" in result
    assert "风险等级: 1.0/10" in result


def test_unverified_structured_signal_does_not_score_but_renders_observation():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "unverified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "竞争格局恶化" in result
    assert "风险等级: 0.0/10" in result
    assert "结构化风险观察（不计分）" in result


def test_low_confidence_structured_signal_does_not_score_but_renders_observation():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 40,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "竞争格局恶化" in result
    assert "风险等级: 0.0/10" in result
    assert "结构化风险观察（不计分）" in result


def test_unknown_signal_name_does_not_score_but_renders_observation():
    signals = [
        {
            "name": "未知风险",
            "score": 2.0,
            "confidence": 80,
            "source": "外部来源",
            "evidence_text": "风险描述",
            "matched_terms": ["风险"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "未知风险" in result
    assert "风险等级: 0.0/10" in result
    assert "结构化风险观察（不计分）" in result


def test_duplicate_structured_signals_score_once_and_render_one_row():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.0,
            "confidence": 60,
            "source": "claim_verification",
            "evidence_text": "A",
            "matched_terms": ["A"],
            "status": "verified",
        },
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "B",
            "matched_terms": ["B"],
            "status": "verified",
        },
    ]
    result = _base_call(structured_risk_signals=signals)
    # Should score the highest valid signal
    assert "风险等级: 1.5/10" in result
    # Observation table should only contain one row for the signal name
    observation_section = result.split("结构化风险观察")[1] if "结构化风险观察" in result else ""
    assert observation_section.count("竞争格局恶化") == 1


def test_evidence_text_and_matched_terms_sanitized():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大[^1]",
            "matched_terms": ["毛利率差距[1]"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "[^1]" not in result
    assert "[1]" not in result
    assert "毛利率差距大" in result


def test_empty_structured_signals_with_keyword_match_keeps_score_unchanged():
    result = _base_call(structured_risk_signals=[], synthesis_text="价格战")
    assert "风险等级: 0.0/10" in result
    assert "LLM文本风险观察（不计分）" in result


def test_unknown_source_renders_as_external():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "外部来源" in result


def test_unrecognized_source_renders_as_external():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "random_blog",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "外部来源" in result
    assert "random_blog" not in result


def test_signal_score_capped_at_max():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 5.0,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "风险等级: 1.5/10" in result


def test_boolean_structured_signal_numbers_do_not_score():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": True,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": ["毛利率差距"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "风险等级: 0.0/10" in result
    assert "结构化风险观察（不计分）" in result


def test_string_matched_terms_render_as_single_term():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "毛利率差距大",
            "matched_terms": "毛利率差距[^1]",
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "毛利率差距大 / 毛利率差距" in result
    assert "毛, 利, 率" not in result
    assert "[^1]" not in result


def test_claim_verification_source_label_rendered():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "价格战压力",
            "matched_terms": ["价格战"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals)
    assert "claim_verification" in result or "Agent-Reach验证" in result or "外部来源" in result


def test_structured_signal_and_keyword_observation_do_not_double_count():
    signals = [
        {
            "name": "竞争格局恶化",
            "score": 1.5,
            "confidence": 80,
            "source": "claim_verification",
            "evidence_text": "价格战压力",
            "matched_terms": ["价格战"],
            "status": "verified",
        }
    ]
    result = _base_call(structured_risk_signals=signals, synthesis_text="价格战加剧")
    # Structured signal should score once, keyword observation should remain observation-only.
    assert "风险等级: 1.5/10" in result
    assert result.count("竞争格局恶化") >= 2  # scored row + observation row
    # The LLM keyword observation should not add a second +1.5
    assert result.count("+1.5") == 1


# ---------------------------------------------------------------------------
# Position advice guardrail tests
# ---------------------------------------------------------------------------


def _make_stock_raw(close=10.0, ma20=15.0, avg_amount=2.0, resonance=None):
    indicators = {
        "close": close,
        "ma_20": ma20,
        "avg_amount_yi": avg_amount,
    }
    if resonance is not None:
        indicators["_resonance"] = resonance
    return {"technical": {"indicators": indicators}}


def _make_entry_quality_stock_raw(
    price_target=None,
    bias_5_extreme_high=False,
    bias_10_extreme_high=False,
    resonance=None,
):
    return {
        "technical": {
            "price_target": price_target,
            "indicators": {
                "close": 10.0,
                "ma_20": 9.0,
                "avg_amount_yi": 8.0,
                "bias_5_extreme_high": bias_5_extreme_high,
                "bias_10_extreme_high": bias_10_extreme_high,
                "_resonance": resonance or {},
            },
        }
    }


def _advice_from(result: str) -> str:
    for line in result.splitlines():
        if line.startswith("> **仓位建议**: "):
            return line.replace("> **仓位建议**: ", "").strip()
    return ""


def _constraint_from(result: str) -> str:
    for line in result.splitlines():
        if line.startswith("> **仓位约束**: "):
            return line.replace("> **仓位约束**: ", "").strip()
    return ""


def _matches_strong_recommendation(text: str) -> list:
    normalized = text.replace(" ", "").replace("　", "")
    return [p for p in STRONG_RECOMMENDATION_PATTERNS if re.search(p, normalized)]


# ---------------------------------------------------------------------------
# Entry quality guardrail tests
# ---------------------------------------------------------------------------


def test_entry_quality_guardrail_detects_price_target_blocked_entry():
    guardrail = _entry_quality_guardrail(
        _make_entry_quality_stock_raw(
            price_target={"error": "关注/不操作", "reason": "形态存在但盈亏比不足（1.06:1）"}
        )
    )

    assert guardrail["level"] == "entry_blocked"


def test_entry_quality_guardrail_detects_overheated_bias_only():
    guardrail = _entry_quality_guardrail(_make_entry_quality_stock_raw(bias_5_extreme_high=True))

    assert guardrail["level"] == "overheated_entry"


def test_entry_quality_guardrail_missing_fields_returns_none():
    assert _entry_quality_guardrail({}) is None
    assert _entry_quality_guardrail({"technical": {"indicators": {}}}) is None


def test_entry_blocked_caps_aggressive_position_without_changing_risk_score():
    stock_raw = _make_entry_quality_stock_raw(
        price_target={"error": "关注/不操作", "reason": "形态存在但盈亏比不足（1.06:1）"}
    )

    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )

    assert "风险等级: 0.0/10" in result
    assert _advice_from(result) == "当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%"
    assert "技术面提示关注/不操作或追高风险" in result
    assert not _matches_strong_recommendation(result)


def test_overheated_entry_caps_aggressive_position_without_forcing_sell_advice():
    stock_raw = _make_entry_quality_stock_raw(bias_10_extreme_high=True)

    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )

    assert "风险等级: 0.0/10" in result
    assert _advice_from(result) == "BIAS严重正偏离，追高风险较大，仓位 5-10%"
    assert "建议减仓或不买入" not in _advice_from(result)
    assert not _matches_strong_recommendation(result)


def test_entry_quality_guardrail_does_not_override_already_conservative_advice():
    stock_raw = _make_entry_quality_stock_raw(
        price_target={"error": "关注/不操作", "reason": "形态存在但盈亏比不足（1.06:1）"}
    )
    stock_raw["technical"]["indicators"].update({
        "monthly_return_pct": 40.0,
        "close": 8.0,
        "ma_20": 10.0,
        "avg_amount_yi": 2.0,
    })

    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote={"price": 100.0},
        consensus={"eps_current": 1.0, "eps_next": 1.1},
        industry_fwd_pe=None,
        synthesis_text="价格战",
        score_llm_keyword_risks=True,
    )

    assert "风险等级: 7.5/10" in result
    assert _advice_from(result) == "建议减仓或不买入"


def test_severe_technical_guardrail_takes_precedence_over_entry_quality():
    stock_raw = _make_entry_quality_stock_raw(
        price_target={"error": "关注/不操作", "reason": "形态存在但盈亏比不足（1.06:1）"},
        resonance={
            "trend_state": {"stage": "破坏期", "primary_state": "下降趋势"},
            "trend_health": {"score": 26, "grade": "趋势失效"},
        },
    )

    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )

    assert _advice_from(result) == "趋势破坏期，以观望或防守仓位为主，建议 0-5%"


def test_severe_guardrail_overrides_aggressive_advice():
    """Severe weak trend overrides aggressive position advice but keeps risk score."""
    stock_raw = _make_stock_raw(
        close=10.0,
        ma20=15.0,
        avg_amount=2.0,
        resonance={
            "trend_state": {"stage": "破坏期", "primary_state": "下降趋势"},
            "trend_health": {"score": 26, "grade": "趋势失效"},
        },
    )
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )
    assert "风险等级: 2.0/10" in result
    assert _advice_from(result) == "趋势破坏期，以观望或防守仓位为主，建议 0-5%"
    assert "技术状态为 下降趋势 / 破坏期" in _constraint_from(result)


def test_severe_guardrail_avoids_strong_recommendation_patterns():
    stock_raw = _make_stock_raw(
        close=10.0,
        ma20=15.0,
        avg_amount=2.0,
        resonance={
            "trend_state": {"stage": "破坏期", "primary_state": "下降趋势"},
            "trend_health": {"score": 26, "grade": "趋势失效"},
        },
    )
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )
    matches = _matches_strong_recommendation(result)
    assert not matches, f"Matched strong recommendation patterns: {matches}"


@pytest.mark.parametrize("score", ["26", None])
def test_severe_guardrail_triggers_with_malformed_score_but_severe_strings(score):
    stock_raw = _make_stock_raw(
        close=10.0,
        ma20=15.0,
        avg_amount=2.0,
        resonance={
            "trend_state": {"stage": "破坏期"},
            "trend_health": {"score": score, "grade": "趋势失效"},
        },
    )
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )
    assert _advice_from(result) == "趋势破坏期，以观望或防守仓位为主，建议 0-5%"


def test_missing_resonance_preserves_risk_only_advice():
    stock_raw = _make_stock_raw(close=20.0, ma20=15.0, avg_amount=10.0, resonance=None)
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )
    assert "风险等级: 0.0/10" in result
    assert _advice_from(result) == "积极配置，最大仓位 20%"


def test_high_risk_plus_severe_weak_trend_keeps_conservative_advice():
    stock_raw = _make_stock_raw(
        close=10.0,
        ma20=15.0,
        avg_amount=2.0,
        resonance={
            "trend_state": {"stage": "破坏期", "primary_state": "下降趋势"},
            "trend_health": {"score": 20, "grade": "趋势失效"},
        },
    )
    signals = [
        {"name": "业绩预期下调", "score": 1.5, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "竞争格局恶化", "score": 1.5, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "盈利压力", "score": 1.0, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "资金流出", "score": 1.0, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "技术路线风险", "score": 1.0, "confidence": 80, "source": "claim_verification", "status": "verified"},
    ]
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        structured_risk_signals=signals,
    )
    assert "风险等级: 8.0/10" in result
    assert _advice_from(result) == "建议减仓或不买入"


def test_moderate_guardrail_caps_aggressive_advice():
    stock_raw = _make_stock_raw(
        close=20.0,
        ma20=15.0,
        avg_amount=10.0,
        resonance={
            "trend_state": {"stage": "转弱期"},
            "trend_health": {"score": 35, "grade": "破坏风险高"},
        },
    )
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
    )
    assert "风险等级: 0.0/10" in result
    assert _advice_from(result) == "趋势转弱，控制仓位，建议 5-10%"
    assert "技术健康度偏弱" in _constraint_from(result)


def test_moderate_guardrail_preserves_conservative_advice():
    stock_raw = _make_stock_raw(
        close=10.0,
        ma20=15.0,
        avg_amount=2.0,
        resonance={
            "trend_state": {"stage": "转弱期"},
            "trend_health": {"score": 35, "grade": "破坏风险高"},
        },
    )
    signals = [
        {"name": "业绩预期下调", "score": 1.5, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "竞争格局恶化", "score": 1.5, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "盈利压力", "score": 1.0, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "资金流出", "score": 1.0, "confidence": 80, "source": "claim_verification", "status": "verified"},
        {"name": "技术路线风险", "score": 1.0, "confidence": 80, "source": "claim_verification", "status": "verified"},
    ]
    result = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw=stock_raw,
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        structured_risk_signals=signals,
    )
    assert "风险等级: 8.0/10" in result
    assert _advice_from(result) == "建议减仓或不买入"
