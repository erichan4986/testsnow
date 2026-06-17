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
