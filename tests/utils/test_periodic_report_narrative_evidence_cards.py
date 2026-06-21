"""Tests for periodic_report_narrative_evidence_cards helper."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_narrative_evidence_cards import (
    build_periodic_report_narrative_evidence_cards,
)


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
    # Fixed order: business_model, operation_update, management_market_view, ...
    expected_order = ["business_model", "management_market_view", "rd_product_progress", "financial_note"]
    observed_types = [c["card_type"] for c in cards]
    for i, expected in enumerate(expected_order):
        if i < len(observed_types):
            assert observed_types[i] == expected
