"""Tests for a_stock_source_intake helper.

All tests use mocking to avoid real network calls and to verify lazy import
behavior. No test should import akshare at module scope.
"""

import sys
import types
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

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "新闻标题": "中简科技：新产品研发进展顺利",
                "新闻内容": "公司表示当前研发投入持续增加。",
                "发布时间": "2026-06-10 10:00:00",
                "文章来源": "东方财富",
                "新闻链接": "https://finance.eastmoney.com/a/202606101234.html",
            },
        )
    ]
    fake_ak.stock_news_em.return_value = fake_df

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "新闻"
    assert item.extra["source_credit"] == 60
    assert item.extra["source_type"] == "news"
    assert item.extra["source_domain"] == "finance.eastmoney.com"
    assert item.extra["verification_status"] == "professional_observation"
    assert item.extra["knowledge_eligible"] is True


def test_eastmoney_stock_news_requires_stock_name_or_code_match():
    from a_stock_source_intake import _adapt_eastmoney_stock_news

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "新闻标题": "某 unrelated 公司发布新品",
                "新闻内容": "与目标公司无关。",
                "发布时间": "2026-06-10 10:00:00",
                "文章来源": "东方财富",
                "新闻链接": "https://finance.eastmoney.com/a/202606101234.html",
            },
        )
    ]
    fake_ak.stock_news_em.return_value = fake_df

    items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert items == []


def test_eastmoney_research_reports_adapter_marks_professional_observation():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["title", "publishDate", "orgSName", "infoCode", "emRatingName", "predictThisYearEps"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "title": "中简科技2024Q3业绩点评：新旧更替，万象更新",
                "publishDate": "2026-05-12",
                "orgSName": "国信证券",
                "infoCode": "ABC123",
                "emRatingName": "买入",
                "predictThisYearEps": 1.23,
            },
        )
    ]
    fake_ak.stock_research_report_em.return_value = fake_df

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert len(items) == 1
    item = items[0]
    assert item.source_platform == "研报"
    assert item.extra["source_credit"] == 65
    assert item.extra["source_type"] == "research_report"
    assert item.extra["verification_status"] == "professional_observation"
    assert item.extra["knowledge_eligible"] is True
    assert item.extra.get("rating") == "买入"
    assert item.extra.get("eps") == 1.23
    assert item.extra.get("institution") == "国信证券"


def test_eastmoney_research_reports_requires_target_reference_without_code_column():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["title", "publishDate", "orgSName", "infoCode"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "title": "某半导体公司深度报告：模拟芯片周期修复",
                "publishDate": "2026-05-12",
                "orgSName": "国信证券",
                "infoCode": "UNRELATED",
            },
        )
    ]
    fake_ak.stock_research_report_em.return_value = fake_df

    items = _adapt_eastmoney_research_reports(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5, "direct_fallback": False},
        stock_name="中简科技",
        ak_module=fake_ak,
    )

    assert items == []


def test_eastmoney_research_reports_matches_stock_name_column():
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["股票简称", "研报标题", "发布日期", "机构名称", "infoCode"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "股票简称": "圣邦股份",
                "研报标题": "模拟芯片行业点评：需求边际改善",
                "发布日期": "2026-05-12",
                "机构名称": "中信证券",
                "infoCode": "SB123",
            },
        )
    ]
    fake_ak.stock_research_report_em.return_value = fake_df

    items = _adapt_eastmoney_research_reports(
        stock_code="300661",
        source_config={"enabled": True, "max_items": 5},
        stock_name="圣邦股份",
        ak_module=fake_ak,
    )

    assert len(items) == 1
    assert items[0].title == "模拟芯片行业点评：需求边际改善"
    assert items[0].extra["institution"] == "中信证券"


def test_eastmoney_research_reports_falls_back_to_direct_reportapi(monkeypatch):
    from a_stock_source_intake import _adapt_eastmoney_research_reports

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.__len__.return_value = 0
    fake_ak.stock_research_report_em.return_value = fake_df

    class FakeResponse:
        def json(self):
            return {
                "data": [
                    {
                        "title": "公司点评：新品平台持续拓展",
                        "publishDate": "2026-05-20",
                        "orgSName": "华泰证券",
                        "infoCode": "DIRECT123",
                        "emRatingName": "增持",
                        "predictThisYearEps": 1.11,
                    }
                ],
                "TotalPage": 1,
            }

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append((url, params, timeout))
            return FakeResponse()

    fake_session = FakeSession()
    fake_requests = types.SimpleNamespace(Session=lambda: fake_session)
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    items = _adapt_eastmoney_research_reports(
        stock_code="300661",
        source_config={"enabled": True, "max_items": 5, "direct_fallback": True},
        stock_name="圣邦股份",
        ak_module=fake_ak,
    )

    assert len(items) == 1
    assert items[0].title == "公司点评：新品平台持续拓展"
    assert items[0].extra["institution"] == "华泰证券"
    assert items[0].extra["rating"] == "增持"
    assert fake_session.calls[0][0] == "https://reportapi.eastmoney.com/report/list"
    assert fake_session.calls[0][1]["code"] == "300661"
    assert fake_session.calls[0][1]["pageSize"] == "100"


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


def test_unsupported_akshare_function_returns_unsupported_function(monkeypatch):
    from a_stock_source_intake import collect_a_stock_source_items

    class FakeAkshare:
        pass

    fake_ak = FakeAkshare()
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    result = collect_a_stock_source_items(
        stock_name="中简科技",
        stock_code="300777",
        config={
            "enabled": True,
            "a_stock": {
                "cninfo_announcements": {"enabled": False},
                "eastmoney_stock_news": {"enabled": True, "max_items": 5},
                "eastmoney_research_reports": {"enabled": False},
            },
        },
    )

    assert result["source_statuses"]["eastmoney_stock_news"]["status"] == "unsupported_function"


def test_medium_credit_items_are_not_confirmed_fact():
    from a_stock_source_intake import _adapt_eastmoney_stock_news, _adapt_eastmoney_research_reports

    fake_ak = MagicMock()
    fake_df = MagicMock()
    fake_df.columns = ["新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]
    fake_df.__len__.return_value = 1
    fake_df.iterrows.return_value = [
        (
            0,
            {
                "新闻标题": "中简科技：新产品研发进展顺利",
                "新闻内容": "公司表示当前研发投入持续增加。",
                "发布时间": "2026-06-10 10:00:00",
                "文章来源": "东方财富",
                "新闻链接": "https://finance.eastmoney.com/a/202606101234.html",
            },
        )
    ]
    fake_ak.stock_news_em.return_value = fake_df

    news_items = _adapt_eastmoney_stock_news(
        stock_code="300777",
        source_config={"enabled": True, "max_items": 5},
        stock_name="中简科技",
        ak_module=fake_ak,
    )
    assert news_items[0].extra["source_credit"] == 60
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
