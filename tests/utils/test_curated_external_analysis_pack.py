import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_analysis_pack import (
    build_curated_external_analysis_preview,
    build_curated_external_analysis_preview_markdown,
    load_url_list,
    read_local_materials,
    read_wechat_exports,
)


def test_load_url_list_accepts_plain_and_labeled_lines(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.md"
    url_list.write_text(
        "\n".join(
            [
                "# 精选材料",
                "https://example.com/a",
                "半导体深度文章 | https://example.com/b?x=1",
                "- https://www.youtube.com/watch?v=abc",
                "",
            ]
        ),
        encoding="utf-8",
    )

    urls = load_url_list(url_list)

    assert urls == [
        {"title": "", "url": "https://example.com/a"},
        {"title": "半导体深度文章", "url": "https://example.com/b?x=1"},
        {"title": "", "url": "https://www.youtube.com/watch?v=abc"},
    ]


def test_read_local_materials_supports_md_txt_and_html(tmp_path: Path) -> None:
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "article.md").write_text("# 标题\n\n模拟芯片产业链分析。", encoding="utf-8")
    (materials_dir / "note.txt").write_text("光模块 800G 需求跟踪。", encoding="utf-8")
    (materials_dir / "page.html").write_text("<html><body><h1>AI芯片</h1><p>算力需求增长。</p></body></html>", encoding="utf-8")
    (materials_dir / "ignored.pdf").write_text("ignore", encoding="utf-8")

    items = read_local_materials(materials_dir)

    assert [item["title"] for item in items] == ["article.md", "note.txt", "page.html"]
    assert "模拟芯片产业链分析" in items[0]["content"]
    assert "光模块 800G" in items[1]["content"]
    assert "AI芯片" in items[2]["content"]
    assert "算力需求增长" in items[2]["content"]


def test_preview_fetches_jina_urls_reads_local_files_and_defers_video(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text(
        "\n".join(
            [
                "产业媒体 | https://example.com/semiconductor",
                "https://www.youtube.com/watch?v=abc",
            ]
        ),
        encoding="utf-8",
    )
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "local.md").write_text("本地长文：CPO 和 1.6T 光模块。", encoding="utf-8")

    fetched_urls = []

    def fake_fetch(url: str, timeout: int = 20) -> str:
        fetched_urls.append(url)
        return "Title: Example\n\nMarkdown Content:\n\n网页正文：半导体国产替代。"

    summary = build_curated_external_analysis_preview(
        url_list_path=url_list,
        materials_dir=materials_dir,
        fetch_text=fake_fetch,
    )

    assert fetched_urls == ["https://example.com/semiconductor"]
    assert summary["status"] == "ok"
    assert summary["counts"] == {"jina_url": 1, "local_file": 1, "video_subtitle_deferred": 1}
    assert [item["source_kind"] for item in summary["items"]] == [
        "jina_url",
        "video_subtitle_deferred",
        "local_file",
    ]
    assert summary["items"][0]["quality_action"] == "preview_only"
    assert summary["items"][0]["knowledge_eligible"] is False
    assert summary["items"][1]["content"] == "视频字幕接口占位：本版本不调用 yt-dlp。"


def test_preview_dedupes_normalized_duplicate_urls_before_fetch(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text(
        "\n".join(
            [
                "PC | http://www.36kr.com/p/123456?utm_source=x",
                "Mobile | https://m.36kr.com/p/123456/",
            ]
        ),
        encoding="utf-8",
    )
    fetched_urls = []

    def fake_fetch(url: str, timeout: int = 20) -> str:
        fetched_urls.append(url)
        return "同一篇光模块深度文章，800G 和 1.6T 是核心方向。"

    summary = build_curated_external_analysis_preview(
        url_list_path=url_list,
        fetch_text=fake_fetch,
    )

    assert fetched_urls == ["http://www.36kr.com/p/123456?utm_source=x"]
    assert summary["counts"] == {"jina_url": 1}
    assert len(summary["items"]) == 1
    assert len(summary["deduped_sources"]) == 1
    assert summary["deduped_sources"][0]["duplicate"]["url"] == "https://m.36kr.com/p/123456/"


def test_preview_dedupes_same_content_across_url_and_local_file_with_local_preferred(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("转载页 | https://example.com/repost\n", encoding="utf-8")
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "wechat-export.txt").write_text(
        "作者深度分析：光芯片产业链进入 AI 算力时代，硅光与薄膜铌酸锂路线并行。",
        encoding="utf-8",
    )

    def fake_fetch(url: str, timeout: int = 20) -> str:
        return "作者深度分析：光芯片产业链进入 AI 算力时代，硅光与薄膜铌酸锂路线并行。"

    summary = build_curated_external_analysis_preview(
        url_list_path=url_list,
        materials_dir=materials_dir,
        fetch_text=fake_fetch,
    )

    assert summary["counts"] == {"local_file": 1}
    assert len(summary["items"]) == 1
    assert summary["items"][0]["source_kind"] == "local_file"
    assert summary["items"][0]["title"] == "wechat-export.txt"
    assert len(summary["deduped_sources"]) == 1
    assert summary["deduped_sources"][0]["kept"]["source_kind"] == "local_file"
    assert summary["deduped_sources"][0]["duplicate"]["source_kind"] == "jina_url"


def test_preview_markdown_is_display_only_and_contains_items(tmp_path: Path) -> None:
    summary = {
        "status": "ok",
        "items": [
            {
                "source_kind": "local_file",
                "title": "local.md",
                "url": "",
                "path": "/tmp/local.md",
                "content": "本地精选材料正文。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            }
        ],
        "counts": {"local_file": 1},
        "errors": [],
    }

    markdown = build_curated_external_analysis_preview_markdown(summary)

    assert "# Curated External Analysis Preview" in markdown
    assert "不写 Knowledge，不接 synthesis，不进入评分或风险评分" in markdown
    assert "local.md" in markdown
    assert "本地精选材料正文" in markdown
    assert "knowledge_eligible: `false`" in markdown


def test_read_wechat_exports_reads_md_with_frontmatter_and_isolates_product_signal(tmp_path: Path) -> None:
    wechat_dir = tmp_path / "wechat"
    wechat_dir.mkdir()
    (wechat_dir / "article.md").write_text(
        "---\n"
        "title: 圣邦微电子推出SGM3810\n"
        "url: https://mp.weixin.qq.com/s/abc123\n"
        "account: 圣邦微电子\n"
        "publish_time: 2026-06-23 08:56:40\n"
        "action: product_signal\n"
        "---\n\n"
        "#js_row { max-width: 667px; }\n\n"
        "圣邦微电子 圣邦微电子 ;)\n\n"
        "[](\n\n"
        "![cover](https://example.com/cover.jpg)\n\n"
        "**圣邦微电子推出SGM3810**，适用于TFT LCD偏置。\n",
        encoding="utf-8",
    )

    items = read_wechat_exports(wechat_dir)

    assert len(items) == 1
    item = items[0]
    assert item["source_kind"] == "wechat_product_signal"
    assert item["source_type"] == "wechat_product_signal"
    assert item["title"] == "圣邦微电子推出SGM3810"
    assert item["url"] == "https://mp.weixin.qq.com/s/abc123"
    assert item["quality_action"] == "preview_only"
    assert item["knowledge_eligible"] is False
    assert item["synthesis_eligible"] is False
    assert item["scoring_eligible"] is False
    assert item["risk_score_eligible"] is False
    assert "SGM3810" in item["content"]
    assert "圣邦微电子 圣邦微电子" not in item["content"]
    assert "#js_row" not in item["content"]
    assert "![cover]" not in item["content"]
    assert ";)" not in item["content"]
    assert "[](" not in item["content"]


def test_read_wechat_exports_respects_max_items(tmp_path: Path) -> None:
    wechat_dir = tmp_path / "wechat"
    wechat_dir.mkdir()
    for idx in range(5):
        (wechat_dir / f"article_{idx}.md").write_text(
            f"---\ntitle: Article {idx}\nurl: https://mp.weixin.qq.com/s/{idx}\n---\n\nBody {idx}.",
            encoding="utf-8",
        )

    items = read_wechat_exports(wechat_dir, max_items=2)

    assert len(items) == 2


def test_build_preview_separates_wechat_product_signals(tmp_path: Path) -> None:
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "local.md").write_text("本地精选：模拟芯片分析。", encoding="utf-8")

    wechat_dir = tmp_path / "wechat"
    wechat_dir.mkdir()
    (wechat_dir / "sgm.md").write_text(
        "---\n"
        "title: 圣邦微电子推出SGM42148Q\n"
        "url: https://mp.weixin.qq.com/s/def456\n"
        "---\n\n"
        "车规级电子保险丝控制器。",
        encoding="utf-8",
    )

    summary = build_curated_external_analysis_preview(
        materials_dir=materials_dir,
        wechat_export_dir=wechat_dir,
    )

    assert summary["status"] == "ok"
    assert summary["counts"] == {"local_file": 1, "wechat_product_signal": 1}
    kinds = [item["source_kind"] for item in summary["items"]]
    assert "wechat_product_signal" in kinds
    assert "local_file" in kinds
    for item in summary["items"]:
        assert item["knowledge_eligible"] is False
        assert item["synthesis_eligible"] is False
        assert item["scoring_eligible"] is False
        assert item["risk_score_eligible"] is False


def test_preview_markdown_groups_wechat_product_signals_separately() -> None:
    summary = {
        "status": "ok",
        "items": [
            {
                "source_kind": "local_file",
                "source_type": "local_file",
                "title": "local.md",
                "url": "",
                "path": "/tmp/local.md",
                "content": "本地材料。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            },
            {
                "source_kind": "wechat_product_signal",
                "source_type": "wechat_product_signal",
                "title": "SGM25890",
                "url": "https://mp.weixin.qq.com/s/xyz",
                "path": "/tmp/wechat/sgm.md",
                "content": "AI电源新品。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            },
        ],
        "counts": {"local_file": 1, "wechat_product_signal": 1},
        "errors": [],
    }

    markdown = build_curated_external_analysis_preview_markdown(summary)

    assert "## WeChat Product Signals" in markdown
    assert "SGM25890" in markdown
    assert "local.md" in markdown
    assert "source_kind: `wechat_product_signal`" in markdown
    assert "source_type: `wechat_product_signal`" in markdown
    assert "knowledge_eligible: `false`" in markdown


def test_preview_markdown_groups_by_source_kind_not_dict_value() -> None:
    base_item = {
        "title": "same-title",
        "url": "https://example.com/same",
        "path": "/tmp/same.md",
        "content": "同一段正文。",
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }
    summary = {
        "status": "ok",
        "items": [
            {**base_item, "source_kind": "local_file", "source_type": "local_file"},
            {**base_item, "source_kind": "wechat_product_signal", "source_type": "wechat_product_signal"},
        ],
        "counts": {"local_file": 1, "wechat_product_signal": 1},
        "errors": [],
    }

    markdown = build_curated_external_analysis_preview_markdown(summary)

    assert "## Items" in markdown
    assert "source_kind: `local_file`" in markdown
    assert "## WeChat Product Signals" in markdown
    assert "source_kind: `wechat_product_signal`" in markdown


def test_read_wechat_exports_ignores_unsupported_files(tmp_path: Path) -> None:
    wechat_dir = tmp_path / "wechat"
    wechat_dir.mkdir()
    (wechat_dir / "article.md").write_text(
        "---\ntitle: Keep\nurl: https://mp.weixin.qq.com/s/keep\n---\n\n正文。",
        encoding="utf-8",
    )
    (wechat_dir / "ignore.pdf").write_text("ignore", encoding="utf-8")

    items = read_wechat_exports(wechat_dir)

    assert len(items) == 1
    assert items[0]["title"] == "Keep"


def test_preview_markdown_lists_deduped_sources() -> None:
    summary = {
        "status": "ok",
        "items": [
            {
                "source_kind": "local_file",
                "title": "wechat-export.txt",
                "url": "",
                "path": "/tmp/wechat-export.txt",
                "content": "正文。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
            }
        ],
        "counts": {"local_file": 1},
        "errors": [],
        "deduped_sources": [
            {
                "reason": "content_fingerprint",
                "kept": {"source_kind": "local_file", "title": "wechat-export.txt", "url": "", "path": "/tmp/wechat-export.txt"},
                "duplicate": {"source_kind": "jina_url", "title": "转载页", "url": "https://example.com/repost", "path": ""},
            }
        ],
    }

    markdown = build_curated_external_analysis_preview_markdown(summary)

    assert "## Deduped Sources" in markdown
    assert "content_fingerprint" in markdown
    assert "转载页" in markdown
