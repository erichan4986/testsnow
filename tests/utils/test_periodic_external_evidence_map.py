from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_display import build_curated_external_argument_display
from external_narrative_plan import deterministic_narrative_plan
from external_pack import (
    build_external_argument_pack_v4,
    external_selection_batches_v4,
    prepare_external_argument_material_v4,
)
from external_source_document import build_external_source_document
from periodic_external_evidence_map import build_periodic_external_evidence_map
from periodic_report_financial_scan import build_periodic_report_financial_scan_pack
from periodic_report_metric_series import build_periodic_report_metric_series_pack


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fact(metric: str, value: str, *, year: int, report_type: str = "annual", basis: str = "as_reported") -> dict:
    block_id = f"financial-{metric}-{year}-{basis}"
    source = f"{metric}:{value}:{year}:{basis}"
    source_doc = f"测试股_{year}_{report_type}_{basis}.txt"
    return {
        "schema_version": "periodic_report_structured_fact.v1",
        "source_type": "periodic_report_filing_fact",
        "fact_id": f"periodic:300001:{year}:{report_type}:{metric}",
        "stock_code": "300001",
        "stock_name": "测试股",
        "report_year": year,
        "report_type": report_type,
        "metric_key": metric,
        "period": str(year),
        "value": f"{value}万元",
        "normalized_value": f"{value}万元",
        "unit": "万元",
        "currency": "CNY",
        "value_basis": basis,
        "source_doc": source_doc,
        "source_block_id": block_id,
        "evidence_refs": [block_id],
        "source_excerpt": source,
        "source_excerpt_hash": _sha(source),
        "source_block_hash": _sha(f"block:{source}"),
    }


def _periodic_inputs(values: dict[int, dict[str, str]], *, report_type: str = "annual") -> tuple[dict, dict]:
    packs = []
    for year, metrics in values.items():
        facts = [_fact(metric, value, year=year, report_type=report_type) for metric, value in metrics.items()]
        packs.append({
            "schema_version": "periodic_report_structured_fact.v1",
            "stock_code": "300001",
            "stock_name": "测试股",
            "report_year": year,
            "report_type": report_type,
            "source_doc": f"测试股_{year}_{report_type}_as_reported.txt",
            "filing_facts": facts,
            "derived_facts": [],
            "filing_risk_signals": [],
            "diagnostics": [],
        })
    metric = build_periodic_report_metric_series_pack(
        stock_code="300001", stock_name="测试股", fact_packs=packs,
    )
    scan = build_periodic_report_financial_scan_pack(
        stock_code="300001", stock_name="测试股", metric_series_pack=metric,
    )
    return metric, scan


def _display(content: str, *, source_id: str = "source:test", title: str = "测试股经营跟踪") -> dict:
    document = build_external_source_document({
        "source_id": source_id,
        "stock_name": "测试股",
        "title": title,
        "account": "测试媒体",
        "publish_time": "2026-07-08 10:00",
        "source_kind": "media",
        "source_ref": f"https://example.test/{source_id}",
        "source_url": f"https://example.test/{source_id}",
        "content": content,
    })
    prepared = prepare_external_argument_material_v4(
        [document], stock_name="测试股", baseline_text="",
    )
    selections = [{
        "schema_version": "curated_external_unit_selection.v2",
        "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": ""}
            for unit in batch
        ],
    } for batch in external_selection_batches_v4(prepared["peer_units"])]
    pack = build_external_argument_pack_v4(
        [document], stock_name="测试股", baseline_text="", selections=selections,
        prepared_material=prepared,
    )
    pack["narrative_plan"] = deterministic_narrative_plan(pack)
    result = build_curated_external_argument_display(pack, expected_stock_name="测试股")
    assert result["status"] == "ok"
    return result["display"]


def _map(content: str, values: dict[int, dict[str, str]], **display_kwargs) -> dict:
    metric, scan = _periodic_inputs(values)
    return build_periodic_external_evidence_map(
        stock_code="300001",
        stock_name="测试股",
        metric_series_pack=metric,
        financial_scan_pack=scan,
        validated_external_display=_display(content, **display_kwargs),
    )


def test_invalid_or_mismatched_inputs_return_complete_unavailable_pack() -> None:
    metric, scan = _periodic_inputs({2025: {"revenue": "100000.00"}})
    display = _display("测试股2025年营业收入10亿元。")
    stale_scan = copy.deepcopy(scan)
    stale_scan["source_point_count"] += 1

    result = build_periodic_external_evidence_map(
        stock_code="300001",
        stock_name="测试股",
        metric_series_pack=metric,
        financial_scan_pack=stale_scan,
        validated_external_display=display,
    )

    assert result["status"] == "unavailable"
    assert result["mappings"] == []
    assert result["observations"] == []
    assert result["report_eligible"] is False
    assert result["scoring_eligible"] is False
    assert result["risk_score_eligible"] is False
    assert result["diagnostics"] == [{"code": "financial_scan_mismatch"}]


def test_duplicate_external_unit_identity_fails_closed() -> None:
    metric, scan = _periodic_inputs({2025: {"revenue": "100000.00"}})
    display = _display("测试股2025年营业收入10亿元。")
    card = display["_curated_external_argument_cards"][0]
    card["evidence_units"].append(copy.deepcopy(card["evidence_units"][0]))

    result = build_periodic_external_evidence_map(
        stock_code="300001", stock_name="测试股", metric_series_pack=metric,
        financial_scan_pack=scan, validated_external_display=display,
    )

    assert result["status"] == "unavailable"
    assert result["diagnostics"] == [{"code": "external_display_duplicate_unit_id"}]


def test_map_output_contains_no_external_prose_or_consumer_authority() -> None:
    result = _map(
        "测试股2025年营业收入10亿元。",
        {2025: {"revenue": "100000.00"}},
    )

    def all_keys(value):
        if isinstance(value, dict):
            return set(value).union(*(all_keys(child) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(all_keys(child) for child in value)) if value else set()
        return set()

    assert not (all_keys(result) & {"text", "content", "title", "url", "source_excerpt"})
    assert result["report_eligible"] is False
    assert result["scoring_eligible"] is False
    assert result["risk_score_eligible"] is False
    assert all(row["report_eligible"] is False for row in result["mappings"])


def test_valid_display_without_target_financial_units_is_empty() -> None:
    result = _map(
        "测试股2026年产品完成客户导入。",
        {2025: {"revenue": "100000.00"}},
    )

    assert result["status"] == "empty"
    assert result["target_unit_count"] == 1
    assert result["target_financial_unit_count"] == 0
    assert result["typed_observation_count"] == 0


def test_peer_and_target_with_peer_cards_never_map_to_target_facts() -> None:
    peer = _map(
        "华工科技2025年营业收入10亿元。",
        {2025: {"revenue": "100000.00"}},
        title="行业公司对比",
    )
    comparative = _map(
        "测试股相比华工科技2025年营业收入10亿元。",
        {2025: {"revenue": "100000.00"}},
    )

    assert peer["observations"] == peer["mappings"] == []
    assert comparative["observations"] == comparative["mappings"] == []


def test_period_and_forecast_context_flow_only_inside_one_card() -> None:
    result = _map(
        "测试股于7月7日披露2026年半年度业绩预告。营业收入预计22至24亿元，同比增长19.64%至30.52%。",
        {2025: {"revenue": "180000.00"}},
    )

    observations = result["observations"]
    assert len(observations) == 2
    assert {row["value_kind"] for row in observations} == {"amount", "growth_rate"}
    assert all(row["report_year"] == 2026 and row["report_type"] == "semiannual" for row in observations)
    assert all(row["period_origin"] == "card_context" for row in observations)
    assert all(row["modality"] == "forecast" for row in observations)
    amount = next(row for row in observations if row["value_kind"] == "amount")
    assert (amount["lower_value"], amount["upper_value"], amount["unit"], amount["is_range"]) == (
        "220000.00", "240000.00", "万元", True,
    )


def test_period_context_does_not_cross_external_cards() -> None:
    result = _map(
        "测试股披露2026年年度业绩预告。测试股产品完成客户导入。营业收入预计12亿元。",
        {2025: {"revenue": "100000.00"}},
    )

    assert result["observations"] == []
    assert result["status"] == "partial"
    assert result["diagnostics"] == [{"code": "period_missing", "unit_id": result["unmapped_observations"][0]["unit_id"]}]


def test_explicit_reported_language_resets_inherited_forecast_modality() -> None:
    result = _map(
        "测试股披露2025年年度业绩预告。营业收入预计9至11亿元。公司实际实现营业收入10亿元。",
        {2025: {"revenue": "100000.00"}},
    )

    modalities = [row["modality"] for row in result["observations"] if row["value_kind"] == "amount"]
    assert modalities == ["forecast", "reported"]


def test_forecast_phrase_containing_realize_remains_forecast() -> None:
    result = _map(
        "测试股预计实现2025年营业收入10亿元。",
        {2025: {"revenue": "100000.00"}},
    )

    assert result["observations"][0]["modality"] == "forecast"


def test_period_and_modality_context_do_not_cross_source_blocks() -> None:
    metric, scan = _periodic_inputs({2025: {"revenue": "100000.00"}})
    display = _display("测试股披露2025年度业绩预告。营业收入预计10亿元。")
    units = display["_curated_external_argument_cards"][0]["evidence_units"]
    units[1]["block_id"] = "source:test:block:1"

    result = build_periodic_external_evidence_map(
        stock_code="300001", stock_name="测试股", metric_series_pack=metric,
        financial_scan_pack=scan, validated_external_display=display,
    )

    assert result["observations"] == []
    assert result["unmapped_observations"][0]["reason"] == "period_missing"


def test_decline_and_loss_language_preserve_negative_numeric_direction() -> None:
    result = _map(
        "测试股2025年营业收入10亿元，同比下降25%；归母净利润亏损2亿元。",
        {
            2024: {"revenue": "133333.33", "net_profit": "10000.00"},
            2025: {"revenue": "100000.00", "net_profit": "-20000.00"},
        },
    )

    by_identity = {
        (row["metric_key"], row["value_kind"]): row
        for row in result["observations"]
    }
    assert by_identity[("revenue", "growth_rate")]["lower_value"] == "-25.00"
    assert by_identity[("net_profit", "amount")]["lower_value"] == "-20000.00"


def test_one_unit_can_yield_two_metrics_and_growth_without_cross_assignment() -> None:
    result = _map(
        "测试股2025年营业收入10亿元，同比增长25%；归母净利润2亿元，同比增长10%。",
        {
            2024: {"revenue": "80000.00", "net_profit": "18181.82"},
            2025: {"revenue": "100000.00", "net_profit": "20000.00"},
        },
    )

    identity = {(row["metric_key"], row["value_kind"], row["lower_value"]) for row in result["observations"]}
    assert identity == {
        ("revenue", "amount", "100000.00"),
        ("revenue", "growth_rate", "25.00"),
        ("net_profit", "amount", "20000.00"),
        ("net_profit", "growth_rate", "10.00"),
    }


def test_generic_metrics_foreign_currency_and_reversed_ranges_are_not_typed() -> None:
    result = _map(
        "测试股2025年收入10亿元，利润2亿元。测试股2025年营业收入10亿港元。测试股2025年归母净利润3至2亿元。",
        {2025: {"revenue": "100000.00", "net_profit": "20000.00"}},
    )

    assert result["observations"] == []
    assert result["mappings"] == []
    assert result["status"] == "partial"


@pytest.mark.parametrize(
    ("external", "filing_value", "relation", "basis", "bounds"),
    [
        ("382.4亿元", "3824000.00", "confirm", "reported_scalar_matches_filing", ("3823500.00", "3824500.00")),
        ("382.4亿元", "3824400.00", "confirm", "reported_scalar_matches_filing", ("3823500.00", "3824500.00")),
        ("382.4亿元", "3825000.00", "contradict", "reported_scalar_differs_from_filing", ("3823500.00", "3824500.00")),
        ("382至383亿元", "3824000.00", "confirm", "reported_range_contains_filing", ("3820000.00", "3830000.00")),
        ("380至381亿元", "3824000.00", "contradict", "reported_range_excludes_filing", ("3800000.00", "3810000.00")),
    ],
)
def test_same_period_amount_relations_respect_source_precision(
    external, filing_value, relation, basis, bounds,
) -> None:
    result = _map(
        f"测试股2025年实际实现营业收入{external}。",
        {2025: {"revenue": filing_value}},
    )

    assert result["status"] == "ready"
    assert len(result["mappings"]) == 1
    mapping = result["mappings"][0]
    assert (mapping["relation"], mapping["relation_basis"]) == (relation, basis)
    assert (mapping["external_lower_value"], mapping["external_upper_value"]) == bounds
    assert mapping["target_kind"] == "filing_point"
    assert mapping["adjudication"] == "none"
    assert mapping["official_fact_mutated"] is False


def test_same_period_forecast_range_records_forecast_compatibility() -> None:
    result = _map(
        "测试股披露2025年年度业绩预告。营业收入预计9至11亿元。",
        {2025: {"revenue": "100000.00"}},
    )

    mapping = result["mappings"][0]
    assert mapping["relation"] == "confirm"
    assert mapping["relation_basis"] == "forecast_range_contains_filing"


@pytest.mark.parametrize(
    ("rate", "relation", "basis"),
    [
        ("25%", "confirm", "reported_scalar_matches_filing"),
        ("24%", "contradict", "reported_scalar_differs_from_filing"),
    ],
)
def test_same_period_growth_maps_to_the_exact_metric_change(rate, relation, basis) -> None:
    result = _map(
        f"测试股2025年营业收入10亿元，同比增长{rate}。",
        {2024: {"revenue": "80000.00"}, 2025: {"revenue": "100000.00"}},
    )

    growth_mapping = next(row for row in result["mappings"] if row["target_kind"] == "metric_change")
    assert (growth_mapping["relation"], growth_mapping["relation_basis"]) == (relation, basis)
    assert growth_mapping["target_periods"] == ["2024", "2025"]
    assert growth_mapping["target_value"] == "25.00"
    assert growth_mapping["unit"] == "pct"


def test_newer_period_is_update_without_cross_period_value_comparison() -> None:
    result = _map(
        "测试股2026年半年度营业收入6亿元，同比增长20%。",
        {2025: {"revenue": "100000.00"}},
    )

    assert {row["relation"] for row in result["mappings"]} == {"update"}
    assert all(row["relation_basis"] == "newer_period_observation" for row in result["mappings"])
    assert all(row["target_kind"] == "filing_point" for row in result["mappings"])
    assert all(row["target_periods"] == ["2025"] for row in result["mappings"])


@pytest.mark.parametrize(
    "external",
    [
        "测试股2025年半年度营业收入6亿元。",
        "测试股2024年营业收入6亿元。",
    ],
)
def test_noncomparable_or_stale_periods_remain_unmapped(external) -> None:
    result = _map(external, {2025: {"revenue": "100000.00"}})

    assert result["mappings"] == []
    assert result["unmapped_observations"]


def test_multiple_filing_value_bases_fail_closed() -> None:
    as_reported, _ = _periodic_inputs({2025: {"revenue": "100000.00"}})
    restated_fact = _fact("revenue", "101000.00", year=2025, basis="restated")
    restated_pack = {
        "schema_version": "periodic_report_structured_fact.v1",
        "stock_code": "300001", "stock_name": "测试股", "report_year": 2025,
        "report_type": "annual", "source_doc": "测试股_2025_annual_restated.txt",
        "filing_facts": [restated_fact], "derived_facts": [],
        "filing_risk_signals": [], "diagnostics": [],
    }
    restated = build_periodic_report_metric_series_pack(
        stock_code="300001", stock_name="测试股", fact_packs=[restated_pack],
    )
    source = copy.deepcopy(as_reported)
    source["series"].extend(restated["series"])
    scan = build_periodic_report_financial_scan_pack(
        stock_code="300001", stock_name="测试股", metric_series_pack=source,
    )

    result = build_periodic_external_evidence_map(
        stock_code="300001", stock_name="测试股", metric_series_pack=source,
        financial_scan_pack=scan,
        validated_external_display=_display("测试股2025年营业收入10亿元。"),
    )

    assert result["mappings"] == []
    assert result["unmapped_observations"][0]["reason"] == "ambiguous_value_basis"


def test_growth_mapping_links_the_exact_financial_scan_finding() -> None:
    result = _map(
        "测试股2025年营业收入11亿元，同比增长10%。",
        {
            2024: {"revenue": "100000.00", "net_profit": "10000.00"},
            2025: {"revenue": "110000.00", "net_profit": "9000.00"},
        },
    )

    amount = next(row for row in result["mappings"] if row["target_kind"] == "filing_point")
    growth = next(row for row in result["mappings"] if row["target_kind"] == "metric_change")
    assert amount["linked_finding_ids"] == []
    assert len(growth["linked_finding_ids"]) == 1
    assert "revenue_growth_profit_contraction" in growth["linked_finding_ids"][0]
    assert result["finding_link_count"] == 1


def test_mapping_output_is_deterministic_under_canonical_collection_order() -> None:
    metric, scan = _periodic_inputs({
        2024: {"revenue": "80000.00", "net_profit": "18000.00"},
        2025: {"revenue": "100000.00", "net_profit": "20000.00"},
    })
    display = _display("测试股2025年营业收入10亿元，同比增长25%；归母净利润2亿元。")
    baseline = build_periodic_external_evidence_map(
        stock_code="300001", stock_name="测试股", metric_series_pack=metric,
        financial_scan_pack=scan, validated_external_display=display,
    )
    reordered_metric = copy.deepcopy(metric)
    reordered_metric["series"].reverse()
    reordered_display = copy.deepcopy(display)
    reordered_display["_curated_external_argument_cards"].reverse()
    for card in reordered_display["_curated_external_argument_cards"]:
        card["evidence_units"].reverse()
    reordered_display["citations"] = dict(reversed(list(reordered_display["citations"].items())))

    assert build_periodic_external_evidence_map(
        stock_code="300001", stock_name="测试股", metric_series_pack=reordered_metric,
        financial_scan_pack=scan, validated_external_display=reordered_display,
    ) == baseline
