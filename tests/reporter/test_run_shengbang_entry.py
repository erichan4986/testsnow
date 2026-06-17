"""Tests for scripts/run_圣邦股份.py single-stock report entry."""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import run_圣邦股份 as run_shengbang


STOCK_NAME = "圣邦股份"


def _sample_post():
    return {
        "title": "样例帖子",
        "content": "c" * 50,
        "url": "https://example.com/post",
        "like": 100,
        "comment": 50,
    }


def test_shengbang_entry_passes_source_intake_config():
    """main(--fast-test) must pass 圣邦股份 Source Intake config from config/stocks.json to PerStockReporter."""
    expected_cfg = {
        STOCK_NAME: {
            "enabled": True,
            "a_stock": {
                "cninfo_announcements": {"enabled": True, "max_items": 12},
                "eastmoney_stock_news": {"enabled": True, "max_items": 10},
                "eastmoney_research_reports": {"enabled": True, "max_items": 8},
            },
            "evidence_notes": {"enabled": True, "dry_run": False},
            "claim_verification": {"enabled": True, "risk_signals": True},
        }
    }
    with patch.object(run_shengbang, "_load_xueqiu_data", return_value=[_sample_post()]):
        with patch.object(run_shengbang, "_load_source_intake_config", return_value=expected_cfg):
            with patch.object(run_shengbang, "PerStockReporter") as mock_reporter:
                with patch.object(run_shengbang, "export_pdf", return_value="reports/圣邦股份_20260615.pdf"):
                    mock_instance = MagicMock()
                    mock_instance.generate_stock_report.return_value = ("reports/圣邦股份_20260615.md", "")
                    mock_reporter.return_value = mock_instance

                    run_shengbang.main(["--fast-test"])

    mock_reporter.assert_called_once()
    kwargs = mock_reporter.call_args.kwargs
    si_configs = kwargs.get("source_intake_configs", {})
    cfg = si_configs.get(STOCK_NAME, {})
    assert cfg.get("enabled") is True
    a_stock = cfg.get("a_stock", {})
    assert a_stock.get("cninfo_announcements", {}).get("max_items") == 12
    assert a_stock.get("eastmoney_stock_news", {}).get("max_items") == 10
    assert a_stock.get("eastmoney_research_reports", {}).get("max_items") == 8
    assert cfg.get("evidence_notes", {}).get("enabled") is True
    assert cfg.get("claim_verification", {}).get("risk_signals") is True


def test_fast_test_mode_skips_zhihu_collector():
    """--fast-test must never instantiate or call ZhihuCollector."""
    with patch.object(run_shengbang, "ZhihuCollector") as mock_zhihu:
        with patch.object(run_shengbang, "_load_xueqiu_data", return_value=[_sample_post()]):
            with patch.object(run_shengbang, "PerStockReporter") as mock_reporter:
                with patch.object(run_shengbang, "export_pdf", return_value="reports/圣邦股份_20260615.pdf"):
                    mock_instance = MagicMock()
                    mock_instance.generate_stock_report.return_value = ("reports/圣邦股份_20260615.md", "")
                    mock_reporter.return_value = mock_instance

                    run_shengbang.main(["--fast-test"])

    mock_zhihu.assert_not_called()


def test_fast_test_mode_reuses_cached_zhihu_data(tmp_path, monkeypatch):
    """--fast-test must reuse zhihu data saved in data/raw/report_input_*_圣邦股份.json."""
    date_str = datetime.now().strftime("%Y%m%d")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)

    cached_zhihu = {"total": 42, "report_items": [{"title": "cached"}], "fast_test": True}
    report_input = {
        "date": date_str,
        "stock_codes": {STOCK_NAME: "300661"},
        "stocks_data": {STOCK_NAME: []},
        "raw_data": {STOCK_NAME: {"zhihu": cached_zhihu}},
    }
    (raw_dir / f"report_input_{date_str}_{STOCK_NAME}.json").write_text(
        json.dumps(report_input, ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(run_shengbang, "__file__", str(scripts_dir / "run_圣邦股份.py"))
    monkeypatch.setattr(run_shengbang, "_load_xueqiu_data", lambda *a, **k: [])
    monkeypatch.setattr(
        run_shengbang, "_load_source_intake_config", lambda *a, **k: {STOCK_NAME: {"enabled": True}}
    )

    with patch.object(run_shengbang, "PerStockReporter") as mock_reporter:
        with patch.object(run_shengbang, "export_pdf", return_value="reports/圣邦股份_20260615.pdf"):
            mock_instance = MagicMock()
            mock_instance.generate_stock_report.return_value = ("reports/圣邦股份_20260615.md", "")
            mock_reporter.return_value = mock_instance

            run_shengbang.main(["--fast-test"])

    call_kwargs = mock_reporter.call_args.kwargs
    assert call_kwargs["raw_data"][STOCK_NAME]["zhihu"]["total"] == 42


def test_load_knowledge_posts_parses_frontmatter_and_body(tmp_path, monkeypatch):
    """_load_knowledge_posts must parse YAML frontmatter and markdown body into post dicts."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    posts_dir = tmp_path / "knowledge" / "10-Stocks" / STOCK_NAME / "posts"
    posts_dir.mkdir(parents=True)
    md = (
        "---\n"
        "source_url: https://xueqiu.com/123/456\n"
        "stock_name: 圣邦股份\n"
        "author: tester\n"
        "title: 测试标题\n"
        "interactions:\n"
        "  likes: 12\n"
        "  comments: 7\n"
        "---\n\n"
        "# 测试标题\n\n"
        "这是正文内容。\n"
    )
    (posts_dir / "test-post.md").write_text(md, encoding="utf-8")

    monkeypatch.setattr(run_shengbang, "__file__", str(scripts_dir / "run_圣邦股份.py"))

    posts = run_shengbang._load_knowledge_posts(STOCK_NAME)
    assert len(posts) == 1
    post = posts[0]
    assert post["title"] == "测试标题"
    assert post["url"] == "https://xueqiu.com/123/456"
    assert "这是正文内容" in post["content"]
    assert post["like"] == 12
    assert post["comment"] == 7


def test_fast_test_uses_knowledge_posts_without_external_fetch(tmp_path, monkeypatch):
    """Without xueqiu cache, --fast-test must use knowledge posts and never call external fetch."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    posts_dir = tmp_path / "knowledge" / "10-Stocks" / STOCK_NAME / "posts"
    posts_dir.mkdir(parents=True)
    md = (
        "---\n"
        "source_url: https://xueqiu.com/123/456\n"
        "title: 知识库帖子\n"
        "interactions:\n"
        "  likes: 20\n"
        "  comments: 10\n"
        "---\n\n"
        "正文：圣邦股份模拟芯片业务分析。\n"
    )
    (posts_dir / "knowledge-post.md").write_text(md, encoding="utf-8")

    monkeypatch.setattr(run_shengbang, "__file__", str(scripts_dir / "run_圣邦股份.py"))
    monkeypatch.setattr(
        run_shengbang, "_load_source_intake_config", lambda *a, **k: {STOCK_NAME: {"enabled": True}}
    )

    with patch.object(run_shengbang, "fetch_all_stocks") as mock_fetch:
        mock_fetch.side_effect = RuntimeError("external fetch should not be called")
        with patch.object(run_shengbang, "PerStockReporter") as mock_reporter:
            with patch.object(run_shengbang, "export_pdf", return_value="reports/圣邦股份_20260615.pdf"):
                mock_instance = MagicMock()
                mock_instance.generate_stock_report.return_value = ("reports/圣邦股份_20260615.md", "")
                mock_reporter.return_value = mock_instance

                run_shengbang.main(["--fast-test"])

    mock_fetch.assert_not_called()
    call_kwargs = mock_reporter.call_args.kwargs
    posts = call_kwargs["stocks_data"][STOCK_NAME]
    assert any(p["title"] == "知识库帖子" and "模拟芯片业务分析" in p["content"] for p in posts)
