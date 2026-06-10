"""Tests for price_adjustment_validator module."""

import numpy as np
import pandas as pd
import pytest


def _import_module():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    import price_adjustment_validator as pav
    return pav


def test_detect_price_gaps_no_gap():
    pav = _import_module()
    dates = pd.date_range("2026-01-01", periods=10, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "close": [100.0 + i * 0.5 for i in range(10)],
    })
    result = pav.detect_price_gaps(df, gap_threshold=0.25)
    assert result["possible_exrights_gap"] is False
    assert result["max_gap_pct"] == 0.0


def test_detect_price_gaps_with_gap():
    pav = _import_module()
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "close": [100.0, 101.0, 102.0, 70.0, 71.0],
    })
    result = pav.detect_price_gaps(df, gap_threshold=0.25)
    assert result["possible_exrights_gap"] is True
    assert result["max_gap_pct"] > 25.0
    assert result["gap_date"] == str(dates[3])


def test_validate_adjustment_raw_with_gap():
    pav = _import_module()
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "close": [100.0, 101.0, 102.0, 70.0, 71.0],
    })
    result = pav.validate_adjustment(df, adjustment="raw")
    assert result["requires_qfq"] is True
    assert result["confidence_limit"] == "低"
    assert result["warning_message"] is not None


def test_validate_adjustment_qfq_with_gap():
    pav = _import_module()
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "date": dates,
        "close": [100.0, 101.0, 102.0, 70.0, 71.0],
    })
    result = pav.validate_adjustment(df, adjustment="qfq")
    assert result["requires_qfq"] is False
    assert result["confidence_limit"] == "中"


def test_apply_qfq_adjustment_single_split():
    pav = _import_module()
    dates = pd.date_range("2026-01-01", "2026-01-15", freq="B")
    prices = [100.0] * len(dates)
    df = pd.DataFrame({
        "date": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
    })
    xdxr = pd.DataFrame({
        "year": [2026], "month": [1], "day": [10],
        "category": [1], "name": ["除权除息"],
        "fenhong": [5.0], "songzhuangu": [4.0], "peigu": [0.0], "peigujia": [0.0],
    })
    result = pav.apply_qfq_adjustment(df, xdxr)
    before = result[result["date"] < "2026-01-10"]
    after = result[result["date"] >= "2026-01-10"]
    # After split date: unchanged
    assert after["close"].iloc[0] == 100.0
    # Before split date: adjusted by (100 - 0.5) / 1.4 = 71.07...
    expected_before = (100.0 - 0.5) / 1.4
    assert abs(before["close"].iloc[0] - expected_before) < 0.01


def test_apply_qfq_adjustment_multiple_splits():
    pav = _import_module()
    dates = pd.date_range("2025-01-01", "2026-06-15", freq="B")
    prices = [200.0] * len(dates)
    df = pd.DataFrame({
        "date": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
    })
    xdxr = pd.DataFrame({
        "year": [2025, 2026],
        "month": [6, 6],
        "day": [4, 5],
        "category": [1, 1],
        "name": ["除权除息", "除权除息"],
        "fenhong": [6.0, 5.0],
        "songzhuangu": [4.0, 4.0],
        "peigu": [0.0, 0.0],
        "peigujia": [0.0, 0.0],
    })
    result = pav.apply_qfq_adjustment(df, xdxr)
    # After 2026-06-05: unchanged = 200
    after_latest = result[result["date"] >= "2026-06-05"]
    assert after_latest["close"].iloc[0] == 200.0

    # Between 2025-06-04 and 2026-06-05: adjusted by 2026 split only
    between = result[(result["date"] >= "2025-06-04") & (result["date"] < "2026-06-05")]
    expected_between = (200.0 - 0.5) / 1.4
    assert abs(between["close"].iloc[0] - expected_between) < 0.01

    # Before 2025-06-04: adjusted by both splits (most recent first)
    before_both = result[result["date"] < "2025-06-04"]
    # Code applies from most recent to oldest:
    # First apply 2026 split: (200 - 0.5) / 1.4 = 142.5
    # Then apply 2025 split: (142.5 - 0.6) / 1.4 = 101.36
    step1 = (200.0 - 0.5) / 1.4
    expected_before = (step1 - 0.6) / 1.4
    assert abs(before_both["close"].iloc[0] - expected_before) < 0.01


def test_apply_qfq_adjustment_empty_xdxr():
    pav = _import_module()
    df = pd.DataFrame({"date": ["2026-01-01"], "close": [100.0]})
    result = pav.apply_qfq_adjustment(df, pd.DataFrame())
    assert result["close"].iloc[0] == 100.0


def test_apply_qfq_adjustment_no_category_1():
    pav = _import_module()
    df = pd.DataFrame({"date": ["2026-01-01"], "close": [100.0]})
    xdxr = pd.DataFrame({
        "year": [2026], "month": [1], "day": [1],
        "category": [5], "name": ["股本变化"],
        "fenhong": [None], "songzhuangu": [None], "peigu": [None], "peigujia": [None],
    })
    result = pav.apply_qfq_adjustment(df, xdxr)
    assert result["close"].iloc[0] == 100.0
