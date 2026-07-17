"""Tests for the sole v3 external display projection."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

import curated_external_display as display_module
from curated_external_argument_cards import build_external_argument_pack, materialize_external_source_units
from curated_external_display import build_curated_external_argument_display


def _pack(stock_name="测试股", include=True):
    text = f"{stock_name}的产品完成客户导入，交付节奏仍需验证。"
    packet = {
        "source_id": "source:one", "stock_name": stock_name, "title": f"{stock_name}观察",
        "account": "观察者", "publish_time": "2026-07-15", "source_url": "https://example.com/one",
        "source_ref": "https://example.com/one", "content": text,
        "source_content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }
    return build_external_argument_pack(
        stock_name=stock_name, source_packets=[packet], baseline_text="" if include else text,
        selections=[],
    )


def test_argument_display_reads_only_valid_v3_pack_and_renders_exact_evidence(tmp_path):
    path = tmp_path / "pack.json"; path.write_text(json.dumps(_pack(), ensure_ascii=False), encoding="utf-8")
    result = build_curated_external_argument_display(path, expected_stock_name="测试股")

    assert result["status"] == "ok"
    assert result["display"]["_curated_external_taxonomy_version"] == "external_argument.v3"
    assert result["display"]["_curated_external_argument_cards"][0]["citation_refs"] == [1]
    assert result["display"]["industry_logic"].count("外部材料原文摘录（Preview，未经官方核验）") == 1
    assert "> 测试股的产品完成客户导入" in result["display"]["industry_logic"]
    assert "测试股的产品完成客户导入" in result["display"]["industry_logic"]


def test_argument_display_fails_closed_for_missing_stale_invalid_mismatch_and_empty(tmp_path):
    assert build_curated_external_argument_display(None, expected_stock_name="测试股")["status"] == "missing_config"
    assert build_curated_external_argument_display(tmp_path / "missing.json", expected_stock_name="测试股")["status"] == "missing"
    cases = []
    stale = _pack(); stale["validator_version"] = "old"; cases.append((stale, "stale"))
    invalid = _pack(); invalid["cards"][0]["scoring_eligible"] = True; cases.append((invalid, "invalid"))
    cases.extend([(_pack("另一家公司"), "stock_identity_mismatch"), (_pack(include=False), "empty")])
    for index, (payload, expected) in enumerate(cases):
        path = tmp_path / f"case-{index}.json"; path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        assert build_curated_external_argument_display(path, expected_stock_name="测试股")["status"] == expected


def test_legacy_display_apis_are_removed():
    assert not hasattr(display_module, "build_curated_external_narrative_display")
    assert not hasattr(display_module, "build_curated_external_digest_display")


def test_argument_display_renders_target_before_separate_peer_preview_block(tmp_path):
    packets = []
    for source_id, text in (
        ("source:target", "测试股产品完成客户导入。"),
        ("source:peer", "英伟达发布800G产品并启动量产。"),
    ):
        packets.append({
            "source_id": source_id, "stock_name": "测试股", "title": "外部观察",
            "account": "观察者", "publish_time": "2026-07-15",
            "source_url": f"https://example.com/{source_id}",
            "source_ref": f"https://example.com/{source_id}", "content": text,
            "source_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        })
    peer_unit = materialize_external_source_units([packets[1]], stock_name="测试股")[0]
    selections = [{"schema_version": "curated_external_unit_selection.v1", "decisions": [{
        "unit_id": peer_unit["unit_id"], "action": "keep", "group_id": "", "reason": "keep",
    }]}]
    pack = build_external_argument_pack(
        stock_name="测试股", source_packets=packets, baseline_text="", selections=selections,
    )
    pack["cards"].reverse()
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")

    result = build_curated_external_argument_display(path, expected_stock_name="测试股")
    text = result["display"]["industry_logic"]
    cards = result["display"]["_curated_external_argument_cards"]

    assert [card["entity_scope"] for card in cards] == ["target", "peer_or_industry"]
    assert text.index("测试股产品完成客户导入") < text.index("同业/行业背景（Preview）")
    assert text.index("同业/行业背景（Preview）") < text.index("英伟达发布800G产品并启动量产")


def test_argument_display_quotes_exact_strong_wording_under_canonical_preview_heading(tmp_path):
    text = "测试股公告显示订单已锁定，交付仍需验证。"
    packet = {
        "source_id": "source:one", "stock_name": "测试股", "title": "测试股观察",
        "account": "观察者", "publish_time": "2026-07-15", "source_url": "https://example.com/one",
        "source_ref": "https://example.com/one", "content": text,
        "source_content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }
    pack = build_external_argument_pack(
        stock_name="测试股", source_packets=[packet], baseline_text="", selections=[],
    )
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")

    result = build_curated_external_argument_display(path, expected_stock_name="测试股")

    assert result["status"] == "ok"
    assert result["lint"]["violations"] == []
    assert text in result["display"]["industry_logic"]
    assert "> 测试股公告显示订单已锁定" in result["display"]["industry_logic"]
