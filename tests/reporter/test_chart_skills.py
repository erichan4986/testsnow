import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from unittest.mock import patch, MagicMock
from skill_pipeline import SkillContext
from report_skills.chart_skills import TechnicalAnalysisSkill, ChartGenerationSkill


class TestTechnicalAnalysisSkill:
    def test_runs_with_technical_data(self, tmp_path):
        ctx = SkillContext(input={
            "stock_name": "测试股",
            "stock_raw": {
                "technical": {
                    "daily_data": {
                        "close": [100.0] * 10,
                        "volume": [1000] * 10,
                        "open": [99.0] * 10,
                        "high": [101.0] * 10,
                        "low": [98.0] * 10,
                    },
                    "indicators": {
                        "rsi_14": 50.0,
                        "macd": 0.5,
                        "macd_hist": 0.2,
                        "macd_signal": 0.3,
                        "_patterns": [],
                        "_levels": {},
                        "_resonance": {
                            "trend": "多头",
                            "momentum": "中性",
                            "volume_price": "量价齐升",
                            "composite_score": 7,
                            "signals": [],
                        },
                    },
                },
            },
            "output_dir": str(tmp_path),
        })

        with patch("report_skills.chart_skills.generate_technical_panel", return_value=str(tmp_path / "tech.png")) as mock_gen:
            skill = TechnicalAnalysisSkill()
            result = skill.run(ctx)

        assert result.get("chart_technical") == str(tmp_path / "tech.png")
        mock_gen.assert_called_once()

    def test_skips_when_no_data(self, tmp_path):
        ctx = SkillContext(input={
            "stock_name": "测试股",
            "stock_raw": {},
            "output_dir": str(tmp_path),
        })

        skill = TechnicalAnalysisSkill()
        result = skill.run(ctx)

        assert result.get("chart_technical") is None


class TestChartGenerationSkill:
    def test_generates_all_charts(self, tmp_path):
        ctx = SkillContext(input={
            "stock_name": "测试股",
            "stock_raw": {
                "technical": {
                    "indicators": {
                        "_resonance": {"composite_score": 7, "trend": "多头"},
                    },
                },
            },
            "keep_posts": [
                {"title": "t1", "like": 100, "comment": 50, "content": "c1"},
            ],
            "quote": {"pe_ttm": 20.0},
            "consensus": {},
            "ind_fwd_pe": 25.0,
            "ps": None,
            "bullish_args": [{"text": "看好", "stars": 4, "credibility": "高"}],
            "bearish_args": [{"text": "谨慎", "stars": 2, "credibility": "中"}],
            "competitor_metrics": {"测试股": {"forward_pe": 18.0, "ps": 2.0}},
            "output_dir": str(tmp_path),
        })

        with patch("report_skills.chart_skills.compute_pillar_scores", return_value={
            "valuation": 6.0,
            "technical": 7.0,
            "sentiment": 5.0,
            "fundamental": 6.0,
            "fundflow": 4.0,
        }) as mock_score, \
             patch("report_skills.chart_skills.generate_radar_chart", return_value=str(tmp_path / "radar.png")) as mock_radar, \
             patch("report_skills.chart_skills.generate_bull_bear_chart", return_value=str(tmp_path / "bb.png")) as mock_bb, \
             patch("report_skills.chart_skills.generate_valuation_comparison", return_value=str(tmp_path / "val.png")) as mock_val:

            skill = ChartGenerationSkill()
            result = skill.run(ctx)

        assert result.get("chart_radar") == str(tmp_path / "radar.png")
        assert result.get("chart_bullbear") == str(tmp_path / "bb.png")
        assert result.get("chart_valuation") == str(tmp_path / "val.png")
        assert result.get("total_score") is not None
        assert "pillar_scores" in result.output
        mock_score.assert_called_once()
        mock_radar.assert_called_once()
        mock_bb.assert_called_once()
        mock_val.assert_called_once()

    def test_skips_valuation_without_competitor_metrics(self, tmp_path):
        ctx = SkillContext(input={
            "stock_name": "测试股",
            "stock_raw": {
                "technical": {
                    "indicators": {
                        "_resonance": {"composite_score": 7, "trend": "多头"},
                    },
                },
            },
            "keep_posts": [],
            "quote": None,
            "consensus": None,
            "ind_fwd_pe": None,
            "ps": None,
            "bullish_args": [],
            "bearish_args": [],
            "output_dir": str(tmp_path),
        })

        with patch("report_skills.chart_skills.compute_pillar_scores", return_value={
            "valuation": 5.0,
            "technical": 5.0,
            "sentiment": 5.0,
            "fundamental": 5.0,
            "fundflow": 5.0,
        }), \
             patch("report_skills.chart_skills.generate_radar_chart", return_value=str(tmp_path / "radar.png")), \
             patch("report_skills.chart_skills.generate_bull_bear_chart", return_value=str(tmp_path / "bb.png")):

            skill = ChartGenerationSkill()
            result = skill.run(ctx)

        assert result.get("chart_valuation") is None
        assert result.get("chart_radar") is not None
        assert result.get("chart_bullbear") is not None
