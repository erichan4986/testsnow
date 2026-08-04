from __future__ import annotations

import importlib
import logging
import sys
from datetime import date
from pathlib import Path


UTILS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "utils"


def _module():
    sys.path.insert(0, str(UTILS_DIR))
    try:
        return importlib.import_module("technical_report_entry")
    finally:
        sys.path.remove(str(UTILS_DIR))


class _Renderer:
    contexts = []

    def render(self, ctx):
        self.contexts.append(ctx)
        return "# rendered\n"


def _render(monkeypatch, tmp_path, **overrides):
    module = _module()
    _Renderer.contexts = []
    monkeypatch.setattr(module, "TechnicalRenderer", _Renderer)
    values = {
        "stock_name": "样例公司",
        "stock_code": "000001",
        "indicators": {"close": 10.5, "ma_5": 10.0},
        "resonance": {"trend_state": {}, "trend_health": {}},
        "report_dir": tmp_path,
        "report_date": date(2026, 8, 4),
    }
    values.update(overrides)
    path = module.write_technical_report(**values)
    return module, path, _Renderer.contexts[-1]


def test_renderer_context_copies_indicators_and_forwards_optional_material(
    monkeypatch, tmp_path
):
    indicators = {"close": 10.5}
    resonance = {"trend_state": {"stage": "修复期"}}
    _, _, ctx = _render(
        monkeypatch,
        tmp_path,
        indicators=indicators,
        resonance=resonance,
        price_target={"display_mode": "levels_only"},
        fund_flow=[],
        concept_blocks={"concept_tags": ["芯片"]},
    )

    technical = ctx["stock_raw"]["technical"]
    assert ctx["technical_render_mode"] == "full"
    assert ctx["chart_paths"] == {}
    assert technical["indicators"] == {"close": 10.5, "_resonance": resonance}
    assert technical["indicators"] is not indicators
    assert "_resonance" not in indicators
    assert technical["price_target"] == {"display_mode": "levels_only"}
    assert technical["fund_flow"] == []
    assert technical["concept_blocks"] == {"concept_tags": ["芯片"]}


def test_optional_material_is_omitted_when_not_supplied(monkeypatch, tmp_path):
    _, _, ctx = _render(monkeypatch, tmp_path)

    assert set(ctx["stock_raw"]["technical"]) == {"indicators"}


def test_report_path_content_and_date_are_stable(monkeypatch, tmp_path):
    _, path, _ = _render(monkeypatch, tmp_path)

    assert path == tmp_path / "样例公司_技术形态分析_真实数据_20260804.md"
    assert path.read_text(encoding="utf-8") == "# rendered\n"


def test_diagnostics_use_current_market_resonance(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    _render(
        monkeypatch,
        tmp_path,
        resonance={
            "trend_state": {},
            "trend_health": {},
            "market_regime": {"impact": "legacy-impact"},
            "market_resonance": {
                "state": "系统性压力",
                "confidence": "中",
                "impact": "保持谨慎",
                "missing": "行业指数",
            },
        },
    )

    assert "系统性压力（中）— 保持谨慎" in caplog.text
    assert "数据备注: 行业指数" in caplog.text
    assert "legacy-impact" not in caplog.text


def test_sparse_indicators_log_na_without_formatting_error(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)

    _render(monkeypatch, tmp_path, indicators={}, resonance={})

    assert "收盘价" in caplog.text
    assert "N/A" in caplog.text
