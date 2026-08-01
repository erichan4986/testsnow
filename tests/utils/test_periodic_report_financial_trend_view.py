from __future__ import annotations

from copy import deepcopy
import sys
import typing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_financial_trend_view import (  # noqa: E402
    build_periodic_report_financial_trend_view,
)
import periodic_report_financial_trend_view as trend_view_module  # noqa: E402
from periodic_report_metric_series import (  # noqa: E402
    build_periodic_report_metric_series_pack,
)


def _api_point(metric_key: str, value: str, *, year: int) -> dict:
    dataset = "cashflow" if metric_key == "operating_cash_flow" else "profit"
    block_id = f"eastmoney:{dataset}:{year}:{metric_key}"
    return {
        "source_type": "structured_financial_api_fact",
        "fact_id": f"periodic:300001:{year}:annual:{metric_key}",
        "stock_code": "300001",
        "report_year": year,
        "report_type": "annual",
        "period": str(year),
        "metric_key": metric_key,
        "currency": "CNY",
        "unit": "万元",
        "value_basis": "as_reported",
        "normalized_value": f"{value}万元",
        "source_doc": "300001.json",
        "source_block_id": block_id,
        "evidence_refs": [block_id],
        "source_excerpt_hash": "a" * 64,
        "source_block_hash": "b" * 64,
        "provider": "eastmoney",
        "dataset": dataset,
        "source_field": "FIELD",
        "report_date": f"{year}-12-31",
        "cache_data_hash": "c" * 64,
    }


def _metric_pack(rows=None) -> dict:
    points = []
    for year, revenue, profit, cashflow in rows or (
        (2022, "8000.00", "1700.00", "1190.00"),
        (2023, "10000.00", "1500.00", "1200.00"),
        (2024, "12000.00", "1300.00", "1170.00"),
        (2025, "15000.00", "1000.00", "1000.00"),
    ):
        points.extend([
            _api_point("revenue", revenue, year=year),
            _api_point("net_profit", profit, year=year),
            _api_point("operating_cash_flow", cashflow, year=year),
        ])
    return build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        source_points=points,
    )


def _margin_point(year: int, value: str, origin: str = "direct") -> dict:
    return {
        "source_type": "structured_financial_api_fact", "stock_code": "300001",
        "report_year": year, "report_type": "annual", "metric_key": "gross_margin",
        "unit": "pct", "value_basis": "as_reported", "numeric_value": value,
        "origin": origin,
    }


def test_financial_trend_view_type_hints_resolve() -> None:
    hints = typing.get_type_hints(trend_view_module._direction)
    assert hints["values"] == list[trend_view_module.Decimal]


def test_builds_latest_three_year_financial_trend_view() -> None:
    view = build_periodic_report_financial_trend_view(
        stock_code="300001",
        metric_series_pack=_metric_pack(),
    )

    assert view["schema_version"] == "financial_trend_view.v1"
    assert view["status"] == "ready"
    assert view["display_eligible"] is True
    assert view["scoring_eligible"] is False
    assert view["years"] == [2023, 2024, 2025]
    assert [row["metric_key"] for row in view["rows"]] == [
        "revenue",
        "net_profit",
        "operating_cash_flow",
    ]
    assert view["rows"][0] == {
        "metric_key": "revenue",
        "label": "营业收入",
        "unit": "亿元",
        "values": ["1.00", "1.20", "1.50"],
        "latest_growth_rate": "+25.0%",
    }
    assert view["cash_conversion"] == {
        "metric_key": "operating_cash_flow_to_net_profit",
        "label": "现金转换率",
        "unit": "%",
        "values": ["80.0%", "90.0%", "100.0%"],
        "latest_growth_rate": "—",
    }
    assert view["summary"] == "营业收入连续增长，归母净利润连续下滑，经营现金流连续下滑。"
    assert view["source_label"].startswith("东方财富结构化年度财务数据")


def test_adds_optional_gross_margin_with_origin_and_percentage_point_change() -> None:
    view = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=_metric_pack(),
        gross_margin_points=[
            _margin_point(2023, "35.00"),
            _margin_point(2024, "36.50", "derived"),
            _margin_point(2025, "38.10"),
        ],
    )

    assert view["gross_margin"] == {
        "metric_key": "gross_margin", "label": "毛利率", "unit": "%",
        "values": ["35.0%", "36.5%*", "38.1%"],
        "origins": ["direct", "derived", "direct"],
        "latest_change": "+1.6pct",
        "derivation_note": "* 为同源同年财务字段计算值。",
    }
    assert view["summary"].endswith("毛利率连续上升。")


def test_optional_gross_margin_keeps_missing_year_and_fails_independently() -> None:
    partial = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=_metric_pack(),
        gross_margin_points=[_margin_point(2023, "35.00"), _margin_point(2025, "38.10")],
    )
    duplicate = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=_metric_pack(),
        gross_margin_points=[_margin_point(2025, "38.10"), _margin_point(2025, "39.10")],
    )

    assert partial["status"] == "ready"
    assert partial["gross_margin"]["values"] == ["35.0%", "—", "38.1%"]
    assert partial["gross_margin"]["latest_change"] == "—"
    assert duplicate["status"] == "ready"
    assert "gross_margin" not in duplicate
    non_finite = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=_metric_pack(),
        gross_margin_points=[_margin_point(2025, "NaN")],
    )
    assert "gross_margin" not in non_finite


def _unavailable() -> dict:
    return {
        "schema_version": "financial_trend_view.v1",
        "status": "unavailable",
        "display_eligible": False,
        "scoring_eligible": False,
        "stock_code": "300001",
        "years": [],
        "rows": [],
        "cash_conversion": {},
        "summary": "",
        "source_label": "",
    }


def test_rejects_invalid_source_envelopes_and_incomplete_windows() -> None:
    cases = []
    for key, value in (
        ("schema_version", "unsupported.v1"),
        ("stock_code", "999999"),
        ("report_eligible", True),
        ("scoring_eligible", True),
    ):
        pack = _metric_pack()
        pack[key] = value
        cases.append(pack)
    cases.extend([
        _metric_pack([
            (2024, "12000.00", "1300.00", "1170.00"),
            (2025, "15000.00", "1000.00", "1000.00"),
        ]),
        _metric_pack([
            (2022, "10000.00", "1500.00", "1200.00"),
            (2024, "12000.00", "1300.00", "1170.00"),
            (2025, "15000.00", "1000.00", "1000.00"),
        ]),
    ])

    assert [
        build_periodic_report_financial_trend_view(
            stock_code="300001", metric_series_pack=pack,
        )
        for pack in cases
    ] == [_unavailable()] * len(cases)


def test_rejects_duplicate_annual_series_and_mixed_value_basis() -> None:
    duplicate = _metric_pack()
    extra = deepcopy(next(row for row in duplicate["series"] if row["metric_key"] == "revenue"))
    extra["value_basis"] = "restated"
    extra["series_id"] = extra["series_id"].replace(":as_reported:", ":restated:")
    duplicate["series"].append(extra)

    mixed = _metric_pack()
    profit = next(row for row in mixed["series"] if row["metric_key"] == "net_profit")
    profit["value_basis"] = "restated"
    profit["series_id"] = profit["series_id"].replace(":as_reported:", ":restated:")

    for pack in (duplicate, mixed):
        assert build_periodic_report_financial_trend_view(
            stock_code="300001", metric_series_pack=pack,
        ) == _unavailable()


def test_rejects_duplicate_cash_conversion_series() -> None:
    pack = _metric_pack()
    pack["derived_series"].append(deepcopy(pack["derived_series"][0]))

    view = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=pack,
    )

    assert view == _unavailable()


def test_missing_cash_conversion_point_does_not_reject_base_metrics() -> None:
    pack = _metric_pack([
        (2023, "10000.00", "1500.00", "1200.00"),
        (2024, "12000.00", "-100.00", "-300.00"),
        (2025, "15000.00", "1000.00", "1000.00"),
    ])

    view = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=pack,
    )

    assert view["status"] == "ready"
    assert view["cash_conversion"]["values"] == ["80.0%", "—", "100.0%"]
    assert view["summary"] == "营业收入连续增长，归母净利润存在波动，经营现金流存在波动。"


def test_ignores_a_valid_semiannual_series() -> None:
    pack = _metric_pack()
    semiannual = deepcopy(next(row for row in pack["series"] if row["metric_key"] == "revenue"))
    semiannual["report_type"] = "semiannual"
    semiannual["series_id"] = semiannual["series_id"].replace(":annual:", ":semiannual:")
    for point in semiannual["points"]:
        point["fact_refs"] = [point["fact_refs"][0].replace(":annual:", ":semiannual:")]
    for change in semiannual["changes"]:
        change["input_refs"] = [ref.replace(":annual:", ":semiannual:") for ref in change["input_refs"]]
    pack["series"].extend([semiannual, deepcopy(semiannual)])

    view = build_periodic_report_financial_trend_view(
        stock_code="300001", metric_series_pack=pack,
    )

    assert view["status"] == "ready"
    assert view["years"] == [2023, 2024, 2025]
