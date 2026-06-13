"""Tests for source_credit module."""

import pytest

from scripts.utils.source_credit import SourceCreditResult, score_source_credit


# ---------------------------------------------------------------------------
# Happy path: source tiers
# ---------------------------------------------------------------------------

def test_black_sesame_official_url():
    result = score_source_credit(url="https://www.blacksesame.com/zh/list_10/972.html")
    assert result.source_type == "company_official"
    assert result.source_credit >= 80
    assert result.verification_status == "primary_source"
    assert result.knowledge_eligible is True
    assert result.report_eligible is True
    assert result.source_domain == "blacksesame.com"


def test_hkex_announcement_url():
    result = score_source_credit(url="https://www.hkexnews.hk/listedco/listconews/sehk/2026/0101/2026010100001_c.htm")
    assert result.source_type == "exchange_announcement"
    assert result.source_credit >= 95
    assert result.verification_status == "primary_source"
    assert result.knowledge_eligible is True
    assert result.report_eligible is True
    assert result.source_domain == "hkexnews.hk"


def test_sse_announcement_url():
    result = score_source_credit(url="http://www.sse.com.cn/assortment/stock/list/info/announcement/")
    assert result.source_type == "exchange_announcement"
    assert result.source_credit >= 95
    assert result.source_domain == "sse.com.cn"


def test_szse_announcement_url():
    result = score_source_credit(url="https://www.szse.cn/disclosure/listed/bulletinDetail/index.html?id=123")
    assert result.source_type == "exchange_announcement"
    assert result.source_domain == "szse.cn"


def test_cninfo_announcement_url():
    result = score_source_credit(url="http://www.cninfo.com.cn/new/disclosure/detail?plate=szse&stockCode=000001")
    assert result.source_type == "exchange_announcement"
    assert result.source_domain == "cninfo.com.cn"


def test_company_ir_path():
    result = score_source_credit(url="https://www.example.com/ir/annual-report.html")
    assert result.source_type == "company_ir"
    assert result.source_credit >= 80
    assert result.verification_status == "primary_source"
    assert result.knowledge_eligible is True
    assert result.report_eligible is True
    assert result.source_domain == "example.com"


def test_company_ir_raw_source_type():
    result = score_source_credit(
        url="https://www.example.com/news.html",
        raw={"source_type": "ir"},
    )
    assert result.source_type == "company_ir"
    assert result.source_domain == "example.com"


def test_broker_research_by_platform():
    result = score_source_credit(source_platform="研报")
    assert result.source_type == "broker_research"
    assert result.source_credit == 72
    assert result.verification_status == "professional_analysis"


def test_broker_research_by_raw_source_type():
    result = score_source_credit(raw={"source_type": "research"})
    assert result.source_type == "broker_research"


def test_broker_research_by_raw_broker_research_source_type():
    result = score_source_credit(raw={"source_type": "broker_research"})
    assert result.source_type == "broker_research"


def test_broker_research_by_raw_report_source_type():
    result = score_source_credit(raw={"source_type": "report"})
    assert result.source_type == "broker_research"


def test_broker_research_by_institution():
    result = score_source_credit(raw={"institution": "国信证券"})
    assert result.source_type == "broker_research"


def test_mainstream_media_eastmoney():
    result = score_source_credit(url="https://finance.eastmoney.com/a/202601011234567890.html")
    assert result.source_type == "mainstream_media"
    assert result.source_credit == 65
    assert result.verification_status == "secondary_source"


def test_mainstream_media_sina_finance():
    result = score_source_credit(url="https://finance.sina.com.cn/stock/relnews/cn/2026-01-01/doc-xyz123.shtml")
    assert result.source_type == "mainstream_media"


def test_mainstream_media_stcn():
    result = score_source_credit(url="https://www.stcn.com/article/123.html")
    assert result.source_type == "mainstream_media"


def test_mainstream_media_yicai():
    result = score_source_credit(url="https://www.yicai.com/news/101234567.html")
    assert result.source_type == "mainstream_media"


def test_mainstream_media_caixin():
    result = score_source_credit(url="https://www.caixin.com/2026-01-01/1234567.html")
    assert result.source_type == "mainstream_media"


def test_industry_media_36kr():
    result = score_source_credit(url="https://36kr.com/p/1234567890")
    assert result.source_type == "industry_media"
    assert result.source_credit == 55
    assert result.verification_status == "secondary_source"
    assert result.knowledge_eligible is True
    assert result.report_eligible is False


def test_industry_media_jiemian():
    result = score_source_credit(url="https://www.jiemian.com/article/1234567.html")
    assert result.source_type == "industry_media"


def test_industry_media_leiphone():
    result = score_source_credit(url="https://www.leiphone.com/category/intelligentcar/123456")
    assert result.source_type == "industry_media"


def test_social_zhihu():
    result = score_source_credit(url="https://www.zhihu.com/question/123456789")
    assert result.source_type == "social_discussion"
    assert result.source_credit == 35
    assert result.verification_status == "market_opinion"
    assert result.knowledge_eligible is True
    assert result.report_eligible is False


def test_social_zhihu_subdomain():
    result = score_source_credit(url="https://zhuanlan.zhihu.com/p/123456789")
    assert result.source_type == "social_discussion"
    assert result.source_domain == "zhuanlan.zhihu.com"


def test_social_xiaohongshu_short_link_domain():
    result = score_source_credit(url="https://xhslink.com/a/example")
    assert result.source_type == "social_discussion"


def test_social_xueqiu_by_platform():
    result = score_source_credit(source_platform="雪球")
    assert result.source_type == "social_discussion"


def test_social_twitter_by_platform():
    result = score_source_credit(source_platform="Twitter")
    assert result.source_type == "social_discussion"


def test_social_x_alias():
    result = score_source_credit(source_platform="X")
    assert result.source_type == "social_discussion"


def test_social_reddit_alias():
    result = score_source_credit(source_platform="reddit")
    assert result.source_type == "social_discussion"


def test_social_bilibili_alias():
    result = score_source_credit(source_platform="Bilibili")
    assert result.source_type == "social_discussion"


def test_social_weibo_alias():
    result = score_source_credit(source_platform="微博")
    assert result.source_type == "social_discussion"


def test_social_xiaohongshu_alias():
    result = score_source_credit(source_platform="小红书")
    assert result.source_type == "social_discussion"


def test_unknown_web_with_url():
    result = score_source_credit(url="https://www.example-random-blog.com/post/123")
    assert result.source_type == "unknown_web"
    assert result.source_credit == 30
    assert result.verification_status == "unverified"
    assert result.knowledge_eligible is True
    assert result.report_eligible is False


def test_missing_source_no_url_no_platform_no_raw():
    result = score_source_credit()
    assert result.source_type == "missing_source"
    assert result.source_credit == 10
    assert result.verification_status == "unverified"
    assert result.knowledge_eligible is False
    assert result.report_eligible is False


def test_missing_source_only_author():
    result = score_source_credit(author="张三")
    assert result.source_type == "missing_source"


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------

def test_url_normalization_strips_www():
    result = score_source_credit(url="https://blacksesame.com/zh/list_10/972.html")
    assert result.source_domain == "blacksesame.com"
    assert result.source_type == "company_official"


def test_url_normalization_without_scheme():
    result = score_source_credit(url="blacksesame.com/zh/list_10/972.html")
    assert result.source_domain == "blacksesame.com"
    assert result.source_type == "company_official"


def test_url_normalization_ignores_query_and_fragment():
    result = score_source_credit(url="https://www.blacksesame.com/zh/list_10/972.html?utm=foo#section")
    assert result.source_domain == "blacksesame.com"
    assert result.source_type == "company_official"


def test_url_normalization_lowercase_host():
    result = score_source_credit(url="https://WWW.BLACKSESAME.COM/zh/")
    assert result.source_domain == "blacksesame.com"


def test_url_normalization_cn_domain():
    result = score_source_credit(url="https://www.blacksesame.com.cn/zh/")
    assert result.source_domain == "blacksesame.com.cn"
    assert result.source_type == "company_official"


def test_malformed_url_returns_empty_domain():
    result = score_source_credit(url="not a url at all")
    assert result.source_domain == ""
    assert result.source_type == "missing_source"


# ---------------------------------------------------------------------------
# Conflict / priority tests
# ---------------------------------------------------------------------------

def test_url_wins_over_social_platform():
    """A social platform label must not downgrade an official company URL."""
    result = score_source_credit(
        url="https://www.blacksesame.com/zh/list_9/977.html",
        source_platform="知乎",
    )
    assert result.source_type == "company_official"
    assert result.source_domain == "blacksesame.com"


def test_raw_source_type_ir_wins_over_plain_url():
    """Raw source_type='ir' should identify investor relations even on plain URL."""
    result = score_source_credit(
        url="https://www.example.com/news/press-release.html",
        raw={"source_type": "ir"},
    )
    assert result.source_type == "company_ir"


def test_is_official_flag_does_not_upgrade_unknown_domain():
    """Official flag should only help when domain is already known official."""
    result = score_source_credit(
        url="https://random-unknown-site.com/post",
        raw={"is_official": True},
    )
    assert result.source_type == "unknown_web"
    assert result.source_credit == 30


def test_empty_url_with_social_platform_is_social():
    """No URL but explicit social platform should still be classified as social."""
    result = score_source_credit(
        url="",
        source_platform="知乎",
    )
    assert result.source_type == "social_discussion"


# ---------------------------------------------------------------------------
# Metadata / reason tests
# ---------------------------------------------------------------------------

def test_user_provided_url_on_official_domain_adds_reason():
    result = score_source_credit(
        url="https://www.blacksesame.com/zh/list_10/972.html",
        raw={"user_provided_url": True},
    )
    assert result.source_type == "company_official"
    assert any("用户显式提供" in reason for reason in result.credit_reasons)


def test_user_provided_url_does_not_boost_unknown_domain():
    result = score_source_credit(
        url="https://random-blog.com/post",
        raw={"user_provided_url": True},
    )
    assert result.source_type == "unknown_web"
    assert result.source_credit == 30
    assert not any("用户显式提供" in reason for reason in result.credit_reasons)


def test_company_official_reasons_list_not_empty():
    result = score_source_credit(url="https://www.blacksesame.com/zh/")
    assert len(result.credit_reasons) >= 1
    assert result.credit_reasons[0].startswith("公司官网")


def test_result_is_frozen_dataclass():
    result = score_source_credit()
    with pytest.raises(Exception):
        result.source_credit = 99


# ---------------------------------------------------------------------------
# Adapter integration (contract)
# ---------------------------------------------------------------------------

def test_adapter_includes_source_credit_in_extra():
    from scripts.utils.source_adapter import AgentReachAdapter

    raw = {
        "_platform": "web",
        "title": "Title: 测试标题",
        "content": "测试内容",
        "url": "https://www.blacksesame.com/zh/list_10/972.html",
        "author": "",
        "publish_time": "2026-06-01",
        "user_provided_url": True,
    }
    item = AgentReachAdapter.to_synthesis_item(raw)

    assert "raw" in item.extra
    assert item.extra["source_type"] == "company_official"
    assert item.extra["source_domain"] == "blacksesame.com"
    assert item.extra["source_credit"] >= 80
    assert item.extra["verification_status"] == "primary_source"
    assert isinstance(item.extra["credit_reasons"], list)
    assert item.extra["knowledge_eligible"] is True
    assert item.extra["report_eligible"] is True


def test_adapter_preserves_existing_extra_raw():
    from scripts.utils.source_adapter import AgentReachAdapter

    raw = {
        "_platform": "web",
        "title": "t",
        "url": "https://www.zhihu.com/question/123",
    }
    item = AgentReachAdapter.to_synthesis_item(raw)
    assert item.extra["raw"] is raw
    assert item.extra["source_type"] == "social_discussion"


def test_adapter_missing_source_fields_still_adapts():
    from scripts.utils.source_adapter import AgentReachAdapter

    raw = {
        "platform": "twitter",
        "title": None,
        "content": None,
        "author": None,
        "url": None,
        "publish_time": None,
    }
    item = AgentReachAdapter.to_synthesis_item(raw)
    assert item.extra["source_type"] == "missing_source"
    assert item.extra["source_credit"] == 10
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["report_eligible"] is False
    assert "raw" in item.extra
