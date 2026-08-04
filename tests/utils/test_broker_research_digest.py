from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from source_adapter import SynthesisItem


def _research_item(**extra) -> SynthesisItem:
    merged_extra = {
        "source_type": "broker_research",
        "source_credit": 72,
        "verification_status": "professional_observation",
        "institution": "国信证券",
        "pdf_local_path": "/tmp/report.pdf",
        "pdf_url": "https://pdf.dfcfw.com/pdf/H3_TEST_1.pdf",
    }
    merged_extra.update(extra)
    return SynthesisItem(
        title="圣邦股份一季度点评：收入创季度新高",
        content="圣邦股份一季度点评：收入创季度新高",
        author="国信证券",
        source_platform="研报",
        url="https://pdf.dfcfw.com/pdf/H3_TEST_1.pdf",
        publish_time="2026-05-12",
        extra=merged_extra,
    )


def test_digest_cards_include_selection_version() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    核心观点
    一季度收入创季度新高，归母净利润同比翻倍以上。公司2026年一季度实现收入10.98亿元，
    同比增长39.08%，毛利率为51.63%。2025年网络与计算收入占比超15%，工业与能源占比超30%。

    风险提示：产品研发不及预期，客户导入不及预期，竞争加剧。
    免责声明
    本报告仅供客户参考，不构成投资建议。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)

    assert len(cards) >= 1
    assert all(card["selection_version"] == "broker_digest_v3_3" for card in cards)


def test_digest_card_identity_hashes_final_selected_excerpt() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    核心观点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
    下游客户需求保持增长，产品结构升级推动盈利能力改善。
    """

    card = build_broker_research_digest_cards(_research_item(), text, max_cards=1)[0]
    expected_hash = hashlib.sha256(card["source_excerpt"].encode("utf-8")).hexdigest()

    assert card["source_excerpt_hash"] == expected_hash
    assert card["card_id"] == f"broker:{expected_hash[:16]}"


def test_digest_extracts_high_value_sections_and_is_professional_analysis() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    核心观点
    一季度收入创季度新高，归母净利润同比翻倍以上。公司2026年一季度实现收入10.98亿元，
    同比增长39.08%，毛利率为51.63%。2025年网络与计算收入占比超15%，工业与能源占比超30%。

    投资建议：模拟芯片平台企业，维持“优于大市”评级。
    我们上调公司2026-2028年归母净利润至8.48/12.53/17.67亿元，对应PE分别为72/49/35倍。

    风险提示：产品研发不及预期，客户导入不及预期，竞争加剧。
    免责声明
    本报告仅供客户参考，不构成投资建议。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)

    assert [card["card_type"] for card in cards] == [
        "broker_core_view",
        "broker_earnings_forecast",
    ]
    assert all(card["source_type"] == "broker_research" for card in cards)
    assert all(card["source_credit"] == 72 for card in cards)
    assert all(card["claim_status"] == "professional_analysis" for card in cards)
    assert all(card["confirmed_fact"] is False for card in cards)
    assert all(card["scoring_eligible"] is False for card in cards)
    assert all(card["risk_score_eligible"] is False for card in cards)
    assert "免责声明" not in "\n".join(card["source_excerpt"] for card in cards)


def test_digest_prefers_sections_over_page_fallback_for_long_deep_report() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    noisy_front = "\n".join(
        f"第{i}页 股票走势图 基础数据 分析师联系方式" for i in range(1, 12)
    )
    text = (
        noisy_front
        + """
        产业趋势
        AI算力基础设施投资持续增长，800G与1.6T高速光模块需求快速提升。
        公司通过预付账款、长期协议和产能扩张提升订单交付确定性。

        竞争格局
        公司在硅光芯片、自研能力和重点客户联合开发方面形成交付优势。
        """
    )

    cards = build_broker_research_digest_cards(
        _research_item(title="中际旭创深度报告：Scaleup 光连接产品领先", pdf_page_count=18),
        text,
        max_cards=5,
    )

    excerpts = "\n".join(card["source_excerpt"] for card in cards)
    assert "800G" in excerpts
    assert "1.6T" in excerpts
    assert "硅光芯片" in excerpts
    assert "股票走势图" not in excerpts


def test_digest_deduplicates_repeated_broker_views() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    repeated = (
        "公司2026年一季度实现营收195亿元，同比增长192%，归母净利润57亿元，"
        "同比增长262%，高速光模块需求快速增长。"
    )
    text = f"""
    投资要点
    {repeated}

    核心观点
    {repeated}

    风险提示
    北美CSP资本开支阶段性节奏变化导致光模块拉货不及预期。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)

    matching = [card for card in cards if "营收195亿元" in card["source_excerpt"]]
    assert len(matching) == 1
    assert len(cards) == 2


def test_digest_falls_back_to_first_meaningful_pages_when_no_headings() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    股票价格走势图 基础数据 分析师电话
    公司ESP32-S31将S3/P4/C6三条产品主线进行系统级融合，
    推动平台从AI MCU走向AIoT智能节点。2025年芯片销量1.78亿颗，
    模组销量1.31亿块，综合毛利率提升至46.6%。
    免责声明 本报告仅供参考。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=3)

    assert len(cards) == 1
    assert cards[0]["card_type"] == "broker_product_driver"
    assert "AIoT智能节点" in cards[0]["source_excerpt"]
    assert "免责声明" not in cards[0]["source_excerpt"]


def test_preview_markdown_makes_broker_boundaries_explicit() -> None:
    from broker_research_digest import (
        build_broker_research_digest_cards,
        build_broker_research_digest_preview_markdown,
    )

    text = """
    核心观点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
    风险提示：产品研发不及预期，客户导入不及预期。
    """
    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)

    markdown = build_broker_research_digest_preview_markdown(
        stock_name="圣邦股份",
        stock_code="300661",
        cards=cards,
    )

    assert "# Broker Research Digest Preview" in markdown
    assert "professional_analysis" in markdown
    assert "confirmed_fact：`false`" in markdown
    assert "scoring_eligible：`false`" in markdown
    assert "圣邦股份" in markdown


def test_digest_removes_pdf_front_matter_noise_from_core_view() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    S31助力端侧部署。端侧AI的核心是让大模型在本地设备完成推理，解决云端AI的隐私、延迟与成本问题。
    乐鑫科技 55% 46% 股票走势图 资料来源：聚源，中邮证券研究所
    ESP32-S31将公司S3/P4/C6三条产品主线进行系统级融合，从而推动平台从AI MCU走向AIoT智能节点。
    最新收盘价（元）143.80 总市值/流通市值（亿元）240/225 Email: analyst@example.com
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)
    excerpt = cards[0]["source_excerpt"]

    assert "ESP32-S31" in excerpt
    assert "AIoT智能节点" in excerpt
    assert "股票走势图" not in excerpt
    assert "资料来源" not in excerpt
    assert "Email" not in excerpt
    assert "总市值" not in excerpt


def test_digest_prefers_clean_candidate_instead_of_repairing_noisy_excerpt() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    事件：2026 年 4 月 17 日，中际旭创发布 2026 年一季报：
    受益于终端客户对算力基础设施的强劲投入，2025 年公司 品出货较快增长，
    随着产 方案不断优化，公司营业收入与净利 均同比实现大幅增长，
    2026 年全年毛利率有望保持稳中 升，预计 20 2027 年 800G 光模块需求持续增长，
    1.6T 光模块需求将迎 强劲增长，公司业绩延续增 势。

    投资要点
    下游云厂商资本开支持续扩张，800G与1.6T高速光模块需求延续高景气，
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)
    excerpt = cards[0]["source_excerpt"]

    assert "下游云厂商资本开支持续扩张" in excerpt
    assert "产品结构升级推动收入增长" in excerpt
    assert "公司 品" not in excerpt
    assert "产 方案" not in excerpt
    assert "净利 均" not in excerpt
    assert "稳中 升" not in excerpt
    assert "20 2027" not in excerpt


def test_excerpt_cleaner_only_repairs_pdf_artifacts_when_legacy_mode_enabled() -> None:
    from broker_research_digest import clean_broker_research_excerpt_text

    noisy = "2025 年公司 品出货较快增长，随着产 方案不断优化，公司净利 均增长。"

    default_cleaned = clean_broker_research_excerpt_text(noisy)
    legacy_cleaned = clean_broker_research_excerpt_text(
        noisy,
        repair_legacy_artifacts=True,
    )

    assert "公司 品出货较快增长" in default_cleaned
    assert "产 方案" in default_cleaned
    assert "公司产品出货较快增长" not in default_cleaned

    assert "公司产品出货较快增长" in legacy_cleaned
    assert "产品方案不断优化" in legacy_cleaned
    assert "净利润均增长" in legacy_cleaned


def test_excerpt_cleaner_repairs_generic_cjk_line_wraps_in_legacy_mode() -> None:
    from broker_research_digest import clean_broker_research_excerpt_text

    noisy = "受益于终端 对算力基础设施的投入，销售回款 持续增强。"

    cleaned = clean_broker_research_excerpt_text(
        noisy,
        repair_legacy_artifacts=True,
    )

    assert cleaned == "受益于终端对算力基础设施的投入，销售回款持续增强。"


def test_digest_selector_drops_irrecoverable_ocr_unit_without_guessing_missing_product() -> None:
    from broker_research_digest import _select_excerpt_units

    text = (
        "高速光模块需求快速增长，公司业绩持续增长。"
        "受益于终端客户投入，公司产品出货持续增长，其中 及1.6T光模块快速放量。"
        "客户订单和产品结构升级推动收入增长，毛利率有望改善。"
    )

    excerpt = _select_excerpt_units(text, "broker_core_view")

    assert "高速光模块需求快速增长" in excerpt
    assert "客户订单和产品结构升级推动收入增长" in excerpt
    assert "其中 及1.6T" not in excerpt
    assert "其中及1.6T" not in excerpt


def test_legacy_cleaner_drops_damaged_financial_units_instead_of_inventing_values() -> None:
    from broker_research_digest import clean_broker_research_excerpt_text

    noisy = (
        "2026年一季度，公司实现营收195. 环比分别增长192.1%、47.3%；"
        "实现归母净利润57.3亿元，同比增长262.3%。"
        "扣非后归母净利润为57.2亿元，同环比分别增长57.7%。"
        "公司单季度销售毛利率为46.1%，创下历史新高。"
    )

    cleaned = clean_broker_research_excerpt_text(
        noisy,
        repair_legacy_artifacts=True,
    )

    assert "营收195" not in cleaned
    assert "环比分别增长192.1%" not in cleaned
    assert "同环比分别增长57.7%" not in cleaned
    assert "归母净利润57.3亿元，同比增长262.3%" in cleaned
    assert "销售毛利率为46.1%" in cleaned


def test_digest_prefers_clean_repeated_heading_candidate_over_noisy_first_match() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现营收195. 环比分别增长192.1%、47.3%；实现归母净利润57.3亿元。

    投资要点
    下游云厂商资本开支持续扩张，800G与1.6T高速光模块需求延续高景气，
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。

    风险提示
    客户资本开支不及预期。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    core_excerpt = next(card["source_excerpt"] for card in cards if card["card_type"] == "broker_core_view")

    assert "下游云厂商资本开支持续扩张" in core_excerpt
    assert "产品结构升级推动收入增长" in core_excerpt
    assert "营收195." not in core_excerpt


def test_digest_records_section_candidate_diagnostics() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现营收195. 环比分别增长192.1%、47.3%；实现归母净利润57.3亿元。

    投资要点
    下游云厂商资本开支持续扩张，800G与1.6T高速光模块需求延续高景气，
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")
    diagnostics = core_card["selection_diagnostics"]

    assert len(diagnostics) == 2
    assert {entry["heading"] for entry in diagnostics} == {"投资要点"}
    assert any(entry["status"] == "selected" for entry in diagnostics)
    assert any(entry["status"] in ("skipped", "rejected") for entry in diagnostics)
    assert all(isinstance(entry["score"], int) for entry in diagnostics)
    assert "selected" in core_card["selection_reason"]


def test_digest_diagnostics_explain_score_parts() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现营收195亿元，同比增长192.1%，环比增长47.3%。

    投资要点
    下游云厂商资本开支持续扩张，800G与1.6T高速光模块需求延续高景气，
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")
    diagnostics = core_card["selection_diagnostics"]

    expected_parts = {
        "signal",
        "evidence",
        "completeness",
        "coherence",
        "ocr_penalty",
        "noise_penalty",
    }
    for entry in diagnostics:
        assert expected_parts == set(entry["score_parts"])
        assert entry["score"] == (
            entry["score_parts"]["signal"]
            + entry["score_parts"]["evidence"]
            + entry["score_parts"]["completeness"]
            + entry["score_parts"]["coherence"]
            - entry["score_parts"]["ocr_penalty"]
            - entry["score_parts"]["noise_penalty"]
        )


def test_digest_rejects_severe_ocr_damage_candidate() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    clean_claim = "下游云厂商资本开支持续扩张"
    text = f"""
    投资要点
    公司2026年一 度实现营 收195. 环比分别 增长192.1%、47.3%；实现归母净 利润57.3亿元，
    预计 20 2027 年 800G 光模 块需求持续 增长，1.6T 光模 块需求将迎 强劲增长，
    公司产 品出 货较快增长，随着产 方案不断优化，公司营业收入与净利 均同比实现大幅增长。

    投资要点
    {clean_claim}，800G与1.6T高速光模块需求延续高景气，
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。

    风险提示
    客户资本开支不及预期。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")

    assert clean_claim in core_card["source_excerpt"]
    assert any(
        entry["status"] == "rejected"
        and entry["reason"] == "rejected_ocr_damage"
        for entry in core_card["selection_diagnostics"]
    )


def test_digest_valid_numbers_are_not_rejected_as_severe_damage() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    我们预计公司2026年实现营收57.3亿元，同比增长262.3%，对应EPS为1.6元，
    1.6T光模块需求保持强劲，2026年全年毛利率稳中回升。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")

    assert all(entry["status"] != "rejected" for entry in core_card["selection_diagnostics"])


def test_digest_clean_pdf_line_wraps_are_not_severe_ocr_damage() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    下游云厂商资本开支持续
    扩张，高速光模块需求延续
    景气，客户订单和产品结构
    升级推动收入增长，毛利率有望改善。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")

    assert all(entry["status"] != "rejected" for entry in core_card["selection_diagnostics"])


def test_digest_selector_rejects_five_cjk_gaps_but_keeps_four_line_wraps() -> None:
    from broker_research_digest import (
        _candidate_score_parts,
        _has_severe_ocr_damage,
        _select_excerpt_units,
    )

    clean = (
        "下游云厂商资本开支持续 扩张，高速光模块需求延续 景气，"
        "客户订单和产品结构 升级推动收入 增长，毛利率有望改善。"
    )
    damaged = (
        "公司处于算力产业链关键互联环节，产品需求持续 扩张，"
        "高速模块出货明显 提升，客户订单加速 释放，"
        "产品结构持续 优化，盈利能力逐步 改善。"
    )

    assert _candidate_score_parts(clean)["ocr_penalty"] == 16
    assert not _has_severe_ocr_damage(_candidate_score_parts(clean))
    assert _select_excerpt_units(clean, "broker_product_driver") == clean
    assert _candidate_score_parts(damaged)["ocr_penalty"] == 20
    assert _has_severe_ocr_damage(_candidate_score_parts(damaged))
    assert _select_excerpt_units(damaged, "broker_product_driver") == ""


def test_digest_selector_keeps_clean_units_from_wrapped_multi_sentence_input() -> None:
    from broker_research_digest import _select_excerpt_units

    wrapped = (
        "下游客户需求持续 扩张，产品订单明显 增长，产品结构加速 升级。"
        "毛利率受规模效应 改善，产能建设有序 推进，客户交付继续 增长。"
    )

    excerpt = _select_excerpt_units(wrapped, "broker_product_driver")

    assert "下游客户需求持续 扩张" in excerpt
    assert "毛利率受规模效应 改善" in excerpt


def test_generic_driver_fallback_rejects_globally_degraded_source() -> None:
    from broker_research_digest import _generic_driver_block_excerpts

    damaged = [
        (
            f"第{i}项业务观察显示，产品需求持续 扩张，客户订单明显 增长，"
            "产能建设加速 推进，产品结构继续 优化，盈利能力逐步 改善。"
        )
        for i in range(8)
    ]
    clean = [
        (
            f"第{i}项业务观察显示，下游需求持续扩张，客户订单明显增长，"
            "产能建设加速推进，产品结构继续优化，盈利能力逐步改善。"
        )
        for i in range(8, 16)
    ]

    assert _generic_driver_block_excerpts("\n\n".join(damaged + clean)) == []


def test_generic_driver_fallback_keeps_source_with_isolated_damage() -> None:
    from broker_research_digest import _generic_driver_block_excerpts

    damaged = [
        (
            f"第{i}项业务观察显示，产品需求持续 扩张，客户订单明显 增长，"
            "产能建设加速 推进，产品结构继续 优化，盈利能力逐步 改善。"
        )
        for i in range(7)
    ]
    clean = [
        (
            f"第{i}项业务观察显示，下游需求持续扩张，客户订单明显增长，"
            "产能建设加速推进，产品结构继续优化，盈利能力逐步改善。"
        )
        for i in range(7, 16)
    ]

    assert _generic_driver_block_excerpts("\n\n".join(damaged + clean))


def test_digest_selector_rejects_residual_chart_metadata() -> None:
    from broker_research_digest import _select_excerpt_units

    damaged = (
        "图 12：2016-2026Q1公司研发费用及增速 图 13：20 数据来源：Wind，西南证券整理 "
        "应收账款同比增长98.42%，应付账款同比增长169.26%，资本开支扩大支撑产能建设。"
    )

    assert _select_excerpt_units(damaged, "broker_product_driver") == ""


def test_digest_selector_rejects_incomplete_multi_period_series() -> None:
    from broker_research_digest import _select_excerpt_units

    damaged = (
        "预计公司高端产品毛利率2026-2028年分别为45.0%、48.0，"
        "产品结构升级推动盈利能力持续提升。"
    )

    assert _select_excerpt_units(damaged, "broker_product_driver") == ""


def test_digest_selector_rejects_corporate_profit_with_bare_yuan_unit() -> None:
    from broker_research_digest import _select_excerpt_units

    damaged = "公司2025年实现营业收入382.40亿元，实现归母净利润107.97元，同比增长108.78%。"

    assert _select_excerpt_units(damaged, "broker_core_view") == ""


def test_digest_selector_keeps_complete_multi_period_series() -> None:
    from broker_research_digest import _select_excerpt_units

    complete = (
        "预计公司高端产品毛利率2026-2028年分别为45.0%、48.0%、50.0%，"
        "产品结构升级推动盈利能力持续提升。"
    )

    assert _select_excerpt_units(complete, "broker_product_driver") == complete


def test_digest_retreats_to_sentence_boundary_when_900_falls_mid_clause() -> None:
    from broker_research_digest import _bounded_complete_excerpt

    complete_prefix = "甲" * 850 + "。"
    excerpt = _bounded_complete_excerpt(complete_prefix + "乙" * 200 + "。")

    assert excerpt == complete_prefix


def test_digest_extends_to_nearby_sentence_boundary_within_limit() -> None:
    from broker_research_digest import _bounded_complete_excerpt

    expected = "甲" * 850 + "。" + "乙" * 70 + "。"
    excerpt = _bounded_complete_excerpt(expected + "丙" * 100)

    assert excerpt == expected
    assert 900 < len(excerpt) <= 980


def test_digest_selected_units_are_ordered_source_substrings() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
    下游云厂商资本开支持续扩张，800G与1.6T高速光模块需求延续高景气。
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")
    excerpt = core_card["source_excerpt"]

    assert "公司2026年一季度实现收入10.98亿元" in excerpt
    assert "下游云厂商资本开支持续扩张" in excerpt
    assert "客户订单和产品结构升级推动收入增长" in excerpt
    assert excerpt.index("下游云厂商") > excerpt.index("公司2026年")
    assert excerpt.index("客户订单") > excerpt.index("下游云厂商")


def test_digest_rejects_long_clause_without_sentence_boundary() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    long_clause = "A" * 2000
    text = f"""
    投资要点
    {long_clause}

    核心观点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    core_card = next(card for card in cards if card["card_type"] == "broker_core_view")

    assert "A" * 100 not in core_card["source_excerpt"]


def test_digest_recognizes_broader_existing_category_headings() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    主要观点
    AI算力资本开支保持高景气，公司800G与1.6T高速光模块需求快速增长，收入和利润弹性提升。

    客户结构
    北美云厂商客户需求延续，重点客户订单能见度提升，产品结构向高端光模块升级。

    估值分析
    预计公司2026-2028年归母净利润为80/110/140亿元，维持买入评级，对应PE继续消化。

    主要风险
    客户资本开支不及预期，高速光模块价格竞争加剧，新产品交付不及预期。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)

    assert [card["card_type"] for card in cards] == [
        "broker_core_view",
        "broker_product_driver",
        "broker_earnings_forecast",
        "broker_risk_note",
    ]
    assert next(card for card in cards if card["card_type"] == "broker_core_view")["source_heading"] == "主要观点"
    assert next(card for card in cards if card["card_type"] == "broker_product_driver")["source_heading"] == "客户结构"
    assert next(card for card in cards if card["card_type"] == "broker_earnings_forecast")["source_heading"] == "估值分析"
    assert next(card for card in cards if card["card_type"] == "broker_risk_note")["source_heading"] == "主要风险"


def test_digest_recognizes_bullet_prefixed_headings_from_pdf_text() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    发布时间：2026
    乐鑫科技(688018)
    l 投资要点
    S31助力端侧部署。ESP32-S31将公司S3/P4/C6三条产品主线进行系统级融合，
    推动平台从AI MCU走向AIoT智能节点。2025年公司芯片销量1.7亿颗，
    模组销量1.31亿块，综合毛利率提升至46.6%。
    """

    cards = build_broker_research_digest_cards(_research_item(), text)

    assert len(cards) == 1
    assert cards[0]["source_heading"] == "投资要点"
    assert cards[0]["viewpoint_cluster"].startswith("business_driver_")
    assert "ESP32-S31" in cards[0]["source_excerpt"]


def test_digest_does_not_classify_risk_sentence_as_product_driver() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    核心观点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，产品结构持续改善。
    竞争格局
    竞争格局加剧风险；产品研发及技术创新不及预期；客户导入不及预期。Email: analyst@example.com
    风险提示
    市场复苏不及预期，客户导入不及预期。
    """

    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=5)

    assert "broker_product_driver" not in [card["card_type"] for card in cards]


def test_short_report_limits_digest_to_core_forecast_and_risk() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。

    产业趋势
    AI算力基础设施升级带动模拟芯片需求。

    盈利预测
    预计公司2026-2028年归母净利润为8.48/12.53/17.67亿元，维持买入评级。

    风险提示
    产品研发不及预期，客户导入不及预期。
    """

    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=4),
        text,
        max_cards=5,
    )

    assert [card["card_type"] for card in cards] == [
        "broker_core_view",
        "broker_earnings_forecast",
    ]
    assert all(card["report_length_class"] == "short" for card in cards)


def test_long_report_allows_product_driver_and_more_cards() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    核心观点
    公司2026年一季度实现收入194.96亿元，同比增长192.12%，归母净利润57.35亿元，同比增长262.28%。

    产业趋势
    AI算力基础设施投资持续增长，800G与1.6T高速光模块需求快速提升。
    云厂商资本开支扩大，推动光连接产品需求延续高景气。

    竞争格局
    公司在硅光芯片、自研能力和重点客户联合开发方面形成交付优势。

    盈利预测
    预计2026-2028年EPS分别为22.36元、35.37元、65.71元，对应PE分别为38倍、24倍、13倍。

    风险提示
    AI算力需求不及预期，客户集中度较高，产能扩张与供应链风险。
    """

    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=18),
        text,
        max_cards=8,
    )

    card_types = [card["card_type"] for card in cards]
    assert "broker_product_driver" in card_types
    assert "broker_earnings_forecast" in card_types
    assert "broker_risk_note" in card_types
    assert all(card["report_length_class"] == "long" for card in cards)


def test_digest_extracts_generic_driver_block_without_industry_specific_keywords() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    报告要点
    公司2025年收入保持增长，产品结构持续优化。展望2026年，预计核心下游需求延续，
    公司在重点客户中的导入进度加快，新产品放量和份额提升有望推动业务继续增长。
    从下游来看，第一类应用场景景气度较高，第二类应用场景受益于客户产品升级，
    第三类应用场景订单改善明显。供应端方面，成熟产能相对偏紧，价格环境趋稳，
    公司新品导入及结构升级顺利推进，盈利能力有望持续改善。
    财务数据和估值 2025A 2026E 2027E 营业收入 3898 4796 5827
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=10), text)

    driver_cards = [card for card in cards if card["card_type"] == "broker_product_driver"]
    assert len(driver_cards) == 1
    assert driver_cards[0]["knowledge_eligible"] is True
    assert driver_cards[0]["viewpoint_cluster"].startswith("business_driver_")
    assert "重点客户" in driver_cards[0]["source_excerpt"]
    assert "产品结构持续优化" in driver_cards[0]["source_excerpt"]
    assert "财务数据" not in driver_cards[0]["source_excerpt"]


def test_digest_extracts_long_report_body_driver_beyond_first_summary() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现营业收入194.96亿元，同比增长192.12%；归母净利润57.35亿元。
    盈利预测
    预计2026-2028年EPS分别为22.36元、35.37元、65.71元。

    公司业务概况
    公司围绕核心业务需求构建了高速产品体系，通过持续向更高端规格升级，实现收入稳增长与盈利能力提升。
    随着下游客户持续扩张基础设施规模，内部互联带宽需求快速增长，高端产品出货占比持续提升，
    成为收入增长的核心驱动力。在业务演进路径上，公司一方面持续推进产品向更高规格迭代，
    另一方面通过提前锁定上游资源与扩充产能提升交付能力，以适应需求快速增长带来的供给压力。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text)

    driver_cards = [card for card in cards if card["card_type"] == "broker_product_driver"]
    assert len(driver_cards) == 1
    assert driver_cards[0]["knowledge_eligible"] is True
    assert "交付能力" in driver_cards[0]["source_excerpt"]
    assert "更高规格迭代" in driver_cards[0]["source_excerpt"]


def test_generic_driver_block_truncates_before_forecast_and_risk_sections() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    报告要点
    公司贴近市场需求，快速响应客户，客户认可度及品牌影响力不断提升，市场份额不断扩大。
    投资建议：预计公司2026—2027年每股收益分别为1.21元和1.64元，对应PE分别为63倍和47倍。
    风险提示：消费类需求复苏不及预期的风险，行业竞争加剧的风险等。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=8), text)
    driver_cards = [card for card in cards if card["card_type"] == "broker_product_driver"]

    assert len(driver_cards) == 1
    assert "投资建议" not in driver_cards[0]["source_excerpt"]
    assert "风险提示" not in driver_cards[0]["source_excerpt"]


def test_financial_core_view_does_not_block_generic_driver_fallback() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    投资要点
    公司2026年一季度实现营业收入194.96亿元，同比增长192.12%；归母净利润57.35亿元。
    盈利预测
    预计2026-2028年EPS分别为22.36元、35.37元、65.71元。

    公司业务概况
    公司围绕核心业务需求构建产品体系，通过持续向更高端规格升级，实现收入稳增长与盈利能力提升。
    随着下游客户持续扩张基础设施规模，高端产品出货占比持续提升，成为收入增长的核心驱动力。
    公司通过提前锁定上游资源与扩充产能提升交付能力，以适应需求快速增长带来的供给压力。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text)

    assert any(
        card["card_type"] == "broker_core_view" and card["knowledge_eligible"] is True
        for card in cards
    )
    assert any(
        card["card_type"] == "broker_product_driver" and card["knowledge_eligible"] is True
        for card in cards
    )


# ---------------------------------------------------------------------------
# Batch B: claim/evidence admission, complementarity, and source fidelity
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize(
    "card_type,heading,text",
    [
        ("broker_core_view", "核心观点", "公司长期发展前景良好。"),
        ("broker_core_view", "核心观点", "公司核心产品市场需求有望保持较快增长。"),
        ("broker_product_driver", "产品布局", "公司产品需求有望增长。"),
        ("broker_earnings_forecast", "盈利预测", "我们预计公司业绩增长，维持买入评级。"),
        ("broker_risk_note", "风险提示", "市场竞争风险。"),
    ],
)
def test_digest_rejects_claim_without_evidence_per_family(card_type, heading, text):
    from broker_research_digest import build_broker_research_digest_cards

    page_count = 18 if card_type == "broker_product_driver" else 4
    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=page_count),
        f"{heading}\n{text}",
        max_cards=8,
    )
    assert card_type not in [c["card_type"] for c in cards]


@pytest.mark.parametrize(
    "card_type,heading,text",
    [
        (
            "broker_core_view",
            "核心观点",
            "公司2026年一季度收入同比增长39.08%，产品结构升级推动毛利率改善。",
        ),
        (
            "broker_product_driver",
            "产品布局",
            "800G与1.6T产品需求增长，重点客户订单和产能扩张支撑交付。",
        ),
        (
            "broker_earnings_forecast",
            "盈利预测",
            "预计公司2026年归母净利润为80亿元，对应PE为30倍，维持买入评级。",
        ),
        (
            "broker_risk_note",
            "风险提示",
            "若客户资本开支不及预期，订单放量和收入增长可能受到影响。",
        ),
    ],
)
def test_digest_admits_claim_with_evidence_per_family(card_type, heading, text):
    from broker_research_digest import build_broker_research_digest_cards

    page_count = 18 if card_type == "broker_product_driver" else 4
    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=page_count),
        f"{heading}\n{text}",
        max_cards=8,
    )
    matching = [c for c in cards if c["card_type"] == card_type]
    assert len(matching) == 1
    assert text in matching[0]["source_excerpt"]


def test_digest_selects_complementary_units_and_drops_semantic_duplicate():
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    产品布局
    AI算力资本开支持续增长，高速互联需求保持高景气。
    800G与1.6T产品进入重点客户验证，订单和产能扩张支撑交付。
    AI算力需求保持高景气，高速互联市场继续增长。
    """
    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=18), text, max_cards=8
    )
    driver = next(c for c in cards if c["card_type"] == "broker_product_driver")
    excerpt = driver["source_excerpt"]

    assert "AI算力资本开支持续增长，高速互联需求保持高景气。" in excerpt
    assert "800G与1.6T产品进入重点客户验证，订单和产能扩张支撑交付。" in excerpt
    assert "AI算力需求保持高景气，高速互联市场继续增长。" not in excerpt
    assert excerpt.index("800G") > excerpt.index("AI算力资本")


def test_digest_core_view_accepts_causal_business_reason_without_numbers():
    from broker_research_digest import build_broker_research_digest_cards

    sentence = "AI算力需求增长推动高端产品放量，形成持续增长动力。"
    cards = build_broker_research_digest_cards(
        _research_item(), f"核心观点\n{sentence}", max_cards=3
    )

    core = next(c for c in cards if c["card_type"] == "broker_core_view")
    assert sentence in core["source_excerpt"]


def test_digest_keeps_same_wording_forecasts_with_distinct_periods_and_values():
    from broker_research_digest import build_broker_research_digest_cards

    first = "预计公司2026年收入为100亿元，同比增长20%。"
    second = "预计公司2027年收入为130亿元，同比增长30%。"
    cards = build_broker_research_digest_cards(
        _research_item(), f"盈利预测\n{first}\n{second}", max_cards=3
    )

    forecast = next(c for c in cards if c["card_type"] == "broker_earnings_forecast")
    assert first in forecast["source_excerpt"]
    assert second in forecast["source_excerpt"]


def _units_from_excerpt(excerpt: str) -> list[str]:
    return [
        unit.strip() + mark
        for unit, mark in re.findall(r"([^。；;！？!?]+)([。；;！？!?])", excerpt)
        if unit.strip()
    ]


def test_digest_selected_units_are_ordered_source_substrings_in_cleaned_text():
    from broker_research_digest import (
        build_broker_research_digest_cards,
        clean_broker_research_excerpt_text,
    )

    text = """
    投资要点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，毛利率为51.63%。
    下游云厂商资本开支持续扩张，800G与1.6T高速光模块需求延续高景气。
    客户订单和产品结构升级推动收入增长，毛利率有望受规模效应改善。
    """
    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=18), text, max_cards=8
    )
    core = next(c for c in cards if c["card_type"] == "broker_core_view")
    excerpt = core["source_excerpt"]
    source = clean_broker_research_excerpt_text(text)
    units = _units_from_excerpt(excerpt)
    assert units

    last_pos = -1
    for unit in units:
        pos = source.find(unit)
        assert pos >= 0, f"unit not in source: {unit}"
        assert pos > last_pos, f"unit order wrong: {unit}"
        last_pos = pos


def test_digest_preserves_cross_heading_product_driver_complementarity():
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    产业趋势
    AI算力基础设施投资持续增长，800G与1.6T高速光模块需求快速提升。
    公司通过预付账款、长期协议和产能扩张提升订单交付确定性。

    竞争格局
    公司在硅光芯片、自研能力和重点客户联合开发方面形成交付优势。
    """
    cards = build_broker_research_digest_cards(
        _research_item(pdf_page_count=18), text, max_cards=8
    )
    driver = next(c for c in cards if c["card_type"] == "broker_product_driver")
    excerpt = driver["source_excerpt"]

    assert "800G与1.6T高速光模块需求快速提升" in excerpt
    assert "硅光芯片" in excerpt
    assert "自研能力" in excerpt
    assert "重点客户联合开发" in excerpt


def test_digest_rejects_incoherent_fallback_without_business_reason():
    from broker_research_digest import build_broker_research_digest_cards

    text = "公司长期发展前景良好，业务布局持续优化，市场份额稳步提升，盈利能力不断改善，经营质量持续提高。"
    cards = build_broker_research_digest_cards(_research_item(), text, max_cards=3)
    assert cards == []


# ---------------------------------------------------------------------------
# Layout-aware PDF extraction tests (use real PDFs from smoke cache)
# ---------------------------------------------------------------------------


_SMOKE_PDF_DIR = Path("/private/tmp/eastmoney_research_pdf_smoke")


def _sample_pdf(name_substring: str) -> Path | None:
    if not _SMOKE_PDF_DIR.exists():
        return None
    for pdf in sorted(_SMOKE_PDF_DIR.glob("*.pdf")):
        if name_substring in pdf.name:
            return pdf
    return None


@pytest.mark.skipif(
    not _SMOKE_PDF_DIR.exists(), reason="smoke PDF cache not available"
)
def test_layout_extract_pdf_text_excludes_header_footer() -> None:
    from broker_research_digest import extract_pdf_text

    pdf_path = _sample_pdf("中邮证券")
    if pdf_path is None:
        pytest.skip("sample PDF not found")
    text = extract_pdf_text(str(pdf_path))

    # Headers and footers should be removed by y-margin filtering.
    assert "请务必阅读" not in text
    assert "证券研究报告：" not in text


@pytest.mark.skipif(
    not _SMOKE_PDF_DIR.exists(), reason="smoke PDF cache not available"
)
def test_layout_extract_pdf_text_excludes_page_one_chart_sidebar() -> None:
    from broker_research_digest import extract_pdf_text

    pdf_path = _sample_pdf("中邮证券")
    if pdf_path is None:
        pytest.skip("sample PDF not found")
    text = extract_pdf_text(str(pdf_path))

    # The "个股表现" stock-chart sidebar and its percentage labels should be gone.
    assert "个股表现" not in text
    assert "乐鑫科技 电子" not in text
    assert "55%" not in text
    assert "46%" not in text


@pytest.mark.skipif(
    not _SMOKE_PDF_DIR.exists(), reason="smoke PDF cache not available"
)
def test_layout_extract_pdf_text_preserves_main_body() -> None:
    from broker_research_digest import extract_pdf_text

    # Use the 中际旭创/西南证券 report which has rich body text.
    pdf_path = _sample_pdf("西南证券")
    if pdf_path is None:
        pytest.skip("sample PDF not found")
    text = extract_pdf_text(str(pdf_path))

    assert len(text) >= 500
    assert "800G" in text or "1.6T" in text
    assert "中际旭创" in text or "光模块" in text


def test_generic_risk_with_financial_table_is_dropped_but_specific_risk_survives() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    generic_with_table = """
    风险提示
    消费类需求复苏不及预期的风险，行业竞争加剧的风险等。
    营业收入 2025A 2026E 2027E 2028E 3,898 4,931 6,154 7,495
    营业成本 销售费用 管理费用 研发费用 归母净利润 每股收益 P/E P/B ROE
    """

    assert build_broker_research_digest_cards(_research_item(), generic_with_table) == []

    specific = """
    风险提示
    个别物料短缺导致出货量不及预期，汇兑损失、关税政策导致毛利率下行，
    北美CSP资本开支阶段性节奏变化导致光模块拉货波动，Scaleup CPO/NPO市场份额不及预期。
    """

    cards = build_broker_research_digest_cards(_research_item(), specific)

    assert len(cards) == 1
    assert cards[0]["card_type"] == "broker_risk_note"
    assert cards[0]["knowledge_eligible"] is True
    assert cards[0]["viewpoint_cluster"] == "risk_supply_chain_fx_tariff_capex_share"


def test_earnings_forecast_is_display_only_not_knowledge_eligible() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    盈利预测
    由于新产品放量和份额提升，收入的规模效应摊薄期间费用，我们上调公司
    2026-2028年归母净利润至8.48/12.53/17.67亿元，对应PE分别为72/49/35倍。
    """

    cards = build_broker_research_digest_cards(_research_item(), text)

    assert len(cards) == 1
    assert cards[0]["card_type"] == "broker_earnings_forecast"
    assert cards[0]["display_only"] is True
    assert cards[0]["knowledge_eligible"] is False
    assert cards[0]["viewpoint_cluster"] == "earnings_forecast"


def test_table_only_earnings_forecast_is_dropped() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    财务数据与估值
    会计年度 2024A 2025A 2026E 2027E 2028E
    营业收入 23862 38240 110450 186757 277988
    营业成本 15796 22166 58636 97099 147898
    净利润 5171 10797 36896 65527 92201
    EPS 4.64 9.70 33.13 58.84 82.80
    P/E 237.5 113.8 33.3 18.7 13.3
    P/B 64.2 41.3 18.7 9.9 7.1
    """

    assert build_broker_research_digest_cards(_research_item(), text) == []


def test_financial_result_commentary_core_view_is_knowledge_eligible() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    核心观点
    公司2026年一季度实现收入10.98亿元，同比增长39.08%，归母净利润1.24亿元，
    同比增长107%，毛利率为51.63%，净利率11.18%。
    """

    cards = build_broker_research_digest_cards(_research_item(), text)

    assert len(cards) == 1
    assert cards[0]["card_type"] == "broker_core_view"
    assert cards[0]["display_only"] is False
    assert cards[0]["knowledge_eligible"] is True
    assert cards[0]["viewpoint_cluster"] == "earnings_growth_snapshot"


def test_long_report_keeps_multiple_distinct_generic_driver_blocks() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    摘要
    本报告围绕公司经营进展展开分析。

    需求端来看，核心下游客户持续扩张基础设施规模，800G产品需求延续高景气，
    1.6T产品验证进度加快，相关订单有望推动公司高端产品收入占比提升。

    供给端来看，公司通过提前锁定上游资源、扩充产能和优化供应链管理提升交付能力，
    在旺盛需求下保障重点客户项目交付，库存和预付款安排体现订单确定性。

    技术路线来看，公司持续推进硅光方案和高速产品迭代，围绕下一代互联规格加强研发，
    产品升级有助于维持客户粘性和份额优势。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=20), text, max_cards=5)
    driver_cards = [card for card in cards if card["card_type"] == "broker_product_driver"]

    assert len(driver_cards) >= 2
    clusters = {card["viewpoint_cluster"] for card in driver_cards}
    assert len(clusters) >= 2
    excerpts = "\n".join(card["source_excerpt"] for card in driver_cards)
    assert "高端产品收入占比" in excerpts
    assert "交付能力" in excerpts


def test_rating_table_fragment_is_not_selected_as_driver_block() -> None:
    from broker_research_digest import build_broker_research_digest_cards

    text = """
    市场中相关报告评级比率分析 市场中相关报告 日期 一周内 一月内 二月内 三月内 六月内
    买入 1 9 12 22 61 增持 0 2 4 8 0 中性 0 0 0 0 0 减持 0 0 0 0 0
    投资评级的说明：买入：预期未来6－12个月内上涨幅度在15%以上；
    增持：预期未来6－12个月内上涨幅度在5%－15%；中性：预期未来6－12个月内变动幅度在-5%－5%。

    需求端来看，核心下游客户持续扩张基础设施规模，800G产品需求延续高景气，
    1.6T产品验证进度加快，相关订单推动高端产品收入占比提升。
    """

    cards = build_broker_research_digest_cards(_research_item(pdf_page_count=18), text, max_cards=5)
    excerpts = "\n".join(card["source_excerpt"] for card in cards)

    assert "投资评级的说明" not in excerpts
    assert "买入：预期未来" not in excerpts
    assert "高端产品收入占比" in excerpts


def test_deduplicates_same_viewpoint_cluster_but_preserves_distinct_clusters() -> None:
    from broker_research_digest import deduplicate_broker_digest_cards_by_viewpoint

    same_weaker = {
        "card_type": "broker_core_view",
        "viewpoint_cluster": "optical_module_scaleup",
        "quality_score": 20,
        "source_excerpt": "800G光模块需求增长。",
        "stock_code": "300308",
    }
    same_stronger = {
        "card_type": "broker_core_view",
        "viewpoint_cluster": "optical_module_scaleup",
        "quality_score": 40,
        "source_excerpt": "800G和1.6T光模块快速放量，Scaleup产品份额提升。",
        "stock_code": "300308",
    }
    distinct = {
        "card_type": "broker_risk_note",
        "viewpoint_cluster": "risk_supply_chain_fx_tariff_capex_share",
        "quality_score": 25,
        "source_excerpt": "物料短缺、汇兑和关税导致毛利率下行。",
        "stock_code": "300308",
    }

    selected = deduplicate_broker_digest_cards_by_viewpoint(
        [same_weaker, distinct, same_stronger]
    )

    assert selected == [same_stronger, distinct]


def test_dedup_preserves_same_viewpoint_from_distinct_institutions() -> None:
    from broker_research_digest import deduplicate_broker_digest_cards_by_viewpoint

    first = {
        "card_type": "broker_core_view",
        "viewpoint_cluster": "optical_module_scaleup",
        "quality_score": 20,
        "source_excerpt": "800G光模块需求增长。",
        "institution": "甲证券",
        "stock_code": "300308",
    }
    second = {
        "card_type": "broker_core_view",
        "viewpoint_cluster": "optical_module_scaleup",
        "quality_score": 40,
        "source_excerpt": "800G和1.6T光模块快速放量。",
        "institution": "乙证券",
        "stock_code": "300308",
    }

    selected = deduplicate_broker_digest_cards_by_viewpoint([first, second])

    assert selected == [first, second]


def test_dedup_preserves_long_report_body_card_against_short_commentary_duplicate() -> None:
    from broker_research_digest import deduplicate_broker_digest_cards_by_viewpoint

    short_commentary = {
        "card_type": "broker_product_driver",
        "viewpoint_cluster": "business_driver_market_demand_product_mix",
        "quality_score": 84,
        "source_excerpt": "短评：800G和1.6T高速光模块同步放量，营收与利润共振。",
        "stock_code": "300308",
        "report_length_class": "short",
        "source_heading": "投资要点",
    }
    long_body = {
        "card_type": "broker_product_driver",
        "viewpoint_cluster": "business_driver_market_demand_product_mix",
        "quality_score": 68,
        "source_excerpt": "长研报正文：公司形成高速光模块为收入基础、AI高端产品为核心增长引擎、供应链能力作为关键支撑的业务结构。",
        "stock_code": "300308",
        "report_length_class": "long",
        "source_heading": "公司业务概况",
    }

    selected = deduplicate_broker_digest_cards_by_viewpoint([short_commentary, long_body])

    assert selected == [short_commentary, long_body]
