from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from structured_financial_history import (
    build_structured_financial_history_cache,
    read_structured_financial_history_source_points,
    write_structured_financial_history_cache,
)
from periodic_report_structured_facts import filing_facts_to_core_facts


def test_a_share_admits_only_fy_rows_and_exact_fields() -> None:
    pack = build_structured_financial_history_cache(
        stock_code="300308",
        stock_name="中际旭创",
        market="A",
        fetched_at="2026-07-29T12:00:00+08:00",
        provider_rows={
            "profit": [
                {
                    "REPORT_DATE": "2025-12-31",
                    "TOTAL_OPERATE_INCOME": "38240000000",
                    "OPERATE_INCOME": "1",
                    "PARENT_NETPROFIT": "10100000000",
                },
                {
                    "REPORT_DATE": "2025-09-30",
                    "TOTAL_OPERATE_INCOME": "99999999999",
                    "PARENT_NETPROFIT": "99999999999",
                },
            ],
            "cashflow": [
                {"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "8900000000"},
                {"REPORT_DATE": "2025-09-30", "NETCASH_OPERATE": "99999999999"},
            ],
        },
    )

    assert pack["schema_version"] == "structured_financial_history_cache.v1"
    assert len(pack["records"]) == 1
    record = pack["records"][0]
    assert record["report_year"] == 2025
    assert record["currency"] == "CNY"
    assert record["metrics"]["revenue"] == {
        "value": "38240000000",
        "source_field": "TOTAL_OPERATE_INCOME",
    }
    assert record["metrics"]["net_profit"]["source_field"] == "PARENT_NETPROFIT"
    assert record["metrics"]["operating_cash_flow"]["source_field"] == "NETCASH_OPERATE"
    assert all(row["row_hash"] for row in record["source_rows"])
    assert "99999999999" not in json.dumps(pack, ensure_ascii=False)


def test_hk_requires_explicit_fy_cny_and_exact_cashflow_label() -> None:
    pack = build_structured_financial_history_cache(
        stock_code="02533",
        stock_name="黑芝麻智能",
        market="HK",
        provider_rows={
            "profit": [
                {
                    "REPORT_DATE": "2025-12-31",
                    "REPORT_TYPE": "FY",
                    "CURRENCY": "CNY",
                    "OPERATE_INCOME": "420000000",
                    "HOLDER_PROFIT": "-1800000000",
                },
                {
                    "REPORT_DATE": "2024-12-31",
                    "REPORT_TYPE": "FY",
                    "CURRENCY": "HKD",
                    "OPERATE_INCOME": "1",
                    "HOLDER_PROFIT": "1",
                },
            ],
            "cashflow": [
                {
                    "REPORT_DATE": "2025-12-31",
                    "REPORT_TYPE": "FY",
                    "CURRENCY": "CNY",
                    "ITEM_NAME": "经营活动产生的现金流量净额",
                    "AMOUNT": "-230000000",
                },
                {
                    "REPORT_DATE": "2025-12-31",
                    "REPORT_TYPE": "FY",
                    "CURRENCY": "CNY",
                    "ITEM_NAME": "经营活动现金流",
                    "AMOUNT": "99999999999",
                },
            ],
        },
    )

    assert [row["report_year"] for row in pack["records"]] == [2025]
    metrics = pack["records"][0]["metrics"]
    assert metrics["operating_cash_flow"] == {
        "value": "-230000000",
        "source_field": "AMOUNT",
    }
    assert any(row["code"] == "unsupported_reporting_currency" for row in pack["diagnostics"])
    assert "99999999999" not in json.dumps(pack, ensure_ascii=False)


def test_hk_admits_eastmoney_operating_business_net_cash_label() -> None:
    pack = build_structured_financial_history_cache(
        stock_code="02533",
        stock_name="黑芝麻智能",
        market="HK",
        provider_rows={
            "profit": [],
            "cashflow": [{
                "REPORT_DATE": "2025-12-31",
                "REPORT_TYPE": "年报",
                "CURRENCY": "人民币",
                "ITEM_NAME": "经营业务现金净额",
                "AMOUNT": "-985373000",
            }],
        },
    )

    assert pack["records"][0]["metrics"]["operating_cash_flow"] == {
        "value": "-985373000",
        "source_field": "AMOUNT",
    }


def test_admits_direct_a_and_hk_annual_gross_margin() -> None:
    a_pack = build_structured_financial_history_cache(
        stock_code="688385", stock_name="复旦微电", market="A",
        provider_rows={
            "profit": [{"REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "100", "PARENT_NETPROFIT": "20"}],
            "cashflow": [{"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "30"}],
            "indicator": [{"指标": "毛利率", "20251231": "41.23", "20250930": "99.99"}],
        },
    )
    hk_pack = build_structured_financial_history_cache(
        stock_code="02533", stock_name="黑芝麻智能", market="HK",
        provider_rows={
            "profit": [{
                "REPORT_DATE": "2025-12-31", "REPORT_TYPE": "FY", "CURRENCY": "CNY",
                "OPERATE_INCOME": "100", "HOLDER_PROFIT": "20", "GROSS_PROFIT_RATIO": "37.50",
            }],
            "cashflow": [],
        },
    )

    assert a_pack["records"][0]["metrics"]["gross_margin"] == {
        "value": "41.23", "source_field": "20251231", "origin": "direct",
    }
    assert hk_pack["records"][0]["metrics"]["gross_margin"] == {
        "value": "37.50", "source_field": "GROSS_PROFIT_RATIO", "origin": "direct",
    }
    assert "99.99" not in json.dumps(a_pack, ensure_ascii=False)


def test_derives_gross_margin_from_same_row_in_fixed_order() -> None:
    from_profit = build_structured_financial_history_cache(
        stock_code="300001", stock_name="测试股份", market="A",
        provider_rows={
            "profit": [{
                "REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200",
                "PARENT_NETPROFIT": "20", "GROSS_PROFIT": "80", "OPERATE_COST": "150",
            }],
            "cashflow": [],
        },
    )
    from_cost = build_structured_financial_history_cache(
        stock_code="300001", stock_name="测试股份", market="A",
        provider_rows={
            "profit": [{
                "REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200",
                "PARENT_NETPROFIT": "20", "OPERATE_COST": "150",
            }],
            "cashflow": [],
        },
    )

    assert from_profit["records"][0]["metrics"]["gross_margin"] == {
        "value": "40.00", "source_field": "derived", "origin": "derived",
        "formula_version": "gross_margin.v1",
        "input_fields": ["GROSS_PROFIT", "TOTAL_OPERATE_INCOME"],
    }
    assert from_cost["records"][0]["metrics"]["gross_margin"]["value"] == "25.00"
    assert from_cost["records"][0]["metrics"]["gross_margin"]["input_fields"] == [
        "OPERATE_COST", "TOTAL_OPERATE_INCOME",
    ]


def test_gross_margin_rejects_total_cost_split_rows_and_direct_conflict() -> None:
    cases = [
        {
            "profit": [{
                "REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200",
                "PARENT_NETPROFIT": "20", "TOTAL_OPERATE_COST": "150",
            }],
            "cashflow": [],
        },
        {
            "profit": [
                {"REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200", "PARENT_NETPROFIT": "20"},
                {"REPORT_DATE": "2025-12-31", "OPERATE_COST": "150"},
            ],
            "cashflow": [],
        },
    ]
    for rows in cases:
        pack = build_structured_financial_history_cache(
            stock_code="300001", stock_name="测试股份", market="A", provider_rows=rows,
        )
        assert "gross_margin" not in pack["records"][0]["metrics"]
        assert not any(row["code"] == "missing_metric" and row.get("metric_key") == "gross_margin" for row in pack["diagnostics"])

    conflict = build_structured_financial_history_cache(
        stock_code="300001", stock_name="测试股份", market="A",
        provider_rows={
            "profit": [{
                "REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200",
                "PARENT_NETPROFIT": "20", "GROSS_PROFIT": "80",
            }],
            "cashflow": [],
            "indicator": [
                {"指标": "毛利率", "20251231": "40.00"},
                {"指标": "毛利率", "20251231": "41.00"},
            ],
        },
    )
    assert "gross_margin" not in conflict["records"][0]["metrics"]
    assert any(row["code"] == "conflicting_period_values" and row.get("metric_key") == "gross_margin" for row in conflict["diagnostics"])


def test_cache_hash_is_stable_and_identical_refresh_is_byte_preserving(tmp_path: Path) -> None:
    kwargs = {
        "stock_code": "688385",
        "stock_name": "复旦微电",
        "market": "A",
        "provider_rows": {
            "profit": [{
                "REPORT_DATE": "2025-12-31",
                "TOTAL_OPERATE_INCOME": "2400000000",
                "PARENT_NETPROFIT": "800000000",
            }],
            "cashflow": [{"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "600000000"}],
        },
    }
    first = build_structured_financial_history_cache(
        **kwargs, fetched_at="2026-07-29T10:00:00+08:00"
    )
    second = build_structured_financial_history_cache(
        **kwargs, fetched_at="2026-07-29T11:00:00+08:00"
    )
    path = tmp_path / "688385.json"

    assert first["data_hash"] == second["data_hash"]
    assert write_structured_financial_history_cache(path, first) is True
    original = path.read_bytes()
    assert write_structured_financial_history_cache(path, second) is False
    assert path.read_bytes() == original


def test_cache_is_deterministic_when_equal_provider_rows_change_order() -> None:
    profit_rows = [
        {
            "REPORT_DATE": "2025-12-31",
            "TOTAL_OPERATE_INCOME": "100",
            "PARENT_NETPROFIT": "20",
        },
        {
            "REPORT_DATE": "2025-12-31",
            "OPERATE_INCOME": "100",
            "PARENT_NETPROFIT": "20",
        },
    ]
    kwargs = {
        "stock_code": "300001",
        "stock_name": "测试股份",
        "market": "A",
        "provider_rows": {
            "profit": profit_rows,
            "cashflow": [
                {"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "30"}
            ],
        },
    }

    first = build_structured_financial_history_cache(**kwargs)
    kwargs["provider_rows"]["profit"] = list(reversed(profit_rows))
    second = build_structured_financial_history_cache(**kwargs)

    assert first["records"] == second["records"]
    assert first["data_hash"] == second["data_hash"]
    assert first["records"][0]["metrics"]["revenue"]["source_field"] == (
        "TOTAL_OPERATE_INCOME"
    )


def test_reader_rejects_hash_valid_record_with_missing_required_field(tmp_path: Path) -> None:
    pack = build_structured_financial_history_cache(
        stock_code="300001",
        stock_name="测试股份",
        market="A",
        provider_rows={
            "profit": [{
                "REPORT_DATE": "2025-12-31",
                "TOTAL_OPERATE_INCOME": "100",
                "PARENT_NETPROFIT": "20",
            }],
            "cashflow": [
                {"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "30"}
            ],
        },
    )
    del pack["records"][0]["report_year"]
    payload = {
        key: pack.get(key)
        for key in ("stock_code", "stock_name", "market", "provider", "records")
    }
    pack["data_hash"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    path = tmp_path / "300001.json"
    path.write_text(json.dumps(pack), encoding="utf-8")

    points, ratios, diagnostics = read_structured_financial_history_source_points(
        path, expected_stock_code="300001"
    )

    assert points == []
    assert ratios == []
    assert diagnostics == [{"code": "invalid_history_cache_record"}]


def test_reader_validates_identity_and_emits_compact_source_points(tmp_path: Path) -> None:
    pack = build_structured_financial_history_cache(
        stock_code="300308",
        stock_name="中际旭创",
        market="A",
        provider_rows={
            "profit": [{
                "REPORT_DATE": "2025-12-31",
                "TOTAL_OPERATE_INCOME": "38240000000",
                "PARENT_NETPROFIT": "10100000000",
            }],
            "cashflow": [{"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "8900000000"}],
        },
    )
    path = tmp_path / "300308.json"
    write_structured_financial_history_cache(path, pack)

    points, ratios, diagnostics = read_structured_financial_history_source_points(
        path, expected_stock_code="300308"
    )

    assert diagnostics == []
    assert ratios == []
    assert {row["metric_key"] for row in points} == {
        "revenue", "net_profit", "operating_cash_flow"
    }
    revenue = next(row for row in points if row["metric_key"] == "revenue")
    assert revenue["source_type"] == "structured_financial_api_fact"
    assert revenue["normalized_value"] == "3824000.00万元"
    assert revenue["fact_id"] == "periodic:300308:2025:annual:revenue"
    assert len(revenue["source_excerpt_hash"]) == 64
    assert len(revenue["source_block_hash"]) == 64
    assert filing_facts_to_core_facts(points) == []

    bad_points, bad_ratios, bad_diagnostics = read_structured_financial_history_source_points(
        path, expected_stock_code="688385"
    )
    assert bad_points == []
    assert bad_ratios == []
    assert bad_diagnostics == [{"code": "history_cache_stock_mismatch"}]


def test_reader_separates_direct_and_derived_gross_margin_points(tmp_path: Path) -> None:
    pack = build_structured_financial_history_cache(
        stock_code="300001", stock_name="测试股份", market="A",
        provider_rows={
            "profit": [
                {"REPORT_DATE": "2024-12-31", "TOTAL_OPERATE_INCOME": "200", "PARENT_NETPROFIT": "20", "GROSS_PROFIT": "80"},
                {"REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200", "PARENT_NETPROFIT": "20"},
            ],
            "cashflow": [],
            "indicator": [{"指标": "毛利率", "20251231": "42.50"}],
        },
    )
    path = tmp_path / "300001.json"
    write_structured_financial_history_cache(path, pack)

    amounts, ratios, diagnostics = read_structured_financial_history_source_points(
        path, expected_stock_code="300001",
    )

    assert {row["metric_key"] for row in amounts} == {"revenue", "net_profit"}
    assert [(row["report_year"], row["unit"], row["numeric_value"], row["origin"]) for row in ratios] == [
        (2024, "pct", "40.00", "derived"), (2025, "pct", "42.50", "direct"),
    ]
    assert ratios[0]["formula_version"] == "gross_margin.v1"
    assert ratios[0]["input_fields"] == ["GROSS_PROFIT", "TOTAL_OPERATE_INCOME"]
    assert {row.get("metric_key") for row in diagnostics} == {"operating_cash_flow"}


def test_reader_rejects_malformed_optional_gross_margin_cell(tmp_path: Path) -> None:
    pack = build_structured_financial_history_cache(
        stock_code="300001", stock_name="测试股份", market="A",
        provider_rows={"profit": [{
            "REPORT_DATE": "2025-12-31", "TOTAL_OPERATE_INCOME": "200",
            "PARENT_NETPROFIT": "20", "GROSS_PROFIT": "80",
        }], "cashflow": []},
    )
    del pack["records"][0]["metrics"]["gross_margin"]["origin"]
    pack["data_hash"] = hashlib.sha256(json.dumps({
        key: pack.get(key) for key in ("stock_code", "stock_name", "market", "provider", "records")
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "300001.json"
    path.write_text(json.dumps(pack), encoding="utf-8")

    assert read_structured_financial_history_source_points(
        path, expected_stock_code="300001",
    ) == ([], [], [{"code": "invalid_history_cache_record"}])


def test_refresh_entry_resolves_config_and_preserves_cache_on_empty_provider(tmp_path: Path, monkeypatch) -> None:
    from scripts import refresh_structured_financial_history as refresh

    config = tmp_path / "stocks.json"
    config.write_text(json.dumps([{"name": "复旦微电", "code": "688385"}]), encoding="utf-8")
    cache_dir = tmp_path / "cache"
    rows = {
        "profit": [{
            "REPORT_DATE": "2025-12-31",
            "TOTAL_OPERATE_INCOME": "2400000000",
            "PARENT_NETPROFIT": "800000000",
        }],
        "cashflow": [{"REPORT_DATE": "2025-12-31", "NETCASH_OPERATE": "600000000"}],
    }
    monkeypatch.setattr(refresh, "fetch_structured_financial_history_rows", lambda code: rows)

    assert refresh.main([
        "--stock", "复旦微电", "--config", str(config), "--cache-dir", str(cache_dir),
    ]) == 0
    path = cache_dir / "688385.json"
    original = path.read_bytes()

    monkeypatch.setattr(
        refresh, "fetch_structured_financial_history_rows",
        lambda code: {"profit": [], "cashflow": []},
    )
    assert refresh.main([
        "--stock", "688385", "--config", str(config), "--cache-dir", str(cache_dir),
    ]) == 2
    assert path.read_bytes() == original
