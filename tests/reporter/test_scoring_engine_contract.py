import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from reporter.scoring_engine import composite_score_section, compute_pillar_scores


def test_technical_score_prefers_trend_health():
    pillar = compute_pillar_scores(
        stock_raw={
            "technical": {
                "indicators": {
                    "rsi_14": 55.0,
                    "macd": 1.2,
                    "ma_20": 10.0,
                    "close": 12.0,
                    "_resonance": {
                        "trend_health": {"score": 42},
                        "trend_state": {
                            "primary_state": "震荡转弱",
                            "stage": "临界破坏观察期",
                        },
                    },
                },
            },
        },
        posts=[],
        quote={"price": 12.0, "pe_ttm": 20.0},
        consensus=None,
        industry_fwd_pe=None,
    )

    assert pillar["technical"] == 4.2
    assert pillar["technical_score_source"] == "trend_health"


def test_technical_score_caps_broken_downtrend():
    pillar = compute_pillar_scores(
        stock_raw={
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_health": {"score": 68},
                        "trend_state": {
                            "primary_state": "下降趋势",
                            "stage": "破坏期",
                        },
                    },
                },
            },
        },
        posts=[],
        quote={"price": 12.0, "pe_ttm": 20.0},
        consensus=None,
        industry_fwd_pe=None,
    )

    assert pillar["technical"] == 4.0
    assert pillar["technical_score_source"] == "trend_health"


def test_technical_score_falls_back_to_legacy_indicators():
    pillar = compute_pillar_scores(
        stock_raw={
            "technical": {
                "indicators": {
                    "rsi_14": 55.0,
                    "macd": 1.2,
                    "ma_20": 10.0,
                    "close": 12.0,
                },
            },
        },
        posts=[],
        quote={"price": 12.0, "pe_ttm": 20.0},
        consensus=None,
        industry_fwd_pe=None,
    )

    assert pillar["technical"] == 8.5
    assert pillar["technical_score_source"] == "legacy_indicators"


def test_composite_score_section_explains_trend_health_source():
    pillar = {
        "valuation": 5.0,
        "technical": 4.2,
        "sentiment": 5.0,
        "fundamental": 5.0,
        "fundflow": 5.0,
        "fwd_pe": None,
        "peg": None,
        "eps_growth": None,
        "industry_fwd_pe": None,
        "price": 12.0,
        "bullish_pct": 0,
        "bearish_pct": 0,
        "has_fund": False,
        "technical_score_source": "trend_health",
        "indicators": {
            "rsi_14": 55.0,
            "macd": 1.2,
            "_resonance": {
                "trend_health": {"score": 42, "grade": "C"},
                "trend_state": {"stage": "临界破坏观察期"},
            },
        },
    }

    md = composite_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw={},
        quote={"price": 12.0, "pe_ttm": 20.0},
        consensus=None,
        industry_fwd_pe=None,
        pillar=pillar,
    )

    assert "趋势健康度 42/100" in md
    assert "阶段 临界破坏观察期" in md
