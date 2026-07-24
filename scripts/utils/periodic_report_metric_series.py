"""Auditable cross-period series assembled from exact filing facts.

This module never extracts source text. It accepts the existing structured-fact
pack, keeps compact evidence identities, and produces compute-only histories.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Dict, Iterable, List, Tuple


METRIC_SERIES_SCHEMA_VERSION = "periodic_report_metric_series_pack.v1"
STRUCTURED_FACT_SCHEMA_VERSION = "periodic_report_structured_fact.v1"
GROWTH_FORMULA_VERSION = "periodic_growth.v1"

_FILING_SOURCE_TYPE = "periodic_report_filing_fact"
_DERIVED_SOURCE_TYPE = "periodic_report_derived_fact"
_ALLOWED_METRICS = {"revenue", "net_profit", "operating_cash_flow"}
_CASH_CONVERSION_METRIC = "operating_cash_flow_to_net_profit"
_CASH_CONVERSION_FORMULA = "cash_conversion.v1"
_TWO_PLACES = Decimal("0.01")


def build_periodic_report_metric_series_pack(
    *,
    stock_code: str,
    stock_name: str,
    fact_packs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build deterministic filing and derived metric histories."""
    diagnostics: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []
    rejected_count = 0
    valid_packs: List[Dict[str, Any]] = []

    for pack in fact_packs or []:
        code = _fact_pack_error(pack, stock_code)
        if code:
            diagnostics.append(_diagnostic(code, pack=pack))
            continue
        valid_packs.append(pack)

    for pack in valid_packs:
        for fact in pack.get("filing_facts") or []:
            row, code = _validated_filing_row(fact, pack, stock_code)
            if code:
                rejected_count += 1
                diagnostics.append(_diagnostic(code, fact=fact, pack=pack))
            elif row:
                rows.append(row)
        diagnostics.extend(_input_pack_diagnostics(pack))

    grouped: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["series_key"]].append(row)

    series = [
        _build_filing_series(stock_code, key, grouped[key], diagnostics)
        for key in sorted(grouped)
    ]
    series = [row for row in series if row["points"]]
    accepted_points = _filing_point_index(series)
    derived_rows: List[Dict[str, Any]] = []
    for pack in valid_packs:
        for fact in pack.get("derived_facts") or []:
            row, code = _validated_derived_row(fact, pack, stock_code, accepted_points)
            if code:
                diagnostics.append(_diagnostic(code, fact=fact, pack=pack))
            elif row:
                derived_rows.append(row)

    return {
        "schema_version": METRIC_SERIES_SCHEMA_VERSION,
        "stock_code": str(stock_code),
        "stock_name": str(stock_name),
        "report_eligible": False,
        "scoring_eligible": False,
        "source_pack_count": len(fact_packs or []),
        "accepted_fact_count": len(rows),
        "rejected_fact_count": rejected_count,
        "series": sorted(series, key=lambda row: row["series_id"]),
        "derived_series": _build_derived_series(stock_code, derived_rows, diagnostics),
        "diagnostics": sorted(diagnostics, key=_diagnostic_sort_key),
    }


def _validated_filing_row(
    fact: Any,
    pack: Dict[str, Any],
    stock_code: str,
) -> Tuple[Dict[str, Any] | None, str]:
    if not isinstance(fact, dict):
        return None, "malformed_filing_fact"
    if fact.get("schema_version") != STRUCTURED_FACT_SCHEMA_VERSION:
        return None, "unsupported_filing_fact_schema"
    if fact.get("source_type") != _FILING_SOURCE_TYPE:
        return None, "unsupported_fact_source_type"
    if str(pack.get("stock_code") or "") != str(stock_code) or str(fact.get("stock_code") or "") != str(stock_code):
        return None, "stock_code_mismatch"
    metric_key = str(fact.get("metric_key") or "")
    if metric_key not in _ALLOWED_METRICS:
        return None, "unsupported_metric_key"
    report_type = str(fact.get("report_type") or "")
    if report_type not in {"annual", "semiannual"}:
        return None, "unsupported_report_type"
    try:
        report_year = int(fact.get("report_year"))
    except (TypeError, ValueError):
        return None, "invalid_report_year"
    if report_year <= 0 or str(fact.get("period") or "") != str(report_year):
        return None, "period_mismatch"
    if report_year != int(pack.get("report_year")) or report_type != str(pack.get("report_type") or ""):
        return None, "fact_pack_period_mismatch"
    expected_fact_id = f"periodic:{stock_code}:{report_year}:{report_type}:{metric_key}"
    if str(fact.get("fact_id") or "") != expected_fact_id:
        return None, "fact_id_mismatch"
    if str(fact.get("currency") or "") != "CNY" or str(fact.get("unit") or "") != "万元":
        return None, "incompatible_fact_dimensions"
    value_basis = str(fact.get("value_basis") or "")
    if not value_basis:
        return None, "missing_value_basis"
    numeric = _amount_in_wan(str(fact.get("normalized_value") or ""))
    if numeric is None:
        return None, "invalid_normalized_value"
    source_doc = str(fact.get("source_doc") or "")
    if not source_doc or source_doc != str(pack.get("source_doc") or ""):
        return None, "source_doc_mismatch"
    if not _valid_sha256(fact.get("source_excerpt_hash")) or not _valid_sha256(fact.get("source_block_hash")):
        return None, "invalid_source_hash"
    evidence = _source_evidence(fact, source_doc)
    if not evidence:
        return None, "incomplete_source_evidence"
    series_key = (
        report_type,
        metric_key,
        value_basis,
        "CNY",
        "万元",
    )
    return {
        "series_key": series_key,
        "fact_id": str(fact.get("fact_id") or ""),
        "report_year": report_year,
        "period": str(report_year),
        "numeric": numeric,
        "source_evidence": evidence,
        "evidence_refs": sorted({str(ref) for ref in fact.get("evidence_refs") or []}),
    }, ""


def _build_filing_series(
    stock_code: str,
    key: Tuple[str, ...],
    rows: List[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    report_type, metric_key, value_basis, currency, unit = key
    by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_year[row["report_year"]].append(row)

    points = []
    for year in sorted(by_year):
        year_rows = by_year[year]
        values = {row["numeric"] for row in year_rows}
        if len(values) != 1:
            diagnostics.append({
                "code": "conflicting_period_values",
                "metric_key": metric_key,
                "report_year": year,
                "report_type": report_type,
            })
            continue
        numeric = year_rows[0]["numeric"]
        point = {
            "period": str(year),
            "report_year": year,
            "numeric_value": _decimal_text(numeric),
            "normalized_value": f"{_decimal_text(numeric)}万元",
            "fact_refs": sorted({row["fact_id"] for row in year_rows}),
            "evidence_refs": sorted({ref for row in year_rows for ref in row["evidence_refs"]}),
            "source_evidence": _unique_evidence(
                evidence
                for row in year_rows
                for evidence in row["source_evidence"]
            ),
        }
        points.append(point)

    return {
        "series_id": _series_id(stock_code, report_type, metric_key, value_basis, currency, unit),
        "metric_key": metric_key,
        "report_type": report_type,
        "value_basis": value_basis,
        "currency": currency,
        "unit": unit,
        "points": points,
        "changes": _build_changes(points, diagnostics, metric_key, report_type),
    }


def _filing_point_index(
    series: List[Dict[str, Any]],
) -> Dict[Tuple[str, int, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, int, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in series:
        for point in row["points"]:
            index[(row["report_type"], point["report_year"], row["metric_key"])].append(point)
    return index


def _validated_derived_row(
    fact: Any,
    pack: Dict[str, Any],
    stock_code: str,
    accepted_points: Dict[Tuple[str, int, str], List[Dict[str, Any]]],
) -> Tuple[Dict[str, Any] | None, str]:
    if not isinstance(fact, dict):
        return None, "malformed_derived_fact"
    if fact.get("schema_version") != STRUCTURED_FACT_SCHEMA_VERSION:
        return None, "unsupported_derived_fact_schema"
    if fact.get("source_type") != _DERIVED_SOURCE_TYPE:
        return None, "unsupported_derived_source_type"
    if str(fact.get("stock_code") or "") != str(stock_code):
        return None, "stock_code_mismatch"
    if fact.get("metric_key") != _CASH_CONVERSION_METRIC:
        return None, "unsupported_derived_metric_key"
    if fact.get("formula_version") != _CASH_CONVERSION_FORMULA or fact.get("unit") != "pct":
        return None, "unsupported_derived_formula"
    report_type = str(fact.get("report_type") or "")
    if report_type not in {"annual", "semiannual"}:
        return None, "unsupported_report_type"
    try:
        report_year = int(fact.get("report_year"))
    except (TypeError, ValueError):
        return None, "invalid_report_year"
    if report_year <= 0 or str(fact.get("period") or "") != str(report_year):
        return None, "period_mismatch"
    if report_year != int(pack.get("report_year")) or report_type != str(pack.get("report_type") or ""):
        return None, "fact_pack_period_mismatch"
    if str(fact.get("source_doc") or "") != str(pack.get("source_doc") or ""):
        return None, "source_doc_mismatch"
    expected_fact_id = f"periodic:{stock_code}:{report_year}:{report_type}:{_CASH_CONVERSION_METRIC}"
    if str(fact.get("fact_id") or "") != expected_fact_id:
        return None, "fact_id_mismatch"
    numeric = _percentage_value(str(fact.get("signed_value") or fact.get("value") or ""))
    if numeric is None:
        return None, "invalid_derived_value"

    expected_refs = {
        f"periodic:{stock_code}:{report_year}:{report_type}:net_profit",
        f"periodic:{stock_code}:{report_year}:{report_type}:operating_cash_flow",
    }
    input_refs = {str(ref) for ref in fact.get("input_refs") or []}
    point_groups = [
        accepted_points.get((report_type, report_year, metric_key), [])
        for metric_key in ("net_profit", "operating_cash_flow")
    ]
    if input_refs != expected_refs or any(len(group) != 1 for group in point_groups):
        return None, "derived_input_not_accepted"
    points = [group[0] for group in point_groups]
    for metric_key, point in zip(("net_profit", "operating_cash_flow"), points):
        expected_ref = f"periodic:{stock_code}:{report_year}:{report_type}:{metric_key}"
        if expected_ref not in point["fact_refs"]:
            return None, "derived_input_not_accepted"

    return {
        "report_type": report_type,
        "report_year": report_year,
        "period": str(report_year),
        "numeric": numeric,
        "fact_id": str(fact.get("fact_id") or ""),
        "input_refs": sorted(input_refs),
        "source_evidence": _unique_evidence(
            evidence
            for point in points
            if point
            for evidence in point["source_evidence"]
        ),
    }, ""


def _build_derived_series(
    stock_code: str,
    rows: List[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_type[row["report_type"]].append(row)
    output = []
    for report_type in sorted(by_type):
        by_year: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for row in by_type[report_type]:
            by_year[row["report_year"]].append(row)
        points = []
        for year in sorted(by_year):
            year_rows = by_year[year]
            values = {row["numeric"] for row in year_rows}
            if len(values) != 1:
                diagnostics.append({
                    "code": "conflicting_derived_period_values",
                    "metric_key": _CASH_CONVERSION_METRIC,
                    "report_year": year,
                    "report_type": report_type,
                })
                continue
            numeric = year_rows[0]["numeric"]
            points.append({
                "period": str(year),
                "report_year": year,
                "numeric_value": _decimal_text(numeric),
                "value": f"{_decimal_text(numeric)}%",
                "fact_refs": sorted({row["fact_id"] for row in year_rows}),
                "input_refs": sorted({ref for row in year_rows for ref in row["input_refs"]}),
                "source_evidence": _unique_evidence(
                    evidence
                    for row in year_rows
                    for evidence in row["source_evidence"]
                ),
            })
        if points:
            output.append({
                "series_id": (
                    f"periodic-derived-series:{stock_code}:{report_type}:"
                    f"{_CASH_CONVERSION_METRIC}:{_CASH_CONVERSION_FORMULA}:pct"
                ),
                "metric_key": _CASH_CONVERSION_METRIC,
                "report_type": report_type,
                "unit": "pct",
                "formula_version": _CASH_CONVERSION_FORMULA,
                "report_eligible": False,
                "scoring_eligible": False,
                "points": points,
            })
    return output


def _build_changes(
    points: List[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
    metric_key: str,
    report_type: str,
) -> List[Dict[str, Any]]:
    changes = []
    for previous, current in zip(points, points[1:]):
        if current["report_year"] - previous["report_year"] != 1:
            diagnostics.append({
                "code": "non_consecutive_period_gap",
                "metric_key": metric_key,
                "report_year": current["report_year"],
                "report_type": report_type,
            })
            continue
        previous_value = Decimal(previous["numeric_value"])
        current_value = Decimal(current["numeric_value"])
        change = {
            "from_period": previous["period"],
            "to_period": current["period"],
            "absolute_change": f"{_decimal_text(current_value - previous_value)}万元",
            "input_refs": sorted(set(previous["fact_refs"] + current["fact_refs"])),
            "formula_version": GROWTH_FORMULA_VERSION,
        }
        if previous_value > 0:
            growth = (current_value - previous_value) / previous_value * Decimal("100")
            change["growth_rate"] = f"{_decimal_text(growth)}%"
        else:
            diagnostics.append({
                "code": "non_positive_growth_base",
                "metric_key": metric_key,
                "report_year": current["report_year"],
                "report_type": report_type,
            })
        changes.append(change)
    return changes


def _source_evidence(fact: Dict[str, Any], source_doc: str) -> List[Dict[str, str]]:
    block_id = str(fact.get("source_block_id") or "")
    excerpt_hash = str(fact.get("source_excerpt_hash") or "")
    block_hash = str(fact.get("source_block_hash") or "")
    refs = {str(ref) for ref in fact.get("evidence_refs") or []}
    if not source_doc or not block_id or block_id not in refs or not excerpt_hash or not block_hash:
        return []
    return [{
        "source_doc": source_doc,
        "source_block_id": block_id,
        "source_excerpt_hash": excerpt_hash,
        "source_block_hash": block_hash,
    }]


def _valid_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _unique_evidence(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    keyed = {
        (
            row["source_doc"],
            row["source_block_id"],
            row["source_excerpt_hash"],
            row["source_block_hash"],
        ): row
        for row in rows
    }
    return [keyed[key] for key in sorted(keyed)]


def _amount_in_wan(value: str) -> Decimal | None:
    value = str(value or "").strip()
    number = value[:-2] if value.endswith("万元") else ""
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", number):
        return None
    try:
        result = Decimal(number)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _percentage_value(value: str) -> Decimal | None:
    value = str(value or "").strip()
    number = value[:-1] if value.endswith("%") else ""
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", number):
        return None
    try:
        result = Decimal(number)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _decimal_text(value: Decimal) -> str:
    value = value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    return "0.00" if value == Decimal("-0.00") else f"{value:.2f}"


def _series_id(
    stock_code: str,
    report_type: str,
    metric_key: str,
    value_basis: str,
    currency: str,
    unit: str,
) -> str:
    unit_token = "wan" if unit == "万元" else unit
    return f"periodic-series:{stock_code}:{report_type}:{metric_key}:{value_basis}:{currency}:{unit_token}"


def _fact_pack_error(pack: Any, stock_code: str) -> str:
    if not isinstance(pack, dict):
        return "malformed_fact_pack"
    if pack.get("schema_version") != STRUCTURED_FACT_SCHEMA_VERSION:
        return "unsupported_fact_pack_schema"
    if str(pack.get("stock_code") or "") != str(stock_code):
        return "fact_pack_stock_mismatch"
    if str(pack.get("report_type") or "") not in {"annual", "semiannual"}:
        return "unsupported_report_type"
    try:
        if int(pack.get("report_year")) <= 0:
            return "invalid_report_year"
    except (TypeError, ValueError):
        return "invalid_report_year"
    if not str(pack.get("source_doc") or ""):
        return "source_doc_missing"
    return ""


def _diagnostic(code: str, *, fact: Any = None, pack: Any = None) -> Dict[str, Any]:
    fact = fact if isinstance(fact, dict) else {}
    pack = pack if isinstance(pack, dict) else {}
    row = {"code": code}
    for key, value in (
        ("metric_key", fact.get("metric_key")),
        ("source_doc", fact.get("source_doc") or pack.get("source_doc")),
        ("report_year", fact.get("report_year") or pack.get("report_year")),
        ("report_type", fact.get("report_type") or pack.get("report_type")),
    ):
        if value not in (None, ""):
            row[key] = value
    return row


def _input_pack_diagnostics(pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    output = []
    for source in pack.get("diagnostics") or []:
        if not isinstance(source, dict) or not source.get("code"):
            continue
        row = {
            "code": str(source["code"]),
            "source_doc": str(pack.get("source_doc") or ""),
            "report_year": pack.get("report_year"),
            "report_type": str(pack.get("report_type") or ""),
        }
        if source.get("metric_key"):
            row["metric_key"] = str(source["metric_key"])
        output.append({key: value for key, value in row.items() if value not in (None, "")})
    return output


def _diagnostic_sort_key(row: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return tuple(str(row.get(key) or "") for key in (
        "code", "report_type", "report_year", "metric_key", "source_doc"
    ))
