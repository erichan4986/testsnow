import os
import sys
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from data_collector import TechnicalCollector


def test_compute_indicators_is_compatibility_wrapper_with_market():
    collector = TechnicalCollector.__new__(TechnicalCollector)
    frame = pd.DataFrame({"close": [10.0, 10.5], "volume": [100, 110]})
    payload = {"indicators": {"close": 10.5}, "price_target": {"status": "observe"}}
    with patch.object(collector, "build_technical_payload", return_value=payload) as builder:
        result = collector.compute_indicators(frame, code="02533", market="hk")
    builder.assert_called_once()
    assert result == payload["indicators"]


def test_build_payload_passes_market_and_cache_dir_to_analyzer(monkeypatch, tmp_path):
    collector = TechnicalCollector.__new__(TechnicalCollector)
    daily = pd.DataFrame({"open": [10.0] * 30, "high": [11.0] * 30, "low": [9.0] * 30, "close": [10.5] * 30, "volume": [100.0] * 30})
    weekly = daily.iloc[::5].reset_index(drop=True)
    observed = {}

    def fake_analyze(df, df_weekly, code, market, cache_dir=None):
        observed.update({"code": code, "market": market, "cache_dir": cache_dir})
        return {"indicators": {"close": 10.5}, "resonance": {}, "price_target": {"status": "observe", "reason_code": "weekly_range", "direction": "neutral"}, "patterns": [], "levels": {}}

    monkeypatch.setattr(collector, "_run_technical_analyzer", fake_analyze)
    result = collector.build_technical_payload(
        daily, weekly, code="02533", market="hk", cache_dir=tmp_path,
    )
    assert observed == {"code": "02533", "market": "hk", "cache_dir": tmp_path}
    assert result["price_target"]["status"] == "observe"


def test_legacy_indicator_fallback_does_not_call_full_analyzer(monkeypatch):
    collector = TechnicalCollector.__new__(TechnicalCollector)
    daily = pd.DataFrame({"open": [10.0] * 30, "high": [11.0] * 30, "low": [9.0] * 30, "close": [10.5] * 30, "volume": [100.0] * 30})
    import reporter.technical_analyzer as technical_analyzer

    calls = []

    def unexpected_analyze(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("legacy fallback must not invoke the full analyzer")

    monkeypatch.setattr(technical_analyzer, "analyze", unexpected_analyze)
    collector._compute_indicators_legacy(daily, code="02533")
    assert calls == []


def test_collect_keeps_daily_payload_when_weekly_fetch_fails(monkeypatch):
    import data_collector as module

    collector = TechnicalCollector.__new__(TechnicalCollector)
    daily = pd.DataFrame({
        "open": [10.0] * 30, "high": [11.0] * 30, "low": [9.0] * 30,
        "close": [10.5] * 30, "volume": [100.0] * 30,
    })
    monkeypatch.setattr(collector, "fetch_kline", lambda *args, **kwargs: daily)
    monkeypatch.setattr(collector, "fetch_weekly_kline", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("weekly unavailable")))
    built = []

    def build(df_daily, df_weekly=None, **kwargs):
        built.append(df_weekly)
        return {"indicators": {"close": 10.5}, "price_target": {"status": "unavailable"}}

    monkeypatch.setattr(collector, "build_technical_payload", build)
    monkeypatch.setattr(module, "_baidu_fund_flow_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_baidu_concept_blocks", lambda *args, **kwargs: [])

    result = collector.collect("300308", market=0)

    assert built == [None]
    assert result["indicators"]["close"] == 10.5


def test_collect_routes_weekly_source_and_cache_dir(monkeypatch, tmp_path):
    import data_collector as module

    collector = TechnicalCollector.__new__(TechnicalCollector)
    daily = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01", "2026-07-02"]),
        "open": [10.0, 10.1], "high": [10.2, 10.3],
        "low": [9.8, 9.9], "close": [10.1, 10.2], "volume": [100, 110],
    })
    daily.attrs.update(data_source="akshare", adjustment="qfq")
    observed = {"weekly": {}, "build": {}}
    monkeypatch.setattr(collector, "fetch_kline", lambda *args, **kwargs: daily)

    def fetch_weekly(*args, **kwargs):
        observed["weekly"].update(kwargs)
        return None

    monkeypatch.setattr(collector, "fetch_weekly_kline", fetch_weekly)
    monkeypatch.setattr(
        collector, "build_technical_payload",
        lambda *args, **kwargs: (
            observed["build"].update(kwargs)
            or {"indicators": {"close": 10.2}, "price_target": None}
        ),
    )
    monkeypatch.setattr(module, "_baidu_fund_flow_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "_baidu_concept_blocks", lambda *args, **kwargs: [])

    collector.collect("300777", market=0, days=2, cache_dir=tmp_path)

    assert observed["weekly"] == {"weeks": 72, "source": "akshare", "adjustment": "qfq"}
    assert observed["build"]["cache_dir"] == tmp_path


def test_collector_has_no_private_ohlcv_normalizer():
    assert not hasattr(TechnicalCollector, "_normalize_ohlcv_frame")

@pytest.mark.skipif(
    os.getenv("RUN_LIVE_DATA_TESTS") != "1",
    reason="live K-line smoke requires RUN_LIVE_DATA_TESTS=1",
)
def test_fetch_kline_300661():
    """Test that we can fetch daily K-line for 圣邦股份."""
    collector = TechnicalCollector()
    df = collector.fetch_kline(code="300661", market=0, days=120)
    if df is None or df.empty:
        pytest.skip("live K-line source unavailable in this environment")
    assert len(df) > 50
    assert "close" in df.columns

def test_legacy_compute_indicators_from_local_frame():
    """Test deterministic legacy indicator computation without live data."""
    collector = TechnicalCollector.__new__(TechnicalCollector)
    close = pd.Series([10.0 + index * 0.05 for index in range(120)])
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=120, freq="B"),
        "open": close - 0.02,
        "high": close + 0.08,
        "low": close - 0.08,
        "close": close,
        "volume": [1000 + index for index in range(120)],
    })
    result = collector._compute_indicators_legacy(df)
    assert "macd" in result
    assert "rsi_14" in result
    assert "ma_60" in result
    assert "boll_upper" in result
