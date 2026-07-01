"""Tests for central RecommendationDecision model.

These tests drive the unification of score, EV display, recommendation label,
entry constraint, and risk position advice.
"""

import pytest
from pathlib import Path

from scripts.utils.reporter.recommendation_decision import (
    DisplayOnlyExternalRiskSignal,
    EntryConstraint,
    EvDecision,
    RecommendationDecision,
    RiskAssessment,
    build_recommendation_decision,
)


# ---------------------------------------------------------------------------
# EV display
# ---------------------------------------------------------------------------


def _pillar(**overrides):
    defaults = {
        "valuation": 7.0,
        "technical": 6.5,
        "sentiment": 5.0,
        "fundamental": 8.0,
        "fundflow": 4.0,
        "price": 100.0,
        "bullish_pct": 50.0,
        "bearish_pct": 20.0,
        "has_fund": True,
        "indicators": {},
        "fwd_pe": 20.0,
    }
    defaults.update(overrides)
    return defaults


def test_missing_ev_renders_na_without_percent():
    decision = build_recommendation_decision(
        stock_name="黑芝麻智能",
        posts=[],
        stock_raw={},
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        pillar=None,
    )
    assert isinstance(decision, RecommendationDecision)
    assert decision.ev.ev_display == "N/A"
    assert "N/A%" not in decision.ev.ev_display
    assert decision.total_score_display == "数据不足"


def test_normal_ev_renders_positive_percent():
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.ev.ev_pct is not None
    assert decision.ev.ev_display.startswith("+")
    assert "%" in decision.ev.ev_display
    assert "N/A%" not in decision.render_header()
    assert "N/A%" not in decision.ev.ev_display


def test_render_header_has_score_ev_and_label():
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    header = decision.render_header()
    assert f"{decision.total_score}/10" in header
    assert decision.ev.ev_display in header
    assert decision.display_recommendation in header


# ---------------------------------------------------------------------------
# Entry constraints
# ---------------------------------------------------------------------------


def test_macd_blocked_entry_any_reason_triggers_wait():
    stock_raw = {
        "technical": {
            "price_target": {
                "error": "关注/不操作",
                "reason": "MACD死叉扩张，不满足触发条件",
            },
            "indicators": {},
        }
    }
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw=stock_raw,
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.entry_constraint.state == "wait_for_entry"
    assert decision.display_recommendation == "看多但等待入场"
    assert decision.recommendation_sentence != ""


def test_overheated_bias_downgrades_label():
    stock_raw = {
        "technical": {
            "indicators": {
                "bias_5_extreme_high": True,
                "bias_10_extreme_high": False,
            },
        }
    }
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw=stock_raw,
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.entry_constraint.state == "overheated"
    assert decision.display_recommendation == "看多但避免追高"


def test_severe_technical_downgrades_label():
    stock_raw = {
        "technical": {
            "indicators": {
                "_resonance": {
                    "trend_state": {
                        "stage": "破坏期",
                        "primary_state": "下降趋势",
                    },
                    "trend_health": {"score": 26, "grade": "趋势失效"},
                }
            },
        }
    }
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="黑芝麻智能",
        posts=[],
        stock_raw=stock_raw,
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.entry_constraint.state == "severe_technical"
    assert decision.display_recommendation == "风险控制优先"


def test_non_positive_label_not_upgraded():
    pillar = _pillar(valuation=2.0, technical=2.0, fundamental=2.0)
    consensus = {"eps_current": 5.0, "eps_next": 4.0}
    decision = build_recommendation_decision(
        stock_name="测试股",
        posts=[],
        stock_raw={
            "technical": {
                "price_target": {"error": "关注/不操作", "reason": "盈亏比不足"},
                "indicators": {},
            }
        },
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.raw_recommendation not in ("强烈看多", "看多")
    assert "但等待入场" not in decision.display_recommendation


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------


def test_risk_assessment_position_advice_capped_by_entry_constraint():
    stock_raw = {
        "technical": {
            "price_target": {"error": "关注/不操作", "reason": "MACD死叉扩张"},
            "indicators": {},
        }
    }
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw=stock_raw,
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.entry_constraint.state == "wait_for_entry"
    assert decision.risk.position_advice != "积极配置，最大仓位 20%"
    assert "等待" in decision.risk.position_advice or "5-10%" in decision.risk.position_advice


def test_display_only_risk_metadata_adds_note_without_changing_score():
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    display_only_risks = [
        DisplayOnlyExternalRiskSignal(
            name="上游价格风险",
            source_kind="雪球精选观察",
            evidence_text="硅料涨价",
        )
    ]
    decision_with = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
        display_only_external_risks=display_only_risks,
    )
    decision_without = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision_with.risk.display_only_notes
    assert "display-only" in decision_with.risk.display_only_notes[0] or "不计入" in decision_with.risk.display_only_notes[0]
    assert decision_with.risk.score == decision_without.risk.score


def test_no_display_only_risk_without_metadata():
    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
        synthesis_text="雪球观察提到硅料涨价风险",
    )
    assert decision.risk.display_only_notes == []


# ---------------------------------------------------------------------------
# Integration helpers
# ---------------------------------------------------------------------------


def test_decision_objects_are_frozen_and_hashable_by_default():
    ev = EvDecision(ev_pct=12.34, ev_display="+12.34%", raw_label="强烈看多", raw_code="STRONG_BUY")
    constraint = EntryConstraint(state="ok", label_suffix="", display_note="", position_cap_note="", source="none", raw_reason="")
    risk = RiskAssessment(score=2.0, level="低风险", position_advice="建议", factors=[], formal_notes=[], display_only_notes=[], special_risk_notes=[])
    decision = RecommendationDecision(
        stock_name="测试",
        total_score=6.0,
        total_score_display="6.0",
        ev=ev,
        raw_recommendation="强烈看多",
        display_recommendation="强烈看多",
        recommendation_sentence="推荐",
        entry_constraint=constraint,
        risk=risk,
    )
    assert decision.ev.ev_pct == 12.34
    assert decision.risk.level == "低风险"


# ---------------------------------------------------------------------------
# Renderer integration tests
# ---------------------------------------------------------------------------


def test_executive_summary_renderer_uses_decision_header():
    from scripts.utils.reporter.sections.executive_summary_renderer import ExecutiveSummaryRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {"valuation_debate": "", "fundamentals": ""},
        "recommendation_decision": decision,
    }
    result = renderer.render(ctx)
    assert decision.render_header() in result
    assert "EV: N/A%" not in result


def test_composite_score_renderer_uses_decision_header():
    from scripts.utils.reporter.sections.composite_score_renderer import CompositeScoreRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    renderer = CompositeScoreRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "posts": [],
        "stock_raw": {},
        "quote": {"price": 100.0},
        "consensus": consensus,
        "industry_fwd_pe": 20.0,
        "pillar": pillar,
        "recommendation_decision": decision,
    }
    result = renderer.render(ctx)
    assert decision.render_header() in result
    assert decision.recommendation_sentence in result


def test_summary_and_section1_headers_match():
    from scripts.utils.reporter.sections.composite_score_renderer import CompositeScoreRenderer
    from scripts.utils.reporter.sections.executive_summary_renderer import ExecutiveSummaryRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    summary = ExecutiveSummaryRenderer().render({
        "stock_name": "中际旭创",
        "synthesis": {"valuation_debate": "", "fundamentals": ""},
        "recommendation_decision": decision,
    })
    section1 = CompositeScoreRenderer().render({
        "stock_name": "中际旭创",
        "posts": [],
        "stock_raw": {},
        "quote": {"price": 100.0},
        "consensus": consensus,
        "industry_fwd_pe": 20.0,
        "pillar": pillar,
        "recommendation_decision": decision,
    })
    assert decision.render_header() in summary
    assert decision.render_header() in section1


def test_summary_blocked_entry_renders_wait_label():
    from scripts.utils.reporter.sections.executive_summary_renderer import ExecutiveSummaryRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={
            "technical": {
                "price_target": {"error": "关注/不操作", "reason": "MACD死叉扩张"},
                "indicators": {},
            }
        },
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.display_recommendation == "看多但等待入场"
    summary = ExecutiveSummaryRenderer().render({
        "stock_name": "中际旭创",
        "synthesis": {"valuation_debate": "", "fundamentals": ""},
        "recommendation_decision": decision,
    })
    assert "看多但等待入场" in summary


def test_risk_renderer_uses_decision_and_caps_position():
    from scripts.utils.reporter.sections.risk_renderer import RiskRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={
            "technical": {
                "price_target": {"error": "关注/不操作", "reason": "MACD死叉扩张"},
                "indicators": {},
            }
        },
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    assert decision.entry_constraint.state == "wait_for_entry"
    renderer = RiskRenderer()
    result = renderer.render({
        "stock_name": "中际旭创",
        "all_posts": [],
        "recommendation_decision": decision,
    })
    assert "积极配置，最大仓位 20%" not in result


def test_display_only_risk_flag_adds_note_without_changing_score():
    from scripts.utils.reporter.sections.risk_renderer import RiskRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision_without = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
    )
    decision_with = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
        display_only_external_risks=[
            DisplayOnlyExternalRiskSignal(name="上游价格风险", source_kind="雪球精选观察", evidence_text="硅料涨价")
        ],
    )
    assert decision_with.risk.score == decision_without.risk.score
    assert decision_with.risk.display_only_notes

    result = RiskRenderer().render({
        "stock_name": "中际旭创",
        "all_posts": [],
        "recommendation_decision": decision_with,
    })
    assert "不计入综合风险评分" in result


def test_risk_renderer_does_not_infer_display_only_from_prose():
    from scripts.utils.reporter.sections.risk_renderer import RiskRenderer

    pillar = _pillar()
    consensus = {"eps_current": 5.0, "eps_next": 6.0}
    decision = build_recommendation_decision(
        stock_name="中际旭创",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=consensus,
        industry_fwd_pe=20.0,
        pillar=pillar,
        synthesis_text="雪球观察提到毛利率承压和价格战风险",
    )
    result = RiskRenderer().render({
        "stock_name": "中际旭创",
        "all_posts": [],
        "recommendation_decision": decision,
    })
    assert "不计入综合风险评分" not in result


def test_executive_summary_renderer_no_longer_uses_signal_key():
    file_path = Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter" / "sections" / "executive_summary_renderer.py"
    source = file_path.read_text(encoding="utf-8")
    assert "ev.get(\"signal\")" not in source
    assert "recommendation_decision" in source


def test_executive_summary_legacy_fallback_does_not_render_na_percent():
    from scripts.utils.reporter.sections.executive_summary_renderer import ExecutiveSummaryRenderer

    result = ExecutiveSummaryRenderer().render(
        {
            "stock_name": "黑芝麻智能",
            "synthesis": {"valuation_debate": "", "fundamentals": ""},
            "pillar": _pillar(),
            "consensus": None,
        }
    )
    assert "EV: N/A（N/A）" in result
    assert "EV: N/A%" not in result


def test_composite_score_legacy_fallback_does_not_render_na_percent():
    from scripts.utils.reporter.scoring_engine import composite_score_section

    result = composite_score_section(
        stock_name="黑芝麻智能",
        posts=[],
        stock_raw={},
        quote={"price": 100.0},
        consensus=None,
        industry_fwd_pe=20.0,
        pillar=_pillar(),
    )
    assert "EV: N/A（N/A）" in result
    assert "EV: N/A%" not in result
