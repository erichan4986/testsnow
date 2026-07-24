from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_coverage_manifest import (  # noqa: E402
    COORDINATE_SPACE,
    SCHEMA_VERSION,
    build_periodic_report_coverage_manifest,
    finalize_periodic_report_coverage_manifest,
    validate_periodic_report_coverage_manifest,
)


def _build(text: str) -> dict:
    return build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[],
        prioritized_candidates=[],
        selected_blocks=[],
    )


def _assert_no_source_payload(value: object) -> None:
    if isinstance(value, dict):
        assert not ({"text", "source_excerpt", "source_units"} & set(value))
        for child in value.values():
            _assert_no_source_payload(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_source_payload(child)


def test_markdown_sections_keep_source_order_and_document_style() -> None:
    text = (
        "# 2025 年年度报告\n"
        "公司年度经营情况概览。\n"
        "## 管理层讨论与分析\n"
        "公司主营芯片设计并服务汽车客户。\n"
        "## 财务报告\n"
        "营业收入为100亿元，净利润为10亿元。\n"
    )

    manifest = _build(text)

    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["coordinate_space"] == COORDINATE_SPACE
    assert manifest["stage"] == "evidence"
    assert manifest["status"] == "ready"
    assert manifest["document_style"] == "a_share_annual"
    assert [section["heading"] for section in manifest["sections"]] == [
        "2025 年年度报告",
        "管理层讨论与分析",
        "财务报告",
    ]
    assert [section["heading_level"] for section in manifest["sections"]] == [1, 2, 2]
    starts = [section["source_span"]["start"] for section in manifest["sections"]]
    assert starts == sorted(starts)
    assert validate_periodic_report_coverage_manifest(manifest) == ()


def test_hkex_markdown_sections_do_not_require_a_share_headings() -> None:
    text = (
        "# 2025 年報\n本集團全年業務摘要及重要事項。\n"
        "## 管理層討論及分析\n本集團推出新平台並拓展客戶。\n"
        "## 綜合財務報表\n本年度收入及毛利均有所增長。\n"
    )
    manifest = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="hkex_annual",
        extracted_candidates=[],
        prioritized_candidates=[],
        selected_blocks=[],
    )

    assert manifest["document_style"] == "hkex_annual"
    assert [section["heading"] for section in manifest["sections"]] == [
        "2025 年報",
        "管理層討論及分析",
        "綜合財務報表",
    ]
    assert validate_periodic_report_coverage_manifest(manifest) == ()


def test_duplicate_heading_names_keep_distinct_full_hash_ids() -> None:
    manifest = _build(
        "# 年度报告\n正文内容足够长用于分析。\n"
        "## 其他事项\n第一处其他事项包含完整说明。\n"
        "## 其他事项\n第二处其他事项包含不同说明。\n"
    )
    duplicate_sections = [
        section for section in manifest["sections"] if section["heading"] == "其他事项"
    ]

    assert len(duplicate_sections) == 2
    assert duplicate_sections[0]["section_id"] != duplicate_sections[1]["section_id"]
    assert all(section["section_id"].startswith("section:") for section in duplicate_sections)
    assert all(len(section["section_id"].removeprefix("section:")) == 64 for section in duplicate_sections)


def test_no_heading_uses_one_synthetic_document_root() -> None:
    manifest = _build("公司主营芯片设计，报告期内实现收入增长。")

    assert manifest["sections"] == [{
        "section_id": manifest["sections"][0]["section_id"],
        "heading": "document-root",
        "heading_level": 0,
        "source_span": {"start": 0, "end": len("公司主营芯片设计，报告期内实现收入增长。")},
        "page_start": None,
        "page_end": None,
        "matched_coverage_block_ids": [],
        "coverage_state": "unmapped",
    }]
    assert len(manifest["sections"][0]["section_id"].removeprefix("section:")) == 64


def test_short_synthetic_root_remains_unmapped_and_whitespace_is_unavailable() -> None:
    short = _build("主营芯片。")
    whitespace = _build(" \n\t")
    headings_only = _build("# 年度报告\n## 管理层讨论与分析\n")

    assert short["sections"][0]["coverage_state"] == "unmapped"
    assert short["analysis_coverage_status"] == "partial"
    assert whitespace["status"] == "unavailable"
    assert whitespace["unavailable_reason"] == "empty_document"
    assert headings_only["analysis_coverage_status"] == "partial"


def test_empty_parent_heading_is_structural_only_not_unresolved() -> None:
    manifest = _build(
        "# 年度报告\n年度报告正文摘要足够长。\n"
        "## 管理层讨论与分析\n"
        "### 主营业务\n公司主营高端芯片并服务汽车客户。\n"
    )
    parent = next(section for section in manifest["sections"] if section["heading"] == "管理层讨论与分析")

    assert parent["coverage_state"] == "structural_only"
    assert manifest["summary"]["section_states"]["structural_only"] == 1
    assert manifest["summary"]["unresolved_section_count"] == 2


def test_explicit_report_page_marker_is_accepted_but_toc_number_is_not() -> None:
    text = (
        "# 目录\n7 管理层讨论及分析\n目录说明文字足够长。\n"
        "7 2025 年年度报告 公司名称\n"
        "## 管理层讨论及分析\n公司主营业务保持稳定增长。\n"
        "## 财务报告\n营业收入和净利润均已披露。\n"
    )
    manifest = _build(text)
    management, financial = manifest["sections"][1:]

    assert management["page_start"] == 7
    assert management["page_end"] is None
    assert financial["page_start"] is None
    assert financial["page_end"] is None
    assert manifest["page_locator_status"] == "partial"


def test_identical_input_produces_identical_manifest_without_source_payload() -> None:
    text = "# 年度报告\n公司主营芯片设计并服务汽车客户。\n"
    first = _build(text)
    second = _build(text)

    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    _assert_no_source_payload(first)


def test_validator_rejects_malformed_span_summary_and_schema() -> None:
    manifest = _build("# 年度报告\n公司主营芯片设计并服务汽车客户。\n")

    bad_span = copy.deepcopy(manifest)
    bad_span["sections"][0]["source_span"]["end"] = manifest["cleaned_char_count"] + 1
    assert "section_span_invalid" in validate_periodic_report_coverage_manifest(bad_span)

    bad_summary = copy.deepcopy(manifest)
    bad_summary["summary"]["recognized_section_count"] += 1
    assert "summary_mismatch" in validate_periodic_report_coverage_manifest(bad_summary)

    bad_schema = copy.deepcopy(manifest)
    bad_schema["schema_version"] = "annual_document_coverage_manifest.v0"
    assert "schema_version_invalid" in validate_periodic_report_coverage_manifest(bad_schema)


def _candidate(text: str, usage: str, start: int, end: int, *, block_id: str | None = None) -> dict:
    row = {
        "usage": usage,
        "section": "管理层讨论与分析",
        "title": usage,
        "text": text,
        "source_span": {"start": start, "end": end},
    }
    if block_id is not None:
        row["id"] = block_id
    return row


def test_block_lifecycle_collapses_exact_duplicates_and_separates_omission_stages() -> None:
    text = "# 年度报告\n年度经营摘要足够长。\n## 管理层讨论与分析\n公司主营芯片并服务汽车客户，报告期内收入增长。\n"
    section_start = text.index("公司主营")
    income_start = text.index("报告期内")
    customer_start = text.index("服务汽车")
    selected = _candidate(
        "公司主营芯片并服务汽车客户。", "business_overview", section_start, income_start,
        block_id="business_overview-0",
    )
    usage_limited = _candidate(
        "报告期内收入增长。", "business_overview", income_start, len(text),
    )
    capacity_omitted = _candidate(
        "公司服务汽车客户。", "market_demand_outlook", customer_start, income_start,
        block_id="market_demand_outlook-0",
    )

    manifest = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[selected, copy.deepcopy(selected), usage_limited, capacity_omitted],
        prioritized_candidates=[selected, capacity_omitted],
        selected_blocks=[selected],
    )
    by_disposition = {row["evidence_disposition"]: row for row in manifest["block_decisions"]}

    assert by_disposition["selected_for_producer"]["candidate_occurrences"] == 2
    assert by_disposition["selected_for_producer"]["evidence_block_id"] == "business_overview-0"
    assert by_disposition["omitted_usage_limit"]["evidence_block_id"] is None
    assert by_disposition["omitted_capacity"]["evidence_block_id"] == "market_demand_outlook-0"
    assert manifest["summary"]["candidate_block_count"] == 4
    management = next(section for section in manifest["sections"] if section["heading"] == "管理层讨论与分析")
    assert management["coverage_state"] == "selected_for_review"
    assert validate_periodic_report_coverage_manifest(manifest) == ()


def test_block_maps_to_section_with_largest_overlap() -> None:
    text = "# 年度报告\n第一部分正文内容足够长。\n## 第一节\n第一节正文内容足够长。\n## 第二节\n第二节正文内容足够长。\n"
    first_start = text.index("## 第一节")
    second_start = text.index("## 第二节")
    block = _candidate(
        "跨节候选。", "industry_outlook", second_start - 3, second_start + 10,
        block_id="industry_outlook-0",
    )
    manifest = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[block],
        prioritized_candidates=[block],
        selected_blocks=[block],
    )
    decision = manifest["block_decisions"][0]
    second = next(section for section in manifest["sections"] if section["heading"] == "第二节")

    assert decision["section_id"] == second["section_id"]
    assert decision["coverage_block_id"] in second["matched_coverage_block_ids"]
    assert first_start < second_start


def test_finalizer_derives_card_and_rejected_block_states_from_exact_ids() -> None:
    text = "# 年度报告\n年度经营摘要足够长。\n## 管理层讨论与分析\n公司主营芯片并服务客户。报告期内收入增长。\n"
    body_start = text.index("公司主营")
    income_start = text.index("报告期内")
    selected = _candidate(
        "公司主营芯片并服务客户。", "business_overview", body_start, income_start,
        block_id="business_overview-0",
    )
    rejected = _candidate(
        "报告期内收入增长。", "segment_table", income_start, len(text),
        block_id="segment_table-0",
    )
    upstream = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[selected, rejected],
        prioritized_candidates=[selected, rejected],
        selected_blocks=[selected, rejected],
    )
    cards = [{"card_id": "card-1", "source_block_id": "business_overview-0"}]
    decisions = [
        {
            "source_block_id": "business_overview-0",
            "source_unit_id": "business_overview-0:u0",
            "disposition": "selected",
            "reason": "selected",
            "selected_by_card_ids": ["card-1"],
        },
        {
            "source_block_id": "segment_table-0",
            "source_unit_id": "segment_table-0:u0",
            "disposition": "rejected",
            "reason": "table_noise",
            "selected_by_card_ids": [],
        },
    ]

    finalized = finalize_periodic_report_coverage_manifest(
        upstream,
        source_unit_decisions=decisions,
        cards=cards,
        report_type="annual_report",
        document_style="a_share_annual",
    )
    by_id = {row["evidence_block_id"]: row for row in finalized["block_decisions"]}

    assert finalized["stage"] == "producer"
    assert by_id["business_overview-0"]["producer_disposition"] == "card_selected"
    assert by_id["business_overview-0"]["selected_by_card_ids"] == ["card-1"]
    assert by_id["segment_table-0"]["producer_disposition"] == "reviewed_no_card"
    assert by_id["segment_table-0"]["unit_rejection_counts"] == {"table_noise": 1}
    assert finalized["summary"]["source_unit_count"] == 2
    assert finalized["summary"]["selected_source_unit_count"] == 1
    assert finalized["summary"]["producer_dispositions"] == {
        "card_selected": 1,
        "reviewed_no_card": 1,
        "not_reviewed": 0,
    }
    management = next(section for section in finalized["sections"] if section["heading"] == "管理层讨论与分析")
    assert management["coverage_state"] == "card_selected"
    assert validate_periodic_report_coverage_manifest(finalized) == ()


def test_finalizer_keeps_omitted_blocks_not_reviewed() -> None:
    text = "# 年度报告\n公司主营芯片并服务汽车客户，年度经营信息完整。\n"
    candidate = _candidate("公司主营芯片。", "business_overview", 8, 16)
    upstream = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[candidate],
        prioritized_candidates=[],
        selected_blocks=[],
    )

    finalized = finalize_periodic_report_coverage_manifest(
        upstream,
        source_unit_decisions=[],
        cards=[],
        report_type="annual_report",
        document_style="a_share_annual",
    )

    assert finalized["block_decisions"][0]["producer_disposition"] == "not_reviewed"
    assert finalized["sections"][0]["coverage_state"] == "candidate_not_reviewed"


def test_finalizer_fails_closed_for_unknown_card_or_malformed_upstream() -> None:
    text = "# 年度报告\n公司主营芯片并服务汽车客户，年度经营信息完整。\n"
    selected = _candidate(
        "公司主营芯片。", "business_overview", 8, 16, block_id="business_overview-0"
    )
    upstream = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[selected],
        prioritized_candidates=[selected],
        selected_blocks=[selected],
    )
    unknown_card = finalize_periodic_report_coverage_manifest(
        upstream,
        source_unit_decisions=[{
            "source_block_id": "business_overview-0",
            "source_unit_id": "business_overview-0:u0",
            "disposition": "selected",
            "reason": "selected",
            "selected_by_card_ids": ["missing-card"],
        }],
        cards=[],
        report_type="annual_report",
        document_style="a_share_annual",
    )
    malformed = copy.deepcopy(upstream)
    malformed["summary"]["recognized_section_count"] = 999
    invalid_upstream = finalize_periodic_report_coverage_manifest(
        malformed,
        source_unit_decisions=[],
        cards=[],
        report_type="annual_report",
        document_style="a_share_annual",
    )

    assert unknown_card["status"] == "unavailable"
    assert unknown_card["stage"] == "producer"
    assert unknown_card["unavailable_reason"] == "producer_invalid"
    assert invalid_upstream["status"] == "unavailable"
    assert invalid_upstream["unavailable_reason"] == "upstream_invalid"


def test_finalizer_rejects_selected_unit_without_card_link() -> None:
    text = "# 年度报告\n公司主营芯片并服务汽车客户，年度经营信息完整。\n"
    selected = _candidate(
        "公司主营芯片。", "business_overview", 8, 16, block_id="business_overview-0"
    )
    upstream = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[selected],
        prioritized_candidates=[selected],
        selected_blocks=[selected],
    )

    result = finalize_periodic_report_coverage_manifest(
        upstream,
        source_unit_decisions=[{
            "source_block_id": "business_overview-0",
            "source_unit_id": "business_overview-0:u0",
            "disposition": "selected",
            "reason": "selected",
            "selected_by_card_ids": [],
        }],
        cards=[],
        report_type="annual_report",
        document_style="a_share_annual",
    )

    assert result["status"] == "unavailable"
    assert result["unavailable_reason"] == "producer_invalid"


def test_validator_rejects_broken_block_references() -> None:
    text = "# 年度报告\n公司主营芯片并服务汽车客户，年度经营信息完整。\n"
    selected = _candidate(
        "公司主营芯片。", "business_overview", 8, 16, block_id="business_overview-0"
    )
    manifest = build_periodic_report_coverage_manifest(
        text,
        report_type="annual_report",
        document_style="a_share_annual",
        extracted_candidates=[selected],
        prioritized_candidates=[selected],
        selected_blocks=[selected],
    )
    missing_evidence_id = copy.deepcopy(manifest)
    missing_evidence_id["block_decisions"][0]["evidence_block_id"] = None
    unknown_section = copy.deepcopy(manifest)
    unknown_section["block_decisions"][0]["section_id"] = "section:missing"
    unknown_match = copy.deepcopy(manifest)
    unknown_match["sections"][0]["matched_coverage_block_ids"] = ["coverage-block:missing"]

    assert "evidence_block_id_invalid" in validate_periodic_report_coverage_manifest(missing_evidence_id)
    assert "section_reference_invalid" in validate_periodic_report_coverage_manifest(unknown_section)
    assert "section_block_links_invalid" in validate_periodic_report_coverage_manifest(unknown_match)
