from types import SimpleNamespace

from scripts.utils.reporter.executive_summary_view import build_executive_summary_view


def _decision(position_note: str = "趋势破坏期，建议 0-5%") -> SimpleNamespace:
    return SimpleNamespace(
        total_score=5.3,
        total_score_display="5.3",
        ev=SimpleNamespace(ev_pct=39.48, ev_display="+39.48%", targets={"base": 100.0}),
        display_recommendation="风险控制优先",
        recommendation_sentence="**风险控制优先** — 技术趋势已失效。",
        entry_constraint=SimpleNamespace(
            state="severe_technical",
            display_note="技术趋势已失效。",
            position_cap_note=position_note,
        ),
        risk=SimpleNamespace(level="中等风险", position_advice="防守仓位 0-5%"),
    )


def _context(position_note: str = "趋势破坏期，建议 0-5%") -> dict:
    return {
        "stock_name": "中际旭创",
        "date_str": "20260719",
        "recommendation_decision": _decision(position_note),
        "pillar": {
            "fundamental": 10.0,
            "fwd_pe": 37.8,
            "eps_growth": 65.5,
        },
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "破坏期"},
                        "trend_health": {"grade": "趋势失效", "score": 26},
                    }
                }
            }
        },
    }


def test_builds_complete_decision_chain_from_structured_owners():
    view = build_executive_summary_view(_context())

    assert view.total_score == "5.3 / 10"
    assert view.ev == "+39.48%"
    assert view.risk_level == "中等风险"
    assert view.position_cap == "0-5%"
    assert view.fundamental.title == "结构化基本面信号较强"
    assert view.fundamental.detail == "基本面评分 10/10"
    assert view.valuation.detail == "Forward PE 37.8x｜预期 EPS 增速 +65.5%"
    assert view.technical.title == "趋势失效 / 破坏期"
    assert view.technical.detail == "趋势健康度 26/100｜风险中等｜仓位 0-5%"
    assert view.action == "风险控制优先"
    assert view.image_ready is True


def test_position_cap_is_not_recomputed_from_entry_state():
    ctx = _context(position_note="")
    ctx["recommendation_decision"].risk.position_advice = ""

    view = build_executive_summary_view(ctx)

    assert view.position_cap == "证据不足"


def test_requires_two_substantive_nodes_for_image():
    ctx = {
        "stock_name": "测试股",
        "date_str": "20260719",
        "pillar": {"fundamental": 6.0},
    }

    view = build_executive_summary_view(ctx)

    assert view.fundamental.substantive is True
    assert view.valuation.substantive is False
    assert view.technical.substantive is False
    assert view.image_ready is False


def test_missing_optional_values_use_evidence_insufficient_label():
    view = build_executive_summary_view({"stock_name": "测试股", "date_str": "20260719"})

    assert view.total_score == "证据不足"
    assert view.ev == "证据不足"
    assert view.risk_level == "证据不足"
    assert view.position_cap == "证据不足"
    assert view.recommendation == "证据不足"
