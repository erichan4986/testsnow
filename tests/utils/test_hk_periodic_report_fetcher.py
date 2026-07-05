"""Tests for HKEX periodic report fetcher helper.

These tests use sample JSON fixtures and do not access the network.
"""

import sys
from pathlib import Path
import logging

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import hk_periodic_report_fetcher
from hk_periodic_report_fetcher import (
    HKEX_BASE_URL,
    build_hk_periodic_report_cache_path,
    build_hkex_title_search_url,
    discover_hkex_periodic_report,
    fetch_hk_periodic_report_text,
    find_hk_periodic_report,
    resolve_hkex_stock_id,
)


SAMPLE_ACTIVE_STOCK_JSON = {
    "count": 3,
    "data": [
        {
            "stockId": "1000000001",
            "stockCode": "00001",
            "name": "CKH HOLDINGS",
            "stockType": "Equity",
        },
        {
            "stockId": "1000221013",
            "stockCode": "02533",
            "name": "BLACK SESAME INTELLIGENCE TECHNOLOGY CO., LTD.",
            "stockType": "Equity",
        },
        {
            "stockId": "1000000003",
            "stockCode": "00003",
            "name": "HK & CHINA GAS",
            "stockType": "Equity",
        },
    ],
}

SAMPLE_ACTIVE_STOCK_SHORT_JSON = {
    "data": [
        {"i": 1000221013, "c": "02533", "n": "BLACK SESAME", "s": 1234},
    ],
}


SAMPLE_TITLE_SEARCH_RESPONSE = {
    "count": 2,
    "data": [
        {
            "title": "2025 ANNUAL REPORT",
            "date_time": "27/04/2026 16:48",
            "file_link": "/listedco/listconews/sehk/2026/0427/2026042701016.pdf",
        },
        {
            "title": "INTERIM REPORT 2025",
            "date_time": "28/08/2025 17:30",
            "file_link": "/listedco/listconews/sehk/2025/0828/2025082801234.pdf",
        },
    ],
}

SAMPLE_TITLE_SEARCH_ZH_RESPONSE = {
    "result": """
    [
      {
        "TITLE": "2025年報",
        "DATE_TIME": "27/04/2026 16:48",
        "FILE_LINK": "/listedco/listconews/sehk/2026/0427/2026042701017_c.pdf"
      },
      {
        "TITLE": "2025 中期報告",
        "DATE_TIME": "28/08/2025 17:30",
        "FILE_LINK": "/listedco/listconews/sehk/2025/0828/2025082801234_c.pdf"
      }
    ]
    """
}


def test_resolve_hkex_stock_id_finds_black_sesame():
    import json

    json_text = json.dumps(SAMPLE_ACTIVE_STOCK_JSON)
    stock_id = resolve_hkex_stock_id("02533", json_text)
    assert stock_id == "1000221013"


def test_resolve_hkex_stock_id_handles_real_hkex_short_keys():
    import json

    json_text = json.dumps(SAMPLE_ACTIVE_STOCK_SHORT_JSON)
    stock_id = resolve_hkex_stock_id("2533", json_text)
    assert stock_id == "1000221013"


def test_resolve_hkex_stock_id_returns_none_when_missing():
    import json

    json_text = json.dumps(SAMPLE_ACTIVE_STOCK_JSON)
    assert resolve_hkex_stock_id("99999", json_text) is None


def test_resolve_hkex_stock_id_returns_none_for_invalid_json():
    assert resolve_hkex_stock_id("02533", "not valid json") is None


def test_resolve_hkex_stock_id_logs_invalid_json(caplog):
    with caplog.at_level(logging.WARNING):
        assert resolve_hkex_stock_id("02533", "not valid json") is None
    assert "failed to parse HKEX active stock JSON" in caplog.text


def test_find_hk_periodic_report_annual():
    report = find_hk_periodic_report(SAMPLE_TITLE_SEARCH_RESPONSE, report_type="annual")
    assert report is not None
    assert report["title"] == "2025 ANNUAL REPORT"
    assert report["date_time"] == "27/04/2026 16:48"
    assert report["file_link"] == "/listedco/listconews/sehk/2026/0427/2026042701016.pdf"
    assert report["pdf_url"] == (
        "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0427/2026042701016.pdf"
    )


def test_find_hk_periodic_report_prefers_chinese_annual_result_wrapper():
    report = find_hk_periodic_report(
        SAMPLE_TITLE_SEARCH_ZH_RESPONSE,
        report_type="annual",
        lang="ZH",
    )
    assert report is not None
    assert report["title"] == "2025年報"
    assert report["date_time"] == "27/04/2026 16:48"
    assert report["file_link"] == "/listedco/listconews/sehk/2026/0427/2026042701017_c.pdf"
    assert report["pdf_url"] == (
        "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0427/2026042701017_c.pdf"
    )


def test_find_hk_periodic_report_interim():
    report = find_hk_periodic_report(SAMPLE_TITLE_SEARCH_RESPONSE, report_type="interim")
    assert report is not None
    assert "INTERIM" in report["title"].upper()
    assert report["pdf_url"].startswith("https://www1.hkexnews.hk/")


def test_find_hk_periodic_report_returns_none_when_no_match():
    response = {"data": [{"title": "ESG REPORT 2025", "date_time": "01/01/2026 00:00", "file_link": "/x.pdf"}]}
    assert find_hk_periodic_report(response, report_type="annual") is None


def test_find_hk_periodic_report_is_case_insensitive():
    response = {
        "data": [
            {"title": "annual report 2025", "date_time": "27/04/2026 16:48", "file_link": "/a.pdf"}
        ]
    }
    report = find_hk_periodic_report(response, report_type="annual")
    assert report is not None
    assert report["title"] == "annual report 2025"


def test_build_hkex_title_search_url_annual():
    url = build_hkex_title_search_url(
        "1000221013",
        start_date="20250401",
        end_date="20260430",
        report_type="annual",
    )
    assert url.startswith("https://www1.hkexnews.hk/search/titleSearchServlet.do")
    assert "stockId=1000221013" in url
    assert "from=20250401" in url
    assert "to=20260430" in url
    assert "lang=ZH" in url
    assert "%E5%B9%B4%E5%A0%B1" in url
    assert "annual+report" not in url.lower()


def test_discover_hkex_periodic_report_resolves_stock_id_and_pdf_url():
    import json

    loaded_search_urls = []

    def fake_active_loader(lang="ZH"):
        assert lang == "ZH"
        return json.dumps(SAMPLE_ACTIVE_STOCK_SHORT_JSON)

    def fake_title_loader(url):
        loaded_search_urls.append(url)
        assert "stockId=1000221013" in url
        assert "from=20250101" in url
        assert "to=20260630" in url
        return SAMPLE_TITLE_SEARCH_ZH_RESPONSE

    result = discover_hkex_periodic_report(
        stock_code="02533",
        report_year=2025,
        active_stock_loader=fake_active_loader,
        title_search_loader=fake_title_loader,
    )

    assert result["title"] == "2025年報"
    assert result["url"] == (
        "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0427/2026042701017_c.pdf"
    )
    assert result["stock_code"] == "02533"
    assert result["stock_id"] == "1000221013"
    assert result["market"] == "HK"
    assert result["report_year"] == 2025
    assert result["report_type"] == "annual"
    assert result["search_url"] == loaded_search_urls[0]


def test_discover_hkex_periodic_report_rejects_missing_stock_id():
    import json

    with pytest.raises(ValueError, match="No HKEX stockId"):
        discover_hkex_periodic_report(
            stock_code="09999",
            report_year=2025,
            active_stock_loader=lambda lang="ZH": json.dumps(SAMPLE_ACTIVE_STOCK_SHORT_JSON),
            title_search_loader=lambda url: SAMPLE_TITLE_SEARCH_ZH_RESPONSE,
        )


def test_build_hkex_title_search_url_english_fallback():
    url = build_hkex_title_search_url(
        "1000221013",
        start_date="20250401",
        end_date="20260430",
        report_type="annual",
        lang="EN",
    )
    assert "lang=EN" in url
    assert "title=annual" in url.lower() or "title=annual+report" in url.lower()


def test_build_hkex_title_search_url_interim():
    url = build_hkex_title_search_url(
        "1000221013",
        start_date="20250801",
        end_date="20250831",
        report_type="interim",
    )
    assert "stockId=1000221013" in url
    assert "lang=ZH" in url
    assert "%E4%B8%AD%E6%9C%9F%E5%A0%B1%E5%91%8A" in url


def test_build_hk_periodic_report_cache_path():
    path = build_hk_periodic_report_cache_path(
        "/tmp/cache",
        stock_code="02533",
        year=2025,
        report_type="annual",
        lang="ZH",
    )
    assert str(path) == "/tmp/cache/hk/02533_2025_annual_zh_jina.txt"


def test_fetch_hk_periodic_report_text_calls_download_and_reader(monkeypatch, tmp_path):
    """fetch_hk_periodic_report_text should orchestrate download -> read without touching network."""
    calls = []
    cache_path = tmp_path / "02533_2025_annual_jina.txt"

    def fake_download(url, path):
        calls.append(("download", url, str(path)))
        assert url.startswith("https://r.jina.ai/http://")
        assert "www1.hkexnews.hk/x.pdf" in url
        path.write_text("Fake PDF text content", encoding="utf-8")

    def fake_read(path):
        calls.append(("read", str(path)))
        return path.read_text(encoding="utf-8")

    monkeypatch.setattr("hk_periodic_report_fetcher._download_pdf_to_cache", fake_download)
    monkeypatch.setattr("hk_periodic_report_fetcher._read_cached_pdf_text", fake_read)

    text = fetch_hk_periodic_report_text(
        pdf_url="https://www1.hkexnews.hk/x.pdf",
        cache_path=cache_path,
    )
    assert text == "Fake PDF text content"
    assert any(c[0] == "download" for c in calls)
    assert any(c[0] == "read" for c in calls)


def test_fetch_hk_periodic_report_text_returns_none_on_failure(monkeypatch, tmp_path):
    def fake_download(url, path):
        raise RuntimeError("network failed")

    monkeypatch.setattr("hk_periodic_report_fetcher._download_pdf_to_cache", fake_download)
    text = fetch_hk_periodic_report_text(
        pdf_url="https://www1.hkexnews.hk/x.pdf",
        cache_path=tmp_path / "02533_2025_annual_jina.txt",
    )
    assert text is None


def test_fetch_hk_periodic_report_text_logs_failure(monkeypatch, tmp_path, caplog):
    def fake_download(url, path):
        raise RuntimeError("network failed")

    monkeypatch.setattr("hk_periodic_report_fetcher._download_pdf_to_cache", fake_download)
    with caplog.at_level(logging.WARNING):
        text = fetch_hk_periodic_report_text(
            pdf_url="https://www1.hkexnews.hk/x.pdf",
            cache_path=tmp_path / "02533_2025_annual_jina.txt",
        )

    assert text is None
    assert "failed to fetch HK periodic report text" in caplog.text


def test_download_pdf_to_cache_retries_and_sleeps(monkeypatch, tmp_path):
    calls = []
    sleeps = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"cached text"

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        if len(calls) == 1:
            raise OSError("temporary failure")
        return FakeResponse()

    monkeypatch.setattr(hk_periodic_report_fetcher.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(hk_periodic_report_fetcher.time, "sleep", lambda seconds: sleeps.append(seconds))

    cache_path = tmp_path / "02533_2025_annual_jina.txt"
    hk_periodic_report_fetcher._download_pdf_to_cache(
        "https://r.jina.ai/http://www1.hkexnews.hk/x.pdf",
        cache_path,
        retries=2,
        delay_seconds=0.25,
    )

    assert cache_path.read_text(encoding="utf-8") == "cached text"
    assert len(calls) == 2
    assert sleeps == [0.25]
