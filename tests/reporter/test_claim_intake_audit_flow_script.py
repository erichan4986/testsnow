import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke_claim_intake_audit_flow.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_claim_intake_audit_flow", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flow_default_runs_audit_only(monkeypatch, tmp_path):
    module = _load_module()
    calls = []

    def fake_audit(**kwargs):
        calls.append(("audit", kwargs))
        return {"status": "written", "path": str(tmp_path / "audit.md"), "low_credit_claims": 2}

    monkeypatch.setattr(module, "run_claim_audit", fake_audit)
    summary = module.run_flow(stock="中简科技", code="300777", base_dir=str(tmp_path))

    assert [name for name, _ in calls] == ["audit"]
    assert summary["audit"]["low_credit_claims"] == 2
    assert summary["intakes"] == []


def test_flow_can_run_cached_and_fresh_before_audit(monkeypatch, tmp_path):
    module = _load_module()
    calls = []

    def fake_cached(**kwargs):
        calls.append(("cached", kwargs))
        return {"status": "written", "claim_count": 6}

    def fake_fresh(**kwargs):
        calls.append(("fresh", kwargs))
        return {"status": "written", "claim_count": 2}

    def fake_audit(**kwargs):
        calls.append(("audit", kwargs))
        return {"status": "written", "path": str(tmp_path / "audit.md"), "low_credit_claims": 8}

    monkeypatch.setattr(module, "run_cached_community_smoke", fake_cached)
    monkeypatch.setattr(module, "run_fresh_social_smoke", fake_fresh)
    monkeypatch.setattr(module, "run_claim_audit", fake_audit)

    summary = module.run_flow(
        stock="中简科技",
        code="300777",
        base_dir=str(tmp_path),
        cached_community=True,
        fresh_eastmoney_guba=True,
        write_inputs=True,
        overwrite=True,
    )

    assert [name for name, _ in calls] == ["cached", "fresh", "audit"]
    assert calls[0][1]["write"] is True
    assert calls[1][1]["write"] is True
    assert calls[1][1]["eastmoney_guba"] is True
    assert summary["intakes"][0]["name"] == "cached_community"
    assert summary["intakes"][1]["name"] == "fresh_social"
    assert summary["audit"]["low_credit_claims"] == 8


def test_flow_json_output(capsys, monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "run_flow",
        lambda **kwargs: {"stock": kwargs["stock"], "intakes": [], "audit": {"status": "written"}},
    )

    exit_code = module.main(["--stock", "中简科技", "--code", "300777", "--base-dir", str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)

    assert data["stock"] == "中简科技"
    assert data["audit"]["status"] == "written"
    assert exit_code == 0
