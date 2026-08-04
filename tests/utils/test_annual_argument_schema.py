"""Tests for the annual narrative argument v2 schema owner."""

import copy
import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import annual_argument_schema as schema

from annual_argument_schema import (
    ANNUAL_CHECKBOX_MARKER_RUN_RE,
    CANONICAL_FAMILIES,
    CARD_SCHEMA_VERSION,
    ENVELOPE_SCHEMA_VERSION,
    FAMILY_LABELS,
    SELECTION_VERSION,
    SOURCE_UNIT_DECISIONS_VERSION,
    adapt_v1_card,
    annual_source_tail,
    is_v1_card,
    validate_card_v2,
    validate_source_unit,
)


def _legacy_card(**overrides):
    card = {
        "card_id": "legacy:1",
        "card_type": "rd_product_progress",
        "title": "研发与产品进展",
        "source_block_id": "rd-0",
        "source_excerpt": "A2000芯片已进入客户验证阶段。",
        "quality_score": 3,
        "report_year": 2025,
        "report_type": "annual",
    }
    card.update(overrides)
    return card


def test_versions_families_and_labels_are_locked():
    assert CARD_SCHEMA_VERSION == "periodic_report_narrative_evidence_card.v2"
    assert ENVELOPE_SCHEMA_VERSION == "periodic_report_narrative_evidence_cards.v2"
    assert SELECTION_VERSION == "annual_argument_selection.v2"
    assert SOURCE_UNIT_DECISIONS_VERSION == "annual_source_unit_decisions.v1"
    assert CANONICAL_FAMILIES == (
        "business_structure",
        "operating_progress",
        "market_competition_outlook",
        "technology_product_progress",
        "financial_quality_explanation",
    )
    assert FAMILY_LABELS == {
        "business_structure": "业务结构",
        "operating_progress": "经营变化",
        "market_competition_outlook": "管理层判断与行业展望",
        "technology_product_progress": "技术与产品进展",
        "financial_quality_explanation": "财务质量与变化原因",
    }


def test_v1_adapter_is_read_only_and_uses_legacy_proxy_unit():
    legacy = _legacy_card(source_excerpt="A2000芯片已进入\n\n客户验证阶段。")
    original = copy.deepcopy(legacy)
    normalized_excerpt = re.sub(r"\s+", " ", legacy["source_excerpt"]).strip()
    expected_unit_id = (
        f"{legacy['source_block_id']}:legacy:"
        f"{hashlib.sha256(normalized_excerpt.encode('utf-8')).hexdigest()}"
    )
    raw_unit_id = (
        f"{legacy['source_block_id']}:legacy:"
        f"{hashlib.sha256(legacy['source_excerpt'].encode('utf-8')).hexdigest()}"
    )

    card = adapt_v1_card(legacy)

    assert legacy == original
    assert card["schema_version"] == CARD_SCHEMA_VERSION
    assert card["selection_version"] == SELECTION_VERSION
    assert card["argument_family"] == "technology_product_progress"
    assert card["argument_complete"] is False
    assert card["selection_reason"] == "legacy_v1_adapter"
    assert card["source_type"] == "periodic_report_narrative_evidence"
    assert card["source_credit"] == 75
    assert "card_type" not in card
    assert expected_unit_id != raw_unit_id
    assert card["source_unit_ids"] == [expected_unit_id]
    assert card["source_unit_ids"] != [raw_unit_id]
    assert card["source_unit_ids"] == [card["source_units"][0]["unit_id"]]
    assert card["source_excerpt"] == legacy["source_excerpt"]
    assert card["source_units"][0]["text"] == legacy["source_excerpt"]
    assert card["source_units"] == [{
        "unit_id": card["source_unit_ids"][0],
        "block_id": "rd-0",
        "ordinal": 0,
        "start_pos": 0,
        "end_pos": len(legacy["source_excerpt"]),
        "text": legacy["source_excerpt"],
    }]
    assert ":legacy:" in card["source_unit_ids"][0]
    assert validate_card_v2(card) == ()


def test_v1_adapter_maps_margin_cards_by_metric_and_causal_token():
    financial = adapt_v1_card(_legacy_card(
        card_type="margin_competitiveness",
        source_excerpt="毛利率同比提升2个百分点，主要系产品结构改善。",
    ))
    outlook = adapt_v1_card(_legacy_card(
        card_type="margin_competitiveness",
        source_excerpt="毛利率承压，但公司客户覆盖和交付能力保持竞争优势。",
    ))

    assert financial["argument_family"] == "financial_quality_explanation"
    assert outlook["argument_family"] == "market_competition_outlook"


def test_is_v1_card_accepts_only_supported_legacy_card_mappings():
    assert is_v1_card({"card_type": "business_model"})
    assert is_v1_card({"card_type": "margin_competitiveness", "schema_version": "legacy.v1"})
    assert not is_v1_card({"card_type": "business_model", "schema_version": CARD_SCHEMA_VERSION})
    assert not is_v1_card({"card_type": "unknown"})
    assert not is_v1_card({})
    assert not is_v1_card(["business_model"])


def test_v1_adapter_maps_each_non_margin_legacy_type():
    mappings = {
        "business_model": "business_structure",
        "operation_update": "operating_progress",
        "management_market_view": "market_competition_outlook",
        "market_outlook": "market_competition_outlook",
        "technology_platform": "technology_product_progress",
        "rd_product_progress": "technology_product_progress",
        "financial_note": "financial_quality_explanation",
    }

    for legacy_type, expected_family in mappings.items():
        card = adapt_v1_card(_legacy_card(card_type=legacy_type))
        assert card["argument_family"] == expected_family


def test_v1_adapter_returns_canonical_fields_without_mutable_aliases():
    legacy = _legacy_card(
        fact_anchors=[{"name": "A2000"}],
        secondary_signals=[{"name": "customer_validation"}],
        score_parts={"anchor": {"score": 3}},
        unknown_legacy_metadata={"keep": "out"},
    )

    card = adapt_v1_card(legacy)

    assert set(card) == {
        "schema_version",
        "selection_version",
        "card_id",
        "argument_family",
        "argument_complete",
        "title",
        "source_block_id",
        "source_unit_ids",
        "source_units",
        "source_excerpt",
        "fact_anchors",
        "secondary_signals",
        "score_parts",
        "quality_score",
        "selection_reason",
        "source_type",
        "source_credit",
        "report_year",
        "report_type",
    }
    card["fact_anchors"][0]["name"] = "changed"
    card["secondary_signals"][0]["name"] = "changed"
    card["score_parts"]["anchor"]["score"] = 0
    assert legacy["fact_anchors"] == [{"name": "A2000"}]
    assert legacy["secondary_signals"] == [{"name": "customer_validation"}]
    assert legacy["score_parts"] == {"anchor": {"score": 3}}


def test_v1_adapter_rejects_empty_or_missing_source_excerpt_for_supported_card():
    missing_excerpt = _legacy_card()
    del missing_excerpt["source_excerpt"]

    for legacy in (_legacy_card(source_excerpt=""), missing_excerpt):
        assert is_v1_card(legacy)
        with pytest.raises(ValueError, match="legacy v1 card requires non-empty source_excerpt"):
            adapt_v1_card(legacy)


def test_v1_adapter_rejects_non_v1_or_post_adaptation_invalid_cards():
    with pytest.raises(ValueError, match="card is not a supported v1 narrative card"):
        adapt_v1_card(_legacy_card(schema_version=CARD_SCHEMA_VERSION))

    with pytest.raises(ValueError, match="adapted v1 card failed v2 validation: invalid_card_signal_lists"):
        adapt_v1_card(_legacy_card(fact_anchors={"not": "a list"}))


def test_validation_rejects_unknown_family_and_mismatched_units():
    card = adapt_v1_card(_legacy_card(card_type="business_model"))
    card["argument_family"] = "old_display_role"
    card["source_unit_ids"] = ["wrong"]

    errors = validate_card_v2(card)

    assert "invalid_argument_family" in errors
    assert "source_unit_ids_mismatch" in errors


def test_validation_rejects_retired_card_type_but_allows_future_fields():
    card = adapt_v1_card(_legacy_card())
    card["card_type"] = "rd_product_progress"
    assert "retired_card_type" in validate_card_v2(card)

    card = adapt_v1_card(_legacy_card())
    card["future_extension"] = "allowed"
    assert validate_card_v2(card) == ()


def test_validation_requires_list_source_unit_ids_and_at_least_one_source_unit():
    card = adapt_v1_card(_legacy_card())

    for source_unit_ids in (tuple(card["source_unit_ids"]), card["source_unit_ids"][0]):
        card["source_unit_ids"] = source_unit_ids
        errors = validate_card_v2(card)
        assert "invalid_source_unit_ids" in errors
        assert "source_unit_ids_mismatch" in errors

    card["source_units"] = []
    card["source_unit_ids"] = []
    assert "missing_source_units" in validate_card_v2(card)


def test_validation_rejects_missing_required_field():
    card = adapt_v1_card(_legacy_card())
    del card["title"]

    assert "missing_card_field" in validate_card_v2(card)


def test_validation_rejects_malformed_required_field_shapes():
    text_fields = {
        "card_id": "",
        "title": [],
        "source_block_id": "",
        "source_excerpt": {},
        "selection_reason": "",
        "source_type": 75,
        "report_type": (),
    }
    for field, value in text_fields.items():
        card = adapt_v1_card(_legacy_card())
        card[field] = value
        assert "invalid_card_text_field" in validate_card_v2(card)

    for field, value in {"fact_anchors": {}, "secondary_signals": ()}.items():
        card = adapt_v1_card(_legacy_card())
        card[field] = value
        assert "invalid_card_signal_lists" in validate_card_v2(card)

    card = adapt_v1_card(_legacy_card())
    card["score_parts"] = []
    assert "invalid_score_parts" in validate_card_v2(card)

    card = adapt_v1_card(_legacy_card())
    card["quality_score"] = True
    assert "invalid_quality_score" in validate_card_v2(card)

    card = adapt_v1_card(_legacy_card())
    card["source_credit"] = "75"
    assert "invalid_source_credit" in validate_card_v2(card)

    for report_year in (True, -1):
        card = adapt_v1_card(_legacy_card())
        card["report_year"] = report_year
        assert "invalid_report_year" in validate_card_v2(card)


def test_validation_rejects_wrong_schema_selection_and_non_bool_completeness():
    card = adapt_v1_card(_legacy_card())
    card["schema_version"] = "periodic_report_narrative_evidence_card.v1"
    card["selection_version"] = "annual_argument_selection.v1"
    card["argument_complete"] = "false"

    errors = validate_card_v2(card)

    assert "invalid_schema_version" in errors
    assert "invalid_selection_version" in errors
    assert "invalid_argument_complete" in errors


def test_validation_rejects_non_monotonic_and_overlapping_source_units():
    card = adapt_v1_card(_legacy_card())
    card["source_units"] = [
        {
            "unit_id": "rd-0:u0",
            "block_id": "rd-0",
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": 4,
            "text": "甲乙丙丁",
        },
        {
            "unit_id": "rd-0:u1",
            "block_id": "rd-0",
            "ordinal": 0,
            "start_pos": 3,
            "end_pos": 7,
            "text": "丁戊己庚",
        },
    ]
    card["source_unit_ids"] = [unit["unit_id"] for unit in card["source_units"]]

    errors = validate_card_v2(card)

    assert "non_monotonic_source_units" in errors
    assert "overlapping_source_units" in errors


def test_validation_rejects_duplicate_or_foreign_source_units():
    card = adapt_v1_card(_legacy_card())
    card["source_units"] = [
        {
            "unit_id": "rd-0:u0",
            "block_id": "rd-0",
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": 4,
            "text": "甲乙丙丁",
        },
        {
            "unit_id": "rd-0:u1",
            "block_id": "rd-0",
            "ordinal": 1,
            "start_pos": 4,
            "end_pos": 8,
            "text": "戊己庚辛",
        },
    ]
    card["source_unit_ids"] = [unit["unit_id"] for unit in card["source_units"]]
    assert validate_card_v2(card) == ()

    duplicate = copy.deepcopy(card)
    duplicate["source_units"][1]["unit_id"] = "rd-0:u0"
    duplicate["source_unit_ids"] = [unit["unit_id"] for unit in duplicate["source_units"]]
    assert "duplicate_source_unit_id" in validate_card_v2(duplicate)

    foreign = copy.deepcopy(card)
    foreign["source_units"][1]["block_id"] = "other-0"
    assert "source_unit_block_id_mismatch" in validate_card_v2(foreign)


def test_validation_enforces_normal_and_legacy_source_unit_id_provenance():
    normal = adapt_v1_card(_legacy_card())
    normal["selection_reason"] = "v2_selector"
    normal["source_units"][0]["unit_id"] = "rd-0:u1"
    normal["source_unit_ids"] = ["rd-0:u1"]
    assert "invalid_source_unit_id_provenance" in validate_card_v2(normal)

    forged_proxy = adapt_v1_card(_legacy_card())
    forged_proxy["selection_reason"] = "v2_selector"
    assert "invalid_source_unit_id_provenance" in validate_card_v2(forged_proxy)

    malformed_proxy = adapt_v1_card(_legacy_card())
    malformed_proxy["source_units"][0]["unit_id"] = "rd-0:legacy:not-a-sha256"
    malformed_proxy["source_unit_ids"] = ["rd-0:legacy:not-a-sha256"]
    assert "invalid_source_unit_id_provenance" in validate_card_v2(malformed_proxy)


def test_validation_rejects_nonstring_source_identity_and_numeric_duplicates():
    card = adapt_v1_card(_legacy_card())
    card["source_units"] = [
        {
            "unit_id": 7,
            "block_id": "rd-0",
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": 4,
            "text": "甲乙丙丁",
        },
        {
            "unit_id": 7,
            "block_id": "rd-0",
            "ordinal": 1,
            "start_pos": 4,
            "end_pos": 8,
            "text": 8,
        },
    ]
    card["source_unit_ids"] = [7, 7]

    errors = validate_card_v2(card)

    assert "invalid_source_unit_text_field" in errors
    assert "invalid_source_unit_ids" in errors
    assert "duplicate_source_unit_id" in errors

    card = adapt_v1_card(_legacy_card())
    card["source_unit_ids"] = [" "]
    assert "invalid_source_unit_ids" in validate_card_v2(card)


def test_source_unit_validation_rejects_missing_non_integer_and_invalid_ranges():
    missing = validate_source_unit({})
    invalid = validate_source_unit({
        "unit_id": "u0",
        "block_id": "b0",
        "ordinal": "0",
        "start_pos": -1,
        "end_pos": 0,
        "text": "text",
    })
    invalid_position = validate_source_unit({
        "unit_id": "u0",
        "block_id": "b0",
        "ordinal": 0,
        "start_pos": "0",
        "end_pos": 4,
        "text": "text",
    })
    negative_ordinal = validate_source_unit({
        "unit_id": "u0",
        "block_id": "b0",
        "ordinal": -1,
        "start_pos": 0,
        "end_pos": 4,
        "text": "text",
    })

    assert "missing_source_unit_field" in missing
    assert "invalid_source_unit_ordinal" in invalid
    assert "invalid_source_unit_range" in invalid
    assert "invalid_source_unit_position" in invalid_position
    assert "invalid_source_unit_ordinal" in negative_ordinal


def test_source_unit_validation_requires_nonblank_identity_strings():
    normal = {
        "unit_id": "b0:u0",
        "block_id": "b0",
        "ordinal": 0,
        "start_pos": 0,
        "end_pos": 4,
        "text": "正文内容",
    }
    assert validate_source_unit(normal) == ()

    for field, value in {"unit_id": 1, "block_id": " ", "text": 3}.items():
        invalid = dict(normal, **{field: value})
        assert "invalid_source_unit_text_field" in validate_source_unit(invalid)


EXPECTED_USAGE_FAMILIES = {
    "business_overview": "business_structure",
    "business_model": "business_structure",
    "product_capacity_profile": "business_structure",
    "sales_certification_model": "business_structure",
    "hk_business_overview": "business_structure",
    "hk_customer_ecosystem": "business_structure",
    "segment_table": "operating_progress",
    "production_sales_inventory_table": "operating_progress",
    "management_strategy": "operating_progress",
    "management_market_view": "market_competition_outlook",
    "industry_outlook": "market_competition_outlook",
    "market_demand_outlook": "market_competition_outlook",
    "competitive_position": "market_competition_outlook",
    "future_strategy": "market_competition_outlook",
    "hk_market_outlook": "market_competition_outlook",
    "rd_product_progress": "technology_product_progress",
    "rd_table": "technology_product_progress",
    "rd_investment_table": "technology_product_progress",
    "hk_product_progress": "technology_product_progress",
    "profitability_commentary": "financial_quality_explanation",
    "hk_financial_commentary": "financial_quality_explanation",
    "cash_flow_capex_table": "financial_quality_explanation",
    "asset_impairment_note": "financial_quality_explanation",
    "ar_aging_note": "financial_quality_explanation",
    "inventory_note": "financial_quality_explanation",
    "audit_key_matters": "financial_quality_explanation",
    "government_grant_note": "financial_quality_explanation",
    "financial_assets_note": "financial_quality_explanation",
    "goodwill_note": "financial_quality_explanation",
}


def test_usage_metadata_replaces_the_former_producer_fallback_map():
    from annual_argument_schema import (
        USAGE_FAMILY_METADATA,
        canonical_family_for_usage,
        is_high_value_narrative_usage,
    )

    assert {
        usage: canonical_family_for_usage(usage)
        for usage in EXPECTED_USAGE_FAMILIES
    } == EXPECTED_USAGE_FAMILIES
    assert set(USAGE_FAMILY_METADATA) == set(EXPECTED_USAGE_FAMILIES)
    assert canonical_family_for_usage("unmapped_usage") is None
    assert is_high_value_narrative_usage("business_overview")
    assert not is_high_value_narrative_usage("segment_table")


def test_shared_normalization_and_anchor_gate_are_deterministic():
    from annual_argument_schema import (
        has_concrete_annual_anchor,
        normalize_annual_source_text,
    )

    assert normalize_annual_source_text("  2025 年\n客户付款形式变更。 ") == "2025 年 客户付款形式变更。"
    assert has_concrete_annual_anchor("2025 年客户付款形式变更为电汇。")
    assert has_concrete_annual_anchor("SESAMEX 平台提供机器人方案。")
    assert not has_concrete_annual_anchor("持续提升核心竞争力。")


def test_annual_source_tail_accepts_one_complete_checkbox_tail_only():
    complete = (
        "现金流变动情况 √适用 □不适用 2025年客户付款形式变更为电汇，"
        "主要系经营活动现金流增加所致。"
    )

    assert ANNUAL_CHECKBOX_MARKER_RUN_RE.search(complete)
    assert annual_source_tail(complete) == (
        "2025年客户付款形式变更为电汇，主要系经营活动现金流增加所致。"
    )
    assert annual_source_tail("事项一 √适用 □不适用 事项二 √适用 □不适用 现金流增加。") is None
    assert annual_source_tail("事项 √适用 □不适用 现金流增加") is None


def test_annual_source_tail_extracts_mid_unit_page_header_without_total_pages():
    text = (
        "3、云技术在EDA领域的应用日趋深入 华大九天科技股份有限公司 "
        "2025年年度报告全文 > 38 随着EDA云平台成熟，芯片设计流程迁移至云端已成为明显趋势。"
    )

    assert annual_source_tail(text) == (
        "随着EDA云平台成熟，芯片设计流程迁移至云端已成为明显趋势。"
    )


def test_annual_source_tail_rejects_text_spanning_multiple_page_headers():
    text = (
        "某公司2025年年度报告全文 > 38 第一页完整事实。"
        "某公司2025年年度报告全文 > 39 第二页完整事实。"
    )

    assert annual_source_tail(text) is None


@pytest.mark.parametrize(
    "text, expected",
    (
        (
            "现金流变动情况 √适用 □不适用 2025年客户付款形式变更为电汇，主要系经营活动现金流增加所致。",
            "2025年客户付款形式变更为电汇，主要系经营活动现金流增加所致。",
        ),
        (
            "17/258 中简科技股份有限公司 2025年年度报告全文 2、生产模式 因公司产品主要用于航空航天领域，性能参数不会发生改变。",
            "因公司产品主要用于航空航天领域，性能参数不会发生改变。",
        ),
        (
            "2、生产模式 因公司产品主要用于航空航天领域，性能参数不会发生改变。",
            "因公司产品主要用于航空航天领域，性能参数不会发生改变。",
        ),
        (
            "2、生产模式 9 中简科技股份有限公司2025年年度报告全文 因公司产品主要用于航空航天领域，性能参数不会发生改变。",
            "因公司产品主要用于航空航天领域，性能参数不会发生改变。",
        ),
        (
            "报告期内公司经营活动产生的现金净流量与本年度净利润存在重大差异的原因说明 2025年四季度客户付款形式由航信变动为电汇支付，导致两者存在较大差异。",
            "2025年四季度客户付款形式由航信变动为电汇支付，导致两者存在较大差异。",
        ),
    ),
)
def test_annual_source_tail_recognizes_only_locked_structural_prefixes(text, expected):
    normalized = schema.normalize_annual_source_text(text)
    tail = schema.annual_source_tail(text)

    assert tail == expected
    assert normalized.find(tail) >= 0
    assert tail.endswith(("。", "；", ";", "！", "？", "!", "?"))


@pytest.mark.parametrize(
    "text",
    (
        "任意前缀 2025年客户付款形式变更为电汇支付。",
        "事项一 √适用 □不适用 事项二 √适用 □不适用 现金流增加。",
        "现金流变动情况 √适用 □不适用 2025年客户付款形式变更为电汇支付",
        "2、生产模式 因公司产品主要用于航空航天领域，性能参数不会发生改变",
        "2、生产模式 3、销售模式 公司产品直接面向客户销售。",
    ),
)
def test_annual_source_tail_rejects_unlocked_or_incomplete_prefixes(text):
    assert schema.annual_source_tail(text) is None
