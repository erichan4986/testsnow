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


def test_discovery_filters_curated_preview_error_pages(tmp_path: Path) -> None:
    curated_summary = tmp_path / "curated_summary.json"
    curated_summary.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_kind": "jina_url",
                        "title": "坏链接",
                        "url": "https://www.36kr.com/p/missing",
                        "content": "Title: 36氪_让一部分人先看到未来 Published Time: 2026 Warning: Target URL returned error 404: Not Found",
                        "quality_action": "preview_only",
                        "knowledge_eligible": False,
                        "synthesis_eligible": False,
                        "scoring_eligible": False,
                        "risk_score_eligible": False,
                    },
                    {
                        "source_kind": "jina_url",
                        "title": "光模块，一路狂飙",
                        "url": "https://www.36kr.com/p/good",
                        "content": "光模块是 AI 算力基础设施的重要环节，800G 与 1.6T 需求增长。",
                        "quality_action": "preview_only",
                        "knowledge_eligible": False,
                        "synthesis_eligible": False,
                        "scoring_eligible": False,
                        "risk_score_eligible": False,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(curated_preview_file=curated_summary)

    assert summary["counts"] == {"curated_preview": 1}
    assert [item["title"] for item in summary["items"]] == ["光模块，一路狂飙"]


def test_discovery_filters_and_scores_candidates_by_theme_keywords(tmp_path: Path) -> None:
    curated_summary = tmp_path / "curated_summary.json"
    curated_summary.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_kind": "jina_url",
                        "title": "光模块，一路狂飙",
                        "url": "https://www.36kr.com/p/optical",
                        "content": "光模块和 CPO 受益于 AI 算力需求。",
                        "quality_action": "preview_only",
                    },
                    {
                        "source_kind": "jina_url",
                        "title": "模拟芯片国产替代进入深水区",
                        "url": "https://example.com/analog",
                        "content": "圣邦股份覆盖模拟芯片、信号链、电源管理、车规、ADC 和 LDO 产品方向。",
                        "quality_action": "preview_only",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(
        curated_preview_file=curated_summary,
        theme_keywords="圣邦,模拟芯片,信号链,电源管理,车规,ADC,LDO",
        min_theme_score=1,
    )

    assert summary["counts"] == {"curated_preview": 1}
    item = summary["items"][0]
    assert item["title"] == "模拟芯片国产替代进入深水区"
    assert item["theme_score"] > 0
    assert set(item["matched_theme_terms"]) >= {"圣邦", "模拟芯片", "信号链", "电源管理"}
    assert "theme_match" in item["ranking_reasons"]


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


def test_discovery_dedupes_same_title_and_keeps_higher_ranked_candidate(tmp_path: Path) -> None:
    curated_summary = tmp_path / "curated_summary.json"
    curated_summary.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_kind": "jina_url",
                        "title": "光芯片：AI算力时代的光子革命",
                        "url": "https://36kr.com/p/repost",
                        "content": "较短转载摘要。",
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
    materials_dir = tmp_path / "materials"
    materials_dir.mkdir()
    (materials_dir / "光芯片：AI算力时代的光子革命.md").write_text(
        "光芯片：AI算力时代的光子革命\n\n" + "硅光、薄膜铌酸锂、CPO、800G、1.6T 与 AI 算力互联。" * 20,
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(
        curated_preview_file=curated_summary,
        materials_dir=materials_dir,
    )

    assert summary["counts"] == {"local_file": 1}
    assert summary["items"][0]["source_kind"] == "local_file"
    assert summary["items"][0]["discovery_score"] > 0
    assert "human_curated_local_file" in summary["items"][0]["ranking_reasons"]
    assert summary["deduped_sources"][0]["reason"] == "title_fingerprint"
    assert summary["deduped_sources"][0]["kept"]["source_kind"] == "local_file"
    assert summary["deduped_sources"][0]["duplicate"]["source_kind"] == "curated_preview"


def test_discovery_sorts_candidates_by_quality_rank(tmp_path: Path) -> None:
    url_list = tmp_path / "urls.txt"
    url_list.write_text("泛链接 | https://example.com/weak\n", encoding="utf-8")
    selector_file = tmp_path / "wechat_selector.jsonl"
    selector_file.write_text(
        json.dumps(
            {
                "action": "product_signal",
                "quality_score": 85,
                "matched_terms": ["AI 电源", "车规"],
                "candidate": {
                    "title": "圣邦微电子推出90A Smart Power Stage SGM25890",
                    "url": "https://mp.weixin.qq.com/s/power",
                    "publish_time": "2026-06-01",
                    "digest": "面向 AI 服务器电源的 90A Smart Power Stage，包含电流检测与高频电源场景。",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(
        url_list_path=url_list,
        wechat_selector_file=selector_file,
    )

    assert [item["source_kind"] for item in summary["items"]] == [
        "wechat_product_signal",
        "url_candidate",
    ]
    top = summary["items"][0]
    assert top["discovery_score"] > summary["items"][1]["discovery_score"]
    assert "selector_quality_score" in top["ranking_reasons"]
    assert "matched_terms" in top["ranking_reasons"]
    assert "dated_candidate" in top["ranking_reasons"]


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


def test_discovery_accepts_targeted_wechat_classification_items(tmp_path: Path) -> None:
    selector_file = tmp_path / "targeted_wechat.jsonl"
    selector_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "title": "中际旭创：全球AI光互联龙头",
                        "url": "https://mp.weixin.qq.com/s/analysis",
                        "publish_date": "2026-05-24",
                        "account": "海陆清风",
                        "digest": "深度受益 AI 算力全球扩容，1.6T 引领新周期。",
                        "classification": "high_quality_analysis",
                        "quality_action": "preview_only",
                        "knowledge_eligible": False,
                        "synthesis_eligible": False,
                        "scoring_eligible": False,
                        "risk_score_eligible": False,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "title": "开盘暴涨800%！中际旭创设备供应商登陆科创板",
                        "url": "https://mp.weixin.qq.com/s/order",
                        "publish_date": "2026-04-24",
                        "account": "半导体产业纵横",
                        "digest": "设备供应商推出 1.6T 光模块核心测试仪器。",
                        "classification": "customer_order_or_design_win",
                        "quality_action": "preview_only",
                        "knowledge_eligible": False,
                        "synthesis_eligible": False,
                        "scoring_eligible": False,
                        "risk_score_eligible": False,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "title": "招聘启事",
                        "url": "https://mp.weixin.qq.com/s/drop",
                        "publish_date": "2026-06-01",
                        "classification": "drop",
                        "quality_action": "preview_only",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    summary = build_curated_external_candidate_discovery(wechat_selector_file=selector_file)

    assert summary["counts"] == {
        "wechat_customer_order_or_design_win": 1,
        "wechat_high_quality_analysis": 1,
    }
    items_by_title = {item["title"]: item for item in summary["items"]}
    analysis = items_by_title["中际旭创：全球AI光互联龙头"]
    assert analysis["wechat_signal_category"] == "high_quality_analysis"
    assert analysis["source_type"] == "wechat_high_quality_analysis"
    assert analysis["publish_time"] == "2026-05-24"
    assert analysis["quality_action"] == "preview_only"
    assert analysis["knowledge_eligible"] is False
    assert analysis["synthesis_eligible"] is False
    assert "招聘启事" not in items_by_title


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
