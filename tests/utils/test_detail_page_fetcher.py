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
