"""Deterministic target, peer and industry scope contracts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from external_scope import resolve_external_scope  # type: ignore[import-not-found]
from external_source_document import build_external_source_document


def _document(content: str, *, title: str = "测试股经营跟踪") -> dict:
    return build_external_source_document({
        "source_id": "source:test", "stock_name": "测试股", "title": title,
        "source_kind": "media", "source_ref": "https://example.test/article",
        "source_url": "https://example.test/article", "content": content,
    })


def test_target_centric_company_continuation_uses_document_anchor():
    units = resolve_external_scope(_document(
        "测试股公告指出，产品已完成客户导入。\n\n公司已接到全年订单。"
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "explicit_target", "target_document_context",
    ]


def test_industry_sentence_does_not_inherit_target_owner():
    units = resolve_external_scope(_document(
        "测试股产品完成客户导入。\n\n2027年行业仍面临产能紧张。"
    ), stock_name="测试股")

    assert units[-1]["scope_provenance"]["origin"] == "industry_context"


def test_comparative_block_returns_to_primary_owner_after_inline_target_contrast():
    units = resolve_external_scope(_document(
        "华工科技拥有全栈自研能力。测试股仅完成样品验证。拥有全栈自研能力，功耗更低。",
        title="测试股与华工科技技术对比",
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "explicit_peer", "explicit_target", "explicit_peer",
    ]


def test_suffixless_competitor_relation_never_inherits_target_owner():
    units = resolve_external_scope(_document(
        "测试股产品完成客户导入。其竞争对手英伟达发布新产品。"
    ), stock_name="测试股")

    assert units[-1]["scope_provenance"]["origin"] == "explicit_peer"
    assert units[-1]["scope_provenance"]["owner_surface"] == "英伟达"


def test_direct_target_peer_comparison_requires_explicit_relation():
    units = resolve_external_scope(_document(
        "测试股相比华工科技具备更大产能。"
    ), stock_name="测试股")

    assert units[0]["scope_provenance"]["origin"] == "target_peer_relation"


def test_target_partner_relation_uses_target_with_peer_context_scope():
    units = resolve_external_scope(_document(
        "测试股与华为合作推进产品验证。"
    ), stock_name="测试股")

    assert units[0]["scope_provenance"]["origin"] == "target_peer_relation"
    assert units[0]["scope_provenance"]["owner_surface"] == "华为"


def test_target_partner_title_keeps_company_continuations_target_centric():
    units = resolve_external_scope(_document(
        "公司已接到全年订单。",
        title="测试股与华为合作推进产品验证",
    ), stock_name="测试股")

    assert units[0]["scope_provenance"]["origin"] == "target_document_context"


def test_suffixless_named_actor_does_not_inherit_target_document_owner():
    units = resolve_external_scope(_document(
        "英伟达发布新产品。其产品已完成客户验证。",
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "explicit_peer", "explicit_peer",
    ]
    assert all(unit["scope_provenance"]["owner_surface"] == "英伟达" for unit in units)


def test_comparative_heading_registers_suffixless_peer_in_document_inventory():
    units = resolve_external_scope(_document(
        "英伟达的技术路线覆盖高端产品。\n\n行业需求仍有波动。",
        title="测试股与英伟达技术对比",
    ), stock_name="测试股")

    assert units[0]["scope_provenance"]["origin"] == "explicit_peer"
    assert units[0]["scope_provenance"]["owner_surface"] == "英伟达"


def test_target_document_does_not_treat_business_phrases_as_peer_entities():
    units = resolve_external_scope(_document(
        "测试股发布业绩预告。公司主营FPGA、安全识别芯片、存储、车规控制芯片等，覆盖工业、汽车电子、AI和通信等多个赛道。"
        "在AI融合方向推出了首款FPAI产品。"
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "explicit_target", "target_document_context", "target_document_context",
    ]


def test_target_product_names_and_action_phrases_inherit_target_document_owner():
    units = resolve_external_scope(_document(
        "测试股展示新一代芯片。黑芝麻华山A2000芯片预计2026年下半年量产装车。"
        "武当C1296已实现舱驾一体量产突破。"
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "explicit_target", "target_document_context", "target_document_context",
    ]


def test_target_title_owns_product_block_with_dated_corporate_action():
    units = resolve_external_scope(_document(
        "华山A1000是国内首款支持L2级辅助驾驶的车规级SoC。2026年初战略收购亿智电子，形成完整产品矩阵。",
        title="测试股十年技术演进与算力版图重构",
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "target_document_context", "target_document_context",
    ]


def test_global_china_and_segment_market_facts_are_industry_context():
    units = resolve_external_scope(_document(
        "全球智能驾驶芯片市场2024年超100亿美元。中国占全球约46%市场份额。"
        "高端市场英伟达Thor系列已进入量产。"
    ), stock_name="测试股")

    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "industry_context", "industry_context", "industry_context",
    ]


def test_target_document_partner_relation_without_repeated_target_name_keeps_both_sides():
    units = resolve_external_scope(_document(
        "测试股展示新产品。华山A1000系列展出一汽红旗与亿咖通联合打造的泊车控制器。"
    ), stock_name="测试股")

    assert units[-1]["scope_provenance"]["origin"] == "target_peer_relation"
    assert units[-1]["scope_provenance"]["owner_surface"] == "亿咖通"


def test_capability_phrase_is_not_treated_as_a_peer_actor():
    units = resolve_external_scope(_document(
        "测试股已具备批量交付能力。能大批量交付高速产品的厂商不多。"
    ), stock_name="测试股")

    assert units[-1]["scope_provenance"]["origin"] == "target_document_context"
    assert units[-1]["scope_provenance"]["resolver_version"] == "external_scope_resolver.v2"
