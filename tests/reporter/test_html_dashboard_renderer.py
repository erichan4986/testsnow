"""Tests for HTMLDashboardRenderer."""

import pytest
from scripts.utils.reporter.sections import HTMLDashboardRenderer


def test_required_keys():
    renderer = HTMLDashboardRenderer()
    assert renderer.required_keys() == ["stock_name", "date_str"]


def test_render_missing_keys():
    renderer = HTMLDashboardRenderer()
    assert renderer.render({}) == ""
    assert renderer.render({"stock_name": "Test"}) == ""


def test_render_basic():
    renderer = HTMLDashboardRenderer()
    ctx = {
        "stock_name": "TestStock",
        "date_str": "20260605",
        "date_display": "2026年06月05日",
        "stock_codes": {"TestStock": "000001"},
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "<!DOCTYPE html>" in result
    assert "TestStock" in result
    assert "舆情 Dashboard" in result


def test_render_with_pillar():
    renderer = HTMLDashboardRenderer()
    ctx = {
        "stock_name": "TestStock",
        "date_str": "20260605",
        "date_display": "2026年06月05日",
        "stock_codes": {"TestStock": "000001"},
        "pillar": {
            "valuation": 7.0,
            "technical": 6.5,
            "sentiment": 5.0,
            "fundamental": 8.0,
            "fundflow": 4.0,
        },
    }
    result = renderer.render(ctx)
    assert "综合评分" in result
    assert "估值健康度" in result


def test_dashboard_uses_same_directory_chart_filenames():
    result = HTMLDashboardRenderer().render({
        "stock_name": "测试股",
        "date_str": "20260719",
        "stock_codes": {},
        "chart_paths": {
            "technical": "/tmp/测试股_technical.png",
            "bullbear": "/tmp/测试股_bullbear.png",
            "radar": "/tmp/测试股_radar.png",
            "valuation": "/tmp/测试股_valuation.png",
        },
    })

    assert "src='测试股_radar.png'" in result
    assert "src='测试股_technical.png'" in result
    assert "src='charts/" not in result


def test_dashboard_reads_nested_technical_judgment(monkeypatch):
    monkeypatch.setattr("scripts.utils.reporter.sections.html_dashboard_renderer.fetch_tencent_quote", lambda _code: None, raising=False)
    renderer = HTMLDashboardRenderer()
    ctx = {
        "stock_name": "TestStock", "date_str": "20260605", "stock_codes": {},
        "stock_raw": {"technical": {
            "price_target": {"profit_risk_ratio": 2.0},
            "indicators": {"_resonance": {"judgment": {
                "schema": "technical_judgment.v1",
                "trend": {"state": "strong_up"},
                "target": {
                    "direction": "bullish", "producer_status": "ready",
                    "reason_code": "target_ready", "structure_confidence": "high",
                    "effective_confidence": "high", "effective_label": "高",
                    "execution_state": "triggered", "display_mode": "full_targets",
                    "trigger_checks": {
                        name: {"status": "pass"}
                        for name in ("price", "trend", "volume", "momentum")
                    },
                },
                "action": {"state": "follow"},
            }}},
        }},
    }

    result = renderer.render(ctx)

    assert "2.0:1" in result
    assert "技术判断" in result
    assert "follow（高）" in result


def test_dashboard_fails_closed_for_contradictory_cached_judgment(monkeypatch):
    monkeypatch.setattr("scripts.utils.reporter.sections.html_dashboard_renderer.fetch_tencent_quote", lambda _code: None, raising=False)
    renderer = HTMLDashboardRenderer()
    ctx = {
        "stock_name": "TestStock", "date_str": "20260605", "stock_codes": {},
        "stock_raw": {"technical": {"indicators": {"_resonance": {"judgment": {
            "schema": "technical_judgment.v1",
            "trend": {"state": "unknown"},
            "target": {
                "direction": "neutral", "producer_status": "unavailable",
                "reason_code": "stale", "structure_confidence": "unavailable",
                "effective_confidence": "unavailable", "effective_label": "高",
                "execution_state": "unavailable", "display_mode": "full_targets",
                "trigger_checks": {
                    name: {"status": "pass"}
                    for name in ("price", "trend", "volume", "momentum")
                },
            },
            "action": {"state": "follow"},
        }}}}},
    }

    result = renderer.render(ctx)

    assert "follow（高）" not in result
    assert "unavailable（不可用）" in result


def test_render_prefers_synthesis_display(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda text, direction, *a, **k: captured.append(text) or [],
    )

    renderer = HTMLDashboardRenderer()
    ctx = {
        "stock_name": "TestStock",
        "date_str": "20260605",
        "date_display": "2026年06月05日",
        "stock_codes": {"TestStock": "000001"},
        "synthesis": {
            "valuation_debate": "baseline 估值。",
            "fundamentals": "baseline 基本面。",
        },
        "synthesis_display": {
            "valuation_debate": "enhanced 年报全文 估值。",
            "fundamentals": "enhanced 年报全文 基本面。",
        },
    }
    renderer.render(ctx)

    assert captured
    assert any("enhanced 年报全文" in t for t in captured)
    assert all("baseline" not in t for t in captured)


def test_render_falls_back_to_synthesis_when_no_display(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda text, direction, *a, **k: captured.append(text) or [],
    )

    renderer = HTMLDashboardRenderer()
    ctx = {
        "stock_name": "TestStock",
        "date_str": "20260605",
        "date_display": "2026年06月05日",
        "stock_codes": {"TestStock": "000001"},
        "synthesis": {
            "valuation_debate": "baseline 估值。",
            "fundamentals": "baseline 基本面。",
        },
    }
    renderer.render(ctx)

    assert any("baseline" in t for t in captured)
