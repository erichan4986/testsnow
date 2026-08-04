import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

import data_collector
from data_collector import AkshareHelper, TechnicalCollector, _baidu_fund_flow_history


def _boom(*args, **kwargs):
    raise ConnectionError("proxy blocked")


def test_optional_akshare_failure_is_logged_as_skip_not_error(caplog):
    helper = AkshareHelper(delay_sec=0, max_retries=1)

    with caplog.at_level(logging.INFO, logger="data_collector"):
        result = helper.call(
            _boom,
            optional=True,
            source_name="akshare index_zh_a_hist",
            fallback_name="mootdx",
        )

    assert result is None
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert "可选数据源 akshare index_zh_a_hist 不可用，已交给 mootdx" in caplog.text


def test_required_akshare_failure_keeps_error_log(caplog):
    helper = AkshareHelper(delay_sec=0, max_retries=1)

    with caplog.at_level(logging.WARNING, logger="data_collector"):
        result = helper.call(_boom, source_name="akshare stock_financial_abstract")

    assert result is None
    assert "akshare 调用 akshare stock_financial_abstract 最终失败" in caplog.text


def test_baidu_fund_flow_failure_is_optional_info(monkeypatch, caplog):
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("network timeout")

    monkeypatch.setattr(requests, "get", raise_timeout)

    with caplog.at_level(logging.INFO, logger="data_collector"):
        rows = _baidu_fund_flow_history("300777", days=5)

    assert rows == []
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert "可选数据源 百度资金流向 不可用，已跳过" in caplog.text


def test_fetch_kline_logs_akshare_fallback_to_mootdx(monkeypatch, caplog):
    class FakeAk:
        @staticmethod
        def stock_zh_a_hist(*args, **kwargs):
            raise ConnectionError("proxy blocked")

    class FakeClient:
        def bars(self, *args, **kwargs):
            return pd.DataFrame(
                {
                    "datetime": pd.to_datetime(["2026-07-01", "2026-07-02"]),
                    "open": [1.0, 1.1],
                    "high": [1.2, 1.3],
                    "low": [0.9, 1.0],
                    "close": [1.1, 1.2],
                    "vol": [1000, 1100],
                }
            )

    monkeypatch.setattr(data_collector, "ak", FakeAk)
    collector = TechnicalCollector()
    collector.client = FakeClient()

    with caplog.at_level(logging.INFO, logger="data_collector"):
        df = collector.fetch_kline("300777", market=0, days=2)

    assert df is not None
    assert df.attrs["data_source"] == "mootdx"
    assert "可选数据源 akshare stock_zh_a_hist 不可用，已交给 mootdx raw" in caplog.text


def test_collector_constructor_does_not_initialize_mootdx():
    with patch.object(data_collector.Quotes, "factory") as factory:
        collector = TechnicalCollector()

    factory.assert_not_called()
    assert collector.client is None


def test_mootdx_daily_uses_one_native_daily_bars_call(monkeypatch):
    calls = []

    class FakeClient:
        def bars(self, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame({
                "datetime": pd.to_datetime(["2026-07-01", "2026-07-02"]),
                "open": [1.0, 1.1], "high": [1.2, 1.3],
                "low": [0.9, 1.0], "close": [1.1, 1.2],
                "vol": [1000, 1100], "volume": [9000, 9100],
                "amount": [1100, 1320],
            })

    monkeypatch.setattr(data_collector, "ak", None)
    collector = TechnicalCollector.__new__(TechnicalCollector)
    collector.client = FakeClient()

    frame = collector.fetch_kline("300777", market=0, days=2)

    assert len(calls) == 1
    assert calls[0] == {"symbol": "300777", "frequency": 9, "start": 0, "offset": 2}
    assert frame.columns.tolist() == ["date", "open", "high", "low", "close", "volume", "amount"]
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-07-01", "2026-07-02"]
    assert frame["volume"].tolist() == [9000, 9100]


def test_mootdx_daily_exception_is_not_retried(monkeypatch):
    calls = 0

    class FakeClient:
        def bars(self, **kwargs):
            nonlocal calls
            calls += 1
            raise KeyError("datetime")

    monkeypatch.setattr(data_collector, "ak", None)
    collector = TechnicalCollector.__new__(TechnicalCollector)
    collector.client = FakeClient()

    assert collector.fetch_kline("300777", market=0, days=120) is None
    assert calls == 1


def test_mootdx_weekly_uses_real_weekly_frequency(monkeypatch):
    calls = []

    class FakeClient:
        def bars(self, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame({
                "datetime": pd.to_datetime(["2026-06-26", "2026-07-03"]),
                "open": [1.0, 1.1], "high": [1.2, 1.3],
                "low": [0.9, 1.0], "close": [1.1, 1.2], "vol": [5000, 5500],
            })

    monkeypatch.setattr(data_collector, "ak", None)
    collector = TechnicalCollector.__new__(TechnicalCollector)
    collector.client = FakeClient()

    frame = collector.fetch_weekly_kline(
        "300777", market=0, weeks=2, source="mootdx", adjustment="raw",
    )

    assert len(frame) == 2
    assert calls == [{"symbol": "300777", "frequency": 5, "start": 0, "offset": 2}]


def test_explicit_qfq_does_not_fall_through_to_raw(monkeypatch):
    class FakeAk:
        @staticmethod
        def stock_zh_a_hist(*args, **kwargs):
            raise ValueError("bad qfq response")

    class FakeClient:
        def bars(self, **kwargs):
            raise AssertionError("explicit qfq must not use mootdx")

    monkeypatch.setattr(data_collector, "ak", FakeAk)
    collector = TechnicalCollector.__new__(TechnicalCollector)
    collector.client = FakeClient()

    assert collector.fetch_kline("300777", market=0, days=2, adjustment="qfq") is None


def test_akshare_weekly_does_not_initialize_or_fall_through_to_mootdx(monkeypatch):
    class FakeAk:
        @staticmethod
        def stock_zh_a_hist(*args, **kwargs):
            return pd.DataFrame({
                "日期": ["2026-06-26", "2026-07-03"],
                "开盘": [1.0, 1.1], "最高": [1.2, 1.3],
                "最低": [0.9, 1.0], "收盘": [1.1, 1.2], "成交量": [5000, 5500],
            })

    monkeypatch.setattr(data_collector, "ak", FakeAk)
    collector = TechnicalCollector()
    with patch.object(data_collector.Quotes, "factory") as factory:
        frame = collector.fetch_weekly_kline(
            "300777", market=0, weeks=2, source="akshare", adjustment="qfq",
        )

    factory.assert_not_called()
    assert frame.attrs == {"data_source": "akshare", "adjustment": "qfq"}
