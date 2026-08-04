"""Contracts for canonical external source documents."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from external_source_document import (  # type: ignore[import-not-found]
    SOURCE_DOCUMENT_SCHEMA,
    build_external_source_document,
    validate_external_source_document,
)


def _packet(content: str, *, title: str = "测试股经营跟踪") -> dict:
    return {
        "source_id": "source:test", "stock_name": "测试股", "title": title,
        "source_kind": "media", "source_ref": "https://example.test/article",
        "source_url": "https://example.test/article", "content": content,
    }


def test_document_preserves_paragraph_blocks_and_exact_offsets():
    document = build_external_source_document(_packet(
        "一、经营情况\n\n测试股表示订单增长。\n\n行业供给仍紧张。"
    ))

    assert document["schema_version"] == SOURCE_DOCUMENT_SCHEMA
    assert [block["text"] for block in document["blocks"]] == [
        "一、经营情况", "测试股表示订单增长。", "行业供给仍紧张。",
    ]
    assert [block["block_kind"] for block in document["blocks"]] == [
        "heading", "narrative", "narrative",
    ]
    for block in document["blocks"]:
        assert document["canonical_text"][block["start"]:block["end"]] == block["text"]
    assert validate_external_source_document(document)["status"] == "ok"


def test_comparative_single_block_document_fails_boundary_quality():
    document = build_external_source_document(_packet(
        "测试股与同业对比：" + "主体内容" * 600,
        title="测试股与华工科技技术对比",
    ))

    assert document["boundary_status"] == "scope_input_degraded"
    assert validate_external_source_document(document)["status"] == "invalid"
    assert validate_external_source_document(document)["reason"] == "scope_input_degraded"


def test_document_rejects_forged_comparative_boundary_status():
    document = build_external_source_document(_packet(
        "测试股与同业对比：" + "主体内容" * 600,
        title="测试股与华工科技技术对比",
    ))
    document["boundary_status"] = "preserved"

    assert validate_external_source_document(document) == {
        "status": "invalid", "reason": "boundary_status",
    }


def test_document_rejects_forged_block_kind_that_would_bypass_boundary_check():
    document = build_external_source_document(_packet(
        "测试股与同业对比：" + "主体内容" * 600,
        title="测试股与华工科技技术对比",
    ))
    document["blocks"][0]["block_kind"] = "heading"
    document["boundary_status"] = "preserved"

    assert validate_external_source_document(document) == {
        "status": "invalid", "reason": "block_kind",
    }


def test_comparative_heading_without_target_in_title_requires_preserved_boundaries():
    document = build_external_source_document(_packet(
        "一、测试股与华工科技技术对比\n\n综合结论" + "内容" * 600,
        title="行业跟踪",
    ))

    assert document["boundary_status"] == "scope_input_degraded"


def test_target_partner_heading_is_not_treated_as_a_comparative_input():
    document = build_external_source_document(_packet(
        "一、测试股与华为合作推进产品验证\n\n公司已完成送样。",
        title="行业跟踪",
    ))

    assert document["boundary_status"] == "preserved"


def test_navigation_and_disclaimer_become_noise_blocks_without_truncating_body():
    document = build_external_source_document(_packet(
        "测试股产品完成客户导入。\n\n免责声明\n\n本文不构成投资建议。"
    ))

    assert [block["block_kind"] for block in document["blocks"]] == [
        "narrative", "structural_noise", "structural_noise",
    ]
    assert document["blocks"][-1]["text"] == "本文不构成投资建议。"
    assert validate_external_source_document(document)["status"] == "ok"


def test_document_rejects_canonical_text_not_exactly_reconstructed_by_blocks():
    document = build_external_source_document(_packet("测试股产品完成客户导入。"))
    document["canonical_text"] += "\n\n未分块残留。"
    document["document_hash"] = "sha256:" + hashlib.sha256(
        document["canonical_text"].encode("utf-8")
    ).hexdigest()

    assert validate_external_source_document(document) == {
        "status": "invalid", "reason": "block_sequence",
    }


def test_document_normalizes_markup_inside_each_paragraph_without_merging_blocks():
    document = build_external_source_document(_packet(
        "[测试股产品](https://example.test/product)完成客户导入。\n\n![配图](https://example.test/image.png)"
    ))

    assert [block["text"] for block in document["blocks"]] == [
        "测试股产品完成客户导入。", "配图",
    ]
    assert len(document["blocks"]) == 2
