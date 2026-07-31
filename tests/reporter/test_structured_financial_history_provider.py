from __future__ import annotations

import sys
from types import SimpleNamespace

from scripts.utils.reporter import data_fetcher


class _Frame:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, orient):
        assert orient == "records"
        return self.rows


def test_a_share_history_provider_uses_exchange_prefixed_statement_symbols(monkeypatch):
    calls = []
    fake_akshare = SimpleNamespace(
        stock_profit_sheet_by_report_em=lambda symbol: calls.append(("profit", symbol)) or _Frame([{"a": 1}]),
        stock_cash_flow_sheet_by_report_em=lambda symbol: calls.append(("cashflow", symbol)) or _Frame([{"b": 2}]),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    rows = data_fetcher.fetch_structured_financial_history_rows("688385")

    assert calls == [("profit", "SH688385"), ("cashflow", "SH688385")]
    assert rows == {"profit": [{"a": 1}], "cashflow": [{"b": 2}]}


def test_hk_history_provider_uses_key_indicators_and_row_oriented_cashflow(monkeypatch):
    calls = []
    monkeypatch.setattr(
        data_fetcher, "hk_key_indicators",
        lambda secucode, page_size: calls.append(("profit", secucode, page_size)) or [{"a": 1}],
    )

    def fake_datacenter(**kwargs):
        calls.append(("cashflow", kwargs))
        return [{"b": 2}]

    monkeypatch.setattr(data_fetcher, "eastmoney_datacenter", fake_datacenter)
    rows = data_fetcher.fetch_structured_financial_history_rows("02533")

    assert calls[0] == ("profit", "02533.HK", 16)
    assert calls[1][1]["report_name"] == "RPT_HKSK_FN_CASHFLOW"
    assert calls[1][1]["filter_str"] == '(SECUCODE="02533.HK")'
    assert rows == {"profit": [{"a": 1}], "cashflow": [{"b": 2}]}


def test_history_provider_rejects_unsupported_security_codes():
    try:
        data_fetcher.fetch_structured_financial_history_rows("MBLY")
    except ValueError as exc:
        assert "unsupported stock code" in str(exc)
    else:
        raise AssertionError("unsupported code must fail before network access")
