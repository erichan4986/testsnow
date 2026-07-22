"""Contracts for the v4 external-material display adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_display import build_curated_external_argument_display
from external_pack import build_external_argument_pack_v4, external_selection_batches_v4, prepare_external_argument_material_v4
from external_source_document import build_external_source_document


def _pack() -> dict:
    document = build_external_source_document({
        "source_id": "source:target", "stock_name": "测试股", "title": "测试股经营观察",
        "source_kind": "media", "source_ref": "https://example.test/target",
        "source_url": "https://example.test/target",
        "content": "测试股产品完成客户导入，订单增长明显。\n\n2027年行业产能仍紧张。",
    })
    prepared = prepare_external_argument_material_v4([document], stock_name="测试股", baseline_text="")
    selections = [{
        "schema_version": "curated_external_unit_selection.v2",
        "decisions": [
            {"unit_id": unit["unit_id"], "action": "keep", "group_id": ""}
            for unit in batch
        ],
    } for batch in external_selection_batches_v4(prepared["peer_units"])]
    return build_external_argument_pack_v4(
        [document], stock_name="测试股", baseline_text="", selections=selections,
    )


def test_v4_display_keeps_report_envelope_and_exact_evidence(tmp_path):
    path = tmp_path / "v4-pack.json"
    path.write_text(json.dumps(_pack(), ensure_ascii=False), encoding="utf-8")

    result = build_curated_external_argument_display(path, expected_stock_name="测试股")

    assert result["status"] == "ok"
    display = result["display"]
    assert {
        "citations", "_curated_external_argument_cards", "_curated_external_topic_narratives",
    } <= set(display)
    assert display["_curated_external_taxonomy_version"] == "external_argument.v4"
    assert "> 测试股产品完成客户导入，订单增长明显。[^1]" in display["industry_logic"]
    assert display["_curated_external_topic_narratives"][0]["parts"][0]["quote"] == "测试股产品完成客户导入，订单增长明显。"


def test_v4_display_fails_closed_for_invalid_embedded_source_document(tmp_path):
    pack = _pack()
    pack["source_documents"][0]["blocks"][0]["text"] = "伪造文本。"
    path = tmp_path / "forged-pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")

    result = build_curated_external_argument_display(path, expected_stock_name="测试股")

    assert result["status"] == "invalid"
    assert result["display"] is None
