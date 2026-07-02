"""Tests for a_stock_source_intake helper.

All tests use mocking to avoid real network calls and to verify lazy import
behavior. No test should import akshare at module scope.
"""

import sys
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import source_adapter
from source_adapter import SynthesisItem


def test_module_does_not_import_akshare_at_top_level():
    """Importing the helper must not trigger an akshare import."""
    import a_stock_source_intake as helper

    assert "akshare" not in helper.__dict__
    assert helper.__name__ == "a_stock_source_intake"


def test_disabled_config_returns_empty_status():
    from a_stock_source_intake import collect_a_stock_source_items

    result = collect_a_stock_source_items(
        stock_name="中简科技",
        stock_code="300777",
        config={"enabled": False},
    )
    assert result["status"] == "disabled"
    assert result["items"] == []
    assert result["source_statuses"]["cninfo_announcements"]["status"] == "disabled"
    assert result["source_statuses"]["eastmoney_stock_news"]["status"] == "disabled"
    assert result["source_statuses"]["eastmoney_research_reports"]["status"] == "disabled"


def test_cninfo_adapter_passes_market_沪深京():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2026年第一季度报告",
                "公告时间": "2026-04-23 00:00:00",
                "公告链接": "http://www.cninfo.com.cn/a/1",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    items = _adapt_cninfo_announcements(
        stock_code="300777",
        source_config={"enabled": True, "lookback_days": 365, "max_items": 5},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    fake_ak.stock_zh_a_disclosure_report_cninfo.assert_called_once()
    call_kwargs = fake_ak.stock_zh_a_disclosure_report_cninfo.call_args.kwargs
    assert call_kwargs.get("symbol") == "300777"
    assert call_kwargs.get("market") == "沪深京"
    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "公告"
    assert item.extra["source_credit"] == 95
    assert item.extra["source_type"] == "exchange_announcement"
    assert item.extra["source_domain"] == "cninfo.com.cn"
    assert item.extra["verification_status"] == "confirmed_fact"
    assert item.extra["knowledge_eligible"] is True
    assert item.extra["report_eligible"] is True


def test_cninfo_adapter_tolerates_alternative_column_names():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["标题", "公告日期", "链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "标题": "中简科技2026年第一季度报告",
                "公告日期": "2026-04-23",
                "链接": "http://www.cninfo.com.cn/a/1",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    items = _adapt_cninfo_announcements(
        stock_code="300777",
        source_config={"enabled": True, "lookback_days": 365, "max_items": 5},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert len(items) == 1
    assert items[0].title == "中简科技2026年第一季度报告"
    assert items[0].publish_time == "2026-04-23"


def test_cninfo_adapter_filters_categories_and_caps_items():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 3
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2025年年度报告",
                "公告时间": "2026-04-20 00:00:00",
                "公告链接": "http://cninfo.com.cn/a/annual",
            },
        ),
        (
            1,
            {
                "公告标题": "中简科技2026年第一季度报告",
                "公告时间": "2026-04-23 00:00:00",
                "公告链接": "http://cninfo.com.cn/a/q1",
            },
        ),
        (
            2,
            {
                "公告标题": "中简科技关于召开股东大会的通知",
                "公告时间": "2026-04-25 00:00:00",
                "公告链接": "http://cninfo.com.cn/a/meeting",
            },
        ),
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    items = _adapt_cninfo_announcements(
        stock_code="300777",
        source_config={
            "enabled": True,
            "lookback_days": 365,
            "max_items": 2,
            "categories": ["年报", "季报"],
        },
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert len(items) == 2
    assert all("报告" in i.title for i in items)


def test_cninfo_adapter_can_read_short_detail_content_via_jina():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2026年第一季度业绩预告",
                "公告时间": "2026-04-15 18:22:28",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225106812&announcementTime=2026-04-15 18:22:28",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    mock_response = MagicMock()
    mock_response.read.return_value = (
        "Title: 1225106812.PDF\n\n"
        "报告期内，客户对公司部分产品的需求量阶段性减少导致发货暂时减少，"
        "其中收入下降约 50%-60%。研发费用同比增长约 175%-185%。"
    ).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        items = _adapt_cninfo_announcements(
            stock_code="300777",
            source_config={
                "enabled": True,
                "lookback_days": 365,
                "max_items": 5,
                "read_detail_content": True,
                "detail_content_categories": ["业绩预告", "季度报告"],
                "max_detail_items": 2,
            },
            stock_name="中简科技",
            ak_module=fake_ak,
        )

    assert len(items) == 1
    assert "收入下降约 50%-60%" in items[0].content
    assert "研发费用同比增长约 175%-185%" in items[0].content
    assert items[0].extra["detail_content_status"] == "ok"
    assert mock_urlopen.call_args.args[0].full_url.startswith("https://r.jina.ai/http://www.cninfo.com.cn/")
    assert "%20" in mock_urlopen.call_args.args[0].full_url


def test_cninfo_adapter_does_not_read_long_annual_report_detail_by_default():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2025年年度报告",
                "公告时间": "2026-04-15 18:22:28",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    with patch("urllib.request.urlopen") as mock_urlopen:
        items = _adapt_cninfo_announcements(
            stock_code="300777",
            source_config={
                "enabled": True,
                "lookback_days": 365,
                "max_items": 5,
                "read_detail_content": True,
                "detail_content_categories": ["业绩预告", "季度报告"],
                "max_detail_items": 2,
            },
            stock_name="中简科技",
            ak_module=fake_ak,
        )

    assert len(items) == 1
    assert items[0].content == "中简科技2025年年度报告"
    assert items[0].extra["detail_content_status"] == "skipped"
    mock_urlopen.assert_not_called()


def test_cninfo_periodic_extraction_reads_annual_report_with_explicit_config():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2025年年度报告",
                "公告时间": "2026-04-15 00:00:00",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    report_text = (
        "中简科技2025年年度报告\n"
        "第三节 管理层讨论与分析\n"
        "报告期内，公司围绕航空航天高性能碳纤维需求推进产业化，营业收入同比下降12.3%。\n"
        "第十节 财务报告\n"
        "审计意见类型 标准的无保留意见\n"
        "经营活动产生的现金流量净额为正。"
    )
    mock_response = MagicMock()
    mock_response.read.return_value = report_text.encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        items = _adapt_cninfo_announcements(
            stock_code="300777",
            source_config={
                "enabled": True,
                "lookback_days": 365,
                "max_items": 5,
                "read_detail_content": True,
                "detail_content_categories": ["业绩预告"],
                "periodic_report_extraction": {
                    "enabled": True,
                    "max_reports": 1,
                    "max_chars": 120000,
                    "max_total_chars": 120000,
                    "industry": "hardtech",
                },
            },
            stock_name="中简科技",
            ak_module=fake_ak,
        )

    assert mock_urlopen.called
    original_items = [item for item in items if item.extra["source_type"] == "exchange_announcement"]
    excerpt_items = [item for item in items if item.extra["source_type"] == "periodic_report_excerpt"]
    assert len(original_items) == 1
    assert excerpt_items
    assert all(item.extra["source_credit"] == 75 for item in excerpt_items)
    assert all(item.extra["verification_status"] != "confirmed_fact" for item in excerpt_items)
    assert all(item.extra.get("periodic_report_excerpt_id") for item in excerpt_items)
    assert all(item.extra.get("periodic_report_schema_version") == "periodic_report_extractor.v1" for item in excerpt_items)
    assert all("periodic_report_not_extracted" in item.extra for item in excerpt_items)


def test_periodic_extraction_import_is_not_shadowed_by_scripts_cli(monkeypatch):
    import a_stock_source_intake as helper

    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    monkeypatch.syspath_prepend(str(scripts_dir))

    result = helper._extract_periodic_report_result(
        (
            "中简科技2025年年度报告\n"
            "第三节 管理层讨论与分析\n"
            "报告期内，公司围绕航空航天高性能碳纤维需求推进产业化，营业收入同比下降12.3%。\n"
            "第十节 财务报告\n"
            "审计意见类型 标准的无保留意见\n"
        ),
        {"periodic_report_extraction": {"industry": "hardtech"}},
    )

    assert result["schema_version"] == "periodic_report_extractor.v1"
    assert result["items"]


def test_cninfo_periodic_extraction_does_not_read_quarterly_report_when_detail_disabled():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2026年第一季度报告",
                "公告时间": "2026-04-23 00:00:00",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225145344",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    with patch("urllib.request.urlopen") as mock_urlopen:
        items = _adapt_cninfo_announcements(
            stock_code="300777",
            source_config={
                "enabled": True,
                "lookback_days": 365,
                "max_items": 5,
                "read_detail_content": False,
                "periodic_report_extraction": {"enabled": True},
            },
            stock_name="中简科技",
            ak_module=fake_ak,
        )

    assert len(items) == 1
    assert items[0].extra["source_type"] == "exchange_announcement"
    assert items[0].content == "中简科技2026年第一季度报告"
    mock_urlopen.assert_not_called()


def test_cninfo_periodic_extraction_skips_annual_report_summary():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2025年年度报告摘要",
                "公告时间": "2026-04-15 00:00:00",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000001",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    with patch("urllib.request.urlopen") as mock_urlopen:
        items = _adapt_cninfo_announcements(
            stock_code="300777",
            source_config={
                "enabled": True,
                "lookback_days": 365,
                "max_items": 5,
                "read_detail_content": False,
                "periodic_report_extraction": {"enabled": True},
            },
            stock_name="中简科技",
            ak_module=fake_ak,
        )

    assert len(items) == 1
    assert items[0].extra["source_type"] == "exchange_announcement"
    mock_urlopen.assert_not_called()


def test_cninfo_periodic_extraction_skips_schema_mismatch(monkeypatch):
    import a_stock_source_intake as helper
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["公告标题", "公告时间", "公告链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "公告标题": "中简科技2025年年度报告",
                "公告时间": "2026-04-15 00:00:00",
                "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
            },
        )
    ]
    fake_ak.stock_zh_a_disclosure_report_cninfo.return_value = fake_df

    mock_response = MagicMock()
    mock_response.read.return_value = "中简科技2025年年度报告 第三节 管理层讨论与分析".encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)
    monkeypatch.setattr(
        helper,
        "_extract_periodic_report_result",
        lambda text, config: {"schema_version": "unexpected.v0", "items": [{"usage": "management_view"}]},
    )

    with patch("urllib.request.urlopen", return_value=mock_response):
        items = _adapt_cninfo_announcements(
            stock_code="300777",
            source_config={
                "enabled": True,
                "lookback_days": 365,
                "max_items": 5,
                "periodic_report_extraction": {"enabled": True},
            },
            stock_name="中简科技",
            ak_module=fake_ak,
        )

    assert len(items) == 1
    assert items[0].extra["source_type"] == "exchange_announcement"
    assert items[0].extra["periodic_report_extraction_status"] == "schema_mismatch"


def test_cninfo_adapter_returns_error_status_on_exception():
    from a_stock_source_intake import _adapt_cninfo_announcements

    fake_ak = MagicMock()
    fake_ak.stock_zh_a_disclosure_report_cninfo.side_effect = RuntimeError("cninfo boom")

    result = _adapt_cninfo_announcements(
        stock_code="300777",
        source_config={"enabled": True},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "cninfo boom" in result["error"]


def test_eastmoney_stock_news_adapter_marks_professional_observation():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    class FakeResponse:
        text = (
            'jQuery_news({"result":{"cmsArticleWebOld":[{'
            '"title":"<em>中简科技</em>：新产品研发进展顺利",'
            '"content":"公司表示当前研发投入持续增加。",'
            '"date":"2026-06-10 10:00:00",'
            '"mediaName":"东方财富",'
            '"url":"https://finance.eastmoney.com/a/202606101234.html"'
            "}]}})"
        )

    calls = []

    def fake_em_get(url, params=None, headers=None, timeout=15):
        calls.append((url, params, headers, timeout))
        return FakeResponse()

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "provider": "eastmoney_raw"},
        stock_name="中简科技",
        em_get=fake_em_get,
    )

    assert len(items) == 1
    item = items[0]
    assert calls[0][0] == "https://search-api-web.eastmoney.com/search/jsonp"
    assert "cmsArticleWebOld" in calls[0][1]["param"]
    assert item.title == "中简科技：新产品研发进展顺利"
    assert item.source_platform == "新闻"
    assert item.extra["source_credit"] == 65
    assert item.extra["source_type"] == "mainstream_media"
    assert item.extra["source_domain"] == "eastmoney.com"
    assert item.extra["verification_status"] == "secondary_source"
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["report_eligible"] is True


def test_eastmoney_stock_news_requires_stock_name_or_code_match():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    class FakeResponse:
        text = (
            'jQuery_news({"result":{"cmsArticleWebOld":[{'
            '"title":"某 unrelated 公司发布新品",'
            '"content":"与目标公司无关。",'
            '"date":"2026-06-10 10:00:00",'
            '"mediaName":"东方财富",'
            '"url":"https://finance.eastmoney.com/a/202606101234.html"'
            "}]}})"
        )

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "provider": "eastmoney_raw"},
        stock_name="中简科技",
        em_get=lambda *args, **kwargs: FakeResponse(),
    )

    assert items == []


def test_eastmoney_stock_news_filters_to_lookback_days():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    class FakeResponse:
        text = (
            'jQuery_news({"result":{"cmsArticleWebOld":['
            '{"title":"中简科技：近期新闻","content":"中简科技近期公告相关报道。",'
            '"date":"2026-06-10 10:00:00","mediaName":"东方财富",'
            '"url":"https://finance.eastmoney.com/a/recent.html"},'
            '{"title":"中简科技：旧新闻","content":"中简科技较早报道。",'
            '"date":"2026-05-01 10:00:00","mediaName":"东方财富",'
            '"url":"https://finance.eastmoney.com/a/old.html"}'
            "]}})"
        )

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "lookback_days": 30, "provider": "eastmoney_raw"},
        stock_name="中简科技",
        today=date(2026, 6, 24),
        em_get=lambda *args, **kwargs: FakeResponse(),
    )

    assert [item.title for item in items] == ["中简科技：近期新闻"]


def test_eastmoney_stock_news_falls_back_to_stock_name_keyword_when_code_empty():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    class EmptyResponse:
        text = 'jQuery_news({"result":{"cmsArticleWebOld":[]}})'

    class NameResponse:
        text = (
            'jQuery_news({"result":{"cmsArticleWebOld":[{'
            '"title":"中简科技：名称搜索命中新闻",'
            '"content":"中简科技相关报道。",'
            '"date":"2026-06-10 10:00:00",'
            '"mediaName":"东方财富",'
            '"url":"https://finance.eastmoney.com/a/name.html"'
            "}]}})"
        )

    calls = []

    def fake_em_get(url, params=None, headers=None, timeout=15):
        calls.append(params["param"])
        return EmptyResponse() if len(calls) == 1 else NameResponse()

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "lookback_days": 30, "provider": "eastmoney_raw"},
        stock_name="中简科技",
        today=date(2026, 6, 24),
        em_get=fake_em_get,
    )

    assert len(calls) == 2
    assert '"keyword":"300777"' in calls[0]
    assert '"keyword":"中简科技"' in calls[1]
    assert [item.title for item in items] == ["中简科技：名称搜索命中新闻"]


def test_eastmoney_stock_news_defaults_to_akshare_stock_news_em():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.__len__.return_value = 2
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "新闻标题": "中简科技：新产品获得客户验证",
                "新闻内容": "中简科技相关产品研发进展顺利。",
                "发布时间": "2026-06-10 10:00:00",
                "文章来源": "财联社",
                "新闻链接": "https://finance.eastmoney.com/a/recent.html",
            },
        ),
        (
            1,
            {
                "新闻标题": "其他公司新闻",
                "新闻内容": "与目标公司无关。",
                "发布时间": "2026-06-10 10:00:00",
                "文章来源": "财联社",
                "新闻链接": "https://finance.eastmoney.com/a/other.html",
            },
        ),
    ]
    fake_ak.stock_news_em.return_value = fake_df

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "lookback_days": 30},
        stock_name="中简科技",
        today=date(2026, 6, 24),
        ak_module=fake_ak,
    )

    fake_ak.stock_news_em.assert_called_once_with(symbol="300777")
    assert len(items) == 1
    assert items[0].title == "中简科技：新产品获得客户验证"
    assert items[0].extra["source_type"] == "mainstream_media"
    assert items[0].extra["source_domain"] == "eastmoney.com"
    assert items[0].extra["knowledge_eligible"] is False
    assert items[0].extra["report_eligible"] is True


def test_akshare_stock_news_filters_generic_list_articles():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.__len__.return_value = 3
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "新闻标题": "圣邦股份：确定H股发行价格为每股85.20港元",
                "新闻内容": "圣邦股份预计将于6月26日在港交所挂牌交易。",
                "发布时间": "2026-06-23 10:00:00",
                "文章来源": "证券时报",
                "新闻链接": "https://finance.eastmoney.com/a/direct.html",
            },
        ),
        (
            1,
            {
                "新闻标题": "汽车芯片概念涨2.28%，主力资金净流入64股",
                "新闻内容": "圣邦股份等个股出现在资金净流入名单中。",
                "发布时间": "2026-06-23 11:00:00",
                "文章来源": "证券时报",
                "新闻链接": "https://finance.eastmoney.com/a/list.html",
            },
        ),
        (
            2,
            {
                "新闻标题": "斥资78亿元！3天2板封测龙头拟建设高端先进封测工厂|盘后公告集锦",
                "新闻内容": "圣邦股份等公司公告被收录在集锦中。",
                "发布时间": "2026-06-23 12:00:00",
                "文章来源": "证券时报",
                "新闻链接": "https://finance.eastmoney.com/a/name-list.html",
            },
        ),
    ]
    fake_ak.stock_news_em.return_value = fake_df

    items = _adapt_eastmoney_stock_news(
        stock_code="300661",
        source_config={"enabled": True, "max_items": 5, "lookback_days": 30},
        stock_name="圣邦股份",
        today=date(2026, 6, 24),
        ak_module=fake_ak,
    )

    assert [item.title for item in items] == ["圣邦股份：确定H股发行价格为每股85.20港元"]


def test_eastmoney_global_news_filters_keywords_and_stays_out_of_knowledge():
    from a_stock_source_intake import _adapt_eastmoney_global_news

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.__len__.return_value = 3
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "标题": "高通将收购AI芯片初创公司",
                "摘要": "半导体行业并购事件。",
                "发布时间": "2026-06-24 19:59:36",
                "链接": "https://finance.eastmoney.com/a/ai-chip.html",
            },
        ),
        (
            1,
            {
                "标题": "普通宏观新闻",
                "摘要": "与关键词无关。",
                "发布时间": "2026-06-24 18:00:00",
                "链接": "https://finance.eastmoney.com/a/macro.html",
            },
        ),
        (
            2,
            {
                "标题": "旧机器人新闻",
                "摘要": "机器人产业事件。",
                "发布时间": "2026-05-01 09:00:00",
                "链接": "https://finance.eastmoney.com/a/old.html",
            },
        ),
    ]
    fake_ak.stock_info_global_em.return_value = fake_df

    items = _adapt_eastmoney_global_news(
        stock_code="300777",
        source_config={
            "enabled": True,
            "max_items": 5,
            "lookback_days": 30,
            "keywords": ["AI芯片", "机器人"],
        },
        stock_name="中简科技",
        today=date(2026, 6, 24),
        ak_module=fake_ak,
    )

    assert [item.title for item in items] == ["高通将收购AI芯片初创公司"]
    assert items[0].source_platform == "行业资讯"
    assert items[0].extra["source_type"] == "mainstream_media"
    assert items[0].extra["source_domain"] == "eastmoney.com"
    assert items[0].extra["knowledge_eligible"] is False
    assert items[0].extra["report_eligible"] is True
    assert items[0].extra["matched_keywords"] == ["AI芯片"]
    assert items[0].extra["relevance_class"] == "sector_background"
    assert items[0].extra["allowed_sections"] == ["4.1"]
    assert "4.3" not in items[0].extra["allowed_sections"]


def test_eastmoney_global_news_attaches_industry_chain_metadata_for_4_3():
    from a_stock_source_intake import _adapt_eastmoney_global_news

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "标题": "存储产品涨价带动晶圆厂产能紧张",
                "摘要": "市场关注存储扩产与晶圆厂排产变化。",
                "发布时间": "2026-06-24 19:59:36",
                "链接": "https://finance.eastmoney.com/a/memory-cis.html",
            },
        )
    ]
    fake_ak.stock_info_global_em.return_value = fake_df

    items = _adapt_eastmoney_global_news(
        stock_code="603501",
        source_config={
            "enabled": True,
            "max_items": 5,
            "lookback_days": 30,
            "keywords": ["存储产品涨价", "晶圆厂产能紧张"],
            "industry_relevance": {
                "products": ["CIS", "图像传感器"],
                "chain_rules": [
                    {
                        "chain_id": "memory_capacity_to_cis_pricing",
                        "target_product": "CIS",
                        "hops": [
                            {
                                "id": "memory_price",
                                "statement": "存储产品涨价",
                                "keywords": ["存储产品涨价"],
                                "requires_news_support": True,
                            },
                            {
                                "id": "wafer_capacity",
                                "statement": "上游晶圆厂产能紧张",
                                "keywords": ["晶圆厂产能紧张", "排产变化"],
                                "requires_news_support": True,
                            },
                            {
                                "id": "cis_capacity",
                                "statement": "CIS 排产可能被挤占",
                                "keywords": ["CIS", "图像传感器"],
                            },
                        ],
                    }
                ],
            },
        },
        stock_name="韦尔股份",
        today=date(2026, 6, 24),
        ak_module=fake_ak,
    )

    assert len(items) == 1
    assert items[0].extra["relevance_class"] == "industry_chain_relevant"
    assert "4.3" in items[0].extra["allowed_sections"]
    assert items[0].extra["relevance_chain"]["chain_id"] == "memory_capacity_to_cis_pricing"


def test_iwencai_industry_research_adapter_marks_display_only(monkeypatch):
    import a_stock_source_intake as helper

    def fake_preview(**kwargs):
        assert kwargs["api_key"] == "test-key"
        assert kwargs["queries"] == ["半导体 行业研究报告"]
        assert kwargs["recent_days"] == 90
        assert kwargs["fallback_days"] == 180
        assert kwargs["max_items_per_query"] == 2
        return {
            "queries": [
                {
                    "query": "半导体 行业研究报告",
                    "selected": [
                        {
                            "uid": "r1",
                            "title": "电子行业中期策略：半导体迎来发展新机遇",
                            "summary": "AI算力需求持续景气，半导体周期延续上行。",
                            "publish_date": "2026-06-23",
                            "organization": "中原证券",
                            "url": "https://ms.10jqka.com.cn/report/r1",
                            "score": 0.15,
                            "query": "半导体 行业研究报告",
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(helper, "_build_iwencai_industry_preview_summary", fake_preview)

    items = helper._adapt_iwencai_industry_research(
        stock_code="300661",
        source_config={
            "enabled": True,
            "api_key": "test-key",
            "queries": ["半导体 行业研究报告"],
            "recent_days": 90,
            "fallback_days": 180,
            "max_items_per_query": 2,
        },
        stock_name="圣邦股份",
        today=date(2026, 6, 24),
    )

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "行业研报"
    assert item.title == "电子行业中期策略：半导体迎来发展新机遇"
    assert "AI算力需求持续景气" in item.content
    assert item.extra["source_type"] == "industry_research"
    assert item.extra["source_credit"] == 70
    assert item.extra["verification_status"] == "professional_observation"
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["report_eligible"] is True
    assert item.extra["scoring_eligible"] is False
    assert item.extra["risk_score_eligible"] is False
    assert item.extra["iwencai_query"] == "半导体 行业研究报告"


def test_collect_includes_iwencai_industry_research_status(monkeypatch):
    import a_stock_source_intake as helper

    def fake_preview(**kwargs):
        return {
            "queries": [
                {
                    "query": "存储芯片 产业链 深度报告",
                    "selected": [
                        {
                            "uid": "r2",
                            "title": "存储行业深度报告：AI纪元，存赢未来",
                            "summary": "AI训练与推理驱动存储需求进入新周期。",
                            "publish_date": "2026-01-14",
                            "organization": "浙商证券",
                            "url": "https://ms.10jqka.com.cn/report/r2",
                            "score": 0.14,
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(helper, "_build_iwencai_industry_preview_summary", fake_preview)

    result = helper.collect_a_stock_source_items(
        stock_name="圣邦股份",
        stock_code="300661",
        config={
            "enabled": True,
            "a_stock": {
                "iwencai_industry_research": {
                    "enabled": True,
                    "api_key": "test-key",
                    "queries": ["存储芯片 产业链 深度报告"],
                }
            },
        },
        today=date(2026, 6, 24),
    )

    assert result["status"] == "ok"
    assert result["source_statuses"]["iwencai_industry_research"] == {
        "status": "ok",
        "count": 1,
        "error": "",
    }
    assert len(result["items"]) == 1
    assert result["items"][0].extra["source_type"] == "industry_research"
    assert result["items"][0].extra["knowledge_eligible"] is False


def test_eastmoney_research_reports_adapter_marks_professional_observation():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class FakeResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "中简科技2024Q3业绩点评：新旧更替，万象更新",
                        "publishDate": "2026-06-12",
                        "orgSName": "国信证券",
                        "infoCode": "ABC123",
                        "emRatingName": "买入",
                        "predictThisYearEps": 1.23,
                    }
                ],
                "TotalPage": 1,
            }

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        em_get=lambda *args, **kwargs: FakeResponse(),
    )

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "研报"
    assert item.extra["source_credit"] == 72
    assert item.extra["source_type"] == "broker_research"
    assert item.extra["verification_status"] == "professional_observation"
    assert item.extra["knowledge_eligible"] is True
    assert item.extra.get("rating") == "买入"
    assert item.extra.get("eps") == 1.23
    assert item.extra.get("institution") == "国信证券"


def test_eastmoney_research_reports_does_not_download_pdf_by_default(tmp_path):
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class ReportListResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "中简科技深度报告：产品进展加速",
                        "publishDate": "2026-06-12",
                        "orgSName": "国信证券",
                        "infoCode": "ABC123",
                    }
                ],
                "TotalPage": 1,
            }

    calls = []

    def fake_em_get(url, params=None, headers=None, timeout=30):
        calls.append(url)
        if url == "https://reportapi.eastmoney.com/report/list":
            return ReportListResponse()
        raise AssertionError("PDF URL should not be requested by default")

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "pdf_cache_dir": str(tmp_path)},
        stock_name="中简科技",
        em_get=fake_em_get,
    )

    assert len(items) == 1
    assert calls == ["https://reportapi.eastmoney.com/report/list"]
    assert "pdf_local_path" not in items[0].extra


def test_eastmoney_research_reports_downloads_pdf_when_enabled(tmp_path):
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    pdf_bytes = b"%PDF-1.4\n" + (b"x" * 2048)

    class ReportListResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "中简科技深度报告：产品进展加速",
                        "publishDate": "2026-06-12",
                        "orgSName": "国信证券",
                        "infoCode": "ABC123",
                    }
                ],
                "TotalPage": 1,
            }

    class PdfResponse:
        status_code = 200
        content = pdf_bytes

    def fake_em_get(url, params=None, headers=None, timeout=30):
        if url == "https://reportapi.eastmoney.com/report/list":
            return ReportListResponse()
        if url == "https://pdf.dfcfw.com/pdf/H3_ABC123_1.pdf":
            return PdfResponse()
        raise AssertionError(f"unexpected URL: {url}")

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={
            "enabled": True,
            "max_items": 5,
            "download_pdfs": True,
            "pdf_cache_dir": str(tmp_path),
        },
        stock_name="中简科技",
        em_get=fake_em_get,
    )

    assert len(items) == 1
    item = items[0]
    assert item.extra["pdf_download_status"] == "ok"
    assert item.extra["pdf_url"] == "https://pdf.dfcfw.com/pdf/H3_ABC123_1.pdf"
    assert item.extra["pdf_bytes"] == len(pdf_bytes)
    assert item.extra["pdf_sha256"]
    pdf_path = Path(item.extra["pdf_local_path"])
    assert pdf_path.parent == tmp_path
    assert pdf_path.read_bytes() == pdf_bytes


def test_eastmoney_research_reports_downloads_pdf_to_standard_stock_cache(tmp_path):
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    pdf_bytes = b"%PDF-1.4\n" + (b"x" * 2048)

    class ReportListResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "圣邦股份深度报告：产品平台扩张",
                        "publishDate": "2026-05-12",
                        "orgSName": "国信证券",
                        "infoCode": "SB123",
                    }
                ],
                "TotalPage": 1,
            }

    class PdfResponse:
        status_code = 200
        content = pdf_bytes

    def fake_em_get(url, params=None, headers=None, timeout=30):
        if url == "https://reportapi.eastmoney.com/report/list":
            return ReportListResponse()
        if url == "https://pdf.dfcfw.com/pdf/H3_SB123_1.pdf":
            return PdfResponse()
        raise AssertionError(f"unexpected URL: {url}")

    cache_root = tmp_path / "broker_research_reports"
    items = _adapt_eastmoney_research_reports(
        stock_code="300661",
        source_config={
            "enabled": True,
            "max_items": 5,
            "download_pdfs": True,
            "broker_research_cache_root": str(cache_root),
        },
        stock_name="圣邦股份",
        em_get=fake_em_get,
    )

    assert len(items) == 1
    item = items[0]
    pdf_path = Path(item.extra["pdf_local_path"])
    assert pdf_path.parent == cache_root / "圣邦股份_300661" / "_downloads"
    assert pdf_path.read_bytes() == pdf_bytes
    manifest_path = cache_root / "圣邦股份_300661" / "manifest.json"
    assert item.extra["pdf_cache_manifest_path"] == str(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "broker_research_cache_manifest.v1"
    assert manifest["stock_name"] == "圣邦股份"
    assert manifest["stock_code"] == "300661"
    assert len(manifest["reports"]) == 1
    report = manifest["reports"][0]
    assert report["title"] == "圣邦股份深度报告：产品平台扩张"
    assert report["institution"] == "国信证券"
    assert report["publish_time"] == "2026-05-12"
    assert report["url"] == "https://pdf.dfcfw.com/pdf/H3_SB123_1.pdf"
    assert report["path"] == str(pdf_path)
    assert report["bytes"] == len(pdf_bytes)
    assert report["sha256"]


def test_eastmoney_research_reports_keeps_item_when_pdf_download_fails(tmp_path):
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class ReportListResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "中简科技深度报告：产品进展加速",
                        "publishDate": "2026-06-12",
                        "orgSName": "国信证券",
                        "infoCode": "ABC123",
                    }
                ],
                "TotalPage": 1,
            }

    class PdfResponse:
        status_code = 403
        content = b""

    def fake_em_get(url, params=None, headers=None, timeout=30):
        if url == "https://reportapi.eastmoney.com/report/list":
            return ReportListResponse()
        return PdfResponse()

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={
            "enabled": True,
            "max_items": 5,
            "download_pdfs": True,
            "pdf_cache_dir": str(tmp_path),
        },
        stock_name="中简科技",
        em_get=fake_em_get,
    )

    assert len(items) == 1
    assert items[0].extra["pdf_download_status"] == "failed"
    assert "PDF HTTP 403" in items[0].extra["pdf_download_error"]
    assert "pdf_local_path" not in items[0].extra


def test_eastmoney_research_reports_uses_and_enforces_lookback_window():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class FakeResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "中简科技近期研报：产品进展加速",
                        "publishDate": "2026-06-05",
                        "orgSName": "华泰证券",
                        "infoCode": "RECENT",
                    },
                    {
                        "title": "中简科技旧研报：历史复盘",
                        "publishDate": "2026-04-01",
                        "orgSName": "华泰证券",
                        "infoCode": "OLD",
                    },
                ],
                "TotalPage": 1,
            }

    calls = []

    def fake_em_get(url, params=None, headers=None, timeout=30):
        calls.append((url, params, headers, timeout))
        return FakeResponse()

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "lookback_days": 30},
        stock_name="中简科技",
        today=date(2026, 6, 24),
        em_get=fake_em_get,
    )

    assert calls[0][1]["beginTime"] == "2026-05-25"
    assert calls[0][1]["endTime"] == "2026-06-24"
    assert [item.title for item in items] == ["中简科技近期研报：产品进展加速"]


def test_eastmoney_research_reports_defaults_to_90_day_window():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class FakeResponse:
        def json(self):
            return {"data": [], "TotalPage": 1}

    calls = []

    def fake_em_get(url, params=None, headers=None, timeout=30):
        calls.append((url, params, headers, timeout))
        return FakeResponse()

    _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        today=date(2026, 6, 24),
        em_get=fake_em_get,
    )

    assert calls[0][1]["beginTime"] == "2026-03-26"
    assert calls[0][1]["endTime"] == "2026-06-24"


def test_eastmoney_research_reports_accepts_code_scoped_reportapi_rows():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class FakeResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "某半导体公司深度报告：模拟芯片周期修复",
                        "publishDate": "2026-06-12",
                        "orgSName": "国信证券",
                        "infoCode": "CODE_SCOPED",
                    }
                ],
                "TotalPage": 1,
            }

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        em_get=lambda *args, **kwargs: FakeResponse(),
    )

    assert len(items) == 1
    assert items[0].extra["fetch_method"] == "eastmoney_reportapi"


def test_eastmoney_research_reports_supports_alternate_report_columns():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class FakeResponse:
        def json(self):
            return {
                "data": [
                    {
                        "股票简称": "圣邦股份",
                        "研报标题": "模拟芯片行业点评：需求边际改善",
                        "发布日期": "2026-06-12",
                        "机构名称": "中信证券",
                        "infoCode": "SB123",
                    }
                ],
                "TotalPage": 1,
            }

    items = _adapt_eastmoney_research_reports(
        stock_code="300661",
        source_config={"enabled": True, "max_items": 5},
        stock_name="圣邦股份",
        em_get=lambda *args, **kwargs: FakeResponse(),
    )

    assert len(items) == 1
    assert items[0].title == "模拟芯片行业点评：需求边际改善"
    assert items[0].extra["institution"] == "中信证券"


def test_eastmoney_research_reports_falls_back_to_direct_reportapi(monkeypatch):
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    class FakeResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "公司点评：新品平台持续拓展",
                        "publishDate": "2026-06-20",
                        "orgSName": "华泰证券",
                        "infoCode": "DIRECT123",
                        "emRatingName": "增持",
                        "predictThisYearEps": 1.11,
                    }
                ],
                "TotalPage": 1,
            }

    calls = []

    def fake_em_get(url, params=None, headers=None, timeout=30):
        calls.append((url, params, headers, timeout))
        return FakeResponse()

    items = _adapt_eastmoney_research_reports(
        stock_code="300661",
        source_config={"enabled": True, "max_items": 5},
        stock_name="圣邦股份",
        em_get=fake_em_get,
    )

    assert len(items) == 1
    assert items[0].title == "公司点评：新品平台持续拓展"
    assert items[0].extra["institution"] == "华泰证券"
    assert items[0].extra["rating"] == "增持"
    assert calls[0][0] == "https://reportapi.eastmoney.com/report/list"
    assert calls[0][1]["code"] == "300661"
    assert calls[0][1]["pageSize"] == "100"


def test_adapter_error_for_one_source_does_not_block_others():
    from a_stock_source_intake import collect_a_stock_source_items, _SOURCE_ADAPTERS

    def fake_adapt_cninfo(*args, **kwargs):
        return [
            SynthesisItem(
                title="cninfo ok",
                content="c",
                author="",
                source_platform="公告",
                url="http://cninfo.com.cn/a",
                publish_time="2026-06-01",
                extra={"source_credit": 95},
            )
        ]

    def fake_adapt_news(*args, **kwargs):
        return []

    def fake_adapt_reports(*args, **kwargs):
        raise RuntimeError("reports boom")

    original_adapters = dict(_SOURCE_ADAPTERS)
    _SOURCE_ADAPTERS["cninfo_announcements"] = fake_adapt_cninfo
    _SOURCE_ADAPTERS["eastmoney_stock_news"] = fake_adapt_news
    _SOURCE_ADAPTERS["eastmoney_research_reports"] = fake_adapt_reports
    try:
        result = collect_a_stock_source_items(
            stock_name="中简科技",
            stock_code="300777",
            config={
                "enabled": True,
                "a_stock": {
                    "cninfo_announcements": {"enabled": True, "max_items": 5},
                    "eastmoney_stock_news": {"enabled": True, "max_items": 5},
                    "eastmoney_research_reports": {"enabled": True, "max_items": 5},
                },
            },
        )
    finally:
        _SOURCE_ADAPTERS.clear()
        _SOURCE_ADAPTERS.update(original_adapters)

    assert result["status"] == "partial"
    assert len(result["items"]) == 1
    assert result["source_statuses"]["cninfo_announcements"]["status"] == "ok"
    assert result["source_statuses"]["eastmoney_stock_news"]["status"] == "empty"
    assert result["source_statuses"]["eastmoney_research_reports"]["status"] == "error"


def test_eastmoney_stock_news_fetch_error_returns_error_status():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    def fake_em_get(*args, **kwargs):
        raise RuntimeError("eastmoney blocked")

    result = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "provider": "eastmoney_raw"},
        stock_name="中简科技",
        em_get=fake_em_get,
    )

    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "eastmoney blocked" in result["error"]


def test_medium_credit_items_are_not_confirmed_fact():
    from a_stock_source_intake import _adapt_eastmoney_stock_news, _adapt_eastmoney_research_reports

    class FakeNewsResponse:
        text = (
            'jQuery_news({"result":{"cmsArticleWebOld":[{'
            '"title":"中简科技：新产品研发进展顺利",'
            '"content":"公司表示当前研发投入持续增加。",'
            '"date":"2026-06-10 10:00:00",'
            '"mediaName":"东方财富",'
            '"url":"https://finance.eastmoney.com/a/202606101234.html"'
            "}]}})"
        )

    news_items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "provider": "eastmoney_raw"},
        stock_name="中简科技",
        em_get=lambda *args, **kwargs: FakeNewsResponse(),
    )
    assert news_items[0].extra["source_credit"] == 65
    assert news_items[0].extra["verification_status"] != "confirmed_fact"
    assert news_items[0].extra["source_credit"] < 80


def test_akshare_imported_only_inside_collection(monkeypatch):
    """When enabled, akshare may be imported, but only inside the helper call."""
    from a_stock_source_intake import collect_a_stock_source_items

    imported = {"times": 0}
    real_import = __builtins__["__import__"]

    def tracking_import(name, *args, **kwargs):
        if name == "akshare":
            imported["times"] += 1
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", tracking_import)

    collect_a_stock_source_items(
        stock_name="中简科技",
        stock_code="300777",
        config={"enabled": False},
    )

    assert imported["times"] == 0
