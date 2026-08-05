# tests/reporter/test_chart_generator.py
import pytest
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
from chart_generator import (
    _wrap_cjk,
    generate_decision_chain_chart,
    generate_technical_panel,
    generate_bull_bear_chart,
    generate_radar_chart,
)
from executive_summary_view import ExecutiveSummaryViewModel, SummaryNode
import chart_generator as chart_module


_KALEIDO_BROWSER_AVAILABLE = None


def _has_kaleido_browser():
    global _KALEIDO_BROWSER_AVAILABLE
    if _KALEIDO_BROWSER_AVAILABLE is not None:
        return _KALEIDO_BROWSER_AVAILABLE

    try:
        import plotly.graph_objects as go

        with tempfile.TemporaryDirectory() as tmpdir:
            probe_path = Path(tmpdir) / "kaleido_probe.png"
            fig = go.Figure(data=[go.Scatter(y=[1, 2, 3])])
            fig.write_image(str(probe_path), width=240, height=180, scale=1)
            _KALEIDO_BROWSER_AVAILABLE = probe_path.exists() and probe_path.stat().st_size > 0
    except Exception:
        _KALEIDO_BROWSER_AVAILABLE = False

    return _KALEIDO_BROWSER_AVAILABLE


@pytest.fixture(autouse=True)
def require_kaleido_browser(request):
    browser_free_tests = {
        "test_generate_decision_chain_chart_uses_fixed_canvas",
        "test_wrap_cjk_keeps_numeric_tokens_intact_and_limits_lines",
        "test_technical_panel_omits_scalar_momentum_panels",
        "test_technical_panel_uses_price_and_aligned_volume",
        "test_technical_panel_uses_canonical_ma_keys_without_range_slider",
        "test_technical_panel_rejects_insufficient_or_single_panel",
    }
    if request.node.name in browser_free_tests:
        return
    if not _has_kaleido_browser():
        pytest.skip("Kaleido/Chrome image export is unavailable in this environment")


def _daily_series(n=60, include_volume=True):
    close = [100.0 + index * 0.1 for index in range(n)]
    data = {
        "close": close,
        "open": [value - 0.2 for value in close],
        "high": [value + 0.5 for value in close],
        "low": [value - 0.5 for value in close],
    }
    if include_volume:
        data["volume"] = [1000 + index * 5 for index in range(n)]
    return data


def _capture_subplots(monkeypatch):
    captured = {}
    original = chart_module.make_subplots

    def wrapper(*args, **kwargs):
        captured["kwargs"] = kwargs
        captured["figure"] = original(*args, **kwargs)
        return captured["figure"]

    monkeypatch.setattr(chart_module, "make_subplots", wrapper)
    monkeypatch.setattr("plotly.graph_objects.Figure.write_image", lambda *args, **kwargs: None)
    return captured


def test_technical_panel_omits_scalar_momentum_panels(monkeypatch, tmp_path):
    captured = _capture_subplots(monkeypatch)

    result = generate_technical_panel(
        "测试股",
        _daily_series(),
        [],
        {"macd": 0.5, "macd_hist": 0.2, "rsi": 55.0},
        str(tmp_path / "tech.png"),
    )

    assert result == str(tmp_path / "tech.png")
    names = {trace.name for trace in captured["figure"].data}
    assert not names.intersection({"MACD", "MACD柱状", "MACD信号线", "RSI"})


def test_technical_panel_uses_price_and_aligned_volume(monkeypatch, tmp_path):
    captured = _capture_subplots(monkeypatch)

    generate_technical_panel("测试股", _daily_series(), [], {}, str(tmp_path / "tech.png"))

    assert captured["kwargs"]["rows"] == 2
    assert captured["kwargs"]["subplot_titles"] == ("价格与均线", "成交量")


def test_technical_panel_uses_canonical_ma_keys_without_range_slider(monkeypatch, tmp_path):
    captured = _capture_subplots(monkeypatch)

    generate_technical_panel(
        "测试股",
        _daily_series(),
        [],
        {"ma_5": 105.0, "ma_20": 103.0, "ma_60": 100.0},
        str(tmp_path / "tech.png"),
    )

    names = {trace.name for trace in captured["figure"].data}
    assert {"MA5", "MA20", "MA60"}.issubset(names)
    assert captured["figure"].layout.xaxis.rangeslider.visible is False


def test_technical_panel_rejects_insufficient_or_single_panel(monkeypatch, tmp_path):
    write_image = monkeypatch.setattr(
        "plotly.graph_objects.Figure.write_image", lambda *args, **kwargs: None
    )

    short = generate_technical_panel(
        "测试股", _daily_series(20), [], {}, str(tmp_path / "short.png")
    )
    price_only = generate_technical_panel(
        "测试股", _daily_series(include_volume=False), [], {"rsi": 55.0},
        str(tmp_path / "price-only.png"),
    )

    assert short is None
    assert price_only is None


def test_generate_technical_panel_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_tech.png"
        daily_data = _daily_series()
        result = generate_technical_panel(
            stock_name="测试股",
            daily_data=daily_data,
            patterns=[
                {
                    "pattern": "双底",
                    "bottom1": 90.0,
                    "bottom1_idx": 2,
                    "bottom2": 91.0,
                    "bottom2_idx": 5,
                    "neckline": 95.0,
                }
            ],
            indicators={
                "ma5": 101.0,
                "ma20": 100.0,
                "ma60": 98.0,
                "macd": 0.5,
                "macd_hist": 0.2,
                "rsi": 55.0,
            },
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 10_000


def test_generate_technical_panel_with_precomputed_ma():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_tech_ma.png"
        daily_data = _daily_series()
        precomputed_ma5 = [None] * 4 + [100.2 + index * 0.1 for index in range(56)]
        result = generate_technical_panel(
            stock_name="测试股",
            daily_data=daily_data,
            patterns=[],
            indicators={"ma5": precomputed_ma5, "macd": 0.5, "macd_hist": 0.2, "rsi": 55.0},
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 10_000


def test_generate_technical_panel_macd_signal_computed():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_tech_macd.png"
        daily_data = _daily_series()
        macd_series = [0.1 + index * 0.01 for index in range(60)]
        result = generate_technical_panel(
            stock_name="测试股",
            daily_data=daily_data,
            patterns=[],
            indicators={
                "macd": macd_series,
                "macd_hist": [0.05] * 60,
                "rsi": 55.0,
            },
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 10_000


def test_generate_bull_bear_chart_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_bb.png"
        bull_args = [
            {"text": "营收增长", "stars": 5, "credibility": "高"},
            {"text": "AI驱动", "stars": 4, "credibility": "高"},
        ]
        bear_args = [
            {"text": "利润下滑", "stars": 4, "credibility": "高"},
            {"text": "估值高", "stars": 3, "credibility": "中"},
        ]
        result = generate_bull_bear_chart(
            stock_name="测试股",
            bullish_args=bull_args,
            bearish_args=bear_args,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 10_000


def test_generate_radar_chart_creates_png_and_matches_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_radar.png"
        pillar = {
            "valuation": 8.0,
            "technical": 7.0,
            "sentiment": 4.0,
            "fundamental": 6.0,
            "fundflow": 5.0,
        }
        result = generate_radar_chart(
            stock_name="测试股",
            pillar_scores=pillar,
            total_score=6.8,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 10_000
        assert Path(result) == output_path


def _summary_view():
    return ExecutiveSummaryViewModel(
        stock_name="中际旭创",
        date_str="20260719",
        total_score="5.3 / 10",
        ev="+39.48%",
        recommendation="风险控制优先",
        recommendation_sentence="风险控制优先，等待趋势确认。",
        risk_level="中等风险",
        position_cap="0-5%",
        fundamental=SummaryNode("结构化基本面信号较强", "基本面评分 10/10", True),
        valuation=SummaryNode("盈利增长正在消化估值", "Forward PE 37.8x｜预期 EPS 增速 +65.5%", True),
        technical=SummaryNode("趋势失效 / 破坏期", "趋势健康度 26/100｜风险中等｜仓位 0-5%", True),
        action="风险控制优先",
    )


def test_generate_decision_chain_chart_creates_fixed_portrait_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "decision.png"

        result = generate_decision_chain_chart(_summary_view(), str(output_path))

        assert Path(result) == output_path
        assert output_path.exists()
        assert output_path.stat().st_size > 10_000


def test_generate_decision_chain_chart_uses_fixed_canvas():
    with patch("plotly.graph_objects.Figure.write_image") as write_image:
        generate_decision_chain_chart(_summary_view(), "/tmp/decision.png")

    write_image.assert_called_once_with("/tmp/decision.png", width=1240, height=1600, scale=1)


def test_wrap_cjk_keeps_numeric_tokens_intact_and_limits_lines():
    wrapped = _wrap_cjk("Forward PE 37.8x 与预期 EPS 增速 +65.5%共同构成估值参考", width=18, max_lines=2)

    assert "37.8x" in wrapped
    assert "+65.5%" in wrapped
    assert len(wrapped.split("<br>")) <= 2
