"""Deterministic cross-period financial consistency findings.

The scanner consumes the typed MetricSeries pack, never source prose. It emits
compute-only findings for later evidence mapping and has no report or scoring
authority.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, Iterable, List, Tuple

if __name__.startswith("utils."):
    from .periodic_report_structured_facts import is_cashflow_quality_weak
else:
    from periodic_report_structured_facts import is_cashflow_quality_weak


FINANCIAL_SCAN_SCHEMA_VERSION = "periodic_report_financial_scan_pack.v1"
METRIC_SERIES_SCHEMA_VERSION = "periodic_report_metric_series_pack.v1"
FINANCIAL_RULE_VERSION = "financial_consistency.v1"

_FILING_METRICS = {"revenue", "net_profit", "operating_cash_flow"}
_CASH_CONVERSION_METRIC = "operating_cash_flow_to_net_profit"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_VALUE_BASIS_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_FIXED_DECIMAL_RE = re.compile(r"(?:0|[1-9]\d*|-(?:0|[1-9]\d*))\.\d{2}")
_UPSTREAM_DIAGNOSTIC_FIELDS = (
    "code", "metric_key", "source_doc", "report_year", "report_type"
)


def build_periodic_report_financial_scan_pack(
    *,
    stock_code: str,
    stock_name: str,
    metric_series_pack: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a code-only financial scan from one validated metric-series pack."""
    raw_schema = metric_series_pack.get("schema_version") if isinstance(metric_series_pack, dict) else ""
    source_schema = raw_schema if isinstance(raw_schema, str) else ""
    top_error = _top_level_error(metric_series_pack, stock_code)
    if top_error:
        return _pack(
            stock_code,
            stock_name,
            source_schema,
            "unavailable",
            diagnostics=[_diagnostic(top_error)],
        )

    diagnostics = _upstream_diagnostics(metric_series_pack.get("diagnostics") or [])
    source_rows = [
        *(metric_series_pack.get("series") or []),
        *(metric_series_pack.get("derived_series") or []),
    ]
    ids = [
        str(row.get("series_id") or "")
        for row in source_rows
        if isinstance(row, dict)
    ]
    duplicate_ids = {series_id for series_id, count in Counter(ids).items() if series_id and count > 1}
    diagnostics.extend(
        _diagnostic("duplicate_source_series_id", series_id=series_id)
        for series_id in sorted(duplicate_ids)
    )

    filing_series = []
    derived_series = []
    for row in metric_series_pack.get("series") or []:
        if isinstance(row, dict) and str(row.get("series_id") or "") in duplicate_ids:
            continue
        admitted, row_diagnostics = _admit_filing_series(row, stock_code)
        diagnostics.extend(row_diagnostics)
        if admitted:
            filing_series.append(admitted)
    for row in metric_series_pack.get("derived_series") or []:
        if isinstance(row, dict) and str(row.get("series_id") or "") in duplicate_ids:
            continue
        admitted, row_diagnostics = _admit_derived_series(row, stock_code, filing_series)
        diagnostics.extend(row_diagnostics)
        if admitted:
            derived_series.append(admitted)

    source_series_count = len(filing_series) + len(derived_series)
    source_point_count = sum(
        len(row["points"]) for row in [*filing_series, *derived_series]
    )
    intervals = {
        (
            row["report_type"],
            row["value_basis"],
            change["from_period"],
            change["to_period"],
        )
        for row in filing_series
        for change in row["changes"]
    }
    if not source_point_count:
        status = "empty"
    elif intervals or any(row["points"] for row in derived_series):
        status = "ready"
    else:
        status = "partial"

    findings, finding_diagnostics = _resolve_findings([
        *_cross_metric_findings(stock_code, filing_series),
        *_trend_findings(stock_code, filing_series),
        *_cashflow_findings(stock_code, derived_series),
    ])
    diagnostics.extend(finding_diagnostics)

    return _pack(
        stock_code,
        stock_name,
        source_schema,
        status,
        source_series_count=source_series_count,
        source_point_count=source_point_count,
        comparable_interval_count=len(intervals),
        findings=findings,
        diagnostics=diagnostics,
    )


def _pack(
    stock_code: str,
    stock_name: str,
    source_schema: str,
    status: str,
    *,
    source_series_count: int = 0,
    source_point_count: int = 0,
    comparable_interval_count: int = 0,
    findings: List[Dict[str, Any]] | None = None,
    diagnostics: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    return {
        "schema_version": FINANCIAL_SCAN_SCHEMA_VERSION,
        "stock_code": str(stock_code),
        "stock_name": str(stock_name),
        "source_schema_version": str(source_schema),
        "status": status,
        "report_eligible": False,
        "scoring_eligible": False,
        "external_mapping_eligible": True,
        "source_series_count": source_series_count,
        "source_point_count": source_point_count,
        "comparable_interval_count": comparable_interval_count,
        "findings": sorted(findings or [], key=lambda row: row["finding_id"]),
        "diagnostics": sorted(diagnostics or [], key=_diagnostic_sort_key),
    }


def _top_level_error(pack: Any, stock_code: str) -> str:
    if not isinstance(pack, dict) or pack.get("schema_version") != METRIC_SERIES_SCHEMA_VERSION:
        return "unsupported_source_schema"
    if str(pack.get("stock_code") or "") != str(stock_code):
        return "source_stock_mismatch"
    if pack.get("report_eligible") is not False or pack.get("scoring_eligible") is not False:
        return "source_eligibility_violation"
    if any(not isinstance(pack.get(key), list) for key in ("series", "derived_series", "diagnostics")):
        return "malformed_source_collections"
    return ""


def _admit_filing_series(
    row: Any,
    stock_code: str,
) -> Tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
    identity = _series_identity(row)
    if not isinstance(row, dict):
        return None, [_diagnostic("invalid_filing_series_contract")]
    metric_key = str(row.get("metric_key") or "")
    report_type = str(row.get("report_type") or "")
    value_basis = str(row.get("value_basis") or "")
    expected_id = (
        f"periodic-series:{stock_code}:{report_type}:{metric_key}:"
        f"{value_basis}:CNY:wan"
    )
    if (
        metric_key not in _FILING_METRICS
        or report_type not in {"annual", "semiannual"}
        or not _VALUE_BASIS_RE.fullmatch(value_basis)
        or row.get("currency") != "CNY"
        or row.get("unit") != "万元"
        or row.get("series_id") != expected_id
        or not isinstance(row.get("points"), list)
        or not row["points"]
        or not isinstance(row.get("changes"), list)
    ):
        return None, [_diagnostic("invalid_filing_series_contract", **identity)]

    points = []
    for point in row["points"]:
        admitted = _admit_filing_point(
            point,
            stock_code=stock_code,
            metric_key=metric_key,
            report_type=report_type,
        )
        if not admitted:
            return None, [_diagnostic("invalid_filing_point_contract", **identity)]
        points.append(admitted)
    years = [point["report_year"] for point in points]
    if years != sorted(set(years)):
        return None, [_diagnostic("invalid_filing_point_contract", **identity)]

    changes = _admit_changes(row["changes"], points)
    if changes is None:
        return None, [_diagnostic("invalid_filing_change_contract", **identity)]
    return {
        "series_id": expected_id,
        "metric_key": metric_key,
        "report_type": report_type,
        "value_basis": value_basis,
        "currency": "CNY",
        "unit": "万元",
        "points": points,
        "changes": changes,
    }, []


def _admit_filing_point(
    point: Any,
    *,
    stock_code: str,
    metric_key: str,
    report_type: str,
) -> Dict[str, Any] | None:
    if not isinstance(point, dict):
        return None
    try:
        year = int(point.get("report_year"))
    except (TypeError, ValueError):
        return None
    numeric = _fixed_decimal(point.get("numeric_value"))
    expected_ref = f"periodic:{stock_code}:{year}:{report_type}:{metric_key}"
    fact_refs = sorted({str(ref) for ref in point.get("fact_refs") or []})
    evidence = _source_evidence(point.get("source_evidence"))
    if (
        year <= 0
        or str(point.get("period") or "") != str(year)
        or numeric is None
        or fact_refs != [expected_ref]
        or evidence is None
    ):
        return None
    return {
        "period": str(year),
        "report_year": year,
        "numeric_value": str(point["numeric_value"]),
        "fact_refs": fact_refs,
        "source_evidence": evidence,
    }


def _admit_changes(
    rows: List[Any],
    points: List[Dict[str, Any]],
) -> List[Dict[str, Any]] | None:
    by_period = {point["period"]: point for point in points}
    expected_intervals = {
        (left["period"], right["period"])
        for left, right in zip(points, points[1:])
        if right["report_year"] - left["report_year"] == 1
    }
    output = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            return None
        interval = (str(row.get("from_period") or ""), str(row.get("to_period") or ""))
        if interval in seen or interval not in expected_intervals:
            return None
        left, right = (by_period.get(period) for period in interval)
        expected_refs = sorted(set(left["fact_refs"] + right["fact_refs"]))
        growth = row.get("growth_rate")
        growth_value = _fixed_decimal(growth, suffix="%") if growth not in (None, "") else None
        if (
            row.get("formula_version") != "periodic_growth.v1"
            or sorted({str(ref) for ref in row.get("input_refs") or []}) != expected_refs
            or (growth not in (None, "") and growth_value is None)
        ):
            return None
        output.append({
            "from_period": interval[0],
            "to_period": interval[1],
            "growth_rate": str(growth) if growth_value is not None else "",
            "input_refs": expected_refs,
            "formula_version": "periodic_growth.v1",
        })
        seen.add(interval)
    if seen != expected_intervals:
        return None
    return sorted(output, key=lambda row: (row["from_period"], row["to_period"]))


def _admit_derived_series(
    row: Any,
    stock_code: str,
    filing_series: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
    identity = _series_identity(row)
    if not isinstance(row, dict):
        return None, [_diagnostic("invalid_derived_series_contract")]
    report_type = str(row.get("report_type") or "")
    value_basis = str(row.get("value_basis") or "")
    expected_id = (
        f"periodic-derived-series:{stock_code}:{report_type}:"
        f"{_CASH_CONVERSION_METRIC}:{value_basis}:cash_conversion.v1:pct"
    )
    if (
        row.get("metric_key") != _CASH_CONVERSION_METRIC
        or report_type not in {"annual", "semiannual"}
        or not _VALUE_BASIS_RE.fullmatch(value_basis)
        or row.get("formula_version") != "cash_conversion.v1"
        or row.get("unit") != "pct"
        or row.get("report_eligible") is not False
        or row.get("scoring_eligible") is not False
        or row.get("series_id") != expected_id
        or not isinstance(row.get("points"), list)
        or not row["points"]
    ):
        return None, [_diagnostic("invalid_derived_series_contract", **identity)]

    filing_index = _filing_ref_index(filing_series)
    points = []
    for source in row["points"]:
        point, code = _admit_derived_point(
            source,
            stock_code=stock_code,
            report_type=report_type,
            value_basis=value_basis,
            filing_index=filing_index,
        )
        if code:
            return None, [_diagnostic(code, **identity)]
        points.append(point)
    years = [point["report_year"] for point in points]
    if years != sorted(set(years)):
        return None, [_diagnostic("invalid_derived_point_contract", **identity)]
    return {
        "series_id": expected_id,
        "metric_key": _CASH_CONVERSION_METRIC,
        "report_type": report_type,
        "value_basis": value_basis,
        "unit": "pct",
        "formula_version": "cash_conversion.v1",
        "points": points,
    }, []


def _filing_ref_index(
    filing_series: List[Dict[str, Any]],
) -> Dict[str, List[Tuple[Dict[str, Any], Dict[str, Any]]]]:
    output: Dict[str, List[Tuple[Dict[str, Any], Dict[str, Any]]]] = {}
    for series in filing_series:
        for point in series["points"]:
            for ref in point["fact_refs"]:
                output.setdefault(ref, []).append((series, point))
    return output


def _admit_derived_point(
    point: Any,
    *,
    stock_code: str,
    report_type: str,
    value_basis: str,
    filing_index: Dict[str, List[Tuple[Dict[str, Any], Dict[str, Any]]]],
) -> Tuple[Dict[str, Any] | None, str]:
    if not isinstance(point, dict):
        return None, "invalid_derived_point_contract"
    try:
        year = int(point.get("report_year"))
    except (TypeError, ValueError):
        return None, "invalid_derived_point_contract"
    numeric = _fixed_decimal(point.get("numeric_value"))
    ratio_ref = (
        f"periodic:{stock_code}:{year}:{report_type}:"
        f"{_CASH_CONVERSION_METRIC}"
    )
    expected_inputs = sorted([
        f"periodic:{stock_code}:{year}:{report_type}:net_profit",
        f"periodic:{stock_code}:{year}:{report_type}:operating_cash_flow",
    ])
    fact_refs = sorted({str(ref) for ref in point.get("fact_refs") or []})
    input_refs = sorted({str(ref) for ref in point.get("input_refs") or []})
    evidence = _source_evidence(point.get("source_evidence"))
    if (
        year <= 0
        or str(point.get("period") or "") != str(year)
        or numeric is None
        or fact_refs != [ratio_ref]
        or evidence is None
    ):
        return None, "invalid_derived_point_contract"
    if input_refs != expected_inputs:
        return None, "unresolved_derived_input_refs"
    resolved_points = []
    for ref in expected_inputs:
        matches = filing_index.get(ref) or []
        if len(matches) != 1:
            return None, "unresolved_derived_input_refs"
        series, filing_point = matches[0]
        if (
            series["report_type"] != report_type
            or series["value_basis"] != value_basis
            or filing_point["report_year"] != year
        ):
            return None, "unresolved_derived_input_refs"
        resolved_points.append(filing_point)
    if evidence != _merge_evidence(*(
        filing_point["source_evidence"] for filing_point in resolved_points
    )):
        return None, "invalid_derived_point_contract"
    return {
        "period": str(year),
        "report_year": year,
        "numeric_value": str(point["numeric_value"]),
        "value": f"{point['numeric_value']}%",
        "fact_refs": fact_refs,
        "input_refs": input_refs,
        "source_evidence": evidence,
    }, ""


def _cross_metric_findings(
    stock_code: str,
    filing_series: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_interval: Dict[Tuple[str, ...], Dict[str, Dict[str, Any]]] = {}
    for series in filing_series:
        points = {point["period"]: point for point in series["points"]}
        for change in series["changes"]:
            growth = _percentage(change["growth_rate"])
            if growth is None:
                continue
            key = (
                series["report_type"],
                series["value_basis"],
                series["currency"],
                series["unit"],
                change["from_period"],
                change["to_period"],
            )
            by_interval.setdefault(key, {})[series["metric_key"]] = {
                "growth": growth,
                "growth_rate": change["growth_rate"],
                "input_refs": change["input_refs"],
                "source_evidence": _merge_evidence(
                    points[change["from_period"]]["source_evidence"],
                    points[change["to_period"]]["source_evidence"],
                ),
            }

    findings = []
    rules = (
        (
            "revenue_growth_profit_contraction",
            "revenue",
            "net_profit",
        ),
        (
            "profit_growth_cashflow_contraction",
            "net_profit",
            "operating_cash_flow",
        ),
    )
    for key in sorted(by_interval):
        report_type, value_basis, _, _, from_period, to_period = key
        rows = by_interval[key]
        for rule_id, positive_metric, negative_metric in rules:
            positive = rows.get(positive_metric)
            negative = rows.get(negative_metric)
            if not positive or not negative:
                continue
            if positive["growth"] <= 0 or negative["growth"] >= 0:
                continue
            findings.append(_finding(
                stock_code=stock_code,
                report_type=report_type,
                value_basis=value_basis,
                periods=[from_period, to_period],
                rule_id=rule_id,
                category="cross_metric_divergence",
                direction="adverse",
                observations=[
                    _growth_observation(positive_metric, positive, from_period, to_period),
                    _growth_observation(negative_metric, negative, from_period, to_period),
                ],
                input_refs=[*positive["input_refs"], *negative["input_refs"]],
                source_evidence=_merge_evidence(
                    positive["source_evidence"], negative["source_evidence"]
                ),
            ))
    return findings


def _trend_findings(
    stock_code: str,
    filing_series: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    findings = []
    for series in filing_series:
        points = {point["period"]: point for point in series["points"]}
        for previous, current in zip(series["changes"], series["changes"][1:]):
            if previous["to_period"] != current["from_period"]:
                continue
            previous_growth = _percentage(previous["growth_rate"])
            current_growth = _percentage(current["growth_rate"])
            if previous_growth is None or current_growth is None:
                continue
            if previous_growth > 0 and current_growth < 0:
                rule_id, direction = "growth_direction_reversal", "adverse"
            elif previous_growth < 0 and current_growth > 0:
                rule_id, direction = "growth_direction_recovery", "recovery"
            else:
                continue
            periods = [
                previous["from_period"], previous["to_period"], current["to_period"]
            ]
            metric_key = series["metric_key"]
            findings.append(_finding(
                stock_code=stock_code,
                report_type=series["report_type"],
                value_basis=series["value_basis"],
                periods=periods,
                rule_id=rule_id,
                category="trend_reversal",
                direction=direction,
                observations=[
                    _growth_observation(
                        metric_key,
                        {"growth_rate": previous["growth_rate"]},
                        previous["from_period"],
                        previous["to_period"],
                    ),
                    _growth_observation(
                        metric_key,
                        {"growth_rate": current["growth_rate"]},
                        current["from_period"],
                        current["to_period"],
                    ),
                ],
                input_refs=[*previous["input_refs"], *current["input_refs"]],
                source_evidence=_merge_evidence(*(
                    points[period]["source_evidence"] for period in periods
                )),
            ))
    return findings


def _cashflow_findings(
    stock_code: str,
    derived_series: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    findings = []
    for series in derived_series:
        points = series["points"]
        weak = {
            point["period"]: is_cashflow_quality_weak(_decimal(point["numeric_value"]))
            for point in points
        }
        for point in points:
            if not weak[point["period"]]:
                continue
            findings.append(_cashflow_finding(
                stock_code,
                series,
                [point],
                "cashflow_quality_weak",
                "adverse",
            ))
        for previous, current in zip(points, points[1:]):
            if current["report_year"] - previous["report_year"] != 1:
                continue
            before = weak[previous["period"]]
            after = weak[current["period"]]
            if not before and after:
                rule_id, direction = "cashflow_quality_deteriorated", "adverse"
            elif before and not after:
                rule_id, direction = "cashflow_quality_recovered", "recovery"
            else:
                continue
            findings.append(_cashflow_finding(
                stock_code,
                series,
                [previous, current],
                rule_id,
                direction,
            ))
    return findings


def _cashflow_finding(
    stock_code: str,
    series: Dict[str, Any],
    points: List[Dict[str, Any]],
    rule_id: str,
    direction: str,
) -> Dict[str, Any]:
    return _finding(
        stock_code=stock_code,
        report_type=series["report_type"],
        value_basis=series["value_basis"],
        periods=[point["period"] for point in points],
        rule_id=rule_id,
        category="cashflow_quality",
        direction=direction,
        observations=[{
            "metric_key": _CASH_CONVERSION_METRIC,
            "value_kind": "ratio",
            "period": point["period"],
            "value": point["value"],
        } for point in points],
        input_refs=[
            ref for point in points for ref in [*point["fact_refs"], *point["input_refs"]]
        ],
        source_evidence=_merge_evidence(*(
            point["source_evidence"] for point in points
        )),
    )


def _resolve_findings(
    rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["finding_id"], []).append(row)
    findings = []
    diagnostics = []
    for finding_id in sorted(grouped):
        candidates = grouped[finding_id]
        if any(candidate != candidates[0] for candidate in candidates[1:]):
            diagnostics.append(_diagnostic(
                "conflicting_finding_identity",
                finding_id=finding_id,
            ))
        else:
            findings.append(candidates[0])
    return findings, diagnostics


def _growth_observation(
    metric_key: str,
    row: Dict[str, Any],
    from_period: str,
    to_period: str,
) -> Dict[str, str]:
    return {
        "metric_key": metric_key,
        "value_kind": "growth_rate",
        "from_period": from_period,
        "to_period": to_period,
        "value": row["growth_rate"],
    }


def _finding(
    *,
    stock_code: str,
    report_type: str,
    value_basis: str,
    periods: List[str],
    rule_id: str,
    category: str,
    direction: str,
    observations: List[Dict[str, str]],
    input_refs: Iterable[str],
    source_evidence: List[Dict[str, str]],
) -> Dict[str, Any]:
    metric_keys = sorted({row["metric_key"] for row in observations})
    period_token = "-".join(periods)
    return {
        "finding_id": (
            f"periodic-financial:{stock_code}:{report_type}:{value_basis}:"
            f"{period_token}:{rule_id}:{'+'.join(metric_keys)}"
        ),
        "rule_id": rule_id,
        "rule_version": FINANCIAL_RULE_VERSION,
        "category": category,
        "direction": direction,
        "report_type": report_type,
        "value_basis": value_basis,
        "periods": list(periods),
        "metric_keys": metric_keys,
        "observations": sorted(
            observations,
            key=lambda row: (
                row["metric_key"], row.get("from_period", ""),
                row.get("to_period", ""), row.get("period", ""),
            ),
        ),
        "input_refs": sorted({str(ref) for ref in input_refs}),
        "source_evidence": source_evidence,
        "report_eligible": False,
        "scoring_eligible": False,
        "external_mapping_eligible": True,
    }


def _merge_evidence(*groups: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    keyed = {
        (
            row["source_doc"],
            row["source_block_id"],
            row["source_excerpt_hash"],
            row["source_block_hash"],
        ): row
        for group in groups
        for row in group
    }
    return [keyed[key] for key in sorted(keyed)]


def _source_evidence(value: Any) -> List[Dict[str, str]] | None:
    if not isinstance(value, list) or not value:
        return None
    keyed = {}
    for row in value:
        if not isinstance(row, dict):
            return None
        source_doc = str(row.get("source_doc") or "")
        block_id = str(row.get("source_block_id") or "")
        excerpt_hash = str(row.get("source_excerpt_hash") or "")
        block_hash = str(row.get("source_block_hash") or "")
        if (
            not source_doc
            or not block_id
            or not _SHA256_RE.fullmatch(excerpt_hash)
            or not _SHA256_RE.fullmatch(block_hash)
        ):
            return None
        key = (source_doc, block_id, excerpt_hash, block_hash)
        keyed[key] = {
            "source_doc": source_doc,
            "source_block_id": block_id,
            "source_excerpt_hash": excerpt_hash,
            "source_block_hash": block_hash,
        }
    return [keyed[key] for key in sorted(keyed)]


def _decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _fixed_decimal(value: Any, *, suffix: str = "") -> Decimal | None:
    if not isinstance(value, str):
        return None
    text = value[:-len(suffix)] if suffix and value.endswith(suffix) else value
    if suffix and not value.endswith(suffix):
        return None
    if not _FIXED_DECIMAL_RE.fullmatch(text):
        return None
    result = _decimal(text)
    return None if result == 0 and text.startswith("-") else result


def _percentage(value: Any) -> Decimal | None:
    text = str(value or "")
    return _decimal(text[:-1]) if text.endswith("%") else None


def _upstream_diagnostics(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    output = []
    for source in rows:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("code"), str)
            or not source["code"]
        ):
            continue
        row = {"origin": "metric_series"}
        row.update({
            key: source[key]
            for key in _UPSTREAM_DIAGNOSTIC_FIELDS
            if _is_diagnostic_scalar(source.get(key))
            and source.get(key) not in (None, "")
        })
        output.append(row)
    return output


def _series_identity(row: Any) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {
        key: row[key]
        for key in ("series_id", "metric_key", "report_type", "value_basis")
        if _is_diagnostic_scalar(row.get(key)) and row.get(key) not in (None, "")
    }


def _diagnostic(code: str, **identity: Any) -> Dict[str, Any]:
    return {
        "code": code,
        "origin": "financial_scan",
        **{
            key: value
            for key, value in identity.items()
            if _is_diagnostic_scalar(value) and value not in (None, "")
        },
    }


def _is_diagnostic_scalar(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (str, int))


def _diagnostic_sort_key(row: Dict[str, Any]) -> Tuple[str, ...]:
    return tuple(str(row.get(key) or "") for key in (
        "origin", "code", "series_id", "report_type", "value_basis",
        "metric_key", "report_year", "from_period", "to_period", "source_doc",
    ))
