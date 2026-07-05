import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from wechat_export_reader import (
    build_wechat_export_preview,
    build_wechat_export_preview_markdown,
    read_wechat_exports,
)


def test_read_wechat_exports_supports_markdown_json_text_and_html(tmp_path: Path):
    exports = tmp_path / "wechat"
    exports.mkdir()
    (exports / "article.md").write_text(
        "---\n"
        "title: 光芯片深度\n"
        "author: 半导体号\n"
        "url: https://mp.weixin.qq.com/s/a\n"
        "publish_time: 2026-06-20\n"
        "---\n\n"
        "# 光芯片深度\n\nAI 算力带动 1.6T 光模块。",
        encoding="utf-8",
    )
    (exports / "article.json").write_text(
        json.dumps(
            {
                "title": "模拟芯片观察",
                "author": "产业号",
                "publish_time": "2026-06-21",
                "url": "https://mp.weixin.qq.com/s/b",
                "content": "模拟芯片国产替代，车规产品推进。",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (exports / "note.txt").write_text("公众号纯文本：CPO 产业链。", encoding="utf-8")
    (exports / "page.html").write_text("<html><body><h1>AI芯片</h1><p>端侧算力增长。</p></body></html>", encoding="utf-8")
    (exports / "ignore.pdf").write_text("ignore", encoding="utf-8")

    items = read_wechat_exports(exports)

    assert [item["title"] for item in items] == ["光芯片深度", "模拟芯片观察", "note.txt", "page.html"]
    assert items[0]["source_kind"] == "wechat_export"
    assert items[0]["author"] == "半导体号"
    assert items[0]["url"] == "https://mp.weixin.qq.com/s/a"
    assert "1.6T 光模块" in items[0]["content"]
    assert "车规产品推进" in items[1]["content"]
    assert "CPO 产业链" in items[2]["content"]
    assert "端侧算力增长" in items[3]["content"]
    assert all(item["knowledge_eligible"] is False for item in items)
    assert all(item["synthesis_eligible"] is False for item in items)
    assert all(item["scoring_eligible"] is False for item in items)
    assert all(item["risk_score_eligible"] is False for item in items)


def test_wechat_preview_dedupes_same_url_and_marks_preview_only(tmp_path: Path):
    exports = tmp_path / "wechat"
    exports.mkdir()
    (exports / "a.md").write_text(
        "---\ntitle: 原文\nurl: https://mp.weixin.qq.com/s/same\n---\n\n光模块深度分析。",
        encoding="utf-8",
    )
    (exports / "b.txt").write_text("光模块深度分析。", encoding="utf-8")

    summary = build_wechat_export_preview(exports)

    assert summary["status"] == "ok"
    assert summary["counts"] == {"wechat_export": 1}
    assert len(summary["items"]) == 1
    assert summary["items"][0]["quality_action"] == "preview_only"
    assert len(summary["deduped_sources"]) == 1
    assert summary["deduped_sources"][0]["reason"] == "content_fingerprint"


def test_wechat_preview_markdown_contains_guardrails():
    summary = {
        "status": "ok",
        "items": [
            {
                "source_kind": "wechat_export",
                "title": "光芯片深度",
                "author": "半导体号",
                "publish_time": "2026-06-20",
                "url": "https://mp.weixin.qq.com/s/a",
                "path": "/tmp/a.md",
                "content": "AI 算力带动 1.6T 光模块。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            }
        ],
        "counts": {"wechat_export": 1},
        "deduped_sources": [],
        "errors": [],
    }

    markdown = build_wechat_export_preview_markdown(summary)

    assert "# WeChat Export Preview" in markdown
    assert "不写 Knowledge" in markdown
    assert "光芯片深度" in markdown
    assert "knowledge_eligible: `false`" in markdown


def test_wechat_reader_drops_export_shell_noise(tmp_path: Path):
    exports = tmp_path / "wechat"
    exports.mkdir()
    (exports / "noise.md").write_text(
        "#js_row_immersive_stream_wrap { max-width: 667px; margin: 0 auto; }\n"
        "在小说阅读器读本章\n"
        "去阅读\n"
        "在小说阅读器中沉浸阅读\n"
        "公众号记得加星标⭐️，第一时间看推送不会错过。\n"
        "原创 作者 [半导体行业观察](javascript:void\\(0\\);)\n"
        "\n"
        "真正正文：AI 算力带动模拟芯片需求。\n",
        encoding="utf-8",
    )

    items = read_wechat_exports(exports)

    content = items[0]["content"]
    assert "max-width" not in content
    assert "小说阅读器" not in content
    assert "加星标" not in content
    assert "javascript:void" not in content
    assert "真正正文" in content
