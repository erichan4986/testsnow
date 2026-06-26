import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_candidate_discovery import (  # noqa: E402
    build_curated_external_candidate_discovery,
    build_curated_external_candidate_discovery_markdown,
)


def test_discovery_filters_wechat_drop_and_dedupes_same_url_with_wechat_preferred(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text(
        "\n".join(
            [
                "SGM3810 长文 | https://mp.weixin.qq.com/s/abc123?utm_source=x",
                "产业长文 | https://36kr.com/p/123456",
            ]
        ),
        encoding="utf-8",
    )
    selector_file = tmp_path / "wechat_selector.jsonl"
    selector_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "action": "product_signal",
                        "category": "product_signal",
                        "reason": "product_release_matches_company_theme",
                        "quality_score": 65,
                        "matched_terms": ["AI 电源"],
                        "candidate": {
                            "title": "圣邦微电子推出SGM3810，让LCD电源设计更简单",
                            "url": "https://mp.weixin.qq.com/s/abc123",
                            "account": "圣邦微电子",
                            "publish_time": "2026-06-01",
                            "digest": "SGM3810 适用于 LCD 偏置电源。",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "action": "drop",
                        "candidate": {
                            "title": "圣邦微电子展会邀请",
                            "url": "https://mp.weixin.qq.com/s/drop",
                            "digest": "展会邀请。",
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(
        url_list_path=url_list,
        wechat_selector_file=selector_file,
    )

    assert summary["status"] == "ok"
    assert summary["counts"] == {"url_candidate": 1, "wechat_product_signal": 1}
    assert len(summary["items"]) == 2
    assert all(item["quality_action"] == "preview_only" for item in summary["items"])
    assert all(item["knowledge_eligible"] is False for item in summary["items"])
    assert all(item["synthesis_eligible"] is False for item in summary["items"])
    assert all(item["scoring_eligible"] is False for item in summary["items"])
    assert all(item["risk_score_eligible"] is False for item in summary["items"])
    assert "圣邦微电子展会邀请" not in json.dumps(summary["items"], ensure_ascii=False)
    assert summary["deduped_sources"][0]["reason"] == "normalized_url"
    assert summary["deduped_sources"][0]["kept"]["source_kind"] == "wechat_product_signal"
    assert summary["deduped_sources"][0]["duplicate"]["source_kind"] == "url_candidate"


def test_discovery_dedupes_content_fingerprint_with_local_material_preferred(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("转载页 | https://example.com/repost\n", encoding="utf-8")
    curated_summary = tmp_path / "curated_summary.json"
    curated_summary.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_kind": "jina_url",
                        "title": "转载页",
                        "url": "https://example.com/repost",
                        "content": "作者深度分析：光芯片产业链进入 AI 算力时代，硅光与薄膜铌酸锂路线并行。",
                        "quality_action": "preview_only",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "author-original.md").write_text(
        "作者深度分析：光芯片产业链进入 AI 算力时代，硅光与薄膜铌酸锂路线并行。",
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(
        url_list_path=url_list,
        curated_preview_file=curated_summary,
        materials_dir=materials_dir,
    )

    assert summary["counts"] == {"local_file": 1}
    assert len(summary["items"]) == 1
    assert summary["items"][0]["source_kind"] == "local_file"
    assert summary["items"][0]["title"] == "author-original.md"
    assert len(summary["deduped_sources"]) == 2
    assert {record["duplicate"]["source_kind"] for record in summary["deduped_sources"]} == {
        "url_candidate",
        "curated_preview",
    }


def test_discovery_filters_candidates_older_than_since_date(tmp_path: Path) -> None:
    selector_file = tmp_path / "selector.jsonl"
    selector_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "action": "product_signal",
                        "candidate": {
                            "title": "近期新品",
                            "url": "https://mp.weixin.qq.com/s/recent",
                            "publish_time": "2026-06-01 09:00:00",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "action": "keep",
                        "candidate": {
                            "title": "过旧分析",
                            "url": "https://mp.weixin.qq.com/s/old",
                            "publish_time": "2022-01-01 09:00:00",
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(
        wechat_selector_file=selector_file,
        since_date="2025-12-27",
    )

    assert [item["title"] for item in summary["items"]] == ["近期新品"]


def test_discovery_preserves_video_subtitle_source_kind_from_curated_preview(tmp_path: Path) -> None:
    video_preview = tmp_path / "video_preview.json"
    video_preview.write_text(
        json.dumps(
            {
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
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(curated_preview_file=video_preview)

    assert summary["counts"] == {"video_subtitle": 1}
    assert summary["items"][0]["source_kind"] == "video_subtitle"


def test_discovery_markdown_records_preview_only_items_and_dedupes() -> None:
    summary = {
        "status": "ok",
        "items": [
            {
                "source_kind": "wechat_product_signal",
                "title": "圣邦微电子推出SGM25890",
                "url": "https://mp.weixin.qq.com/s/power",
                "content_preview": "90A Smart Power Stage。",
                "quality_action": "preview_only",
                "knowledge_eligible": False,
                "synthesis_eligible": False,
                "scoring_eligible": False,
                "risk_score_eligible": False,
                "matched_terms": ["AI 电源"],
            }
        ],
        "counts": {"wechat_product_signal": 1},
        "deduped_sources": [
            {
                "reason": "normalized_url",
                "kept": {"source_kind": "wechat_product_signal", "title": "圣邦微电子推出SGM25890"},
                "duplicate": {"source_kind": "url_candidate", "title": "转载链接"},
            }
        ],
    }

    markdown = build_curated_external_candidate_discovery_markdown(summary)

    assert "# Curated External Candidate Discovery Preview" in markdown
    assert "Preview-only" in markdown
    assert "wechat_product_signal: `1`" in markdown
    assert "knowledge_eligible: `false`" in markdown
    assert "synthesis_eligible: `false`" in markdown
    assert "normalized_url" in markdown
