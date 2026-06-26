import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import pytest

from wechat_targeted_discovery import (
    CATEGORIES,
    DEFAULT_TARGET_ACCOUNTS,
    PRIORITY,
    add_preview_fields,
    build_search_keywords,
    classify,
    deduplicate,
    discover_articles,
    load_auth_key,
    load_stock_config,
    ts_to_date,
)


@pytest.fixture
def stock_config():
    return {
        "name": "测试股份",
        "code": "123456",
        "industry": "半导体",
        "source_intake": {
            "a_stock": {
                "eastmoney_global_news": {
                    "keywords": ["模拟芯片", "AI芯片", "算力"]
                }
            },
            "iwencai_industry_research": {
                "queries": ["半导体 深度报告", "模拟芯片 国产替代"]
            },
        },
    }


def test_load_stock_config_by_name(tmp_path):
    cfg = [{"name": "圣邦股份", "code": "300661", "industry": "半导体"}]
    path = tmp_path / "stocks.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    assert load_stock_config("圣邦股份", path)["code"] == "300661"
    assert load_stock_config("300661", path)["name"] == "圣邦股份"


def test_load_stock_config_missing_returns_empty(tmp_path):
    path = tmp_path / "stocks.json"
    path.write_text(json.dumps([]), encoding="utf-8")
    assert load_stock_config("不存在", path) == {}


def test_build_search_keywords_uses_config_and_extra(stock_config):
    kws = build_search_keywords(stock_config, extra_keywords=["订单", "涨价"])
    assert "测试股份" in kws
    assert "123456" in kws
    assert "模拟芯片" in kws
    assert "AI芯片" in kws
    assert "算力" in kws
    assert "半导体" in kws
    assert "深度报告" in kws
    assert "订单" in kws
    assert "涨价" in kws


def test_ts_to_date_from_seconds():
    # 2026-06-26 00:00:00 UTC / local approximate
    ts = int(date(2026, 6, 26).strftime("%s"))
    assert ts_to_date(ts) == date(2026, 6, 26)


def test_ts_to_date_returns_none_for_bad_values():
    assert ts_to_date(0) is None
    assert ts_to_date("") is None
    assert ts_to_date("abc") is None


class TestClassify:
    def test_high_quality_analysis_by_depth_indicator(self):
        cat, reason = classify("圣邦股份 深度解析：竞争格局与估值", "", "半导体行业观察", "300661")
        assert cat == "high_quality_analysis"
        assert "深度" in reason

    def test_customer_order_or_design_win(self):
        cat, reason = classify("圣邦股份拿下大客户订单", "", "集微网", "300661")
        assert cat == "customer_order_or_design_win"

    def test_capacity_supply_chain_signal(self):
        cat, _ = classify("圣邦股份扩产爬坡，产能紧缺", "", "半导体产业纵横", "300661")
        assert cat == "capacity_supply_chain_signal"

    def test_industry_cycle_price_signal(self):
        cat, _ = classify("模拟芯片涨价，行业景气上行", "", "电子工程专辑", "300661")
        assert cat == "industry_cycle_price_signal"

    def test_certification_policy_standard(self):
        cat, _ = classify("圣邦股份通过AEC-Q100车规认证", "", "汽车电子", "300661")
        assert cat == "certification_policy_standard"

    def test_earnings_financial_context(self):
        cat, _ = classify("圣邦股份2025年净利润大增", "", "财报号", "300661")
        assert cat == "earnings_financial_context"

    def test_product_or_event_signal(self):
        cat, _ = classify("圣邦股份发布新品电源管理芯片", "", "产品号", "300661")
        assert cat == "product_or_event_signal"

    def test_capital_market_context(self):
        cat, _ = classify("圣邦股份市值突破千亿", "", "资本号", "300661")
        assert cat == "capital_market_context"

    def test_capital_market_terms_beat_industry_price_terms(self):
        cat, _ = classify(
            "华为苹果也要涨价！国内又一MCU公司涨价！港交所圣邦微等6家同日招股,\"03661.HK\"拟本月上市",
            "",
            "集微网",
            "300661",
        )
        assert cat == "capital_market_context"

    def test_drop_recruiting(self):
        cat, _ = classify("圣邦股份2026届校园招聘启动", "", "HR", "300661")
        assert cat == "drop"

    def test_drop_festival(self):
        cat, _ = classify("圣邦股份祝您新春快乐", "", "官方", "300661")
        assert cat == "drop"

    def test_drop_unrelated(self):
        cat, _ = classify("某无关新闻标题", "", "其他", "300661")
        assert cat == "drop"

    def test_financial_review_is_not_dropped_by_generic_review_word(self):
        cat, _ = classify("中际旭创年度业绩回顾：净利润高增", "", "海陆清风", "300308")
        assert cat == "earnings_financial_context"

    def test_analysis_media_and_design_win_can_be_high_quality(self):
        cat, _ = classify("圣邦股份拿下车企定点，产业链格局生变", "", "半导体行业观察", "300661")
        assert cat == "high_quality_analysis"


def test_add_preview_fields_sets_isolation():
    item = add_preview_fields({"title": "t"})
    assert item["quality_action"] == "preview_only"
    assert item["knowledge_eligible"] is False
    assert item["synthesis_eligible"] is False
    assert item["scoring_eligible"] is False
    assert item["risk_score_eligible"] is False


def test_deduplicate_removes_url_and_title_duplicates():
    candidates = [
        {"title": "重复标题", "url": "https://mp.weixin.qq.com/s/A", "digest": "d1", "account": "a1", "publish_date": "2026-01-01"},
        {"title": "重复标题", "url": "https://mp.weixin.qq.com/s/B", "digest": "d2", "account": "a2", "publish_date": "2026-01-02"},
        {"title": "另一标题", "url": "https://mp.weixin.qq.com/s/C", "digest": "d3", "account": "a3", "publish_date": "2026-01-03"},
    ]
    result = deduplicate(candidates)
    assert result["unique_count"] == 2
    assert result["duplicate_count"] == 1
    assert len(result["items"]) == 2


def test_deduplicate_prefers_authoritative_account():
    # Two duplicates; authoritative account should win.
    candidates = [
        {"title": "标题", "url": "https://mp.weixin.qq.com/s/A", "digest": "d", "account": "小代理", "publish_date": "2026-01-01"},
        {"title": "标题", "url": "https://mp.weixin.qq.com/s/A", "digest": "更长更详细的摘要内容", "account": "半导体行业观察", "publish_date": "2026-01-02"},
    ]
    result = deduplicate(candidates)
    assert result["unique_count"] == 1
    assert result["items"][0]["account"] == "半导体行业观察"


def test_deduplicate_counts_classification():
    candidates = [
        {"title": "深度研报", "url": "https://mp.weixin.qq.com/s/A", "digest": "", "account": "a", "publish_date": "2026-01-01"},
        {"title": "新品发布", "url": "https://mp.weixin.qq.com/s/B", "digest": "", "account": "a", "publish_date": "2026-01-01"},
    ]
    result = deduplicate(candidates)
    assert result["counts"]["high_quality_analysis"] == 1
    assert result["counts"]["product_or_event_signal"] == 1


def test_load_auth_key_reads_env_and_does_not_leak(tmp_path):
    env = tmp_path / ".env"
    env.write_text("WECHAT_EXPORTER_AUTH_KEY=secret-xyz\n", encoding="utf-8")
    key = load_auth_key(env)
    assert key == "secret-xyz"


def test_load_auth_key_missing_raises(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=value\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_auth_key(env)


class RecordingWechatDiscoveryClient:
    def __init__(self):
        self.searched_keywords = []

    def search_accounts(self, keyword):
        self.searched_keywords.append(keyword)
        return {"list": []}

    def list_articles(self, fakeid, keyword="", page=1):
        return {"articles": []}


def test_discover_articles_appends_extra_accounts_to_default_targets(stock_config):
    client = RecordingWechatDiscoveryClient()
    discover_articles(
        client,
        stock_config,
        date(2025, 12, 28),
        extra_accounts=["自定义行业号"],
        delay_seconds=0,
    )

    assert DEFAULT_TARGET_ACCOUNTS[0] in client.searched_keywords
    assert "自定义行业号" in client.searched_keywords


def test_categories_include_required_set():
    required = {
        "high_quality_analysis",
        "customer_order_or_design_win",
        "capacity_supply_chain_signal",
        "industry_cycle_price_signal",
        "certification_policy_standard",
        "earnings_financial_context",
        "product_or_event_signal",
        "capital_market_context",
        "drop",
        "duplicate",
    }
    assert set(CATEGORIES) == required
    assert PRIORITY["high_quality_analysis"] < PRIORITY["product_or_event_signal"]
    assert PRIORITY["drop"] == max(PRIORITY.values())
