"""Tests that Agent-Reach source expansion remains scoped to the target stock."""

import json
from pathlib import Path


CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "stocks.json"


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_only_target_stock_has_agent_reach_enabled():
    stocks = _load_config()
    enabled_stocks = []
    for stock in stocks:
        ar = stock.get("agent_reach", {})
        if ar.get("enabled", False):
            enabled_stocks.append(stock.get("name"))

    assert enabled_stocks == ["黑芝麻智能"], f"Only 黑芝麻智能 should have agent_reach.enabled=true, got {enabled_stocks}"


def test_target_stock_has_web_urls_and_official_domains():
    stocks = _load_config()
    target = next((s for s in stocks if s.get("name") == "黑芝麻智能"), None)
    assert target is not None
    ar = target.get("agent_reach", {})
    assert ar.get("enabled") is True
    assert len(ar.get("web_urls", [])) > 0
    assert "blacksesame.com" in ar.get("official_domains", [])


def test_other_stocks_do_not_have_agent_reach_urls():
    stocks = _load_config()
    for stock in stocks:
        if stock.get("name") == "黑芝麻智能":
            continue
        ar = stock.get("agent_reach", {})
        assert not ar.get("web_urls", []), f"{stock.get('name')} must not have agent_reach.web_urls"
        assert not ar.get("official_domains", []), f"{stock.get('name')} must not have agent_reach.official_domains"
