from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
ENTRIES = {
    "zhongjian": SCRIPTS_DIR / "run_中简科技技术分析_真实数据.py",
    "lexin": SCRIPTS_DIR / "run_乐鑫科技技术分析_真实数据.py",
    "lanqi": SCRIPTS_DIR / "run_澜起科技技术分析_真实数据.py",
}


def _load_entry(name: str):
    path = ENTRIES[name]
    spec = importlib.util.spec_from_file_location(f"test_technical_entry_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", ENTRIES.values())
def test_entries_use_one_shared_output_owner_and_one_import_root(path):
    source = path.read_text(encoding="utf-8")

    assert "def main(" in source
    assert source.count("write_technical_report(") == 1
    assert "from technical_report_entry import write_technical_report" in source
    assert "if str(UTILS_DIR) not in sys.path:" in source
    assert 'parent / "utils" / "reporter"' not in source
    assert "TechnicalRenderer" not in source
    assert "【核心指标】" not in source
    assert "【Phase 2 增强信号】" not in source


def test_zhongjian_keeps_fixed_csv_and_analyzer_call(monkeypatch):
    module = _load_entry("zhongjian")
    assert hasattr(module, "write_technical_report")
    frame = pd.DataFrame({
        "date": ["2026-08-01", "2026-08-04"],
        "close": [10.0, 10.5],
    })
    seen = {}
    def read_csv(path):
        seen["csv"] = path
        return frame.copy()

    def analyze(daily):
        seen["daily"] = daily
        return {
            "indicators": {"close": 10.5},
            "resonance": {"trend_state": {}},
            "price_target": {"display_mode": "levels_only"},
        }

    monkeypatch.setattr(module.pd, "read_csv", read_csv)
    monkeypatch.setattr(module, "analyze", analyze)
    sentinel = Path("report.md")
    def write_report(**kwargs):
        seen["output"] = kwargs
        return sentinel

    monkeypatch.setattr(module, "write_technical_report", write_report)

    result = module.main()

    assert result == sentinel
    assert str(seen["csv"]).endswith("data/raw/zhongjian_300777_daily_20260608.csv")
    assert seen["daily"]["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-08-01", "2026-08-04",
    ]
    assert seen["output"]["stock_name"] == "中简科技"
    assert seen["output"]["stock_code"] == "300777"
    assert seen["output"]["price_target"] == {"display_mode": "levels_only"}


class _Collector:
    def __init__(self, payload, *, daily=None, weekly=None):
        self.payload = payload
        self.daily = daily
        self.weekly = weekly
        self.calls = []

    def collect(self, *args, **kwargs):
        self.calls.append(("collect", args, kwargs))
        return self.payload

    def fetch_kline(self, *args, **kwargs):
        self.calls.append(("daily", args, kwargs))
        return self.daily

    def fetch_weekly_kline(self, *args, **kwargs):
        self.calls.append(("weekly", args, kwargs))
        return self.weekly


def _collector_payload():
    return {
        "adjustment": "qfq",
        "days": 250,
        "indicators": {"close": 20.0, "_resonance": {"trend_state": {}}},
        "price_target": {"display_mode": "levels_only"},
        "fund_flow": [],
        "concept_blocks": {"concept_tags": ["芯片"]},
    }


def test_lexin_preserves_collection_contract_and_forwards_optional_material(monkeypatch):
    module = _load_entry("lexin")
    assert hasattr(module, "TechnicalCollector")
    collector = _Collector(_collector_payload())
    seen = {}
    monkeypatch.setattr(module, "TechnicalCollector", lambda: collector)
    monkeypatch.setattr(module, "write_technical_report", lambda **kwargs: seen.update(kwargs) or Path("lexin.md"))

    result = module.main()

    assert result == Path("lexin.md")
    assert collector.calls == [
        ("collect", ("688018",), {"market": 1, "days": 250, "adjustment": "qfq"})
    ]
    assert seen["stock_name"] == "乐鑫科技"
    assert seen["price_target"] == {"display_mode": "levels_only"}
    assert seen["fund_flow"] == []
    assert seen["concept_blocks"] == {"concept_tags": ["芯片"]}


def test_lanqi_preserves_collection_and_csv_exports(monkeypatch, tmp_path):
    module = _load_entry("lanqi")
    assert hasattr(module, "TechnicalCollector")
    daily = pd.DataFrame({"date": ["2026-08-04"], "close": [20.0]})
    weekly = pd.DataFrame({"date": ["2026-08-01"], "close": [19.0]})
    collector = _Collector(_collector_payload(), daily=daily, weekly=weekly)
    seen = {}
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "TechnicalCollector", lambda: collector)
    monkeypatch.setattr(module, "write_technical_report", lambda **kwargs: seen.update(kwargs) or Path("lanqi.md"))

    result = module.main()

    assert result == Path("lanqi.md")
    assert collector.calls == [
        ("collect", ("688008",), {"market": 1, "days": 250, "adjustment": "qfq"}),
        ("daily", ("688008",), {"market": 1, "days": 250}),
        ("weekly", ("688008",), {"market": 1, "weeks": 72}),
    ]
    assert len(list((tmp_path / "data" / "raw").glob("lanqi_688008_daily_*_raw.csv"))) == 1
    assert len(list((tmp_path / "data" / "raw").glob("lanqi_688008_weekly_*.csv"))) == 1
    assert seen["stock_name"] == "澜起科技"
    assert seen["report_dir"] == tmp_path / "reports"


@pytest.mark.parametrize("name", ["lexin", "lanqi"])
def test_collector_entries_reject_empty_indicators_before_output(name, monkeypatch):
    module = _load_entry(name)
    assert hasattr(module, "TechnicalCollector")
    monkeypatch.setattr(module, "TechnicalCollector", lambda: _Collector({}))
    monkeypatch.setattr(
        module,
        "write_technical_report",
        lambda **kwargs: pytest.fail("output must not run for an empty payload"),
    )

    with pytest.raises(RuntimeError, match="未取得可用技术指标"):
        module.main()
