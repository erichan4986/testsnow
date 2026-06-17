import logging
import sys
from pathlib import Path

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
        def k(self, *args, **kwargs):
            return pd.DataFrame(
                {
                    "open": [1.0, 1.1],
                    "high": [1.2, 1.3],
                    "low": [0.9, 1.0],
                    "close": [1.1, 1.2],
                    "volume": [1000, 1100],
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
