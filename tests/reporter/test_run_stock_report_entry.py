"""Tests for the generic single-stock report entry."""

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


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
                "source_intake": {"enabled": True, "curated_external_argument_pack_synthesis_display": {"enabled": True}},
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
            "--no-llm",
            "--no-pdf",
        ]
    )

    assert exit_code == 0
    assert len(_FakeReporter.instances) == 1
    kwargs = _FakeReporter.instances[0].kwargs
    assert kwargs["stock_codes"] == {"测试股": "300001"}
    assert kwargs["agent_reach_configs"] == {"测试股": {"enabled": True, "web_urls": ["https://example.com"]}}
    assert kwargs["source_intake_configs"] == {
        "测试股": {"enabled": True, "curated_external_argument_pack_synthesis_display": {"enabled": True}}
    }
    assert kwargs["report_llm_enabled"] is False
    assert kwargs["stocks_data"]["测试股"][0]["content"] == "缓存标题"
    assert kwargs["stocks_data"]["测试股"][0]["like"] == 10
    raw_payload = json.loads((raw_dir / "report_input_20260629_测试股.json").read_text(encoding="utf-8"))
    assert raw_payload["stock_codes"] == {"测试股": "300001"}


def test_unknown_stock_names_config_path_without_removed_bootstrap_flag(tmp_path, capsys):
    mod = _load_entry_module()
    config_path = tmp_path / "stocks.json"
    _write_config(config_path, [])

    exit_code = mod.main(["--stock", "新股票", "--config", str(config_path), "--no-pdf"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "新股票" in captured.err
    assert str(config_path) in captured.err
    assert "--bootstrap-config" not in captured.err


@pytest.mark.parametrize(
    "option",
    [
        "--bootstrap-config",
        "--write-config",
        "--bootstrap-output",
        "--code",
        "--xueqiu-code",
        "--gid",
    ],
)
def test_removed_bootstrap_options_are_rejected(option):
    mod = _load_entry_module()
    argv = ["--stock", "新股票", option]
    if option in {"--bootstrap-output", "--code", "--xueqiu-code", "--gid"}:
        argv.append("value")

    with pytest.raises(SystemExit) as exc_info:
        mod._parse_args(argv)

    assert exc_info.value.code == 2


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


def test_parse_markdown_post_reads_nested_interactions(tmp_path):
    mod = _load_entry_module()
    post_path = tmp_path / "post.md"
    post_path.write_text(
        "---\n"
        "title: 测试标题\n"
        "source_url: https://example.com/post\n"
        "interactions:\n"
        "  likes: 12\n"
        "  comments: 7\n"
        "---\n\n"
        "# 测试标题\n\n正文内容。\n",
        encoding="utf-8",
    )

    post = mod._parse_markdown_post(post_path)

    assert post == {
        "title": "测试标题",
        "content": "# 测试标题\n\n正文内容。",
        "url": "https://example.com/post",
        "like": 12,
        "comment": 7,
    }


def test_fast_test_without_local_posts_never_fetches_network(tmp_path, monkeypatch):
    mod = _load_entry_module()
    monkeypatch.setattr(mod, "_load_xueqiu_data", lambda *args: [])
    monkeypatch.setattr(mod, "_load_knowledge_posts", lambda *args: [])
    monkeypatch.setattr(
        mod,
        "fetch_all_stocks",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no fetch")),
    )

    posts = mod._load_posts(
        SimpleNamespace(fast_test=True),
        {"name": "测试股", "code": "300001"},
        tmp_path,
        "20260731",
    )

    assert posts == {"测试股": []}


def test_fast_test_reuses_cached_zhihu_data(tmp_path):
    mod = _load_entry_module()
    cached = {"total": 42, "report_items": [{"title": "cached"}], "fast_test": True}
    (tmp_path / "report_input_20260730_测试股.json").write_text(
        json.dumps({"raw_data": {"测试股": {"zhihu": cached}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = mod._collect_zhihu(
        SimpleNamespace(fast_test=True, keyword=[]),
        {"name": "测试股"},
        tmp_path,
        "20260731",
    )

    assert result == cached


def test_no_llm_keeps_zhihu_search_but_disables_curator(tmp_path, monkeypatch):
    mod = _load_entry_module()
    calls = {}

    class _Collector:
        def collect(self, **kwargs):
            calls.update(kwargs)
            return {"report_items": [], "knowledge_items": [], "total": 0}

    monkeypatch.setattr(mod, "ZhihuCollector", _Collector)
    result = mod._collect_zhihu(
        SimpleNamespace(fast_test=False, no_llm=True, keyword=["AI"]),
        {"name": "测试股", "keywords": ["芯片"]},
        tmp_path,
        "20260731",
    )

    assert result["total"] == 0
    assert calls["use_curator"] is False
    assert calls["keywords"] == ["测试股", "芯片", "AI"]


def test_parse_args_accepts_no_llm_flag():
    mod = _load_entry_module()

    args = mod._parse_args(["--stock", "测试股", "--no-llm"])

    assert args.no_llm is True


def test_cached_value_prefers_exact_filename_over_newer_fallback(tmp_path):
    mod = _load_entry_module()
    exact = tmp_path / "cache_20260804_测试股.json"
    fallback = tmp_path / "cache_20260803_测试股.json"
    exact.write_text(json.dumps({"value": "exact"}), encoding="utf-8")
    fallback.write_text(json.dumps({"value": "newer"}), encoding="utf-8")
    fallback.touch()

    value, path = mod._load_cached_value(
        tmp_path,
        exact.name,
        "cache_*_测试股.json",
        lambda payload: payload.get("value"),
        str,
    )

    assert value == "exact"
    assert path == exact


def test_cached_zhihu_skips_malformed_and_wrong_typed_candidates(tmp_path):
    mod = _load_entry_module()
    expected = {"total": 3, "report_items": []}
    (tmp_path / "report_input_20260802_测试股.json").write_text(
        json.dumps({"raw_data": {"测试股": {"zhihu": expected}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "report_input_20260803_测试股.json").write_text(
        json.dumps({"raw_data": {"测试股": {"zhihu": []}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "report_input_20260804_测试股.json").write_text("{broken", encoding="utf-8")

    result = mod._load_cached_zhihu_data(tmp_path, "测试股", "20260804")

    assert result == expected


def test_xueqiu_cache_filters_non_mapping_posts(tmp_path):
    mod = _load_entry_module()
    (tmp_path / "xueqiu_data_20260804_测试股.json").write_text(
        json.dumps({"posts": [{"title": "保留"}, "丢弃", 1, None]}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = mod._load_xueqiu_data(tmp_path, "测试股", "20260804")

    assert result == [{"title": "保留"}]


def test_named_stock_configs_keep_required_source_features():
    mod = _load_entry_module()
    repo_root = Path(__file__).resolve().parents[2]
    stocks = mod._load_stocks_config(repo_root / "config" / "stocks.json")

    black_sesame = mod._find_stock(stocks, "黑芝麻智能")
    shengbang = mod._find_stock(stocks, "圣邦股份")
    zhongjian = mod._find_stock(stocks, "中简科技")

    assert black_sesame["agent_reach"]["enabled"] is True
    assert black_sesame["source_intake"]["periodic_narrative_cards_synthesis_display"]["enabled"] is True
    assert shengbang["source_intake"]["periodic_report_fulltext"]["enabled"] is True
    assert shengbang["source_intake"]["periodic_narrative_cards_synthesis_display"]["enabled"] is True
    assert zhongjian["source_intake"]["a_stock"]["cninfo_announcements"]["enabled"] is True
    assert zhongjian["source_intake"]["claim_verification"]["enabled"] is True



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
    assert args.no_llm is True
    assert args.raw_dir.startswith("/tmp/")
    assert args.report_dir.startswith("/tmp/")
    assert "offline_smoke" in args.raw_dir
    assert "offline_smoke" in args.report_dir


def test_offline_smoke_patches_quality_gate_to_rule_based(monkeypatch):
    mod = _load_entry_module()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")

    from utils import content_quality_gate

    def fail_if_client_initializes(self):
        raise AssertionError("offline smoke must patch the pipeline quality gate")

    monkeypatch.setattr(
        content_quality_gate.LLMQualityAssessor,
        "_init_client",
        fail_if_client_initializes,
    )

    mod._install_offline_smoke_patches()

    assessor = content_quality_gate.LLMQualityAssessor()
    assert assessor.client is None


def test_offline_smoke_patches_consolidator_and_synthesizer_llm(monkeypatch):
    mod = _load_entry_module()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")

    from utils import content_consolidator, knowledge_synthesizer

    monkeypatch.setattr(
        content_consolidator.ContentConsolidator,
        "_init_llm",
        lambda self: (_ for _ in ()).throw(
            AssertionError("offline smoke must patch the pipeline consolidator")
        ),
    )
    monkeypatch.setattr(
        knowledge_synthesizer.KnowledgeSynthesizer,
        "_init_client",
        lambda self: (_ for _ in ()).throw(
            AssertionError("offline smoke must patch the pipeline synthesizer")
        ),
    )

    mod._install_offline_smoke_patches()

    consolidator = content_consolidator.ContentConsolidator()
    synthesizer = knowledge_synthesizer.KnowledgeSynthesizer()
    assert consolidator._client is None
    assert synthesizer.client is None


def test_offline_smoke_patches_data_fetcher_lazy_fetches(monkeypatch):
    mod = _load_entry_module()

    from utils.reporter import data_fetcher
    from utils.report_skills import data_skills

    names = (
        "fetch_tencent_quote",
        "fetch_consensus_eps",
        "industry_fwd_pe",
        "fetch_ps",
        "fetch_competitor_metrics",
    )
    for module in (data_fetcher, data_skills):
        for name in names:
            monkeypatch.setattr(
                module,
                name,
                lambda *args, **kwargs: (_ for _ in ()).throw(
                    AssertionError("offline smoke must patch every lazy fetch owner")
                ),
            )

    mod._install_offline_smoke_patches()

    for module in (data_fetcher, data_skills):
        for name in names:
            assert getattr(module, name)("02533") is None


def test_disable_functions_supports_mixed_call_signatures():
    mod = _load_entry_module()
    module = SimpleNamespace(one=lambda value: value, many=lambda *args, **kwargs: args)

    mod._disable_functions(module, ("one", "many"))

    assert module.one("value") is None
    assert module.many("value", another=True) is None


def test_offline_smoke_clears_key_restored_by_quality_gate_import(monkeypatch):
    mod = _load_entry_module()
    real_import_module = mod.importlib.import_module

    def import_module(name):
        module = real_import_module(name)
        if name == "utils.content_quality_gate":
            os.environ["DEEPSEEK_API_KEY"] = "restored-by-dotenv"
        return module

    monkeypatch.setattr(mod.importlib, "import_module", import_module)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "initial")

    mod._install_offline_smoke_patches()

    assert "DEEPSEEK_API_KEY" not in os.environ
