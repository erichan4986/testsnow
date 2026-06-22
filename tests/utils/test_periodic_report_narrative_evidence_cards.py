"""Tests for periodic_report_narrative_evidence_cards helper."""

import hashlib
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_narrative_evidence_cards import (
    build_periodic_report_narrative_evidence_cards,
)


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def test_empty_evidence_pack_returns_empty_cards_and_diagnostics():
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack={
            "schema_version": "periodic_report_evidence_pack.v1",
            "blocks": [],
        },
    )
    assert result["schema_version"] == "periodic_report_narrative_evidence_cards.v1"
    assert result["stock_code"] == "300777"
    assert result["stock_name"] == "中简科技"
    assert result["report_year"] == 2025
    assert result["report_type"] == "annual"
    assert result["cards"] == []
    assert any(d["code"] == "empty_evidence_pack" for d in result["diagnostics"])


def test_business_model_card_from_company_description_block():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "报告期内公司从事的主要业务",
                "text": (
                    "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。"
                    "产品主要应用于航空航天、轨道交通、新能源等领域。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    cards = result["cards"]
    assert len(cards) >= 1
    card = cards[0]
    assert card["card_type"] == "business_model"
    assert card["source_block_id"] == "business_overview-0"
    assert card["evidence_refs"] == ["business_overview-0"]
    assert "高性能碳纤维" in card["source_excerpt"]


def test_cards_include_stable_excerpt_and_block_hashes():
    block_text = (
        "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务，"
        " 主要产品应用于航空航天、轨道交通、新能源等领域，并持续服务核心客户。"
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "报告期内公司从事的主要业务",
                "text": block_text,
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    card = result["cards"][0]
    assert re.fullmatch(r"[0-9a-f]{64}", card["source_excerpt_hash"])
    assert re.fullmatch(r"[0-9a-f]{64}", card["source_block_hash"])
    assert card["source_excerpt_hash"] == _normalized_hash(card["source_excerpt"])
    assert card["source_block_hash"] == _normalized_hash(block_text)

    whitespace_variant = {
        **evidence_pack,
        "blocks": [
            {
                **evidence_pack["blocks"][0],
                "text": block_text.replace("， ", "，   \n  "),
            }
        ],
    }
    variant = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=whitespace_variant,
    )
    assert variant["cards"][0]["source_block_hash"] == card["source_block_hash"]


def test_management_market_view_card_from_industry_judgment_block():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": (
                    "碳纤维行业由规模竞争逐步转向价值竞争。高端航空航天用碳纤维需求保持增长，"
                    "低端通用级碳纤维产能过剩，价格承压。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) >= 1
    card = cards[0]
    assert card["source_block_id"] == "industry_outlook-0"
    assert "价格承压" in card["source_excerpt"]


def test_rd_product_progress_card_from_certification_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "rd_table-0",
                "usage": "rd_table",
                "section": "第三节 管理层讨论与分析",
                "title": "研发项目",
                "text": (
                    "公司持续推动ZT9H系列碳纤维的工程化应用和产业化，相关产品已通过主机厂认证并进入小批量供货阶段。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    cards = [c for c in result["cards"] if c["card_type"] == "rd_product_progress"]
    assert len(cards) >= 1
    card = cards[0]
    assert card["source_block_id"] == "rd_table-0"
    assert "ZT9H" in card["source_excerpt"]


def test_rd_product_progress_card_from_debang_like_rd_progress_block():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "rd_product_progress-0",
                "usage": "rd_product_progress",
                "section": "第三节 管理层讨论与分析",
                "title": "报告期内的主要研发成果",
                "text": (
                    "报告期内，公司开发的 TIM1 热界面材料专为高功率芯片散热管理设计，"
                    "超薄型 TIM、液态金属复合导热膏、高可靠合金导热片、光模块导热材料等产品"
                    "已进入客户验证或小批量交付阶段。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "rd_product_progress"]
    assert len(cards) >= 1
    assert "TIM1" in cards[0]["source_excerpt"]
    assert "小批量交付" in cards[0]["source_excerpt"]


def test_margin_competitiveness_card_from_debang_like_margin_commentary():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "profitability_commentary-0",
                "usage": "profitability_commentary",
                "section": "第三节 管理层讨论与分析",
                "title": "主营业务分产品情况",
                "text": (
                    "集成电路封装材料受益于先进封装需求拉动，全年收入同比增长，"
                    "毛利率同比提升 2.98 个百分点；智能终端封装材料受产品结构影响，"
                    "毛利率同比小幅降低；新能源应用材料全年营收同比增长 20.03%，毛利率基本持平。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "margin_competitiveness"]
    assert len(cards) >= 1
    assert "毛利率同比提升 2.98 个百分点" in cards[0]["source_excerpt"]
    assert "毛利率基本持平" in cards[0]["source_excerpt"]


def test_margin_competitiveness_keeps_narrative_with_revenue_numbers():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "profitability_commentary-0",
                "usage": "profitability_commentary",
                "section": "第三节 管理层讨论与分析",
                "title": "主营业务分产品情况",
                "text": (
                    "毛利率同比提升 2.98 个百分点；智能终端封装材料依托核心头部客户群优势，"
                    "全年实现营收 38,325.99 万元，同比增长 48.16%。"
                    "受供应链价格波动等因素影响，毛利率同比小幅降低。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "margin_competitiveness"]
    assert len(cards) >= 1
    assert "全年实现营收 38,325.99 万元" in cards[0]["source_excerpt"]
    assert "毛利率同比小幅降低" in cards[0]["source_excerpt"]


def test_margin_competitiveness_keeps_later_product_margin_sentence():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "profitability_commentary-0",
                "usage": "profitability_commentary",
                "section": "第三节 管理层讨论与分析",
                "title": "主营业务分产品情况",
                "text": (
                    "毛利率同比提升 2.98 个百分点；智能终端封装材料依托核心头部客户群优势，"
                    "公司在巩固提升老产品市场份额的同时，加大产品创新及市场开拓力度，"
                    "在智能穿戴、新型显示等应用场景开辟了新的增长空间，全年实现营收 38,325.99 万元，"
                    "同比增长 48.16%。受供应链价格波动等因素影响，毛利率同比小幅降低；"
                    "新能源应用材料在下游新能源装机出货量持续稳定增长的驱动下，公司新产线投产，"
                    "产能释放，收入规模持续扩大，同时围绕核心客户优化交付节奏并提升自动化生产效率，"
                    "持续推进原材料采购、生产工艺和订单结构优化，进一步强化规模化制造能力和快速响应能力，"
                    "公司通过新增产线爬坡、提高良率、优化配方和扩大订单覆盖提升运营效率，"
                    "并结合客户项目节奏持续改善交付稳定性，推动新能源应用材料板块收入规模继续扩大，"
                    "同时在价格竞争和供应链波动环境下保持谨慎的成本管控策略，"
                    "在产线自动化、关键设备维护、原材料替代验证、客户交期协同和质量控制体系方面持续投入，"
                    "使得该业务在收入快速增长的同时能够维持较好的生产组织效率和成本弹性，"
                    "并在多品类订单切换过程中降低工艺波动对单位成本的扰动，"
                    "全年实现营收 80,884.65 万元，同比增长 18.06%。"
                    "随着产能爬坡和成本优化，毛利率基本持平。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "margin_competitiveness"]
    assert len(cards) >= 1
    assert "毛利率同比提升 2.98 个百分点" in cards[0]["source_excerpt"]
    assert "毛利率同比小幅降低" in cards[0]["source_excerpt"]
    assert "毛利率基本持平" in cards[0]["source_excerpt"]


def test_financial_note_card_from_impairment_note():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "asset_impairment_note-0",
                "usage": "asset_impairment_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "受下游需求放缓影响，部分存货可变现净值低于账面成本，公司基于谨慎性原则计提存货跌价准备。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    cards = [c for c in result["cards"] if c["card_type"] == "financial_note"]
    assert len(cards) >= 1
    card = cards[0]
    assert card["source_block_id"] == "asset_impairment_note-0"
    assert "存货跌价准备" in card["source_excerpt"]


def test_financial_note_rejects_generic_accounting_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货",
                "text": (
                    "存货跌价准备 资产负债表日，存货采用成本与可变现净值孰低计量，"
                    "按照成本高于可变现净值的差额计提存货跌价准备。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_generic_inventory_valuation_basis_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货",
                "text": (
                    "在确定存货的可变现净值时，以取得的确凿证据为基础，"
                    "同时考虑持有存货的目的以及资产负债表日后事项的影响。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="301269",
        stock_name="华大九天",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_generic_significant_influence_policy_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "investment_policy-0",
                "usage": "financial_assets_note",
                "section": "第十节 财务报告",
                "title": "长期股权投资",
                "text": (
                    "参与被投资单位的政策制定过程；向被投资单位派出管理人员；"
                    "被投资单位依赖投资公司的技术或技术资料；与被投资单位之间发生重要交易。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="301269",
        stock_name="华大九天",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_generic_equity_method_policy_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "investment_policy-0",
                "usage": "financial_assets_note",
                "section": "第十节 财务报告",
                "title": "长期股权投资",
                "text": (
                    "后续计量及损益确认方法 本公司能够对被投资单位实施控制的长期股权投资采用成本法核算，"
                    "对联营企业和合营企业的长期股权投资采用权益法核算。"
                    "按照《企业会计准则第 22 号——金融工具确认和计量》的有关规定处理。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="301269",
        stock_name="华大九天",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_debang_like_inventory_impairment_policy_heading():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货跌价",
                "text": (
                    "存货跌价准备的确认标准和计提方法 √适用 □不适用 "
                    "在资产负债表日，存货按照成本与可变现净值孰低计量。"
                    "当其可变现净值低于成本时，提取存货跌价准备。"
                    "存货跌价准备通常按单个存货项目的成本高于其可变现净值的差额提取。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_inventory_impairment_reversal_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货",
                "text": (
                    "计提存货跌价准备后，如果以前减记存货价值的影响因素已经消失，"
                    "导致存货的可变现净值高于其账面价值的，在原已计提的存货跌价准备金额内予以转回，"
                    "转回的金额计入当期损益。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_long_term_equity_investment_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "长期股权投资",
                "text": (
                    "对于同一控制下的企业合并取得的长期股权投资，在合并日按照被合并方股东权益"
                    "在最终控制方合并财务报表中的账面价值的份额作为长期股权投资的初始投资成本。"
                    "长期股权投资初始投资成本与支付的现金、转让的非现金资产以及所承担债务账面价值之间的差额，"
                    "调整资本公积；资本公积不足冲减的，调整留存收益。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_disposal_group_impairment_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "对于持有待售的处置组确认的资产减值损失金额，先抵减处置组中商誉的账面价值，"
                    "再根据处置组中的各项非流动资产账面价值所占比重，按比例抵减其账面价值。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_measurement_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "持有待售的非流动资产或处置组的会计处理 初始计量和后续计量时，"
                    "其账面价值高于公允价值减去出售费用后的净额的，将账面价值减记至公允价值减去出售费用后的净额。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_borrowing_cost_capitalization_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "借款费用",
                "text": (
                    "21、借款费用 1. 借款费用资本化的确认原则 "
                    "本公司发生的借款费用，可直接归属于符合资本化条件的资产的购建或者生产的，"
                    "予以资本化，计入相关资产成本；其他借款费用，在发生时根据其发生额确认为费用，计入当期损益。"
                    "符合资本化条件的资产，是指需要经过相当长时间的购建或者生产活动才能达到预定可使用"
                    "或者可销售状态的固定资产、投资性房地产和存货等资产。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="301269",
        stock_name="华大九天",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_held_for_sale_policy_without_company_specific_context():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "不再继续划分为持有待售类别以及终止确认的会计处理，非流动资产或处置组因不再满足持有待售类别的划分条件而不再继续划分为持有待售类别，"
                    "按照划分为持有待售类别前的账面价值与可收回金额两者孰低计量。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_held_for_sale_policy_even_with_impairment_terms():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "持有待售的非流动资产或处置组的会计处理，初始计量和后续计量时，"
                    "将账面价值减记至公允价值减去出售费用后的净额，减记的金额确认为资产减值损失，"
                    "计入当期损益，同时计提持有待售资产减值准备。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_impairment_reversal_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "资产减值损失转回的会计处理 后续资产负债表日持有待售的非流动资产公允价值减去出售费用后的净额增加的，"
                    "以前减记的金额予以恢复，并在划分为持有待售类别后确认的资产减值损失金额内转回，转回金额计入当期损益。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_keeps_company_specific_impairment_explanation():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "asset_impairment_note-0",
                "usage": "asset_impairment_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "报告期内，因部分待安装设备与现有生产线适配性不足，"
                    "公司对在建工程相关设备计提资产减值准备。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "financial_note"]
    assert len(cards) == 1
    assert "适配性不足" in cards[0]["source_excerpt"]


def test_financial_note_rejects_key_audit_matter_definition_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "audit_key_matters-0",
                "usage": "audit_key_matters",
                "section": "第十节 财务报告",
                "title": "关键审计事项",
                "text": (
                    "三、关键审计事项 关键审计事项是我们根据职业判断，认为对本期财务报表审计最为重要的事项。"
                    "这些事项的应对以对财务报表整体进行审计并形成审计意见为背景，我们不对这些事项单独发表意见。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_keeps_specific_key_audit_matter_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "audit_key_matters-0",
                "usage": "audit_key_matters",
                "section": "第十节 财务报告",
                "title": "关键审计事项",
                "text": (
                    "收入确认：公司产品销售收入金额重大，收入确认是否恰当对财务报表影响重大，"
                    "我们将收入确认识别为关键审计事项。应收账款减值：管理层对应收账款预期信用损失进行估计。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "financial_note"]
    assert len(cards) == 1
    assert "收入确认" in cards[0]["source_excerpt"]
    assert "应收账款减值" in cards[0]["source_excerpt"]


def test_card_keys_match_allowlist_and_no_forbidden_fields():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "报告期内公司从事的主要业务",
                "text": (
                    "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。"
                    "产品主要应用于航空航天、轨道交通、新能源等领域。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    assert len(result["cards"]) >= 1
    card = result["cards"][0]
    allowed_keys = {
        "schema_version",
        "source_type",
        "card_id",
        "stock_code",
        "stock_name",
        "report_year",
        "report_type",
        "card_type",
        "title",
        "source_block_id",
        "evidence_refs",
        "source_excerpt",
        "source_excerpt_hash",
        "source_block_hash",
        "keywords",
        "confidence",
        "source_credit",
        "knowledge_eligible",
        "synthesis_eligible",
        "experimental",
    }
    assert set(card.keys()) == allowed_keys
    forbidden_keys = {
        "judgment",
        "interpretation",
        "claim_status",
        "verification_status",
        "report_eligible",
        "knowledge_persisted",
        "output_path",
        "planned_path",
    }
    for key in forbidden_keys:
        assert key not in card
    assert card["knowledge_eligible"] is False
    assert card["synthesis_eligible"] is False
    assert card["experimental"] is True
    assert card["source_credit"] == 75
    assert card["source_type"] == "periodic_report_narrative_evidence"
    assert re.match(
        r"^periodic:300777:2025:annual:narrative:business_model:\d+$",
        card["card_id"],
    )


def test_operation_update_card_from_production_sales_inventory_block():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "production_sales_inventory_table-0",
                "usage": "production_sales_inventory_table",
                "section": "第三节 管理层讨论与分析",
                "title": "产销库存",
                "text": (
                    "报告期内，公司碳纤维产品产量同比增长百分之十五，销量同比增长百分之十二，"
                    "期末库存同比下降百分之八，主要得益于下游航空航天客户需求回暖。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    cards = [c for c in result["cards"] if c["card_type"] == "operation_update"]
    assert len(cards) >= 1
    card = cards[0]
    assert card["source_block_id"] == "production_sales_inventory_table-0"
    assert "销量" in card["source_excerpt"]


def test_multiple_applicability_checkbox_fragment_is_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "management_strategy-0",
                "usage": "management_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "关键技术指标",
                "text": (
                    "产品或业务适用的关键技术或性能指标情况 从事通信传输设备或其零部件制造适用的关键技术或性能指标 "
                    "□适用 不适用 从事通信交换设备或其零部件制造适用的关键技术或性能指标 □适用 不适用 "
                    "从事通信接入设备或其零部件制造适用的关键技术或性能指标 适用 □不适用 "
                    "产品名称 接入网类型 传输速率 带宽 利用率 控制管理软件性能指标 光模块 光纤接入 详见下文 不适用 不适用 "
                    "从事通信配套服务的关键技术或性能指标 □适用 不适用 "
                    "传输速率是指理论上能达到的最高传输速率，公司产品传输速率主要为100G/200G/400G/800G/1.6T。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_applicability_checkbox_marker_is_stripped_from_useful_strategy_excerpt():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "公司发展战略",
                "text": (
                    "(二) 公司发展战略 √适用 □不适用 公司以成为全球高端封装材料引领者为愿景，"
                    "围绕技术创新、突破增长、高效运营、国际拓展四个战略主题，"
                    "持续为客户、员工、股东与社会创造长期价值。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] in {"management_market_view", "market_outlook"}]
    assert cards
    assert "√适用" not in cards[0]["source_excerpt"]
    assert "□不适用" not in cards[0]["source_excerpt"]
    assert "全球高端封装材料引领者" in cards[0]["source_excerpt"]


def test_management_market_view_keeps_competitive_position_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业竞争格局及公司竞争地位",
                "text": (
                    "光模块头部厂商凭借领先的研发实力及交付能力，竞争优势进一步强化，行业集中度有望持续提升。"
                    "公司凭借技术研发能力、低成本产品制造能力和全面交付能力等优势，赢得海内外客户认可，并保持市场份额持续成长。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert "市场份额持续成长" in cards[0]["source_excerpt"]


def test_management_market_view_keeps_market_outlook_and_company_strategy_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "management_market_view-0",
                "usage": "management_market_view",
                "section": "第三节 管理层讨论与分析",
                "title": "公司未来发展的展望",
                "text": (
                    "未来数通光模块市场需求有望由算力集群扩张、网络架构迭代、ASIC芯片规模化部署等因素共同驱动。"
                    "公司将持续专注于AI数据中心等核心市场，进一步加大1.6T、3.2T及以上高速率光模块、硅光、相干等核心产品或技术的投入与研究。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert "算力集群扩张" in cards[0]["source_excerpt"]
    assert "1.6T" in cards[0]["source_excerpt"]
    assert not any(c["card_type"] == "operation_update" for c in result["cards"])


def test_management_market_view_keeps_numeric_market_outlook_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业发展情况",
                "text": (
                    "光模块是AI投资中网络端的重要环节，根据LightCounting预测，2026年全球数通光模块市场规模有望达到228亿美元，"
                    "预计2030年整体市场规模将增长至414亿美元，对应2025-2030年复合增长率为20%。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert "414亿美元" in cards[0]["source_excerpt"]


def test_market_outlook_card_type_from_market_demand_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "market_demand_outlook-0",
                "usage": "market_demand_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "市场需求",
                "text": (
                    "未来数通光模块市场需求有望由算力集群扩张、网络架构迭代、ASIC芯片规模化部署等因素共同驱动，"
                    "预计800G和1.6T等高速光模块需求将占据市场主导地位。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "market_outlook"]
    assert len(cards) == 1
    assert cards[0]["title"] == "市场前景判断"
    assert "市场需求" in cards[0]["source_excerpt"]


def test_margin_competitiveness_card_type_from_profitability_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "profitability_commentary-0",
                "usage": "profitability_commentary",
                "section": "第三节 管理层讨论与分析",
                "title": "盈利能力",
                "text": (
                    "报告期内，公司高端产品出货占比提升，产品结构持续优化，规模效应逐步释放，"
                    "毛利率较上年同期提升，盈利能力持续改善。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "margin_competitiveness"]
    assert len(cards) == 1
    assert cards[0]["title"] == "毛利率与竞争力"
    assert "毛利率较上年同期提升" in cards[0]["source_excerpt"]


def test_business_model_excerpt_is_not_duplicated_as_rd_progress_card():
    text = (
        "公司主营业务为模拟芯片的研发与销售，主要产品包括电池管理芯片和电源管理芯片，"
        "产品主要应用于消费电子、工业控制等客户场景。"
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "product_capacity_profile-0",
                "usage": "product_capacity_profile",
                "section": "第三节 管理层讨论与分析",
                "title": "主要产品",
                "text": text,
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688325",
        stock_name="赛微微电",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert any(c["card_type"] == "business_model" for c in result["cards"])
    assert not any(c["card_type"] == "rd_product_progress" for c in result["cards"])


def test_identical_market_outlook_and_management_view_is_deduplicated_once():
    text = (
        "未来先进封装占比将逐步超越传统封装，Chiplet、2.5D、3D、HBM 等技术路线带动材料需求提升，"
        "国产替代从单点突破迈向全产业链系统性突破，市场规模预计持续增长。"
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来发展战略",
                "text": text,
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    matching_cards = [c for c in result["cards"] if text in c["source_excerpt"]]
    assert len(matching_cards) == 1
    assert matching_cards[0]["card_type"] in {"management_market_view", "market_outlook"}


def test_default_per_type_limit_allows_more_than_three_clean_cards():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": f"market_demand_outlook-{idx}",
                "usage": "market_demand_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "市场需求",
                "text": (
                    f"第{idx}类下游应用市场需求保持增长，行业景气度持续提升，"
                    f"公司关注客户结构变化和产品迭代机会，预计相关市场规模继续扩大。"
                ),
            }
            for idx in range(4)
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "market_outlook"]
    assert len(cards) == 4


def test_management_market_view_rejects_policy_catalog_fragment():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业发展情况",
                "text": (
                    "政策目录 主管部门 时间 相关政策内容 《2025年数字经济发展工作要点》 国家发改委 2025年 "
                    "部署7大任务，释放数据要素价值，筑牢数字基础设施，提升数字经济竞争力，支持AI创新。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_management_market_view_rejects_policy_clause_fragment():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业发展情况",
                "text": (
                    "7、完善体制机制（财税金融支持、数字人才培养）《关于促进数据产业高质量发展的指导意见》"
                    "国家发改委、国家数据局、教育部、财政部、金融监管总局、中国证监会2024年提出打造全国一体化算力体系，"
                    "数据产业结构明显优化，涌现一批具有国际竞争力的数据企业。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_management_market_view_rejects_chart_caption_fragment():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业发展情况",
                "text": (
                    "中际旭创股份有限公司2025年年度报告全文 -15- 图1：谷歌、豆包token调用量曲线 来源：中信建投证券 "
                    "为了满足快速增长的推理和训练算力需求，海内外CSP厂商逐步加大资本开支投入。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_management_market_view_keeps_profitability_commentary():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "management_market_view-0",
                "usage": "management_market_view",
                "section": "第三节 管理层讨论与分析",
                "title": "经营情况讨论",
                "text": (
                    "报告期内，公司高端产品出货占比提升，规模效应逐步释放，毛利率较上年同期提升，盈利能力持续改善。"
                    "公司将继续优化产品结构和供应链管理。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert "毛利率较上年同期提升" in cards[0]["source_excerpt"]


def test_new_high_value_narrative_usages_map_to_management_market_view_cards():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "market_demand_outlook-0",
                "usage": "market_demand_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "数通市场",
                "text": "光模块是AI投资中网络端的重要环节，预计2030年整体市场规模将增长至414亿美元，复合增长率为20%。",
            },
            {
                "id": "competitive_position-0",
                "usage": "competitive_position",
                "section": "第三节 管理层讨论与分析",
                "title": "公司竞争地位",
                "text": "公司凭借技术研发能力、低成本产品制造能力和全面交付能力等优势，保持市场份额持续成长。",
            },
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来展望",
                "text": "公司将持续专注于AI数据中心等核心市场，加大1.6T、3.2T高速率光模块、硅光、相干等技术投入。",
            },
            {
                "id": "profitability_commentary-0",
                "usage": "profitability_commentary",
                "section": "第三节 管理层讨论与分析",
                "title": "经营情况",
                "text": "报告期内高端产品出货占比提升，规模效应释放，毛利率较上年同期提升，盈利能力持续改善。",
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        max_cards_per_type=4,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 4
    joined = "\n".join(card["source_excerpt"] for card in cards)
    assert "414亿美元" in joined
    assert "市场份额持续成长" in joined
    assert "3.2T" in joined
    assert "毛利率较上年同期提升" in joined


def test_truncation_prefers_diverse_source_blocks_within_same_card_type():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "market_demand_outlook-0",
                "usage": "market_demand_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "数通市场",
                "text": (
                    "未来数通光模块市场需求有望由算力集群扩张和ASIC芯片规模化部署共同驱动，高速率产品需求提升。 "
                    "AI算力需求推动数据中心持续扩容，全球云服务厂商对GPU需求持续增长，并拉动光互连升级。 "
                    "光模块是AI投资中网络端的重要环节，全球算力投资推动市场增长，行业景气度持续提升。 "
                ),
            },
            {
                "id": "competitive_position-0",
                "usage": "competitive_position",
                "section": "第三节 管理层讨论与分析",
                "title": "竞争地位",
                "text": "公司凭借技术研发能力、低成本产品制造能力和全面交付能力等优势，保持市场份额持续成长。",
            },
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来展望",
                "text": "公司将持续专注于AI数据中心等核心市场，加大1.6T、3.2T高速率光模块、硅光、相干等技术投入。",
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        max_cards_per_type=3,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 3
    assert {card["source_block_id"] for card in cards} == {
        "market_demand_outlook-0",
        "competitive_position-0",
        "future_strategy-0",
    }


def test_table_only_dense_numeric_snippets_are_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "segment_table-0",
                "usage": "segment_table",
                "section": "第三节 管理层讨论与分析",
                "title": "分产品收入",
                "text": (
                    "分产品 营业收入 营业成本 毛利率 营业收入同比 毛利率同比\n"
                    "碳纤维 500,000,000.00 350,000,000.00 30.00% -10.00% -2.00%\n"
                    "碳纤维织物 600,000,000.00 360,000,000.00 40.00% 15.00% 3.00%"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    assert result["cards"] == []
    assert any(d["code"] == "no_candidate_snippets" for d in result["diagnostics"])


def test_investment_status_table_fragments_are_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "ar_aging_note-0",
                "usage": "ar_aging_note",
                "section": "第十节 财务报告",
                "title": "投资状况",
                "text": (
                    "七、投资状况分析 1、总体情况 适用 □不适用 "
                    "报告期投资额（元） 上年同期投资额（元） 变动幅度。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_spaced_multiple_applicability_checkbox_fragment_is_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "management_strategy-0",
                "usage": "management_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "关键技术指标",
                "text": (
                    "从事通信传输设备或其零部件制造适用的关键技术或性能指标 □适用  不适用 "
                    "从事通信接入设备或其零部件制造适用的关键技术或性能指标 适用  □不适用 "
                    "产品名称 接入网类型 传输速率 光模块 光纤接入 详见下文 不适用 不适用 "
                    "从事通信配套服务的关键技术或性能指标 □适用  不适用 "
                    "公司产品传输速率主要为 100G/200G/400G/800G/1.6T，报告期内未发生重大变化。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_single_applicability_checkbox_report_tail_fragment_is_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "主营业务",
                "text": "主营业务情况 □适用 √不适用 广东赛微微电子股份有限公司 2025 年年度报告",
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688325",
        stock_name="赛微微电",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_product_feature_table_header_is_trimmed_from_narrative_excerpt():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "glossary-0",
                "usage": "glossary",
                "section": "第一节 释义",
                "title": "常用词语释义",
                "text": (
                    "电池计量芯片 指 用于确定电池的电量状态和健康状态。 "
                    "FastCali 指 一种电池电量算法。"
                ),
            },
            {
                "id": "management_strategy-0",
                "usage": "management_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "主要产品",
                "text": (
                    "公司电池计量芯片主要产品如下表所示： 产品类型 图片示例 主要技术特点 主要应用领域 "
                    "电池计量芯片 结合FastCali电池电量算法和电池建模信息，准确计算电池剩余电量，"
                    "可监测电池在充放电状态下的电压、电流和温度。"
                    "依托于公司自主研发的FastCali电池电量算法，公司电池计量芯片可以快速计算电池状态，"
                    "精准提供电池生命周期内电池荷电状态。"
                ),
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688325",
        stock_name="赛微微电",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "rd_product_progress"]
    assert len(cards) == 1
    excerpt = cards[0]["source_excerpt"]
    assert "产品类型" not in excerpt
    assert "图片示例" not in excerpt
    assert "主要技术特点" not in excerpt
    assert "依托于公司自主研发的FastCali" in excerpt


def test_structural_table_header_snippets_are_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "rd_table-0",
                "usage": "rd_table",
                "section": "第三节 管理层讨论与分析",
                "title": "研发项目",
                "text": (
                    "主要研发项目名称 项目目的 项目进展 拟达到的目标 预计对公司未来发展的影响 "
                    "国产 T1100 级碳纤维材料制备技术研发 研制湿纺制备 T1100 碳纤维 项目目标已达成。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_toc_dot_leader_snippets_are_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "目录",
                "title": "目录",
                "text": "第三节 管理层讨论与分析 ........................ 15",
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    assert result["cards"] == []


def test_llm_judgment_phrases_are_rejected_unless_verbatim_in_source():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": (
                    "碳纤维行业竞争加剧，高端产品需求增长放缓，"
                    "这意味着公司毛利率将持续承压，需要跟踪下游需求变化。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    assert result["cards"] == []

    # Verbatim phrase in the original excerpt should be kept if other markers match.
    evidence_pack_verbatim = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": (
                    "年报原文提到需要跟踪的下游客户包括航空航天主机厂和轨道交通装备企业，"
                    "行业需求保持增长。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack_verbatim,
    )
    assert any("需要跟踪" in c["source_excerpt"] for c in result["cards"])


def test_original_report_phrase_with_shuoming_is_not_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "asset_impairment_note-0",
                "usage": "asset_impairment_note",
                "section": "第十节 财务报告",
                "title": "资产减值",
                "text": (
                    "年报附注说明，受下游需求放缓影响，部分存货可变现净值低于账面成本，"
                    "公司基于谨慎性原则计提存货跌价准备。"
                ),
            }
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert any("年报附注说明" in c["source_excerpt"] for c in result["cards"])


def test_within_type_cards_are_ranked_by_score_then_source_order():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": "行业整体运行保持平稳，公司围绕重点客户应用场景持续完善产品布局并推进服务能力建设。",
            },
            {
                "id": "industry_outlook-1",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": "行业竞争格局发生变化，国产替代需求提升，高端市场价格承压，公司持续关注政策和技术周期变化。",
            },
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        max_cards_per_type=1,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert cards[0]["source_block_id"] == "industry_outlook-1"
    assert "国产替代" in cards[0]["source_excerpt"]


def test_glossary_terms_boost_company_specific_technical_sentences():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "glossary-0",
                "usage": "glossary",
                "section": "第一节 释义",
                "title": "释义",
                "text": (
                    "释义项 指 释义内容 "
                    "PDK 指 Process Design Kit，即工艺设计套件。 "
                    "PPA 指 功耗、性能、面积，芯片设计中的核心评估指标。 "
                    "版图验证 指 对芯片版图进行规则检查和验证。 "
                    "半导体 指 常温下导电性能介于导体与绝缘体之间的材料。"
                ),
            },
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": "行业竞争加剧，市场需求保持增长，公司关注政策变化并提升经营效率。",
            },
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来展望",
                "text": "公司将围绕PDK、PPA和版图验证能力完善产品矩阵，持续提升先进制程市场服务能力和客户支持能力。",
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="301269",
        stock_name="华大九天",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        max_cards_per_type=1,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert cards[0]["source_block_id"] == "future_strategy-0"
    assert {"PDK", "PPA", "版图验证"}.issubset(set(cards[0]["keywords"]))
    assert "半导体" not in cards[0]["keywords"]


def test_raw_text_glossary_terms_can_boost_evidence_pack_blocks():
    raw_text = (
        "第一节 释义\n"
        "释义项 指 释义内容\n"
        "PDK 指 Process Design Kit，即工艺设计套件。\n"
        "PPA 指 功耗、性能、面积，芯片设计中的核心评估指标。\n"
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": "行业竞争加剧，市场需求保持增长，公司关注政策变化并提升经营效率。",
            },
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来展望",
                "text": "公司围绕PDK和PPA能力完善产品矩阵，持续提升先进制程市场服务能力和客户支持能力。",
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="301269",
        stock_name="华大九天",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        raw_text=raw_text,
        max_cards_per_type=1,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert cards[0]["source_block_id"] == "future_strategy-0"
    assert {"PDK", "PPA"}.issubset(set(cards[0]["keywords"]))


def test_glossary_terms_filter_generic_noise_but_keep_product_terms():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "glossary-0",
                "usage": "glossary",
                "section": "第一节 释义",
                "title": "常用词语释义",
                "text": (
                    "公司、本公司 指 广东赛微微电子股份有限公司 "
                    "报告期 指 2025年1月1日至2025年12月31日 "
                    "元、万元 指 人民币元、万元 "
                    "芯片 指 集成电路的载体 "
                    "电池计量芯片 指 用于确定电池的电量状态和健康状态。 "
                    "FastCali 指 一种电池电量算法。"
                ),
            },
            {
                "id": "rd_table-0",
                "usage": "rd_table",
                "section": "第三节 管理层讨论与分析",
                "title": "研发项目",
                "text": "公司围绕FastCali算法研发新一代电池计量芯片，产品已完成验证并进入客户导入阶段。",
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688325",
        stock_name="赛微微电",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "rd_product_progress"]
    assert len(cards) == 1
    assert {"FastCali", "电池计量芯片"}.issubset(set(cards[0]["keywords"]))
    assert "公司" not in cards[0]["keywords"]
    assert "报告期" not in cards[0]["keywords"]
    assert "元、万元" not in cards[0]["keywords"]
    assert "芯片" not in cards[0]["keywords"]


def test_definition_like_body_terms_boost_optical_module_strategy_sentences():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业技术趋势",
                "text": (
                    "光电共封装技术（CPO）指的是交换ASIC芯片和硅光引擎在同一高速主板上协同封装。"
                    "线性驱动可插拔光模块（LPO）是指采用线性直驱技术、去除传统DSP/CDR芯片的光模块方案。"
                ),
            },
            {
                "id": "industry_outlook-1",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业情况",
                "text": "行业竞争加剧，市场需求保持增长，公司关注政策变化并提升经营效率。",
            },
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来展望",
                "text": "公司将加大CPO、LPO、硅光等核心产品或技术投入，积极推动下一代光互连技术发展。",
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        max_cards_per_type=1,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "management_market_view"]
    assert len(cards) == 1
    assert cards[0]["source_block_id"] == "future_strategy-0"
    assert {"CPO", "LPO"}.issubset(set(cards[0]["keywords"]))


def test_near_duplicate_business_model_cards_are_deduplicated_across_blocks():
    duplicated_text = (
        "公司客户主要为国内大型航空航天企业集团，客户明确且集中度高。"
        "公司采用直接销售方式，销售产品主要为高性能碳纤维及碳纤维织物，"
        "产品经客户定型认证通过后进入最终用户认定的合格供方目录。"
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "sales_certification_model-0",
                "usage": "sales_certification_model",
                "section": "第三节 管理层讨论与分析",
                "title": "销售模式",
                "text": duplicated_text,
            },
            {
                "id": "business_model-0",
                "usage": "business_model",
                "section": "第三节 管理层讨论与分析",
                "title": "经营模式",
                "text": "3、销售模式 " + duplicated_text,
            },
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    cards = [c for c in result["cards"] if c["card_type"] == "business_model"]
    assert len(cards) == 1


def test_risk_disclosure_blocks_do_not_generate_narrative_cards():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "risk_disclosure-0",
                "usage": "risk_disclosure",
                "section": "第三节 管理层讨论与分析",
                "title": "可能面对的风险",
                "text": (
                    "新产品研发风险 集成电路设计公司的营业收入及利润增长主要基于新产品的研发及销售，"
                    "如果公司未来不能紧跟市场需求，公司将面临产品竞争力下降的风险。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_goodwill_policy_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "goodwill_note-0",
                "usage": "goodwill_note",
                "section": "第十节 财务报告",
                "title": "商誉",
                "text": (
                    "商誉减值 本公司至少每年测试商誉是否发生减值。这要求对分配了商誉的资产组或者资产组组合"
                    "的未来现金流量的现值进行预计。预计未来现金流量现值时，管理层必须估计该项资产组"
                    "的预计未来现金流量，并选择恰当的折现率确定未来现金流量的现值。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_non_financial_risk_paragraphs_are_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "management_strategy-0",
                "usage": "management_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "核心竞争力",
                "text": (
                    "新产品研发风险 集成电路设计公司的营业收入及利润增长主要基于新产品的研发及销售，"
                    "如果公司未来不能紧跟市场需求，公司将面临产品竞争力下降的风险。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_hash_page_fragments_are_rejected():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "management_market_view-0",
                "usage": "management_market_view",
                "section": "第三节 管理层讨论与分析",
                "title": "风险",
                "text": (
                    "# 化的激励措施来稳定和扩大人才队伍，但由于市场竞争加剧，进入模拟集成 # "
                    "电路设计行业的门槛较高，加剧了对该行业的人才争夺，所以公司仍然存在 # 技术人员流失的风险。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_generic_inventory_policy_estimate_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货",
                "text": (
                    "存货跌价准备 本公司根据存货会计政策，按照成本与可变现净值孰低计量，对成本高于"
                    "可变现净值及过时和滞销的存货，计提存货跌价准备。鉴定存货减值要求管理层"
                    "在取得确凿证据，并且考虑持有存货的目的、资产负债表日后事项的影响等因素的基础上做出判断和估计。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_generic_fair_value_estimate_text():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "financial_assets_note-0",
                "usage": "financial_assets_note",
                "section": "第十节 财务报告",
                "title": "金融资产",
                "text": (
                    "非上市股权投资的公允价值 本公司根据对当前市场状况的判断，选择确定非上市公司股权投资公允价值"
                    "的估值方法，并作出相关假设和估计。如果任何估计和假设发生变化，可能会导致这些金融资产各自的公允价值发生重大变化。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_discount_rate_note_reference_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "goodwill_note-0",
                "usage": "goodwill_note",
                "section": "第十节 财务报告",
                "title": "商誉",
                "text": (
                    "对未来现金流量的现值进行预计时，本公司需要预计未来资产组或者资产组组合产生的现金流量，"
                    "同时选择恰当的折现 率确定未来现金流量的现值。详见附注七、22。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_key_audit_procedure_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "goodwill_note-0",
                "usage": "goodwill_note",
                "section": "第十节 财务报告",
                "title": "商誉减值",
                "text": (
                    "基于所实施的审计程序，我们发现管理层在商誉减值测试评估中采用的关键假设可以被我们获取的证据所支持。"
                    "我们了解、评估了与管理层计提商誉减值相关的内部控制，并测试了相关控制设计和执行的有效性。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_spaced_key_audit_procedure_boilerplate():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "goodwill_note-0",
                "usage": "goodwill_note",
                "section": "第十节 财务报告",
                "title": "商誉减值",
                "text": (
                    "基于所实施的审计 程序，我们发现管理层在商誉 减值测试评估中采用的关键假设可以被我们获取的证据所支持。"
                    "我们了解、评估了与管理层计提商誉减值相 关的 内部控制，并测试了相关控制设计和执行的有效 性。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_audit_response_procedure_bullets():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "goodwill_note-0",
                "usage": "goodwill_note",
                "section": "第十节 财务报告",
                "title": "商誉减值",
                "text": (
                    "我们获取了管理层聘请的外部评估师出具的商誉减值报告，并对外部评估师的胜任能力、专业素质和客观性进行了评价。"
                    "在内部估值专家协助下，我们通过比较行业或市场数据，评估了于商誉减值测试时所用的税前折现率的合理性。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_mixed_audit_procedure_with_specific_impairment_terms():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "ar_aging_note-0",
                "usage": "ar_aging_note",
                "section": "第十节 财务报告",
                "title": "商誉减值",
                "text": (
                    "管理层于每年年度终了对商誉进行减值测试。管理层将含有商誉的资产组的账面价值与其可收回金额进行比较，"
                    "以确定是否需要计提减值。可收回金额根据资产组的公允价值减去处置费用后的净额与预计未来现金流量的现值确定。"
                    "与评价商誉的潜在减值相关的审计程序中包括以下程序：了解并评价与商誉的潜在减值测试相关的关键财务报告内部控制的设计和运行有效性；"
                    "对管理层编制预计未来现金流量的现值时采用的关键假设进行敏感性分析。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="603986",
        stock_name="兆易创新",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_prior_year_assumption_comparison_audit_procedure():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货跌价",
                "text": (
                    "将管理层在上一年度计算预计未来现金流量的现值时使用的关键假设与本年度的实际结果进行比较，"
                    "以评价是否存在管理层偏向的迹象。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="603986",
        stock_name="兆易创新",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_audit_sensitivity_analysis_procedure():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "goodwill_note-0",
                "usage": "goodwill_note",
                "section": "第十节 财务报告",
                "title": "商誉减值",
                "text": (
                    "对减值评估中采用的预测期收入增长率、稳定期收入增长率、毛利率和税前折现率执行敏感性分析，"
                    "考虑这些关键假设在合理变动时对减值测试评估结果的潜在影响。"
                ),
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_income_statement_line_fragment():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "asset_impairment_note-0",
                "usage": "asset_impairment_note",
                "section": "第十节 财务报告",
                "title": "资产减值损失",
                "text": "资产减值损失（损失以 “-”号填列） -125,895,310.88 -78,580,366.45 资产处置收益（损失以 “-”号填列）",
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_income_statement_reason_line_fragment_with_checkbox_answer():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "asset_impairment_note-0",
                "usage": "asset_impairment_note",
                "section": "第三节 管理层讨论与分析",
                "title": "利润表项目",
                "text": "否 信用减值损失 -2,046,854.83 -0.37% 主要为 计提应收及其他应收款坏账准备。",
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_income_statement_reason_line_fragment_without_checkbox_answer():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "financial_assets_note-0",
                "usage": "financial_assets_note",
                "section": "第三节 管理层讨论与分析",
                "title": "利润表项目",
                "text": "公允价值变动损益 42,509,240.73 7.73% 主要为 交易性金融资产及其他非流动金融资产公允价值变动。",
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300661",
        stock_name="圣邦股份",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_financial_note_rejects_orphaned_note_heading_with_bullet():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "inventory_note-0",
                "usage": "inventory_note",
                "section": "第十节 财务报告",
                "title": "存货跌价准备",
                "text": "存货跌价准备的评估 中际旭创股份有限公司 2025 年年度报告全文 > -87 - > ",
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"] == []


def test_long_excerpt_truncates_at_sentence_boundary():
    sentence = "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务，客户覆盖航空航天主机厂。"
    long_text = sentence + (
        "公司采用直接销售模式，产品经客户定型认证通过后进入最终用户认定的合格供方目录。"
        * 20
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "主营业务",
                "text": long_text,
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"]
    excerpt = result["cards"][0]["source_excerpt"]
    assert len(excerpt) <= 500
    assert excerpt.endswith("。")


def test_long_excerpt_prefers_shorter_complete_sentence_over_mid_sentence_cut():
    complete_sentence = (
        "公司将持续专注于 AI 数据中心等核心市场，进一步加大 1.6T、3.2T 及以上高速率光模块、"
        "硅光、相干等核心产品或技术的投入与研究，积极推动下一代光互连技术的发展。"
    )
    unfinished_tail = (
        "同时，公司还将抓住有利经营环境持续拓展客户，围绕高速互联、云计算数据中心、"
        "下一代网络架构和产品平台持续投入，提升规模化交付能力和全球化客户服务能力"
        * 8
    )
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "future_strategy-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "未来发展战略",
                "text": complete_sentence + unfinished_tail,
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300308",
        stock_name="中际旭创",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"]
    excerpt = result["cards"][0]["source_excerpt"]
    assert excerpt == complete_sentence
    assert not excerpt.endswith("…")


def test_long_excerpt_may_extend_slightly_to_reach_nearby_sentence_boundary():
    prefix = (
        "公司将围绕高端封装材料持续推进客户导入、批量供货、国产化验证和核心产品平台建设，"
        "提升先进封装材料在头部客户中的覆盖能力，"
    )
    filler = "并持续加强研发协同、供应链韧性、质量管控、交付体系和海外客户服务能力，" * 12
    sentence = prefix + filler + "推动公司在先进封装材料领域的竞争力稳步提升。"
    assert len(sentence) > 500
    assert sentence.index("。") <= 620
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "competitive_position-0",
                "usage": "future_strategy",
                "section": "第三节 管理层讨论与分析",
                "title": "竞争力",
                "text": sentence + "后续第二句不应进入摘录。",
            }
        ],
    }

    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688035",
        stock_name="德邦科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )

    assert result["cards"]
    excerpt = result["cards"][0]["source_excerpt"]
    assert excerpt.endswith("。")
    assert not excerpt.endswith("…")
    assert "后续第二句" not in excerpt


def test_stable_id_and_order_across_repeated_calls():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "报告期内公司从事的主要业务",
                "text": (
                    "公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。"
                    "产品主要应用于航空航天、轨道交通、新能源等领域。"
                ),
            }
        ],
    }
    result1 = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    result2 = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
    )
    assert result1["cards"] == result2["cards"]
    assert [c["card_id"] for c in result1["cards"]] == [
        c["card_id"] for c in result2["cards"]
    ]


def test_max_cards_per_type_and_max_total_cards_truncation_is_deterministic():
    # Build a pack where each card type could produce at least two snippets.
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "business_overview-0",
                "usage": "business_overview",
                "section": "第三节 管理层讨论与分析",
                "title": "业务",
                "text": (
                    "公司主要从事高性能碳纤维及相关产品的研发、生产和销售业务。"
                    "产品广泛应用于航空航天、轨道交通、新能源等领域，客户覆盖国内主要主机厂。"
                ),
            },
            {
                "id": "industry_outlook-0",
                "usage": "industry_outlook",
                "section": "第三节 管理层讨论与分析",
                "title": "行业",
                "text": (
                    "碳纤维行业正由规模竞争逐步转向价值竞争，高端航空航天用碳纤维需求保持稳健增长。"
                    "低端通用级碳纤维市场产能过剩，价格承压明显。"
                ),
            },
            {
                "id": "rd_table-0",
                "usage": "rd_table",
                "section": "第三节 管理层讨论与分析",
                "title": "研发",
                "text": (
                    "公司ZT7H系列碳纤维产品已完成量产验证并批量供货，应用范围持续拓展。"
                    "ZT9H系列产品已通过主机厂认证，进入小批量供货阶段，产业化进度符合预期。"
                ),
            },
            {
                "id": "asset_impairment_note-0",
                "usage": "asset_impairment_note",
                "section": "第十节 财务报告",
                "title": "减值",
                "text": (
                    "受下游需求放缓影响，部分存货可变现净值低于账面成本，公司基于谨慎性原则计提存货跌价准备。"
                    "同时公司对应收账款坏账准备进行了复核，未发现需要单项计提的重大风险。"
                ),
            },
        ],
    }
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="300777",
        stock_name="中简科技",
        report_year=2025,
        report_type="annual",
        evidence_pack=evidence_pack,
        max_cards_per_type=2,
        max_total_cards=5,
    )
    cards = result["cards"]
    # Per-type cap: at most 2 of each type.
    assert sum(1 for c in cards if c["card_type"] == "business_model") <= 2
    assert sum(1 for c in cards if c["card_type"] == "management_market_view") <= 2
    assert sum(1 for c in cards if c["card_type"] == "rd_product_progress") <= 2
    assert sum(1 for c in cards if c["card_type"] == "financial_note") <= 2
    # Global cap.
    assert len(cards) <= 5
    # Fixed order follows the card type priority.
    expected_order = ["business_model", "management_market_view", "market_outlook", "rd_product_progress", "financial_note"]
    observed_types = [c["card_type"] for c in cards]
    for i, expected in enumerate(expected_order):
        if i < len(observed_types):
            assert observed_types[i] == expected
