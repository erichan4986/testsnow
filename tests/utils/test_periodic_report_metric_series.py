from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_metric_series import build_periodic_report_metric_series_pack


def _filing_fact(
    metric_key: str,
    value: str,
    *,
    year: int,
    report_type: str = "annual",
    stock_code: str = "300001",
    source_doc: str = "",
    **overrides,
):
    source_doc = source_doc or f"测试股份_{year}_{report_type}_jina.txt"
    block_id = f"financial_summary_table-{year}"
    fact = {
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
        "value_basis": "as_reported",
        "source_doc": source_doc,
        "source_block_id": block_id,
        "evidence_refs": [block_id],
        "source_excerpt": f"{metric_key} {value}万元",
        "source_excerpt_hash": f"e{year}".ljust(64, "0"),
        "source_block_hash": f"b{year}".ljust(64, "0"),
    }
    fact.update(overrides)
    return fact


def _fact_pack(
    year: int,
    facts: list[dict],
    *,
    report_type: str = "annual",
    stock_code: str = "300001",
    source_doc: str = "",
    derived_facts: list[dict] | None = None,
    diagnostics: list[dict] | None = None,
):
    source_doc = source_doc or f"测试股份_{year}_{report_type}_jina.txt"
    return {
        "schema_version": "periodic_report_structured_fact.v1",
        "stock_code": stock_code,
        "stock_name": "测试股份",
        "report_year": year,
        "report_type": report_type,
        "source_doc": source_doc,
        "filing_facts": facts,
        "derived_facts": derived_facts or [],
        "filing_risk_signals": [],
        "diagnostics": diagnostics or [],
    }


def _derived_cash_conversion(
    value: str,
    *,
    year: int,
    report_type: str = "annual",
    stock_code: str = "300001",
    source_doc: str = "",
    **overrides,
):
    source_doc = source_doc or f"测试股份_{year}_{report_type}_jina.txt"
    row = {
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
        "label": "经营现金流/归母净利润",
        "value": f"{value}%",
        "signed_value": f"{value}%",
        "unit": "pct",
        "input_refs": [
            f"periodic:{stock_code}:{year}:{report_type}:operating_cash_flow",
            f"periodic:{stock_code}:{year}:{report_type}:net_profit",
        ],
        "calculation": "operating_cash_flow / abs(net_profit)",
        "formula_version": "cash_conversion.v1",
        "source_doc": source_doc,
        "knowledge_eligible": False,
    }
    row.update(overrides)
    return row


def _series(pack: dict, metric_key: str, report_type: str = "annual") -> dict:
    return next(
        row
        for row in pack["series"]
        if row["metric_key"] == metric_key and row["report_type"] == report_type
    )


def test_builds_oldest_first_annual_series_and_consecutive_growth() -> None:
    packs = [
        _fact_pack(2025, [_filing_fact("revenue", "1100.00", year=2025)]),
        _fact_pack(2024, [_filing_fact("revenue", "1000.00", year=2024)]),
    ]

    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=packs,
    )

    assert result["schema_version"] == "periodic_report_metric_series_pack.v1"
    assert result["report_eligible"] is False
    assert result["scoring_eligible"] is False
    assert result["source_pack_count"] == 2
    assert result["accepted_fact_count"] == 2
    assert result["rejected_fact_count"] == 0

    revenue = _series(result, "revenue")
    assert revenue["series_id"].startswith("periodic-series:300001:annual:revenue:")
    assert [point["report_year"] for point in revenue["points"]] == [2024, 2025]
    assert [point["numeric_value"] for point in revenue["points"]] == [
        "1000.00",
        "1100.00",
    ]
    assert revenue["changes"] == [
        {
            "from_period": "2024",
            "to_period": "2025",
            "absolute_change": "100.00万元",
            "growth_rate": "10.00%",
            "input_refs": [
                "periodic:300001:2024:annual:revenue",
                "periodic:300001:2025:annual:revenue",
            ],
            "formula_version": "periodic_growth.v1",
        }
    ]
    assert '"source_excerpt":' not in json.dumps(result, ensure_ascii=False)


def test_annual_and_semiannual_facts_never_share_a_series() -> None:
    packs = [
        _fact_pack(2025, [_filing_fact("revenue", "1100.00", year=2025)]),
        _fact_pack(
            2025,
            [
                _filing_fact(
                    "revenue",
                    "550.00",
                    year=2025,
                    report_type="semiannual",
                    source_doc="测试股份_2025_semiannual_jina.txt",
                )
            ],
            report_type="semiannual",
            source_doc="测试股份_2025_semiannual_jina.txt",
        ),
    ]

    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=packs,
    )

    assert {(row["metric_key"], row["report_type"]) for row in result["series"]} == {
        ("revenue", "annual"),
        ("revenue", "semiannual"),
    }
    assert len({row["series_id"] for row in result["series"]}) == 2


def test_exact_same_period_value_merges_document_bound_evidence() -> None:
    zh_doc = "测试股份_2025_annual_zh_jina.txt"
    en_doc = "测试股份_2025_annual_en_jina.txt"
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [_filing_fact("revenue", "1100.00", year=2025, source_doc=zh_doc)],
                source_doc=zh_doc,
            ),
            _fact_pack(
                2025,
                [
                    _filing_fact(
                        "revenue",
                        "1100.00",
                        year=2025,
                        source_doc=en_doc,
                        source_excerpt_hash="c" * 64,
                        source_block_hash="d" * 64,
                    )
                ],
                source_doc=en_doc,
            ),
        ],
    )

    points = _series(result, "revenue")["points"]
    assert len(points) == 1
    assert [row["source_doc"] for row in points[0]["source_evidence"]] == [
        en_doc,
        zh_doc,
    ]


def test_conflicting_same_period_values_are_omitted_fail_closed() -> None:
    first_doc = "测试股份_2025_annual_jina.txt"
    revised_doc = "测试股份_2025_annual_jina-1.txt"
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [_filing_fact("revenue", "1000.00", year=2025, source_doc=first_doc)],
                source_doc=first_doc,
            ),
            _fact_pack(
                2025,
                [_filing_fact("revenue", "1100.00", year=2025, source_doc=revised_doc)],
                source_doc=revised_doc,
            ),
        ],
    )

    assert result["series"] == []
    assert any(row["code"] == "conflicting_period_values" for row in result["diagnostics"])


def test_non_positive_growth_base_keeps_absolute_change_and_omits_rate() -> None:
    for previous_value in ("0.00", "-100.00"):
        result = build_periodic_report_metric_series_pack(
            stock_code="300001",
            stock_name="测试股份",
            fact_packs=[
                _fact_pack(2024, [_filing_fact("revenue", previous_value, year=2024)]),
                _fact_pack(2025, [_filing_fact("revenue", "100.00", year=2025)]),
            ],
        )

        change = _series(result, "revenue")["changes"][0]
        assert "growth_rate" not in change
        assert change["absolute_change"] in {"100.00万元", "200.00万元"}
        assert any(row["code"] == "non_positive_growth_base" for row in result["diagnostics"])


def test_non_consecutive_history_does_not_emit_pseudo_yoy_change() -> None:
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(2022, [_filing_fact("revenue", "800.00", year=2022)]),
            _fact_pack(2025, [_filing_fact("revenue", "1100.00", year=2025)]),
        ],
    )

    assert _series(result, "revenue")["changes"] == []
    assert any(row["code"] == "non_consecutive_period_gap" for row in result["diagnostics"])


def test_invalid_filing_dimensions_and_provenance_are_rejected() -> None:
    facts = [
        _filing_fact("revenue", "1000.00", year=2025, stock_code="999999"),
        _filing_fact("revenue", "1000.00", year=2025, source_block_hash=""),
        _filing_fact("revenue", "1000.00", year=2025, unit="元"),
        _filing_fact("revenue", "1000.00", year=2025, currency="HKD"),
        _filing_fact("revenue", "1000.00", year=2025, normalized_value="not-a-number万元"),
        _filing_fact(
            "revenue",
            "1000.00",
            year=2025,
            source_type="periodic_report_fulltext_analysis",
        ),
    ]
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[_fact_pack(2025, facts)],
    )

    assert result["series"] == []
    assert result["accepted_fact_count"] == 0
    assert result["rejected_fact_count"] == len(facts)
    assert {row["code"] for row in result["diagnostics"]} == {
        "stock_code_mismatch",
        "invalid_source_hash",
        "incompatible_fact_dimensions",
        "invalid_normalized_value",
        "unsupported_fact_source_type",
    }


def test_assembles_existing_signed_cash_conversion_without_recalculation() -> None:
    year = 2025
    facts = [
        _filing_fact("net_profit", "100.00", year=year),
        _filing_fact("operating_cash_flow", "-20.00", year=year),
    ]
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                year,
                facts,
                derived_facts=[_derived_cash_conversion("-20.00", year=year)],
            )
        ],
    )

    assert len(result["derived_series"]) == 1
    series = result["derived_series"][0]
    assert series["series_id"].startswith(
        "periodic-derived-series:300001:annual:operating_cash_flow_to_net_profit:"
    )
    assert series["metric_key"] == "operating_cash_flow_to_net_profit"
    assert series["formula_version"] == "cash_conversion.v1"
    assert series["report_eligible"] is False
    assert series["scoring_eligible"] is False
    point = series["points"][0]
    assert point["period"] == "2025"
    assert point["numeric_value"] == "-20.00"
    assert point["value"] == "-20.00%"
    assert point["input_refs"] == [
        "periodic:300001:2025:annual:net_profit",
        "periodic:300001:2025:annual:operating_cash_flow",
    ]
    assert {row["source_block_id"] for row in point["source_evidence"]} == {
        "financial_summary_table-2025"
    }


def test_derived_row_cannot_bypass_a_conflicted_filing_input() -> None:
    doc_a = "测试股份_2025_annual_jina.txt"
    doc_b = "测试股份_2025_annual_jina-1.txt"
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [
                    _filing_fact("net_profit", "100.00", year=2025, source_doc=doc_a),
                    _filing_fact("operating_cash_flow", "-20.00", year=2025, source_doc=doc_a),
                ],
                source_doc=doc_a,
                derived_facts=[_derived_cash_conversion("-20.00", year=2025, source_doc=doc_a)],
            ),
            _fact_pack(
                2025,
                [_filing_fact("net_profit", "120.00", year=2025, source_doc=doc_b)],
                source_doc=doc_b,
            ),
        ],
    )

    assert result["derived_series"] == []
    assert any(row["code"] == "derived_input_not_accepted" for row in result["diagnostics"])


def test_conflicting_same_period_derived_values_are_omitted() -> None:
    facts = [
        _filing_fact("net_profit", "100.00", year=2025),
        _filing_fact("operating_cash_flow", "-20.00", year=2025),
    ]
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                facts,
                derived_facts=[
                    _derived_cash_conversion("-20.00", year=2025),
                    _derived_cash_conversion("-30.00", year=2025),
                ],
            )
        ],
    )

    assert result["derived_series"] == []
    assert any(
        row["code"] == "conflicting_derived_period_values"
        for row in result["diagnostics"]
    )


def test_input_diagnostics_are_copied_through_a_strict_compact_allowlist() -> None:
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [],
                diagnostics=[{
                    "code": "unanchored_filing_fact",
                    "metric_key": "revenue",
                    "source_excerpt": "must not leak",
                    "arbitrary": "must not leak",
                }],
            )
        ],
    )

    assert result["diagnostics"] == [{
        "code": "unanchored_filing_fact",
        "metric_key": "revenue",
        "source_doc": "测试股份_2025_annual_jina.txt",
        "report_year": 2025,
        "report_type": "annual",
    }]
    assert '"source_excerpt":' not in json.dumps(result, ensure_ascii=False)


def test_pack_and_fact_identity_mismatches_fail_closed_with_diagnostics() -> None:
    valid_fact = _filing_fact("revenue", "1000.00", year=2025)
    wrong_schema_pack = _fact_pack(2025, [])
    wrong_schema_pack["schema_version"] = "periodic_report_structured_fact.v0"

    wrong_stock_pack = _fact_pack(2025, [], stock_code="999999")
    wrong_period_pack = _fact_pack(2024, [valid_fact])
    wrong_doc_fact = _filing_fact(
        "revenue",
        "1000.00",
        year=2025,
        source_doc="other-document.txt",
    )
    wrong_id_fact = _filing_fact(
        "revenue",
        "1000.00",
        year=2025,
        fact_id="periodic:300001:2025:annual:net_profit",
    )
    bad_hash_fact = _filing_fact(
        "revenue",
        "1000.00",
        year=2025,
        source_excerpt_hash="not-sha256",
    )

    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            wrong_schema_pack,
            wrong_stock_pack,
            wrong_period_pack,
            _fact_pack(2025, [wrong_doc_fact]),
            _fact_pack(2025, [wrong_id_fact]),
            _fact_pack(2025, [bad_hash_fact]),
        ],
    )

    assert result["series"] == []
    assert {row["code"] for row in result["diagnostics"]} == {
        "unsupported_fact_pack_schema",
        "fact_pack_stock_mismatch",
        "fact_pack_period_mismatch",
        "source_doc_mismatch",
        "fact_id_mismatch",
        "invalid_source_hash",
    }


def test_non_finite_filing_and_derived_values_are_rejected() -> None:
    filing_result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [_filing_fact("revenue", "1000.00", year=2025, normalized_value="NaN万元")],
            )
        ],
    )
    assert filing_result["series"] == []
    assert any(row["code"] == "invalid_normalized_value" for row in filing_result["diagnostics"])

    facts = [
        _filing_fact("net_profit", "100.00", year=2025),
        _filing_fact("operating_cash_flow", "-20.00", year=2025),
    ]
    derived_result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                facts,
                derived_facts=[_derived_cash_conversion("NaN", year=2025)],
            )
        ],
    )
    assert derived_result["derived_series"] == []
    assert any(row["code"] == "invalid_derived_value" for row in derived_result["diagnostics"])


def test_derived_input_is_rejected_when_value_basis_is_ambiguous() -> None:
    facts = [
        _filing_fact("net_profit", "100.00", year=2025),
        _filing_fact("net_profit", "90.00", year=2025, value_basis="restated"),
        _filing_fact("operating_cash_flow", "-20.00", year=2025),
    ]
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                facts,
                derived_facts=[_derived_cash_conversion("-20.00", year=2025)],
            )
        ],
    )

    assert len([row for row in result["series"] if row["metric_key"] == "net_profit"]) == 2
    assert result["derived_series"] == []
    assert any(row["code"] == "derived_input_not_accepted" for row in result["diagnostics"])


def test_filing_fact_rejects_unsafe_value_basis_identity() -> None:
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [
                    _filing_fact(
                        "revenue",
                        "1000.00",
                        year=2025,
                        value_basis="as:reported",
                    )
                ],
            )
        ],
    )

    assert result["series"] == []
    assert any(row["code"] == "invalid_value_basis" for row in result["diagnostics"])


def test_derived_input_rejects_mismatched_value_basis_dimensions() -> None:
    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=[
            _fact_pack(
                2025,
                [
                    _filing_fact("net_profit", "100.00", year=2025),
                    _filing_fact(
                        "operating_cash_flow",
                        "80.00",
                        year=2025,
                        value_basis="restated",
                    ),
                ],
                derived_facts=[_derived_cash_conversion("80.00", year=2025)],
            )
        ],
    )

    assert result["derived_series"] == []
    assert any(
        row["code"] == "derived_input_dimension_mismatch"
        for row in result["diagnostics"]
    )


def test_derived_series_never_mix_value_basis_across_years() -> None:
    packs = []
    for year, basis, net_profit, operating_cash_flow in (
        (2024, "as_reported", "100.00", "80.00"),
        (2025, "restated", "120.00", "90.00"),
    ):
        packs.append(_fact_pack(
            year,
            [
                _filing_fact("net_profit", net_profit, year=year, value_basis=basis),
                _filing_fact(
                    "operating_cash_flow",
                    operating_cash_flow,
                    year=year,
                    value_basis=basis,
                ),
            ],
            derived_facts=[
                _derived_cash_conversion(
                    "80.00" if year == 2024 else "75.00",
                    year=year,
                )
            ],
        ))

    result = build_periodic_report_metric_series_pack(
        stock_code="300001",
        stock_name="测试股份",
        fact_packs=packs,
    )

    assert len(result["derived_series"]) == 2
    assert {
        (row["value_basis"], row["series_id"])
        for row in result["derived_series"]
    } == {
        (
            "as_reported",
            "periodic-derived-series:300001:annual:"
            "operating_cash_flow_to_net_profit:as_reported:cash_conversion.v1:pct",
        ),
        (
            "restated",
            "periodic-derived-series:300001:annual:"
            "operating_cash_flow_to_net_profit:restated:cash_conversion.v1:pct",
        ),
    }
