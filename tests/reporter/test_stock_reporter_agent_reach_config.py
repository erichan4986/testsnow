import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.stock_reporter import PerStockReporter


def test_default_reporter_does_not_enable_claim_risk_signals():
    """Default reporter without claim_verification.risk_signals should not enable it."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_claim_risk_signals") is False


def test_claim_risk_signals_enabled_passes_through():
    """claim_verification.risk_signals=True should pass enable_claim_risk_signals=True."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "claim_verification": {
                    "enabled": False,
                    "risk_signals": True,
                    "base_dir": "/tmp/kb",
                },
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=True,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_claim_risk_signals") is True
    assert "enable_claim_verification_context" not in call_input
    assert call_input.get("claim_verification_base_dir") == "/tmp/kb"


def test_claim_risk_signals_independent_of_claim_verification_enabled():
    """risk_signals=True should work even when claim_verification.enabled=False."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "claim_verification": {
                    "enabled": False,
                    "risk_signals": True,
                },
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_claim_risk_signals") is True
    assert "enable_claim_verification_context" not in call_input


def test_other_stocks_unaffected_by_claim_risk_signals_config():
    """Stocks without claim_verification.risk_signals should keep default behavior."""
    reporter = PerStockReporter(
        stocks_data={
            "测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}],
            "unaffected股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}],
        },
        stock_codes={"测试股": "000001", "unaffected股": "000002"},
        raw_data={"测试股": {}, "unaffected股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "claim_verification": {"enabled": False, "risk_signals": True},
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("unaffected股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )


def test_per_stock_claim_verification_enabled_without_agent_reach():
    """claim_verification.enabled=True should pass through and not require Agent-Reach."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "claim_verification": {
                    "enabled": True,
                    "base_dir": "/tmp/kb",
                    "max_verified": 3,
                    "max_supported": 2,
                    "max_unverified": 1,
                },
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_claim_verification_context") is True
    assert call_input.get("claim_verification_base_dir") == "/tmp/kb"
    assert call_input.get("claim_verification_max_verified") == 3
    assert call_input.get("claim_verification_max_supported") == 2
    assert call_input.get("claim_verification_max_unverified") == 1


def test_claim_verification_and_risk_signals_enable_independent_flags():
    """claim_verification.enabled and risk_signals=True should set both independent flags."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "claim_verification": {
                    "enabled": True,
                    "risk_signals": True,
                    "base_dir": "/tmp/kb",
                },
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=True,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_claim_verification_context") is True
    assert call_input.get("enable_claim_risk_signals") is True
    assert call_input.get("claim_verification_base_dir") == "/tmp/kb"


def test_per_stock_claim_verification_disabled_does_not_pass():
    """claim_verification.enabled=False should not pass any claim verification keys."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "claim_verification": {
                    "enabled": False,
                    "base_dir": "/tmp/kb",
                },
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert "enable_claim_verification_context" not in call_input
    assert "claim_verification_base_dir" not in call_input


def test_per_stock_agent_reach_official_domains_passed():
    """Per-stock agent_reach.official_domains should be passed into pipeline_input."""
    reporter = PerStockReporter(
        stocks_data={"黑芝麻智能": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"黑芝麻智能": "02533"},
        raw_data={"黑芝麻智能": {}},
        agent_reach_configs={
            "黑芝麻智能": {
                "enabled": True,
                "web_urls": ["https://www.blacksesame.com/a"],
                "official_domains": ["blacksesame.com"],
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("黑芝麻智能", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("agent_reach_official_domains") == ["blacksesame.com"]


def test_default_reporter_does_not_enable_agent_reach():
    """Default reporter without config should not enable Agent-Reach."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert "agent_reach_urls" not in call_input
    assert "agent_reach_rss_feeds" not in call_input
    assert "agent_reach_rss_filter_terms" not in call_input
    assert "enable_evidence_notes" not in call_input
    assert "agent_reach_official_domains" not in call_input


def test_per_stock_config_enables_agent_reach_and_passes_url():
    """Per-stock config with enabled=True should build 14-skill pipeline and pass URLs."""
    reporter = PerStockReporter(
        stocks_data={"黑芝麻智能": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"黑芝麻智能": "02533"},
        raw_data={"黑芝麻智能": {}},
        agent_reach_configs={
            "黑芝麻智能": {
                "enabled": True,
                "web_urls": ["https://www.blacksesame.com/zh/list_10/972.html"],
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("黑芝麻智能", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=True,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_agent_reach") is True
    assert call_input.get("agent_reach_urls") == ["https://www.blacksesame.com/zh/list_10/972.html"]


def test_disabled_per_stock_config_does_not_enable_agent_reach():
    """Config with enabled=False should not enable Agent-Reach even if URLs are present."""
    reporter = PerStockReporter(
        stocks_data={"黑芝麻智能": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"黑芝麻智能": "02533"},
        raw_data={"黑芝麻智能": {}},
        agent_reach_configs={
            "黑芝麻智能": {
                "enabled": False,
                "web_urls": ["https://example.com/article"],
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("黑芝麻智能", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert "agent_reach_urls" not in call_input
    assert "enable_evidence_notes" not in call_input


def test_global_enable_overrides_per_stock():
    """Global enable_agent_reach=True should enable for all stocks."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        enable_agent_reach=True,
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=True,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )


def test_rss_config_mapping_when_enabled():
    """RSS feeds and filter terms should be passed only when enabled."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": True,
                "rss_feeds": ["http://example.com/feed"],
                "rss_filter_terms": ["测试股"],
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("agent_reach_rss_feeds") == ["http://example.com/feed"]
    assert call_input.get("agent_reach_rss_filter_terms") == ["测试股"]


def test_urls_alias_backward_compatible():
    """Config key 'urls' should map to agent_reach_urls as an alias."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": True,
                "urls": ["https://example.com/article"],
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("agent_reach_urls") == ["https://example.com/article"]


def test_no_evidence_notes_config_does_not_enable_evidence_notes():
    """Default config without evidence_notes should pass enable_evidence_notes=False."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": True,
                "web_urls": ["https://example.com/article"],
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=True,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert "enable_evidence_notes" not in call_input


def test_evidence_notes_enabled_with_agent_reach():
    """Per-stock evidence_notes.enabled=True should enable writer with dry_run default True."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": True,
                "evidence_notes": {"enabled": True},
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=True,
        enable_evidence_notes=True,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_evidence_notes") is True
    assert call_input.get("evidence_notes_dry_run") is True


def test_evidence_notes_dry_run_and_base_dir_passed():
    """evidence_notes.dry_run=False and base_dir should be passed through."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": True,
                "evidence_notes": {
                    "enabled": True,
                    "dry_run": False,
                    "base_dir": "/tmp/evidence_kb",
                },
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=True,
        enable_evidence_notes=True,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("evidence_notes_dry_run") is False
    assert call_input.get("knowledge_base_dir") == "/tmp/evidence_kb"


def test_evidence_notes_enabled_without_agent_reach_does_not_enable():
    """evidence_notes.enabled=True without Agent-Reach should not enable writer."""
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {
                "enabled": False,
                "evidence_notes": {"enabled": True},
            }
        },
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once_with(
        enable_agent_reach=False,
        enable_evidence_notes=False,
        enable_claim_risk_signals=False,
        enable_source_intake=False,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert "enable_evidence_notes" not in call_input
