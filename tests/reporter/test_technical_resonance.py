import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_resonance import evaluate_market_resonance


def test_evaluate_market_resonance_placeholder():
    result = evaluate_market_resonance(
        stock_trend_state={"primary_state": "上升趋势", "stage": "主升期"},
    )
    assert result["state"] == "未知"
    assert result["confidence"] == "低"
    assert "market index data missing" in result["missing"]


def test_evaluate_market_resonance_with_data():
    result = evaluate_market_resonance(
        stock_trend_state={"primary_state": "上升趋势", "stage": "主升期"},
        market_trend_state={"primary_state": "上升趋势", "stage": "主升期"},
        sector_trend_state={"primary_state": "上升趋势", "stage": "主升期"},
    )
    assert result["state"] == "顺风共振"
    assert result["confidence"] == "高"
    assert "可信度上调" in result["impact"]


def test_evaluate_market_resonance_independent():
    result = evaluate_market_resonance(
        stock_trend_state={"primary_state": "上升趋势", "stage": "主升期"},
        market_trend_state={"primary_state": "下降趋势", "stage": "破坏期"},
        sector_trend_state={"primary_state": "下降趋势", "stage": "破坏期"},
    )
    assert result["state"] == "逆风独立"
