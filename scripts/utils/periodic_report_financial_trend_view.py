"""Display-only projection of validated annual financial metric series."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
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
    gross_margin_points: list[dict[str, Any]] | None = None,
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
    view = {
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
    margin = _gross_margin_row(gross_margin_points or [], str(stock_code), years)
    if margin:
        view["gross_margin"] = margin
        if all(value != "—" for value in margin["values"]):
            values = [Decimal(value.rstrip("%*")) for value in margin["values"]]
            direction = "连续上升" if values[0] < values[1] < values[2] else "连续下降" if values[0] > values[1] > values[2] else "存在波动"
            view["summary"] = view["summary"].rstrip("。") + f"，毛利率{direction}。"
    return view


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


def _gross_margin_row(
    points: list[dict[str, Any]], stock_code: str, years: list[int],
) -> dict[str, Any] | None:
    if not points or any(
        str(point.get("stock_code")) != stock_code or point.get("metric_key") != "gross_margin"
        or point.get("report_type") != "annual" or point.get("unit") != "pct"
        or point.get("value_basis") != "as_reported" or point.get("origin") not in {"direct", "derived"}
        for point in points
    ):
        return None
    index: dict[int, tuple[Decimal, str]] = {}
    for point in points:
        year = point.get("report_year")
        try:
            value = Decimal(str(point.get("numeric_value") or ""))
        except (InvalidOperation, ValueError):
            return None
        if not value.is_finite():
            return None
        if year in index:
            return None
        if year in years:
            index[year] = (value, point["origin"])
    if not index:
        return None
    origins = [index[year][1] if year in index else "missing" for year in years]
    values = [f"{index[year][0]:.1f}%" + ("*" if index[year][1] == "derived" else "") if year in index else "—" for year in years]
    latest = "—" if years[-2] not in index or years[-1] not in index else f"{index[years[-1]][0] - index[years[-2]][0]:+.1f}pct"
    return {
        "metric_key": "gross_margin", "label": "毛利率", "unit": "%", "values": values,
        "origins": origins, "latest_change": latest,
        "derivation_note": "* 为同源同年财务字段计算值。",
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
