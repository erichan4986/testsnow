from __future__ import annotations

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
# Layout-aware PDF extraction tests (use real PDFs from smoke cache)
# ---------------------------------------------------------------------------

import pytest

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
