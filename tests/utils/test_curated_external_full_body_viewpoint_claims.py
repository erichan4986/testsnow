from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_full_body_viewpoint_claims import (
    FullBodyExtractorError,
    THEME_PROFILES,
    _longest_common_substring_positions,
    build_source_packets,
    build_viewpoint_digest,
    llm_extractor_factory,
    multipass_llm_extractor_factory,
    normalized_hash,
    repair_quote,
    validate_claim,
)


def _claim_contract() -> dict[str, Any]:
    return {
        "schema_version": "curated_external_viewpoint_claim.v1",
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _source_packet(
    source_id: str = "curated-source:test:1",
    content: str = "外部文章提示，市场传言公司因材料短缺将交付计划从1500万降至1200万只。",
    title: str = "测试文章",
    url: str = "https://example.com/s1",
) -> dict[str, Any]:
    return {
        "schema_version": "curated_external_source_packet.v1",
        "source_id": source_id,
        "stock_name": "TestCo",
        "title": title,
        "account": "测试账号",
        "publish_time": "2026-04-01",
        "source_kind": "wechat_high_quality_analysis",
        "source_ref": url,
        "source_url": url,
        "content": content,
        "source_content_hash": normalized_hash(content),
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "synthesis_eligible": True,
        "synthesis_display_only": True,
        "verification_status": "professional_observation",
    }


def _evidence_hashes(packet: dict[str, Any], quote: str) -> list[dict[str, str]]:
    return [
        {
            "source_id": packet["source_id"],
            "source_block_hash": packet["source_content_hash"],
            "source_quote_hash": normalized_hash(quote),
        }
    ]


def test_normalized_hash_is_stable():
    assert normalized_hash("  a\n\tb  ") == normalized_hash("a b")


class TestSourcePacketConversion:
    def test_build_source_packets_from_jsonl(self, tmp_path: Path):
        jsonl = tmp_path / "sources.jsonl"
        jsonl.write_text(
            json.dumps(
                {
                    "title": "文章一",
                    "account": "账号一",
                    "publish_time": "2026-04-01",
                    "source_kind": "wechat_high_quality_analysis",
                    "source_ref": "https://example.com/a",
                    "content": "这是正文一。",
                    "quality_action": "preview_only",
                    "knowledge_eligible": False,
                    "scoring_eligible": False,
                    "risk_score_eligible": False,
                },
                ensure_ascii=False,
            )
            + "\n"
            + json.dumps(
                {
                    "title": "文章二",
                    "account": "账号二",
                    "publish_time": "2026-04-02",
                    "source_kind": "wechat_capacity_supply_chain_signal",
                    "url": "https://example.com/b",
                    "content": "这是正文二。",
                    "quality_action": "preview_only",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        packets = build_source_packets(str(jsonl), stock_name="TestCo", max_sources=10)
        assert len(packets) == 2
        assert packets[0]["schema_version"] == "curated_external_source_packet.v1"
        assert packets[0]["source_id"].startswith("curated-source:")
        assert packets[0]["source_content_hash"] == normalized_hash("这是正文一。")
        assert packets[1]["source_ref"] == "https://example.com/b"

    def test_build_source_packets_respects_max_sources(self, tmp_path: Path):
        jsonl = tmp_path / "sources.jsonl"
        lines = []
        for i in range(5):
            lines.append(
                json.dumps(
                    {"title": f"文章{i}", "content": f"正文{i}", "source_ref": f"https://example.com/{i}"},
                    ensure_ascii=False,
                )
            )
        jsonl.write_text("\n".join(lines), encoding="utf-8")
        packets = build_source_packets(str(jsonl), stock_name="TestCo", max_sources=2)
        assert len(packets) == 2


class TestQuoteRepair:
    def test_longest_common_substring_positions_returns_longest_match(self):
        early = "EARLY_FRAGMENT_1234567890"
        later = "LATER_UNIQUE_FRAGMENT_WITH_NPO_XPO_2027_TIMELINE"
        quote = f"{early} plus {later}"
        source = f"intro {early} body {later} tail"
        positions = _longest_common_substring_positions(quote, source)
        assert positions
        length, quote_start, _ = positions[0]
        assert quote[quote_start : quote_start + length].strip() == later

    def test_exact_match_no_repair_needed(self):
        source = "中际旭创表示，订单获取及产品交付均在正常有序进行，不存在上述情况。"
        quote = "订单获取及产品交付均在正常有序进行，不存在上述情况。"
        repaired, status = repair_quote(quote, source)
        assert status == "exact"
        assert repaired == quote

    def test_repair_finds_nearby_substring_with_long_exact_fragment(self):
        source = "4月12日，有投资者在互动平台向中际旭创询问一则市场传言，该传言称中际旭创由于光芯片的短缺，800G的交付计划从1500万降到了1200万只。"
        quote = "中际旭创由于光芯片短缺，800G交付计划从1500万降到了1200万只"
        repaired, status = repair_quote(quote, source)
        assert status == "repaired"
        assert repaired in source
        assert "800G的交付计划从1500万降到了1200万只" in repaired

    def test_repair_prefers_longest_unique_fragment_over_early_short_fragment(self):
        source = (
            "前置共同短片段1234567890。"
            "正文后半段高信号内容包括NPO和XPO将在2027年进入量产时间表。"
        )
        quote = (
            "前置共同短片段1234567890，但是更关键的是"
            "后半段高信号内容包括NPO和XPO将在2027年进入量产时间表"
        )
        repaired, status = repair_quote(quote, source)
        assert status == "repaired"
        assert repaired in source
        assert "后半段高信号内容包括NPO和XPO将在2027年进入量产时间表" in repaired

    def test_repair_rejects_cross_source(self):
        source = "这是来源A的正文。"
        quote = "这是来源B的句子。"
        repaired, status = repair_quote(quote, source)
        assert status == "failed"
        assert repaired == ""

    def test_repair_rejects_multiple_candidates(self):
        source = "公司订单正常。公司订单正常。"
        quote = "公司订单正常进行"
        repaired, status = repair_quote(quote, source)
        assert status == "failed"

    def test_repair_rejects_short_exact_fragment(self):
        source = "中际旭创2026年Q1营收194.96亿元。"
        quote = "2026年营收194.96亿元"
        repaired, status = repair_quote(quote, source)
        assert status == "failed"


class TestValidateClaim:
    def test_valid_claim_passes(self):
        content = "外部文章提示，市场传言公司因材料短缺将交付计划从1500万降至1200万只。"
        packet = _source_packet(content=content)
        packets_by_id = {packet["source_id"]: packet}
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "watch_variable",
            "topic": "commercialization",
            "claim": "外部文章提示交付计划下调的传言。",
            "source_quote": content,
            "source_quote_hash": normalized_hash(content),
            "why_incremental": "baseline未涉及。",
            "baseline_overlap": "none",
            "source_id": packet["source_id"],
            "evidence_refs": [packet["source_id"]],
            "evidence_hashes": _evidence_hashes(packet, content),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        ok, reason, meta = validate_claim(claim, packets_by_id, baseline_fingerprint=set())
        assert ok is True
        assert reason == "ok"
        assert meta["repaired"] is False

    def test_invalid_display_only_flags_rejected(self):
        content = "外部文章提示交付计划下调。"
        packet = _source_packet(content=content)
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "watch_variable",
            "topic": "commercialization",
            "claim": "外部文章提示交付计划下调。",
            "source_quote": content,
            "source_quote_hash": normalized_hash(content),
            "why_incremental": "baseline未涉及。",
            "baseline_overlap": "none",
            "source_id": packet["source_id"],
            "evidence_refs": [packet["source_id"]],
            "evidence_hashes": _evidence_hashes(packet, content),
            "quality_action": "preview_only",
            "knowledge_eligible": True,
            "synthesis_display_only": False,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        ok, reason, _ = validate_claim(claim, {packet["source_id"]: packet}, baseline_fingerprint=set())
        assert ok is False
        assert "display-only" in reason.lower()

    def test_missing_evidence_ref_rejected(self):
        packet = _source_packet()
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "watch_variable",
            "topic": "commercialization",
            "claim": "claim text",
            "source_quote": packet["content"],
            "source_quote_hash": normalized_hash(packet["content"]),
            "why_incremental": "baseline未涉及。",
            "baseline_overlap": "none",
            "source_id": packet["source_id"],
            "evidence_refs": ["curated-source:missing:1"],
            "evidence_hashes": _evidence_hashes(packet, packet["content"]),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        ok, reason, _ = validate_claim(claim, {packet["source_id"]: packet}, baseline_fingerprint=set())
        assert ok is False
        assert "evidence ref" in reason.lower()

    def test_duplicate_baseline_fact_dropped(self):
        baseline = "公司2025年营收8.22亿元，净亏损14.25亿元。"
        packet = _source_packet(content="财报显示，公司2025年营收8.22亿元，同比增长73%。")
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "context_extension",
            "topic": "earnings_context",
            "claim": "公司营收8.22亿元。",
            "source_quote": packet["content"],
            "source_quote_hash": normalized_hash(packet["content"]),
            "why_incremental": "baseline未涉及。",
            "baseline_overlap": "none",
            "source_id": packet["source_id"],
            "evidence_refs": [packet["source_id"]],
            "evidence_hashes": _evidence_hashes(packet, packet["content"]),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        from curated_external_full_body_viewpoint_claims import baseline_fact_fingerprint

        fp = baseline_fact_fingerprint(baseline)
        ok, reason, _ = validate_claim(claim, {packet["source_id"]: packet}, baseline_fingerprint=fp)
        assert ok is False
        assert "duplicate" in reason.lower()

    def test_explicit_duplicate_baseline_overlap_rejected(self):
        packet = _source_packet(content="外部文章提示，市场传言交付计划可能调整。")
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "watch_variable",
            "topic": "commercialization",
            "claim": "外部文章提示交付计划可能调整。",
            "source_quote": packet["content"],
            "source_quote_hash": normalized_hash(packet["content"]),
            "why_incremental": "baseline已覆盖。",
            "baseline_overlap": "duplicate",
            "source_id": packet["source_id"],
            "evidence_refs": [packet["source_id"]],
            "evidence_hashes": _evidence_hashes(packet, packet["content"]),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        ok, reason, _ = validate_claim(claim, {packet["source_id"]: packet}, baseline_fingerprint=set())
        assert ok is False
        assert "duplicate" in reason.lower()

    def test_overclaim_strong_term_rejected(self):
        content = "外部文章提示交付计划下调。"
        packet = _source_packet(content=content)
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "watch_variable",
            "topic": "commercialization",
            "claim": "公司已确认交付计划下调。",
            "source_quote": content,
            "source_quote_hash": normalized_hash(content),
            "why_incremental": "baseline未涉及。",
            "baseline_overlap": "none",
            "source_id": packet["source_id"],
            "evidence_refs": [packet["source_id"]],
            "evidence_hashes": _evidence_hashes(packet, content),
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        ok, reason, _ = validate_claim(claim, {packet["source_id"]: packet}, baseline_fingerprint=set())
        assert ok is False
        assert "overclaim" in reason.lower()

    def test_evidence_hash_mismatch_rejected(self):
        content = "外部文章提示交付计划下调。"
        packet = _source_packet(content=content)
        claim = {
            "schema_version": "curated_external_viewpoint_claim.v1",
            "claim_type": "watch_variable",
            "topic": "commercialization",
            "claim": "外部文章提示交付计划下调。",
            "source_quote": content,
            "source_quote_hash": normalized_hash(content),
            "why_incremental": "baseline未涉及。",
            "baseline_overlap": "none",
            "source_id": packet["source_id"],
            "evidence_refs": [packet["source_id"]],
            "evidence_hashes": [
                {
                    "source_id": packet["source_id"],
                    "source_block_hash": "wrong-block-hash",
                    "source_quote_hash": normalized_hash(content),
                }
            ],
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
        }
        ok, reason, _ = validate_claim(claim, {packet["source_id"]: packet}, baseline_fingerprint=set())
        assert ok is False
        assert "evidence hash" in reason.lower()


class TestLLMExtractor:
    def test_malformed_json_fail_closed(self):
        fake_client = _FakeLLMClient(json_payload="not json")
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        with pytest.raises(FullBodyExtractorError) as exc_info:
            extractor([_source_packet()], "baseline", set())
        assert exc_info.value.status == "parse_failed"

    def test_llm_extractor_retries_once_after_malformed_json(self):
        source = _source_packet(
            content="外部产业分析认为800G交付传言仍需跟踪，公司否认相关交付下调。"
        )
        fake_client = _SequencedRawLLMClient(
            [
                "not json",
                json.dumps(
                    {
                        "claims": [
                            {
                                **_claim_contract(),
                                "claim_type": "dissent",
                                "topic": "supply_delivery_capacity",
                                "claim": "外部文章提示800G交付传言仍需跟踪，公司否认相关下调。",
                                "source_quote": source["content"],
                                "why_incremental": "baseline未讨论。",
                                "baseline_overlap": "none",
                                "source_id": source["source_id"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
            max_parse_retries=1,
        )
        claims = extractor([source], "baseline", set())
        assert len(claims) == 1
        assert fake_client._calls == 2

    def test_llm_extractor_returns_valid_claims(self):
        source = _source_packet(
            content="外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        )
        fake_client = _FakeLLMClient(
            claims=[
                {
                    **_claim_contract(),
                    "claim_type": "novel_mechanism",
                    "topic": "commercialization",
                    "claim": "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成。",
                    "source_quote": source["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
            ]
        )
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        claims = extractor([source], "baseline", set())
        assert len(claims) == 1
        assert claims[0]["schema_version"] == "curated_external_viewpoint_claim.v1"
        assert claims[0]["source_quote_hash"] == normalized_hash(source["content"])

    def test_llm_extractor_preserves_source_metadata_for_report_citations(self):
        source = _source_packet(
            content="外部产业分析认为NPO和XPO将在2027年进入量产时间表。",
            title="ZIA Insight | 中际旭创：从光模块龙头向平台转变",
            url="https://example.com/zia",
        )
        fake_client = _FakeLLMClient(
            claims=[
                {
                    **_claim_contract(),
                    "claim_type": "novel_mechanism",
                    "topic": "technology_path",
                    "claim": "外部产业分析认为NPO和XPO将在2027年进入量产时间表。",
                    "source_quote": source["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
            ]
        )
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        claims = extractor([source], "baseline", set())
        assert claims[0]["source_title"] == source["title"]
        assert claims[0]["source_account"] == source["account"]
        assert claims[0]["source_ref"] == source["source_ref"]
        assert claims[0]["source_url"] == source["source_url"]

    def test_llm_quote_repair_is_applied(self):
        source = _source_packet(
            content="有投资者在互动平台向中际旭创询问一则市场传言，该传言称中际旭创由于光芯片的短缺，800G的交付计划从1500万降到了1200万只。"
        )
        fake_client = _FakeLLMClient(
            claims=[
                {
                    **_claim_contract(),
                    "claim_type": "dissent",
                    "topic": "commercialization",
                    "claim": "市场传言800G交付计划从1500万降至1200万只。",
                    "source_quote": "中际旭创由于光芯片短缺，800G交付计划从1500万降到了1200万只",
                    "why_incremental": "baseline未涉及。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
            ]
        )
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        claims = extractor([source], "baseline", set())
        assert len(claims) == 1
        assert "800G的交付计划从1500万降到了1200万只" in claims[0]["source_quote"]

    def test_llm_extractor_retains_all_valid_claims(self):
        sources = [
            _source_packet(
                source_id=f"curated-source:test:{idx}",
                content=f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                url=f"https://example.com/{idx}",
            )
            for idx in range(7)
        ]
        fake_client = _FakeLLMClient(
            claims=[
                {
                    **_claim_contract(),
                    "claim_type": "novel_mechanism",
                    "topic": "commercialization",
                    "claim": f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                    "source_quote": source["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
                for idx, source in enumerate(sources)
            ]
        )
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        claims = extractor(sources, "baseline", set())
        assert len(claims) == 7

    def test_multipass_extractor_merges_pass_outputs(self):
        sources = [
            _source_packet(
                source_id=f"curated-source:test:{idx}",
                content=f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                url=f"https://example.com/{idx}",
            )
            for idx in range(3)
        ]
        fake_client = _SequencedLLMClient(
            [
                {"claims": [
                    {
                        **_claim_contract(),
                        "claim_type": "watch_variable",
                        "topic": "supply_chain",
                        "claim": "外部文章提示第0条供应链变量。",
                        "source_quote": sources[0]["content"],
                        "why_incremental": "baseline未讨论。",
                        "baseline_overlap": "none",
                        "source_id": sources[0]["source_id"],
                    }
                ]},
                {"claims": [
                    {
                        **_claim_contract(),
                        "claim_type": "novel_mechanism",
                        "topic": "technology_path",
                        "claim": "外部文章提示第1条技术路径变量。",
                        "source_quote": sources[1]["content"],
                        "why_incremental": "baseline未讨论。",
                        "baseline_overlap": "none",
                        "source_id": sources[1]["source_id"],
                    }
                ]},
            ]
        )
        extractor = multipass_llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
            pass_specs=[
                {"name": "supply_chain", "focus": "供应链变量"},
                {"name": "technology_path", "focus": "技术路径变量"},
            ],
        )
        claims = extractor(sources, "baseline", set())
        assert len(claims) == 2
        assert {claim["topic"] for claim in claims} == {"supply_chain", "technology_path"}

    def test_multipass_prompt_includes_800g_delivery_rumor_focus(self):
        source = _source_packet(
            content="外部文章提示800G交付计划传言仍需跟踪。",
        )
        fake_client = _CaptureLLMClient(
            {
                "claims": [
                    {
                        **_claim_contract(),
                        "claim_type": "watch_variable",
                        "topic": "supply_delivery_capacity",
                        "claim": "外部文章提示800G交付计划传言仍需跟踪。",
                        "source_quote": source["content"],
                        "why_incremental": "baseline未讨论。",
                        "baseline_overlap": "none",
                        "source_id": source["source_id"],
                    }
                ]
            }
        )
        extractor = multipass_llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        extractor([source], "baseline", set())
        assert any("800G" in prompt and "1500万" in prompt and "1200万" in prompt for prompt in fake_client.prompts)

    def test_llm_extractor_retries_api_failure_then_success(self):
        source = _source_packet(
            content="外部产业分析认为800G交付传言仍需跟踪，公司否认相关交付下调。"
        )
        payload = {
            "claims": [
                {
                    **_claim_contract(),
                    "claim_type": "dissent",
                    "topic": "supply_delivery_capacity",
                    "claim": "外部文章提示800G交付传言仍需跟踪，公司否认相关下调。",
                    "source_quote": source["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
            ]
        }
        fake_client = _FailingThenSuccessLLMClient(failures=1, payload=payload)
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
            max_api_retries=2,
            sleep_fn=_noop_sleep,
        )
        claims = extractor([source], "baseline", set())
        assert len(claims) == 1
        assert fake_client._calls == 2

    def test_llm_extractor_fails_closed_after_api_retries_exhausted(self):
        source = _source_packet(
            content="外部产业分析认为800G交付传言仍需跟踪，公司否认相关交付下调。"
        )
        fake_client = _FailingThenSuccessLLMClient(failures=10, payload={"claims": []})
        extractor = llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
            max_api_retries=2,
            sleep_fn=_noop_sleep,
        )
        with pytest.raises(FullBodyExtractorError) as exc_info:
            extractor([source], "baseline", set())
        assert exc_info.value.status == "extractor_failed"
        assert fake_client._calls == 3

    def test_multipass_extractor_continues_when_one_pass_fails(self):
        source = _source_packet(
            content="外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        )
        payload = {
            "claims": [
                {
                    **_claim_contract(),
                    "claim_type": "novel_mechanism",
                    "topic": "technology_path",
                    "claim": "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成。",
                    "source_quote": source["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
            ]
        }
        # First pass exhausts 3 API attempts (initial + 2 retries); second pass succeeds on call 4.
        fake_client = _FailingThenSuccessLLMClient(failures=3, payload=payload)
        extractor = multipass_llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
            max_api_retries=2,
            sleep_fn=_noop_sleep,
            pass_specs=[
                {"name": "failing_pass", "focus": "this pass will fail"},
                {"name": "ok_pass", "focus": "this pass returns a claim"},
            ],
        )
        claims = extractor([source], "baseline", set())
        assert len(claims) == 1
        assert claims[0]["topic"] == "technology_path"
        failed_passes = getattr(claims, "failed_passes", [])
        assert len(failed_passes) == 1
        assert failed_passes[0]["pass"] == "failing_pass"
        assert failed_passes[0]["status"] == "extractor_failed"

    def test_multipass_extractor_fails_closed_when_all_passes_fail(self):
        source = _source_packet(
            content="外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        )
        # Two passes, each exhausts 3 attempts: 6 failures total.
        fake_client = _FailingThenSuccessLLMClient(failures=6, payload={"claims": []})
        extractor = multipass_llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
            max_api_retries=2,
            sleep_fn=_noop_sleep,
            pass_specs=[
                {"name": "failing_pass_1", "focus": "fail"},
                {"name": "failing_pass_2", "focus": "fail"},
            ],
        )
        with pytest.raises(FullBodyExtractorError) as exc_info:
            extractor([source], "baseline", set())
        assert exc_info.value.status == "extractor_failed"
        assert fake_client._calls == 6


class TestBuildViewpointDigest:
    def test_digest_ok(self):
        source = _source_packet(
            content="外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        )

        def extractor(sources, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "novel_mechanism",
                    "topic": "commercialization",
                    "claim": "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成。",
                    "source_quote": sources[0]["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": sources[0]["source_id"],
                }
            ]

        digest = build_viewpoint_digest(
            [source],
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
        )
        assert digest["status"] == "ok"
        assert digest["claims_count"] == 1
        assert digest["stats"]["claims_valid"] == 1
        assert digest["stats"]["display_claims"] == 1
        assert "[^1]" in digest["preview_markdown"]

    def test_digest_fail_closed_below_min(self):
        source = _source_packet()

        def extractor(sources, baseline, fingerprint):
            return []

        digest = build_viewpoint_digest(
            [source],
            "baseline text",
            extractor=extractor,
            min_display_claims=2,
            stock_name="TestCo",
        )
        assert digest["status"] == "no_incremental_claims"
        assert digest["claims_count"] == 0

    def test_digest_dedupes_repeated_quote_without_hard_display_cap(self):
        sources = [
            _source_packet(
                source_id=f"curated-source:test:{idx}",
                content=f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                url=f"https://example.com/{idx}",
            )
            for idx in range(8)
        ]

        def extractor(source_packets, baseline, fingerprint):
            claims = []
            for idx, source in enumerate(source_packets):
                claims.append(
                    {
                        **_claim_contract(),
                        "claim_type": "novel_mechanism",
                        "topic": "commercialization",
                        "claim": f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                        "source_quote": source["content"],
                        "why_incremental": "baseline未讨论。",
                        "baseline_overlap": "none",
                        "source_id": source["source_id"],
                    }
                )
            claims.append({**claims[0], "claim": "外部文章重复提示第0条变量。"})
            return claims

        digest = build_viewpoint_digest(
            sources,
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
        )
        assert digest["status"] == "ok"
        assert digest["claims_count"] == 8
        assert digest["stats"]["display_claims"] == 8
        assert digest["stats"]["merge_duplicate_dropped_count"] == 1
        assert digest["preview_markdown"].count("- **增量机制**") == 8

    def test_digest_drops_only_claims_that_fail_final_render_lint(self):
        sources = [
            _source_packet(
                source_id="curated-source:test:safe",
                content="外部文章认为供应链预付款变化提示上游材料紧张。",
                url="https://example.com/safe",
            ),
            _source_packet(
                source_id="curated-source:test:unsafe",
                content="外部文章认为客户导入节奏仍需继续跟踪。",
                url="https://example.com/unsafe",
            ),
        ]

        def extractor(source_packets, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "watch_variable",
                    "topic": "supply_chain",
                    "claim": "外部文章认为供应链预付款变化提示上游材料紧张。",
                    "source_quote": source_packets[0]["content"],
                    "why_incremental": "baseline未讨论上游材料紧张。",
                    "baseline_overlap": "none",
                    "source_id": source_packets[0]["source_id"],
                },
                {
                    **_claim_contract(),
                    "claim_type": "watch_variable",
                    "topic": "commercialization",
                    "claim": "外部文章认为客户导入节奏仍需继续跟踪。",
                    "source_quote": source_packets[1]["content"],
                    "why_incremental": "该表述确认客户已经锁定。",
                    "baseline_overlap": "none",
                    "source_id": source_packets[1]["source_id"],
                },
            ]

        digest = build_viewpoint_digest(
            sources,
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
        )
        assert digest["status"] == "ok"
        assert digest["claims_count"] == 1
        assert digest["stats"]["final_overclaim_dropped_count"] == 1
        assert "供应链预付款变化" in digest["preview_markdown"]
        assert "客户已经锁定" not in digest["preview_markdown"]

    def test_digest_includes_failed_passes_in_stats(self):
        source = _source_packet(
            content="外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成，这一变量仍需客户验证。"
        )

        def extractor(sources, baseline, fingerprint):
            claims = type("ClaimList", (list,), {})(
                [
                    {
                        **_claim_contract(),
                        "claim_type": "novel_mechanism",
                        "topic": "commercialization",
                        "claim": "外部产业分析认为公司核心机制正从光模块速率转向硅光平台集成。",
                        "source_quote": sources[0]["content"],
                        "why_incremental": "baseline未讨论。",
                        "baseline_overlap": "none",
                        "source_id": sources[0]["source_id"],
                    }
                ]
            )
            claims.failed_passes = [
                {"pass": "supply_chain", "status": "extractor_failed", "message": "api error"}
            ]
            return claims

        digest = build_viewpoint_digest(
            [source],
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
        )
        assert digest["status"] == "ok"
        assert digest["stats"]["failed_passes_count"] == 1
        assert digest["stats"]["failed_passes"][0]["pass"] == "supply_chain"


class _FakeChatCompletions:
    def __init__(self, response_text: str):
        self._response_text = response_text

    def create(self, **kwargs):
        return _FakeResponse(self._response_text)


class _FakeChat:
    def __init__(self, response_text: str):
        self.completions = _FakeChatCompletions(response_text)


class _FakeLLMClient:
    def __init__(self, json_payload: str | None = None, claims: list[dict] | None = None):
        if json_payload is not None:
            self._text = json_payload
        else:
            self._text = json.dumps({"claims": claims or []}, ensure_ascii=False)
        self.chat = _FakeChat(self._text)


class _SequencedLLMClient:
    def __init__(self, payloads: list[dict]):
        self._texts = [json.dumps(payload, ensure_ascii=False) for payload in payloads]
        self._calls = 0
        self.chat = _SequencedChat(self)


class _SequencedChat:
    def __init__(self, client: _SequencedLLMClient):
        self.completions = _SequencedChatCompletions(client)


class _SequencedChatCompletions:
    def __init__(self, client: _SequencedLLMClient):
        self._client = client

    def create(self, **kwargs):
        idx = min(self._client._calls, len(self._client._texts) - 1)
        self._client._calls += 1
        return _FakeResponse(self._client._texts[idx])


class _SequencedRawLLMClient:
    def __init__(self, texts: list[str]):
        self._texts = texts
        self._calls = 0
        self.chat = _SequencedRawChat(self)


class _SequencedRawChat:
    def __init__(self, client: _SequencedRawLLMClient):
        self.completions = _SequencedRawChatCompletions(client)


class _SequencedRawChatCompletions:
    def __init__(self, client: _SequencedRawLLMClient):
        self._client = client

    def create(self, **kwargs):
        idx = min(self._client._calls, len(self._client._texts) - 1)
        self._client._calls += 1
        return _FakeResponse(self._client._texts[idx])


class _FakeResponse:
    def __init__(self, text: str):
        self.choices = [type("Choice", (), {"message": type("Message", (), {"content": text})()})]


class _CaptureLLMClient:
    def __init__(self, payload: dict):
        self._text = json.dumps(payload, ensure_ascii=False)
        self.prompts: list[str] = []
        self.chat = _CaptureChat(self)


class _CaptureChat:
    def __init__(self, client: _CaptureLLMClient):
        self.completions = _CaptureChatCompletions(client)


class _CaptureChatCompletions:
    def __init__(self, client: _CaptureLLMClient):
        self._client = client

    def create(self, **kwargs):
        messages = kwargs.get("messages") or []
        if messages:
            self._client.prompts.append(str(messages[0].get("content") or ""))
        return _FakeResponse(self._client._text)


class _FailingThenSuccessLLMClient:
    """Fake client that raises `exc_class` for the first `failures` calls, then returns payload."""

    def __init__(self, failures: int, payload: dict, exc_class: type = RuntimeError):
        self._failures = failures
        self._payload = payload
        self._exc_class = exc_class
        self._calls = 0
        self.chat = _FailingThenSuccessChat(self)


class _FailingThenSuccessChat:
    def __init__(self, client: _FailingThenSuccessLLMClient):
        self.completions = _FailingThenSuccessChatCompletions(client)


class _FailingThenSuccessChatCompletions:
    def __init__(self, client: _FailingThenSuccessLLMClient):
        self._client = client

    def create(self, **kwargs):
        client = self._client
        client._calls += 1
        if client._calls <= client._failures:
            raise client._exc_class("simulated API failure")
        return _FakeResponse(json.dumps(client._payload, ensure_ascii=False))


def _noop_sleep(_seconds: float) -> None:
    pass


class TestThemeCoverageAndNearDuplicate:
    def test_digest_theme_coverage_pass(self):
        source = _source_packet(
            content="市场传言公司 800G 交付计划从1500万只下调至1200万只，引发供应链担忧。"
        )

        def extractor(sources, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "watch_variable",
                    "topic": "supply_delivery_capacity",
                    "claim": "外部文章提示800G交付计划从1500万降至1200万只的传言。",
                    "source_quote": sources[0]["content"],
                    "why_incremental": "baseline未涉及。",
                    "baseline_overlap": "none",
                    "source_id": sources[0]["source_id"],
                }
            ]

        digest = build_viewpoint_digest(
            [source],
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
            theme_profile=THEME_PROFILES["zhongji_ai_optics"],
            min_theme_coverage=0.1,
        )
        assert digest["status"] == "ok"
        assert digest["stats"]["theme_coverage_count"] > 0
        assert "800G_rumor" in digest["stats"]["covered_themes"]
        assert "800G_rumor" not in digest["stats"]["missing_themes"]

    def test_digest_theme_coverage_fail(self):
        source = _source_packet(content="外部文章提示一般性行业观察，无具体主题。")

        def extractor(sources, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "context_extension",
                    "topic": "general",
                    "claim": "外部文章提示一般性行业观察。",
                    "source_quote": sources[0]["content"],
                    "why_incremental": "baseline未涉及。",
                    "baseline_overlap": "none",
                    "source_id": sources[0]["source_id"],
                }
            ]

        digest = build_viewpoint_digest(
            [source],
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
            theme_profile=THEME_PROFILES["zhongji_ai_optics"],
            min_theme_coverage=0.9,
        )
        assert digest["status"] == "theme_coverage_failed"
        assert digest["stats"]["theme_coverage_ratio"] < 0.9
        assert len(digest["stats"]["missing_themes"]) > 0
        assert digest["preview_markdown"] == ""

    def test_theme_coverage_does_not_match_year_without_demand_context(self):
        source = _source_packet(content="外部文章提示2026年行业节奏仍需观察，但没有具体指引。")

        def extractor(sources, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "context_extension",
                    "topic": "general",
                    "claim": "外部文章提示2026年行业节奏仍需观察。",
                    "source_quote": sources[0]["content"],
                    "why_incremental": "baseline未涉及。",
                    "baseline_overlap": "none",
                    "source_id": sources[0]["source_id"],
                }
            ]

        digest = build_viewpoint_digest(
            [source],
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
            theme_profile=THEME_PROFILES["zhongji_ai_optics"],
        )
        assert digest["status"] == "ok"
        assert "customer_demand_capex_guide_2026_2028" not in digest["stats"]["covered_themes"]

    def test_digest_near_duplicate_merge_keeps_more_informative(self):
        sources = [
            _source_packet(
                source_id="curated-source:test:a",
                content="外部文章认为公司800G交付计划可能下调。",
                url="https://example.com/a",
            ),
            _source_packet(
                source_id="curated-source:test:b",
                content="外部文章指出市场传言公司800G交付计划从1500万降至1200万只。",
                url="https://example.com/b",
            ),
        ]

        def extractor(source_packets, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "watch_variable",
                    "topic": "supply_delivery_capacity",
                    "claim": "外部文章认为公司800G交付计划可能下调。",
                    "source_quote": source_packets[0]["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source_packets[0]["source_id"],
                },
                {
                    **_claim_contract(),
                    "claim_type": "watch_variable",
                    "topic": "supply_delivery_capacity",
                    "claim": "外部文章认为公司800G交付计划可能下调。",
                    "source_quote": source_packets[1]["content"],
                    "why_incremental": "baseline未讨论800G具体数字。",
                    "baseline_overlap": "none",
                    "source_id": source_packets[1]["source_id"],
                },
            ]

        digest = build_viewpoint_digest(
            sources,
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
        )
        assert digest["status"] == "ok"
        assert digest["stats"]["near_duplicate_dropped_count"] == 1
        assert digest["claims_count"] == 1
        # The more informative quote (with specific numbers) should be kept.
        assert "1500万" in digest["claims"][0]["source_quote"]

    def test_multipass_prompt_includes_1260H_cue(self):
        source = _source_packet(content="外部文章提示1260H实体清单影响仍需跟踪。")
        fake_client = _CaptureLLMClient(
            {
                "claims": [
                    {
                        **_claim_contract(),
                        "claim_type": "watch_variable",
                        "topic": "geopolitics_capex_customers",
                        "claim": "外部文章提示1260H实体清单影响仍需跟踪。",
                        "source_quote": source["content"],
                        "why_incremental": "baseline未讨论。",
                        "baseline_overlap": "none",
                        "source_id": source["source_id"],
                    }
                ]
            }
        )
        extractor = multipass_llm_extractor_factory(
            model="test",
            base_url="http://localhost",
            api_key="dummy",
            stock_name="TestCo",
            client=fake_client,
            prompt_path=None,
        )
        extractor([source], "baseline", set())
        assert any("1260H" in prompt for prompt in fake_client.prompts)

    def test_digest_retains_all_qualified_claims_no_hard_cap(self):
        sources = [
            _source_packet(
                source_id=f"curated-source:test:{idx}",
                content=f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                url=f"https://example.com/{idx}",
            )
            for idx in range(10)
        ]

        def extractor(source_packets, baseline, fingerprint):
            return [
                {
                    **_claim_contract(),
                    "claim_type": "novel_mechanism",
                    "topic": f"mechanism_{idx}",
                    "claim": f"外部产业分析认为第{idx}条增量机制仍需客户验证。",
                    "source_quote": source["content"],
                    "why_incremental": "baseline未讨论。",
                    "baseline_overlap": "none",
                    "source_id": source["source_id"],
                }
                for idx, source in enumerate(source_packets)
            ]

        digest = build_viewpoint_digest(
            sources,
            "baseline text",
            extractor=extractor,
            min_display_claims=1,
            stock_name="TestCo",
            max_display_claims=5,  # should not affect JSON output
        )
        assert digest["status"] == "ok"
        assert digest["claims_count"] == 10
        assert len(digest["claims"]) == 10
        assert digest["stats"]["display_claims"] == 10
