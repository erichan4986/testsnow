import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

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


def test_collected_technical_fund_flow_is_bridged_to_stock_raw_fundflow():
    collected = {
        "daily_data": {"close": [1.0, 1.1], "volume": [100, 110]},
        "indicators": {"close": 1.1, "rsi_14": 52.0},
        "fund_flow": [
            {
                "date": "2026-07-02",
                "close": "65.40",
                "change_pct": "2.5",
                "main_in": "1200",
                "super_net_in": "500",
                "large_net_in": "300",
                "medium_net_in": "-100",
                "small_net_in": "-900",
            }
        ],
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "300001"},
        "stock_raw": {},
    })

    with patch("report_skills.technical_skills.TechnicalCollector") as mock_collector:
        mock_collector.return_value.collect.return_value = collected
        result = technical_fetching_skill(ctx)

    fundflow = result.get("stock_raw")["fundflow"]
    assert len(fundflow) == 1
    assert fundflow[0]["date"] == "2026-07-02"
    assert fundflow[0]["main_inflow"] == 1200.0
    assert fundflow[0]["main_in"] == 1200.0
    assert fundflow[0]["super_net_in"] == 500.0
    assert fundflow[0]["large_net_in"] == 300.0
    assert fundflow[0]["medium_net_in"] == -100.0
    assert fundflow[0]["small_net_in"] == -900.0
    assert fundflow[0]["change_pct"] == 2.5
    assert fundflow[0]["source"] == "baidu_pae"


def test_collected_technical_fund_flow_does_not_override_existing_fundflow():
    existing = [{"date": "2026-07-01", "main_inflow": 88, "source": "manual"}]
    collected = {
        "daily_data": {"close": [1.0, 1.1], "volume": [100, 110]},
        "indicators": {"close": 1.1, "rsi_14": 52.0},
        "fund_flow": [{"date": "2026-07-02", "main_in": "1200"}],
    }
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "300001"},
        "stock_raw": {"fundflow": existing},
    })

    with patch("report_skills.technical_skills.TechnicalCollector") as mock_collector:
        mock_collector.return_value.collect.return_value = collected
        result = technical_fetching_skill(ctx)

    assert result.get("stock_raw")["fundflow"] == existing


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
    fresh_dates = pd.to_datetime([pd.Timestamp.today().date()])
    fresh_daily = pd.DataFrame({
        "date": fresh_dates,
        "open": [14.0],
        "high": [14.5],
        "low": [13.8],
        "close": [14.02],
        "volume": [5959595.0],
        "amount": [84007503.0],
    })
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "stock_codes": {"黑芝麻智能": "02533"},
        "stock_raw": {},
    })

    with (
        patch(
            "report_skills.technical_skills.load_wind_package",
            return_value={
                "daily": fresh_daily,
                "benchmarks": {"恒生科技指数": fresh_daily},
            },
        ),
        patch("report_skills.technical_skills.TechnicalCollector") as mock_collector,
    ):
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


def test_hk_code_skips_stale_local_wind_excel_before_network_collector():
    stale_daily = pd.DataFrame({
        "date": pd.to_datetime(["2000-01-01", "2000-01-02"]),
        "open": [10.0, 10.1],
        "high": [10.2, 10.3],
        "low": [9.8, 9.9],
        "close": [10.0, 10.1],
        "volume": [1000.0, 1200.0],
        "amount": [10000.0, 12000.0],
    })
    collected = {
        "daily_data": {"close": [8.8, 8.9], "volume": [100, 110]},
        "indicators": {"close": 8.9, "ma_20": 9.5},
        "price_target": {"direction": "neutral"},
        "data_source": "network_hk",
    }
    ctx = SkillContext(input={
        "stock_name": "港股测试",
        "stock_codes": {"港股测试": "02533"},
        "stock_raw": {},
    })

    with (
        patch(
            "report_skills.technical_skills.load_wind_package",
            return_value={"daily": stale_daily, "benchmarks": {}},
        ),
        patch("report_skills.technical_skills.TechnicalCollector") as mock_collector,
    ):
        mock_collector.return_value.collect.return_value = collected
        result = technical_fetching_skill(ctx)

    mock_collector.return_value.collect.assert_called_once_with("02533", market="hk", days=120)
    mock_collector.return_value.compute_indicators.assert_not_called()
    assert result.get("technical") == collected
    assert result.get("technical_local_data_stale_reason").startswith("wind_excel_stale")
