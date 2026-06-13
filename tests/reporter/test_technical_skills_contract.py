import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from report_skills.technical_skills import technical_fetching_skill


def test_reuses_cached_technical_and_preserves_daily_data():
    technical = {
        "daily_data": {
            "close": [10.0, 10.5, 11.0],
            "volume": [100, 120, 140],
        },
        "indicators": {
            "close": 11.0,
            "volume": 140,
            "_resonance": {"trend": "震荡", "composite_score": 6.0},
        },
        "price_target": {"direction": "neutral"},
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "300001"},
        "stock_raw": {"technical": technical},
    })

    result = technical_fetching_skill(ctx)

    assert result.get("technical") == technical
    assert result.get("daily_data") == technical["daily_data"]
    assert result.get("indicators") == technical["indicators"]
    assert result.get("price_target") == technical["price_target"]
    assert result.get("stock_raw")["technical"] == technical


def test_collected_technical_is_written_back_to_stock_raw():
    collected = {
        "daily_data": {"close": [1.0, 1.1], "volume": [100, 110]},
        "indicators": {"close": 1.1, "rsi_14": 52.0},
        "price_target": {"direction": "bullish"},
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "300001"},
        "stock_raw": {},
    })

    with patch("report_skills.technical_skills.TechnicalCollector") as mock_collector:
        mock_collector.return_value.collect.return_value = collected
        result = technical_fetching_skill(ctx)

    mock_collector.return_value.collect.assert_called_once_with("300001", market=0, days=120)
    assert result.get("technical") == collected
    assert result.get("stock_raw")["technical"] == collected
    assert result.get("daily_data") == collected["daily_data"]


def test_hk_code_uses_hk_market_contract():
    ctx = SkillContext(input={
        "stock_name": "港股测试",
        "stock_codes": {"港股测试": "02533"},
        "stock_raw": {},
    })

    with patch("report_skills.technical_skills.TechnicalCollector") as mock_collector:
        mock_collector.return_value.collect.return_value = {}
        result = technical_fetching_skill(ctx)

    mock_collector.return_value.collect.assert_called_once_with("02533", market="hk", days=120)
    assert result.get("technical") is None
    assert result.get("technical_unavailable_reason") == "technical_data_unavailable"
    assert result.get("stock_raw")["technical_unavailable_reason"] == "technical_data_unavailable"


def test_missing_code_sets_unavailable_reason():
    ctx = SkillContext(input={
        "stock_name": "无代码",
        "stock_codes": {},
        "stock_raw": {},
    })

    result = technical_fetching_skill(ctx)

    assert result.get("technical") is None
    assert result.get("daily_data") == {}
    assert result.get("technical_unavailable_reason") == "missing_stock_code"


def test_hk_code_prefers_local_wind_excel_before_network_collector():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "stock_codes": {"黑芝麻智能": "02533"},
        "stock_raw": {},
    })

    with patch("report_skills.technical_skills.TechnicalCollector") as mock_collector:
        mock_collector.return_value.compute_indicators.return_value = {
            "close": 14.02,
            "volume": 5959595,
            "_resonance": {
                "trend": "多头",
                "composite_score": 7,
                "trend_state": {"primary_state": "上升趋势", "stage": "推进期"},
                "trend_health": {"score": 72, "grade": "B+"},
            },
        }
        result = technical_fetching_skill(ctx)

    mock_collector.return_value.collect.assert_not_called()
    mock_collector.return_value.compute_indicators.assert_called_once()
    assert result.get("technical")["data_source"] == "wind_excel"
    assert result.get("technical")["market"] == "hk"
    assert result.get("daily_data")["close"][-1] == 14.02
    assert "恒生科技指数" in result.get("technical")["benchmark_data"]
    assert result.get("stock_raw")["technical"]["data_source"] == "wind_excel"
