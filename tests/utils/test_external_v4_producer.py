"""Offline producer contracts for the v4 external-material path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_full_body_viewpoint_claims import (
    FullBodyExtractorError,
    build_external_argument_pack_from_sources,
    build_source_documents,
    llm_unit_selector_factory,
)
from external_source_document import build_external_source_document


def _document(content: str) -> dict:
    return build_external_source_document({
        "source_id": "source:one", "stock_name": "测试股", "title": "测试股经营观察",
        "source_kind": "media", "source_ref": "https://example.test/one",
        "source_url": "https://example.test/one", "content": content,
    })


def test_source_documents_preserve_paragraphs_and_keep_disclaimers_as_noise(tmp_path):
    source = tmp_path / "sources.jsonl"
    source.write_text(json.dumps({
        "title": "测试股观察", "source_ref": "https://example.test/one",
        "content": "测试股产品完成客户导入。\n\n免责声明：本文不构成投资建议。",
    }, ensure_ascii=False), encoding="utf-8")

    documents = build_source_documents(source, stock_name="测试股")

    assert [block["text"] for block in documents[0]["blocks"]] == [
        "测试股产品完成客户导入。", "免责声明：本文不构成投资建议。",
    ]
    assert documents[0]["blocks"][1]["block_kind"] == "structural_noise"


def test_v4_producer_retries_one_malformed_peer_selection_then_writes_id_only_plan():
    calls = []

    def selector(units):
        calls.append([unit["unit_id"] for unit in units])
        return (
            {"schema_version": "curated_external_unit_selection.v2", "decisions": []}
            if len(calls) == 1
            else {"schema_version": "curated_external_unit_selection.v2", "decisions": [
                {"unit_id": unit["unit_id"], "action": "keep", "group_id": ""}
                for unit in units
            ]}
        )

    pack = build_external_argument_pack_from_sources(
        [_document("测试股产品完成客户导入。华工科技发布新产品并启动量产。")],
        baseline_text="", selector=selector, stock_name="测试股",
    )

    assert pack["status"] == "ready"
    assert calls[0] == calls[1]
    assert pack["diagnostics"]["selector_request_count"] == 2
    assert set(pack["narrative_plan"]) == {"schema_version", "groups"}
    assert all(set(group) == {"scope_bucket", "primary_family", "card_ids"} for group in pack["narrative_plan"]["groups"])


def test_v4_producer_rejects_degraded_source_before_calling_selector():
    degraded = build_external_source_document({
        "source_id": "source:degraded", "stock_name": "测试股", "title": "测试股与华工科技对比",
        "source_kind": "media", "source_ref": "https://example.test/degraded",
        "source_url": "https://example.test/degraded", "content": "测试股与华工科技对比：" + "内容" * 600,
    })
    calls = []

    def selector(units):
        calls.append(units)
        return {"schema_version": "curated_external_unit_selection.v2", "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": ""} for unit in units
        ]}

    pack = build_external_argument_pack_from_sources(
        [_document("华工科技发布新产品并启动量产。"), degraded],
        baseline_text="", selector=selector, stock_name="测试股",
    )

    assert pack["status"] == "source_input_degraded"
    assert calls == []


def test_v4_selector_prompt_exposes_only_unit_selection_fields():
    class Response:
        def __init__(self, text):
            self.choices = [type("Choice", (), {"message": type("Message", (), {"content": text})()})()]

    class Completions:
        def __init__(self, client):
            self.client = client

        def create(self, **kwargs):
            self.client.prompt = kwargs["messages"][0]["content"]
            return Response(json.dumps(self.client.payload, ensure_ascii=False))

    class Client:
        def __init__(self, payload):
            self.payload = payload
            self.prompt = ""
            self.chat = type("Chat", (), {"completions": Completions(self)})()

    unit = {"unit_id": "external-unit:one", "source_id": "source:one", "block_id": "block:one", "unit_ordinal": 0, "text": "行业产能仍紧张。"}
    client = Client({"schema_version": "curated_external_unit_selection.v2", "decisions": [
        {"unit_id": unit["unit_id"], "action": "skip", "group_id": ""},
    ]})

    result = llm_unit_selector_factory("test", "", "", stock_name="测试股", client=client)([unit])

    assert result["decisions"][0]["unit_id"] == unit["unit_id"]
    assert "unit_id" in client.prompt
    assert all(forbidden not in client.prompt for forbidden in ("topic_family", "source_quote", "relation", "reason"))


def test_selector_factory_makes_one_request_per_producer_attempt():
    class Completions:
        def __init__(self):
            self.calls = 0

        def create(self, **_kwargs):
            self.calls += 1
            raise RuntimeError("temporary API failure")

    completions = Completions()
    client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
    selector = llm_unit_selector_factory("test", "", "", stock_name="测试股", client=client)

    try:
        selector([{"unit_id": "u1", "text": "行业产能仍紧张。"}])
    except FullBodyExtractorError:
        pass
    else:
        raise AssertionError("selector should surface its one failed producer attempt")

    assert completions.calls == 1
