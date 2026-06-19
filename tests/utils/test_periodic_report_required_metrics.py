"""Tests for deterministic required business metrics extraction."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack
from periodic_report_required_metrics import (
    REQUIRED_METRICS_SCHEMA_VERSION,
    build_required_business_metrics,
    _normalize_numeric,
)


# Compact fixture copied from /tmp/yingjixin_2025_annual_jina.txt
YINGJIXIN_SEGMENT_MARGIN_TEXT = """
主营业务分行业情况
分行业 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
集成电路 1,602,118,368.25 1,052,172,639.66 34.33 14.25 12.96 增加0.75个百分点
主营业务分产品情况
分产品 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
电源管理类 1,062,041,234.54 695,954,120.28 34.47 12.44 8.09 增加2.64个百分点
电池管理类 202,758,468.19 124,020,223.92 38.83 72.39 77.37 减少1.72个百分点
数 模 混 合 SoC 类 337,194,197.68 232,094,292.80 31.17 -0.83 6.68 -4.84
其他芯片 124,467.84 104,002.66 16.44 11.36 -25.56 41.45
主营业务分地区情况
分地区 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
国内销售 1,561,613,954.63 1,026,973,475.97 34.24 15.11 13.63 增加0.86个百分点
国外销售 40,504,413.62 25,199,163.69 37.79 -11.30 -9.04 减少1.55个百分点
主营业务分销售模式情况
销售模式 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
直销模式 214,214,701.91 147,573,180.46 31.11 5.83 -0.88 增加4.66个百分点
经销模式 1,387,903,666.34 904,599,459.20 34.82 15.67 15.59 增加0.05个百分点
"""

YINGJIXIN_INVENTORY_TEXT = """
产销量情况分析表
主要产品 单位 生产量 销售量 库存量 生产量比上年增减（%） 销售量比上年增减（%） 库存量比上年增减（%）
电源管理类 万颗 131,477.02 128,731.91 10,154.28 13.19 10.61 51.80
数 模 混 合
SoC 类 万颗 44,349.66 46,639.47 5,446.70 10.21 22.09 61.04
电池管理类 万颗 31,138.84 28,144.41 4,276.65 106.44 90.09 618.99
其他芯片 万颗 2,384.36 153.00 686.87 2,464.24 72.42 4,458.47
"""

YINGJIXIN_CUSTOMER_SUPPLIER_TEXT = """
前五名客户销售额 49,019.50 万元，占年度销售总额 30.46%；其中前五名客户销售额中关联方销售额 0.00 万元，占年度销售总额 0.00%。
公司前五名客户
序号 客户名称 销售额 占年度销售总额比例（%） 是否与上市公司存在关联关系
1 客户一 10,835.52 6.73 否
2 客户二 9,941.16 6.18 否
3 客户三 9,925.97 6.17 否
4 客户四 9,341.19 5.80 否
5 客户五 8,975.66 5.58 否
合计 / 49,019.50 30.46 /

前五名供应商采购额 97,080.28 万元，占年度采购总额 73.45%；其中前五名供应商采购额中关联方采购额 0.00 万元，占年度采购总额 0.00%。
公司前五名供应商
序号 供应商名称 采购额 占年度采购总额比例（%） 是否与上市公司存在关联关系
1 供应商一 43,030.34 32.56 否
2 供应商二 19,425.71 14.70 否
3 供应商三 17,516.51 13.25 否
4 供应商四 9,574.21 7.24 否
5 供应商五 7,533.50 5.70 否
合计 / 97,080.28 73.45 /
"""

HUIZHIWEI_SEGMENT_INVENTORY_TEXT = """
主营业务分产品情况
分产品 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
4G 模组 328,312,300.00 313,073,600.00 4.64 66.69 70.10 减少1.91个百分点
5G 模组 475,731,700.00 434,765,300.00 8.61 45.92 31.81 增加9.80个百分点
产销量情况分析表
主要产品 单位 生产量 销售量 库存量 生产量比上年增减（%） 销售量比上年增减（%） 库存量比上年增减（%）
4G 模组 万颗 19,235.56 20,289.91 2,585.09 39.71 40.56 -34.11
5G 模组 万颗 26,694.89 23,713.77 5,852.31 75.42 50.33 94.01
"""

HUADAJIUTIAN_SEGMENT_MARGIN_TEXT = """
主营业务分产品情况
分产品 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
EDA 软件销售 1,074,512,360.11 0.00 100.00% -1.63% 0.00%
技术服务 201,282,884.21 111,431,188.39 44.64% 74.93% 57.18% 6.25%
主营业务分地区情况
"""

YINGJIXIN_FULL_REPORT = (
    YINGJIXIN_SEGMENT_MARGIN_TEXT + "\n" +
    YINGJIXIN_INVENTORY_TEXT + "\n" +
    YINGJIXIN_CUSTOMER_SUPPLIER_TEXT
)

ZHONGJIAN_SEGMENT_INVENTORY_TEXT = """
主营业务分产品情况
分产品 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
碳纤维 443,494,353.42 198,674,441.60 55.21 -19.59 -12.85 减少8.79个百分点
碳纤维织物 402,520,846.01 98,704,973.33 75.46 54.60 30.42 增加13.38个百分点
产销量情况分析表
主要产品 单位 生产量 销售量 库存量 生产量比上年增减（%） 销售量比上年增减（%） 库存量比上年增减（%）
碳纤维 KG 388,277.44 315,326.80 94,938.11 23.07 8.88 150.95
碳纤维织物 KG 52,930.66 73,313.33 2,102.28 47.37 52.12 -31.91
"""

ZHONGJIAN_CUSTOMER_TEXT = """
前五名客户销售额 98,341.07 万元，占年度销售总额 99. 42%；其中前五名客户销售额中关联方销售额 0.00 万元，占年度销售总额 0.00%。
公司前五名客户
序号 客户名称 销售额 占年度销售总额比例（%） 是否与上市公司存在关联关系
1 客户 A 86,560.30 87.4 9 否
"""

ZHONGJIAN_ACTUAL_INVENTORY_TEXT = """
产销量情况
销售量 KG 315,326.80 301,915.01 4.44%
生产量 KG 388,277.44 306,163.72 26.82%
库存量 KG 94,938.11 37,831.74 150.95%
随着三期各生产线正常投产，产量有所上升，客户四季度需求呈现阶段性放缓，导致年末库存量增大。
"""

ZHONGJIAN_ACTUAL_CUSTOMER_SUPPLIER_TEXT = """
前五名客户合计销售金额（元） 841,075,474.56
前五名客户合计销售金额占年度销售总额比例 99. 42%
前五名客户销售额中关联方销售额占年度销售总额比例 1. 54%
公司前 5 大客户资料
序号 客户名称 销售额（元） 占年度销售总额比例
1 客户 A 740,169,474.89 87.4 9%
合计 -- 841,075,474.56 99.42%

前五名供应商合计采购金额（元） 357,509,148.64
前五名供应商合计采购金额占年度采购总额比例 41.58%
前五名供应商采购额中关联方采购额占年度采购总额比例 0.00%
公司前 5 大供应商资料
序号 供应商名称 采购额（元） 占年度采购总额比例
1 供应商 A 133,000,000.00 15.48%
合计 -- 357,509,148.64 41.58%
"""

SHENGBANG_ACTUAL_INVENTORY_TEXT = """
产销量情况
销售量 颗 7,862,728,539 5,964,060,712 31.84%
生产量 颗 8,610,305,518 6,481,555,180 32.84%
库存量 颗 2,593,446,280 1,838,773,138 41.04%
销售量本报告期比上一个报告期增加系营业收入增加，相应销售数量增加所致。
"""

SHENGBANG_ACTUAL_CUSTOMER_SUPPLIER_TEXT = """
前五名客户合计销售金额（元） 1,291,257,970.80
前五名客户合计销售金额占年度销售总额比例 33.13%
前五名客户销售额中关联方销售额占年度销售总额比例 0.00%
公司前 5 大客户资料
序号 客户名称 销售额（元） 占年度销售总额比例
1 第一名 303,592,511.98 7.79%
合计 -- 1,291,257,970.80 33.13%

前五名供应商合计采购金额（元） 2,180,676,102.11
前五名供应商合计采购金额占年度采购总额比例 90.99%
前五名供应商采购额中关联方采购额占年度采购总额比例 0.00%
公司前 5 大供应商资料
序号 供应商名称 采购额（元） 占年度采购总额比例
1 第一名 949,000,000.00 39.61%
合计 -- 2,180,676,102.11 90.99%
"""

SHENGBANG_COMBINED_SEGMENT_MARGIN_TEXT = """
营业收入 营业成本 毛利率 营业收入比上 年同期增减 营业成本比上 年同期增减 毛利率比上年 同期增减
分行业
集成电路行业 3,898,054,583.68 1,912,334,714.23 50.94% 16.46% 17.72% -0.52%
分产品
信号链产品 1,471,022,875.27 615,285,480.40 58.17% 26.23% 26.62% -0.13%
电源管理产品 2,379,833,746.57 1,276,179,316.39 46.38% 9.08% 12.09% -1.43%
分地区 圣邦微电子（北京）股份有限公司 2025 年年度报告全文 22
大陆 1,635,122,171.09 792,836,248.42 51.51% 9.18% 17.17% -3.31%
香港 1,921,049,328.98 947,182,843.23 50.69% 29.37% 24.16% 2.07%
分销售模式
经销 3,609,911,439.81 1,746,401,174.88 51.62% 20.37% 21.03% -0.27%
"""

HK_BLACK_SESAME_BUSINESS_TEXT = """
收入
我們的收入由截至 2024 年12 月31 日止年度的人民幣 474.3 百萬元增加 73.4% 至截至 2025 年12 月31 日止年度的人民幣 822.3 百萬元。
輔助駕駛產品及解決方案
我們的輔助駕駛產品及解決方案收入由截至 2024 年12 月31 日止年度的人民幣 438.0 百萬元增加 56.8% 至截至 2025 年12 月31 日止年度的人民幣 686.9 百萬元。
智能影像解決方案
我們的智能影像解決方案收入由截至 2024 年12 月31 日止年度的人民幣 36.3 百萬元增加 7.9%，至截至 2025 年12 月31 日止年度的人民幣 39.2 百萬元。
具身智能解決方案
我們的具身智能解決方案，截至 2025 年12 月31 日止年度的收入為人民幣 96.3 百萬元。

輔助駕駛產品及解決方案的銷售成本由截至 2024 年12 月31 日止年度的人民幣 274.2 百萬元增加 56.8% 至截至 2025 年12 月31 日止年度的人民幣 429.8 百萬元。
智能影像解決方案的銷售成本由截至 2024 年12 月31 日止年度的人民幣 5.3 百萬元增加 12.4% 至截至 2025 年12 月31 日止年度的人民幣 6.0 百萬元。
具身智能解決方案的銷售成本，截至 2025 年12 月31 日止年度為人民幣 49.4 百萬元。

毛利及毛利率
我們輔助駕駛產品及解決方案的毛利率保持相對穩定，截至 2024 年12 月31 日止年度與截至 2025 年12 月31 日止年度均為 37.4%。
我們智能影像解決方案業務的毛利率同樣保持相對穩定，截至 2024 年12 月31 日止年度與截至2025 年12 月31 日止年度的分別為 85.4% 與84.7%。
此外，我們的新業務具身智能解決方案的毛利率截至 2025 年12 月31 日止年度為 48.7%。

於報告期內，本集團五大客戶產生的收入約佔本集團總收入的 38.1%，而最大客戶產生的收入約佔本集團總收入的 9.1%。
於報告期內，本集團五大供應商的採購額約佔本集團採購總額的 27.6%，而最大供應商的採購額約佔本集團採購總額的 10.2%。
"""

HK_BLACK_SESAME_REALISTIC_ADAS_MARGIN_TEXT = """
收入
我們的輔助駕駛產品及解決方案收入由截至 2024 年12 月31 日止年度的人民幣 438.0 百萬元增加 56.8% 至截至 2025 年12 月31 日止年度的人民幣 686.9 百萬元。
輔助駕駛產品及解決方案的銷售成本由截至 2024 年12 月31 日止年度的人民幣 274.2 百萬元增加 56.8% 至截至 2025 年12 月31 日止年度的人民幣 429.8 百萬元。
由於上述原因，我們的整體毛利由截至 2024 年12 月31 日止年度的人民幣 194.7 百萬元增加 73.1% 至截至 2025 年12 月31 日止年度的人民幣 337.1 百萬元。我們輔助駕駛產品及解決方案的毛利率保持相對穩定，截至 2024 年12 月31 日止年度與截至 2025 年12 月31 日止年度均為 37.4%。
"""

HK_HORIZON_BUSINESS_LINE_TEXT = """
收入
截至 2025 年12 月31 日止年度，收入同比增加 57.7% 至人民幣 3,758.3 百萬元。下表載列我們截至 2025 年及2024 年12 月31 日止年度按收入來源劃分的收入：
> 汽車解決方案
> 產品解決方案 1,622,274 43.2% 664,237 27.9%
> 授權及服務業務 1,934,913 51.4% 1,647,466 69.1%
> 非車解決方案 201,081 5.3% 71,851 3.0%
截至 2025 年12 月31 日止年度，汽車解決方案的收入同比增加 53.9% 至人民幣 3,557.2 百萬元。
截至 2025 年12 月31 日止年度，產品解決方案的收入同比增加 144.2% 至人民幣 1,622.3 百萬元。
截至 2025 年12 月31 日止年度，授權及服務業務的收入同比增加 17.4% 至人民幣 1,934.9 百萬元。
截至 2025 年12 月31 日止年度，非車解決方案的收入同比增加 179.9% 至人民幣 201.1 百萬元。

毛利及毛利率
於2025 年，毛利為人民幣 2,425.7 百萬元，同比增加 31.7% 。毛利率由 2024 年的 77.3% 下降至 2025 年的 64.5% 。
下表載列我們截至 2025 年及 2024 年12 月31 日止年度按汽車解決方案的業務線劃分的毛利及毛利率：
> 毛利 毛利率 毛利 毛利率 （人民幣千元，百分比除外）
> 汽車解決方案
> 產品解決方案 559,898 34.5% 308,059 46.4%
> 授權及服務業務 1,829,426 94.5% 1,516,480 92.0%
> 總計 2,389,324 67.2% 1,824,539 78.9%
－ 截至 2025 年12 月31 日止年度，汽車解決方案的毛利同比增加 31.0% 至人民幣 2,389.3 百萬元，而汽車解決方案的毛利率由上年的 78.9% 下降至 67.2% 。
• 截至 2025 年12 月31 日止年度，產品解決方案的毛利同比增加 81.8% 至人民幣 559.9 百萬元，而毛利率由 2024 年的 46.4% 下降至 34.5% 。
• 截至 2025 年12 月31 日止年度，授權及服務業務的毛利同比增加 20.6% 至人民幣 1,829.4 百萬元，而毛利率由上年的 92.0% 增加至 94.5% 。
－ 截至 2025 年12 月31 日止年度，非車解決方 案的毛利同比增加 116.2% 至人民幣 36.4 百萬元，而毛利率由去年的 23.4% 下降至 18.1% 。
"""

ZHONGJIAN_FULL_REPORT = ZHONGJIAN_SEGMENT_INVENTORY_TEXT + "\n" + ZHONGJIAN_CUSTOMER_TEXT


def _find_row(rows, label):
    for row in rows:
        if row["label"] == label:
            return row
    return None


def test_required_metrics_consumes_evidence_pack_blocks():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)
    assert metrics["schema_version"] == REQUIRED_METRICS_SCHEMA_VERSION
    assert metrics["source_pack_schema_version"] == "periodic_report_evidence_pack.v1"
    assert metrics["segment_rows"]
    assert metrics["inventory_rows"]
    assert metrics["customer_concentration"]["present"]
    assert metrics["supplier_concentration"]["present"]


def test_extracts_yingjixin_segment_margin_rows_from_evidence_block():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    power = _find_row(metrics["segment_rows"], "电源管理类")
    assert power is not None
    assert power["revenue"]["normalized"] in {"106204.12万元", "1062041200元"}
    assert power["revenue_yoy"]["text"] == "12.44%"
    assert power["gross_margin"]["text"] == "34.47%"
    assert power["gross_margin_delta"]["text"] in {"增加2.64个百分点", "+2.64pct"}

    battery = _find_row(metrics["segment_rows"], "电池管理类")
    assert battery is not None
    assert battery["revenue"]["normalized"] in {"20275.85万元", "202758468.19元"}
    assert battery["revenue_yoy"]["text"] == "72.39%"
    assert battery["gross_margin"]["text"] == "38.83%"
    assert battery["gross_margin_delta"]["text"] in {"减少1.72个百分点", "-1.72pct"}

    soc = _find_row(metrics["segment_rows"], "数模混合 SoC 类")
    assert soc is not None
    assert soc["revenue"]["normalized"] in {"33719.42万元", "337194197.68元"}
    assert soc["revenue_yoy"]["text"] == "-0.83%"
    assert soc["gross_margin"]["text"] == "31.17%"
    assert soc["gross_margin_delta"]["text"] in {"-4.84", "减少4.84个百分点", "-4.84pct"}


def test_extracts_hk_business_segment_rows_and_concentration_from_narrative():
    evidence_pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_BUSINESS_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=HK_BLACK_SESAME_BUSINESS_TEXT,
    )

    adas = _find_row(metrics["segment_rows"], "輔助駕駛產品及解決方案")
    imaging = _find_row(metrics["segment_rows"], "智能影像解決方案")
    embodied = _find_row(metrics["segment_rows"], "具身智能解決方案")

    assert adas is not None
    assert adas["revenue"]["normalized"] == "68690.00万元"
    assert adas["cost"]["normalized"] == "42980.00万元"
    assert adas["revenue_yoy"]["text"] == "56.8%"
    assert adas["gross_margin"]["text"] == "37.4%"

    assert imaging is not None
    assert imaging["revenue"]["normalized"] == "3920.00万元"
    assert imaging["cost"]["normalized"] == "600.00万元"
    assert imaging["revenue_yoy"]["text"] == "7.9%"
    assert imaging["gross_margin"]["text"] == "84.7%"

    assert embodied is not None
    assert embodied["revenue"]["normalized"] == "9630.00万元"
    assert embodied["cost"]["normalized"] == "4940.00万元"
    assert embodied["gross_margin"]["text"] == "48.7%"

    customer = metrics["customer_concentration"]
    assert customer["present"]
    assert customer["top_five_percentage"]["text"] == "38.1%"
    assert customer["largest_percentage"]["text"] == "9.1%"

    supplier = metrics["supplier_concentration"]
    assert supplier["present"]
    assert supplier["top_five_percentage"]["text"] == "27.6%"
    assert supplier["largest_percentage"]["text"] == "10.2%"


def test_hk_business_segment_margin_handles_realistic_long_adas_sentence():
    evidence_pack = build_periodic_report_evidence_pack(HK_BLACK_SESAME_REALISTIC_ADAS_MARGIN_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=HK_BLACK_SESAME_REALISTIC_ADAS_MARGIN_TEXT,
    )

    adas = _find_row(metrics["segment_rows"], "輔助駕駛產品及解決方案")
    assert adas is not None
    assert adas["revenue"]["normalized"] == "68690.00万元"
    assert adas["cost"]["normalized"] == "42980.00万元"
    assert adas["gross_margin"]["text"] == "37.4%"


def test_extracts_hk_horizon_business_line_revenue_and_margin_rows():
    evidence_pack = build_periodic_report_evidence_pack(HK_HORIZON_BUSINESS_LINE_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=HK_HORIZON_BUSINESS_LINE_TEXT,
    )

    auto = _find_row(metrics["segment_rows"], "汽車解決方案")
    product = _find_row(metrics["segment_rows"], "產品解決方案")
    license_service = _find_row(metrics["segment_rows"], "授權及服務業務")
    non_auto = _find_row(metrics["segment_rows"], "非車解決方案")
    labels = {row["label"] for row in metrics["segment_rows"]}

    assert auto is not None
    assert auto["revenue"]["normalized"] == "355720.00万元"
    assert auto["revenue_yoy"]["text"] == "53.9%"
    assert auto["gross_margin"]["text"] == "67.2%"

    assert product is not None
    assert product["revenue"]["normalized"] == "162230.00万元"
    assert product["revenue_yoy"]["text"] == "144.2%"
    assert product["gross_margin"]["text"] == "34.5%"

    assert license_service is not None
    assert license_service["revenue"]["normalized"] == "193490.00万元"
    assert license_service["gross_margin"]["text"] == "94.5%"

    assert non_auto is not None
    assert non_auto["revenue"]["normalized"] == "20110.00万元"
    assert non_auto["gross_margin"]["text"] == "18.1%"
    assert "而汽車解決方案" not in labels


def test_extracts_yingjixin_inventory_rows_from_evidence_block():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    power = _find_row(metrics["inventory_rows"], "电源管理类")
    assert power is not None
    assert power["quantity_unit"] == "万颗"
    assert power["inventory_volume"]["text"] in {"10,154.28", "10,154.28万颗"}
    assert power["inventory_yoy"]["text"] == "51.80%"

    battery = _find_row(metrics["inventory_rows"], "电池管理类")
    assert battery["inventory_yoy"]["text"] == "618.99%"

    soc = _find_row(metrics["inventory_rows"], "数模混合 SoC 类")
    assert soc is not None
    assert soc["inventory_yoy"]["text"] == "61.04%"


def test_preserves_product_labels_that_start_with_4g_or_5g():
    evidence_pack = build_periodic_report_evidence_pack(HUIZHIWEI_SEGMENT_INVENTORY_TEXT)
    metrics = build_required_business_metrics(evidence_pack, raw_text=HUIZHIWEI_SEGMENT_INVENTORY_TEXT)

    segment_labels = [row["label"] for row in metrics["segment_rows"]]
    inventory_labels = [row["label"] for row in metrics["inventory_rows"]]

    assert "4G 模组" in segment_labels
    assert "5G 模组" in segment_labels
    assert "4G 模组" in inventory_labels
    assert "5G 模组" in inventory_labels
    assert "G 模组" not in segment_labels + inventory_labels


def test_extracts_zero_cost_software_segment_row_alongside_full_rows():
    evidence_pack = build_periodic_report_evidence_pack(HUADAJIUTIAN_SEGMENT_MARGIN_TEXT)
    metrics = build_required_business_metrics(evidence_pack, raw_text=HUADAJIUTIAN_SEGMENT_MARGIN_TEXT)

    software = _find_row(metrics["segment_rows"], "EDA 软件销售")
    service = _find_row(metrics["segment_rows"], "技术服务")

    assert software is not None
    assert software["revenue"]["normalized"] == "107451.24万元"
    assert software["cost"]["normalized"] == "0.00万元"
    assert software["gross_margin"]["text"] == "100.00%"
    assert software["revenue_yoy"]["text"] == "-1.63%"
    assert service is not None
    assert service["gross_margin"]["text"] == "44.64%"


def test_extracts_yingjixin_customer_supplier_concentration_from_evidence_block():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    customer = metrics["customer_concentration"]
    assert customer["present"]
    assert customer["top_five_amount"]["text"] == "49,019.50"
    assert customer["top_five_amount"]["unit"] == "万元"
    assert customer["top_five_percentage"]["text"] == "30.46%"
    assert customer["largest_amount"]["text"] == "10,835.52"
    assert customer["largest_percentage"]["text"] == "6.73%"

    supplier = metrics["supplier_concentration"]
    assert supplier["present"]
    assert supplier["top_five_amount"]["text"] == "97,080.28"
    assert supplier["top_five_percentage"]["text"] == "73.45%"
    assert supplier["largest_amount"]["text"] == "43,030.34"
    assert supplier["largest_percentage"]["text"] == "32.56%"


def test_customer_concentration_uses_raw_fallback_when_evidence_block_is_truncated():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "customer_supplier_table-0",
                "usage": "customer_supplier_table",
                "text": (
                    "前五名客户销售额 49,019.50 万元，占年度销售总额 30.46%；"
                    "公司前五名客户 √适用 □不适用"
                ),
            }
        ],
    }
    metrics = build_required_business_metrics(evidence_pack, raw_text=YINGJIXIN_CUSTOMER_SUPPLIER_TEXT)

    customer = metrics["customer_concentration"]
    assert customer["top_five_percentage"]["text"] == "30.46%"
    assert customer["largest_amount"]["text"] == "10,835.52"
    assert customer["largest_percentage"]["text"] == "6.73%"


def test_sales_mode_merges_rows_from_multiple_candidate_blocks():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "segment_margin_table-0",
                "usage": "segment_margin_table",
                "text": (
                    "主营业务分销售模式情况 "
                    "分销售模式 营业收入 营业成本 毛利率 营业收入比上年增减 营业成本比上年增减 毛利率比上年增减 "
                    "经销 3,609,911,439.81 1,746,401,174.88 51.62% 20.37% 21.03% -0.27%"
                ),
            },
            {
                "id": "segment_table-0",
                "usage": "segment_table",
                "text": (
                    "分销售模式 "
                    "经销 3,609,911,439.81 92.61% 2,999,043,790.63 89.60% 20.37% "
                    "直销 280,648,096.22 7.20% 347,939,330.03 10.40% -19.34%"
                ),
            },
        ],
    }
    metrics = build_required_business_metrics(evidence_pack)
    labels = {row["label"] for row in metrics["sales_mode_rows"]}
    assert {"经销", "直销"}.issubset(labels)


def test_region_and_sales_mode_rows_for_yingjixin():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    domestic = _find_row(metrics["region_rows"], "国内销售")
    assert domestic is not None
    assert domestic["revenue"]["unit"] == "万元"
    assert domestic["revenue"]["text"] == "156,161.40" or domestic["revenue"]["normalized"] == "156161.40万元"
    assert domestic["revenue_yoy"]["text"] == "15.11%"

    overseas = _find_row(metrics["region_rows"], "国外销售")
    assert overseas is not None
    assert overseas["revenue_yoy"]["text"] == "-11.30%"

    direct = _find_row(metrics["sales_mode_rows"], "直销模式")
    assert direct is not None
    assert direct["revenue_yoy"]["text"] == "5.83%"

    distributor = _find_row(metrics["sales_mode_rows"], "经销模式")
    assert distributor is not None
    assert distributor["revenue_yoy"]["text"] == "15.67%"


def test_region_and_sales_mode_rows_do_not_include_product_rows():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    assert {row["label"] for row in metrics["region_rows"]} == {"国内销售", "国外销售"}
    assert {row["label"] for row in metrics["sales_mode_rows"]} == {"直销模式", "经销模式"}


def test_combined_margin_block_splits_segment_region_and_sales_mode_cleanly():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "segment_margin_table-0",
                "usage": "segment_margin_table",
                "text": SHENGBANG_COMBINED_SEGMENT_MARGIN_TEXT,
            }
        ],
    }
    metrics = build_required_business_metrics(evidence_pack)

    assert {row["label"] for row in metrics["segment_rows"]} == {"信号链产品", "电源管理产品"}
    assert {row["label"] for row in metrics["region_rows"]} == {"大陆", "香港"}
    assert {row["label"] for row in metrics["sales_mode_rows"]} == {"经销"}
    mainland = _find_row(metrics["region_rows"], "大陆")
    assert mainland["revenue_yoy"]["text"] == "9.18%"


def test_extracts_actual_three_line_inventory_table_for_zhongjian():
    evidence_pack = build_periodic_report_evidence_pack(ZHONGJIAN_ACTUAL_INVENTORY_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=ZHONGJIAN_ACTUAL_INVENTORY_TEXT,
    )

    row = _find_row(metrics["inventory_rows"], "整体")
    assert row is not None
    assert row["quantity_unit"] == "KG"
    assert row["sales_volume"]["text"] == "315,326.80"
    assert row["production_volume"]["text"] == "388,277.44"
    assert row["inventory_volume"]["text"] == "94,938.11"
    assert row["inventory_yoy"]["text"] == "150.95%"


def test_extracts_actual_three_line_inventory_table_for_shengbang():
    evidence_pack = build_periodic_report_evidence_pack(SHENGBANG_ACTUAL_INVENTORY_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=SHENGBANG_ACTUAL_INVENTORY_TEXT,
    )

    row = _find_row(metrics["inventory_rows"], "整体")
    assert row is not None
    assert row["quantity_unit"] == "颗"
    assert row["sales_volume"]["text"] == "7,862,728,539"
    assert row["production_volume"]["text"] == "8,610,305,518"
    assert row["inventory_volume"]["text"] == "2,593,446,280"
    assert row["inventory_yoy"]["text"] == "41.04%"


def test_extracts_actual_zhongjian_customer_supplier_concentration():
    evidence_pack = build_periodic_report_evidence_pack(ZHONGJIAN_ACTUAL_CUSTOMER_SUPPLIER_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=ZHONGJIAN_ACTUAL_CUSTOMER_SUPPLIER_TEXT,
    )

    customer = metrics["customer_concentration"]
    assert customer["present"]
    assert customer["top_five_amount"]["normalized"] == "84107.55万元"
    assert customer["top_five_percentage"]["text"] == "99.42%"
    assert customer["largest_amount"]["normalized"] == "74016.95万元"
    assert customer["largest_percentage"]["text"] == "87.49%"
    assert customer["related_party_percentage"]["text"] == "1.54%"

    supplier = metrics["supplier_concentration"]
    assert supplier["present"]
    assert supplier["top_five_amount"]["normalized"] == "35750.91万元"
    assert supplier["top_five_percentage"]["text"] == "41.58%"
    assert supplier["largest_percentage"]["text"] == "15.48%"


def test_extracts_actual_shengbang_customer_supplier_concentration():
    evidence_pack = build_periodic_report_evidence_pack(SHENGBANG_ACTUAL_CUSTOMER_SUPPLIER_TEXT)
    metrics = build_required_business_metrics(
        evidence_pack,
        raw_text=SHENGBANG_ACTUAL_CUSTOMER_SUPPLIER_TEXT,
    )

    customer = metrics["customer_concentration"]
    assert customer["present"]
    assert customer["top_five_amount"]["normalized"] == "129125.80万元"
    assert customer["top_five_percentage"]["text"] == "33.13%"
    assert customer["largest_amount"]["normalized"] == "30359.25万元"
    assert customer["largest_percentage"]["text"] == "7.79%"

    supplier = metrics["supplier_concentration"]
    assert supplier["present"]
    assert supplier["top_five_amount"]["normalized"] == "218067.61万元"
    assert supplier["top_five_percentage"]["text"] == "90.99%"
    assert supplier["largest_amount"]["normalized"] == "94900.00万元"
    assert supplier["largest_percentage"]["text"] == "39.61%"


def test_rejects_hk_english_concentration_year_false_positive():
    evidence_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "blocks": [
            {
                "id": "customer_supplier_table-0",
                "usage": "customer_supplier_table",
                "text": (
                    "Black Sesame International Holding Limited 2025 Annual Report "
                    "1 Customer A 31, 2025 Notes to the Consolidated Financial Statements"
                ),
            },
            {
                "id": "supplier_concentration_table-0",
                "usage": "supplier_concentration_table",
                "text": (
                    "Black Sesame International Holding Limited 2025 Annual Report "
                    "1 Supplier A 31, 2025 Notes to the Consolidated Financial Statements"
                ),
            },
        ],
    }

    metrics = build_required_business_metrics(evidence_pack)

    assert not metrics["customer_concentration"]["present"]
    assert not metrics["supplier_concentration"]["present"]
    assert "2025%" not in metrics["normalized_values"]


def test_required_metrics_preserve_original_units_and_normalized_values():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)
    values = set(metrics["normalized_values"])

    assert "34.47%" in values
    assert "12.44%" in values
    assert "106204.12万元" in values or "1062041200元" in values
    assert "30.46%" in values
    assert "51.80%" in values

    power = _find_row(metrics["segment_rows"], "电源管理类")
    assert power["revenue"]["unit"] == "万元" or "元" in power["revenue"]["unit"]


def test_normalized_values_canonical_form():
    assert _normalize_numeric("1,062,041,234.54 元") == "1062041234.54元"
    assert _normalize_numeric("30.46 %") == "30.46%"
    assert _normalize_numeric("增加 2.6 4 个百分点") == "+2.64pct"
    assert _normalize_numeric("减少 1.7 2 个百分点") == "-1.72pct"
    assert _normalize_numeric("-4.84") == "-4.84"


def test_required_metrics_handles_jina_spaced_numbers():
    evidence_pack = build_periodic_report_evidence_pack(ZHONGJIAN_CUSTOMER_TEXT)
    metrics = build_required_business_metrics(evidence_pack, raw_text=ZHONGJIAN_CUSTOMER_TEXT)
    customer = metrics["customer_concentration"]
    assert customer["present"]
    assert "99.42%" in metrics["normalized_values"]
    assert "87.49%" in metrics["normalized_values"]


def test_required_metrics_handles_broken_product_names():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)
    labels = {row["label"] for row in metrics["segment_rows"]}
    assert "数模混合 SoC 类" in labels
    labels_inv = {row["label"] for row in metrics["inventory_rows"]}
    assert "数模混合 SoC 类" in labels_inv


def test_required_metrics_table_presence_when_header_found_but_no_rows():
    text = "主营业务分产品情况\n分产品 营业收入 营业成本 毛利率（%）"
    evidence_pack = build_periodic_report_evidence_pack(text)
    metrics = build_required_business_metrics(evidence_pack)
    assert metrics["tables"]["segment_margin"]["present"]
    assert metrics["tables"]["segment_margin"]["row_count"] == 0


def test_table_presence_row_block_id_consistency():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    for table_key in ("segment_margin", "inventory", "customer_supplier"):
        table = metrics["tables"][table_key]
        row_ids = set()
        if table_key == "segment_margin":
            for row in metrics["segment_rows"]:
                row_ids.add(row["source_block_id"])
        elif table_key == "region":
            for row in metrics["region_rows"]:
                row_ids.add(row["source_block_id"])
        elif table_key == "sales_mode":
            for row in metrics["sales_mode_rows"]:
                row_ids.add(row["source_block_id"])
        elif table_key == "inventory":
            for row in metrics["inventory_rows"]:
                row_ids.add(row["source_block_id"])
        elif table_key == "customer_supplier":
            if metrics["customer_concentration"].get("source_block_id"):
                row_ids.add(metrics["customer_concentration"]["source_block_id"])
            if metrics["supplier_concentration"].get("source_block_id"):
                row_ids.add(metrics["supplier_concentration"]["source_block_id"])
        assert row_ids == set(table["source_block_ids"]), f"{table_key} ids mismatch"


def test_source_excerpt_bounded():
    evidence_pack = build_periodic_report_evidence_pack(YINGJIXIN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)
    for row in metrics["segment_rows"]:
        assert len(row["source_excerpt"]) <= 300
    for row in metrics["inventory_rows"]:
        assert len(row["source_excerpt"]) <= 300


def test_zhongjian_required_metrics_regression():
    evidence_pack = build_periodic_report_evidence_pack(ZHONGJIAN_FULL_REPORT)
    metrics = build_required_business_metrics(evidence_pack)

    carbon = _find_row(metrics["segment_rows"], "碳纤维")
    assert carbon is not None
    assert carbon["revenue"]["text"] == "443,494,353.42"
    assert carbon["gross_margin"]["text"] == "55.21%"

    fabric = _find_row(metrics["segment_rows"], "碳纤维织物")
    assert fabric is not None
    assert fabric["gross_margin"]["text"] == "75.46%"

    assert metrics["customer_concentration"]["present"]
    assert "99.42%" in metrics["normalized_values"]
    assert "87.49%" in metrics["normalized_values"]


def test_raw_text_fallback_extracts_metrics():
    """Fallback must work when evidence pack has no relevant blocks."""
    text = """
主营业务分产品情况
分产品 营业收入 营业成本 毛利率（%） 营业收入比上年增减（%） 营业成本比上年增减（%） 毛利率比上年增减（%）
电源管理类 1,062,041,234.54 695,954,120.28 34.47 12.44 8.09 增加2.64个百分点
"""
    evidence_pack = build_periodic_report_evidence_pack(text)
    # Force relevant blocks to empty by constructing minimal pack, but keep schema.
    minimal_pack = {
        "schema_version": "periodic_report_evidence_pack.v1",
        "report_type": "annual_report",
        "audit_status": "audited",
        "blocks": [],
    }
    metrics = build_required_business_metrics(minimal_pack, raw_text=text)
    power = _find_row(metrics["segment_rows"], "电源管理类")
    assert power is not None
    assert power["revenue"]["text"] == "1,062,041,234.54"
