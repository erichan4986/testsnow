"""Deterministic structured financial-history cache and source-point adapter."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


SCHEMA_VERSION = "structured_financial_history_cache.v1"
SOURCE_TYPE = "structured_financial_api_fact"
_METRICS = ("revenue", "net_profit", "operating_cash_flow")
_OPTIONAL_METRICS = ("gross_margin",)
_FIELDS = {
    ("A", "profit"): (("revenue", "TOTAL_OPERATE_INCOME"), ("net_profit", "PARENT_NETPROFIT")),
    ("A", "cashflow"): (("operating_cash_flow", "NETCASH_OPERATE"),),
    ("HK", "profit"): (("revenue", "OPERATE_INCOME"), ("net_profit", "HOLDER_PROFIT")),
    ("HK", "cashflow"): (("operating_cash_flow", "AMOUNT"),),
}
_REPORT_NAMES = {
    ("A", "profit"): "stock_profit_sheet_by_report_em", ("A", "cashflow"): "stock_cash_flow_sheet_by_report_em",
    ("A", "indicator"): "stock_financial_abstract",
    ("HK", "profit"): "RPT_HKF10_FN_GMAININDICATOR", ("HK", "cashflow"): "RPT_HKSK_FN_CASHFLOW",
}
_HK_CASH_LABELS = {
    "经营活动产生的现金流量净额", "經營活動產生的現金流量淨額",
    "经营活动所用现金净额", "經營活動所用現金淨額", "经营业务现金净额", "經營業務現金淨額",
}
_CNY = {"CNY", "RMB", "人民币", "人民幣"}

def build_structured_financial_history_cache(
    *, stock_code: str, stock_name: str, market: str,
    provider_rows: dict[str, list[dict[str, Any]]], fetched_at: str = "",
) -> dict[str, Any]:
    """Normalize exact provider fields into compact annual CNY records."""
    market, provider = str(market or "").upper(), "eastmoney"
    candidates, margins, diagnostics = defaultdict(list), defaultdict(list), []
    for dataset in ("profit", "cashflow"):
        for row in provider_rows.get(dataset) or []:
            date = _report_date(row) if isinstance(row, dict) else ""
            if not _is_annual(row, date, market):
                continue
            year = int(date[:4])
            currency = "CNY" if market == "A" else _currency(row)
            if currency != "CNY":
                diagnostics.append({"code": "unsupported_reporting_currency", "report_year": year, "currency": currency or "unknown"})
                continue
            selected = _selected(row, dataset, market)
            margin = _gross_margin_cell(row, market) if dataset == "profit" else None
            if not selected and not margin:
                continue
            fields = {field: value for _, value, field in selected}
            if margin:
                fields.update(margin[1])
            if dataset == "cashflow" and market == "HK":
                fields["ITEM_NAME"] = str(row.get("ITEM_NAME") or "")
            source = {
                "dataset": dataset, "report_name": _REPORT_NAMES[(market, dataset)],
                "report_date": date, "selected_fields": dict(sorted(fields.items())),
            }
            source["row_hash"] = _sha(source)
            for metric, value, field in selected:
                candidates[(year, metric)].append((value, field, source))
            if margin:
                margins[year].append((margin[0]["value"], margin[0], source))

    if market == "A":
        for row in provider_rows.get("indicator") or []:
            if not isinstance(row, dict) or str(row.get("指标") or "").strip() != "毛利率":
                continue
            for field, raw_value in row.items():
                if not re.fullmatch(r"\d{4}1231", str(field)) or (value := _decimal(raw_value)) is None:
                    continue
                year, date = int(str(field)[:4]), f"{str(field)[:4]}-12-31"
                source = {
                    "dataset": "indicator", "report_name": _REPORT_NAMES[(market, "indicator")],
                    "report_date": date, "selected_fields": {"指标": "毛利率", str(field): format(value, "f")},
                }
                source["row_hash"] = _sha(source)
                cell = {"value": format(value, "f"), "source_field": str(field), "origin": "direct"}
                margins[year].append((cell["value"], cell, source))

    records = []
    for year in sorted({key[0] for key in candidates} | set(margins)):
        metrics, rows = {}, {}
        for metric in _METRICS:
            options = candidates.get((year, metric), [])
            if len({option[0] for option in options}) > 1:
                diagnostics.append({"code": "conflicting_period_values", "report_year": year, "metric_key": metric})
                continue
            if not options:
                diagnostics.append({"code": "missing_metric", "report_year": year, "metric_key": metric})
                continue
            preferred = dict(_FIELDS.get((market, options[0][2]["dataset"]), ())).get(metric)
            value, field, source = min(options, key=lambda option: (option[1] != preferred, option[1], option[2]["row_hash"]))
            metrics[metric] = {"value": value, "source_field": field}
            rows[source["row_hash"]] = source
        options = margins.get(year, [])
        direct = [option for option in options if option[1]["origin"] == "direct"]
        admitted = direct or options
        if len({option[0] for option in admitted}) > 1:
            diagnostics.append({"code": "conflicting_period_values", "report_year": year, "metric_key": "gross_margin"})
        elif admitted:
            _, cell, source = min(admitted, key=lambda option: (option[1]["source_field"], option[2]["row_hash"]))
            metrics["gross_margin"] = cell
            rows[source["row_hash"]] = source
        if metrics:
            records.append({
                "report_year": year, "report_date": f"{year}-12-31", "report_type": "annual",
                "currency": "CNY", "metrics": dict(sorted(metrics.items())),
                "source_rows": [rows[key] for key in sorted(rows)],
            })
    pack = {
        "schema_version": SCHEMA_VERSION, "stock_code": str(stock_code), "stock_name": str(stock_name),
        "market": market, "provider": provider, "fetched_at": fetched_at, "records": records,
        "diagnostics": sorted(diagnostics, key=lambda row: tuple(str(row.get(key) or "") for key in ("code", "report_year", "metric_key"))),
    }
    pack["data_hash"] = _data_hash(pack)
    return pack
def read_structured_financial_history_source_points(
    path: str | Path, *, expected_stock_code: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Read one verified cache and project compact MetricSeries source points."""
    try:
        pack = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return [], [], [{"code": "history_cache_unavailable"}]
    error = _pack_error(pack, expected_stock_code)
    if error:
        return [], [], [{"code": error}]
    points, ratios = [], []
    for record in pack["records"]:
        for metric, cell in sorted((record.get("metrics") or {}).items()):
            if metric == "gross_margin":
                row = _gross_margin_source(record, cell, pack["market"])
                if row:
                    year = int(record["report_year"])
                    block_id = f"{pack['provider']}:{row['dataset']}:{year}:{metric}"
                    ratios.append({
                        "source_type": SOURCE_TYPE, "fact_id": f"periodic:{pack['stock_code']}:{year}:annual:{metric}",
                        "stock_code": pack["stock_code"], "report_year": year, "report_type": "annual", "period": str(year),
                        "metric_key": metric, "currency": "CNY", "unit": "pct", "value_basis": "as_reported",
                        "numeric_value": f"{Decimal(cell['value']):.2f}", "source_doc": Path(path).name,
                        "source_block_id": block_id, "evidence_refs": [block_id], "source_excerpt_hash": _sha(cell),
                        "source_block_hash": row["row_hash"], "provider": pack["provider"], "dataset": row["dataset"],
                        "source_field": cell["source_field"], "report_date": record["report_date"],
                        "cache_data_hash": pack["data_hash"], "origin": cell["origin"],
                        **({"formula_version": cell["formula_version"], "input_fields": cell["input_fields"]}
                           if cell["origin"] == "derived" else {}),
                    })
                continue
            dataset = "cashflow" if metric == "operating_cash_flow" else "profit"
            rows = [
                row for row in record.get("source_rows") or []
                if row.get("dataset") == dataset
                and str((row.get("selected_fields") or {}).get(cell.get("source_field"))) == str(cell.get("value"))
            ]
            amount = _decimal(cell.get("value"))
            if metric not in _METRICS or len(rows) != 1 or amount is None:
                continue
            year, row = int(record["report_year"]), rows[0]
            block_id = f"{pack['provider']}:{dataset}:{year}:{metric}"
            points.append({
                "source_type": SOURCE_TYPE, "fact_id": f"periodic:{pack['stock_code']}:{year}:annual:{metric}",
                "stock_code": pack["stock_code"], "report_year": year, "report_type": "annual", "period": str(year),
                "metric_key": metric, "currency": "CNY", "unit": "万元", "value_basis": "as_reported",
                "normalized_value": f"{(amount / Decimal('10000')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}万元", "source_doc": Path(path).name,
                "source_block_id": block_id, "evidence_refs": [block_id],
                "source_excerpt_hash": _sha({"source_field": cell["source_field"], "value": cell["value"]}),
                "source_block_hash": row["row_hash"], "provider": pack["provider"], "dataset": dataset,
                "source_field": cell["source_field"], "report_date": record["report_date"],
                "cache_data_hash": pack["data_hash"],
            })
    return points, ratios, list(pack.get("diagnostics") or [])

def write_structured_financial_history_cache(path: str | Path, pack: dict[str, Any]) -> bool:
    """Atomically write a valid cache; preserve bytes when data is unchanged."""
    if _pack_error(pack, str(pack.get("stock_code") or "")):
        raise ValueError("invalid structured financial history cache")
    path = Path(path)
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        current = {}
    if current.get("data_hash") == pack.get("data_hash"):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(_canonical(pack) + "\n", encoding="utf-8")
    temporary.replace(path)
    return True

def _selected(row: dict[str, Any], dataset: str, market: str) -> list[tuple[str, str, str]]:
    if dataset == "cashflow" and market == "HK" and str(row.get("ITEM_NAME") or "") not in _HK_CASH_LABELS:
        return []
    output = _cells(row, _FIELDS.get((market, dataset), ()))
    if market == "A" and dataset == "profit" and not any(metric == "revenue" for metric, _, _ in output):
        output += _cells(row, (("revenue", "OPERATE_INCOME"),))
    return output

def _cells(row: dict[str, Any], fields: Iterable[tuple[str, str]]) -> list[tuple[str, str, str]]:
    return [(metric, format(value, "f"), field) for metric, field in fields if (value := _decimal(row.get(field))) is not None]

def _gross_margin_cell(row: dict[str, Any], market: str) -> tuple[dict[str, Any], dict[str, str]] | None:
    direct = _decimal(row.get("GROSS_PROFIT_RATIO")) if market == "HK" else None
    if direct is not None:
        value = format(direct, "f")
        return {"value": value, "source_field": "GROSS_PROFIT_RATIO", "origin": "direct"}, {"GROSS_PROFIT_RATIO": value}
    revenue_field = "OPERATE_INCOME" if market == "HK" else "TOTAL_OPERATE_INCOME"
    revenue = _decimal(row.get(revenue_field))
    if market == "A" and revenue is None:
        revenue_field, revenue = "OPERATE_INCOME", _decimal(row.get("OPERATE_INCOME"))
    if revenue is None or revenue <= 0:
        return None
    gross_profit, cost = _decimal(row.get("GROSS_PROFIT")), _decimal(row.get("OPERATE_COST"))
    if gross_profit is not None:
        numerator, inputs = gross_profit, ["GROSS_PROFIT", revenue_field]
    elif cost is not None:
        numerator, inputs = revenue - cost, ["OPERATE_COST", revenue_field]
    else:
        return None
    value = (numerator * Decimal("100") / revenue).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    cell = {"value": format(value, ".2f"), "source_field": "derived", "origin": "derived",
            "formula_version": "gross_margin.v1", "input_fields": inputs}
    return cell, {field: format(_decimal(row.get(field)), "f") for field in inputs}

def _gross_margin_source(record: dict[str, Any], cell: dict[str, Any], market: str) -> dict[str, Any] | None:
    rows = record.get("source_rows") or []
    if cell.get("origin") == "direct":
        matches = [row for row in rows if str((row.get("selected_fields") or {}).get(cell.get("source_field"))) == str(cell.get("value"))]
    elif cell.get("origin") == "derived" and cell.get("formula_version") == "gross_margin.v1":
        matches = []
        for row in rows:
            derived = _gross_margin_cell(row.get("selected_fields") or {}, market)
            if derived and derived[0] == cell:
                matches.append(row)
    else:
        matches = []
    return matches[0] if len(matches) == 1 else None

def _is_annual(row: Any, date: str, market: str) -> bool:
    if not isinstance(row, dict) or not date.endswith("-12-31"):
        return False
    marker = " ".join(str(row.get(key) or "") for key in ("REPORT_TYPE", "DATE_TYPE", "REPORT"))
    return market == "A" or "FY" in marker.upper() or any(token in marker for token in ("年报", "年報", "年度"))

def _report_date(row: dict[str, Any]) -> str:
    value = str(row.get("REPORT_DATE") or "")[:10]
    return value if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-" else ""

def _currency(row: dict[str, Any]) -> str:
    value = str(row.get("CURRENCY") or row.get("REPORT_CURRENCY") or "").strip()
    return "CNY" if value.upper() in _CNY or value in _CNY else value.upper()

def _pack_error(pack: Any, stock_code: str) -> str:
    if not isinstance(pack, dict) or pack.get("schema_version") != SCHEMA_VERSION or pack.get("provider") != "eastmoney":
        return "unsupported_history_cache_schema"
    if str(pack.get("stock_code") or "") != str(stock_code):
        return "history_cache_stock_mismatch"
    if not isinstance(pack.get("records"), list) or pack.get("data_hash") != _data_hash(pack):
        return "invalid_history_cache_hash"
    for record in pack["records"]:
        try:
            year, metrics, source_rows = int(record["report_year"]), record["metrics"], record["source_rows"]
        except (KeyError, TypeError, ValueError, AttributeError):
            return "invalid_history_cache_record"
        if (year <= 0 or record.get("report_date") != f"{year}-12-31"
                or record.get("report_type") != "annual" or record.get("currency") != "CNY"
                or not isinstance(metrics, dict) or not metrics or not isinstance(source_rows, list)
                or any(metric not in _METRICS + _OPTIONAL_METRICS or not isinstance(cell, dict) or not str(cell.get("source_field") or "")
                       or _decimal(cell.get("value")) is None or (metric == "gross_margin" and (
                           cell.get("origin") not in {"direct", "derived"} or (cell.get("origin") == "derived" and (
                               cell.get("source_field") != "derived" or cell.get("formula_version") != "gross_margin.v1"
                               or not isinstance(cell.get("input_fields"), list))))) for metric, cell in metrics.items())):
            return "invalid_history_cache_record"
        for row in source_rows:
            if not isinstance(row, dict) or not isinstance(row.get("selected_fields"), dict):
                return "invalid_history_cache_record"
            payload = {key: row.get(key) for key in ("dataset", "report_name", "report_date", "selected_fields")}
            if row.get("row_hash") != _sha(payload):
                return "invalid_history_cache_row_hash"
    return ""

def _data_hash(pack: dict[str, Any]) -> str:
    return _sha({key: pack.get(key) for key in ("stock_code", "stock_name", "market", "provider", "records")})

def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()

def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None
