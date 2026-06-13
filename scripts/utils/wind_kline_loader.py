"""Local Wind Excel K-line loader.

Reads manually exported Wind行情 Excel files from data/raw/ for Hong Kong stocks.
"""

from pathlib import Path
from typing import Dict, Optional

import pandas as pd


def find_wind_excel(stock_name: str, raw_dir: Path | None = None) -> Path | None:
    """Locate a Wind Excel file for the given stock name."""
    raw_dir = raw_dir or Path(__file__).resolve().parent.parent.parent / "data" / "raw"
    candidate = raw_dir / f"{stock_name}数据.xlsx"
    if candidate.exists():
        return candidate
    return None


def load_wind_ohlcv(path: Path, sheet_name: str, days: int | None = None) -> pd.DataFrame:
    """Load and normalize a single OHLCV sheet from a Wind Excel file.

    Args:
        path: Path to the Excel file.
        sheet_name: Name of the sheet to load.
        days: Optional number of most recent rows to retain.

    Returns:
        Cleaned DataFrame with columns: date, open, high, low, close, volume, amount.
    """
    df = pd.read_excel(path, sheet_name=sheet_name, header=5)

    # Rename columns to lowercase standard names
    rename_map = {
        "Date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amt": "amount",
    }
    df = df.rename(columns=rename_map)

    # Convert date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Coerce numeric fields
    numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop incomplete rows (missing any core OHLCV field)
    required = ["date", "open", "high", "low", "close", "volume"]
    df = df.dropna(subset=required)

    # Sort ascending by date
    df = df.sort_values("date").reset_index(drop=True)

    # Tail to requested days
    if days is not None:
        df = df.tail(days).reset_index(drop=True)

    # Set attrs
    df.attrs["data_source"] = "wind_excel"
    df.attrs["adjustment"] = "raw"
    df.attrs["wind_sheet"] = sheet_name

    return df


def load_wind_package(stock_name: str, days: int = 120, raw_dir: Path | None = None) -> Dict:
    """Load stock OHLCV and benchmark sheets from a Wind Excel package.

    Returns an empty dict when no matching Excel exists.
    """
    path = find_wind_excel(stock_name, raw_dir=raw_dir)
    if path is None:
        return {}

    package = {
        "path": str(path),
        "daily": load_wind_ohlcv(path, stock_name, days=days),
        "benchmarks": {},
    }

    benchmark_sheets = ["恒生人工智能主题", "恒生科技指数"]
    for sheet in benchmark_sheets:
        try:
            package["benchmarks"][sheet] = load_wind_ohlcv(path, sheet, days=days)
        except Exception:
            # Benchmark sheet may not exist in all files
            pass

    return package
