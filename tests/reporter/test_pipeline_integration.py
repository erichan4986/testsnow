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


def test_agent_reach_enabled_pipeline_has_14_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True)
    assert len(pipeline.skills) == 14


def test_agent_reach_skills_inserted_after_quality_gate():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    # agent_reach_query comes right after quality_gate
    assert names[2] == "agent_reach_query_skill"
    assert names[3] == "agent_reach_fetch_skill"
    assert names[4] == "agent_reach_quality_skill"
    # cross_source_consolidation comes after agent_reach_quality
    assert names[5] == "cross_source_consolidation_skill"


def test_agent_reach_disabled_pipeline_no_connector_calls_no_items():
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
                "output_dir": str(Path(__file__).parent / "tmp_out"),
                "stocks_data": {"测试股": [{"title": "t", "content": "优质内容" * 50, "like": 100, "comment": 50}]},
                "raw_data": {"测试股": {}},
                "stock_codes": {"测试股": "000001"},
            })
    mock_run.assert_not_called()
    # When disabled, agent_reach skills are not in the pipeline, so keys are unset
    assert ctx.get("agent_reach_items") is None
    assert ctx.get("agent_reach_status") is None


def test_evidence_notes_enabled_pipeline_has_15_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True, enable_evidence_notes=True)
    assert len(pipeline.skills) == 15


def test_evidence_note_writer_inserted_after_quality_gate():
    pipeline = build_stock_report_pipeline(enable_agent_reach=True, enable_evidence_notes=True)
    names = [getattr(s, "__name__", getattr(s, "name", type(s).__name__)) for s in pipeline.skills]
    assert names[2] == "agent_reach_query_skill"
    assert names[3] == "agent_reach_fetch_skill"
    assert names[4] == "agent_reach_quality_skill"
    assert names[5] == "evidence_note_writer_skill"
    assert names[6] == "cross_source_consolidation_skill"


def test_evidence_notes_without_agent_reach_is_11_skills():
    pipeline = build_stock_report_pipeline(enable_agent_reach=False, enable_evidence_notes=True)
    assert len(pipeline.skills) == 11
