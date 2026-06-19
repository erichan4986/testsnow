"""Tests for deterministic required financial-risk metrics extraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack
from periodic_report_required_financial_metrics import (
    REQUIRED_FINANCIAL_METRICS_SCHEMA_VERSION,
    build_required_financial_risk_metrics,
)


YINGJIXIN_FINANCIAL_RISK_TEXT = """
主要会计数据和财务指标
营业收入 1,609,000,000.00 1,430,000,000.00 12.49%
归属于上市公司股东的净利润 178,000,000.00 124,000,000.00 43.24%
归属于上市公司股东的扣除非经常性损益的净利润 162,000,000.00 110,000,000.00 46.39%
经营活动产生的现金流量净额 27,420,500.00 233,959,000.00 -88.28%

存货账面价值 596,800,000.00 元，同比增长60.75%，占总资产24.21%。
存货余额 662,000,000.00 元，存货跌价准备 65,140,000.00 元，本期计提存货跌价准备 18,510,000.00 元。
审计师将存货跌价准备列为关键审计事项。

前五名供应商采购额 970,802,800.00 元，占年度采购总额73.45%；第一大供应商采购额 430,303,400.00 元，占比32.56%。
短期借款 70,040,000.00 元，应付账款同比增长76.96%。
长期股权投资同比增长101.85%，其他非流动金融资产同比增长672.21%，商誉同比增长1390.40%。
"""


SHENGBANG_FINANCIAL_RISK_TEXT = """
主要会计数据和财务指标
营业收入 3,898,054,583.68 3,346,983,120.66 16.46%
归属于上市公司股东的净利润 547,059,403.97 500,247,943.10 9.36%
归属于上市公司股东的扣除非经常性损益的净利润 427,582,529.58 451,159,069.34 -5.23%
经营活动产生的现金流量净额 466,319,946.20 549,337,594.89 -15.11%

存货账面价值 1,448,216,300.11 元，占总资产20.83%；存货余额 1,759,000,000.00 元，存货跌价准备 310,000,000.00 元。
资产减值损失 170,237,600.06 元，主要为存货跌价准备。
交易性金融资产 1,340,000,000.00 元，占总资产19.27%。
短期借款 301,000,000.00 元。
商誉 301,000,000.00 元，年初商誉 78,690,000.00 元。
"""


ZHONGJIAN_FINANCIAL_RISK_TEXT = """
主要会计数据和财务指标
营业收入 846,015,199.43 812,300,000.00 4.14%
归属于上市公司股东的净利润 315,000,000.00 356,500,000.00 -11.65%
经营活动产生的现金流量净额 880,000,000.00 198,900,000.00 342.37%
资产负债率 9.77%

应收账款期末余额 401,000,000.00 元，应收账款余额前五名客户占比 98.81%。
商业承兑汇票期末余额 178,000,000.00 元。
在建工程 615,000,000.00 元，年初 311,000,000.00 元，主要是四期项目建设投入。
资产减值损失 17,073,500.00 元，原因为在建工程设备计提减值。
购建固定资产、无形资产和其他长期资产支付的现金 585,000,000.00 元；投资活动产生的现金流量净额 -512,000,000.00 元。
货币资金 958,000,000.00 元，交易性金融资产 1,082,000,000.00 元。
审计意见类型为标准的无保留意见，关键审计事项包括收入确认和应收账款减值。
董事温月芳对财务报告、内控、项目投资、关联方认定、资金往来等议案提出异议。
"""

REALISTIC_FINANCIAL_TABLE_WITH_BARE_RATE = """
营业收入 1,609,228,659.14 1,430,516,298.72 12.49
经营活动产生的现金流量净额 27,420,497.61 233,896,798.98 -88.28
"""

REALISTIC_INVENTORY_NOTE_WITH_RMB_UNITS = """
于 2025 年 12 月 31 日，存货账面价值为人民币 59,651.98 万元，占公司期末资产总额的 24.21%。
项目 期末余额 期初余额
账面余额 存货跌价准备 /合同 履约成本减值准备 账面价值
合计 661,661,014.30 65,141,231.63 596,519,782.67 417,952,472.09 46,864,928.08 371,087,544.01
(3). 存货跌价准备及合同履约成本减值准备
项目 期初余额 本期增加金额 本期减少金额 期末余额
合计 46,864,928.08 18,507,557.26 10,231,253.71 65,141,231.63
"""

REALISTIC_INVENTORY_NOTE_WITH_THOUSAND_UNIT_SENTENCE = """
存货跌价准备
圣邦股份公司截至 2025 年 12 月 31 日的存货账面余额为人民币 1,758,646 千元，已计提存货跌价准备为 310,430 千元。
"""

NO_GOVERNANCE_DISSENT_TEMPLATE = """
董事对公司有关事项是否提出异议
报告期内董事对公司有关事项未提出异议。
表决结果：4票同意，0票反对，0票弃权。
"""

BROKEN_CAPEX_CASH_FLOW_ROW = """
购建固定资产、无形资产和其他长期资产支付
的现金 584,871,714.98 304,458,547.95
投资活动产生的现金流量净额 -511,546,206.23 -111,219,657.25
"""

MULTIPLE_MONETARY_FUNDS_AND_ASSET_IMPAIRMENT_ROWS = """
货币资金 12,853,268.43 12,853,268.43 冻结、保证金
货币资金 七、 1 728,225,080.00 676,365,893.69
资产减值损失（损失以 “-”号填列） -410,075.77
资产减值 -170,237,600.06 -30.96% 主要为计提存货跌价准备。
"""

LABEL_WITH_COMMA_BUT_NO_AMOUNT = """
投资收益 , 主要系理财产品收益变化所致。
交易性金融资产 140,143,893.83 元。
"""

HK_BLACK_SESAME_FINANCIAL_TEXT = """
截至 12 月31 日止年度
2025 年 2024 年
人民幣千元 人民幣千元 收入 822,328 474,252
毛利 337,089 194,708
研發開支 (1,417,423) (1,435,156)
經營虧損 (1,448,320) (1,753,982)
年內經調整虧損淨額 （非國際財務報告準則計量） (1,075,674) (1,304,251)
全年營收人民幣 8.22 億元，同比增長 73.4%，毛利率為 41.0%，與去年相比保持穩定。

下表載列所示年度我們現金流量的概要：
人民幣千元 人民幣千元 經營活動所用現金淨額 (985,373) (1,189,754)

# 19 存貨
減：存貨減值撥備 (49,093) (40,800)
截至 2025 年及 2024 年12 月31 日，確認為銷售成本的存貨減值撥備為分別人民幣 22.7 百萬元及人民幣 22.6 百萬元。

# 21 按公允價值計入損益的金融資產
金融資產總值 231,308 195,906

# 23 貿易應收款項及應收票據
人民幣千元 人民幣千元 貿易應收款項 553,953 306,181
減：減值撥備 (59,526) (49,629)
應收票據 5,286 1,515
499,713 258,067

# 24 現金及銀行結餘
現金及現金等價物 1,446,756 1,448,106

(b) 於2025 年2月26 日，合共 53,650,000 股新股份已按每股 23.20 港元發行。
配售所得款項淨額約為 1,237.4 百萬港元 （相當於人民幣1,142.1 百萬元）。

# 28 借款
人民幣千元 人民幣千元 借款 739,892 674,212

政府補助 (a) 99,762 79,527

於2025 年12 月31 日，黑芝麻智能武漢與億智電子訂立協議，據此，本公司同意收購億智電子合共 60% 的股權，
總代價為人民幣 478.02 百萬元。
"""

HK_BLACK_SESAME_REALISTIC_PROFIT_TABLE = """
總體而言，2025 年本集團收入、毛利實現穩步增長。
五年財務概要 收入 60,504 165,442 312,428 474,252 822,328
毛利 21,872 50,000 100,000 194,708 337,089

截至 12 月31 日止年度
2025 年 2024 年
人民幣千元 人民幣千元 收入 822,328 474,252
銷售成本 (485,239) (279,544)
毛利 337,089 194,708
研發開支 (1,417,423) (1,435,156)
經營虧損 (1,448,320) (1,753,982)
財務收入 58,175 41,084
財務收入－淨額 24,580 23,010
"""

HK_BLACK_SESAME_REALISTIC_RECEIVABLES_NOTE = """
關鍵審計事項 貿易應收款項的預期信貸虧損計量
於2025 年12 月31 日，個別已減值的貿易應收款項的虧損撥備釐定如下：
個別基準 賬面總值 預期虧損率 虧損撥備計提 原因 人民幣千元 % 人民幣千元 貿易應收款項 68,168 61.2% (41,694) 可能收回

# 23 貿易應收款項及應收票據 於12 月31 日
人民幣千元 人民幣千元 貿易應收款項 553,953 306,181
減：減值撥備 (59,526) (49,629)
應收票據 5,286 1,515
499,713 258,067
"""

HK_BLACK_SESAME_REALISTIC_CASH_GOVERNMENT_TEXT = """
截至 2025 年12 月31 日，我們的現金及現金等價物以及按公允價值計入損益的當期金融資產為人民幣 1,530.7 百萬元。
綜合現金流量表
年末現金及現金等價物 1,446,756 1,448,106

# 24 現金及銀行結餘
於12 月31 日
人民幣千元 人民幣千元 現金及現金等價物 （附註 20 ） 1,446,756 1,448,106

其他應付款項及應計費用
非流動： 政府補助 (a) Ð 2,681
流動： 政府補助 (a) 99,762 79,527
"""

HK_BLACK_SESAME_REALISTIC_ACQUISITION_TEXT = """
本公司投資 DeepRout Inc.，總代價為人民幣 50 百萬元。
本集團與珠海億智電子科技有限公司 （「億智電子」）訂立若干為期一年的貸款協議，據此，本集團向億智電子提供總額為人民幣 85 百萬元的貸款。
於2025 年12 月31 日，黑芝麻智能武漢與億智電子訂立協議，據此，本公司同意收購億智電子合共 60% 的股權，總代價為人民幣 478.02 百萬元。
"""


def test_extracts_yingjixin_financial_risk_metrics_from_raw_text():
    pack = build_periodic_report_evidence_pack(YINGJIXIN_FINANCIAL_RISK_TEXT)
    metrics = build_required_financial_risk_metrics(pack, raw_text=YINGJIXIN_FINANCIAL_RISK_TEXT)

    assert metrics["schema_version"] == REQUIRED_FINANCIAL_METRICS_SCHEMA_VERSION
    assert metrics["cash_flow_quality"]["operating_cash_flow"]["normalized"] == "2742.05万元"
    assert metrics["cash_flow_quality"]["operating_cash_flow_yoy"]["text"] == "-88.28%"
    assert metrics["profit_quality"]["deducted_net_profit_yoy"]["text"] == "46.39%"
    assert metrics["inventory_risk"]["inventory_book_value"]["normalized"] == "59680.00万元"
    assert metrics["inventory_risk"]["inventory_book_value_yoy"]["text"] == "60.75%"
    assert metrics["inventory_risk"]["inventory_impairment_allowance"]["normalized"] == "6514.00万元"
    assert metrics["inventory_risk"]["current_impairment_provision"]["normalized"] == "1851.00万元"
    assert metrics["supplier_concentration"]["top_five_percentage"]["text"] == "73.45%"
    assert metrics["supplier_concentration"]["largest_percentage"]["text"] == "32.56%"
    assert metrics["leverage_liquidity"]["short_term_borrowings"]["normalized"] == "7004.00万元"
    assert metrics["goodwill_risk"]["goodwill_yoy"]["text"] == "1390.40%"


def test_extracts_shengbang_profit_inventory_financial_assets_and_goodwill():
    pack = build_periodic_report_evidence_pack(SHENGBANG_FINANCIAL_RISK_TEXT)
    metrics = build_required_financial_risk_metrics(pack, raw_text=SHENGBANG_FINANCIAL_RISK_TEXT)

    assert metrics["profit_quality"]["revenue_yoy"]["text"] == "16.46%"
    assert metrics["profit_quality"]["net_profit_yoy"]["text"] == "9.36%"
    assert metrics["profit_quality"]["deducted_net_profit_yoy"]["text"] == "-5.23%"
    assert metrics["cash_flow_quality"]["operating_cash_flow"]["normalized"] == "46631.99万元"
    assert metrics["inventory_risk"]["inventory_book_value"]["normalized"] == "144821.63万元"
    assert metrics["inventory_risk"]["inventory_to_total_assets"]["text"] == "20.83%"
    assert metrics["inventory_risk"]["inventory_impairment_allowance"]["normalized"] == "31000.00万元"
    assert metrics["asset_impairment"]["asset_impairment_loss"]["normalized"] == "17023.76万元"
    assert metrics["financial_assets"]["trading_financial_assets"]["normalized"] == "134000.00万元"
    assert metrics["financial_assets"]["trading_financial_assets_to_total_assets"]["text"] == "19.27%"
    assert metrics["goodwill_risk"]["goodwill_balance"]["normalized"] == "30100.00万元"


def test_extracts_zhongjian_capex_receivables_and_governance_signals():
    pack = build_periodic_report_evidence_pack(ZHONGJIAN_FINANCIAL_RISK_TEXT)
    metrics = build_required_financial_risk_metrics(pack, raw_text=ZHONGJIAN_FINANCIAL_RISK_TEXT)

    assert metrics["profit_quality"]["revenue"]["normalized"] == "84601.52万元"
    assert metrics["cash_flow_quality"]["operating_cash_flow"]["normalized"] == "88000.00万元"
    assert metrics["cash_flow_quality"]["operating_cash_flow_yoy"]["text"] == "342.37%"
    assert metrics["receivables_collection"]["accounts_receivable"]["normalized"] == "40100.00万元"
    assert metrics["receivables_collection"]["top_five_ar_percentage"]["text"] == "98.81%"
    assert metrics["receivables_collection"]["commercial_bills_receivable"]["normalized"] == "17800.00万元"
    assert metrics["capex_capacity"]["construction_in_progress"]["normalized"] == "61500.00万元"
    assert metrics["capex_capacity"]["capex_cash_paid"]["normalized"] == "58500.00万元"
    assert metrics["capex_capacity"]["investing_cash_flow"]["normalized"] == "-51200.00万元"
    assert metrics["asset_impairment"]["asset_impairment_loss"]["normalized"] == "1707.35万元"
    assert metrics["financial_assets"]["monetary_funds"]["normalized"] == "95800.00万元"
    assert metrics["financial_assets"]["trading_financial_assets"]["normalized"] == "108200.00万元"
    assert metrics["audit_governance"]["audit_opinion"] == "标准无保留意见"
    assert "收入确认" in metrics["audit_governance"]["key_audit_matters"]
    assert metrics["audit_governance"]["governance_dissent_present"] is True


def test_a_share_profit_quality_is_not_overridden_by_generic_hk_revenue_noise():
    text = """
    主要会计数据和财务指标
    营业收入 846,092,620.66 812,470,190.54 4.14%
    归属于上市公司股东的净利润 315,000,000.00 356,500,000.00 -11.65%

    附注：按千元披露的其他表格
    收入 501.45 400.00
    """
    pack = build_periodic_report_evidence_pack(text)
    metrics = build_required_financial_risk_metrics(pack, raw_text=text)

    assert metrics["profit_quality"]["revenue"]["normalized"] == "84609.26万元"
    assert metrics["profit_quality"]["revenue_yoy"]["text"] == "4.14%"


def test_a_share_empty_borrowing_rows_do_not_create_hk_borrowings():
    text = """
    资产负债表
    人民币千元
    流动负债： 短期借款 交易性金融负债 衍生金融负债 应付票据 115,212,343.16 28,011,846.78
    应付账款 85,956,780.29 56,536,258.43 应交税费 75,295,957.01 40,000,000.00
    非流动负债： 长期借款 应付债券 递延收益 29,149,256.54 34,594,880.96
    """
    pack = build_periodic_report_evidence_pack(text)
    metrics = build_required_financial_risk_metrics(pack, raw_text=text)

    assert "borrowings" not in metrics["leverage_liquidity"]
    assert "short_term_borrowings" not in metrics["leverage_liquidity"]


def test_financial_metrics_normalized_values_include_extracted_amounts_and_rates():
    pack = build_periodic_report_evidence_pack(SHENGBANG_FINANCIAL_RISK_TEXT)
    metrics = build_required_financial_risk_metrics(pack, raw_text=SHENGBANG_FINANCIAL_RISK_TEXT)

    assert "144821.63万元" in metrics["normalized_values"]
    assert "-5.23%" in metrics["normalized_values"]
    assert "19.27%" in metrics["normalized_values"]


def test_financial_summary_rows_accept_bare_percentage_rate():
    pack = build_periodic_report_evidence_pack(REALISTIC_FINANCIAL_TABLE_WITH_BARE_RATE)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=REALISTIC_FINANCIAL_TABLE_WITH_BARE_RATE,
    )

    assert metrics["profit_quality"]["revenue_yoy"]["text"] == "12.49%"
    assert metrics["cash_flow_quality"]["operating_cash_flow"]["normalized"] == "2742.05万元"
    assert metrics["cash_flow_quality"]["operating_cash_flow_yoy"]["text"] == "-88.28%"


def test_inventory_note_accepts_rmb_unit_table_and_thousand_unit_sentence():
    pack = build_periodic_report_evidence_pack(REALISTIC_INVENTORY_NOTE_WITH_RMB_UNITS)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=REALISTIC_INVENTORY_NOTE_WITH_RMB_UNITS,
    )
    assert metrics["inventory_risk"]["inventory_book_value"]["normalized"] == "59651.98万元"
    assert metrics["inventory_risk"]["inventory_balance"]["normalized"] == "66166.10万元"
    assert metrics["inventory_risk"]["inventory_impairment_allowance"]["normalized"] == "6514.12万元"
    assert metrics["inventory_risk"]["current_impairment_provision"]["normalized"] == "1850.76万元"

    pack = build_periodic_report_evidence_pack(REALISTIC_INVENTORY_NOTE_WITH_THOUSAND_UNIT_SENTENCE)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=REALISTIC_INVENTORY_NOTE_WITH_THOUSAND_UNIT_SENTENCE,
    )
    assert metrics["inventory_risk"]["inventory_balance"]["normalized"] == "175864.60万元"
    assert metrics["inventory_risk"]["inventory_impairment_allowance"]["normalized"] == "31043.00万元"
    assert metrics["inventory_risk"]["inventory_book_value"]["normalized"] == "144821.60万元"


def test_governance_template_does_not_create_false_dissent_signal():
    pack = build_periodic_report_evidence_pack(NO_GOVERNANCE_DISSENT_TEMPLATE)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=NO_GOVERNANCE_DISSENT_TEMPLATE,
    )
    assert metrics["audit_governance"].get("governance_dissent_present") is None


def test_capex_cash_paid_handles_jina_line_break_inside_label():
    pack = build_periodic_report_evidence_pack(BROKEN_CAPEX_CASH_FLOW_ROW)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=BROKEN_CAPEX_CASH_FLOW_ROW,
    )
    assert metrics["capex_capacity"]["capex_cash_paid"]["normalized"] == "58487.17万元"
    assert metrics["capex_capacity"]["investing_cash_flow"]["normalized"] == "-51154.62万元"


def test_financial_assets_and_impairment_choose_material_rows_when_label_repeats():
    pack = build_periodic_report_evidence_pack(MULTIPLE_MONETARY_FUNDS_AND_ASSET_IMPAIRMENT_ROWS)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=MULTIPLE_MONETARY_FUNDS_AND_ASSET_IMPAIRMENT_ROWS,
    )
    assert metrics["financial_assets"]["monetary_funds"]["normalized"] == "72822.51万元"
    assert metrics["asset_impairment"]["asset_impairment_loss"]["normalized"] == "-17023.76万元"


def test_financial_metrics_ignore_punctuation_without_amount_after_label():
    pack = build_periodic_report_evidence_pack(LABEL_WITH_COMMA_BUT_NO_AMOUNT)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=LABEL_WITH_COMMA_BUT_NO_AMOUNT,
    )

    assert "investment_income" not in metrics["financial_assets"]
    assert "元" not in metrics["normalized_values"]


def test_extracts_hk_traditional_chinese_financial_risk_metrics():
    pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_FINANCIAL_TEXT)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=HK_BLACK_SESAME_FINANCIAL_TEXT,
    )

    assert metrics["profit_quality"]["revenue"]["normalized"] == "82232.80万元"
    assert metrics["profit_quality"]["revenue_yoy"]["text"] == "73.4%"
    assert metrics["profit_quality"]["gross_profit"]["normalized"] == "33708.90万元"
    assert metrics["profit_quality"]["gross_margin"]["text"] == "41.0%"
    assert metrics["profit_quality"]["operating_loss"]["normalized"] == "-144832.00万元"
    assert metrics["profit_quality"]["adjusted_net_loss"]["normalized"] == "-107567.40万元"
    assert metrics["profit_quality"]["rd_expense"]["normalized"] == "-141742.30万元"
    assert metrics["cash_flow_quality"]["operating_cash_flow"]["normalized"] == "-98537.30万元"
    assert metrics["inventory_risk"]["inventory_impairment_allowance"]["normalized"] == "-4909.30万元"
    assert metrics["inventory_risk"]["current_impairment_provision"]["normalized"] == "2270.00万元"
    assert metrics["receivables_collection"]["accounts_receivable"]["normalized"] == "55395.30万元"
    assert metrics["receivables_collection"]["bills_receivable"]["normalized"] == "528.60万元"
    assert metrics["financial_assets"]["monetary_funds"]["normalized"] == "144675.60万元"
    assert metrics["financial_assets"]["fair_value_financial_assets"]["normalized"] == "23130.80万元"
    assert metrics["leverage_liquidity"]["borrowings"]["normalized"] == "73989.20万元"
    assert metrics["government_grants"]["government_grants_current"]["normalized"] == "9976.20万元"
    assert metrics["corporate_actions"]["placing_net_proceeds"]["normalized"] == "114210.00万元"
    assert metrics["corporate_actions"]["acquisition_consideration"]["normalized"] == "47802.00万元"


def test_hk_profit_metrics_prefer_main_statement_over_finance_income_and_five_year_summary():
    pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_REALISTIC_PROFIT_TABLE)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=HK_BLACK_SESAME_REALISTIC_PROFIT_TABLE,
    )

    assert metrics["profit_quality"]["revenue"]["normalized"] == "82232.80万元"
    assert metrics["profit_quality"]["gross_profit"]["normalized"] == "33708.90万元"
    assert metrics["profit_quality"]["operating_loss"]["normalized"] == "-144832.00万元"
    assert metrics["profit_quality"]["rd_expense"]["normalized"] == "-141742.30万元"


def test_hk_receivables_and_bills_use_note_table_not_audit_or_section_fragments():
    pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_REALISTIC_RECEIVABLES_NOTE)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=HK_BLACK_SESAME_REALISTIC_RECEIVABLES_NOTE,
    )

    assert metrics["receivables_collection"]["accounts_receivable"]["normalized"] == "55395.30万元"
    assert metrics["receivables_collection"]["bills_receivable"]["normalized"] == "528.60万元"


def test_hk_cash_and_government_grants_use_note_rows_not_summary_or_policy_fragments():
    pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_REALISTIC_CASH_GOVERNMENT_TEXT)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=HK_BLACK_SESAME_REALISTIC_CASH_GOVERNMENT_TEXT,
    )

    assert metrics["financial_assets"]["monetary_funds"]["normalized"] == "144675.60万元"
    assert metrics["government_grants"]["government_grants_current"]["normalized"] == "9976.20万元"


def test_hk_acquisition_consideration_prefers_target_company_over_other_investments():
    pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_REALISTIC_ACQUISITION_TEXT)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=HK_BLACK_SESAME_REALISTIC_ACQUISITION_TEXT,
    )

    assert metrics["corporate_actions"]["acquisition_consideration"]["normalized"] == "47802.00万元"


def test_derived_financial_metrics_for_hk_black_sesame():
    """Derived ratios are computed deterministically from normalized required metrics."""
    pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_FINANCIAL_TEXT)
    metrics = build_required_financial_risk_metrics(
        pack,
        raw_text=HK_BLACK_SESAME_FINANCIAL_TEXT,
    )

    derived = metrics.get("derived_financial_metrics")
    assert derived is not None
    assert derived["rd_expense_to_revenue"]["normalized"] == "172.37%"
    assert derived["rd_expense_to_gross_profit"]["normalized"] == "420.49%"
    assert derived["operating_cash_outflow_to_cash"]["normalized"] == "68.11%"
    # 口径：贸易应收款项 + 应收票据
    assert derived["receivables_to_revenue"]["normalized"] == "68.01%"
    # 口径：现金及现金等价物 + 按公允价值计入损益的金融资产
    assert derived["acquisition_to_cash_and_fv_assets"]["normalized"] == "28.49%"
    # 当前 HK 示例未稳定抽到存货原值，因此该派生指标应缺省
    assert "inventory_impairment_allowance_to_inventory_if_available" not in derived


def test_hk_profit_quality_prefers_contract_revenue_summary_row():
    """HK revenue should prefer the main contract-revenue row over ESG revenue-intensity text."""
    text = """
    變動 (%) 2025 年 2024 年（人民幣千元，百分比除外）
    來自客戶合同的收入 3,758,268 2,383,554 57.7
    毛利 2,425,680 1,841,354 31.7
    研發開支 (5,153,708) (3,156,055) 63.3
    經調整經營虧損 (2,372,323) (1,495,179) 58.7
    經調整虧損淨額 (2,811,776) (1,681,155) 67.3

    目前的每百萬人民幣收益耗電量強度為 1.60 兆瓦時，較基準年減少 30%。
    """
    pack = build_periodic_report_evidence_pack(text)
    metrics = build_required_financial_risk_metrics(pack, raw_text=text)

    profit = metrics["profit_quality"]
    assert profit["revenue"]["normalized"] == "375826.80万元"
    assert profit["revenue_yoy"]["text"] == "57.7%"
    assert profit["gross_profit"]["normalized"] == "242568.00万元"
    assert profit["rd_expense"]["normalized"] == "-515370.80万元"
    assert profit["adjusted_net_loss"]["normalized"] == "-281177.60万元"


def test_hk_profit_quality_prefers_comprehensive_gross_margin_over_adjusted_product_margin():
    text = """
    變動 (%) 2025 年 2024 年（人民幣千元，百分比除外）
    來自客戶合同的收入 3,758,268 2,383,554 57.7
    毛利 2,425,680 1,841,354 31.7
    研發開支 (5,153,708) (3,156,055) 63.3
    經調整虧損淨額 (2,811,776) (1,681,155) 67.3

    於2025 年，毛利為人民幣 2,425.7 百萬元，同比增加 31.7%。
    毛利率由 2024 年的 77.3% 下降至 2025 年的 64.5%。
    為促使若干客戶快速導入產品，剔除此項影響後，我們的經調整毛利率為 42.5%。
    """
    pack = build_periodic_report_evidence_pack(text)
    metrics = build_required_financial_risk_metrics(pack, raw_text=text)

    assert metrics["profit_quality"]["gross_margin"]["text"] == "64.5%"


def test_derived_financial_metrics_skip_when_denominator_missing():
    metrics = build_required_financial_risk_metrics({"blocks": []}, raw_text="")
    assert metrics.get("derived_financial_metrics") in (None, {})


def test_derived_financial_metrics_skip_when_denominator_zero():
    text = "营业收入 0.00 元，研发开支 100.00 元。"
    pack = build_periodic_report_evidence_pack(text)
    metrics = build_required_financial_risk_metrics(pack, raw_text=text)
    derived = metrics.get("derived_financial_metrics", {})
    assert "rd_expense_to_revenue" not in derived
