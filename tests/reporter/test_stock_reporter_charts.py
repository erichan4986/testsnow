# tests/reporter/test_stock_reporter_charts.py
"""Integration tests for chart embedding in stock reporter."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from utils.stock_reporter import PerStockReporter


class TestStockReporterChartIntegration:
    def test_generate_stock_report_embeds_chart_images(self, tmp_path):
        """验证 generate_stock_report 在 Markdown 中嵌入了 4 张图表的图片引用。"""
        stock_name = "测试科技"
        posts = [
            {"title": "看好", "content": "增长突破", "_track": "featured"},
            {"title": "谨慎", "content": "风险压力", "_track": "sentiment"},
        ]
        raw_data = {
            stock_name: {
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
                "analysis": {},
            }
        }

        reporter = PerStockReporter(
            stocks_data={stock_name: posts},
            stock_codes={stock_name: "000001"},
            raw_data=raw_data,
        )

        # Mock chart generators so we don't need Kaleido/Plotly rendering
        fake_chart_path = str(tmp_path / "charts" / "fake.png")
        Path(fake_chart_path).parent.mkdir(parents=True, exist_ok=True)
        Path(fake_chart_path).write_text("fake png", encoding="utf-8")

        with patch(
            "utils.stock_reporter.generate_technical_panel", return_value=fake_chart_path
        ) as mock_tech, patch(
            "utils.stock_reporter.generate_bull_bear_chart", return_value=fake_chart_path
        ) as mock_bb, patch(
            "utils.stock_reporter.generate_radar_chart", return_value=fake_chart_path
        ) as mock_radar, patch(
            "utils.stock_reporter.generate_valuation_comparison", return_value=fake_chart_path
        ) as mock_val, patch(
            "utils.stock_reporter.fetch_tencent_quote", return_value={"pe_ttm": 15.0}
        ), patch(
            "utils.stock_reporter.fetch_consensus_eps", return_value={}
        ), patch(
            "utils.stock_reporter.industry_fwd_pe", return_value=18.0
        ), patch(
            "utils.stock_reporter.fetch_competitor_metrics", return_value={"测试科技": {"forward_pe": 15.0, "ps": 2.0}}
        ), patch(
            "utils.stock_reporter.competitor_metrics_table", return_value="## 竞争对手财务指标对比\n"
        ):
            md_path = reporter.generate_stock_report(stock_name, str(tmp_path))

        assert md_path
        md_content = Path(md_path).read_text(encoding="utf-8")

        # Assert all 4 chart image references are present
        # The actual path uses the real chart path pattern; verify by alt text and extension
        assert f"![{stock_name} 技术面分析](" in md_content
        assert f"![{stock_name} 多空论点对比](" in md_content
        assert f"![{stock_name} 五维评分雷达图](" in md_content
        assert f"![{stock_name} 估值对比](" in md_content

        # Assert chart generators were called
        mock_tech.assert_called_once()
        mock_bb.assert_called_once()
        mock_radar.assert_called_once()
        mock_val.assert_called_once()
