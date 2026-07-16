"""Tests for the generic single-stock report entry."""

import importlib.util
import json
from pathlib import Path


def _load_entry_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "run_stock_report.py"
    spec = importlib.util.spec_from_file_location("run_stock_report", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_config(path: Path, stocks: list[dict]) -> None:
    path.write_text(json.dumps(stocks, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeReporter:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeReporter.instances.append(self)

    def generate_stock_report(self, stock_name, output_dir):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        md = out / f"{stock_name}_20260629.md"
        html = out / f"{stock_name}_20260629.html"
        md.write_text("# report", encoding="utf-8")
        html.write_text("<html></html>", encoding="utf-8")
        return str(md), str(html)


class _FailingZhihuCollector:
    def collect(self, *args, **kwargs):
        raise AssertionError("fast-test must not collect Zhihu")


def test_configured_stock_entry_wires_reporter_without_network(tmp_path, monkeypatch):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    raw_dir = tmp_path / "raw"
    report_dir = tmp_path / "reports"
    _write_config(
        config_path,
        [
            {
                "name": "测试股",
                "code": "300001",
                "xueqiu_code": "SZ300001",
                "gid": "300001",
                "keywords": ["测试股", "AI芯片"],
                "agent_reach": {"enabled": True, "web_urls": ["https://example.com"]},
                "source_intake": {"enabled": True, "curated_external_viewpoint_narrative_synthesis_display": {"enabled": True}},
            }
        ],
    )
    (raw_dir / "xueqiu_data_20260629_测试股.json").parent.mkdir(parents=True, exist_ok=True)
    (raw_dir / "xueqiu_data_20260629_测试股.json").write_text(
        json.dumps({"posts": [{"title": "缓存标题", "content": "", "like": 0, "comment": 0}], "gate_stats": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ZhihuCollector", _FailingZhihuCollector)
    monkeypatch.setattr(mod, "PerStockReporter", _FakeReporter)
    monkeypatch.setattr(mod, "export_pdf", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no pdf")))
    monkeypatch.setattr(mod, "fetch_all_stocks", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no fetch")))
    _FakeReporter.instances = []

    exit_code = mod.main(
        [
            "--stock",
            "测试股",
            "--config",
            str(config_path),
            "--raw-dir",
            str(raw_dir),
            "--report-dir",
            str(report_dir),
            "--date",
            "20260629",
            "--fast-test",
            "--no-pdf",
        ]
    )

    assert exit_code == 0
    assert len(_FakeReporter.instances) == 1
    kwargs = _FakeReporter.instances[0].kwargs
    assert kwargs["stock_codes"] == {"测试股": "300001"}
    assert kwargs["agent_reach_configs"] == {"测试股": {"enabled": True, "web_urls": ["https://example.com"]}}
    assert kwargs["source_intake_configs"] == {
        "测试股": {"enabled": True, "curated_external_viewpoint_narrative_synthesis_display": {"enabled": True}}
    }
    assert kwargs["stocks_data"]["测试股"][0]["content"] == "缓存标题"
    assert kwargs["stocks_data"]["测试股"][0]["like"] == 10
    raw_payload = json.loads((raw_dir / "report_input_20260629_测试股.json").read_text(encoding="utf-8"))
    assert raw_payload["stock_codes"] == {"测试股": "300001"}


def test_unknown_stock_requires_bootstrap_flag(tmp_path, capsys):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    _write_config(config_path, [])

    exit_code = mod.main(["--stock", "新股票", "--config", str(config_path), "--no-pdf"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--bootstrap-config" in captured.err
    assert "新股票" in captured.err


def test_bootstrap_preview_writes_tmp_config_without_mutating_config(tmp_path):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    preview_path = tmp_path / "preview.json"
    _write_config(config_path, [])

    exit_code = mod.main(
        [
            "--stock",
            "新股票",
            "--config",
            str(config_path),
            "--bootstrap-config",
            "--bootstrap-output",
            str(preview_path),
            "--code",
            "300999",
            "--xueqiu-code",
            "SZ300999",
            "--keyword",
            "先进封装",
        ]
    )

    assert exit_code == 0
    assert json.loads(config_path.read_text(encoding="utf-8")) == []
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    assert preview["name"] == "新股票"
    assert preview["code"] == "300999"
    assert preview["xueqiu_code"] == "SZ300999"
    assert preview["keywords"] == ["新股票", "先进封装"]
    assert preview["source_intake"]["enabled"] is True
    assert preview["source_intake"]["a_stock"]["enabled"] is True
    assert preview["source_intake"]["a_stock"]["cninfo_announcements"]["enabled"] is True
    assert preview["source_intake"]["a_stock"]["eastmoney_research_reports"]["enabled"] is True
    assert preview["source_intake"]["a_stock"]["eastmoney_global_news"]["enabled"] is True
    assert preview["source_intake"]["a_stock"]["iwencai_industry_research"]["enabled"] is True
    assert "先进封装" in preview["source_intake"]["a_stock"]["eastmoney_global_news"]["keywords"]


def test_bootstrap_write_config_requires_code(tmp_path, capsys):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    _write_config(config_path, [])

    exit_code = mod.main(["--stock", "新股票", "--config", str(config_path), "--bootstrap-config", "--write-config"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--code" in captured.err
    assert json.loads(config_path.read_text(encoding="utf-8")) == []


def test_bootstrap_write_config_appends_reviewed_stock(tmp_path):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    _write_config(config_path, [{"name": "已有", "code": "000001"}])

    exit_code = mod.main(
        [
            "--stock",
            "新股票",
            "--config",
            str(config_path),
            "--bootstrap-config",
            "--write-config",
            "--code",
            "300999",
            "--xueqiu-code",
            "SZ300999",
            "--keyword",
            "先进封装",
        ]
    )

    stocks = json.loads(config_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert [stock["name"] for stock in stocks] == ["已有", "新股票"]
    assert stocks[-1]["gid"] == "300999"
    assert stocks[-1]["source_intake"]["enabled"] is True
    assert stocks[-1]["source_intake"]["a_stock"]["eastmoney_research_reports"]["enabled"] is True


def test_zhongjixuchuang_config_has_canonical_a_stock_source_intake():
    mod = _load_entry_module()
    repo_root = Path(__file__).resolve().parents[2]
    stocks = mod._load_stocks_config(repo_root / "config" / "stocks.json")

    stock = mod._find_stock(stocks, "中际旭创")

    assert stock is not None
    source_intake = stock.get("source_intake", {})
    a_stock = source_intake.get("a_stock", {})
    assert source_intake.get("enabled") is True
    assert a_stock.get("enabled") is True
    assert a_stock.get("cninfo_announcements", {}).get("enabled") is True
    assert a_stock.get("eastmoney_research_reports", {}).get("enabled") is True
    assert a_stock.get("eastmoney_global_news", {}).get("enabled") is True
    assert a_stock.get("iwencai_industry_research", {}).get("enabled") is True
    keywords = a_stock.get("eastmoney_global_news", {}).get("keywords", [])
    assert {"光模块", "800G", "1.6T", "CPO", "AI算力"}.issubset(set(keywords))


def test_heizhima_config_enables_digest_enrichment_for_external_v2():
    mod = _load_entry_module()
    repo_root = Path(__file__).resolve().parents[2]
    stocks = mod._load_stocks_config(repo_root / "config" / "stocks.json")

    stock = mod._find_stock(stocks, "黑芝麻智能")

    assert stock is not None
    digest = stock["source_intake"]["curated_external_viewpoint_digest_synthesis_display"]
    assert digest == {
        "enabled": True,
        "digest_json": "data/curated_external/viewpoint_digests/heizhima_20260629.json",
    }


def test_offline_smoke_implies_fast_test_no_pdf_and_installs_patches(tmp_path, monkeypatch):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    raw_dir = tmp_path / "raw"
    report_dir = tmp_path / "reports"
    _write_config(
        config_path,
        [
            {
                "name": "测试股",
                "code": "300001",
                "xueqiu_code": "SZ300001",
                "gid": "300001",
            }
        ],
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    installed = []

    monkeypatch.setattr(mod, "_install_offline_smoke_patches", lambda: installed.append(True))
    monkeypatch.setattr(mod, "ZhihuCollector", _FailingZhihuCollector)
    monkeypatch.setattr(mod, "PerStockReporter", _FakeReporter)
    monkeypatch.setattr(mod, "export_pdf", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no pdf")))
    monkeypatch.setattr(mod, "fetch_all_stocks", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no fetch")))
    _FakeReporter.instances = []

    exit_code = mod.main(
        [
            "--stock",
            "测试股",
            "--config",
            str(config_path),
            "--raw-dir",
            str(raw_dir),
            "--report-dir",
            str(report_dir),
            "--date",
            "20260629",
            "--offline-smoke",
        ]
    )

    assert exit_code == 0
    assert installed == [True]
    assert _FakeReporter.instances[0].kwargs["stocks_data"] == {"测试股": []}


def test_offline_smoke_defaults_outputs_to_tmp(monkeypatch):
    mod = _load_entry_module()
    monkeypatch.setattr(mod, "_install_offline_smoke_patches", lambda: None)

    args = mod._parse_args(["--stock", "测试股", "--offline-smoke"])
    mod._apply_offline_smoke_mode(args)

    assert args.fast_test is True
    assert args.no_pdf is True
    assert args.raw_dir.startswith("/tmp/")
    assert args.report_dir.startswith("/tmp/")
    assert "offline_smoke" in args.raw_dir
    assert "offline_smoke" in args.report_dir


def test_offline_smoke_patches_quality_gate_to_rule_based(monkeypatch):
    mod = _load_entry_module()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")

    mod._install_offline_smoke_patches()

    import content_quality_gate

    assessor = content_quality_gate.LLMQualityAssessor()
    assert assessor.client is None


def test_offline_smoke_patches_consolidator_and_synthesizer_llm(monkeypatch):
    mod = _load_entry_module()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")

    mod._install_offline_smoke_patches()

    import content_consolidator
    import knowledge_synthesizer

    consolidator = content_consolidator.ContentConsolidator()
    synthesizer = knowledge_synthesizer.KnowledgeSynthesizer()
    assert consolidator._client is None
    assert synthesizer.client is None


def test_offline_smoke_patches_data_fetcher_lazy_fetches():
    mod = _load_entry_module()

    mod._install_offline_smoke_patches()

    import reporter.data_fetcher as data_fetcher

    assert data_fetcher.fetch_tencent_quote("02533") is None
    assert data_fetcher.fetch_consensus_eps("02533") is None
