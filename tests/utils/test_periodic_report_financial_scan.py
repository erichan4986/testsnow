from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_financial_scan import (
    build_periodic_report_financial_scan_pack,
    read_periodic_financial_scan_source,
)
from periodic_report_metric_series import build_periodic_report_metric_series_pack


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _filing_fact(
    metric_key: str,
    value: str,
    *,
    year: int,
    report_type: str = "annual",
    value_basis: str = "as_reported",
    stock_code: str = "300001",
) -> dict:
    source_doc = f"测试股份_{year}_{report_type}_{value_basis}.txt"
    block_id = f"financial-{metric_key}-{year}-{value_basis}"
    source = f"{metric_key}:{value}:{year}:{value_basis}"
    return {
        "schema_version": "periodic_report_structured_fact.v1",
        "source_type": "periodic_report_filing_fact",
        "fact_id": f"periodic:{stock_code}:{year}:{report_type}:{metric_key}",
        "stock_code": stock_code,
        "stock_name": "测试股份",
        "report_year": year,
        "report_type": report_type,
        "metric_key": metric_key,
        "label": metric_key,
        "value": f"{value}万元",
        "normalized_value": f"{value}万元",
        "unit": "万元",
        "currency": "CNY",
        "period": str(year),
        "value_basis": value_basis,
        "source_doc": source_doc,
        "source_block_id": block_id,
        "evidence_refs": [block_id],
        "source_excerpt": source,
        "source_excerpt_hash": _hash(source),
        "source_block_hash": _hash(f"block:{source}"),
    }


def _derived_fact(
    ratio: str,
    *,
    year: int,
    report_type: str = "annual",
    value_basis: str = "as_reported",
    stock_code: str = "300001",
) -> dict:
    return {
        "schema_version": "periodic_report_structured_fact.v1",
        "source_type": "periodic_report_derived_fact",
        "fact_id": (
            f"periodic:{stock_code}:{year}:{report_type}:"
            "operating_cash_flow_to_net_profit"
        ),
        "stock_code": stock_code,
        "report_year": year,
        "report_type": report_type,
        "period": str(year),
        "metric_key": "operating_cash_flow_to_net_profit",
        "value": f"{ratio}%",
        "signed_value": f"{ratio}%",
        "unit": "pct",
        "input_refs": [
            f"periodic:{stock_code}:{year}:{report_type}:operating_cash_flow",
            f"periodic:{stock_code}:{year}:{report_type}:net_profit",
        ],
        "formula_version": "cash_conversion.v1",
        "source_doc": f"测试股份_{year}_{report_type}_{value_basis}.txt",
    }


def _fact_pack(
    year: int,
    facts: list[dict],
    *,
    report_type: str = "annual",
    value_basis: str = "as_reported",
    derived: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": "periodic_report_structured_fact.v1",
        "stock_code": "300001",
        "stock_name": "测试股份",
        "report_year": year,
        "report_type": report_type,
        "source_doc": f"测试股份_{year}_{report_type}_{value_basis}.txt",
        "filing_facts": facts,
        "derived_facts": derived or [],
        "filing_risk_signals": [],
        "diagnostics": [],
    }


def _metric_pack(*packs: dict) -> dict:
    return build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=list(packs),
    )


def _scan(pack: dict) -> dict:
    return build_periodic_report_financial_scan_pack(
        stock_code="300001",
        stock_name="测试股份",
        metric_series_pack=pack,
    )


def _read_source(pack: dict) -> dict:
    return read_periodic_financial_scan_source(
        stock_code="300001",
        metric_series_pack=pack,
    )


def _history(
    values: dict[int, dict[str, str]],
    *,
    report_type: str = "annual",
    value_basis: str = "as_reported",
) -> dict:
    packs = []
    for year, metrics in values.items():
        facts = [
            _filing_fact(
                metric_key,
                value,
                year=year,
                report_type=report_type,
                value_basis=value_basis,
            )
            for metric_key, value in metrics.items()
        ]
        packs.append(_fact_pack(
            year,
            facts,
            report_type=report_type,
            value_basis=value_basis,
        ))
    return _metric_pack(*packs)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda pack: pack.update(schema_version="other.v1"), "unsupported_source_schema"),
        (lambda pack: pack.update(stock_code="999999"), "source_stock_mismatch"),
        (lambda pack: pack.update(report_eligible=True), "source_eligibility_violation"),
        (lambda pack: pack.update(series={}), "malformed_source_collections"),
    ],
)
def test_invalid_top_level_source_returns_complete_unavailable_pack(mutation, code) -> None:
    source = _metric_pack()
    mutation(source)

    result = _scan(source)

    assert result == {
        "schema_version": "periodic_report_financial_scan_pack.v1",
        "stock_code": "300001",
        "stock_name": "测试股份",
        "source_schema_version": str(source.get("schema_version") or ""),
        "status": "unavailable",
        "report_eligible": False,
        "scoring_eligible": False,
        "external_mapping_eligible": True,
        "source_series_count": 0,
        "source_point_count": 0,
        "comparable_interval_count": 0,
        "findings": [],
        "diagnostics": [{"code": code, "origin": "financial_scan"}],
    }


def test_non_scalar_schema_is_not_stringified_into_the_unavailable_pack() -> None:
    source = _metric_pack()
    source["schema_version"] = {"raw_text": "must not leak"}

    result = _scan(source)

    assert result["status"] == "unavailable"
    assert result["source_schema_version"] == ""
    assert "raw_text" not in json.dumps(result, ensure_ascii=False)


def test_non_scalar_diagnostic_and_series_identity_payloads_do_not_leak() -> None:
    source = _metric_pack()
    source["diagnostics"] = [{
        "code": {"raw_text": "upstream secret"},
        "source_doc": {"url": "https://example.invalid"},
    }]
    source["series"] = [{"series_id": {"prompt": "series secret"}}]

    result = _scan(source)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert result["status"] == "empty"
    assert result["diagnostics"] == [{
        "code": "invalid_filing_series_contract",
        "origin": "financial_scan",
    }]
    assert all(token not in payload for token in ("raw_text", "url", "prompt", "secret"))


def test_valid_source_without_points_returns_empty_pack() -> None:
    result = _scan(_metric_pack())

    assert result["status"] == "empty"
    assert result["source_series_count"] == 0
    assert result["source_point_count"] == 0
    assert result["comparable_interval_count"] == 0
    assert result["findings"] == []


def test_public_source_reader_returns_the_scanners_sanitized_inputs() -> None:
    source = _cashflow_history([
        (2025, "100.00", "40.00", "40.00", "as_reported"),
    ])

    result = _read_source(source)

    assert result["status"] == "ok"
    assert result["source_schema_version"] == "periodic_report_metric_series_pack.v1"
    assert [row["metric_key"] for row in result["filing_series"]] == [
        "net_profit",
        "operating_cash_flow",
    ]
    assert [row["metric_key"] for row in result["derived_series"]] == [
        "operating_cash_flow_to_net_profit",
    ]
    assert result["diagnostics"] == []


def test_source_reader_and_scan_reject_the_same_duplicate_and_malformed_rows() -> None:
    source = _metric_pack(_fact_pack(
        2025,
        [
            _filing_fact("revenue", "1000.00", year=2025),
            _filing_fact("net_profit", "100.00", year=2025),
        ],
    ))
    source["series"].append(copy.deepcopy(source["series"][0]))
    source["series"][1]["points"][0]["numeric_value"] = "100.000"

    reader = _read_source(source)
    scan = _scan(source)

    assert reader["status"] == "ok"
    assert reader["filing_series"] == []
    assert reader["derived_series"] == []
    assert reader["diagnostics"] == scan["diagnostics"]
    assert scan["source_series_count"] == 0
    assert scan["source_point_count"] == 0


def test_one_admitted_point_returns_partial_pack() -> None:
    source = _metric_pack(_fact_pack(
        2025,
        [_filing_fact("revenue", "1000.00", year=2025)],
    ))

    result = _scan(source)

    assert result["status"] == "partial"
    assert result["source_series_count"] == 1
    assert result["source_point_count"] == 1
    assert result["comparable_interval_count"] == 0
    assert result["findings"] == []


def test_duplicate_source_series_ids_reject_every_duplicate() -> None:
    source = _metric_pack(_fact_pack(
        2025,
        [_filing_fact("revenue", "1000.00", year=2025)],
    ))
    source["series"].append(copy.deepcopy(source["series"][0]))

    result = _scan(source)

    assert result["status"] == "empty"
    assert result["source_series_count"] == 0
    assert result["source_point_count"] == 0
    assert sum(
        row["code"] == "duplicate_source_series_id"
        for row in result["diagnostics"]
    ) == 1


@pytest.mark.parametrize("mutation", [
    lambda point: point.update(numeric_value="NaN"),
    lambda point: point["source_evidence"][0].update(source_excerpt_hash="bad"),
])
def test_invalid_filing_point_is_omitted_and_diagnosed(mutation) -> None:
    source = _metric_pack(_fact_pack(
        2025,
        [_filing_fact("revenue", "1000.00", year=2025)],
    ))
    mutation(source["series"][0]["points"][0])

    result = _scan(source)

    assert result["status"] == "empty"
    assert result["source_point_count"] == 0
    assert any(
        row["code"] == "invalid_filing_point_contract"
        for row in result["diagnostics"]
    )


def test_empty_source_series_is_not_counted_as_admitted() -> None:
    source = _metric_pack(_fact_pack(
        2025,
        [_filing_fact("revenue", "1000.00", year=2025)],
    ))
    source["series"][0]["points"] = []
    source["series"][0]["changes"] = []

    result = _scan(source)

    assert result["source_series_count"] == 0
    assert any(
        row["code"] == "invalid_filing_series_contract"
        for row in result["diagnostics"]
    )


def test_noncanonical_point_precision_is_rejected_not_rounded() -> None:
    source = _metric_pack(_fact_pack(
        2025,
        [_filing_fact("revenue", "1000.00", year=2025)],
    ))
    source["series"][0]["points"][0]["numeric_value"] = "1000.000"

    result = _scan(source)

    assert result["source_point_count"] == 0
    assert any(
        row["code"] == "invalid_filing_point_contract"
        for row in result["diagnostics"]
    )


def test_noncanonical_growth_precision_is_rejected_not_rounded() -> None:
    source = _history({
        2024: {"revenue": "1000.00"},
        2025: {"revenue": "1100.00"},
    })
    source["series"][0]["changes"][0]["growth_rate"] = "10.000%"

    result = _scan(source)

    assert result["source_series_count"] == 0
    assert any(
        row["code"] == "invalid_filing_change_contract"
        for row in result["diagnostics"]
    )


def test_empty_pack_is_json_serializable_without_source_prose() -> None:
    payload = json.dumps(_scan(_metric_pack()), ensure_ascii=False, sort_keys=True)
    assert "source_excerpt" not in payload
    assert "raw_text" not in payload


def test_revenue_growth_with_profit_contraction_emits_auditable_finding() -> None:
    result = _scan(_history({
        2024: {"revenue": "1000.00", "net_profit": "100.00"},
        2025: {"revenue": "1100.00", "net_profit": "90.00"},
    }))

    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["finding_id"] == (
        "periodic-financial:300001:annual:as_reported:2024-2025:"
        "revenue_growth_profit_contraction:net_profit+revenue"
    )
    assert finding["rule_id"] == "revenue_growth_profit_contraction"
    assert finding["rule_version"] == "financial_consistency.v1"
    assert finding["category"] == "cross_metric_divergence"
    assert finding["direction"] == "adverse"
    assert finding["periods"] == ["2024", "2025"]
    assert finding["metric_keys"] == ["net_profit", "revenue"]
    observed = {row["metric_key"]: row for row in finding["observations"]}
    assert observed["revenue"] == {
        "metric_key": "revenue",
        "value_kind": "growth_rate",
        "from_period": "2024",
        "to_period": "2025",
        "value": "10.00%",
    }
    assert observed["net_profit"]["value"] == "-10.00%"
    assert finding["input_refs"] == [
        "periodic:300001:2024:annual:net_profit",
        "periodic:300001:2024:annual:revenue",
        "periodic:300001:2025:annual:net_profit",
        "periodic:300001:2025:annual:revenue",
    ]
    assert len(finding["source_evidence"]) == 4
    assert finding["report_eligible"] is False
    assert finding["scoring_eligible"] is False
    assert finding["external_mapping_eligible"] is True


def test_profit_growth_with_cashflow_contraction_emits_auditable_finding() -> None:
    result = _scan(_history({
        2024: {"net_profit": "100.00", "operating_cash_flow": "100.00"},
        2025: {"net_profit": "120.00", "operating_cash_flow": "80.00"},
    }))

    assert [row["rule_id"] for row in result["findings"]] == [
        "profit_growth_cashflow_contraction"
    ]
    finding = result["findings"][0]
    assert finding["metric_keys"] == ["net_profit", "operating_cash_flow"]
    assert {row["value"] for row in finding["observations"]} == {
        "20.00%", "-20.00%"
    }


def test_same_direction_growth_does_not_emit_cross_metric_divergence() -> None:
    result = _scan(_history({
        2024: {
            "revenue": "1000.00",
            "net_profit": "100.00",
            "operating_cash_flow": "80.00",
        },
        2025: {
            "revenue": "1100.00",
            "net_profit": "120.00",
            "operating_cash_flow": "90.00",
        },
    }))

    assert result["findings"] == []


def test_cross_metric_join_requires_the_same_interval() -> None:
    source = _metric_pack(
        *[
            _fact_pack(
                year,
                [_filing_fact("revenue", value, year=year)],
            )
            for year, value in ((2023, "900.00"), (2024, "1000.00"))
        ],
        *[
            _fact_pack(
                year,
                [_filing_fact("net_profit", value, year=year)],
            )
            for year, value in ((2024, "100.00"), (2025, "90.00"))
        ],
    )

    assert _scan(source)["findings"] == []


def test_cross_metric_join_requires_the_same_value_basis() -> None:
    packs = []
    for year, value in ((2024, "1000.00"), (2025, "1100.00")):
        packs.append(_fact_pack(
            year,
            [_filing_fact("revenue", value, year=year)],
        ))
    for year, value in ((2024, "100.00"), (2025, "90.00")):
        packs.append(_fact_pack(
            year,
            [
                _filing_fact(
                    "net_profit",
                    value,
                    year=year,
                    value_basis="restated",
                )
            ],
            value_basis="restated",
        ))

    assert _scan(_metric_pack(*packs))["findings"] == []


def test_cross_metric_join_never_mixes_annual_and_semiannual_series() -> None:
    annual = _history({
        2024: {"revenue": "1000.00"},
        2025: {"revenue": "1100.00"},
    })
    semiannual = _history(
        {
            2024: {"net_profit": "100.00"},
            2025: {"net_profit": "90.00"},
        },
        report_type="semiannual",
    )
    source = copy.deepcopy(annual)
    source["series"].extend(semiannual["series"])

    assert _scan(source)["findings"] == []


def test_findings_never_copy_source_prose_or_editorial_fields() -> None:
    result = _scan(_history({
        2024: {"revenue": "1000.00", "net_profit": "100.00"},
        2025: {"revenue": "1100.00", "net_profit": "90.00"},
    }))
    banned = {"text", "source_excerpt", "raw_text", "url", "prompt", "rationale"}

    def _keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from _keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from _keys(item)

    assert banned.isdisjoint(set(_keys(result["findings"])))


def test_positive_growth_reversing_negative_emits_three_period_finding() -> None:
    result = _scan(_history({
        2023: {"revenue": "100.00"},
        2024: {"revenue": "110.00"},
        2025: {"revenue": "99.00"},
    }))

    assert [row["rule_id"] for row in result["findings"]] == [
        "growth_direction_reversal"
    ]
    finding = result["findings"][0]
    assert finding["periods"] == ["2023", "2024", "2025"]
    assert finding["metric_keys"] == ["revenue"]
    assert [
        (row["from_period"], row["to_period"], row["value"])
        for row in finding["observations"]
    ] == [
        ("2023", "2024", "10.00%"),
        ("2024", "2025", "-10.00%"),
    ]


def test_negative_growth_turning_positive_emits_recovery() -> None:
    result = _scan(_history({
        2023: {"net_profit": "100.00"},
        2024: {"net_profit": "90.00"},
        2025: {"net_profit": "99.00"},
    }))

    finding = result["findings"][0]
    assert finding["rule_id"] == "growth_direction_recovery"
    assert finding["direction"] == "recovery"


@pytest.mark.parametrize("values", [
    {
        2023: {"revenue": "100.00"},
        2024: {"revenue": "100.00"},
        2025: {"revenue": "90.00"},
    },
    {
        2022: {"revenue": "100.00"},
        2023: {"revenue": "110.00"},
        2025: {"revenue": "100.00"},
        2026: {"revenue": "90.00"},
    },
])
def test_zero_growth_or_non_shared_boundaries_do_not_emit_reversal(values) -> None:
    assert _scan(_history(values))["findings"] == []


def _cashflow_history(
    rows: list[tuple[int, str, str, str, str]],
) -> dict:
    packs = []
    for year, net_profit, operating_cash_flow, ratio, value_basis in rows:
        facts = [
            _filing_fact(
                "net_profit",
                net_profit,
                year=year,
                value_basis=value_basis,
            ),
            _filing_fact(
                "operating_cash_flow",
                operating_cash_flow,
                year=year,
                value_basis=value_basis,
            ),
        ]
        packs.append(_fact_pack(
            year,
            facts,
            value_basis=value_basis,
            derived=[
                _derived_fact(ratio, year=year, value_basis=value_basis)
            ],
        ))
    return _metric_pack(*packs)


def test_weak_cash_conversion_uses_shared_rule_and_exact_inputs() -> None:
    result = _scan(_cashflow_history([
        (2025, "100.00", "40.00", "40.00", "as_reported"),
    ]))

    assert [row["rule_id"] for row in result["findings"]] == [
        "cashflow_quality_weak"
    ]
    finding = result["findings"][0]
    assert finding["category"] == "cashflow_quality"
    assert finding["observations"] == [{
        "metric_key": "operating_cash_flow_to_net_profit",
        "value_kind": "ratio",
        "period": "2025",
        "value": "40.00%",
    }]
    assert finding["input_refs"] == [
        "periodic:300001:2025:annual:net_profit",
        "periodic:300001:2025:annual:operating_cash_flow",
        "periodic:300001:2025:annual:operating_cash_flow_to_net_profit",
    ]


def test_missing_ratio_after_loss_is_not_inferred_healthy_or_weak() -> None:
    source = _history({
        2025: {"net_profit": "-100.00", "operating_cash_flow": "40.00"},
    })

    assert _scan(source)["findings"] == []


def test_cashflow_quality_transition_detects_deterioration() -> None:
    result = _scan(_cashflow_history([
        (2024, "100.00", "60.00", "60.00", "as_reported"),
        (2025, "100.00", "40.00", "40.00", "as_reported"),
    ]))

    assert {row["rule_id"] for row in result["findings"]} == {
        "cashflow_quality_weak",
        "cashflow_quality_deteriorated",
    }


def test_cashflow_quality_transition_detects_recovery() -> None:
    result = _scan(_cashflow_history([
        (2024, "100.00", "40.00", "40.00", "as_reported"),
        (2025, "100.00", "60.00", "60.00", "as_reported"),
    ]))

    by_rule = {row["rule_id"]: row for row in result["findings"]}
    assert set(by_rule) == {"cashflow_quality_weak", "cashflow_quality_recovered"}
    assert by_rule["cashflow_quality_recovered"]["direction"] == "recovery"


def test_cashflow_quality_transition_requires_consecutive_same_basis_points() -> None:
    nonconsecutive = _scan(_cashflow_history([
        (2023, "100.00", "60.00", "60.00", "as_reported"),
        (2025, "100.00", "40.00", "40.00", "as_reported"),
    ]))
    separated_basis = _scan(_cashflow_history([
        (2024, "100.00", "60.00", "60.00", "as_reported"),
        (2025, "100.00", "40.00", "40.00", "restated"),
    ]))

    assert "cashflow_quality_deteriorated" not in {
        row["rule_id"] for row in nonconsecutive["findings"]
    }
    assert "cashflow_quality_deteriorated" not in {
        row["rule_id"] for row in separated_basis["findings"]
    }


def test_unresolved_derived_input_refs_omit_the_ratio_point() -> None:
    source = _cashflow_history([
        (2025, "100.00", "40.00", "40.00", "as_reported"),
    ])
    source["derived_series"][0]["points"][0]["input_refs"][0] = (
        "periodic:300001:2025:annual:missing"
    )

    result = _scan(source)

    assert result["findings"] == []
    assert any(
        row["code"] == "unresolved_derived_input_refs"
        for row in result["diagnostics"]
    )


def test_derived_evidence_must_equal_its_filing_input_evidence_union() -> None:
    source = _cashflow_history([
        (2025, "100.00", "40.00", "40.00", "as_reported"),
    ])
    source["derived_series"][0]["points"][0]["source_evidence"] = [{
        "source_doc": "unrelated.txt",
        "source_block_id": "other-0",
        "source_excerpt_hash": "a" * 64,
        "source_block_hash": "b" * 64,
    }]

    result = _scan(source)

    assert result["findings"] == []
    assert any(
        row["code"] == "invalid_derived_point_contract"
        for row in result["diagnostics"]
    )


def test_scan_output_is_deterministic_under_source_pack_order() -> None:
    packs = []
    for year, revenue, net_profit in (
        (2024, "1000.00", "100.00"),
        (2025, "1100.00", "90.00"),
    ):
        packs.append(_fact_pack(
            year,
            [
                _filing_fact("revenue", revenue, year=year),
                _filing_fact("net_profit", net_profit, year=year),
            ],
        ))

    assert _scan(_metric_pack(*packs)) == _scan(_metric_pack(*reversed(packs)))
