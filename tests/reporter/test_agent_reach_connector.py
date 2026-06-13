import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_skills.agent_reach_skill import (
    CONNECTOR_REGISTRY,
    RSSConnector,
    WebConnector,
    YouTubeConnector,
    ExaSearchConnector,
    WechatConnector,
    _get_connector,
    _UNSUPPORTED_PLATFORMS,
    _dedupe_records,
)


# --- Registry tests ---

def test_registry_contains_rss():
    assert "rss" in CONNECTOR_REGISTRY
    assert isinstance(CONNECTOR_REGISTRY["rss"], RSSConnector)


def test_registry_contains_web():
    assert "web" in CONNECTOR_REGISTRY
    assert isinstance(CONNECTOR_REGISTRY["web"], WebConnector)


def test_registry_does_not_contain_twitter():
    assert "twitter" not in CONNECTOR_REGISTRY


def test_registry_does_not_contain_youtube():
    assert "youtube" not in CONNECTOR_REGISTRY


def test_registry_does_not_contain_exa_search():
    assert "exa_search" not in CONNECTOR_REGISTRY


def test_registry_does_not_contain_wechat():
    assert "wechat" not in CONNECTOR_REGISTRY


def test_get_connector_returns_registered():
    assert _get_connector("rss") is not None
    assert _get_connector("web") is not None


def test_get_connector_returns_detection_only():
    assert _get_connector("youtube") is not None
    assert _get_connector("exa_search") is not None
    assert _get_connector("wechat") is not None


def test_get_connector_returns_none_for_unknown():
    assert _get_connector("unknown_platform_xyz") is None


# --- RSSConnector tests ---

def test_rss_connector_check_deps_ok():
    connector = RSSConnector()
    available, reason = connector.check_deps()
    # feedparser is installed as agent-reach dependency
    assert available is True
    assert reason == ""


def test_rss_connector_skips_empty_filter_terms():
    connector = RSSConnector()
    records, warnings = connector.run({
        "rss_feeds": ["http://example.com/feed"],
        "rss_filter_terms": [],
        "rss_limit": 5,
    })
    assert records == []
    assert any("no filter terms" in w for w in warnings)


def test_rss_connector_filters_matching_entries():
    connector = RSSConnector()
    mock_entry = MagicMock()
    mock_entry.get.side_effect = lambda key, default="": {
        "title": "黑芝麻智能发布新芯片",
        "summary": "公司宣布最新ADAS芯片量产",
        "description": "",
        "link": "http://example.com/1",
        "author": "TechNews",
        "published": "2026-06-10",
    }.get(key, default)

    mock_parsed = MagicMock()
    mock_parsed.entries = [mock_entry]

    with patch("feedparser.parse", return_value=mock_parsed):
        records, warnings = connector.run({
            "rss_feeds": ["http://example.com/feed"],
            "rss_filter_terms": ["黑芝麻智能"],
            "rss_limit": 5,
        })

    assert len(records) == 1
    assert records[0]["_platform"] == "rss"
    assert records[0]["title"] == "黑芝麻智能发布新芯片"
    assert records[0]["url"] == "http://example.com/1"
    assert records[0]["source_feed"] == "http://example.com/feed"


def test_rss_connector_no_match_returns_empty():
    connector = RSSConnector()
    mock_entry = MagicMock()
    mock_entry.get.side_effect = lambda key, default="": {
        "title": " unrelated news ",
        "summary": "something else",
        "description": "",
        "link": "http://example.com/2",
        "author": "News",
        "published": "2026-06-10",
    }.get(key, default)

    mock_parsed = MagicMock()
    mock_parsed.entries = [mock_entry]

    with patch("feedparser.parse", return_value=mock_parsed):
        records, warnings = connector.run({
            "rss_feeds": ["http://example.com/feed"],
            "rss_filter_terms": ["黑芝麻智能"],
            "rss_limit": 5,
        })

    assert records == []


def test_rss_connector_runtime_failure_returns_warning():
    connector = RSSConnector()
    with patch("feedparser.parse", side_effect=Exception("network down")):
        records, warnings = connector.run({
            "rss_feeds": ["http://example.com/feed"],
            "rss_filter_terms": ["test"],
            "rss_limit": 5,
        })
    assert records == []
    assert any("parse/runtime error" in w for w in warnings)


def test_rss_connector_limit_enforced():
    connector = RSSConnector()
    entries = []
    for i in range(10):
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="", idx=i: {
            "title": f"News {idx}",
            "summary": f"Summary about 黑芝麻智能 {idx}",
            "description": "",
            "link": f"http://example.com/{idx}",
            "author": "Author",
            "published": "2026-06-10",
        }.get(key, default)
        entries.append(mock_entry)

    mock_parsed = MagicMock()
    mock_parsed.entries = entries

    with patch("feedparser.parse", return_value=mock_parsed):
        records, warnings = connector.run({
            "rss_feeds": ["http://example.com/feed"],
            "rss_filter_terms": ["黑芝麻智能"],
            "rss_limit": 3,
        })

    assert len(records) == 3


# --- WebConnector tests ---

def test_web_connector_check_deps_ok():
    connector = WebConnector()
    available, reason = connector.check_deps()
    assert available is True
    assert reason == ""


def test_web_connector_skips_empty_urls():
    connector = WebConnector()
    records, warnings = connector.run({"urls": [], "timeout": 15})
    assert records == []
    assert any("no URLs provided" in w for w in warnings)


def test_web_connector_read_success():
    connector = WebConnector()
    mock_response = MagicMock()
    mock_response.read.return_value = b"Title Line\nBody content here.\nMore content."
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response):
        records, warnings = connector.run({
            "urls": ["http://example.com/article"],
            "timeout": 15,
        })

    assert len(records) == 1
    assert records[0]["_platform"] == "web"
    assert records[0]["title"] == "Title Line"
    assert records[0]["content"] == "Body content here.\nMore content."
    assert records[0]["url"] == "http://example.com/article"
    assert records[0]["author"] == ""
    assert records[0]["publish_time"] == ""


def test_web_connector_marks_official_seed_url():
    connector = WebConnector()
    mock_response = MagicMock()
    mock_response.read.return_value = b"Title\nBody"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response):
        records, warnings = connector.run({
            "urls": ["https://www.blacksesame.com/zh/list_10/972.html"],
            "timeout": 15,
            "official_domains": ["blacksesame.com"],
        })

    assert len(records) == 1
    assert records[0].get("user_provided_url") is True
    assert records[0].get("query_type") == "web_read"
    assert records[0].get("official_seed_url") is True
    assert records[0].get("source_type") == "official"


def test_web_connector_does_not_mark_unofficial_domain():
    connector = WebConnector()
    mock_response = MagicMock()
    mock_response.read.return_value = b"Title\nBody"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response):
        records, warnings = connector.run({
            "urls": ["https://notblacksesame.com/a"],
            "timeout": 15,
            "official_domains": ["blacksesame.com"],
        })

    assert len(records) == 1
    assert records[0].get("official_seed_url") is not True
    assert records[0].get("source_type") != "official"


def test_web_connector_hostname_match_is_conservative():
    connector = WebConnector()
    mock_response = MagicMock()
    mock_response.read.return_value = b"Title\nBody"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    cases = [
        ("https://blacksesame.com/a", True),
        ("https://www.blacksesame.com/a", True),
        ("https://sub.blacksesame.com/a", True),
        ("https://notblacksesame.com/a", False),
        ("https://blacksesame.com.cn/a", False),
        ("https://xblacksesame.com/a", False),
    ]
    for url, expected in cases:
        with patch("urllib.request.urlopen", return_value=mock_response):
            records, _ = connector.run({
                "urls": [url],
                "timeout": 15,
                "official_domains": ["blacksesame.com"],
            })
        assert records[0].get("official_seed_url") is expected, f"{url} expected {expected}"


def test_web_connector_marks_user_provided_url():
    connector = WebConnector()
    mock_response = MagicMock()
    mock_response.read.return_value = b"Title\nBody"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response):
        records, warnings = connector.run({
            "urls": ["http://example.com/article"],
            "timeout": 15,
        })

    assert len(records) == 1
    assert records[0].get("user_provided_url") is True
    assert records[0].get("query_type") == "web_read"


def test_web_connector_http_error_warning():
    connector = WebConnector()
    with patch("urllib.request.urlopen", side_effect=Exception("HTTP Error 404")):
        records, warnings = connector.run({
            "urls": ["http://example.com/bad"],
            "timeout": 15,
        })
    assert records == []
    assert any("failed to read" in w for w in warnings)


def test_web_connector_empty_content_warning():
    connector = WebConnector()
    mock_response = MagicMock()
    mock_response.read.return_value = b"   "
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    with patch("urllib.request.urlopen", return_value=mock_response):
        records, warnings = connector.run({
            "urls": ["http://example.com/empty"],
            "timeout": 15,
        })

    assert records == []
    assert any("empty content" in w for w in warnings)


def test_web_connector_multiple_urls_partial_success():
    connector = WebConnector()

    def _side_effect(req, timeout):
        url = req.get_full_url()
        mock_resp = MagicMock()
        if "good" in url:
            mock_resp.read.return_value = b"Good Title\nGood body."
        else:
            raise Exception("HTTP Error 500")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=None)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=_side_effect):
        records, warnings = connector.run({
            "urls": [
                "http://example.com/good",
                "http://example.com/bad",
            ],
            "timeout": 15,
        })

    assert len(records) == 1
    assert records[0]["title"] == "Good Title"
    assert any("failed to read" in w for w in warnings)


# --- Detection-only connector tests ---

def test_youtube_connector_detection_only():
    connector = YouTubeConnector()
    records, warnings = connector.run({})
    assert records == []
    assert any("detection-only" in w or "unavailable" in w for w in warnings)


def test_exa_search_connector_detection_only():
    connector = ExaSearchConnector()
    records, warnings = connector.run({})
    assert records == []
    assert any("detection-only" in w or "unavailable" in w for w in warnings)


def test_wechat_connector_detection_only():
    connector = WechatConnector()
    records, warnings = connector.run({})
    assert records == []
    assert any("detection-only" in w or "unavailable" in w for w in warnings)


# --- Dedupe tests ---

def test_dedupe_records_by_url():
    records = [
        {"url": "http://a", "title": "t1", "_platform": "rss"},
        {"url": "http://a", "title": "t2", "_platform": "rss"},
        {"url": "http://b", "title": "t3", "_platform": "web"},
    ]
    result = _dedupe_records(records)
    assert len(result) == 2


def test_dedupe_records_by_platform_title_time():
    records = [
        {"_platform": "rss", "title": "t", "publish_time": "2026-01-01"},
        {"_platform": "rss", "title": "t", "publish_time": "2026-01-01"},
        {"_platform": "web", "title": "t", "publish_time": "2026-01-01"},
    ]
    result = _dedupe_records(records)
    assert len(result) == 2


# --- Unsupported platform guard ---

def test_unsupported_platforms_set_contains_twitter():
    assert "twitter" in _UNSUPPORTED_PLATFORMS


def test_unsupported_platforms_set_contains_xiaohongshu():
    assert "xiaohongshu" in _UNSUPPORTED_PLATFORMS
