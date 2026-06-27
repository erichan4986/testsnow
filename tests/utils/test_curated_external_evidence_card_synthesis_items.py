"""Tests for curated external evidence card -> SynthesisItem conversion."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

import json

import pytest

from source_adapter import SynthesisItem

from curated_external_evidence_card_synthesis_items import (
    load_curated_external_evidence_card_synthesis_items,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_card(
    *,
    card_id="c1",
    topic="industry_logic",
    title=None,
    source_excerpt="" * 400,
    source_credit=55,
    source_ref="https://example.com/article",
    source_kind="wechat_high_quality_analysis",
    quality_action="preview_only",
    knowledge_eligible=False,
    synthesis_eligible=True,
    synthesis_display_only=True,
    scoring_eligible=False,
    risk_score_eligible=False,
    verification_status="professional_observation",
    normalized_substring_verified=True,
    source_excerpt_hash="h1",
    source_block_hash="bh1",
):
    """Build a minimal valid enriched evidence card."""
    return {
        "schema_version": "periodic_report_narrative_evidence_card.v1",
        "card_id": card_id,
        "topic": topic,
        "source_type": "curated_external_analysis_evidence",
        "source_kind": source_kind,
        "title": title if title is not None else f"title {card_id}",
        "source_excerpt": source_excerpt,
        "source_excerpt_hash": source_excerpt_hash,
        "source_block_hash": source_block_hash,
        "source_ref": source_ref,
        "source_credit": source_credit,
        "quality_action": quality_action,
        "knowledge_eligible": knowledge_eligible,
        "synthesis_eligible": synthesis_eligible,
        "synthesis_display_only": synthesis_display_only,
        "scoring_eligible": scoring_eligible,
        "risk_score_eligible": risk_score_eligible,
        "verification_status": verification_status,
        "normalized_substring_verified": normalized_substring_verified,
    }


def _make_summary(cards, **extra):
    return {
        "schema_version": "curated_external_evidence_cards.v1",
        "wrote_knowledge": False,
        "connected_synthesis": False,
        "cards": cards,
        "excerpt_packs": [
            {
                "card_id": card.get("card_id"),
                "excerpts": [
                    {
                        "source_excerpt_hash": card.get("source_excerpt_hash"),
                        "normalized_substring_verified": card.get("normalized_substring_verified", True),
                    }
                ],
            }
            for card in cards
        ],
        **extra,
    }


def _write_summary(tmp_path, cards, **extra):
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(_make_summary(cards, **extra), ensure_ascii=False), encoding="utf-8")
    return path


def _long_chinese_excerpt(length=400):
    return "公司持续加大研发投入，拓展高端客户，产品竞争力提升。" * (length // 30)


def _neutral_excerpt(length=400):
    base = "今日市场波动较大，投资者情绪保持谨慎，板块轮动明显，个股走势分化。"
    return base * (length // len(base))


def test_accepts_valid_enriched_cards(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="industry_logic", source_excerpt=_long_chinese_excerpt(500)),
        _make_card(card_id="c2", topic="commercialization", source_excerpt=_long_chinese_excerpt(500)),
        _make_card(card_id="c3", topic="earnings_context", source_excerpt=_long_chinese_excerpt(500)),
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(
        str(path), min_cards=3, min_total_excerpt_chars=1000
    )
    assert len(items) == 3
    assert stats["status"] == "ok"
    assert stats["cards_eligible"] == 3
    assert all(isinstance(item, SynthesisItem) for item in items)
    item = items[0]
    assert item.source_platform == "微信公众号精选观察"
    assert item.extra["source_type"] == "curated_external_analysis_evidence"
    assert item.extra["card_id"] == "c1"
    assert item.extra["topic"] == "industry_logic"
    assert item.extra["source_credit"] == 55
    assert item.extra["knowledge_eligible"] is False
    assert item.extra["synthesis_display_only"] is True


def test_accepts_real_phase1_schema_with_fidelity_in_excerpt_pack(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="industry_logic", source_excerpt=_long_chinese_excerpt(500)),
        _make_card(card_id="c2", topic="commercialization", source_excerpt=_long_chinese_excerpt(500)),
        _make_card(card_id="c3", topic="earnings_context", source_excerpt=_long_chinese_excerpt(500)),
    ]
    for card in cards:
        card.pop("normalized_substring_verified")
    path = _write_summary(tmp_path, cards)

    items, stats = load_curated_external_evidence_card_synthesis_items(
        str(path), min_cards=3, min_total_excerpt_chars=1000
    )

    assert len(items) == 3
    assert stats["status"] == "ok"


def test_rejects_excerpt_too_short(tmp_path):
    cards = [_make_card(card_id="c1", topic="industry_logic", source_excerpt="太短")]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert stats["status"] != "ok"
    assert stats["cards_rejected"] >= 1
    assert any("excerpt" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_too_few_chinese_chars(tmp_path):
    excerpt = "a" * 350
    cards = [_make_card(card_id="c1", topic="industry_logic", source_excerpt=excerpt)]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("chinese" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_low_chinese_density(tmp_path):
    # 160 Chinese chars but 7000 total -> density <5%
    excerpt = "公司研发" * 40 + " x" * 3400
    cards = [_make_card(card_id="c1", topic="industry_logic", source_excerpt=excerpt)]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("density" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_product_roadmap(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="product_roadmap", source_excerpt=_long_chinese_excerpt(400))
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("product_roadmap" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_capital_market_without_substance(tmp_path):
    cards = [
        _make_card(
            card_id="c1",
            topic="capital_market_context",
            title="股价大涨，市场情绪高涨",
            source_excerpt=_neutral_excerpt(400),
        )
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("substance" in r.lower() for r in stats["rejection_reasons"])


def test_accepts_capital_market_with_substance(tmp_path):
    cards = [
        _make_card(
            card_id="c1",
            topic="capital_market_context",
            title="公司发布财报",
            source_excerpt=_long_chinese_excerpt(400) + "毛利率提升",
        )
        for _ in range(3)
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 3
    assert stats["status"] == "ok"


def test_rejects_aggregated_market_article_title(tmp_path):
    cards = [
        _make_card(
            card_id="c1",
            topic="industry_logic",
            title="中际旭创（300308）近期的主要市场文章和研报汇总",
            source_excerpt=_long_chinese_excerpt(500),
        )
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("title quality" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_sentiment_event_title(tmp_path):
    cards = [
        _make_card(
            card_id="c1",
            topic="commercialization",
            title="开盘暴涨800%！中际旭创设备供应商登陆科创板",
            source_excerpt=_long_chinese_excerpt(500),
        )
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("title quality" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_numbered_news_digest_excerpt(tmp_path):
    excerpt = (
        "1.美国发起调查，商务部回应；2.寒武纪营收增长；3.从索尼主导到国产突围；"
        "4.全球模块出货增长；5.中东冲突危机扩散。"
        + _long_chinese_excerpt(500)
    )
    cards = [
        _make_card(
            card_id="c1",
            topic="commercialization",
            title="全球五成芯片产能面临风险！中东冲突危机扩散；寒武纪2025年度营收暴涨453%",
            source_excerpt=excerpt,
        )
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("news digest" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_report_metadata_without_substantive_view(tmp_path):
    excerpt = (
        "文中报告节选自天风证券研究所已公开发布研究报告，具体报告内容及相关风险提示等详见完整版报告。"
        "证券研究报告：《全球光模块龙头》 对外发布时间：2026年05月23日。"
        "报告发布机构：天风证券股份有限公司。本报告分析师：王某 SAC 执业证书编号。"
    ) * 4
    cards = [
        _make_card(
            card_id="c1",
            topic="industry_logic",
            title="天风·通信【深度】| 中际旭创：全球AI光互联龙头",
            source_excerpt=excerpt,
        )
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("report metadata" in r.lower() for r in stats["rejection_reasons"])


def test_rejects_source_credit_too_high(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="industry_logic", source_excerpt=_long_chinese_excerpt(400), source_credit=80)
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path))
    assert len(items) == 0
    assert any("source_credit" in r.lower() for r in stats["rejection_reasons"])


def test_enforces_stock_level_min_cards(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="industry_logic", source_excerpt=_long_chinese_excerpt(400)),
        _make_card(card_id="c2", topic="commercialization", source_excerpt=_long_chinese_excerpt(400)),
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(
        str(path), min_cards=3, min_total_excerpt_chars=1200
    )
    assert len(items) == 0
    assert any("min_cards" in r.lower() for r in stats["rejection_reasons"])


def test_enforces_stock_level_min_total_excerpt_chars(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="industry_logic", source_excerpt=_long_chinese_excerpt(400)),
        _make_card(card_id="c2", topic="commercialization", source_excerpt=_long_chinese_excerpt(400)),
        _make_card(card_id="c3", topic="earnings_context", source_excerpt=_long_chinese_excerpt(400)),
    ]
    path = _write_summary(tmp_path, cards)
    items, stats = load_curated_external_evidence_card_synthesis_items(
        str(path), min_cards=3, min_total_excerpt_chars=9999
    )
    assert len(items) == 0
    assert any("min_total_excerpt_chars" in r.lower() for r in stats["rejection_reasons"])


def test_sorts_deterministically(tmp_path):
    cards = [
        _make_card(card_id="c1", topic="cycle_price", source_excerpt=_long_chinese_excerpt(500)),
        _make_card(card_id="c2", topic="industry_logic", source_excerpt=_long_chinese_excerpt(400)),
        _make_card(card_id="c3", topic="industry_logic", source_excerpt=_long_chinese_excerpt(600)),
    ]
    path = _write_summary(tmp_path, cards)
    items, _ = load_curated_external_evidence_card_synthesis_items(str(path), min_cards=3)
    topics = [item.extra["topic"] for item in items]
    assert topics[0] == "industry_logic"
    # longer excerpt first within same topic
    assert items[0].extra["card_id"] == "c3"
    assert items[1].extra["card_id"] == "c2"
    assert items[2].extra["card_id"] == "c1"


def test_emits_traceability_fields(tmp_path):
    cards = [
        _make_card(
            card_id="c1",
            topic="industry_logic",
            source_excerpt=_long_chinese_excerpt(400),
            source_excerpt_hash="seh1",
            source_block_hash="sbh1",
            source_ref="https://example.com/x",
        )
    ]
    path = _write_summary(tmp_path, cards)
    items, _ = load_curated_external_evidence_card_synthesis_items(str(path), min_cards=1, min_total_excerpt_chars=1)
    item = items[0]
    assert item.extra["card_id"] == "c1"
    assert item.extra["source_excerpt_hash"] == "seh1"
    assert item.extra["source_block_hash"] == "sbh1"
    assert item.extra["source_ref"] == "https://example.com/x"
    assert item.extra["topic"] == "industry_logic"


def test_rejects_wrote_knowledge_or_connected_synthesis(tmp_path):
    cards = [_make_card(card_id="c1", topic="industry_logic", source_excerpt=_long_chinese_excerpt(400))]
    path = _write_summary(tmp_path, cards, wrote_knowledge=True)
    items, stats = load_curated_external_evidence_card_synthesis_items(str(path), min_cards=1, min_total_excerpt_chars=1)
    assert len(items) == 0
    assert any("wrote_knowledge" in r.lower() for r in stats["rejection_reasons"])
