import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_resonance import evaluate_market_resonance


def test_evaluate_market_resonance_placeholder():
    result = evaluate_market_resonance(
        stock_trend_state={"primary_state": "上升趋势"},
    )
    assert result["sector_trend"] == "未接入"
    assert result["market_trend"] == "未接入"
    assert "暂未接入" in result["impact"]
    assert result["resonance_signals"] == []


def test_evaluate_market_resonance_with_data():
    result = evaluate_market_resonance(
        stock_trend_state={"primary_state": "上升趋势"},
        sector_trend="上涨",
        market_trend="上涨",
    )
    assert "共振上涨" in result["resonance_signals"][0]
    assert "增强" in result["impact"]


def test_evaluate_market_resonance_independent():
    result = evaluate_market_resonance(
        stock_trend_state={"primary_state": "上升趋势"},
        sector_trend="震荡",
        market_trend="上涨",
    )
    assert "独立行情" in result["resonance_signals"][0]
