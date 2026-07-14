import sys
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from data_collector import TechnicalCollector, ReportCollector, AnnouncementCollector, FundFlowCollector, NewsCollector


def test_compute_indicators_is_compatibility_wrapper_with_market():
    collector = TechnicalCollector.__new__(TechnicalCollector)
    frame = pd.DataFrame({"close": [10.0, 10.5], "volume": [100, 110]})
    payload = {"indicators": {"close": 10.5}, "price_target": {"status": "observe"}}
    with patch.object(collector, "build_technical_payload", return_value=payload) as builder:
        result = collector.compute_indicators(frame, code="02533", market="hk")
    builder.assert_called_once()
    assert result == payload["indicators"]


def test_build_payload_passes_hk_market_to_analyzer(monkeypatch):
    collector = TechnicalCollector.__new__(TechnicalCollector)
    daily = pd.DataFrame({"open": [10.0] * 30, "high": [11.0] * 30, "low": [9.0] * 30, "close": [10.5] * 30, "volume": [100.0] * 30})
    weekly = daily.iloc[::5].reset_index(drop=True)
    observed = {}

    def fake_analyze(df, df_weekly, code, market):
        observed.update({"code": code, "market": market})
        return {"indicators": {"close": 10.5}, "resonance": {}, "price_target": {"status": "observe", "reason_code": "weekly_range", "direction": "neutral"}, "patterns": [], "levels": {}}

    monkeypatch.setattr(collector, "_run_technical_analyzer", fake_analyze)
    result = collector.build_technical_payload(daily, weekly, code="02533", market="hk")
    assert observed == {"code": "02533", "market": "hk"}
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

def test_fetch_kline_300661():
    """Test that we can fetch daily K-line for 圣邦股份."""
    collector = TechnicalCollector()
    df = collector.fetch_kline(code="300661", market=0, days=120)
    assert df is not None
    assert len(df) > 50
    assert "close" in df.columns

def test_compute_indicators():
    """Test indicator computation."""
    collector = TechnicalCollector()
    df = collector.fetch_kline(code="300661", market=0, days=120)
    result = collector.compute_indicators(df)
    assert "macd" in result
    assert "rsi_14" in result
    assert "ma_60" in result
    assert "boll_upper" in result

def test_fetch_reports_300661():
    """Test research report fetching for 圣邦股份."""
    collector = ReportCollector()
    reports = collector.collect(code="300661", months=4)
    assert isinstance(reports, list)
    if len(reports) > 0:
        assert "title" in reports[0]
        assert "institution" in reports[0]

def test_fetch_announcements_300661():
    """Test announcement fetching for 圣邦股份."""
    collector = AnnouncementCollector()
    announcements = collector.collect(code="300661", months=3)
    assert isinstance(announcements, list)
    if len(announcements) > 0:
        assert "title" in announcements[0]
        assert "date" in announcements[0]

def test_fetch_fundflow_300661():
    collector = FundFlowCollector()
    data = collector.collect(code="300661", days=7)
    assert isinstance(data, list)

def test_fetch_news_300661():
    collector = NewsCollector()
    data = collector.collect(code="300661", days=30)
    assert isinstance(data, list)
