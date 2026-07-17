from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_full_body_viewpoint_claims import (
    build_curated_external_argument_pack,
    build_source_packets,
    llm_unit_selector_factory,
    normalized_hash,
    write_curated_external_argument_pack,
)


def _packet(content="TestCo 产品完成客户导入。TestCo 毛利率改善。"):
    return {
        "source_id": "curated-source:test:1", "stock_name": "TestCo", "title": "测试文章",
        "account": "测试账号", "publish_time": "2026-04-01", "source_kind": "wechat",
        "source_ref": "https://example.com/s1", "source_url": "https://example.com/s1",
        "content": content, "source_content_hash": normalized_hash(content),
    }


def test_build_source_packets_keeps_local_cleaned_body_and_stable_source_identity(tmp_path):
    source = tmp_path / "sources.jsonl"
    source.write_text(json.dumps({
        "title": "文章", "source_ref": "https://example.com/a", "content": "正文。免责声明后续内容",
        "quality_score": 2, "discovery_score": 1,
    }, ensure_ascii=False), encoding="utf-8")

    packets = build_source_packets(source, stock_name="TestCo")

    assert packets[0]["content"] == "正文。"
    assert packets[0]["source_id"].startswith("curated-source:external:")
    assert packets[0]["source_content_hash"] == normalized_hash("正文。")


def test_v3_argument_pack_retries_incomplete_selection_once_then_writes_exact_pack(tmp_path):
    calls = []

    def selector(units):
        calls.append([unit["unit_id"] for unit in units])
        return ({"schema_version": "curated_external_unit_selection.v1", "decisions": []} if len(calls) == 1 else {
            "schema_version": "curated_external_unit_selection.v1",
            "decisions": [{"unit_id": unit["unit_id"], "action": "keep", "group_id": "", "reason": "incremental_target_fact"} for unit in units],
        })

    pack = build_curated_external_argument_pack(
        [_packet("TestCo 产品完成客户导入。英伟达发布800G产品并启动量产。")],
        "baseline", selector=selector, stock_name="TestCo",
    )
    output = write_curated_external_argument_pack(pack, tmp_path / "pack.json")

    assert calls[0] == calls[1]
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "ready"
    assert all("claim" not in card for card in pack["cards"])
    assert pack["diagnostics"]["selector_request_count"] == 2


def test_target_only_argument_pack_bypasses_selector_entirely():
    calls = []

    def selector(units):
        calls.append(units)
        raise AssertionError("target units must not reach the selector")

    pack = build_curated_external_argument_pack(
        [_packet("TestCo 产品完成客户导入。TestCo 毛利率改善。")],
        "", selector=selector, stock_name="TestCo",
    )

    assert pack["status"] == "ready"
    assert calls == []
    assert pack["diagnostics"]["selector_request_count"] == 0
    assert pack["diagnostics"]["selector_batch_count"] == 0


def test_mixed_argument_pack_selects_only_eligible_peer_units_after_target_bypass():
    calls = []

    def selector(units):
        calls.append([unit["text"] for unit in units])
        return {"schema_version": "curated_external_unit_selection.v1", "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": "", "reason": "peer"}
            for unit in units
        ]}

    pack = build_curated_external_argument_pack(
        [_packet("TestCo 产品完成客户导入。行业竞争格局加剧。英伟达发布800G产品并启动量产。")],
        "", selector=selector, stock_name="TestCo",
    )

    assert pack["status"] == "ready"
    assert calls == [["英伟达发布800G产品并启动量产。"]]
    assert pack["diagnostics"]["selector_batch_count"] == 1
    assert pack["diagnostics"]["accepted_target_card_count"] == 1
    assert pack["diagnostics"]["accepted_peer_card_count"] == 1


def test_selector_batch_keeps_source_order_after_target_peer_partition():
    calls = []

    def selector(units):
        calls.append([unit["source_ordinal"] for unit in units])
        return {"schema_version": "curated_external_unit_selection.v1", "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": "", "reason": "keep"}
            for unit in units
        ]}

    pack = build_curated_external_argument_pack(
        [_packet("TestCo 产品完成客户导入。英伟达发布800G产品并启动量产。")],
        "", selector=selector, stock_name="TestCo",
    )

    assert pack["status"] == "ready"
    assert calls == [[1]]


def test_nonconsecutive_peer_group_downgrades_to_singletons_without_retry():
    calls = []

    def selector(units):
        calls.append([unit["source_ordinal"] for unit in units])
        return {"schema_version": "curated_external_unit_selection.v1", "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": "peer-argument", "reason": "peer"}
            for unit in units
        ]}

    pack = build_curated_external_argument_pack(
        [_packet(
            "TestCo 产品完成客户导入。英伟达发布800G产品并启动量产。"
            "行业仍在观察。华为发布1.6T产品并启动量产。"
        )],
        "", selector=selector, stock_name="TestCo",
    )

    peer_cards = [card for card in pack["cards"] if card["entity_scope"] == "peer_or_industry"]
    assert pack["status"] == "ready"
    assert calls == [[1, 3]]
    assert pack["diagnostics"]["selector_request_count"] == 1
    assert len(peer_cards) == 2
    assert all(len(card["evidence_units"]) == 1 for card in peer_cards)


def test_consecutive_peer_group_remains_one_card():
    def selector(units):
        return {"schema_version": "curated_external_unit_selection.v1", "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": "peer-argument", "reason": "peer"}
            for unit in units
        ]}

    pack = build_curated_external_argument_pack(
        [_packet(
            "TestCo 产品完成客户导入。英伟达发布800G产品并启动量产。"
            "英伟达同时扩大相关产品交付。"
        )],
        "", selector=selector, stock_name="TestCo",
    )

    peer_cards = [card for card in pack["cards"] if card["entity_scope"] == "peer_or_industry"]
    assert pack["status"] == "ready"
    assert len(peer_cards) == 1
    assert [unit["source_ordinal"] for unit in peer_cards[0]["evidence_units"]] == [1, 2]


def test_oversized_peer_group_still_fails_closed_after_existing_retry():
    calls = []

    def selector(units):
        calls.append([unit["source_ordinal"] for unit in units])
        return {"schema_version": "curated_external_unit_selection.v1", "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": "peer-argument", "reason": "peer"}
            for unit in units
        ]}

    pack = build_curated_external_argument_pack(
        [_packet(
            "TestCo 产品完成客户导入。英伟达发布800G产品并启动量产。"
            "华为发布1.6T产品并启动量产。AMD发布新芯片并启动量产。"
            "英特尔发布新产品并启动量产。"
        )],
        "", selector=selector, stock_name="TestCo",
    )

    assert pack["status"] == "selector_incomplete"
    assert len(calls) == 2


def test_v3_unit_selector_requests_only_stable_unit_decisions():
    class Response:
        def __init__(self, text): self.choices = [type("Choice", (), {"message": type("Message", (), {"content": text})()})()]
    class Completions:
        def __init__(self, client): self.client = client
        def create(self, **kwargs):
            self.client.prompt = kwargs["messages"][0]["content"]
            return Response(json.dumps(self.client.payload, ensure_ascii=False))
    class Client:
        def __init__(self, payload): self.payload = payload; self.prompt = ""; self.chat = type("Chat", (), {"completions": Completions(self)})()

    units = [{"unit_id": "external-unit:source:1:0:aaa", "source_id": "source:1", "source_ordinal": 0, "text": "TestCo 产品完成客户导入。"}]
    client = Client({"schema_version": "curated_external_unit_selection.v1", "decisions": [{
        "unit_id": units[0]["unit_id"], "action": "keep", "group_id": "", "reason": "incremental_target_fact",
    }]})

    result = llm_unit_selector_factory("test", "", "", stock_name="TestCo", client=client)(units)

    assert result["decisions"][0]["unit_id"] == units[0]["unit_id"]
    assert "unit_id" in client.prompt and "topic_family" not in client.prompt and "source_quote" not in client.prompt
