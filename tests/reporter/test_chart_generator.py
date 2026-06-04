# tests/reporter/test_chart_generator.py
import pytest
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
from chart_generator import (
    generate_technical_panel,
    generate_bull_bear_chart,
    generate_radar_chart,
    generate_valuation_comparison,
)


def test_generate_technical_panel_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_tech.png"
        daily_data = {"close": [100.0, 101.0, 102.0], "volume": [1000, 2000, 1500]}
        result = generate_technical_panel(
            stock_name="测试股",
            daily_data=daily_data,
            patterns=[{"pattern": "双底", "bottom1": 90.0, "bottom2": 91.0, "neckline": 95.0}],
            indicators={"ma5": 101.0, "ma20": 100.0, "ma60": 98.0, "macd": 0.5, "macd_hist": 0.2, "rsi": 55.0},
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0


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
        assert output_path.stat().st_size > 0


def test_generate_radar_chart_creates_png():
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
        assert output_path.stat().st_size > 0


def test_generate_valuation_comparison_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_val.png"
        metrics = {
            "测试股": {"forward_pe": 70.0, "ps": 15.0},
            "竞品A": {"forward_pe": 120.0, "ps": 8.0},
            "竞品B": {"forward_pe": 200.0, "ps": 5.0},
        }
        result = generate_valuation_comparison(
            stock_name="测试股",
            competitor_metrics=metrics,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0
