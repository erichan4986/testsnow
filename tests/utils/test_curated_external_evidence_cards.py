from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_evidence_cards import (
    build_curated_external_evidence_cards,
    normalized_hash,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _item(
    *,
    title: str = "黑芝麻智能华山A2000拿下首个量产项目定点",
    content: str = "2月24日，黑芝麻智能宣布华山A2000拿下首个量产项目定点。该项目预计2026年量产，但仍缺少车型名称和收入节奏。",
    source_kind: str = "wechat_customer_order_or_design_win",
    topic: str = "commercialization",
    url: str = "https://mp.weixin.qq.com/s/design-win",
    source_ref: str | None = None,
    synthesis_display_only: bool = True,
    knowledge_eligible: bool = False,
    scoring_eligible: bool = False,
    risk_score_eligible: bool = False,
) -> dict:
    return {
        "title": title,
        "content": content,
        "source_type": "curated_external_analysis",
        "source_kind": source_kind,
        "verification_status": "professional_observation",
        "quality_action": "preview_only",
        "knowledge_eligible": knowledge_eligible,
        "synthesis_eligible": True,
        "synthesis_display_only": synthesis_display_only,
        "scoring_eligible": scoring_eligible,
        "risk_score_eligible": risk_score_eligible,
        "topic": topic,
        "url": url,
        "source_ref": source_ref or url,
        "account": "高工智能汽车",
        "publish_time": "2026-02-24",
    }


def _write_jsonl(path: Path, items: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)
        + ("\n" if items else ""),
        encoding="utf-8",
    )
    return path


def test_builds_cards_and_excerpt_packs_with_existing_schema_fields(tmp_path: Path):
    path = _write_jsonl(tmp_path / "items.jsonl", [_item()])

    result = build_curated_external_evidence_cards(path, stock_name="黑芝麻智能")

    assert result["schema_version"] == "curated_external_evidence_cards.v1"
    assert result["stock_name"] == "黑芝麻智能"
    assert result["status"] == "ok"
    assert len(result["cards"]) == 1
    assert len(result["excerpt_packs"]) == 1

    card = result["cards"][0]
    assert card["schema_version"] == "periodic_report_narrative_evidence_card.v1"
    assert card["card_id"].startswith("curated:commercialization:")
    assert card["source_type"] == "curated_external_analysis_evidence"
    assert card["topic"] == "commercialization"
    assert card["card_type"] == "commercialization"
    assert card["evidence_refs"] == [card["source_ref"]]
    assert card["source_excerpt_hash"] == normalized_hash(card["source_excerpt"])
    assert card["source_block_hash"] == normalized_hash(_item()["content"])
    assert card["knowledge_eligible"] is False
    assert card["synthesis_eligible"] is True
    assert card["synthesis_display_only"] is True
    assert card["scoring_eligible"] is False
    assert card["risk_score_eligible"] is False
    assert card["verification_status"] == "professional_observation"

    pack = result["excerpt_packs"][0]
    assert pack["card_id"] == card["card_id"]
    assert pack["source_ref"] == card["source_ref"]
    assert pack["source_content_hash"] == card["source_block_hash"]
    assert len(pack["excerpts"]) == 1
    excerpt = pack["excerpts"][0]
    assert excerpt["source_excerpt_hash"] == card["source_excerpt_hash"]
    assert excerpt["normalized_substring_verified"] is True
    assert _normalize(excerpt["text"]) in _normalize(_item()["content"])


def test_filters_non_display_only_or_unsafe_items(tmp_path: Path):
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(title="safe"),
            _item(title="not display", synthesis_display_only=False),
            _item(title="knowledge unsafe", knowledge_eligible=True),
            _item(title="scoring unsafe", scoring_eligible=True),
            _item(title="risk unsafe", risk_score_eligible=True),
        ],
    )

    result = build_curated_external_evidence_cards(path)

    assert [card["title"] for card in result["cards"]] == ["safe"]


def test_deduplicates_by_canonical_url_and_preserves_multiple_sources(tmp_path: Path):
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(
                title="A2000定点转载一",
                url="https://mp.weixin.qq.com/s/design-win?utm_source=a#frag",
                source_ref="https://mp.weixin.qq.com/s/design-win?utm_source=a#frag",
            ),
            _item(
                title="A2000定点转载二",
                url="https://mp.weixin.qq.com/s/design-win",
                source_ref="https://mp.weixin.qq.com/s/design-win",
            ),
        ],
    )

    result = build_curated_external_evidence_cards(path)

    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["source_ref"] == "https://mp.weixin.qq.com/s/design-win"
    assert sorted(card["source_refs"]) == [
        "https://mp.weixin.qq.com/s/design-win",
        "https://mp.weixin.qq.com/s/design-win?utm_source=a#frag",
    ]
    assert result["deduped_sources"][0]["reason"] == "canonical_url"


def test_deduplicates_by_content_fingerprint_without_url(tmp_path: Path):
    content = "同一段行业分析内容，强调客户定点、2026年量产和收入节奏仍待验证。"
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(title="转载一", content=content, url="", source_ref="file-a.md"),
            _item(title="转载二", content=content, url="", source_ref="file-b.md"),
        ],
    )

    result = build_curated_external_evidence_cards(path)

    assert len(result["cards"]) == 1
    assert sorted(result["cards"][0]["source_refs"]) == ["file-a.md", "file-b.md"]
    assert result["deduped_sources"][0]["reason"] == "content_fingerprint"


def test_excerpt_budget_limits_excerpt_length_and_reports_budget(tmp_path: Path):
    content = "A" * 2000
    path = _write_jsonl(tmp_path / "items.jsonl", [_item(content=content)])

    result = build_curated_external_evidence_cards(path, max_excerpt_chars=120)

    excerpt = result["excerpt_packs"][0]["excerpts"][0]
    assert len(excerpt["text"]) <= 120
    assert result["excerpt_budget"]["max_excerpt_chars"] == 120
    assert result["excerpt_budget"]["total_excerpt_chars"] <= 120


def test_long_form_excerpt_selects_later_high_signal_sentences(tmp_path: Path):
    generic_intro = "公司持续关注行业发展，保持稳健经营，并围绕客户需求推进相关业务。" * 22
    rd_sentence = "2025年研发开支为14.17亿元，研发开支占营收比例高达173.38%，三费合计18.03亿元。"
    price_sentence = "公司部分存储芯片产品价格有合理范围上调，上游供应商价格持续上调，产能供给紧张。"
    content = generic_intro + rd_sentence + "同时，公司继续推进日常运营。" + price_sentence
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(
                title="财报与价格周期深度分析",
                content=content,
                topic="earnings_context",
                source_kind="wechat_high_quality_analysis",
            )
        ],
    )

    result = build_curated_external_evidence_cards(path, stock_name="黑芝麻智能", max_excerpt_chars=260)

    card = result["cards"][0]
    assert "研发开支为14.17亿元" in card["source_excerpt"]
    assert "上游供应商价格持续上调" in card["source_excerpt"]
    assert len(card["source_excerpt"]) <= 260

    pack = result["excerpt_packs"][0]
    assert pack["combined_source_excerpt_hash"] == card["source_excerpt_hash"]
    assert len(pack["excerpts"]) >= 2
    for excerpt in pack["excerpts"]:
        assert excerpt["normalized_substring_verified"] is True
        assert _normalize(excerpt["text"]) in _normalize(content)


def test_long_high_signal_intro_cannot_consume_entire_excerpt_budget(tmp_path: Path):
    long_intro = (
        (
            "黑芝麻智能财报显示，公司营收收入同比增长，净利润亏损，毛利率保持稳定，"
            "研发费用、客户订单、量产商业化、国产替代、行业景气与资本开支均是本文关注重点，"
            "但这一段只是概览铺垫并没有给出具体拆分，"
        )
        * 8
        + "因此需要继续往后阅读。"
    )
    rd_sentence = "财报显示，2025年研发开支为14.17亿元，三费合计18.03亿元，为营收的2.19倍。"
    price_sentence = "普冉股份表示，上游供应商价格持续上调，封测原材料持续上涨且产能供给持续紧张。"
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(
                title="财报与价格周期深度分析",
                content=long_intro + rd_sentence + price_sentence,
                topic="earnings_context",
                source_kind="wechat_high_quality_analysis",
            )
        ],
    )

    result = build_curated_external_evidence_cards(path, stock_name="黑芝麻智能", max_excerpt_chars=500)

    card = result["cards"][0]
    assert "研发开支为14.17亿元" in card["source_excerpt"]
    assert "上游供应商价格持续上调" in card["source_excerpt"]
    assert len(card["source_excerpt"]) <= 500
    assert len(result["excerpt_packs"][0]["excerpts"]) >= 2


def test_excerpts_record_matched_terms_and_selection_reason(tmp_path: Path):
    content = (
        "财报显示，2025年研发开支为14.17亿元，三费合计18.03亿元，为营收的2.19倍。"
        "公司产品价格上调，产能供给持续紧张。"
    )
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(
                title="财报与价格周期深度分析",
                content=content,
                topic="earnings_context",
                source_kind="wechat_high_quality_analysis",
            )
        ],
    )

    result = build_curated_external_evidence_cards(path, stock_name="黑芝麻智能")

    excerpt = result["excerpt_packs"][0]["excerpts"][0]
    assert "matched_terms" in excerpt
    assert "研发" in excerpt["matched_terms"]
    assert "三费" in excerpt["matched_terms"]
    assert excerpt["selection_reason"].startswith("matched_terms:")


def test_operational_tail_is_cleaned_before_excerpt_selection(tmp_path: Path):
    content = (
        "财报显示，公司2025年营业收入8.22亿元，同比增长73.42%。"
        "往期热文推荐 1 客户订单爆发，2 研发费用高增，3 价格周期上行。"
        "联系我们，报告询价、商务合作、进群交流请联系小编。阅读原文"
    )
    path = _write_jsonl(
        tmp_path / "items.jsonl",
        [
            _item(
                title="财报分析",
                content=content,
                topic="earnings_context",
                source_kind="wechat_high_quality_analysis",
            )
        ],
    )

    result = build_curated_external_evidence_cards(path, stock_name="黑芝麻智能")

    card = result["cards"][0]
    assert "营业收入8.22亿元" in card["source_excerpt"]
    assert "往期热文推荐" not in card["source_excerpt"]
    assert "联系我们" not in card["source_excerpt"]
    assert "阅读原文" not in card["source_excerpt"]


def test_normalized_hash_matches_sha256():
    text = "A  B\nC"
    expected = hashlib.sha256("A B C".encode("utf-8")).hexdigest()
    assert normalized_hash(text) == expected
