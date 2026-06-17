import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke_fresh_social_claims.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("smoke_fresh_social_claims", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_fresh_social_claims_dry_run_default_writes_nothing(monkeypatch, tmp_path):
    module = _load_module()
    calls = []

    def fake_write(**kwargs):
        calls.append(kwargs)
        return {"status": "dry_run", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_fresh_social_claim_note", fake_write)
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        urls=["https://guba.eastmoney.com/oa/300777.html"],
        write=False,
        date_str="20260615",
    )
    assert summary["status"] == "dry_run"
    assert calls[0]["dry_run"] is True


def test_smoke_fresh_social_claims_write_mode_passes_dry_run_false(monkeypatch, tmp_path):
    module = _load_module()

    def fake_write(**kwargs):
        assert kwargs["dry_run"] is False
        return {"status": "written", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_fresh_social_claim_note", fake_write)
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        urls=["https://guba.eastmoney.com/oa/300777.html"],
        write=True,
        date_str="20260615",
    )
    assert summary["status"] == "written"


def test_smoke_fresh_social_claims_no_urls_returns_empty(monkeypatch, tmp_path):
    module = _load_module()
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        urls=[],
        write=False,
        date_str="20260615",
    )
    assert summary["status"] == "empty"
    assert summary["claim_count"] == 0


def test_smoke_fresh_social_claims_provider_failure_records_status(monkeypatch, tmp_path):
    module = _load_module()

    def fake_fetch(url, timeout, **kwargs):
        return {"status": "error", "url": url, "text": "", "error": "connection refused", "claims": []}

    monkeypatch.setattr(module, "_fetch_url", fake_fetch)
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        urls=["https://guba.eastmoney.com/oa/300777.html"],
        write=False,
        date_str="20260615",
    )
    assert summary["status"] == "empty"
    assert any(p["status"] == "error" for p in summary.get("providers", []))


def test_fetch_url_extracts_claims_with_stock_context(monkeypatch):
    module = _load_module()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def getcode(self):
            return 200

        def read(self):
            return (
                "我认为中简科技的收入下降了，研发费用也增长不少。"
                "这只是股吧里的个人看法，需要后续用公告验证。"
            ).encode("utf-8")

    def fake_urlopen(req, timeout):
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    record = module._fetch_url(
        "https://guba.eastmoney.com/oa/300777.html",
        timeout=1,
        stock_name="中简科技",
        stock_code="300777",
    )

    assert record["status"] == "ok"
    assert len(record["claims"]) == 1
    assert record["claims"][0]["claim_status"] == "unverified_claim"


def test_eastmoney_guba_provider_extracts_scoped_title_claim():
    module = _load_module()
    provider = module._build_eastmoney_guba_provider_record(
        stock_name="中简科技",
        stock_code="300777",
        list_url="https://guba.eastmoney.com/list,300777.html",
        posts=[
            {
                "title": "我觉得研发费用增长不少，订单也有压力",
                "url": "https://guba.eastmoney.com/news,300777,1.html",
                "time": "06-15 12:48",
            }
        ],
    )

    assert provider["status"] == "ok"
    assert provider["platform"] == "股吧"
    assert provider["post_count"] == 1
    assert len(provider["claims"]) == 1
    assert provider["claims"][0]["source_url"].endswith("1.html")
    assert provider["claims"][0]["claim_status"] == "unverified_claim"


def test_smoke_fresh_social_claims_eastmoney_guba_flag_uses_direct_provider(monkeypatch, tmp_path):
    module = _load_module()

    def fake_fetch(stock_code, stock_name, timeout=15):
        return {
            "url": "https://guba.eastmoney.com/list,300777.html",
            "status": "ok",
            "platform": "股吧",
            "claims": [
                {
                    "claim_text": "股吧帖子：中简科技我觉得研发费用增长不少",
                    "claim_status": "unverified_claim",
                    "source_url": "https://guba.eastmoney.com/news,300777,1.html",
                    "source_platform": "股吧",
                }
            ],
            "error": "",
        }

    monkeypatch.setattr(module, "_fetch_eastmoney_guba_list", fake_fetch)
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        urls=[],
        eastmoney_guba=True,
        write=False,
        date_str="20260615",
    )

    assert summary["status"] == "dry_run"
    assert summary["claim_count"] == 1
    assert summary["eastmoney_guba"] is True
    assert summary["providers"][0]["platform"] == "股吧"


def test_smoke_fresh_social_claims_blocked_url_returns_blocked_status(monkeypatch, tmp_path):
    module = _load_module()
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        urls=["https://www.cninfo.com.cn/announcement/123.html"],
        write=False,
        date_str="20260615",
    )
    assert summary["status"] == "empty"
    assert any(p["status"] == "blocked" for p in summary.get("providers", []))


def test_smoke_fresh_social_claims_json_output(capsys, monkeypatch, tmp_path):
    module = _load_module()

    def fake_run_smoke(**kwargs):
        return {"stock_name": kwargs["stock_name"], "status": "empty", "claim_count": 0}

    monkeypatch.setattr(module, "run_smoke", fake_run_smoke)
    exit_code = module.main(["--stock", "中简科技", "--code", "300777", "--json", "--base-dir", str(tmp_path)])
    data = json.loads(capsys.readouterr().out)
    assert data["stock_name"] == "中简科技"
    assert data["status"] == "empty"
    assert exit_code is None or exit_code == 0


def test_smoke_fresh_social_claims_write_audit_writes_compact_json(monkeypatch, tmp_path):
    module = _load_module()
    audit_dir = tmp_path / "reports"
    audit_dir.mkdir()

    def fake_write(**kwargs):
        return {"status": "written", "claim_count": 1, "path": str(tmp_path / "note.md")}

    monkeypatch.setattr(module, "write_fresh_social_claim_note", fake_write)

    def fake_fetch(url, timeout, **kwargs):
        return {
            "status": "ok",
            "url": url,
            "text": "社区讨论内容",
            "claims": [],
        }

    monkeypatch.setattr(module, "_fetch_url", fake_fetch)
    summary = module.run_smoke(
        stock_name="中简科技",
        stock_code="300777",
        base_dir=str(tmp_path),
        output_dir=str(audit_dir),
        urls=["https://guba.eastmoney.com/oa/300777.html"],
        write=True,
        write_audit=True,
        date_str="20260615",
    )
    assert summary["status"] == "written"
    audit_files = list(audit_dir.glob("*.json"))
    assert len(audit_files) == 1
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
    assert "providers" in audit or "summary" in audit
    # Audit must not contain full page content.
    assert len(json.dumps(audit, ensure_ascii=False)) < 5000


def test_smoke_fresh_social_claims_url_limit_capped():
    module = _load_module()
    assert module.MAX_URLS == 5
    with pytest.raises(SystemExit):
        module._parse_args(["--stock", "中简科技", "--url", "https://x.com/1"] * 6)


def test_smoke_fresh_social_claims_parse_eastmoney_guba_flag():
    module = _load_module()
    args = module._parse_args(["--stock", "中简科技", "--eastmoney-guba"])
    assert args.eastmoney_guba is True


def test_smoke_fresh_social_claims_default_exit_code_zero_for_empty(monkeypatch, tmp_path):
    module = _load_module()
    exit_code = module.main(["--stock", "中简科技", "--code", "300777", "--base-dir", str(tmp_path), "--json"])
    assert exit_code is None or exit_code == 0
