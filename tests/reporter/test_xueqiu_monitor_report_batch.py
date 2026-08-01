import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import xueqiu_monitor_v2


def test_generate_deep_reports_uses_source_order_and_returns_only_stock_outputs(tmp_path):
    stocks = [
        {"name": "甲", "code": "000001", "agent_reach": {"enabled": True}},
        {"name": "乙", "code": "000002"},
    ]
    reporter = MagicMock()
    reporter.generate_stock_report.side_effect = [
        ("/tmp/甲.md", "/tmp/甲.html"),
        ("", "/tmp/乙.html"),
    ]
    with patch("utils.stock_reporter.PerStockReporter", return_value=reporter) as reporter_cls:
        paths = xueqiu_monitor_v2._generate_deep_reports(
            stocks,
            {"甲": [], "乙": []},
            {"甲": {"technical": {}}, "乙": {}},
            tmp_path,
        )

    reporter_cls.assert_called_once_with(
        stocks_data={"甲": [], "乙": []},
        stock_codes={"甲": "000001", "乙": "000002"},
        raw_data={"甲": {"technical": {}}, "乙": {}},
        agent_reach_configs={"甲": {"enabled": True}},
    )
    assert reporter.generate_stock_report.call_args_list[0].args == ("甲", str(tmp_path))
    assert reporter.generate_stock_report.call_args_list[1].args == ("乙", str(tmp_path))
    assert paths == ["/tmp/甲.md", "/tmp/甲.html", "/tmp/乙.html"]
    assert all("xueqiu_summary_" not in path for path in paths)
