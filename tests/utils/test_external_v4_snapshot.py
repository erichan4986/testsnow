"""v4 pack display integration contracts for the Chapter 4 snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_display import build_curated_external_argument_display
from deep_analysis_material_snapshot import build_deep_analysis_material_snapshot
from external_pack import build_external_argument_pack_v4, external_selection_batches_v4, prepare_external_argument_material_v4
from external_source_document import build_external_source_document


def _display(tmp_path) -> dict:
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
    pack = build_external_argument_pack_v4(
        [document], stock_name="测试股", baseline_text="", selections=selections,
    )
    path = tmp_path / "v4-pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    return build_curated_external_argument_display(path, expected_stock_name="测试股")["display"]


def test_snapshot_reads_v4_exact_unit_text_and_preserves_external_offset(tmp_path):
    snapshot = build_deep_analysis_material_snapshot({
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "formal_financial_fact_pack": {
            "facts": [{"metric": "营业收入", "value": "10亿元", "source": "公司年报"}],
        },
        "deep_analysis_display": _display(tmp_path),
    })

    external = next(row for row in snapshot.rows if row.source_layer == "external")
    assert external.body == "测试股产品完成客户导入，订单增长明显。"
    assert external.citation_refs == (2,)
    assert snapshot.citations[2]["title"] == "测试股经营观察"
    assert snapshot.external_topic_narratives[0].parts[0].quote == external.body
