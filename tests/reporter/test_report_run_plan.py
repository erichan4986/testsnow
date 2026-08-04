import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from utils.report_run_plan import ReportRunPlan, compile_report_run_plan
from external_pack import read_external_argument_pack_v4


@pytest.mark.parametrize(
    (
        "agent_cfg",
        "source_cfg",
        "global_agent",
        "expected_agent",
        "expected_source",
        "expected_context",
        "can_run",
    ),
    [
        ({}, {}, False, False, False, {"enable_claim_risk_signals": False}, False),
        (
            {"enabled": True},
            {},
            False,
            True,
            False,
            {"enable_claim_risk_signals": False, "enable_agent_reach": True},
            True,
        ),
        (
            {"enabled": False},
            {},
            True,
            True,
            False,
            {"enable_claim_risk_signals": False, "enable_agent_reach": True},
            True,
        ),
        (
            {},
            {"enabled": True},
            False,
            False,
            True,
            {
                "enable_claim_risk_signals": False,
                "source_intake_enabled": True,
                "source_intake_config": {"enabled": True},
            },
            True,
        ),
        ({"enabled": False}, {"enabled": False}, False, False, False, {"enable_claim_risk_signals": False}, False),
    ],
)
def test_compile_report_run_plan_core_gates(
    tmp_path,
    agent_cfg,
    source_cfg,
    global_agent,
    expected_agent,
    expected_source,
    expected_context,
    can_run,
):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config=agent_cfg,
        source_intake_config=source_cfg,
        global_agent_reach_enabled=global_agent,
    )

    assert isinstance(plan, ReportRunPlan)
    assert plan.pipeline_kwargs == {
        "enable_agent_reach": expected_agent,
        "enable_evidence_notes": False,
        "enable_claim_risk_signals": False,
        "enable_source_intake": expected_source,
    }
    assert plan.context_values == expected_context
    assert plan.can_run_without_posts is can_run


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("True", True), ("0", False), ("TRUE", False), (" true ", False)],
)
def test_agent_reach_environment_values_are_compiled_explicitly(tmp_path, value, expected):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={},
        environment={"ENABLE_AGENT_REACH": value},
    )

    assert plan.pipeline_kwargs["enable_agent_reach"] is expected
    assert plan.context_values.get("enable_agent_reach", False) is expected
    assert plan.can_run_without_posts is expected


def test_omitted_environment_does_not_read_process_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_AGENT_REACH", "1")
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={},
    )

    assert plan.pipeline_kwargs["enable_agent_reach"] is False
    assert "enable_agent_reach" not in plan.context_values


def test_agent_reach_context_preserves_urls_alias_and_optional_lists(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": True,
            "urls": ["https://example.test/a"],
            "rss_feeds": ["https://example.test/feed.xml"],
            "rss_filter_terms": ["光模块"],
            "official_domains": ["example.test"],
        },
        source_intake_config={},
    )
    assert plan.context_values == {
        "enable_claim_risk_signals": False,
        "enable_agent_reach": True,
        "agent_reach_urls": ["https://example.test/a"],
        "agent_reach_rss_feeds": ["https://example.test/feed.xml"],
        "agent_reach_rss_filter_terms": ["光模块"],
        "agent_reach_official_domains": ["example.test"],
    }


@pytest.mark.parametrize(
    ("child", "global_default", "expected"),
    [({}, False, False), ({}, True, True), ({"enabled": True}, False, True), ({"enabled": False}, True, False)],
)
def test_periodic_fulltext_nested_value_overrides_global(tmp_path, child, global_default, expected):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={"enabled": True, "periodic_report_fulltext": child},
        global_periodic_fulltext_enabled=global_default,
    )
    assert plan.pipeline_kwargs.get("enable_periodic_report_fulltext_intake", False) is expected


def test_child_displays_require_active_source_intake_and_keep_limits(tmp_path):
    source = {
        "enabled": True,
        "periodic_narrative_cards_synthesis_display": {"enabled": True, "max_display_items": 7},
        "broker_research_digest_synthesis_display": {"enabled": True, "max_display_items": 6},
        "curated_external_argument_pack_synthesis_display": {
            "enabled": True,
            "pack_json": "data/curated_external/argument_packs/sample.json",
        },
    }
    plan = compile_report_run_plan(repo_root=tmp_path, agent_reach_config={}, source_intake_config=source)
    assert plan.context_values["periodic_narrative_cards_max_display_items"] == 7
    assert plan.context_values["broker_research_digest_max_display_items"] == 6
    assert plan.context_values["curated_external_argument_pack_json"] == str(
        tmp_path / "data/curated_external/argument_packs/sample.json"
    )
    assert plan.pipeline_kwargs["curated_external_argument_pack_json"] == plan.context_values[
        "curated_external_argument_pack_json"
    ]


def test_evidence_payload_keeps_agent_block_precedence_when_source_enables_notes(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": False,
            "evidence_notes": {"enabled": True, "dry_run": False, "base_dir": "/agent/kb"},
        },
        source_intake_config={
            "enabled": True,
            "evidence_notes": {"enabled": True, "dry_run": True, "base_dir": "/source/kb"},
        },
    )
    assert plan.pipeline_kwargs["enable_evidence_notes"] is True
    assert plan.context_values["evidence_notes_dry_run"] is False
    assert plan.context_values["knowledge_base_dir"] == "/agent/kb"


@pytest.mark.parametrize(
    ("agent_enabled", "expected_enabled"),
    [(True, True), (False, False)],
)
def test_agent_evidence_notes_require_active_agent_parent(
    tmp_path, agent_enabled, expected_enabled
):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": agent_enabled,
            "evidence_notes": {
                "enabled": True,
                "dry_run": False,
                "base_dir": "/agent/kb",
            },
        },
        source_intake_config={},
    )
    assert plan.pipeline_kwargs["enable_evidence_notes"] is expected_enabled
    assert ("enable_evidence_notes" in plan.context_values) is expected_enabled
    if expected_enabled:
        assert plan.context_values["evidence_notes_dry_run"] is False
        assert plan.context_values["knowledge_base_dir"] == "/agent/kb"


def test_claim_precedence_and_risk_signal_independence(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "claim_verification": {
                "enabled": False,
                "risk_signals": True,
                "base_dir": "/agent/claims",
                "max_verified": 3,
                "max_supported": 2,
                "max_unverified": 1,
            }
        },
        source_intake_config={"enabled": True, "claim_verification": {"enabled": True}},
    )
    assert plan.pipeline_kwargs["enable_claim_risk_signals"] is True
    assert "enable_claim_verification_context" not in plan.context_values
    assert plan.context_values["claim_verification_base_dir"] == "/agent/claims"
    assert plan.context_values["claim_verification_max_verified"] == 3
    assert plan.context_values["claim_verification_max_supported"] == 2
    assert plan.context_values["claim_verification_max_unverified"] == 1


def test_agent_claim_verification_does_not_require_active_agent_source(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": False,
            "claim_verification": {
                "enabled": True,
                "base_dir": "/agent/claims",
                "max_verified": 3,
                "max_supported": 2,
                "max_unverified": 1,
            },
        },
        source_intake_config={},
    )
    assert plan.pipeline_kwargs["enable_agent_reach"] is False
    assert plan.context_values["enable_claim_verification_context"] is True
    assert plan.context_values["claim_verification_base_dir"] == "/agent/claims"
    assert plan.context_values["claim_verification_max_verified"] == 3
    assert plan.context_values["claim_verification_max_supported"] == 2
    assert plan.context_values["claim_verification_max_unverified"] == 1


def test_web_urls_take_precedence_over_legacy_urls_alias(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={
            "enabled": True,
            "web_urls": ["https://example.test/new"],
            "urls": ["https://example.test/legacy"],
        },
        source_intake_config={},
    )
    assert plan.context_values["agent_reach_urls"] == ["https://example.test/new"]


def test_disabled_source_parent_suppresses_all_child_displays(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": False,
            "periodic_report_fulltext": {"enabled": True, "cache_dir": "/tmp/cache"},
            "periodic_narrative_cards_synthesis_display": {"enabled": True, "max_display_items": 7},
            "broker_research_digest_synthesis_display": {"enabled": True, "max_display_items": 6},
            "curated_external_argument_pack_synthesis_display": {
                "enabled": True,
                "pack_json": "/tmp/pack.json",
            },
        },
        global_periodic_fulltext_enabled=True,
    )
    assert "enable_periodic_report_fulltext_intake" not in plan.pipeline_kwargs
    assert "include_curated_external_argument_pack_in_deep_analysis_display" not in plan.pipeline_kwargs
    assert plan.context_values == {"enable_claim_risk_signals": False}


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("formal_first", "formal_first"), ("legacy_mixed", None), ("", None)],
)
def test_only_formal_first_policy_is_emitted(tmp_path, policy, expected):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={"enabled": True, "canonical_synthesis_source_policy": policy},
    )
    assert plan.pipeline_kwargs.get("canonical_synthesis_source_policy") == expected
    assert plan.context_values.get("canonical_synthesis_source_policy") == expected


def test_absolute_pack_path_is_not_rebased(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "curated_external_argument_pack_synthesis_display": {
                "enabled": True,
                "pack_json": "/absolute/pack.json",
            },
        },
    )
    assert plan.pipeline_kwargs["curated_external_argument_pack_json"] == "/absolute/pack.json"


@pytest.mark.parametrize("pack_json", [None, 0, ""])
def test_empty_or_non_path_pack_value_stays_empty(tmp_path, pack_json):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "curated_external_argument_pack_synthesis_display": {
                "enabled": True,
                "pack_json": pack_json,
            },
        },
    )
    assert plan.pipeline_kwargs["curated_external_argument_pack_json"] == ""
    assert plan.context_values["curated_external_argument_pack_json"] == ""


def test_fulltext_cache_and_report_type_emit_only_when_enabled(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "periodic_report_fulltext": {
                "enabled": True,
                "cache_dir": "/tmp/annual-cache",
                "report_type": "annual_report",
            },
        },
    )
    assert plan.context_values["periodic_report_fulltext_cache_dir"] == "/tmp/annual-cache"
    assert plan.context_values["periodic_report_fulltext_report_type"] == "annual_report"


def test_malformed_nested_values_are_disabled(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={"evidence_notes": "invalid", "claim_verification": ["invalid"]},
        source_intake_config={
            "enabled": True,
            "periodic_report_fulltext": "invalid",
            "broker_research_digest_synthesis_display": 1,
        },
    )
    assert plan.pipeline_kwargs == {
        "enable_agent_reach": False,
        "enable_evidence_notes": False,
        "enable_claim_risk_signals": False,
        "enable_source_intake": True,
    }
    assert plan.context_values == {
        "enable_claim_risk_signals": False,
        "source_intake_enabled": True,
        "source_intake_config": {
            "enabled": True,
            "periodic_report_fulltext": "invalid",
            "broker_research_digest_synthesis_display": 1,
        },
    }


def test_source_intake_evidence_payload_is_used_without_agent_block(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={},
        source_intake_config={
            "enabled": True,
            "evidence_notes": {"enabled": True, "dry_run": False, "base_dir": "/source/kb"},
        },
    )
    assert plan.pipeline_kwargs["enable_evidence_notes"] is True
    assert plan.context_values["evidence_notes_dry_run"] is False
    assert plan.context_values["knowledge_base_dir"] == "/source/kb"


def test_source_claim_config_is_fallback_when_agent_claim_block_is_empty(tmp_path):
    plan = compile_report_run_plan(
        repo_root=tmp_path,
        agent_reach_config={"claim_verification": {}},
        source_intake_config={"claim_verification": {"enabled": True, "max_verified": 4}},
    )
    assert plan.context_values["enable_claim_verification_context"] is True
    assert plan.context_values["claim_verification_max_verified"] == 4


def _production_stock_configs():
    root = Path(__file__).resolve().parents[2]
    rows = json.loads((root / "config" / "stocks.json").read_text(encoding="utf-8"))
    return root, {row["name"]: row for row in rows}


def test_production_pilot_configs_use_formal_first_source_policy():
    _, configs = _production_stock_configs()
    for stock_name in ("中际旭创", "圣邦股份", "黑芝麻智能"):
        source = configs[stock_name]["source_intake"]
        assert source["enabled"] is True
        assert source["canonical_synthesis_source_policy"] == "formal_first"


def test_production_annual_review_configs_enable_annual_fulltext():
    _, configs = _production_stock_configs()
    for stock_name in ("中际旭创", "复旦微电", "黑芝麻智能"):
        fulltext = configs[stock_name]["source_intake"]["periodic_report_fulltext"]
        assert fulltext["enabled"] is True
        assert fulltext["report_type"] == "annual_report"


def test_production_zhongji_config_enables_broker_digest_display():
    _, configs = _production_stock_configs()
    broker = configs["中际旭创"]["source_intake"]["broker_research_digest_synthesis_display"]
    assert broker["enabled"] is True
    assert broker["max_display_items"] >= 5


def test_production_fudan_config_keeps_direct_relevance_fields():
    _, configs = _production_stock_configs()
    stock = configs["复旦微电"]
    assert stock["code"] == "688385"
    assert stock["xueqiu_code"] == "SH688385"
    assert stock["gid"] == "688385"
    assert "FPGA" in stock["industry"]
    assert "紫光国微" in stock["competitors"]
    assert stock["peer_codes"]["紫光国微"] == "002049"
    assert "产品线重叠" in stock["peer_dimensions"]
    assert "FPGA" in stock["product_exposure_terms"]
    assert "EEPROM" in stock["product_exposure_terms"]
    assert "MLCC" not in stock["product_exposure_terms"]
    source = stock["source_intake"]
    assert source["enabled"] is True
    assert source["canonical_synthesis_source_policy"] == "formal_first"
    assert source["a_stock"]["enabled"] is True
    assert source["a_stock"]["iwencai_industry_research"]["enabled"] is True
    assert source["periodic_report_fulltext"]["enabled"] is True


def test_production_peer_and_product_exposure_fields_are_present():
    _, configs = _production_stock_configs()
    zhongji = configs["中际旭创"]
    assert "光模块" in zhongji["industry"]
    assert "新易盛" in zhongji["competitors"]
    assert zhongji["peer_codes"]["新易盛"] == "300502"
    assert "光模块" in zhongji["product_exposure_terms"]
    assert "CPO" in zhongji["product_exposure_terms"]
    shengbang = configs["圣邦股份"]
    assert "模拟芯片" in shengbang["industry"]
    assert "思瑞浦" in shengbang["competitors"]
    assert shengbang["peer_codes"]["思瑞浦"] == "688536"
    assert "模拟芯片" in shengbang["product_exposure_terms"]
    assert "电源管理芯片" in shengbang["product_exposure_terms"]


def test_production_external_configs_point_to_readable_canonical_v4_packs():
    root, configs = _production_stock_configs()
    expected = {
        "中际旭创": "data/curated_external/argument_packs/zhongjixuchuang.json",
        "复旦微电": "data/curated_external/argument_packs/fudan.json",
        "黑芝麻智能": "data/curated_external/argument_packs/heizhima.json",
    }
    for stock_name, relative_path in expected.items():
        intake = configs[stock_name]["source_intake"]
        assert intake["curated_external_argument_pack_synthesis_display"] == {
            "enabled": True,
            "pack_json": relative_path,
        }
        assert {key for key in intake if key.startswith("curated_external_")} == {
            "curated_external_argument_pack_synthesis_display"
        }
        pack = json.loads((root / relative_path).read_text(encoding="utf-8"))
        assert read_external_argument_pack_v4(pack, expected_stock_name=stock_name)["status"] == "ok"
