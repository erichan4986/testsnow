"""Tests for PerStockReporter Source Intake config wiring."""

import sys
import types
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.stock_reporter import PerStockReporter


def test_default_reporter_does_not_enable_source_intake():
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


def test_source_intake_enabled_passes_flag():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {"enabled": True},
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
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("source_intake_enabled") is True
    assert call_input.get("source_intake_config") == {"enabled": True}


def test_source_intake_formal_first_policy_passes_context_and_pipeline_kwarg():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "canonical_synthesis_source_policy": "formal_first",
            },
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
        enable_source_intake=True,
        canonical_synthesis_source_policy="formal_first",
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input["canonical_synthesis_source_policy"] == "formal_first"


def test_pilot_stocks_enable_formal_first_source_policy_in_config():
    config_path = Path(__file__).resolve().parents[2] / "config" / "stocks.json"
    stocks = json.loads(config_path.read_text(encoding="utf-8"))
    by_name = {stock.get("name"): stock for stock in stocks}

    for stock_name in ("中际旭创", "圣邦股份", "黑芝麻智能"):
        source_intake = by_name[stock_name]["source_intake"]
        assert source_intake["enabled"] is True
        assert source_intake["canonical_synthesis_source_policy"] == "formal_first"


def test_fudan_microelectronics_config_present_and_wired():
    config_path = Path(__file__).resolve().parents[2] / "config" / "stocks.json"
    stocks = json.loads(config_path.read_text(encoding="utf-8"))
    by_name = {stock.get("name"): stock for stock in stocks}

    stock = by_name["复旦微电"]
    assert stock["code"] == "688385"
    assert stock["xueqiu_code"] == "SH688385"
    assert stock["gid"] == "688385"

    source_intake = stock["source_intake"]
    assert source_intake["enabled"] is True
    assert source_intake["canonical_synthesis_source_policy"] == "formal_first"

    a_stock = source_intake["a_stock"]
    assert a_stock["enabled"] is True
    assert a_stock["iwencai_industry_research"]["enabled"] is True

    assert source_intake["periodic_report_fulltext"]["enabled"] is True

    # 4.4 narrative generated -> curated external viewpoint narrative display is enabled
    narrative_cfg = source_intake["curated_external_viewpoint_narrative_synthesis_display"]
    assert narrative_cfg["enabled"] is True
    assert "fudan_20260702.json" in narrative_cfg["narrative_json"]


def test_source_intake_enabled_allows_empty_community_posts(monkeypatch):
    reporter = PerStockReporter(
        stocks_data={"测试股": []},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {"enabled": True, "a_stock": {"eastmoney_research_reports": {"enabled": True}}},
        },
    )

    mock_build = MagicMock()
    mock_pipeline = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.output.get.return_value = ""
    mock_pipeline.run.return_value = mock_ctx
    mock_build.return_value = mock_pipeline
    fake_report_skills = types.ModuleType("utils.report_skills")
    fake_report_skills.build_stock_report_pipeline = mock_build
    monkeypatch.setitem(sys.modules, "utils.report_skills", fake_report_skills)

    reporter.generate_stock_report("测试股", "/tmp/out")

    mock_build.assert_called_once()
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input["stocks_data"] == {"测试股": []}
    assert call_input["source_intake_enabled"] is True


def test_source_intake_periodic_fulltext_enabled_passes_pipeline_flag(tmp_path):
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "periodic_report_fulltext": {
                    "enabled": True,
                    "cache_dir": str(tmp_path),
                    "report_type": "annual_report",
                },
            },
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
        enable_source_intake=True,
        enable_periodic_report_fulltext_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("periodic_report_fulltext_cache_dir") == str(tmp_path)
    assert call_input.get("periodic_report_fulltext_report_type") == "annual_report"


def test_global_periodic_fulltext_flag_enables_source_intake_fulltext():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={"测试股": {"enabled": True}},
        enable_periodic_report_fulltext_intake=True,
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
        enable_source_intake=True,
        enable_periodic_report_fulltext_intake=True,
    )


def test_periodic_fulltext_stock_config_can_disable_global_flag():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "periodic_report_fulltext": {"enabled": False},
            }
        },
        enable_periodic_report_fulltext_intake=True,
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
        enable_source_intake=True,
    )


def test_periodic_narrative_cards_display_default_off():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={"测试股": {"enabled": True}},
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert "include_periodic_narrative_cards_in_synthesis_display" not in call_input
    assert "periodic_narrative_cards_max_display_items" not in call_input


def test_source_intake_periodic_narrative_cards_display_enabled_passes_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "periodic_narrative_cards_synthesis_display": {
                    "enabled": True,
                    "max_display_items": 8,
                },
            },
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
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("include_periodic_narrative_cards_in_synthesis_display") is True
    assert call_input.get("periodic_narrative_cards_max_display_items") == 8


def test_periodic_narrative_cards_display_requires_source_intake_enabled():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": False,
                "periodic_narrative_cards_synthesis_display": {"enabled": True},
            },
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
    assert "include_periodic_narrative_cards_in_synthesis_display" not in call_input


def test_source_intake_evidence_notes_enabled_without_agent_reach():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "evidence_notes": {"enabled": True},
            },
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
        enable_evidence_notes=True,
        enable_claim_risk_signals=False,
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_evidence_notes") is True
    assert call_input.get("evidence_notes_dry_run") is True


def test_source_intake_config_separate_from_agent_reach():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        agent_reach_configs={
            "测试股": {"enabled": True, "web_urls": ["https://example.com"]},
        },
        source_intake_configs={
            "测试股": {"enabled": True},
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
        enable_source_intake=True,
    )


def test_source_intake_disabled_per_stock():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {"enabled": False},
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


def test_source_intake_with_dry_run_false():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "evidence_notes": {"enabled": True, "dry_run": False},
            },
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
    assert call_input.get("evidence_notes_dry_run") is False


def test_source_intake_claim_verification_enabled_passes_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "claim_verification": {
                    "enabled": True,
                    "base_dir": "/tmp/kb",
                    "max_verified": 5,
                    "max_supported": 3,
                    "max_unverified": 2,
                },
            },
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
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("enable_claim_verification_context") is True
    assert call_input.get("claim_verification_base_dir") == "/tmp/kb"
    assert call_input.get("claim_verification_max_verified") == 5
    assert call_input.get("claim_verification_max_supported") == 3
    assert call_input.get("claim_verification_max_unverified") == 2


def test_broker_research_digest_display_default_off():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={"测试股": {"enabled": True}},
    )

    with patch("utils.report_skills.build_stock_report_pipeline") as mock_build:
        mock_pipeline = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.output.get.return_value = ""
        mock_pipeline.run.return_value = mock_ctx
        mock_build.return_value = mock_pipeline

        reporter.generate_stock_report("测试股", "/tmp/out")

    call_input = mock_pipeline.run.call_args[0][0]
    assert "include_broker_research_digest_in_synthesis_display" not in call_input
    assert "broker_research_digest_max_display_items" not in call_input


def test_source_intake_broker_research_digest_display_enabled_passes_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "broker_research_digest_synthesis_display": {
                    "enabled": True,
                    "max_display_items": 7,
                },
            },
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
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input.get("include_broker_research_digest_in_synthesis_display") is True
    assert call_input.get("broker_research_digest_max_display_items") == 7


def test_broker_research_digest_display_requires_source_intake_enabled():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": False,
                "broker_research_digest_synthesis_display": {"enabled": True},
            },
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
    assert "include_broker_research_digest_in_synthesis_display" not in call_input


def test_source_intake_curated_external_display_default_off():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={"测试股": {"enabled": True}},
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
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert "include_curated_external_evidence_cards_in_synthesis_display" not in call_input
    assert "curated_external_evidence_cards_json" not in call_input


def test_source_intake_legacy_curated_external_cards_config_is_ignored():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "curated_external_evidence_cards_synthesis_display": {
                    "enabled": True,
                    "cards_json": "/tmp/cards.json",
                    "max_display_items": 6,
                    "min_cards": 2,
                    "min_total_excerpt_chars": 900,
                },
            },
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
        enable_source_intake=True,
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert "include_curated_external_evidence_cards_in_synthesis_display" not in call_input
    assert "curated_external_evidence_cards_json" not in call_input


def test_source_intake_curated_external_viewpoint_digest_enabled_passes_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "curated_external_viewpoint_digest_synthesis_display": {
                    "enabled": True,
                    "digest_json": "/tmp/viewpoint_digest.json",
                },
            },
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
        enable_source_intake=True,
        include_curated_external_viewpoint_digest_in_deep_analysis_display=True,
        curated_external_viewpoint_digest_json="/tmp/viewpoint_digest.json",
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input["include_curated_external_viewpoint_digest_in_deep_analysis_display"] is True
    assert call_input["curated_external_viewpoint_digest_json"] == "/tmp/viewpoint_digest.json"


def test_source_intake_curated_external_viewpoint_narrative_enabled_passes_context():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": True,
                "curated_external_viewpoint_narrative_synthesis_display": {
                    "enabled": True,
                    "narrative_json": "/tmp/viewpoint_narrative.json",
                },
            },
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
        enable_source_intake=True,
        include_curated_external_viewpoint_narrative_in_deep_analysis_display=True,
        curated_external_viewpoint_narrative_json="/tmp/viewpoint_narrative.json",
    )
    call_input = mock_pipeline.run.call_args[0][0]
    assert call_input["include_curated_external_viewpoint_narrative_in_deep_analysis_display"] is True
    assert call_input["curated_external_viewpoint_narrative_json"] == "/tmp/viewpoint_narrative.json"


def test_curated_external_viewpoint_display_requires_source_intake_enabled():
    reporter = PerStockReporter(
        stocks_data={"测试股": [{"title": "t", "content": "c" * 50, "like": 100, "comment": 50}]},
        stock_codes={"测试股": "000001"},
        raw_data={"测试股": {}},
        source_intake_configs={
            "测试股": {
                "enabled": False,
                "curated_external_viewpoint_narrative_synthesis_display": {
                    "enabled": True,
                    "narrative_json": "/tmp/viewpoint_narrative.json",
                },
                "curated_external_viewpoint_digest_synthesis_display": {
                    "enabled": True,
                    "digest_json": "/tmp/viewpoint_digest.json",
                },
            },
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
    assert "include_curated_external_viewpoint_narrative_in_deep_analysis_display" not in call_input
    assert "include_curated_external_viewpoint_digest_in_deep_analysis_display" not in call_input
