"""Unit tests for DetailPageFetcher."""

import sys
from pathlib import Path

# Add project root to sys.path so `scripts.utils.detail_page_fetcher` is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.utils.detail_page_fetcher import DetailPageFetcher


def test_extract_post_id():
    fetcher = DetailPageFetcher(vault_base=Path("/tmp/test-vault"))
    assert fetcher._extract_post_id("https://xueqiu.com/8025337289/389734910") == "389734910"
    assert fetcher._extract_post_id("https://xueqiu.com/8025337289/389734910/") == "389734910"
    assert fetcher._extract_post_id("https://xueqiu.com/8025337289/389734910?from=timeline") == "389734910"


def test_write_to_vault():
    import tempfile
    from datetime import datetime

    with tempfile.TemporaryDirectory() as tmpdir:
        fetcher = DetailPageFetcher(vault_base=Path(tmpdir))
        metadata = {
            "source_url": "https://xueqiu.com/8025337289/389734910",
            "title": "测试标题",
            "author": "测试作者",
            "date": "2026-05-20",
            "likes": 10,
            "comments": 2,
            "reposts": 1,
        }
        path = fetcher._write_to_vault(
            stock_name="测试股票",
            post_id="389734910",
            metadata=metadata,
            full_content="这是测试正文内容。",
        )
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "测试标题" in content
        assert "这是测试正文内容" in content
        assert "389734910" in content
        assert "source_url" in content
        assert "interactions" in content


def test_accepts_cdp_url_without_connecting():
    fetcher = DetailPageFetcher(
        vault_base=Path("/tmp/test-vault"),
        cdp_url="http://localhost:9222",
    )
    assert fetcher.cdp_url == "http://localhost:9222"
    assert fetcher._context is None
    assert fetcher._playwright is None


def test_close_is_public_alias_for_browser_cleanup():
    fetcher = DetailPageFetcher(vault_base=Path("/tmp/test-vault"))
    assert hasattr(fetcher, "close")
    fetcher.close()


def test_close_does_not_close_reused_cdp_context():
    """In CDP mode, when reusing an existing browser context, close() must not close it or the browser."""
    fetcher = DetailPageFetcher(
        vault_base=Path("/tmp/test-vault"),
        cdp_url="http://localhost:9222",
    )

    fake_context = type("FakeContext", (), {"close": lambda self: setattr(self, "was_closed", True)})()
    fake_browser = type("FakeBrowser", (), {
        "contexts": [fake_context],
        "close": lambda self: setattr(self, "was_closed", True),
    })()
    fake_playwright = type("FakePlaywright", (), {
        "stop": lambda self: setattr(self, "was_stopped", True),
    })()

    fetcher._playwright = fake_playwright
    fetcher._browser = fake_browser
    fetcher._context = fake_context
    fetcher._owns_context = False
    fetcher._owns_browser = False

    fetcher.close()

    assert not getattr(fake_context, "was_closed", False), "reused CDP context was closed"
    assert not getattr(fake_browser, "was_closed", False), "CDP browser was closed"
    assert getattr(fake_playwright, "was_stopped", False), "playwright was not stopped"
    assert not fetcher._owns_context
    assert not fetcher._owns_browser


def test_close_closes_new_cdp_context_but_not_browser():
    """In CDP mode, when creating a new context, close() closes the new context but not the browser."""
    fetcher = DetailPageFetcher(
        vault_base=Path("/tmp/test-vault"),
        cdp_url="http://localhost:9222",
    )

    fake_context = type("FakeContext", (), {"close": lambda self: setattr(self, "was_closed", True)})()
    fake_browser = type("FakeBrowser", (), {
        "contexts": [],
        "close": lambda self: setattr(self, "was_closed", True),
    })()
    fake_playwright = type("FakePlaywright", (), {
        "stop": lambda self: setattr(self, "was_stopped", True),
    })()

    fetcher._playwright = fake_playwright
    fetcher._browser = fake_browser
    fetcher._context = fake_context
    fetcher._owns_context = True
    fetcher._owns_browser = False

    fetcher.close()

    assert getattr(fake_context, "was_closed", False), "new CDP context was not closed"
    assert not getattr(fake_browser, "was_closed", False), "CDP browser was closed"
    assert getattr(fake_playwright, "was_stopped", False), "playwright was not stopped"


def test_close_closes_owned_non_cdp_context_and_browser():
    """In non-CDP mode, close() closes both context and browser."""
    fetcher = DetailPageFetcher(vault_base=Path("/tmp/test-vault"))

    fake_context = type("FakeContext", (), {"close": lambda self: setattr(self, "was_closed", True)})()
    fake_browser = type("FakeBrowser", (), {
        "close": lambda self: setattr(self, "was_closed", True),
    })()
    fake_playwright = type("FakePlaywright", (), {
        "stop": lambda self: setattr(self, "was_stopped", True),
    })()

    fetcher._playwright = fake_playwright
    fetcher._browser = fake_browser
    fetcher._context = fake_context
    fetcher._owns_context = True
    fetcher._owns_browser = True

    fetcher.close()

    assert getattr(fake_context, "was_closed", False), "non-CDP context was not closed"
    assert getattr(fake_browser, "was_closed", False), "non-CDP browser was not closed"
    assert getattr(fake_playwright, "was_stopped", False), "playwright was not stopped"
