import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_analysis_pack import (
    build_curated_external_analysis_preview,
    build_curated_external_analysis_preview_markdown,
    load_url_list,
    read_local_materials,
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
