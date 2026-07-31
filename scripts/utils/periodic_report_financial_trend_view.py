"""Display-only projection of validated annual financial metric series."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

if __name__.startswith("utils."):
    from .periodic_report_financial_scan import read_periodic_financial_scan_source
else:
    from periodic_report_financial_scan import read_periodic_financial_scan_source

FINANCIAL_TREND_VIEW_SCHEMA_VERSION = "financial_trend_view.v1"
_SOURCE_LABEL = "东方财富结构化年度财务数据；仅用于趋势观察，不替代年报确认，不参与评分。"
_BASE_METRICS = (("revenue", "营业收入"), ("net_profit", "归母净利润"),
                 ("operating_cash_flow", "经营现金流"))
_DISPLAY_SERIES_TOKENS = tuple(f":annual:{key}:" for key, _ in _BASE_METRICS) + (
    ":annual:operating_cash_flow_to_net_profit:",)


def build_periodic_report_financial_trend_view(
    *, stock_code: str, metric_series_pack: dict[str, Any],
) -> dict[str, Any]:
    """Return a strict latest-three-year Chapter 2 display view."""
    source = read_periodic_financial_scan_source(
        stock_code=stock_code, metric_series_pack=metric_series_pack,
    )
    if source["status"] != "ok" or any(
        row.get("code") == "duplicate_source_series_id" and any(
            token in str(row.get("series_id") or "") for token in _DISPLAY_SERIES_TOKENS)
        for row in source["diagnostics"]):
        return _unavailable(stock_code)
    candidates = {
        key: [row for row in source["filing_series"]
              if row["report_type"] == "annual" and row["metric_key"] == key]
        for key, _ in _BASE_METRICS
    }
    if any(len(rows) != 1 for rows in candidates.values()):
        return _unavailable(stock_code)
    selected = [candidates[key][0] for key, _ in _BASE_METRICS]
    if len({row["value_basis"] for row in selected}) != 1:
        return _unavailable(stock_code)
    common_years = set.intersection(*(
        {point["report_year"] for point in row["points"]} for row in selected
    ))
    years = sorted(common_years)[-3:]
    if len(years) != 3 or years != list(range(years[0], years[0] + 3)):
        return _unavailable(stock_code)
    raw_values = {row["metric_key"]: _point_values(row, years) for row in selected}
    ratio = _cash_conversion_row(
        source["derived_series"], selected[0]["value_basis"], years,
    )
    if ratio is None:
        return _unavailable(stock_code)
    return {
        "schema_version": FINANCIAL_TREND_VIEW_SCHEMA_VERSION,
        "status": "ready",
        "display_eligible": True,
        "scoring_eligible": False,
        "stock_code": str(stock_code),
        "years": years,
        "rows": [_display_row(row, label, years)
                 for row, (_, label) in zip(selected, _BASE_METRICS)],
        "cash_conversion": ratio,
        "summary": "，".join(
            f"{label}{_direction(raw_values[key])}" for key, label in _BASE_METRICS
        ) + "。",
        "source_label": _SOURCE_LABEL,
    }


def _unavailable(stock_code: str) -> dict[str, Any]:
    return {
        "schema_version": FINANCIAL_TREND_VIEW_SCHEMA_VERSION, "status": "unavailable",
        "display_eligible": False, "scoring_eligible": False,
        "stock_code": str(stock_code), "years": [], "rows": [],
        "cash_conversion": {}, "summary": "", "source_label": "",
    }

def _point_values(row: dict[str, Any], years: list[int]) -> list[Decimal]:
    index = {point["report_year"]: Decimal(point["numeric_value"])
             for point in row["points"]}
    return [index[year] for year in years]


def _display_row(row: dict[str, Any], label: str, years: list[int]) -> dict[str, Any]:
    interval = (str(years[-2]), str(years[-1]))
    match = next((change for change in row["changes"]
                  if (change["from_period"], change["to_period"]) == interval), None)
    rate = Decimal(match["growth_rate"].removesuffix("%")) if match and match["growth_rate"] else None
    return {
        "metric_key": row["metric_key"],
        "label": label,
        "unit": "亿元",
        "values": [f"{value / Decimal('10000'):.2f}"
                   for value in _point_values(row, years)],
        "latest_growth_rate": "—" if rate is None else (f"{rate:+.1f}%" if rate else "0.0%"),
    }


def _cash_conversion_row(
    rows: list[dict[str, Any]], value_basis: str, years: list[int],
) -> dict[str, Any] | None:
    candidates = [row for row in rows if row["report_type"] == "annual"
                  and row["value_basis"] == value_basis]
    if len(candidates) > 1:
        return None
    index = ({point["report_year"]: Decimal(point["numeric_value"])
              for point in candidates[0]["points"]} if candidates else {})
    return {
        "metric_key": "operating_cash_flow_to_net_profit", "label": "现金转换率",
        "unit": "%", "latest_growth_rate": "—",
        "values": [f"{index[year]:.1f}%" if year in index else "—" for year in years],
    }


def _direction(values: list[Decimal]) -> str:
    if values[0] < 0 < values[-1]:
        return "由负转正"
    if values[0] > 0 > values[-1]:
        return "由正转负"
    if all(value < 0 for value in values):
        return "持续为负"
    if values[0] < values[1] < values[2]:
        return "连续增长"
    if values[0] > values[1] > values[2]:
        return "连续下滑"
    return "存在波动"
