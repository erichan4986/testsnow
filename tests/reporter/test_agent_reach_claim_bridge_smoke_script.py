"""Tests for scripts/smoke_agent_reach_claim_bridge.py."""

import ast
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke_agent_reach_claim_bridge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_agent_reach_claim_bridge", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_source() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_bridge_smoke_script_does_not_import_full_report_paths():
    source = _module_source()
    tree = ast.parse(source)
    forbidden = {
        "PerStockReporter",
        "ZhihuCollector",
        "KnowledgeSynthesizer",
        "export_pdf",
        "ReportAssemblySkill",
        "build_stock_report_pipeline",
        "SynthesisSkill",
        "risk_score_section",
    }
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name in forbidden or (alias.asname and alias.asname in forbidden):
                    found.add(alias.name)
            if isinstance(node, ast.ImportFrom) and node.module:
                for name in forbidden:
                    if name in node.module:
                        found.add(name)
    assert not found


def test_bridge_smoke_dry_run_does_not_write_evidence(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: {"enabled": True})
    calls = {"query": 0, "fetch": 0, "quality": 0, "writer": 0}

    def fake_query(ctx):
        calls["query"] += 1
        ctx.set("agent_reach_enabled", True)
        ctx.set("search_queries", [])
        return ctx

    def fake_fetch(ctx):
        calls["fetch"] += 1
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality(ctx):
        calls["quality"] += 1
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_keep_items", [])
        ctx.set("agent_reach_demote_items", [])
        ctx.set("agent_reach_quality_summary", {"keep": 0, "demote": 0, "discard": 0, "total": 0})
        ctx.set("agent_reach_run_summary", {"queries": [], "results": []})
        return ctx

    def fake_writer(ctx):
        calls["writer"] += 1
        ctx.set("evidence_note_status", "written")
        return ctx

    class FakePlan:
        high_credit_claims = []
        low_credit_claims = []
        verifications = []
        skipped_files = []

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality)
    monkeypatch.setattr(module, "evidence_note_writer_skill", fake_writer)
    monkeypatch.setattr(module, "build_claim_verification_plan", lambda *args, **kwargs: FakePlan())
    monkeypatch.setattr(module, "derive_structured_risk_signals_from_plan", lambda plan: [])

    summary = module.run_bridge_smoke("黑芝麻智能", output_dir=str(tmp_path), write_evidence_notes=False)

    assert calls == {"query": 1, "fetch": 1, "quality": 1, "writer": 0}
    assert summary["evidence_note_status"] == "disabled"
    assert summary["claim_plan"]["high_credit_claims"] == 0
    assert summary["structured_risk_signals"] == []


def test_bridge_smoke_write_evidence_calls_writer_and_reports_counts(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: {"enabled": True})

    def fake_query(ctx):
        ctx.set("agent_reach_enabled", True)
        ctx.set("search_queries", [{"query": "web_read"}])
        return ctx

    def fake_fetch(ctx):
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality(ctx):
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_keep_items", ["item"])
        ctx.set("agent_reach_demote_items", [])
        ctx.set("agent_reach_quality_summary", {"keep": 1, "demote": 0, "discard": 0, "total": 1})
        ctx.set("agent_reach_run_summary", {"queries": [{"query": "web_read"}], "results": []})
        return ctx

    def fake_writer(ctx):
        assert ctx.get("enable_evidence_notes") is True
        assert ctx.get("evidence_notes_dry_run") is False
        ctx.set("evidence_note_status", "written")
        ctx.set("evidence_note_summary", {
            "written_count": 1,
            "skipped_existing_count": 0,
            "filtered_count": 0,
            "dry_run": False,
        })
        return ctx

    class FakePlan:
        high_credit_claims = [object(), object()]
        low_credit_claims = [object()]
        verifications = [object()]
        skipped_files = []

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality)
    monkeypatch.setattr(module, "evidence_note_writer_skill", fake_writer)
    monkeypatch.setattr(module, "build_claim_verification_plan", lambda *args, **kwargs: FakePlan())
    monkeypatch.setattr(module, "derive_structured_risk_signals_from_plan", lambda plan: [{"name": "盈利压力"}])

    summary = module.run_bridge_smoke("黑芝麻智能", output_dir=str(tmp_path), write_evidence_notes=True)

    assert summary["evidence_note_status"] == "written"
    assert summary["evidence_note_summary"]["written_count"] == 1
    assert summary["claim_plan"] == {
        "high_credit_claims": 2,
        "low_credit_claims": 1,
        "verifications": 1,
        "skipped_files": 0,
    }
    assert summary["structured_risk_signals"] == [{"name": "盈利压力"}]


def test_bridge_smoke_writes_compact_audit_json(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: {"enabled": True})
    monkeypatch.setattr(module, "agent_reach_query_skill", lambda ctx: ctx)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", lambda ctx: ctx)
    monkeypatch.setattr(module, "agent_reach_quality_skill", lambda ctx: ctx)
    monkeypatch.setattr(module, "build_claim_verification_plan", lambda *args, **kwargs: type("P", (), {
        "high_credit_claims": [],
        "low_credit_claims": [],
        "verifications": [],
        "skipped_files": [],
    })())
    monkeypatch.setattr(module, "derive_structured_risk_signals_from_plan", lambda plan: [])

    summary = module.run_bridge_smoke(
        "黑芝麻智能",
        output_dir=str(tmp_path),
        date_str="20260614",
        write_audit=True,
    )

    audit_path = Path(summary["audit_path"])
    assert audit_path.exists()
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert data["stock_name"] == "黑芝麻智能"
    assert "content" not in str(data)


def test_bridge_smoke_main_json_output(monkeypatch, capsys):
    module = _load_module()

    def fake_run(**kwargs):
        return {
            "stock_name": kwargs["stock_name"],
            "claim_plan": {"high_credit_claims": 0},
            "structured_risk_signals": [],
        }

    monkeypatch.setattr(module, "run_bridge_smoke", fake_run)

    module.main(["--stock", "黑芝麻智能", "--json"])

    data = json.loads(capsys.readouterr().out)
    assert data["stock_name"] == "黑芝麻智能"
