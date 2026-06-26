from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import pytest

from curated_external_to_synthesis_items import (
    TOPIC_ORDER,
    build_curated_external_synthesis_items,
    map_source_kind_to_topic,
)


WECHAT_SOURCE_KINDS_TO_TOPICS = [
    ("wechat_high_quality_analysis", "industry_logic"),
    ("wechat_customer_order_or_design_win", "commercialization"),
    ("wechat_capacity_supply_chain_signal", "commercialization"),
    ("wechat_industry_cycle_price_signal", "cycle_price"),
    ("wechat_earnings_financial_context", "earnings_context"),
    ("wechat_certification_policy_standard", "certification_policy"),
    ("wechat_product_signal", "product_roadmap"),
    ("wechat_product_or_event_signal", "product_roadmap"),
    ("wechat_capital_market_context", "capital_market_context"),
]


def _candidate(
    title: str = "标题",
    source_kind: str = "wechat_high_quality_analysis",
    content_preview: str = "摘要",
    account: str = "测试号",
    publish_time: str = "2026-06-01",
    url: str = "https://mp.weixin.qq.com/s/test",
    quality_action: str = "preview_only",
    knowledge_eligible: bool = False,
    synthesis_eligible: bool = False,
    scoring_eligible: bool = False,
    risk_score_eligible: bool = False,
    extra: dict | None = None,
):
    item = {
        "title": title,
        "source_kind": source_kind,
        "source_type": source_kind,
        "content_preview": content_preview,
        "account": account,
        "publish_time": publish_time,
        "url": url,
        "quality_action": quality_action,
        "knowledge_eligible": knowledge_eligible,
        "synthesis_eligible": synthesis_eligible,
        "scoring_eligible": scoring_eligible,
        "risk_score_eligible": risk_score_eligible,
        "discovery_score": 70,
    }
    if extra:
        item.update(extra)
    return item


def _write_jsonl(path: Path, items: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)
        + ("\n" if items else ""),
        encoding="utf-8",
    )
    return path


def test_load_jsonl_candidates_into_display_synthesis_items(tmp_path: Path):
    input_path = tmp_path / "candidates.jsonl"
    _write_jsonl(
        input_path,
        [
            _candidate(
                title="深度分析",
                source_kind="wechat_high_quality_analysis",
                content_preview="行业逻辑内容",
            ),
            _candidate(
                title="新品发布",
                source_kind="wechat_product_signal",
                content_preview="产品路线图内容",
            ),
        ],
    )

    result = build_curated_external_synthesis_items(input_path, stock_name="测试股")
    items = result["items"]
    assert len(items) == 2
    assert result["counts"]["industry_logic"] == 1
    assert result["counts"]["product_roadmap"] == 1

    for item in items:
        assert item["source_type"] == "curated_external_analysis"
        assert item["verification_status"] == "professional_observation"
        assert item["knowledge_eligible"] is False
        assert item["synthesis_eligible"] is True
        assert item["synthesis_display_only"] is True
        assert item["scoring_eligible"] is False
        assert item["risk_score_eligible"] is False
        assert "title" in item
        assert "content" in item
        assert "url" in item
        assert "account" in item
        assert "publish_time" in item
        assert "source_ref" in item
        assert "topic" in item


def test_source_ref_uses_url_for_traceability(tmp_path: Path):
    input_path = tmp_path / "candidates.jsonl"
    _write_jsonl(
        input_path,
        [
            _candidate(
                title="客户定点",
                source_kind="wechat_customer_order_or_design_win",
                url="https://mp.weixin.qq.com/s/design-win",
            )
        ],
    )

    result = build_curated_external_synthesis_items(input_path)

    assert result["items"][0]["source_ref"] == "https://mp.weixin.qq.com/s/design-win"


def test_sort_prefers_newer_items_with_same_topic_and_score(tmp_path: Path):
    input_path = tmp_path / "candidates.jsonl"
    _write_jsonl(
        input_path,
        [
            _candidate(title="旧材料", publish_time="2026-01-01"),
            _candidate(title="新材料", publish_time="2026-06-01"),
        ],
    )

    result = build_curated_external_synthesis_items(input_path)

    assert [item["title"] for item in result["items"]] == ["新材料", "旧材料"]


def test_filters_unsafe_eligibility_items(tmp_path: Path):
    input_path = tmp_path / "candidates.jsonl"
    _write_jsonl(
        input_path,
        [
            _candidate(title="safe"),
            _candidate(title="knowledge unsafe", knowledge_eligible=True),
            _candidate(title="scoring unsafe", scoring_eligible=True),
            _candidate(title="risk unsafe", risk_score_eligible=True),
            _candidate(title="not preview", quality_action="keep"),
        ],
    )

    result = build_curated_external_synthesis_items(input_path)
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "safe"


@pytest.mark.parametrize("source_kind, expected_topic", WECHAT_SOURCE_KINDS_TO_TOPICS)
def test_wechat_source_kind_maps_to_topic(source_kind: str, expected_topic: str):
    assert map_source_kind_to_topic(source_kind, {}) == expected_topic


def test_curated_preview_defaults_to_industry_logic():
    assert map_source_kind_to_topic("curated_preview", {}) == "industry_logic"


def test_local_file_with_existing_topic_is_preserved():
    assert map_source_kind_to_topic("local_file", {"topic": "cycle_price"}) == "cycle_price"
    assert map_source_kind_to_topic("local_file", {"category": "earnings_context"}) == "earnings_context"


def test_unknown_source_kind_falls_back_to_industry_logic():
    assert map_source_kind_to_topic("unknown_kind", {}) == "industry_logic"


def test_max_items_limits_output(tmp_path: Path):
    input_path = tmp_path / "candidates.jsonl"
    _write_jsonl(
        input_path,
        [
            _candidate(title=f"item {i}", source_kind="wechat_high_quality_analysis")
            for i in range(5)
        ],
    )

    result = build_curated_external_synthesis_items(input_path, max_items=2)
    assert len(result["items"]) == 2


def test_empty_jsonl_returns_empty(tmp_path: Path):
    input_path = tmp_path / "empty.jsonl"
    input_path.write_text("", encoding="utf-8")
    result = build_curated_external_synthesis_items(input_path)
    assert result["items"] == []
    assert result["status"] == "empty"


def test_topic_order_includes_required_topics():
    required = {
        "industry_logic",
        "commercialization",
        "product_roadmap",
        "cycle_price",
        "earnings_context",
        "certification_policy",
        "capital_market_context",
        "other_observation",
    }
    assert required.issubset(set(TOPIC_ORDER))
