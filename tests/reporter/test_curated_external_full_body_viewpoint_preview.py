from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "previews"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import curated_external_full_body_viewpoint_preview as preview


def _inputs(tmp_path):
    source = tmp_path / "sources.jsonl"
    source.write_text(json.dumps({
        "title": "测试文章", "account": "测试账号", "publish_time": "2026-04-01",
        "source_ref": "https://example.com/cli", "content": "测试股产品完成客户导入，仍需验证。",
    }, ensure_ascii=False), encoding="utf-8")
    baseline = tmp_path / "baseline.txt"; baseline.write_text("canonical baseline", encoding="utf-8")
    return source, baseline


def test_cli_writes_only_v3_pack_under_tmp(tmp_path, capsys, monkeypatch):
    source, baseline = _inputs(tmp_path); stock = f"argument_v3_{uuid.uuid4().hex[:8]}"
    output = Path(f"/tmp/{stock}-curated-external-argument-pack-v3.json")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(preview, "llm_unit_selector_factory", lambda *args, **kwargs: lambda units: {
        "schema_version": "curated_external_unit_selection.v1",
        "decisions": [{"unit_id": unit["unit_id"], "action": "keep", "group_id": "", "reason": "incremental_target_fact"} for unit in units],
    })
    monkeypatch.setattr(preview, "llm_topic_narrative_composer_factory", lambda *args, **kwargs: lambda pack: {
        "schema_version": "curated_external_topic_narrative_draft.v1",
        "groups": [{
            "scope_bucket": "peer_or_industry" if card["entity_scope"] == "peer_or_industry" else "target",
            "primary_family": card["primary_family"],
            "parts": [{
                "argument_key": card["argument_key"], "unit_id": unit["unit_id"],
                "quote": unit["text"], "relation": "first" if index == 0 else "continuation",
            } for index, unit in enumerate(card["evidence_units"])],
        } for card in pack["cards"]],
    })
    try:
        assert preview.main(["--source-jsonl", str(source), "--baseline-synthesis-file", str(baseline), "--stock", stock, "--llm-model", "test", "--llm-base-url", "http://localhost"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema_version"] == "curated_external_argument_pack.v3"
        assert payload["topic_narrative_status"] == "ready"
        assert Path(payload["pack_output_path"]) == output.resolve() and output.exists()
    finally:
        output.unlink(missing_ok=True)


def test_cli_rejects_rendered_baseline_and_repository_output(tmp_path, capsys, monkeypatch):
    source, baseline = _inputs(tmp_path)
    baseline.write_text("## 四、深度分析", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    assert preview.main(["--source-jsonl", str(source), "--baseline-synthesis-file", str(baseline), "--stock", "测试股", "--llm-model", "test", "--llm-base-url", "http://localhost"]) == 1
    assert "canonical" in capsys.readouterr().err
    baseline.write_text("canonical", encoding="utf-8")
    assert preview.main(["--source-jsonl", str(source), "--baseline-synthesis-file", str(baseline), "--stock", "测试股", "--pack-output", str(Path(__file__).parents[2] / "bad.json"), "--llm-model", "test", "--llm-base-url", "http://localhost"]) == 1
    assert "outside the repository" in capsys.readouterr().err
