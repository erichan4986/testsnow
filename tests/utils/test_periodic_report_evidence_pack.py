"""Tests for periodic_report_evidence_pack builder."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_evidence_pack import (
    USAGE_PRIORITY,
    build_periodic_report_evidence_pack,
)


SAMPLE_REPORT = """
第一节 重要提示、目录和释义
本公司及董事会全体成员保证年度报告内容的真实、准确、完整。

第二节 公司简介和主要财务指标
公司名称：中简科技股份有限公司
证券代码：300777
报告期内，公司实现营业收入 1,234,567,890.12 元，归属于上市公司股东的净利润 123,456,789.01 元。

第三节 管理层讨论与分析
一、报告期内公司从事的主要业务
公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。产品主要应用于航空航天、轨道交通、新能源等领域。
报告期内，公司持续推进高强型、高模型碳纤维系列产品的研发与产业化，形成了系列化产品格局。

二、行业情况
碳纤维行业由规模竞争逐步转向价值竞争。高端航空航天用碳纤维需求保持增长，低端通用级碳纤维产能过剩，价格承压。

三、经营模式
公司主要采用以销定产、自主研发的经营模式。采购环节实行合格供应商制度，生产环节按订单组织排产，销售环节以直销为主。

四、核心竞争力分析
公司核心竞争优势体现在自主知识产权、稳定客户结构和持续研发投入。

五、主营业务分析
1、营业收入构成
分产品            营业收入（元）  营业成本（元）  毛利率  营业收入同比增减  毛利率同比增减
碳纤维            500,000,000.00  350,000,000.00  30.00%      -10.00%          -2.00%
碳纤维织物        600,000,000.00  360,000,000.00  40.00%       15.00%           3.00%
其他              134,567,890.12   80,000,000.00  40.50%        5.00%           1.00%
合计            1,234,567,890.12  790,000,000.00  36.00%

4、研发投入
项目        本期金额（元）  上期金额（元）  同比增减
研发费用    80,000,000.00   70,000,000.00       14.29%
资本化研发投入 0.00         0.00                0.00%

2、分地区
地区              营业收入（元）  营业收入占比  营业收入同比增减
国内            1,100,000,000.00       89.10%          2.00%
国外              134,567,890.12       10.90%         -8.00%

3、前五名客户合计销售
客户名称      销售额（元）    占年度销售总额比例
客户 A        600,000,000.00          48.60%
客户 B        200,000,000.00          16.20%
客户 C        150,000,000.00          12.15%
客户 D         80,000,000.00           6.48%
客户 E         50,000,000.00           4.05%
合计        1,080,000,000.00          87.48%

四、可能面对的风险
公司面临客户集中、产品价格下降、技术迭代及供应链波动风险。

第四节 公司治理
一、股东情况
普通股股东总数 12,345 人。

第五节 环境和社会责任
不适用。

第六节 重要事项
一、承诺事项履行情况
公司实际控制人、控股股东承诺在限售期内不转让首发前股份。

二、对外担保
报告期内无重大对外担保。

第七节 股份变动及股东情况
一、股份变动情况
报告期内，公司控股股东未发生变更，实际控制人未发生变更。

二、股东股份质押情况
截至报告期末，控股股东质押股份 0 股。

第八节 优先股相关情况
不适用。

第九节 债券相关情况
不适用。

第十节 财务报告
一、审计报告
审计意见类型：标准无保留意见。

二、财务报表
（一）合并资产负债表
应收账款 123,456,789.01 元，存货 234,567,890.12 元，在建工程 345,678,901.23 元。

（二）合并利润表
营业收入 1,234,567,890.12 元，营业成本 790,000,000.00 元。

（三）合并现金流量表
经营活动产生的现金流量净额 98,765,432.10 元。

三、财务报表附注
（一）应收账款
1 年以内应收账款占比 85.00%，1-2 年应收账款占比 12.00%，2 年以上占比 3.00%。

（二）存货
原材料 80,000,000.00 元，在产品 90,000,000.00 元，库存商品 64,567,890.12 元。

（三）在建工程
四期项目投入 345,678,901.23 元，工程进度 78.00%。

（四）政府补助
计入当期损益的政府补助 12,345,678.90 元。

（五）受限资产
所有权或使用权受到限制的资产合计 5,000,000.00 元，主要为银行承兑汇票保证金。

（六）关联方及关联交易
报告期内，公司向关联方采购商品 1,000,000.00 元，向关联方销售商品 2,000,000.00 元。

（七）或有事项
截至报告期末，公司无重大诉讼、仲裁事项。

（八）资产负债表日后事项
2025 年 4 月，公司召开董事会审议利润分配方案。
"""


def _texts_for_usage(pack: dict, usage: str) -> str:
    return "\n".join(block["text"] for block in pack["blocks"] if block["usage"] == usage)


def test_locates_management_discussion_without_company_specific_terms():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "business_overview" in usages
    assert "industry_outlook" in usages
    assert "business_model" in usages
    assert "management_strategy" in usages
    # No carbon-fiber-specific usage.
    assert "碳纤维" not in [b["title"] for b in pack["blocks"]]


def test_extracts_segment_margin_table_block():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    # The revenue/cost/margin table is classified as the richer segment_margin_table
    # rather than a plain segment_table.
    assert "segment_margin_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "segment_margin_table")
    assert "碳纤维" in block["text"]
    assert "毛利率" in block["text"]


def test_extracts_region_table_block():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "region_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "region_table")
    assert "国内" in block["text"]


def test_extracts_customer_supplier_block():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "customer_supplier_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "customer_supplier_table")
    assert "客户 A" in block["text"]
    assert "前五名" in block["text"]


def test_extracts_rd_table_block():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    # A spending/personnel/capitalization table is classified separately from
    # project-progress R&D tables.
    assert "rd_investment_table" in usages


def test_extracts_risk_disclosure_block():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "risk_disclosure" in usages


def test_extracts_ar_aging_inventory_cip_grant_restricted_blocks():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "ar_aging_note" in usages
    assert "inventory_note" in usages
    assert "capex_cip_note" in usages
    assert "government_grant_note" in usages
    assert "restricted_assets_note" in usages


def test_extracts_related_party_litigation_subsequent_shareholder_pledge_commitments():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "related_party_transactions" in usages
    assert "contingencies_litigation" in usages
    assert "subsequent_events" in usages
    assert "shareholder_structure" in usages
    assert "pledge" in usages
    assert "commitments" in usages


def test_caps_block_length_and_count():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    assert len(pack["blocks"]) <= 48
    for block in pack["blocks"]:
        assert len(block["text"]) <= 2000


def test_stable_ids_for_same_input():
    pack1 = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    pack2 = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    ids1 = [b["id"] for b in pack1["blocks"]]
    ids2 = [b["id"] for b in pack2["blocks"]]
    assert ids1 == ids2


def test_document_style_is_envelope_only_and_conservative():
    assert build_periodic_report_evidence_pack(
        "管理层讨论与分析\n公司主营业务为测试产品。", report_type="annual"
    )["document_style"] == "a_share_annual"
    assert build_periodic_report_evidence_pack(
        "管理層討論及分析\n本集團業務回顧。", report_type="annual"
    )["document_style"] == "hkex_annual"
    assert build_periodic_report_evidence_pack(
        "季度经营摘要。", report_type="quarterly"
    )["document_style"] == "unknown"


def test_family_reserve_keeps_low_priority_business_narrative():
    from periodic_report_evidence_pack import _select_bounded_blocks

    blocks = [
        {"id": f"financial_summary_table-{i}", "usage": "financial_summary_table",
         "section": "财务", "title": "财务",
         "text": "营业收入 100 亿元，净利润 10 亿元。",
         "source_span": {"start": i, "end": i + 1}}
        for i in range(48)
    ] + [{
        "id": "business_overview-0", "usage": "business_overview",
        "section": "主营业务", "title": "主营业务",
        "text": "公司主要从事高端光通信收发模块的研发、生产及销售。",
        "source_span": {"start": 99, "end": 100},
    }]
    selected = _select_bounded_blocks(blocks)
    assert len(selected) == 48
    assert any(block["id"] == "business_overview-0" for block in selected)
    assert any(block["usage"] == "financial_summary_table" for block in selected)


def test_structural_usage_cannot_consume_a_family_reserve_slot():
    from periodic_report_evidence_pack import _reserved_narrative_blocks

    blocks = [{"id": "segment_table-0", "usage": "segment_table",
               "section": "表", "title": "表",
               "text": "分产品 营业收入 营业成本 毛利率。",
               "source_span": {"start": 0, "end": 1}}]
    assert _reserved_narrative_blocks(blocks) == []


def test_no_full_report_outside_bounded_blocks():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    full = " ".join(b["text"] for b in pack["blocks"])
    # The evidence pack is bounded and should not simply be a copy-paste of the
    # whole report text. For this short synthetic fixture, a large fraction is
    # intentionally extracted, but the concatenated text must still be bounded
    # by the per-block caps and not reproduce boilerplate verbatim.
    assert len(full) <= len(SAMPLE_REPORT) * 1.3


def test_report_type_and_audit_status_detected():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    assert pack["report_type"] == "annual_report"
    assert pack["audit_status"] == "audited"


def test_usage_priority_order():
    # Lower number = higher priority. Tables and notes should outrank narrative.
    assert USAGE_PRIORITY["segment_table"] < USAGE_PRIORITY["business_overview"]
    assert USAGE_PRIORITY["customer_supplier_table"] < USAGE_PRIORITY["management_strategy"]


def test_block_has_required_keys():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT)
    for block in pack["blocks"]:
        assert set(block.keys()) >= {"id", "usage", "section", "title", "text", "source_span"}
        assert isinstance(block["source_span"], dict)
        assert "start" in block["source_span"]
        assert "end" in block["source_span"]


HK_REPORT_WITH_CURRENT_STATEMENTS = """
黑芝麻智能股份有限公司
2025 年報

業務回顧
公司在智能汽車場景實現收入增長，其他收入不作為主營收入指標。

五年財務概要
截至十二月三十一日止年度
人民幣千元 人民幣千元 人民幣千元
收入 999,999 888,888 777,777
經營活動所用現金淨額 (123,456) (234,567) (345,678)

綜合損益表
截至 2025 年 12 月 31 日止年度
人民幣千元 人民幣千元
2025 年 2024 年
收入 822,328 535,539
銷售成本 (627,000) (500,000)
毛利 195,328 35,539
年內虧損 (1,200,000) (2,000,000)

綜合現金流量表
截至 2025 年 12 月 31 日止年度
人民幣千元 人民幣千元
2025 年 2024 年
經營活動所用現金淨額 (985,373) (1,300,000)
投資活動所用現金淨額 (10,000) (20,000)
"""


def test_extracts_hk_income_and_cash_flow_statement_blocks_without_five_year_summary():
    pack = build_periodic_report_evidence_pack(HK_REPORT_WITH_CURRENT_STATEMENTS)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert blocks["hk_income_statement_table"]["id"] == "hk_income_statement_table-0"
    assert "綜合損益表" in blocks["hk_income_statement_table"]["text"]
    assert "收入 822,328" in blocks["hk_income_statement_table"]["text"]
    assert "五年財務概要" not in blocks["hk_income_statement_table"]["text"]
    assert "999,999" not in blocks["hk_income_statement_table"]["text"]

    assert blocks["hk_cash_flow_table"]["id"] == "hk_cash_flow_table-0"
    assert "綜合現金流量表" in blocks["hk_cash_flow_table"]["text"]
    assert "經營活動所用現金淨額 (985,373)" in blocks["hk_cash_flow_table"]["text"]
    assert "五年財務概要" not in blocks["hk_cash_flow_table"]["text"]
    assert "123,456" not in blocks["hk_cash_flow_table"]["text"]


def test_hk_five_year_summary_only_does_not_emit_primary_statement_blocks():
    text = """
    五年財務概要
    截至十二月三十一日止年度
    人民幣千元 人民幣千元 人民幣千元
    收入 999,999 888,888 777,777
    經營活動所用現金淨額 (123,456) (234,567) (345,678)
    """
    pack = build_periodic_report_evidence_pack(text)
    usages = {block["usage"] for block in pack["blocks"]}

    assert "hk_income_statement_table" not in usages
    assert "hk_cash_flow_table" not in usages


def test_extracts_hk_management_discussion_financial_summary_tables():
    text = """
    管理層討論及分析
    下表載列截至 2025 年及 2024 年12 月31 日止年度的比較數字：
    截至 12 月31 日止年度
    2025 年 2024 年
    人民幣千元 人民幣千元 收入 822,328 474,252
    銷售成本 (485,239) (279,544)
    毛利 337,089 194,708
    研發開支 (1,417,423) (1,435,156)
    經營虧損 (1,448,320) (1,753,982)
    年內虧損 (1,424,700) 313,315

    流動資金及財務資源
    下表載列所示年度我們現金流量的概要：
    截至 12 月31 日止年度
    2025 年 2024 年
    （人民幣千元） （人民幣千元） 經營活動所用現金淨額 (985,373) (1,189,754)
    投資活動所用現金淨額 (179,605) (223,006)
    """

    pack = build_periodic_report_evidence_pack(text)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert "收入 822,328" in blocks["hk_income_statement_table"]["text"]
    assert "經營活動所用現金淨額 (985,373)" in blocks["hk_cash_flow_table"]["text"]


NARRATIVE_WINDOW_REPORT = """
第三节 管理层讨论与分析
一、行业情况
未来数通光模块市场需求有望由算力集群扩张、网络架构迭代、ASIC 芯片规模化部署等因素共同驱动。
AI 算力需求推动数据中心持续扩容，全球云服务厂商对 GPU 的需求量持续增长。
光模块是 AI 投资中网络端的重要环节，根据 LightCounting 预测，2026 年全球数通光模块市场规模有望达到 228 亿美元，
预计 2030 年整体市场规模将增长至 414 亿美元，对应 2025-2030 年复合增长率为 20%。
未来三年内 800G 和 1.6T 等高速光模块的需求将占据市场主导地位，3.2T 光模块有望从 2028 年起逐步起量。

二、行业竞争格局及公司竞争地位
光模块头部厂商凭借领先的研发实力及交付能力，竞争优势进一步强化，行业集中度有望持续提升。
公司凭借行业领先的技术研发能力、低成本产品制造能力和全面交付能力等优势，赢得海内外客户认可，并保持市场份额持续成长。

三、公司未来发展的展望
公司将持续专注于 AI 数据中心等核心市场，进一步加大 1.6T、3.2T 及以上高速率光模块、硅光、相干等核心产品或技术的投入与研究。
2026 年度工作计划包括继续提升 1.6T、800G 等高端产品交付能力和出货量，推进国际化战略并优化供应链稳定性。

四、经营情况讨论
报告期内，公司高端产品出货占比提升，规模效应逐步释放，毛利率较上年同期提升，盈利能力持续改善。
"""


def test_extracts_high_value_narrative_windows_for_market_competition_strategy_profitability():
    pack = build_periodic_report_evidence_pack(NARRATIVE_WINDOW_REPORT)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert "market_demand_outlook" in blocks
    assert "2030 年整体市场规模将增长至 414 亿美元" in blocks["market_demand_outlook"]["text"]
    assert "800G 和 1.6T" in blocks["market_demand_outlook"]["text"]

    assert "competitive_position" in blocks
    assert "市场份额持续成长" in blocks["competitive_position"]["text"]

    assert "future_strategy" in blocks
    assert "1.6T、3.2T" in blocks["future_strategy"]["text"]
    assert "国际化战略" in blocks["future_strategy"]["text"]

    assert "profitability_commentary" in blocks
    assert "毛利率较上年同期提升" in blocks["profitability_commentary"]["text"]


SAIWEI_LIKE_NARRATIVE_REPORT = """
第三节 管理层讨论与分析

一、 报告期内公司所从事的主要业务、经营模式、行业情况说明

(一) 主要业务、主要产品或服务情况

公司自成立以来始终致力于模拟芯片的研发与销售业务。公司以电池管理芯片为核心，辐射电源管理芯片领域。

(三) 所处行业情况

1、行业的发展阶段、基本特点、主要技术门槛

近年来全球集成电路行业整体发展愈发景气，在此背景下集成电路设计市场也呈增长趋势。
电池管理芯片在工业控制、消费电子、新能源汽车及储能等领域应用广泛，下游各应用领域具备较大的增长潜力。
根据 Mordor Intelligence 预测，全球电池管理 IC 市场规模在 2026 年达到 65.2 亿美元，
预计到 2031 年将增长到 113.4 亿美元，预测期内复合年增长率将达 11.71%，增长源于电动汽车、移动和可穿戴设备等应用领域。
目前全球电池管理芯片市场主要被 TI、ADI 等国际龙头企业占据，国内企业布局相对有限，国产替代前景十分广阔。

2、公司所处的行业地位分析及其变化情况

公司致力于模拟芯片的研发和销售，主要产品包括电池安全芯片、电池计量芯片和充电管理等其他芯片。
凭借公司持续的研发投入及优秀的研发团队，使得公司的产品在行业内处于先进水平，主要产品在市场中具有一定竞争力。
相比竞争对手，公司专注于电池管理芯片领域，能够更为灵活和敏锐地捕捉客户需求并快速作出响应。
目前，公司已成为电池管理芯片领域主要的国内供应商，产品均已应用于相关行业国内外知名客户的产品中，并获得广泛认可。

五、报告期内主要经营情况

报告期内，本期实现营业收入 48,865.97 万元，较上年同期增加 24.34%。
公司产品主要面向工业级和消费级终端应用市场，下游终端市场需求在本年度得到延续。
毛利率较上年同期增加 1.15%，本期价格策略没有显著变化，成本端因采购量上升进一步获得成本规模效应，毛利率整体保持稳中有升。

六、公司关于公司未来发展的讨论与分析

(二) 公司发展战略

公司始终坚持以技术创新为发展战略方向。未来，公司将继续以下游市场需求为导向，进行新产品的研发，
丰富现有产品服务体系，扩大下游市场覆盖面，推动公司产品的结构升级；同时，公司将加大技术研发投入，
加强对电池管理芯片基础核心技术与前沿技术的研究，提升公司的自主研发及创新能力。
"""


def test_extracts_saiwei_like_generic_market_competition_margin_strategy_sections():
    pack = build_periodic_report_evidence_pack(SAIWEI_LIKE_NARRATIVE_REPORT)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert "industry_outlook" in blocks
    assert "全球电池管理 IC 市场规模" in blocks["industry_outlook"]["text"]
    assert blocks["industry_outlook"]["text"] != "行业情况说明"

    assert "market_demand_outlook" in blocks
    assert "复合年增长率将达 11.71%" in blocks["market_demand_outlook"]["text"]
    assert "国产替代前景十分广阔" in blocks["market_demand_outlook"]["text"]

    assert "competitive_position" in blocks
    assert "电池管理芯片领域主要的国内供应商" in blocks["competitive_position"]["text"]

    assert "profitability_commentary" in blocks
    assert "毛利率较上年同期增加 1.15%" in blocks["profitability_commentary"]["text"]
    assert "成本规模效应" in blocks["profitability_commentary"]["text"]

    assert "future_strategy" in blocks
    assert "下游市场需求为导向" in blocks["future_strategy"]["text"]
    assert "产品的结构升级" in blocks["future_strategy"]["text"]


DEBANG_LIKE_ADVANCED_PACKAGING_REPORT = """
第三节 管理层讨论与分析
一、经营模式、行业情况说明
公司专注于高端电子封装材料的研发及产业化。

（一）行业情况说明
未来，先进封装占比将逐步超越传统封装，先进封装技术成为延续摩尔定律的重要方向；
Chiplet 异构集成、2.5D/3D 封装、HBM 存储器封装等技术路径成为主流，
带动 TSV 材料、ABF 载板、高导热界面材料需求快速提升。

2、报告期内的主要研发成果
报告期内，公司开发的 TIM1 热界面材料专为高功率芯片散热管理设计，
超薄型 TIM、液态金属复合导热膏、高可靠合金导热片、光模块导热材料等产品
已进入客户验证或小批量交付阶段。

主营业务分产品情况
（1）集成电路封装材料：受益于先进封装需求拉动，全年收入同比增长，
毛利率同比提升 2.98 个百分点；（2）智能终端封装材料：受产品结构影响，
毛利率同比小幅降低；（3）新能源应用材料：该板块全年营收同比增长 20.03%，毛利率基本持平。
"""


def test_extracts_debang_like_rd_progress_margin_and_advanced_packaging_outlook():
    pack = build_periodic_report_evidence_pack(DEBANG_LIKE_ADVANCED_PACKAGING_REPORT)
    blocks = {block["usage"]: block for block in pack["blocks"]}
    rd_text = _texts_for_usage(pack, "rd_product_progress")

    assert "rd_product_progress" in blocks
    assert "TIM1" in rd_text
    assert "小批量交付" in rd_text

    assert "profitability_commentary" in blocks
    assert "毛利率同比提升 2.98 个百分点" in blocks["profitability_commentary"]["text"]
    assert "毛利率基本持平" in blocks["profitability_commentary"]["text"]

    assert "market_demand_outlook" in blocks or "industry_outlook" in blocks
    outlook_text = blocks.get("market_demand_outlook", {}).get("text", "") + blocks.get("industry_outlook", {}).get("text", "")
    assert "Chiplet" in outlook_text
    assert "HBM" in outlook_text
    assert "ABF" in outlook_text


def test_profitability_commentary_window_keeps_later_margin_sentences():
    report = """
第三节 管理层讨论与分析
主营业务分产品情况
（1）集成电路封装材料：受益于先进封装需求拉动，全年收入同比增长，
毛利率同比提升 2.98 个百分点；
（2）智能终端封装材料：依托核心头部客户群优势，公司在巩固提升老产品市场份额的同时，
加大产品创新及市场开拓力度，在智能穿戴、新型显示等应用场景开辟了新的增长空间，
全年实现营收 38,325.99 万元，同比增长 48.16%。
受供应链价格波动等因素影响，毛利率同比小幅降低；
（3）新能源应用材料：在下游新能源装机出货量持续稳定增长的背景下，
该板块全年营收同比增长 20.03%，毛利率基本持平。
"""
    pack = build_periodic_report_evidence_pack(report)
    blocks = {block["usage"]: block for block in pack["blocks"]}
    profitability_text = _texts_for_usage(pack, "profitability_commentary")

    assert "profitability_commentary" in blocks
    assert "毛利率同比提升 2.98 个百分点" in profitability_text
    assert "毛利率同比小幅降低" in profitability_text
    assert "毛利率基本持平" in profitability_text


def test_profitability_commentary_window_keeps_preceding_subject_line():
    report = """
第三节 管理层讨论与分析
主营业务分产品情况
电池计量芯片收入较上年同比增加 36.01%，主要受益于新产品推出，带动了该产品
的出货量增加。毛利率较上年同期增加 1.15%，本期价格策略没有显著变化，成本端因采购量上
升进一步获得成本规模效应，毛利率整体保持稳中有升。
"""
    pack = build_periodic_report_evidence_pack(report)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert "profitability_commentary" in blocks
    text = blocks["profitability_commentary"]["text"]
    assert "电池计量芯片收入较上年同比增加 36.01%" in text
    assert not text.lstrip().startswith("的出货量增加")


def test_keeps_multiple_high_value_keyword_blocks_for_same_usage():
    report = """
第三节 管理层讨论与分析
主要产品
公司主营产品以电池管理芯片为核心，涵盖电池安全芯片、电池计量芯片和充电管理等其他芯片。
过渡说明 01
过渡说明 02
过渡说明 03
过渡说明 04
过渡说明 05
过渡说明 06
过渡说明 07
过渡说明 08
过渡说明 09
过渡说明 10
过渡说明 11
过渡说明 12
过渡说明 13
过渡说明 14
过渡说明 15
过渡说明 16
过渡说明 17
过渡说明 18
过渡说明 19
过渡说明 20
过渡说明 21
过渡说明 22
过渡说明 23
过渡说明 24
过渡说明 25
主要产品
依托于公司自主研发的 FastCali 电池电量算法，公司电池计量芯片可以快速计算电池状态，
精准提供电池生命周期内电池荷电状态，并将误差控制在 1-3%。
"""
    pack = build_periodic_report_evidence_pack(report)
    product_blocks = [block for block in pack["blocks"] if block["usage"] == "product_capacity_profile"]

    assert len(product_blocks) >= 2
    assert product_blocks[0]["id"] == "product_capacity_profile-0"
    assert product_blocks[1]["id"] == "product_capacity_profile-1"
    assert "FastCali" in product_blocks[1]["text"]


def test_keyword_extraction_skips_overlapping_same_usage_windows():
    report = """
第三节 管理层讨论与分析
主营业务分产品情况
电池计量芯片收入较上年同比增加 36.01%，主要受益于新产品推出，带动了该产品
的出货量增加。毛利率较上年同期增加 1.15%，成本端因采购量上升进一步获得成本规模效应，
毛利率整体保持稳中有升。
"""
    pack = build_periodic_report_evidence_pack(report)
    profitability_blocks = [block for block in pack["blocks"] if block["usage"] == "profitability_commentary"]

    assert len(profitability_blocks) == 1


def test_competitive_position_window_keeps_preceding_subject_line():
    report = """
第三节 管理层讨论与分析
公司专注于电池管理芯片领域，经过多年深耕，进行了集中的技术和资源投入，
凭借产品的供货能力和品牌认可度，取得良好的市场份额。目前，公司已成为电池管理芯片领域
主要的国内供应商，产品均已应用于相关行业国内外知名客户的产品中，并获得广泛认可。
"""
    pack = build_periodic_report_evidence_pack(report)
    competitive_text = _texts_for_usage(pack, "competitive_position")

    assert "凭借产品的供货能力和品牌认可度，取得良好的市场份额" in competitive_text
    assert not competitive_text.lstrip().startswith("主要的国内供应商")


def test_market_demand_window_keeps_wrapped_year_subject_line():
    report = """
第三节 管理层讨论与分析
世界半导体贸易统计预计 2025
年全球半导体营收有望同比增长 22.5%。根据 IBS 报告，预计到 2030 年中国半导体市场规模将达到 7,389 亿美元，
占全球市场的 54.69%，2020 年至 2030 年间中国半导体市场的年均复合增长率达 11.93%。
"""
    pack = build_periodic_report_evidence_pack(report)
    market_text = _texts_for_usage(pack, "market_demand_outlook")

    assert "世界半导体贸易统计预计 2025" in market_text
    assert not market_text.lstrip().startswith("年全球半导体营收")


def test_profitability_commentary_window_tolerates_jina_blank_lines():
    report = """
第三节 管理层讨论与分析
主营业务分产品情况
毛利率同比提升 2.98 个百分点；（ 2）智能终端封装材料：依托核心头部客户群优势，公司在巩

固提升老产品市场份额的同时，加大产品创新及市场开拓力度，在智能穿戴、新型显示等应用场

景开辟了新的增长空间，全年实现营收 38,325.99 万元，同比增长 48.16%。受供应链价格波动等

因素影响，毛利率同比小幅降低；（ 3）新能源应用材料：在下游新能源装机出货量持续稳定增

长的驱动下，公司新产线投产，产能释放，收入规模持续扩大，全年实现营收 80,884.65 万元，

同比增长 18.06%。随着产能爬坡和成本优化，毛利率基本持平。
"""
    pack = build_periodic_report_evidence_pack(report)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert "profitability_commentary" in blocks
    assert "毛利率同比小幅降低" in blocks["profitability_commentary"]["text"]
    assert "毛利率基本持平" in blocks["profitability_commentary"]["text"]


def test_keyword_window_extends_to_sentence_boundary_when_blank_lines_exhaust_line_budget():
    report = """
第三节 管理层讨论与分析

十一、公司未来发展的展望

（一）公司发展战略

公司将持续专注于 AI 数据中心等核心市场，进一步加大 1.6T、3.2T 及以上高速率光模块、硅光、

相干等核心产品或技术的投入与研究，积极推动下一代光互连技术的发展。同时，公司还将抓住有利经










营环境带来的战略机遇，在保持现有行业地位的同时，加快产业链纵向与横向的投资布局，致力于成为

具有国际影响力和领先水平的光互连综合解决方案提供商。

（二）2026 年度工作计划

继续加大 1.6T、800G 等高端产品的交付能力和出货量。
"""

    pack = build_periodic_report_evidence_pack(report)
    blocks = {block["usage"]: block for block in pack["blocks"]}

    assert "future_strategy" in blocks
    text = blocks["future_strategy"]["text"]
    assert "抓住有利经营环境" in re.sub(r"\s+", "", text)
    assert text.rstrip().endswith("。")
    assert not text.rstrip().endswith("有利经")


# ---------------------------------------------------------------------------
# Real-layout fixtures (mirroring 中简科技 2025 annual report)
# ---------------------------------------------------------------------------


ZHONGJIAN_LIKE_SEGMENT_MARGIN = """
（2） 占公司营业收入或营业利润 10% 以上的行业、产品、地区、销售模式的情况

单位：元

营业收入  营业成本  毛利率  营业收入比上年同期增减

营业成本比上年同期增减

毛利率比上年同期增减

分行业

新材料制造业  846,015,199.43  297,411,048.79  64.85%  4.20%  0.05%  1.46%

分产品

其中：碳纤维  443,494,353.42  198,630,573.93  55.21%  -19.59%  0.05%  -8.79%

碳纤维织物  402,520,846.01  98,780,474.86  75.46%  54.60%  0.04%  13.38%

分地区

其中：北京  806,513,711.29  278,131,342.44  65.51%  1.16%  -4.68%  2.11%
"""


ZHONGJIAN_LIKE_CUSTOMER_SUPPLIER = """
公司主要销售客户情况

前五名客户合计销售金额（元）  841,075,474.56

前五名客户合计销售金额占年度销售总额比例  99. 42%

前五名客户销售额中关联方销售额占年度销售总额比例  1. 54%

公司前  5 大客户资料

序号  客户名称  销售额（元）  占年度销售总额比例

1 客户  A 740,169,474.89  87.4 9%

2 客户  Q 66,344,237.31  7.84%

3 客户  V 16,377,309.27  1.94%

4 客户  ZE  13,033,745.13  1.54%

5 客户  K 5,150,707.96  0.61%

合计  -- 841,075,474.56  99.4 2%
"""


ZHONGJIAN_LIKE_RD = """
主要研发项目名称  项目目的  项目进展  拟达到的目标  预计对公司未来发展的影响

碳纤维预浸料制备技

术研制

研制高性能预浸

料

已完成多型产品的实验验

证及工艺验证，部分产品

达到供货条件

可批量供货  为民用航空及航天用户提供

具备竞争力的结构材料，开

拓新的应用领域

国产  T1100  级碳纤维

材料制备技术研发

研制湿纺制备

T1100  碳纤维

项目目标已达成，项目结

题

可批量供货  为新、老客户提供多样化产

品，提升竞争力

ZM40X  碳纤维百吨级

工程化制备技术研究

研发高强高模碳

纤维及其产业化

已完成部分生产线安装，

具备工程化制备能力

达到批产可批

量供货

为航空、航天用户提供自主

可控的高端产品，开拓新的

应用场景
"""


def test_extracts_zhongjian_like_segment_margin_table():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_SEGMENT_MARGIN)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "segment_margin_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "segment_margin_table")
    assert "443,494,353.42" in block["text"]
    assert "55.21%" in block["text"]
    assert "-19.59%" in block["text"]
    assert "碳纤维织物" in block["text"]
    assert "75.46%" in block["text"]


def test_extracts_zhongjian_like_customer_supplier_table():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_CUSTOMER_SUPPLIER)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "customer_supplier_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "customer_supplier_table")
    text = block["text"].replace(" ", "")
    assert "99.42%" in text
    assert "客户A" in text or "客户 A" in block["text"]


def test_extracts_zhongjian_like_rd_table():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_RD)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "rd_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "rd_table")
    assert "T1100" in block["text"]
    assert "ZM40X" in block["text"]
    assert "可批量供货" in block["text"]
    assert "项目目标已达成" in block["text"]


def test_extracts_long_multiline_rd_table_without_truncating_late_projects():
    filler_lines = "\n".join(f"研发项目延续说明 {idx}" for idx in range(80))
    text = f"""
主要研发项目名称  项目目的  项目进展  拟达到的目标  预计对公司未来发展的影响

国产  T1100  级碳纤维
材料制备技术研发
研制湿纺制备
T1100  碳纤维
项目目标已达成，项目结
题
可批量供货
{filler_lines}
ZM40X  碳纤维百吨级
工程化制备技术研究
研发高强高模碳
纤维及其产业化
已完成部分生产线安装，
具备工程化制备能力
达到批产可批
量供货
"""
    pack = build_periodic_report_evidence_pack(text)
    block = next(b for b in pack["blocks"] if b["usage"] == "rd_table")
    assert "T1100" in block["text"]
    assert "ZM40X" in block["text"]


def test_segment_table_not_squeezed_by_financial_notes():
    # A block of financial-note-like text should not be misclassified as a table
    # that pushes out the business segment table.
    text = ZHONGJIAN_LIKE_SEGMENT_MARGIN + "\n\n（一）应收账款\n1 年以内应收账款占比 85.00%。\n"
    pack = build_periodic_report_evidence_pack(text)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "segment_margin_table" in usages
    assert "ar_aging_note" in usages


ZHONGJIAN_LIKE_PROFILE_AND_MODEL = """
第三节 管理层讨论与分析
一、报告期内公司从事的主要业务
公司主要从事高性能碳纤维及相关产品的研发、生产、销售和技术服务。
公司主要产品为 PAN 基碳纤维，已建有百吨级、千吨级、1500 吨级、2000 吨级国产高性能碳纤维生产线，
可规模化生产 ZT7、ZT8、ZT9 系列以及 ZM40J、ZM40X 等高端碳/石墨纤维。
织物产品主要包括 ZT7、ZT8、ZT9 系列碳纤维对应的机织物，可按客户需求定制。

二、经营模式
公司客户主要为国内大型航空航天企业集团，采用直接销售模式。产品通常需通过客户定型认证并进入最终用户认可的合格供方目录后，
由客户按最终用户需求下单。
"""


ZHONGJIAN_LIKE_NUMBERED_PRODUCT_PROFILE = """
(二)主要产品及应用

1、高性能碳纤维（可定制）

聚丙烯腈（ PAN ）基碳纤维目前为碳纤维主流产品。公司自主设计，先后建有百吨级、千吨级、一千五百吨级、两千吨级国产高性能碳纤维生产线，
系柔性生产线，可在同一条生产线中生产不同规格和级别的 PAN 基碳纤维，目前可实现规模化生产高强型 ZT7 系列、ZT8 系列、ZT9 系列和高模型 ZM40J、ZM40X 石墨纤维。

2、碳纤维织物（可定制）

公司目前主要生产 ZT7、ZT8 及 ZT9 系列碳纤维对应的碳纤维织物。
"""


ZHONGJIAN_LIKE_PRODUCTION_SALES_INVENTORY = """
（3） 公司实物销售收入是否大于劳务收入

行业分类  项目  单位  2025 年  2024 年  同比增减

制造业  销售量  kg  315,326.80  301,909.94  4.44%

制造业  生产量  kg  388,277.44  306,159.21  26.82%

制造业  库存量  kg  94,938.11  37,830.55  150.95%

相关数据同比发生变动 30% 以上的原因说明：三期生产线正常投产，产量上升，但客户四季度需求阶段性放缓，导致年末库存增大。
"""


SHENGBANG_LIKE_PRODUCT_PROFILE = """
一、报告期内公司从事的主要业务
（一）公司的经营范围和主营业务
公司专注于高性能、高品质模拟集成电路研发和销售，拥有信号链、电源管理以及传感器三大产品方向。
公司坚持信号链和电源管理双支柱发展战略，截至报告期末可供销售产品超过 38 大类 6,800 余款。
信号链产品包括运算放大器、比较器、模数转换器、数模转换器、接口芯片等。
电源管理产品包括电源转换、驱动、保护和电池管理等多个系列。
"""


SHENGBANG_LIKE_INVENTORY_AUDIT_NOISE = """
关键审计事项
圣邦股份存货为原材料晶圆、产成品芯片以及生产线上的半成品。
我们关注存货跌价准备计提是否充分，相关会计估计是否合理。
"""


ZHONGJIAN_LIKE_RD_INVESTMENT = """
4、研发投入

项目  2025 年  2024 年  变动比例

研发人员数量（人）  75  45  66.67%

研发人员数量占比  13.51%  8.88%  4.63%

研发投入金额（元）  117,500,000.00  85,750,000.00  37.02%

研发投入占营业收入比例  13.89%  10.56%  3.33%

研发投入资本化的金额（元）  0.00  0.00  0.00%

资本化研发投入占研发投入的比例  0.00%  0.00%  0.00%
"""


ZHONGJIAN_LIKE_LONG_RD_INVESTMENT = """
研发人员数量（人）  75  45  66.67%
研发人员学历
本科  26  12  116.67%
硕士  10  4  150.00%
其他  39  29  34.48%
研发人员年龄构成
30 岁以下  23  4  475.00%
30~40 岁  33  27  22.22%
其他  19  14  35.71%

近三年公司研发投入金额及占营业收入的比例
2025 年 2024 年 2023 年
研发投入金额（元）  117,509,715.58  85,763,342.72  115,657,426.88
研发投入占营业收入比例  13.89%  10.56%  20.70%
研发支出资本化的金额（元）  0.00  0.00  0.00
资本化研发支出占研发投入的比例  0.00%  0.00%  0.00%
"""


ZHONGJIAN_LIKE_FINANCIAL_RISK_NOTES = """
第十节 财务报告
三、关键审计事项
收入确认和应收账款减值是关键审计事项。

（一）应收账款
截至 2025 年末，应收账款余额前五名客户占比 98.81%，对应收账款余额未持有担保物或其他信用增级。

（二）应收票据
商业承兑汇票期末余额 178,000,000.00 元。

（三）资产减值损失
本期资产减值损失 17,073,500.00 元，主要系在建工程设备计提减值。

（四）合并现金流量表
经营活动产生的现金流量净额 880,000,000.00 元，同比增长 342.37%。
购建固定资产、无形资产和其他长期资产支付的现金 585,000,000.00 元。
投资活动产生的现金流量净额 -512,000,000.00 元。

（五）交易性金融资产
交易性金融资产期末余额 1,082,000,000.00 元，主要为理财产品。

第四节 公司治理
董事温月芳对财务报告、内部控制、项目投资、关联方认定、资金往来等多个议案提出异议。
"""


SHENGBANG_LIKE_CASH_FLOW = """
5、现金流

单位：元

项目 2025 年 2024 年 同比增减

经营活动现金流入小计 4,307,895,738.98 3,741,231,434.31 15.15%

经营活动现金流出小计 3,841,575,792.78 3,191,893,839.42 20.35%

经营活动产生的现金流量净额 466,319,946.20 549,337,594.89 -15.11%

投资活动现金流入小计 5,374,908,604.80 2,581,785,772.04 108.19%

投资活动现金流出小计 5,839,558,594.94 3,845,292,059.29 51.86%

投资活动产生的现金流量净额 -464,649,990.14 -1,263,506,287.25 63.23%

现金及现金等价物净增加额 367,833,104.71 -489,812,857.10 175.10%
"""


SHENGBANG_LIKE_FINANCIAL_SUMMARY = """
# 五、主要会计数据和财务指标

公司是否需追溯调整或重述以前年度会计数据

□是 否

2025 年 2024 年 本年比上年增减 2023 年

营业收入（元） 3,898,054,583.68 3,346,983,120.66 16.46% 2,615,716,404.14

归属于上市公司股东的净利润（元） 547,059,403.97 500,247,943.10 9.36% 280,768,286.79

归属于上市公司股东的扣除非经常性

损益的净利润（元） 427,582,529.58 451,159,069.34 -5.23% 211,774,004.01

经营活动产生的现金流量净额（元） 466,319,946.20 549,337,594.89 -15.11% 170,670,822.08

基本每股收益（元 /股） 0.8861 0.8168 8.48% 0.4624

稀释每股收益（元 /股） 0.8780 0.8130 8.00% 0.4562

加权平均净资产收益率 11.24% 11.90% -0.66% 7.63%

2025 年末 2024 年末 本年末比上年末

增减 2023 年末

资产总额（元） 6,954,149,664.98 5,771,119,556.50 20.50% 4,706,853,231.69

归属于上市公司股东的净资产（元） 5,294,385,006.97 4,609,226,482.20 14.86% 3,850,547,539.29
"""


SHENGBANG_LIKE_SUPPLIER_TABLE = """
公司主要供应商情况

前五名供应商合计采购金额（元） 2,180,676,102.11

前五名供应商合计采购金额占年度采购总额比例 90.99%

前五名供应商采购额中关联方采购额占年度采购总额比例 0.00%

公司前 5 名供应商资料

序号 供应商名称 采购额（元） 占年度采购总额比例

1 第一名 949,187,469.36 39.61%

2 第二名 379,679,188.23 15.84%

合计 -- 2,180,676,102.11 90.99%
"""


SHENGBANG_LIKE_FINANCIAL_METRICS_WITH_OPERATING_CF = """
第二节 公司简介和主要财务指标
主要会计数据和财务指标
营业收入（元） 3,898,054,583.68 3,347,204,110.17 16.46%
归属于上市公司股东的净利润（元） 488,914,721.35 450,696,105.15 8.48%
经营活动产生的现金流量净额（元） 466,319,946.20 549,337,594.89 -15.11%
基本每股收益（元 /股） 0.8861 0.8168 8.48%
"""


def test_extracts_product_capacity_profile_and_sales_certification_model():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_PROFILE_AND_MODEL)
    by_usage = {b["usage"]: b for b in pack["blocks"]}
    product_text = _texts_for_usage(pack, "product_capacity_profile")
    assert "product_capacity_profile" in by_usage
    assert "sales_certification_model" in by_usage
    assert "ZT7" in product_text
    assert "ZM40X" in product_text
    assert "2000 吨级" in product_text
    assert "合格供方目录" in by_usage["sales_certification_model"]["text"]
    assert "定型认证" in by_usage["sales_certification_model"]["text"]


def test_extracts_numbered_product_profile_without_stopping_at_subheading():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_NUMBERED_PRODUCT_PROFILE)
    block = next(b for b in pack["blocks"] if b["usage"] == "product_capacity_profile")
    assert "百吨级" in block["text"]
    assert "两千吨级" in block["text"]
    assert "ZT7" in block["text"]
    assert "ZM40X" in block["text"]


def test_extracts_production_sales_inventory_table():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_PRODUCTION_SALES_INVENTORY)
    block = next(b for b in pack["blocks"] if b["usage"] == "production_sales_inventory_table")
    assert "315,326.80" in block["text"]
    assert "388,277.44" in block["text"]
    assert "94,938.11" in block["text"]
    assert "150.95%" in block["text"]


def test_extracts_chip_company_product_profile_from_business_overview():
    pack = build_periodic_report_evidence_pack(SHENGBANG_LIKE_PRODUCT_PROFILE)
    block = next(b for b in pack["blocks"] if b["usage"] == "product_capacity_profile")
    assert "信号链" in block["text"]
    assert "电源管理" in block["text"]
    assert "6,800" in block["text"]


def test_product_profile_ignores_inventory_audit_production_line_noise():
    pack = build_periodic_report_evidence_pack(SHENGBANG_LIKE_INVENTORY_AUDIT_NOISE)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "product_capacity_profile" not in usages


def test_extracts_rd_investment_table_separately_from_rd_project_table():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_RD_INVESTMENT + "\n" + ZHONGJIAN_LIKE_RD)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "rd_investment_table" in usages
    assert "rd_table" in usages
    block = next(b for b in pack["blocks"] if b["usage"] == "rd_investment_table")
    assert "研发人员数量" in block["text"]
    assert "75" in block["text"]
    assert "13.89%" in block["text"]
    assert "研发投入资本化的金额" in block["text"]
    assert "0.00" in block["text"]


def test_extracts_long_rd_investment_table_through_amount_and_capitalization_rows():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_LONG_RD_INVESTMENT)
    block = next(b for b in pack["blocks"] if b["usage"] == "rd_investment_table")
    assert "研发人员数量" in block["text"]
    assert "研发投入金额" in block["text"]
    assert "117,509,715.58" in block["text"]
    assert "13.89%" in block["text"]
    assert "研发支出资本化的金额" in block["text"]
    assert "0.00" in block["text"]


def test_extracts_financial_risk_notes_for_llm_pack():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_LIKE_FINANCIAL_RISK_NOTES)
    usages = {b["usage"]: b for b in pack["blocks"]}
    expected = {
        "audit_key_matters",
        "ar_customer_concentration_note",
        "bills_receivable_note",
        "asset_impairment_note",
        "cash_flow_capex_table",
        "financial_assets_note",
        "governance_dissent",
    }
    assert expected.issubset(usages)
    assert "98.81%" in usages["ar_customer_concentration_note"]["text"]
    assert "178,000,000.00" in usages["bills_receivable_note"]["text"]
    assert "17,073,500.00" in usages["asset_impairment_note"]["text"]
    assert "585,000,000.00" in usages["cash_flow_capex_table"]["text"]
    assert "1,082,000,000.00" in usages["financial_assets_note"]["text"]
    assert "温月芳" in usages["governance_dissent"]["text"]


def test_cash_flow_table_starts_from_operating_cash_flow_rows():
    pack = build_periodic_report_evidence_pack(SHENGBANG_LIKE_CASH_FLOW)
    block = next(b for b in pack["blocks"] if b["usage"] == "cash_flow_capex_table")
    assert "经营活动产生的现金流量净额" in block["text"]
    assert "466,319,946.20" in block["text"]
    assert "投资活动产生的现金流量净额" in block["text"]
    assert "-464,649,990.14" in block["text"]
    assert "现金及现金等价物净增加额" in block["text"]


def test_financial_metrics_operating_cash_flow_does_not_masquerade_as_cash_flow_table():
    pack = build_periodic_report_evidence_pack(SHENGBANG_LIKE_FINANCIAL_METRICS_WITH_OPERATING_CF)
    usages = [b["usage"] for b in pack["blocks"]]
    assert "cash_flow_capex_table" not in usages


def test_extracts_financial_summary_table_for_snapshot_card():
    pack = build_periodic_report_evidence_pack(SHENGBANG_LIKE_FINANCIAL_SUMMARY)
    block = next(b for b in pack["blocks"] if b["usage"] == "financial_summary_table")
    assert "3,898,054,583.68" in block["text"]
    assert "547,059,403.97" in block["text"]
    assert "427,582,529.58" in block["text"]
    assert "466,319,946.20" in block["text"]
    assert "6,954,149,664.98" in block["text"]
    assert "5,294,385,006.97" in block["text"]


def test_extracts_supplier_concentration_table_separately_from_customer_table():
    pack = build_periodic_report_evidence_pack(SHENGBANG_LIKE_SUPPLIER_TABLE)
    block = next(b for b in pack["blocks"] if b["usage"] == "supplier_concentration_table")
    assert "2,180,676,102.11" in block["text"]
    assert "90.99%" in block["text"]
    assert "949,187,469.36" in block["text"]
    assert "39.61%" in block["text"]


# ---------------------------------------------------------------------------
# HK narrative block extraction (Traditional/Simplified)
# ---------------------------------------------------------------------------

HK_NARRATIVE_REPORT = """
黑芝麻智能國際控股有限公司
2025 年年度報告

管理層討論及分析

業務回顧
2025 年，本公司在智能汽車計算芯片領域持續鞏固領先地位，全年營收人民幣 8.22 億元，同比增長 73.4%。

華山 A1000 系列芯片已成功搭載於吉利、東風、比亞迪、一汽等多款車型，成為 2025 年本公司芯片銷量的主力貢獻。武當 C1200 系列芯片 2025 年實現從定點到量產的推進，在頭部車企的新車型上已經進入量產階段。華山 A2000 系列芯片作為全球首款全景通識高算力芯片，基於 7nm 先進工藝打造，目前正與元戎啟行、Nullmax 等核心算法廠商進行端到端算法的深度適配與驗證。 8黑芝麻智能國際控股有限公司  2025 年年度報告 管理層討論及分析 （續）

報告期內，本公司先後與雲深處、傅利葉智能、聯想、智平方等頭部機器人產業鏈企業合作夥伴，共同推動具身智能的商業化落地。目前已在四足機器人、航運智能巡檢等場景規模化交付，與智能駕駛形成生態協同的雙主業增長格局。

業務展望
2026 年本公司將以華山 A2000 芯片為核心，助力合作夥伴實現 L3 級高級輔助駕駛規模化落地，同步佈局 L4 級 Robotaxi 等場景，推動年內與蘿蔔快跑合作量產。依託 A2000 通過美國相關審查的全球市場准入優勢，加速海外整車項目量產應用，把握泛端側 AI 市場機遇。

毛利及毛利率
我們的整體毛利由截至 2024 年的人民幣 194.7 百萬元增加 73.1% 至截至 2025 年的人民幣 337.1 百萬元，整體毛利率保持相對穩定。我們輔助駕駛產品及解決方案的毛利率截至 2025 年為 37.4%，新業務具身智能解決方案的毛利率截至 2025 年為 48.7%，本公司產品在市場中保持有利競爭力。
"""

HK_AI_SOFTWARE_NARRATIVE_REPORT = """
MINIMAX GROUP INC. 2025年度報告

業務回顧及展望
業務回顧
2025年，我們構建了全模態的研發能力，語言、視頻、語音、音樂等各主要模態均擁有了具備全球競爭力的模型。同時，不斷通過技術創新給全球用戶帶來更好的體驗，升級我們的AI原生產品，包括面向企業客戶的開放平台，和面向消費者的MiniMax Agent、海螺AI、Talkie╱星野等。全球化佈局也走得更深更實。

2025年全年MiniMax總收入同比增長158.9%達到7,900萬美元，其中超過70%的收入來自國際市場。截至2025年12月31日，MiniMax累計服務超過200個國家及地區的逾2.36億名用戶，以及來自超過100個國家及地區的21.4萬企業客戶以及開發者。

在語言模型方面，2025年第四季度我們更新了M2、M2.1、M2-her三款模型。M2重新定義了效果、價格和速度上的平衡，具備編程、工具調用和深度搜索三項關鍵能力，發佈後迅速獲得全球開發者社區認可，成為OpenRouter上首個日Token消耗量超過500億的中國模型，並登頂HuggingFace全球熱榜第一。

在多模態方面，我們已具備視頻、語音、音樂三大模型能力。2025年10月，我們發佈了視頻模型Hailuo 2.3，在人物動作、畫面質量和風格化方面實現顯著提升，同時推出更快速的Fast模型，批量創作成本最高可降低50%。我們還在海螺AI產品中升級了Media Agent，支持全模態全能創作。

業務展望
展望未來，在公司戰略層面，我們會從基礎模型公司向AI時代的平台型公司邁進。模型能力的突破、智能體應用的部署以及變現模式的成熟，都在不斷擴展產業上限。我們將持續定義和推動新的智能範式，不斷提升技術和產品的創新能力，以及可擴展的基建和Token吞吐能力，同時深化商業化佈局並深耕全球市場機會。
"""


def _hk_usages(text):
    pack = build_periodic_report_evidence_pack(text, report_type="annual")
    return {block["usage"]: block for block in pack["blocks"]}


def test_extracts_hk_product_progress_narrative_block():
    blocks = _hk_usages(HK_NARRATIVE_REPORT)
    assert "hk_product_progress" in blocks
    text = blocks["hk_product_progress"]["text"]
    assert "A2000" in text
    assert "華山" in text or "武當" in text


def test_extracts_hk_customer_ecosystem_narrative_block():
    blocks = _hk_usages(HK_NARRATIVE_REPORT)
    assert "hk_customer_ecosystem" in blocks
    text = blocks["hk_customer_ecosystem"]["text"]
    assert "合作夥伴" in text or "傅利葉" in text or "生態" in text


def test_extracts_hk_market_outlook_narrative_block():
    blocks = _hk_usages(HK_NARRATIVE_REPORT)
    assert "hk_market_outlook" in blocks
    text = blocks["hk_market_outlook"]["text"]
    assert "Robotaxi" in text or "L4" in text


def test_extracts_hk_financial_commentary_narrative_block():
    blocks = _hk_usages(HK_NARRATIVE_REPORT)
    assert "hk_financial_commentary" in blocks
    assert "毛利率" in blocks["hk_financial_commentary"]["text"]


def test_hk_narrative_blocks_strip_embedded_page_markers():
    blocks = _hk_usages(HK_NARRATIVE_REPORT)
    for usage, block in blocks.items():
        if usage.startswith("hk_"):
            assert "（續）" not in block["text"]
            assert "年年度報告 管理層討論及分析" not in block["text"]


def test_hk_narrative_extraction_does_not_fire_on_ashare_report():
    pack = build_periodic_report_evidence_pack(SAMPLE_REPORT, report_type="annual")
    usages = {block["usage"] for block in pack["blocks"]}
    assert not any(usage.startswith("hk_") for usage in usages)


def test_hk_narrative_usages_have_priority():
    for usage in (
        "hk_business_overview",
        "hk_product_progress",
        "hk_market_outlook",
        "hk_customer_ecosystem",
        "hk_financial_commentary",
    ):
        assert usage in USAGE_PRIORITY


def test_extracts_hk_ai_software_business_overview_from_minimax_style_report():
    blocks = _hk_usages(HK_AI_SOFTWARE_NARRATIVE_REPORT)
    assert "hk_business_overview" in blocks
    text = blocks["hk_business_overview"]["text"]
    assert "AI原生產品" in text
    assert "開放平台" in text


def test_extracts_hk_ai_software_product_progress_from_model_release_paragraphs():
    blocks = _hk_usages(HK_AI_SOFTWARE_NARRATIVE_REPORT)
    assert "hk_product_progress" in blocks
    text = blocks["hk_product_progress"]["text"]
    assert "M2" in text or "Hailuo" in text
    assert "模型" in text


def test_extracts_hk_ai_software_customer_ecosystem_from_user_and_developer_scale():
    blocks = _hk_usages(HK_AI_SOFTWARE_NARRATIVE_REPORT)
    assert "hk_customer_ecosystem" in blocks
    text = blocks["hk_customer_ecosystem"]["text"]
    assert "企業客戶" in text
    assert "開發者" in text


def test_extracts_hk_ai_software_market_outlook_from_platform_strategy():
    blocks = _hk_usages(HK_AI_SOFTWARE_NARRATIVE_REPORT)
    assert "hk_market_outlook" in blocks
    text = blocks["hk_market_outlook"]["text"]
    assert "平台型公司" in text
    assert "Token吞吐能力" in text


def test_hk_narrative_rejects_sustainability_privacy_boilerplate():
    report = """
MINIMAX GROUP INC. 2025年度報告
管理層討論及分析
可持續性報告
1.5 信息安全與隱私保護
MiniMax深刻認識到，在人工智能技術快速演進的背景下，保障數據安全與客戶隱私，不僅是對客戶與合作夥伴的莊嚴承諾，也是履行企業社會責任、遵守全球合規要求的必然選擇。我們將信息安全內嵌於產品研發、運營管理與公司治理的全過程，通過體系化的風險防控、持續的技術投入與全員的安全意識培育，構建可信賴的技術生態。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert not [block for block in blocks if str(block.get("usage", "")).startswith("hk_")]


def test_hk_narrative_rejects_financial_summary_table_as_commentary():
    report = """
MINIMAX GROUP INC. 2025年度報告
管理層討論及分析
財務摘要
本集團過去四個財政年度的已公佈業績以及資產及負債摘要載列如下：業績截至12月31日止年度2025年 2024年 2023年 2022年千美元 千美元 千美元 千美元收入 79,038 30,523 3,460 –毛利 20,079 3,738 (854) –稅前虧損 (1,871,617) (465,238) (269,246) (73,728)年內虧損 (1,871,617) (465,238) (269,246) (73,728)經調整淨虧損（非《國際財務報告準則》計量指標）附註。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_financial_commentary" not in {block["usage"] for block in blocks}


def test_hk_narrative_rejects_forward_looking_statement_disclaimer():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
前瞻性陳述的風險聲明
本報告可能載有（除歷史數據外）前瞻性陳述。該等前瞻性陳述乃根據中芯國際對未來事件或績效的現行假設、期望、信念、計劃、目標及預測而作出。中芯國際使用包括（但不限於）「相信」、「預期」、「打算」、「估計」、「預計」、「預測」、「指標」、「展望」、「繼續」、「應該」、「或許」、「尋求」、「應當」、「計劃」、「可能」、「願景」、「目標」、「旨在」、「渴望」、「目的」、「預定」、「前景」和其他類似的表述，以識別前瞻性陳述。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_market_outlook" not in {block["usage"] for block in blocks}


def test_hk_narrative_rejects_smic_five_year_summary_and_income_statement_tables():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
五年業績概要
損益數據 千美元 截至12月31日止年度 2025年 2024年 2023年 2022年 2021年 收入 9,326,799 8,029,921 6,321,560 7,273,284 5,443,112 銷售成本 (7,370,200) (6,581,953) 毛利 1,956,599 1,447,968 研究及開發開支 (773,634) (765,279) 經營利潤 1,109,937 473,900。
合併損益及其他綜合收益表
截至2025年12月31日止年度（以千美元計值，每股數據除外）附註 2025年 2024年 收入 9,326,799 8,029,921 銷售成本 (7,370,200) (6,581,953) 毛利 1,956,599 1,447,968 研究及開發開支 (773,634) (765,279) 銷售及市場推廣開支 (42,963) (39,847) 一般及行政開支 (526,237) (580,041) 年內利潤 988,944 729,993。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_financial_commentary" not in {block["usage"] for block in blocks}


def test_hk_narrative_keeps_smic_operating_margin_commentary():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
財務回顧
這一年，我們持續聚焦主業發展，順利推進項目進展，經營業績再上新台階。面對外部複雜多變的環境，公司保持深耕晶圓製造長期戰略不動搖，穩步實施產能擴建，折合8吋標準邏輯的月產能規模超過了100萬片；全年實現銷售收入93.27億美元，同比增長16.2%，繼續鞏固全球純晶圓代工企業第二位置；產能利用率增至93.5%，同比增長8個百分點；在折舊大幅增長的情況下，毛利率增至21%，同比增加3個百分點。
"""
    blocks = _hk_usages(report)
    assert "hk_financial_commentary" in blocks
    assert "毛利率增至21%" in blocks["hk_financial_commentary"]["text"]


def test_hk_narrative_rejects_dense_rd_project_table_rows():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
研發項目表
3 65納米射頻絕緣體上硅 已發佈新一代平台PDK，性能較上 新一代平台繼續提升性能至業界一 中國大陸領先 主要應用於智能手機、WIFI工藝平台持續研發項 代平台大幅提升，導入客戶新產 流水平，完成更多客戶的新產品 等射頻前端模組中的射頻目 品測試驗證中。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_product_progress" not in {block["usage"] for block in blocks}


def test_hk_narrative_rejects_smic_key_financial_indicator_tables():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
主要財務指標
截至12月31日止年度 2025年較2025年 2024年 2024年（%） 2023年 毛利率 21.0% 18.0% 增加3.0個百分點 19.3% 淨利率 10.6% 9.1% 增加1.5個百分點 17.8% EBITDA利潤率 56.4% 54.5% 增加1.9個百分點 64.3% 基本每股收益 0.09美元 0.06美元 50.0 0.11美元 攤薄每股收益 0.09美元 0.06美元 50.0 0.11美元。
利潤表及現金流量表相關科目變動分析表 千美元 截至12月31日止 2025年較2025年 2024年 2024年(%) 收入 9,326,799 8,029,921 16.2 銷售成本 (7,370,200) (6,581,953) 12.0 毛利 1,956,599 1,447,968 35.1。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_financial_commentary" not in {block["usage"] for block in blocks}


def test_hk_narrative_rejects_dense_rd_project_table_rows_without_process_node():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
研發項目表
7 中大尺寸高壓顯示驅動 新一代中尺寸顯示驅動平台進入規 持續開發新的器件和技術平台，推 中國大陸領先 主要應用於中大尺寸屏幕顯工藝平台持續研發項 模量產；新一代大尺寸顯示驅動 出PDK，產品導入和實現批量生 示驅動芯片和車載屏幕顯目 平台工藝開發完成，PDK製作中。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_product_progress" not in {block["usage"] for block in blocks}


def test_hk_industry_trend_paragraph_does_not_become_product_progress_without_product_anchor():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
所處行業情況
從產業格局來看，晶圓代工環節持續凸顯戰略價值。算力芯片領域，邏輯運算類芯片需求爆發式增長，推動設計工具，工藝製程與異構封裝技術持續反覆運算，構築起涵蓋IP核、EDA工具鏈、工藝製程的全方位技術壁壘；消費電子領域，整體市場溫和復甦，系統級芯片、感測器、存儲芯片等產品持續通過工藝優化與成本管控構建競爭優勢；汽車電子與工業工控領域，由於功能安全認證體系與長週期驗證要求，形成了高度集中的產業生態格局。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    usages = {block["usage"] for block in blocks}
    assert "hk_product_progress" not in usages
    assert "hk_market_outlook" in usages or "hk_business_overview" in usages


def test_hk_narrative_rejects_financial_risk_disclosure_as_margin_commentary():
    report = """
中芯國際集成電路製造有限公司
2025年年度報告
管理層討論及分析
財務風險
1. 業績波動風險 宏觀經濟週期的波動，集成電路行業景氣度變化，境內外客戶的訂單調整，供應鏈的價格波動，廠務、電力、設備驗證等事件造成的非計劃性生產波動等，及持續的資本開支、折舊壓力和研發支出，可能導致公司在一定時期內面臨銷售收入、毛利率和利潤波動等風險。
"""
    blocks = build_periodic_report_evidence_pack(report, report_type="annual")["blocks"]
    assert "hk_financial_commentary" not in {block["usage"] for block in blocks}
