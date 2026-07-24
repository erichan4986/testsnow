"""Code-only compatibility map between external evidence and filing metrics."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any, Dict, Iterable, Mapping, Tuple

if __name__.startswith("utils."):
    from .periodic_report_financial_scan import (
        FINANCIAL_SCAN_SCHEMA_VERSION,
        build_periodic_report_financial_scan_pack,
        read_periodic_financial_scan_source,
    )
else:
    from periodic_report_financial_scan import (
        FINANCIAL_SCAN_SCHEMA_VERSION,
        build_periodic_report_financial_scan_pack,
        read_periodic_financial_scan_source,
    )


SCHEMA_VERSION = "periodic_external_evidence_map.v1"
EXTERNAL_TAXONOMY_VERSION = "external_argument.v4"
_CARD_SCHEMA = "curated_external_argument_card.v4"
_UNIT_SCHEMA = "curated_external_evidence_unit.v2"
_METRIC_ALIASES = {
    "revenue": (
        "来自客户合同的收入", "來自客戶合同的收入", "营业收入", "營業收入", "营收",
    ),
    "net_profit": (
        "归属于上市公司股东的净利润", "歸屬於本公司股東的利潤", "归母净利润",
    ),
    "operating_cash_flow": (
        "经营活动产生的现金流量净额", "經營活動產生的現金流量淨額",
        "经营现金流量净额", "經營現金流量淨額", "经营现金流", "經營現金流",
    ),
}
_ALIAS_TO_METRIC = {
    alias: metric for metric, aliases in _METRIC_ALIASES.items() for alias in aliases
}
_METRIC_RE = re.compile("|".join(map(re.escape, sorted(_ALIAS_TO_METRIC, key=len, reverse=True))))
_NUMBER = r"-?[\d,]+(?:\.\d+)?"
_AMOUNT_RANGE_RE = re.compile(
    rf"(?P<low>{_NUMBER})\s*(?P<unit1>亿元|萬元|万元)?\s*"
    rf"(?:至|到|[-—~～])\s*(?P<high>{_NUMBER})\s*(?P<unit2>亿元|萬元|万元)"
)
_AMOUNT_SCALAR_RE = re.compile(rf"(?P<value>{_NUMBER})\s*(?P<unit>亿元|萬元|万元)")
_RATE_RANGE_RE = re.compile(
    rf"(?P<low>{_NUMBER})\s*(?P<unit1>%)?\s*(?:至|到|[-—~～])\s*"
    rf"(?P<high>{_NUMBER})\s*(?P<unit2>%)"
)
_RATE_SCALAR_RE = re.compile(rf"(?P<value>{_NUMBER})\s*%")
_HALF_RE = re.compile(r"(?P<year>20\d{2})(?:年)?(?:上半年|半年度|H1)", re.I)
_ANNUAL_RE = re.compile(r"(?P<year>20\d{2})年(?:全年|年度|年报)")
_BARE_YEAR_RE = re.compile(r"(?P<year>20\d{2})年")
_NON_ANNUAL_PERIOD_RE = re.compile(r"(?:\d{1,2}月|\d{1,2}日|季度|前三季度|Q[1-4])", re.I)
_FORECAST_RE = re.compile(r"预计|預計|预告|預告|预测|預測|指引|有望")
_REPORTED_RE = re.compile(r"实际|實際|已实现|已實現|报告期内实现|報告期內實現|实现|實現")
_CLAUSE_BOUNDARY_RE = re.compile(r"[。；;！？!?]")
_DECLINE_RE = re.compile(r"下降|减少|減少|下滑|降低")
_LOSS_RE = re.compile(r"亏损|虧損")
_FOREIGN_CURRENCY_RE = re.compile(r"港元|美元|美金|HKD|USD", re.I)
_SHA_RE = re.compile(r"sha256:[0-9a-f]{64}")

def build_periodic_external_evidence_map(
    *, stock_code: str, stock_name: str, metric_series_pack: Dict[str, Any],
    financial_scan_pack: Dict[str, Any], validated_external_display: Dict[str, Any],
) -> Dict[str, Any]:
    """Build deterministic typed observations and compatibility mappings."""
    source = read_periodic_financial_scan_source(stock_code=stock_code, metric_series_pack=metric_series_pack)
    if source["status"] != "ok":
        return _pack(stock_code, stock_name, source=source, status="unavailable", diagnostics=[{"code": "metric_series_unavailable"}])
    expected_scan = build_periodic_report_financial_scan_pack(stock_code=stock_code, stock_name=stock_name, metric_series_pack=metric_series_pack)
    if financial_scan_pack != expected_scan:
        return _pack(stock_code, stock_name, source=source, status="unavailable", diagnostics=[{"code": "financial_scan_mismatch"}])
    display_error = _display_error(validated_external_display, stock_name)
    if display_error:
        return _pack(stock_code, stock_name, source=source, status="unavailable", diagnostics=[{"code": display_error}])

    cards = validated_external_display.get("_curated_external_argument_cards") or []
    citations = _citations(validated_external_display.get("citations"))
    target_cards = [card for card in cards if card.get("entity_scope") == "target"]
    target_units = [unit for card in target_cards for unit in card.get("evidence_units") or []]
    financial_cards = [card for card in target_cards if "financial_quality" in (card.get("coverage_families") or [])]
    financial_units = [unit for card in financial_cards for unit in card.get("evidence_units") or []]
    observations, unmapped, diagnostics = [], [], []
    for card in sorted(financial_cards, key=lambda row: str(row.get("card_id") or "")):
        found, missing, issues = _card_observations(card, citations)
        observations.extend(found)
        unmapped.extend(missing)
        diagnostics.extend(issues)
    observations, collision_diagnostics = _resolve_identities(observations, "observation_id")
    diagnostics.extend(collision_diagnostics)
    mappings, relation_unmapped = _build_mappings(observations, source["filing_series"], financial_scan_pack)
    unmapped.extend(relation_unmapped)
    mappings, collision_diagnostics = _resolve_identities(mappings, "mapping_id")
    diagnostics.extend(collision_diagnostics)
    status = "empty" if not financial_units else ("ready" if mappings else "partial")
    return _pack(stock_code, stock_name, source=source, status=status,
        target_unit_count=len(target_units),
        target_financial_unit_count=len(financial_units),
        observations=observations, mappings=mappings, unmapped=unmapped,
        diagnostics=diagnostics)

def _pack(
    stock_code: str,
    stock_name: str,
    *,
    source: Mapping[str, Any],
    status: str,
    target_unit_count: int = 0,
    target_financial_unit_count: int = 0,
    observations: Iterable[dict] = (),
    mappings: Iterable[dict] = (),
    unmapped: Iterable[dict] = (),
    diagnostics: Iterable[dict] = (),
) -> Dict[str, Any]:
    observation_rows = sorted(observations, key=lambda row: row["observation_id"])
    mapping_rows = sorted(mappings, key=lambda row: row["mapping_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "stock_code": str(stock_code),
        "stock_name": str(stock_name),
        "metric_series_schema_version": str(source.get("source_schema_version") or ""),
        "financial_scan_schema_version": FINANCIAL_SCAN_SCHEMA_VERSION,
        "external_taxonomy_version": EXTERNAL_TAXONOMY_VERSION,
        "status": status,
        "report_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "target_unit_count": target_unit_count,
        "target_financial_unit_count": target_financial_unit_count,
        "typed_observation_count": len(observation_rows),
        "mapping_count": len(mapping_rows),
        "finding_link_count": len({
            (row["mapping_id"], finding_id)
            for row in mapping_rows for finding_id in row.get("linked_finding_ids") or []
        }),
        "observations": observation_rows,
        "mappings": mapping_rows,
        "unmapped_observations": sorted(
            unmapped, key=lambda row: (row.get("observation_id", ""), row.get("unit_id", ""), row["reason"]),
        ),
        "diagnostics": sorted(
            _unique_rows(diagnostics), key=lambda row: (row.get("code", ""), row.get("unit_id", "")),
        ),
    }

def _display_error(display: Any, stock_name: str) -> str:
    if not isinstance(display, Mapping) or display.get("_curated_external_taxonomy_version") != EXTERNAL_TAXONOMY_VERSION:
        return "external_display_invalid"
    cards, citations = display.get("_curated_external_argument_cards"), _citations(display.get("citations"))
    if not isinstance(cards, list) or not isinstance(display.get("citations"), Mapping):
        return "external_display_invalid"
    unit_ids = set()
    for card in cards:
        if not isinstance(card, Mapping) or card.get("schema_version") != _CARD_SCHEMA:
            return "external_display_invalid"
        scope = card.get("entity_scope")
        if scope not in {"target", "target_with_peer_context", "peer_or_industry"}:
            return "external_display_invalid"
        if scope != "peer_or_industry" and card.get("target_entity") != stock_name:
            return "external_display_invalid"
        for unit in card.get("evidence_units") or []:
            if not _valid_unit(unit) or any(ref not in citations for ref in unit.get("citation_refs") or []):
                return "external_display_invalid"
            if unit["unit_id"] in unit_ids:
                return "external_display_duplicate_unit_id"
            unit_ids.add(unit["unit_id"])
    return ""

def _valid_unit(unit: Any) -> bool:
    return bool(
        isinstance(unit, Mapping)
        and unit.get("schema_version") == _UNIT_SCHEMA
        and isinstance(unit.get("text"), str)
        and unit.get("unit_id")
        and unit.get("source_id")
        and unit.get("block_id")
        and _SHA_RE.fullmatch(str(unit.get("document_hash") or ""))
        and _SHA_RE.fullmatch(str(unit.get("unit_hash") or ""))
    )

def _card_observations(card: Mapping[str, Any], citations: Mapping[int, dict]) -> Tuple[list, list, list]:
    observations, unmapped, diagnostics = [], [], []
    period: Tuple[int, str, str] | None = None
    modality: Tuple[str, str] = ("reported", "")
    context_key: Tuple[str, str, str] | None = None
    units = sorted(card.get("evidence_units") or [], key=lambda row: (
        int(row.get("block_ordinal") or 0), int(row.get("unit_ordinal") or 0), str(row.get("unit_id") or ""),
    ))
    for unit in units:
        text, unit_id = str(unit.get("text") or ""), str(unit.get("unit_id") or "")
        unit_context = tuple(str(unit.get(key) or "") for key in ("source_id", "document_hash", "block_id"))
        if unit_context != context_key:
            period, modality, context_key = None, ("reported", ""), unit_context
        explicit_period = _report_period(text)
        if explicit_period:
            period = (*explicit_period, unit_id)
        explicit_modality = _explicit_modality(text)
        if explicit_modality:
            modality = (explicit_modality, unit_id)
        for ordinal, (metric_key, clause) in enumerate(_metric_clauses(text)):
            candidates = [
                ("amount", _numeric_candidate(clause, amount=True)),
                ("growth_rate", _growth_candidate(clause)),
            ]
            for kind_ordinal, (value_kind, candidate) in enumerate(candidates):
                if candidate is None:
                    continue
                provisional_id = _observation_id(
                    unit_id, metric_key, value_kind, period, modality[0], candidate, ordinal * 2 + kind_ordinal,
                )
                if candidate.get("error"):
                    row = _unmapped(provisional_id, unit_id, metric_key, value_kind, period, candidate["error"])
                    unmapped.append(row)
                    diagnostics.append({"code": candidate["error"], "unit_id": unit_id})
                    continue
                if period is None:
                    row = _unmapped(provisional_id, unit_id, metric_key, value_kind, None, "period_missing")
                    unmapped.append(row)
                    diagnostics.append({"code": "period_missing", "unit_id": unit_id})
                    continue
                observations.append({
                    "observation_id": provisional_id,
                    "metric_key": metric_key,
                    "value_kind": value_kind,
                    "report_year": period[0],
                    "report_type": period[1],
                    "period_origin": "explicit_unit" if period[2] == unit_id else "card_context",
                    "period_anchor_unit_id": period[2],
                    "modality": modality[0],
                    "modality_anchor_unit_id": modality[1],
                    **{key: candidate[key] for key in (
                        "lower_value", "upper_value", "precision", "unit", "is_range",
                    )},
                    "external_evidence": [_external_evidence(unit, citations)],
                })
    return observations, unmapped, diagnostics

def _report_period(text: str) -> Tuple[int, str] | None:
    matches = [
        *( (match.start(), int(match.group("year")), "semiannual") for match in _HALF_RE.finditer(text) ),
        *( (match.start(), int(match.group("year")), "annual") for match in _ANNUAL_RE.finditer(text) ),
    ]
    if matches:
        _, year, report_type = max(matches)
        return year, report_type
    if _NON_ANNUAL_PERIOD_RE.search(text):
        return None
    years = list(_BARE_YEAR_RE.finditer(text))
    return (int(years[-1].group("year")), "annual") if years else None

def _metric_clauses(text: str) -> list[Tuple[str, str]]:
    matches = list(_METRIC_RE.finditer(text))
    return [
        (_ALIAS_TO_METRIC[match.group(0)], text[match.start(): matches[index + 1].start() if index + 1 < len(matches) else len(text)])
        for index, match in enumerate(matches)
    ]

def _growth_candidate(clause: str) -> dict | None:
    match = re.search(r"同比|較上年同期|较上年同期", clause)
    return _numeric_candidate(clause[match.end():], amount=False) if match else None

def _numeric_candidate(clause: str, *, amount: bool) -> dict | None:
    if amount and _FOREIGN_CURRENCY_RE.search(clause):
        return {"error": "foreign_currency"}
    range_re, scalar_re = (_AMOUNT_RANGE_RE, _AMOUNT_SCALAR_RE) if amount else (_RATE_RANGE_RE, _RATE_SCALAR_RE)
    ranges = list(range_re.finditer(clause))
    excluded = [match.span() for match in ranges]
    scalars = [
        match for match in scalar_re.finditer(clause)
        if not any(left <= match.start() and match.end() <= right for left, right in excluded)
    ]
    if len(ranges) + len(scalars) != 1:
        return {"error": "numeric_value_ambiguous"} if ranges or scalars else None
    match, is_range = (ranges[0], True) if ranges else (scalars[0], False)
    if is_range:
        unit1, unit2 = match.groupdict().get("unit1"), match.groupdict().get("unit2")
        if unit1 and _normalize_unit(unit1) != _normalize_unit(unit2):
            return {"error": "mixed_numeric_units"}
        low_raw, high_raw, unit = match.group("low"), match.group("high"), unit2
    else:
        low_raw = high_raw = match.group("value")
        unit = match.groupdict().get("unit") or "%"
    low, high = _decimal(low_raw), _decimal(high_raw)
    if low is None or high is None or low > high:
        return {"error": "invalid_numeric_range"}
    if ((_LOSS_RE.search(clause) if amount else _DECLINE_RE.search(clause)) and low >= 0 and high >= 0):
        low, high = -high, -low
    normalized_unit = _normalize_unit(unit)
    factor = Decimal("10000") if normalized_unit == "万元" and str(unit) == "亿元" else Decimal("1")
    precision = _source_precision(low_raw) * factor
    return {
        "lower_value": _decimal_text(low * factor),
        "upper_value": _decimal_text(high * factor),
        "precision": _decimal_text(precision),
        "unit": normalized_unit,
        "is_range": is_range,
    }

def _explicit_modality(text: str) -> str:
    candidates = [(match.start(), "forecast") for match in _FORECAST_RE.finditer(text)]
    boundaries = [match.end() for match in _CLAUSE_BOUNDARY_RE.finditer(text)]
    for match in _REPORTED_RE.finditer(text):
        if match.group(0) in {"实现", "實現"}:
            start = max((position for position in boundaries if position <= match.start()), default=0)
            if _FORECAST_RE.search(text[start:match.start()]):
                continue
        candidates.append((match.start(), "reported"))
    return max(candidates)[1] if candidates else ""

def _external_evidence(unit: Mapping[str, Any], citations: Mapping[int, dict]) -> dict:
    refs = sorted({int(ref) for ref in unit.get("citation_refs") or []})
    return {
        "source_id": str(unit.get("source_id") or ""),
        "document_hash": str(unit.get("document_hash") or ""),
        "block_id": str(unit.get("block_id") or ""),
        "unit_id": str(unit.get("unit_id") or ""),
        "unit_hash": str(unit.get("unit_hash") or ""),
        "citation_refs": refs,
        "publish_times": sorted({str(citations[ref].get("publish_time") or "") for ref in refs}),
    }

def _observation_id(unit_id: str, metric: str, kind: str, period: Any, modality: str, candidate: Mapping[str, Any], ordinal: int) -> str:
    token = "|".join(map(str, (
        unit_id, metric, kind, period or "", modality, candidate.get("lower_value", ""),
        candidate.get("upper_value", ""), candidate.get("precision", ""), ordinal,
    )))
    return "external-observation:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]

def _unmapped(observation_id: str, unit_id: str, metric: str, kind: str, period: Any, reason: str) -> dict:
    return {
        "observation_id": observation_id,
        "unit_id": unit_id,
        "metric_key": metric,
        "value_kind": kind,
        "report_year": period[0] if period else 0,
        "report_type": period[1] if period else "",
        "reason": reason,
    }

def _build_mappings(
    observations: Iterable[dict],
    filing_series: Iterable[dict],
    financial_scan_pack: Mapping[str, Any],
) -> Tuple[list, list]:
    series_rows = list(filing_series)
    mappings, unmapped = [], []
    for observation in sorted(observations, key=lambda row: row["observation_id"]):
        targets = _exact_targets(observation, series_rows)
        if len(targets) > 1:
            unmapped.append(_relation_unmapped(observation, "ambiguous_value_basis"))
            continue
        if targets:
            mappings.append(_compatibility_mapping(
                observation, targets[0], financial_scan_pack,
            ))
            continue
        update, reason = _update_target(observation, series_rows)
        if update:
            mappings.append(_update_mapping(observation, update))
        else:
            unmapped.append(_relation_unmapped(observation, reason))
    return mappings, unmapped

def _exact_targets(observation: Mapping[str, Any], series_rows: Iterable[dict]) -> list[dict]:
    output = []
    for series in series_rows:
        if (
            series["metric_key"] != observation["metric_key"]
            or series["report_type"] != observation["report_type"]
        ):
            continue
        if observation["value_kind"] == "amount":
            for point in series["points"]:
                if point["report_year"] == observation["report_year"]:
                    output.append(_point_target(series, point))
        else:
            for change in series["changes"]:
                if (
                    change["to_period"] == str(observation["report_year"])
                    and change["from_period"] == str(observation["report_year"] - 1)
                    and change["growth_rate"]
                ):
                    output.append(_change_target(series, change))
    return sorted(output, key=lambda row: row["target_id"])

def _point_target(series: Mapping[str, Any], point: Mapping[str, Any]) -> dict:
    return {
        "target_kind": "filing_point",
        "target_id": point["fact_refs"][0],
        "metric_key": series["metric_key"],
        "report_type": series["report_type"],
        "value_basis": series["value_basis"],
        "target_periods": [point["period"]],
        "target_value": point["numeric_value"],
        "unit": series["unit"],
        "input_refs": point["fact_refs"],
        "filing_evidence": point["source_evidence"],
    }

def _change_target(series: Mapping[str, Any], change: Mapping[str, Any]) -> dict:
    points = {point["period"]: point for point in series["points"]}
    periods = [change["from_period"], change["to_period"]]
    return {
        "target_kind": "metric_change",
        "target_id": f"{series['series_id']}:change:{'-'.join(periods)}",
        "metric_key": series["metric_key"],
        "report_type": series["report_type"],
        "value_basis": series["value_basis"],
        "target_periods": periods,
        "target_value": change["growth_rate"].removesuffix("%"),
        "unit": "pct",
        "input_refs": change["input_refs"],
        "filing_evidence": _merge_mapping_evidence(*(
            points[period]["source_evidence"] for period in periods
        )),
    }

def _update_target(observation: Mapping[str, Any], series_rows: Iterable[dict]) -> Tuple[dict | None, str]:
    points = [
        _point_target(series, point)
        for series in series_rows
        if series["metric_key"] == observation["metric_key"]
        for point in series["points"]
    ]
    if not points:
        return None, "annual_metric_missing"
    latest_year = max(int(row["target_periods"][0]) for row in points)
    if observation["report_year"] > latest_year:
        latest = [row for row in points if int(row["target_periods"][0]) == latest_year]
        return (latest[0], "") if len(latest) == 1 else (None, "ambiguous_value_basis")
    if observation["report_year"] < latest_year:
        return None, "stale_external_period"
    if any(row["report_type"] != observation["report_type"] for row in points if int(row["target_periods"][0]) == latest_year):
        return None, "noncomparable_report_type"
    return None, "target_observation_missing"

def _compatibility_mapping(
    observation: Mapping[str, Any],
    target: Mapping[str, Any],
    financial_scan_pack: Mapping[str, Any],
) -> dict:
    low = _decimal(observation["lower_value"])
    high = _decimal(observation["upper_value"])
    precision = _decimal(observation["precision"])
    target_value = _decimal(target["target_value"])
    assert low is not None and high is not None and precision is not None and target_value is not None
    is_range = bool(observation["is_range"])
    if not is_range:
        low -= precision / 2
        high += precision / 2
    contains = low <= target_value <= high
    relation = "confirm" if contains else "contradict"
    shape = "range" if is_range else "scalar"
    outcome = "contains_filing" if is_range and contains else (
        "excludes_filing" if is_range else ("matches_filing" if contains else "differs_from_filing")
    )
    basis = f"{observation['modality']}_{shape}_{outcome}"
    linked = _linked_findings(observation, target, financial_scan_pack)
    return _mapping(
        observation,
        target,
        relation=relation,
        relation_basis=basis,
        external_low=low,
        external_high=high,
        linked_finding_ids=linked,
    )

def _update_mapping(observation: Mapping[str, Any], target: Mapping[str, Any]) -> dict:
    return _mapping(
        observation,
        target,
        relation="update",
        relation_basis="newer_period_observation",
        external_low=_decimal(observation["lower_value"]),
        external_high=_decimal(observation["upper_value"]),
        linked_finding_ids=[],
    )

def _mapping(
    observation: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    relation: str,
    relation_basis: str,
    external_low: Decimal | None,
    external_high: Decimal | None,
    linked_finding_ids: Iterable[str],
) -> dict:
    token = "|".join((observation["observation_id"], target["target_id"], relation, relation_basis))
    return {
        "mapping_id": "periodic-external-map:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:24],
        "relation": relation,
        "relation_basis": relation_basis,
        "observation_id": observation["observation_id"],
        **{key: target[key] for key in (
            "target_kind", "target_id", "metric_key", "report_type", "value_basis",
            "target_periods", "target_value", "unit", "input_refs", "filing_evidence",
        )},
        "external_lower_value": _decimal_text(external_low) if external_low is not None else "",
        "external_upper_value": _decimal_text(external_high) if external_high is not None else "",
        "external_evidence": observation["external_evidence"],
        "linked_finding_ids": sorted(set(linked_finding_ids)),
        "adjudication": "none",
        "official_fact_mutated": False,
        "report_eligible": False,
        "scoring_eligible": False,
    }

def _linked_findings(
    observation: Mapping[str, Any],
    target: Mapping[str, Any],
    financial_scan_pack: Mapping[str, Any],
) -> list[str]:
    if target["target_kind"] != "metric_change":
        return []
    target_refs = set(target["input_refs"])
    periods = target["target_periods"]
    return sorted({
        finding["finding_id"]
        for finding in financial_scan_pack.get("findings") or []
        if target_refs.issubset(set(finding.get("input_refs") or []))
        and any(
            row.get("metric_key") == observation["metric_key"]
            and row.get("from_period") == periods[0]
            and row.get("to_period") == periods[1]
            for row in finding.get("observations") or []
        )
    })

def _relation_unmapped(observation: Mapping[str, Any], reason: str) -> dict:
    evidence = observation.get("external_evidence") or [{}]
    return _unmapped(
        observation["observation_id"],
        str(evidence[0].get("unit_id") or ""),
        observation["metric_key"],
        observation["value_kind"],
        (observation["report_year"], observation["report_type"]),
        reason,
    )

def _merge_mapping_evidence(*groups: Iterable[dict]) -> list[dict]:
    keyed = {
        (
            row.get("source_doc", ""), row.get("source_block_id", ""),
            row.get("source_excerpt_hash", ""), row.get("source_block_hash", ""),
        ): row
        for group in groups for row in group
    }
    return [keyed[key] for key in sorted(keyed)]

def _resolve_identities(rows: Iterable[dict], key: str) -> Tuple[list, list]:
    grouped: Dict[str, list] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    output, diagnostics = [], []
    for identity in sorted(grouped):
        candidates = grouped[identity]
        if any(row != candidates[0] for row in candidates[1:]):
            diagnostics.append({"code": f"conflicting_{key}", key: identity})
        else:
            output.append(candidates[0])
    return output, diagnostics

def _citations(value: Any) -> Dict[int, dict]:
    return {
        int(key): dict(row) for key, row in (value or {}).items()
        if str(key).isdigit() and isinstance(row, Mapping)
    }

def _normalize_unit(value: Any) -> str:
    return "%" if value == "%" else "万元"

def _decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None

def _source_precision(value: str) -> Decimal:
    clean = str(value).replace(",", "")
    places = len(clean.partition(".")[2])
    return Decimal(1).scaleb(-places)

def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." not in text:
        return text + ".00"
    whole, fraction = text.split(".", 1)
    return whole + "." + fraction.ljust(2, "0")

def _unique_rows(rows: Iterable[dict]) -> list[dict]:
    keyed = {tuple(sorted((key, str(value)) for key, value in row.items())): row for row in rows}
    return [keyed[key] for key in sorted(keyed)]
