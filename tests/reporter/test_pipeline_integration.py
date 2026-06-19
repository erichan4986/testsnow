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


def test_agent_reach_enabled_pipeline_has_15_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True)
    assert len(pipeline.skills) == 15


def test_agent_reach_skills_inserted_after_quality_gate():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    # agent_reach_query comes right after quality_gate
    assert names[2] == "agent_reach_query_skill"
    assert names[3] == "agent_reach_fetch_skill"
    assert names[4] == "agent_reach_quality_skill"
    # source_intake_merge normalizes external evidence before cross_source_consolidation
    assert names[5] == "source_intake_merge_skill"
    assert names[6] == "cross_source_consolidation_skill"


def test_agent_reach_disabled_pipeline_no_connector_calls_no_items(tmp_path):
    pipeline = build_stock_report_pipeline(enable_agent_reach=False)
    with patch.object(
        __import__("report_skills.agent_reach_skill", fromlist=["RSSConnector"]).RSSConnector,
        "run",
    ) as mock_run:
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
    mock_run.assert_not_called()
    # When disabled, agent_reach skills are not in the pipeline, so keys are unset
    assert ctx.get("agent_reach_items") is None
    assert ctx.get("agent_reach_status") is None


def test_evidence_notes_enabled_pipeline_has_16_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True, enable_evidence_notes=True)
    assert len(pipeline.skills) == 16


def test_evidence_note_writer_inserted_after_quality_gate():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True, enable_evidence_notes=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[2] == "agent_reach_query_skill"
    assert names[3] == "agent_reach_fetch_skill"
    assert names[4] == "agent_reach_quality_skill"
    assert names[5] == "source_intake_merge_skill"
    assert names[6] == "evidence_note_writer_skill"
    assert names[7] == "cross_source_consolidation_skill"


def test_evidence_notes_without_agent_reach_is_11_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=False, enable_evidence_notes=True)
    assert len(pipeline.skills) == 11


def test_claim_risk_signals_only_has_12_skills():
    pipeline = build_stock_report_pipeline(enable_claim_risk_signals=True)
    assert len(pipeline.skills) == 12


def test_claim_risk_signal_skill_order():
    pipeline = build_stock_report_pipeline(enable_claim_risk_signals=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    synth_idx = names.index("synthesis")
    risk_idx = names.index("claim_risk_signal_skill")
    scoring_idx = names.index("scoring_skill")
    assert synth_idx < risk_idx < scoring_idx


def test_all_three_enabled_has_17_skills():
    pipeline = build_stock_report_pipeline(
        enable_agent_reach=True,
        enable_evidence_notes=True,
        enable_claim_risk_signals=True,
    )
    assert len(pipeline.skills) == 17


def test_source_intake_only_has_13_skills():
    pipeline = build_stock_report_pipeline(enable_source_intake=True)
    assert len(pipeline.skills) == 13


def test_source_intake_only_skill_order():
    pipeline = build_stock_report_pipeline(enable_source_intake=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[0] == "data_loading_skill"
    assert names[1] == "quality_gate_skill"
    assert names[2] == "a_stock_source_intake_skill"
    assert names[3] == "source_intake_merge_skill"
    assert names[4] == "cross_source_consolidation_skill"


def test_source_intake_and_evidence_notes_has_14_skills():
    pipeline = build_stock_report_pipeline(enable_source_intake=True, enable_evidence_notes=True)
    assert len(pipeline.skills) == 14


def test_source_intake_evidence_notes_order():
    pipeline = build_stock_report_pipeline(enable_source_intake=True, enable_evidence_notes=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[2] == "a_stock_source_intake_skill"
    assert names[3] == "source_intake_merge_skill"
    assert names[4] == "evidence_note_writer_skill"
    assert names[5] == "cross_source_consolidation_skill"


def test_agent_reach_and_source_intake_both_enabled_has_16_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True, enable_source_intake=True)
    assert len(pipeline.skills) == 16


def test_agent_reach_source_intake_evidence_notes_has_17_skills():
    pipeline = build_stock_report_pipeline(
        enable_agent_reach=True,
        enable_source_intake=True,
        enable_evidence_notes=True,
    )
    assert len(pipeline.skills) == 17


def test_all_external_paths_enabled_has_18_skills():
    pipeline = build_stock_report_pipeline(
        enable_agent_reach=True,
        enable_source_intake=True,
        enable_evidence_notes=True,
        enable_claim_risk_signals=True,
    )
    assert len(pipeline.skills) == 18


def test_periodic_report_fulltext_intake_disabled_by_default():
    pipeline = build_stock_report_pipeline()
    assert len(pipeline.skills) == 11


def test_periodic_report_fulltext_intake_only_has_12_skills():
    pipeline = build_stock_report_pipeline(enable_periodic_report_fulltext_intake=True)
    assert len(pipeline.skills) == 12


def test_periodic_report_fulltext_intake_order_when_alone():
    pipeline = build_stock_report_pipeline(enable_periodic_report_fulltext_intake=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[0] == "data_loading_skill"
    assert names[1] == "quality_gate_skill"
    assert names[2] == "periodic_report_fulltext_intake_skill"
    assert names[3] == "cross_source_consolidation_skill"


def test_periodic_report_fulltext_intake_with_source_intake_has_14_skills():
    pipeline = build_stock_report_pipeline(
        enable_source_intake=True,
        enable_periodic_report_fulltext_intake=True,
    )
    assert len(pipeline.skills) == 14


def test_periodic_report_fulltext_intake_order_after_source_intake_merge():
    pipeline = build_stock_report_pipeline(
        enable_source_intake=True,
        enable_periodic_report_fulltext_intake=True,
    )
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[2] == "a_stock_source_intake_skill"
    assert names[3] == "source_intake_merge_skill"
    assert names[4] == "periodic_report_fulltext_intake_skill"
    assert names[5] == "cross_source_consolidation_skill"


def test_periodic_report_fulltext_intake_with_agent_reach_and_evidence_notes():
    pipeline = build_stock_report_pipeline(
        enable_agent_reach=True,
        enable_evidence_notes=True,
        enable_periodic_report_fulltext_intake=True,
    )
    assert len(pipeline.skills) == 17
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[5] == "source_intake_merge_skill"
    assert names[6] == "periodic_report_fulltext_intake_skill"
    assert names[7] == "evidence_note_writer_skill"
    assert names[8] == "cross_source_consolidation_skill"


def test_all_five_external_paths_enabled_has_19_skills():
    pipeline = build_stock_report_pipeline(
        enable_agent_reach=True,
        enable_source_intake=True,
        enable_evidence_notes=True,
        enable_claim_risk_signals=True,
        enable_periodic_report_fulltext_intake=True,
    )
    assert len(pipeline.skills) == 19


def test_periodic_report_fulltext_intake_end_to_end_missing_cache(tmp_path):
    pipeline = build_stock_report_pipeline(enable_periodic_report_fulltext_intake=True)
    with patch("report_skills.technical_skills.TechnicalCollector") as mock_tc:
        mock_tc.return_value.collect.return_value = None
        ctx = pipeline.run({
            "stock_name": "测试股",
            "date_str": "20260604",
            "output_dir": str(tmp_path),
            "stocks_data": {"测试股": [{"title": "t", "content": "优质内容" * 50, "like": 100, "comment": 50}]},
            "raw_data": {"测试股": {}},
            "stock_codes": {"测试股": "000001"},
            "periodic_report_fulltext_cache_dir": str(tmp_path / "nonexistent"),
        })
    assert ctx.get("periodic_report_fulltext_items") == []
    assert ctx.get("periodic_report_fulltext_status") == "empty"
    assert ctx.get("md_path") is not None


def test_periodic_report_fulltext_intake_end_to_end_with_cache(tmp_path):
    cache_dir = tmp_path / "periodic_reports"
    cache_dir.mkdir()
    cache_file = cache_dir / "000001_2025_annual_jina.txt"
    cache_file.write_text("第一节 重要提示\n营业收入 100亿\n", encoding="utf-8")

    pipeline = build_stock_report_pipeline(enable_periodic_report_fulltext_intake=True)
    with patch("report_skills.technical_skills.TechnicalCollector") as mock_tc:
        mock_tc.return_value.collect.return_value = None
        ctx = pipeline.run({
            "stock_name": "测试股",
            "date_str": "20260604",
            "output_dir": str(tmp_path),
            "stocks_data": {"测试股": [{"title": "t", "content": "优质内容" * 50, "like": 100, "comment": 50}]},
            "raw_data": {"测试股": {}},
            "stock_codes": {"测试股": "000001"},
            "periodic_report_fulltext_cache_dir": str(cache_dir),
        })
    items = ctx.get("periodic_report_fulltext_items", [])
    assert len(items) == 1
    assert items[0].extra["source_type"] == "periodic_report_fulltext_analysis"
    assert items[0].extra["source_credit"] == 75
    assert items[0].extra["verification_status"] == "professional_analysis"
    assert items[0].extra["claim_status"] == "professional_analysis"
    assert items[0].extra["knowledge_eligible"] is False
    assert items[0].extra["report_eligible"] is False
    assert items[0].extra["experimental"] is True
    assert ctx.get("periodic_report_fulltext_status") == "ok"
    assert ctx.get("external_evidence_keep_items") is None
