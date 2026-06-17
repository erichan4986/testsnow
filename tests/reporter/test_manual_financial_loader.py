from pathlib import Path

from scripts.utils.reporter.manual_financial_loader import load_manual_financials


def test_load_manual_financials_from_csv_by_stock_name(tmp_path):
    manual_dir = tmp_path / "manual_financials"
    manual_dir.mkdir()
    (manual_dir / "黑芝麻智能_financials.csv").write_text(
        "\n".join([
            "report_date,report_type,currency,revenue,revenue_yoy,gross_margin,net_profit,net_profit_yoy,roe,basic_eps,source",
            "2025-12-31,年报,HKD,822328000,73.4,41,-1773000000,-15.2,-126.5,-2.4,Wind",
        ]),
        encoding="utf-8",
    )

    result = load_manual_financials("黑芝麻智能", raw_dir=tmp_path)

    assert result is not None
    assert result["report_date"] == "2025-12-31"
    assert result["date_type"] == "年报"
    assert result["currency"] == "HKD"
    assert result["revenue"] == 822328000
    assert result["revenue_yoy"] == 73.4
    assert result["gross_margin"] == 41
    assert result["net_profit"] == -1773000000
    assert result["source"] == "manual_financials:Wind"


def test_load_manual_financials_from_csv_by_code_picks_latest_report(tmp_path):
    manual_dir = tmp_path / "manual_financials"
    manual_dir.mkdir()
    (manual_dir / "02533_financials.csv").write_text(
        "\n".join([
            "报告日期,报告类型,币种,营业收入,营业收入同比,毛利率,归母净利润,来源",
            "2024-12-31,年报,HKD,474000000,12.1,24.5,-1500000000,Wind",
            "2025-12-31,年报,HKD,822328000,73.4,41,-1773000000,Wind",
        ]),
        encoding="utf-8",
    )

    result = load_manual_financials("02533", raw_dir=tmp_path)

    assert result is not None
    assert result["report_date"] == "2025-12-31"
    assert result["revenue"] == 822328000
    assert result["gross_margin"] == 41
