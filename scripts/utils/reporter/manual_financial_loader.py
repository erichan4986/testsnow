"""Manual financial override loader for locally supplied Wind-style files."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


_ALIASES = {
    "report_date": ["report_date", "报告日期", "报告期", "日期"],
    "date_type": ["date_type", "report_type", "报告类型", "报表类型"],
    "currency": ["currency", "币种"],
    "revenue": ["revenue", "营业收入", "营业总收入"],
    "revenue_yoy": ["revenue_yoy", "营业收入同比", "营业总收入同比"],
    "gross_profit": ["gross_profit", "毛利"],
    "gross_profit_yoy": ["gross_profit_yoy", "毛利同比"],
    "gross_margin": ["gross_margin", "毛利率"],
    "gross_margin_yoy": ["gross_margin_yoy", "毛利率同比"],
    "net_profit": ["net_profit", "归母净利润", "净利润"],
    "net_profit_yoy": ["net_profit_yoy", "归母净利润同比", "净利润同比"],
    "net_margin": ["net_margin", "净利率", "销售净利率"],
    "net_margin_yoy": ["net_margin_yoy", "净利率同比"],
    "roe": ["roe", "ROE", "净资产收益率"],
    "basic_eps": ["basic_eps", "基本每股收益", "EPS"],
    "eps_yoy": ["eps_yoy", "每股收益同比", "EPS同比"],
    "debt_ratio": ["debt_ratio", "debt_asset_ratio", "资产负债率"],
    "operating_cash_flow": ["operating_cash_flow", "经营现金流", "经营活动现金流"],
    "rd_expense": ["rd_expense", "研发费用"],
    "source": ["source", "来源", "数据来源"],
}

_NUMERIC_FIELDS = {
    "revenue",
    "revenue_yoy",
    "gross_profit",
    "gross_profit_yoy",
    "gross_margin",
    "gross_margin_yoy",
    "net_profit",
    "net_profit_yoy",
    "net_margin",
    "net_margin_yoy",
    "roe",
    "basic_eps",
    "eps_yoy",
    "debt_ratio",
    "operating_cash_flow",
    "rd_expense",
}


def _manual_dir(raw_dir: Path | None = None) -> Path:
    if raw_dir is None:
        raw_dir = Path(__file__).resolve().parents[3] / "data" / "raw"
    return Path(raw_dir) / "manual_financials"


def _candidate_paths(identifier: str, raw_dir: Path | None = None) -> list[Path]:
    base = _manual_dir(raw_dir)
    stems = [
        f"{identifier}_financials",
        f"{identifier}财务数据",
        f"{identifier}财务",
    ]
    paths: list[Path] = []
    for stem in stems:
        paths.extend([base / f"{stem}.xlsx", base / f"{stem}.csv"])
    return paths


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def _first_present(row: pd.Series, aliases: list[str]) -> Any:
    for alias in aliases:
        if alias in row.index:
            val = row.get(alias)
            if pd.notna(val):
                return val
    return None


def _to_number(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if not text or text in {"-", "N/A", "nan", "None"}:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def load_manual_financials(identifier: str, raw_dir: Path | None = None) -> Optional[Dict[str, Any]]:
    """Load latest local manual financial row for stock name or code.

    Expected location:
    `data/raw/manual_financials/<identifier>_financials.{csv,xlsx}`.
    """
    identifier = str(identifier or "").strip()
    if not identifier:
        return None

    path = next((p for p in _candidate_paths(identifier, raw_dir=raw_dir) if p.exists()), None)
    if path is None:
        return None

    df = _read_table(path)
    if df is None or df.empty:
        return None

    if "report_date" not in df.columns:
        for alias in _ALIASES["report_date"]:
            if alias in df.columns:
                df = df.rename(columns={alias: "report_date"})
                break
    if "report_date" in df.columns:
        df["_report_date_sort"] = pd.to_datetime(df["report_date"], errors="coerce")
        df = df.sort_values("_report_date_sort", ascending=False, na_position="last")

    row = df.iloc[0]
    result: Dict[str, Any] = {}
    for field, aliases in _ALIASES.items():
        value = _first_present(row, aliases)
        if field in _NUMERIC_FIELDS:
            value = _to_number(value)
        elif value is not None:
            value = str(value).strip()
        if value is not None:
            result[field] = value

    if not result:
        return None

    if "report_date" in result:
        result["report_date"] = str(result["report_date"])[:10]
    if "source" in result:
        result["source"] = f"manual_financials:{result['source']}"
    else:
        result["source"] = "manual_financials"
    return result
