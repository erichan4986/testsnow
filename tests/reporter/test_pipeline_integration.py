import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_skills import build_stock_report_pipeline


def test_pipeline_builder_returns_pipeline():
    pipeline = build_stock_report_pipeline()
    assert pipeline is not None
    assert len(pipeline.skills) == 11


def test_pipeline_end_to_end(tmp_path):
    pipeline = build_stock_report_pipeline()
    with patch("report_skills.technical_skills.TechnicalCollector") as mock_tc:
        mock_tc.return_value.collect.return_value = None
        ctx = pipeline.run({
            "stock_name": "测试股",
            "date_str": "20260604",
            "output_dir": str(tmp_path),
            "stocks_data": {"测试股": [{"title": "t", "content": "优质内容" * 50, "like": 100, "comment": 50}]},
            "raw_data": {"测试股": {}},
            "stock_codes": {"测试股": "000001"},
        })
    assert ctx.get("md_path") is not None
    assert ctx.get("html_path") is not None
