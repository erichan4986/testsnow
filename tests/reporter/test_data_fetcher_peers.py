from unittest.mock import patch

from scripts.utils.reporter import data_fetcher


def test_fetch_competitor_metrics_prefers_config_peers_and_codes():
    seen_codes = []

    def fake_financial(code):
        seen_codes.append(code)
        return {"gross_margin": 50.0}

    stock_config = {
        "competitors": ["紫光国微", "安路科技"],
        "peer_codes": {"紫光国微": "002049", "安路科技": "688107"},
    }

    with patch.object(data_fetcher, "load_manual_financials", return_value=None), patch.object(
        data_fetcher, "fetch_financial_abstract", side_effect=fake_financial
    ), patch.object(data_fetcher, "fetch_tencent_quote", return_value=None), patch.object(
        data_fetcher, "fetch_consensus_eps", return_value=None
    ):
        result = data_fetcher.fetch_competitor_metrics(
            "复旦微电",
            {"复旦微电": "688385"},
            stock_config=stock_config,
        )

    assert list(result) == ["复旦微电", "紫光国微", "安路科技"]
    assert seen_codes == ["688385", "002049", "688107"]


def test_fetch_competitor_metrics_falls_back_to_constants_for_existing_stock():
    with patch.object(data_fetcher, "load_manual_financials", return_value=None), patch.object(
        data_fetcher, "fetch_financial_abstract", return_value={}
    ), patch.object(data_fetcher, "fetch_tencent_quote", return_value=None), patch.object(
        data_fetcher, "fetch_consensus_eps", return_value=None
    ):
        result = data_fetcher.fetch_competitor_metrics("圣邦股份", {"圣邦股份": "300661"})

    assert "圣邦股份" in result
    assert "杰华特" in result


def test_competitor_metrics_table_uses_config_peer_order():
    stock_config = {"competitors": ["紫光国微", "安路科技"]}
    metrics = {
        "复旦微电": {"gross_margin": 60, "mcap": 360},
        "紫光国微": {"gross_margin": 65, "mcap": 600},
        "安路科技": {"gross_margin": 55, "mcap": 200},
    }

    table = data_fetcher.competitor_metrics_table("复旦微电", metrics, stock_config=stock_config)

    assert "| **复旦微电** |" in table
    assert "| 紫光国微 |" in table
    assert "| 安路科技 |" in table
    assert "思瑞浦" not in table

