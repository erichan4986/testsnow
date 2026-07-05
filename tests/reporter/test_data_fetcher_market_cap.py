"""Tests for quote market-cap normalization."""

from scripts.utils.reporter.data_fetcher import _normalize_market_cap_fields


def test_normalize_market_cap_flags_float_larger_than_total():
    quote = {
        "mcap_yi": 374.8,
        "float_mcap_yi": 572.3,
        "source": "tencent_a",
    }

    normalized = _normalize_market_cap_fields(quote)

    assert normalized["mcap_yi"] == 374.8
    assert normalized["float_mcap_yi"] is None
    assert normalized["market_cap_quality"] == "market_cap_inconsistent"


def test_normalize_market_cap_marks_missing_float_as_unavailable():
    quote = {
        "mcap_yi": 120.0,
        "source": "tencent_us",
    }

    normalized = _normalize_market_cap_fields(quote)

    assert normalized["mcap_yi"] == 120.0
    assert normalized["float_mcap_yi"] is None
    assert normalized["market_cap_quality"] == "float_market_cap_unavailable"
