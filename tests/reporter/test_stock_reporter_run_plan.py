import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from utils.report_run_plan import ReportRunPlan
from utils.stock_reporter import PerStockReporter


def _pipeline_result(md="/tmp/report.md", html="/tmp/report.html"):
    pipeline = MagicMock()
    pipeline.run.return_value.output = {"md_path": md, "html_path": html}
    return pipeline


def test_reporter_forwards_one_compiled_plan_to_builder_and_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"content": "有效帖子"}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {"technical": {}}},
        stock_configs={"测试股": {"industry": "测试行业"}},
    )
    plan = ReportRunPlan(
        pipeline_kwargs={"enable_agent_reach": True},
        context_values={"enable_claim_risk_signals": False, "enable_agent_reach": True},
        can_run_without_posts=True,
    )
    pipeline = _pipeline_result()
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan) as compile_plan, patch(
        "utils.report_skills.build_stock_report_pipeline", return_value=pipeline
    ) as build:
        result = reporter.generate_stock_report("测试股", "/tmp/out")

    assert result == ("/tmp/report.md", "/tmp/report.html")
    compile_plan.assert_called_once()
    build.assert_called_once_with(enable_agent_reach=True)
    assert pipeline.run.call_args.args[0] == {
        "stock_name": "测试股",
        "date_str": reporter.date_str,
        "output_dir": "/tmp/out",
        "stocks_data": reporter.stocks_data,
        "raw_data": reporter.raw_data,
        "stock_codes": reporter.stock_codes,
        "stock_config": {"industry": "测试行业"},
        "enable_claim_risk_signals": False,
        "enable_agent_reach": True,
    }


def test_reporter_skips_empty_posts_when_plan_has_no_source():
    reporter = PerStockReporter(stocks_data={"测试股": []})
    plan = ReportRunPlan({}, {"enable_claim_risk_signals": False}, False)
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan), patch(
        "utils.report_skills.build_stock_report_pipeline"
    ) as build:
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")
    build.assert_not_called()


def test_reporter_runs_empty_posts_when_plan_has_active_source():
    reporter = PerStockReporter(stocks_data={"测试股": []})
    plan = ReportRunPlan({}, {"enable_claim_risk_signals": False}, True)
    pipeline = _pipeline_result("", "")
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan), patch(
        "utils.report_skills.build_stock_report_pipeline", return_value=pipeline
    ):
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")
    pipeline.run.assert_called_once()


def test_reporter_environment_only_enablement_builds_agent_branch_without_network(monkeypatch):
    monkeypatch.setenv("ENABLE_AGENT_REACH", "1")
    reporter = PerStockReporter(stocks_data={"测试股": []})
    pipeline = _pipeline_result("", "")

    with patch("utils.report_skills.build_stock_report_pipeline", return_value=pipeline) as build:
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")

    assert build.call_args.kwargs["enable_agent_reach"] is True
    pipeline.run.assert_called_once()
    assert pipeline.run.call_args.args[0]["enable_agent_reach"] is True


def test_reporter_returns_empty_paths_when_pipeline_raises():
    reporter = PerStockReporter(stocks_data={"测试股": [{"content": "有效帖子"}]})
    plan = ReportRunPlan({}, {"enable_claim_risk_signals": False}, False)
    pipeline = MagicMock()
    pipeline.run.side_effect = RuntimeError("boom")
    with patch("utils.stock_reporter.compile_report_run_plan", return_value=plan), patch(
        "utils.report_skills.build_stock_report_pipeline", return_value=pipeline
    ):
        assert reporter.generate_stock_report("测试股", "/tmp/out") == ("", "")
