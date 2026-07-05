import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_video_subtitles import (  # noqa: E402
    build_video_subtitle_preview,
    build_video_subtitle_preview_markdown,
    clean_subtitle_text,
    write_video_subtitle_preview,
)


def test_clean_subtitle_text_removes_vtt_noise_and_repeated_lines() -> None:
    raw = """WEBVTT

00:00:01.000 --> 00:00:04.000 align:start position:0%
<c>AI server power modules are moving to higher current.</c>

00:00:04.000 --> 00:00:08.000
AI server power modules are moving to higher current.

00:00:08.000 --> 00:00:10.000
国产模拟芯片进入车规验证。
"""

    cleaned = clean_subtitle_text(raw)

    assert "WEBVTT" not in cleaned
    assert "-->" not in cleaned
    assert "<c>" not in cleaned
    assert cleaned.count("AI server power modules") == 1
    assert "国产模拟芯片进入车规验证" in cleaned


def test_build_video_subtitle_preview_uses_explicit_urls_and_keeps_preview_only(tmp_path: Path) -> None:
    url_list = tmp_path / "videos.txt"
    url_list.write_text(
        "\n".join(
            [
                "AI 电源访谈 | https://www.youtube.com/watch?v=abc123",
                "B站模拟芯片圆桌 | https://www.bilibili.com/video/BV1xx411c7mD",
            ]
        ),
        encoding="utf-8",
    )

    def fake_fetch(url: str, timeout: int = 90):
        return {
            "title": "AI 电源访谈" if "youtube" in url else "B站模拟芯片圆桌",
            "author": "Semiconductor Channel",
            "publish_time": "2026-06-01",
            "language": "zh",
            "content": "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nAI 电源和车规模拟芯片讨论。",
        }

    summary = build_video_subtitle_preview(url_list_path=url_list, fetch_subtitle=fake_fetch)

    assert summary["status"] == "ok"
    assert summary["counts"] == {"video_subtitle": 2}
    assert len(summary["items"]) == 2
    assert all(item["source_kind"] == "video_subtitle" for item in summary["items"])
    assert all(item["quality_action"] == "preview_only" for item in summary["items"])
    assert all(item["knowledge_eligible"] is False for item in summary["items"])
    assert all(item["synthesis_eligible"] is False for item in summary["items"])
    assert all(item["scoring_eligible"] is False for item in summary["items"])
    assert all(item["risk_score_eligible"] is False for item in summary["items"])
    assert "00:00" not in summary["items"][0]["content"]
    assert summary["items"][0]["platform"] == "youtube"
    assert summary["items"][1]["platform"] == "bilibili"


def test_build_video_subtitle_preview_records_fetch_errors(tmp_path: Path) -> None:
    url_list = tmp_path / "videos.txt"
    url_list.write_text("坏视频 | https://www.youtube.com/watch?v=missing\n", encoding="utf-8")

    def fake_fetch(url: str, timeout: int = 90):
        raise RuntimeError("no usable subtitles")

    summary = build_video_subtitle_preview(url_list_path=url_list, fetch_subtitle=fake_fetch)

    assert summary["status"] == "empty"
    assert summary["items"] == []
    assert summary["errors"] == [
        {"url": "https://www.youtube.com/watch?v=missing", "error": "no usable subtitles"}
    ]


def test_write_video_subtitle_preview_writes_markdown_and_json(tmp_path: Path) -> None:
    url_list = tmp_path / "videos.txt"
    url_list.write_text("AI 电源访谈 | https://www.youtube.com/watch?v=abc123\n", encoding="utf-8")
    output = tmp_path / "preview.md"
    json_output = tmp_path / "preview.json"

    def fake_fetch(url: str, timeout: int = 90):
        return {
            "title": "AI 电源访谈",
            "author": "Semiconductor Channel",
            "publish_time": "2026-06-01",
            "language": "zh",
            "content": "AI 电源和车规模拟芯片讨论。",
        }

    summary = write_video_subtitle_preview(
        url_list_path=url_list,
        output_path=output,
        json_output_path=json_output,
        fetch_subtitle=fake_fetch,
    )

    assert summary["preview_path"] == str(output)
    assert summary["json_output_path"] == str(json_output)
    markdown = output.read_text(encoding="utf-8")
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert "# Video Subtitle Preview" in markdown
    assert payload["counts"] == {"video_subtitle": 1}
    assert payload["items"][0]["source_kind"] == "video_subtitle"
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False


def test_video_subtitle_markdown_mentions_preview_only() -> None:
    markdown = build_video_subtitle_preview_markdown(
        {
            "status": "ok",
            "counts": {"video_subtitle": 1},
            "items": [
                {
                    "source_kind": "video_subtitle",
                    "title": "AI 电源访谈",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "content": "AI 电源和车规模拟芯片讨论。",
                    "quality_action": "preview_only",
                    "knowledge_eligible": False,
                    "synthesis_eligible": False,
                    "scoring_eligible": False,
                    "risk_score_eligible": False,
                }
            ],
            "errors": [],
        }
    )

    assert "Preview-only" in markdown
    assert "source_kind: `video_subtitle`" in markdown
    assert "knowledge_eligible: `false`" in markdown
