"""Tests for scripts/smoke_agent_reach.py.

These tests prove that the smoke script:
- Only runs Agent-Reach query/fetch/quality skills.
- Does not import or instantiate full-report paths (PerStockReporter, ZhihuCollector, KnowledgeSynthesizer, PDF export, report assembly).
- Correctly handles enabled/disabled/unknown stocks.
- Writes compact audit JSON only when requested.
- Never stores full fetched content.
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


SMOKE_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke_agent_reach.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("smoke_agent_reach", SMOKE_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_source() -> str:
    return SMOKE_SCRIPT_PATH.read_text(encoding="utf-8")


def test_smoke_script_does_not_import_forbidden_modules():
    """Smoke script must not import PerStockReporter, ZhihuCollector, KnowledgeSynthesizer, export_pdf, or assembly skills."""
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
    }
    found = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name
                if name in forbidden:
                    found.add(name)
                # also catch module-level imports like utils.stock_reporter
                if alias.name in forbidden:
                    found.add(alias.name)
        # catch attribute imports like from utils.pdf_exporter import export_pdf
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name in forbidden:
                    found.add(alias.name)

    assert not found, f"smoke_agent_reach.py imports forbidden names: {found}"


def test_smoke_script_has_main_and_run_smoke_functions():
    module = _load_smoke_module()
    assert hasattr(module, "main")
    assert hasattr(module, "run_smoke")


def test_smoke_runs_only_query_fetch_quality(monkeypatch, tmp_path):
    """Smoke script must call only the three Agent-Reach skills, not full report pipeline."""
    module = _load_smoke_module()

    fake_config = {
        "黑芝麻智能": {
            "enabled": True,
            "web_urls": ["https://example.com/a"],
            "official_domains": ["example.com"],
        }
    }
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: fake_config.get(stock_name, {}))

    query_calls = []
    fetch_calls = []
    quality_calls = []

    def fake_query_skill(ctx):
        query_calls.append(ctx)
        ctx.set("search_queries", [{"query": "web_read", "target_platforms": ["web"]}])
        ctx.set("agent_reach_enabled", True)
        return ctx

    def fake_fetch_skill(ctx):
        fetch_calls.append(ctx)
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality_skill(ctx):
        quality_calls.append(ctx)
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_quality_summary", {"keep": 0, "demote": 0, "discard": 0, "total": 0})
        ctx.set("agent_reach_run_summary", {
            "stock_name": "黑芝麻智能",
            "counts": {"keep": 0, "demote": 0, "discard": 0, "total": 0},
            "warnings": [],
        })
        return ctx

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query_skill)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch_skill)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality_skill)

    summary = module.run_smoke("黑芝麻智能", output_dir=str(tmp_path))

    assert len(query_calls) == 1
    assert len(fetch_calls) == 1
    assert len(quality_calls) == 1
    assert summary["stock_name"] == "黑芝麻智能"
    assert summary["counts"]["total"] == 0


def test_smoke_disabled_stock(monkeypatch, tmp_path):
    module = _load_smoke_module()

    fake_config = {}
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: fake_config.get(stock_name, {}))

    def fake_query_skill(ctx):
        ctx.set("agent_reach_enabled", False)
        ctx.set("search_queries", [])
        return ctx

    def fake_fetch_skill(ctx):
        ctx.set("agent_reach_status", "disabled")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality_skill(ctx):
        ctx.set("agent_reach_quality_status", "disabled")
        ctx.set("agent_reach_run_summary", {
            "stock_name": "黑芝麻智能",
            "enabled": False,
            "counts": {"keep": 0, "demote": 0, "discard": 0, "total": 0},
            "warnings": [],
        })
        return ctx

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query_skill)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch_skill)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality_skill)

    summary = module.run_smoke("黑芝麻智能", output_dir=str(tmp_path))

    assert summary["enabled"] is False
    assert summary["quality_status"] == "disabled"


def test_smoke_unknown_stock(monkeypatch, tmp_path):
    module = _load_smoke_module()
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: {})

    summary = module.run_smoke("未知股票", output_dir=str(tmp_path))

    assert summary["enabled"] is False
    assert summary["stock_name"] == "未知股票"


def test_smoke_writes_audit_json(monkeypatch, tmp_path):
    module = _load_smoke_module()

    fake_config = {
        "黑芝麻智能": {
            "enabled": True,
            "web_urls": ["https://example.com/a"],
        }
    }
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: fake_config.get(stock_name, {}))

    def fake_query_skill(ctx):
        ctx.set("agent_reach_enabled", True)
        ctx.set("search_queries", [{"query": "web_read", "target_platforms": ["web"], "urls": ["https://example.com/a"]}])
        return ctx

    def fake_fetch_skill(ctx):
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality_skill(ctx):
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_run_summary", {
            "stock_name": "黑芝麻智能",
            "enabled": True,
            "counts": {"keep": 0, "demote": 0, "discard": 0, "total": 0},
            "warnings": [],
            "results": [],
        })
        return ctx

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query_skill)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch_skill)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality_skill)

    summary = module.run_smoke("黑芝麻智能", output_dir=str(tmp_path), date_str="20260613", write_audit=True)
    audit_path = summary["audit_path"]

    assert Path(audit_path).exists()
    assert Path(audit_path).name == "黑芝麻智能_20260613_agent_reach_smoke.json"
    data = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    assert data["stock_name"] == "黑芝麻智能"
    assert "content" not in str(data)


def test_smoke_default_does_not_write_audit(monkeypatch, tmp_path):
    module = _load_smoke_module()

    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: {"enabled": True})
    write_calls = []
    monkeypatch.setattr(module, "write_audit_summary", lambda *args, **kwargs: write_calls.append(args) or "audit.json")

    def fake_query_skill(ctx):
        ctx.set("agent_reach_enabled", True)
        return ctx

    def fake_fetch_skill(ctx):
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality_skill(ctx):
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_quality_summary", {"keep": 0, "demote": 0, "discard": 0, "total": 0})
        ctx.set("agent_reach_run_summary", {"stock_name": "黑芝麻智能", "counts": {"total": 0}, "warnings": []})
        return ctx

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query_skill)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch_skill)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality_skill)

    summary = module.run_smoke("黑芝麻智能", output_dir=str(tmp_path))

    assert "audit_path" not in summary
    assert write_calls == []


def test_smoke_dry_run_does_not_write_audit(monkeypatch, tmp_path):
    module = _load_smoke_module()

    fake_config = {
        "黑芝麻智能": {
            "enabled": True,
            "web_urls": ["https://example.com/a"],
        }
    }
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: fake_config.get(stock_name, {}))

    write_calls = []

    def fake_write(output_dir, date_str, summary):
        write_calls.append((output_dir, date_str, summary))
        return str(Path(output_dir) / "would_be_written.json")

    monkeypatch.setattr(module, "write_audit_summary", fake_write)

    def fake_query_skill(ctx):
        ctx.set("agent_reach_enabled", True)
        ctx.set("search_queries", [])
        return ctx

    def fake_fetch_skill(ctx):
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    def fake_quality_skill(ctx):
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_run_summary", {
            "stock_name": "黑芝麻智能",
            "enabled": True,
            "counts": {"keep": 0, "demote": 0, "discard": 0, "total": 0},
            "warnings": [],
        })
        return ctx

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query_skill)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch_skill)
    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality_skill)

    module.run_smoke("黑芝麻智能", output_dir=str(tmp_path), dry_run=True)

    assert len(write_calls) == 0


def test_smoke_summary_does_not_contain_full_content(monkeypatch, tmp_path):
    module = _load_smoke_module()

    fake_config = {
        "黑芝麻智能": {
            "enabled": True,
            "web_urls": ["https://example.com/a"],
        }
    }
    monkeypatch.setattr(module, "load_stock_config", lambda stock_name: fake_config.get(stock_name, {}))

    def fake_quality_skill(ctx):
        ctx.set("agent_reach_quality_status", "ok")
        ctx.set("agent_reach_run_summary", {
            "stock_name": "黑芝麻智能",
            "enabled": True,
            "counts": {"keep": 1, "demote": 0, "discard": 0, "total": 1},
            "warnings": [],
            "results": [
                {
                    "title": "Example",
                    "url": "https://example.com/a",
                    "score": 80,
                    "action": "keep",
                    # content key must NOT appear
                }
            ],
        })
        return ctx

    monkeypatch.setattr(module, "agent_reach_quality_skill", fake_quality_skill)

    def fake_query_skill(ctx):
        ctx.set("agent_reach_enabled", True)
        ctx.set("search_queries", [])
        return ctx

    def fake_fetch_skill(ctx):
        ctx.set("agent_reach_status", "ok")
        ctx.set("agent_reach_items", [])
        ctx.set("agent_reach_warnings", [])
        return ctx

    monkeypatch.setattr(module, "agent_reach_query_skill", fake_query_skill)
    monkeypatch.setattr(module, "agent_reach_fetch_skill", fake_fetch_skill)

    summary = module.run_smoke("黑芝麻智能", output_dir=str(tmp_path))

    assert "content" not in str(summary)


def test_smoke_loads_config_from_stocks_json(tmp_path, monkeypatch):
    """load_stock_config must read from config/stocks.json and return the agent_reach block for the named stock."""
    module = _load_smoke_module()
    fake_config = tmp_path / "stocks.json"
    fake_config.write_text(
        json.dumps([
            {
                "name": "黑芝麻智能",
                "agent_reach": {
                    "enabled": True,
                    "official_domains": ["blacksesame.com"],
                    "web_urls": ["https://www.blacksesame.com/a"],
                },
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_CONFIG_PATH", fake_config)
    cfg = module.load_stock_config("黑芝麻智能")
    assert cfg.get("enabled") is True
    assert "blacksesame.com" in cfg.get("official_domains", [])


def test_smoke_loads_zhongjian_cninfo_config_from_stocks_json(tmp_path, monkeypatch):
    module = _load_smoke_module()
    fake_config = tmp_path / "stocks.json"
    fake_config.write_text(
        json.dumps([
            {
                "name": "中简科技",
                "agent_reach": {
                    "enabled": True,
                    "official_domains": ["cninfo.com.cn"],
                    "web_urls": [
                        "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1",
                        "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=2",
                        "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=3",
                        "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=4",
                    ],
                },
            }
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_CONFIG_PATH", fake_config)
    cfg = module.load_stock_config("中简科技")
    assert cfg.get("enabled") is True
    assert "cninfo.com.cn" in cfg.get("official_domains", [])
    assert len(cfg.get("web_urls", [])) >= 4


def test_smoke_config_not_present_for_other_stocks(tmp_path, monkeypatch):
    module = _load_smoke_module()
    fake_config = tmp_path / "stocks.json"
    fake_config.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "_CONFIG_PATH", fake_config)
    for name in ["长春高新", "三花智控", "圣邦股份", "乐鑫科技"]:
        cfg = module.load_stock_config(name)
        assert not cfg.get("enabled", False), f"{name} must not have agent_reach.enabled"


def test_smoke_main_parses_stock_and_dry_run(monkeypatch, tmp_path):
    module = _load_smoke_module()

    run_calls = []

    def fake_run_smoke(stock_name, output_dir, date_str, dry_run, write_audit=False):
        run_calls.append((stock_name, output_dir, date_str, dry_run, write_audit))
        return {
            "stock_name": stock_name,
            "enabled": True,
            "fetch_status": "ok",
            "quality_status": "ok",
            "counts": {"keep": 0, "demote": 0, "discard": 0, "total": 0},
            "warnings": [],
        }

    monkeypatch.setattr(module, "run_smoke", fake_run_smoke)

    module.main(["--stock", "黑芝麻智能", "--dry-run", "--output-dir", str(tmp_path)])

    assert len(run_calls) == 1
    assert run_calls[0][0] == "黑芝麻智能"
    assert run_calls[0][3] is True
    assert run_calls[0][4] is False


def test_smoke_main_json_output(monkeypatch, capsys):
    module = _load_smoke_module()

    def fake_run_smoke(stock_name, output_dir, date_str, dry_run, write_audit=False):
        return {
            "stock_name": stock_name,
            "enabled": True,
            "fetch_status": "ok",
            "quality_status": "ok",
            "counts": {"keep": 1, "demote": 0, "discard": 0, "total": 1},
            "warnings": [],
        }

    monkeypatch.setattr(module, "run_smoke", fake_run_smoke)

    module.main(["--stock", "黑芝麻智能", "--json"])

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["stock_name"] == "黑芝麻智能"
    assert data["counts"]["keep"] == 1
