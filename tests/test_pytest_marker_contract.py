from pathlib import Path


def test_pytest_markers_are_registered():
    config = Path("pytest.ini").read_text(encoding="utf-8")

    for marker in [
        "slow:",
        "integration:",
        "legacy:",
        "external_material:",
        "report_core:",
    ]:
        assert marker in config


def test_reporter_path_marker_routing_contract():
    from tests.conftest import markers_for_path

    assert markers_for_path("tests/reporter/test_synthesis_skills.py") == {"report_core"}
    assert markers_for_path("tests/reporter/test_deep_analysis_renderer.py") == {"report_core"}
    assert markers_for_path("tests/reporter/test_phase3_integration.py") == set()
    assert markers_for_path("tests/reporter/test_lanqi_phase3_report.py") == set()
    assert markers_for_path("tests/reporter/test_run_black_sesame_entry.py") == {"integration"}
    assert markers_for_path("tests/reporter/test_chart_generator.py") == {"integration", "slow"}
    assert markers_for_path("tests/reporter/test_agent_reach_skills.py") == {"external_material"}
    assert markers_for_path("tests/reporter/test_wechat_targeted_discovery_preview.py") == {
        "external_material"
    }
    assert markers_for_path("tests/test_data_collector.py") == {"slow"}
