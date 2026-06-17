from unittest.mock import patch

import logging

from scripts.utils.reporter import data_fetcher


def test_latest_quarterly_financials_prefers_manual_financials():
    manual = {
        "report_date": "2025-12-31",
        "date_type": "年报",
        "revenue": 822328000,
        "gross_margin": 41.0,
        "source": "manual_financials:Wind",
    }

    with patch.object(data_fetcher, "load_manual_financials", return_value=manual) as mock_manual, patch.object(
        data_fetcher, "hk_key_indicators"
    ) as mock_hk:
        result = data_fetcher.fetch_latest_quarterly_financials("02533")

    mock_manual.assert_called_once_with("02533")
    mock_hk.assert_not_called()
    assert result == manual


def test_latest_quarterly_financials_falls_back_to_manual_stock_name_for_code():
    manual = {
        "report_date": "2025-12-31",
        "date_type": "年报",
        "revenue": 822328000,
        "source": "manual_financials:Wind",
    }

    def fake_manual(identifier):
        return manual if identifier == "黑芝麻智能" else None

    with patch.object(data_fetcher, "load_manual_financials", side_effect=fake_manual), patch.object(
        data_fetcher, "hk_key_indicators"
    ) as mock_hk:
        result = data_fetcher.fetch_latest_quarterly_financials("02533")

    mock_hk.assert_not_called()
    assert result == manual


def test_competitor_metrics_uses_manual_financials_for_non_standard_code_without_akshare():
    manual = {
        "report_date": "2025-12-31",
        "date_type": "年报",
        "revenue": 100000000,
        "gross_margin": 30.0,
        "source": "manual_financials:Wind",
    }

    def fake_manual(identifier):
        return manual if identifier == "H100027" else None

    with patch.object(data_fetcher, "load_manual_financials", side_effect=fake_manual), patch.object(
        data_fetcher, "fetch_financial_abstract"
    ) as mock_financial, patch.object(data_fetcher, "fetch_tencent_quote", return_value=None), patch.object(
        data_fetcher, "fetch_consensus_eps", return_value=None
    ):
        result = data_fetcher.fetch_competitor_metrics("中简科技", {"中简科技": "300777"})

    assert result["恒神股份"]["revenue"] == 100000000
    assert result["恒神股份"]["gross_margin"] == 30.0
    assert result["恒神股份"]["source"] == "manual_financials:Wind"
    assert all(call.args[0] != "H100027" for call in mock_financial.call_args_list)


def test_competitor_metrics_skips_non_standard_code_without_manual_financials():
    with patch.object(data_fetcher, "load_manual_financials", return_value=None), patch.object(
        data_fetcher, "fetch_financial_abstract"
    ) as mock_financial, patch.object(data_fetcher, "fetch_tencent_quote", return_value=None), patch.object(
        data_fetcher, "fetch_consensus_eps", return_value=None
    ):
        result = data_fetcher.fetch_competitor_metrics("中简科技", {"中简科技": "300777"})

    assert "恒神股份" in result
    assert all(call.args[0] != "H100027" for call in mock_financial.call_args_list)


def test_financial_abstract_skips_non_standard_code_without_warning(caplog):
    with caplog.at_level(logging.INFO), patch("builtins.__import__") as mock_import:
        result = data_fetcher.fetch_financial_abstract("H100027")

    assert result is None
    assert "非标准A股代码" in caplog.text
    assert "已跳过财务摘要接口" in caplog.text
    assert "财务指标获取失败" not in caplog.text
    assert all(call.args[0] != "akshare" for call in mock_import.call_args_list)


def test_latest_quarterly_financials_skips_non_standard_code_without_akshare(caplog):
    with caplog.at_level(logging.INFO), patch.object(
        data_fetcher, "load_manual_financials", return_value=None
    ), patch("builtins.__import__") as mock_import:
        result = data_fetcher.fetch_latest_quarterly_financials("H100027")

    assert result is None
    assert "非标准A股代码" in caplog.text
    assert "已跳过季度财务接口" in caplog.text
    assert "最新季度财务数据获取失败" not in caplog.text
    assert all(call.args[0] != "akshare" for call in mock_import.call_args_list)
