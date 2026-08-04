"""Contracts for exact external evidence units and admission."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from external_evidence import (  # type: ignore[import-not-found]
    EXTERNAL_DISPLAY_TOPIC_ORDER,
    EVIDENCE_UNIT_SCHEMA,
    argument_status,
    external_coverage_families,
    external_family_title,
    materialize_external_evidence_units,
    validate_external_evidence_unit,
)
from external_source_document import build_external_source_document


def _document(content: str) -> dict:
    return build_external_source_document({
        "source_id": "source:test", "stock_name": "测试股", "title": "测试股经营跟踪",
        "source_kind": "media", "source_ref": "https://example.test/article",
        "source_url": "https://example.test/article", "content": content,
    })


def test_evidence_units_reconstruct_exact_block_spans_in_source_order():
    document = _document("测试股产品完成客户导入。订单增长明显。")

    units = materialize_external_evidence_units(document)

    assert [unit["text"] for unit in units] == ["测试股产品完成客户导入。", "订单增长明显。"]
    assert all(unit["schema_version"] == EVIDENCE_UNIT_SCHEMA for unit in units)
    block = document["blocks"][0]
    assert [block["text"][unit["start"]:unit["end"]] for unit in units] == [
        unit["text"] for unit in units
    ]


def test_argument_admission_covers_negative_and_constraint_conclusions():
    assert argument_status("测试股表示不存在故意压低股价。") == "admitted"
    assert argument_status("公司表示上游设备采购没有明显瓶颈。") == "admitted"
    assert argument_status("NPO是测试股的强催化，短期影响有限。") == "admitted"
    assert argument_status("一、产品情况") == "incomplete"
    assert "technology_product" in external_coverage_families("NPO是测试股的强催化，短期影响有限。")


def test_evidence_validator_rejects_forged_derived_unit_fields():
    document = _document("测试股产品完成客户导入。")
    unit = materialize_external_evidence_units(document)[0]
    forged_ordinal = copy.deepcopy(unit)
    forged_ordinal["unit_ordinal"] = 9
    assert validate_external_evidence_unit(forged_ordinal, document) == {
        "status": "invalid", "reason": "unit_identity",
    }
    forged_family = copy.deepcopy(unit)
    forged_family["coverage_families"] = ["financial_quality"]
    assert validate_external_evidence_unit(forged_family, document) == {
        "status": "invalid", "reason": "unit_identity",
    }


def test_taxonomy_module_owns_titles_and_display_order():
    assert external_family_title("technology_product") == "技术与产品"
    assert external_family_title("unknown") == "外部变量"
    assert EXTERNAL_DISPLAY_TOPIC_ORDER[:3] == ("需求与客户", "商业化进展", "技术与产品")
