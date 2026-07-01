"""Tests for Wind Excel K-line loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from wind_kline_loader import (
    find_wind_excel,
    load_wind_ohlcv,
    load_wind_package,
)


def test_find_wind_excel_locates_black_sesame_file():
    path = find_wind_excel("黑芝麻智能")
    assert path is not None
    assert path.name == "黑芝麻智能数据.xlsx"


def test_load_wind_ohlcv_normalizes_and_drops_incomplete_rows():
    path = Path("data/raw/黑芝麻智能数据.xlsx")
    df = load_wind_ohlcv(path, "黑芝麻智能", days=120)

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amount"]
    assert len(df) <= 120
    assert df[["open", "high", "low", "close", "volume"]].isna().sum().sum() == 0
    assert str(df["date"].iloc[-1].date()) == "2026-06-30"
    assert df.attrs["data_source"] == "wind_excel"
    assert df.attrs["adjustment"] == "raw"
    assert df.attrs["wind_sheet"] == "黑芝麻智能"


def test_load_wind_package_includes_benchmarks():
    package = load_wind_package("黑芝麻智能", days=120)

    assert package["daily"].attrs["data_source"] == "wind_excel"
    assert "恒生人工智能主题" in package["benchmarks"]
    assert "恒生科技指数" in package["benchmarks"]
    assert len(package["benchmarks"]["恒生科技指数"]) <= 120
