"""Tests for a_stock_source_intake_skill."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from report_skills.a_stock_source_intake_skill import a_stock_source_intake_skill


def test_disabled_skill_does_not_call_helper():
    with patch("a_stock_source_intake.collect_a_stock_source_items") as mock_collect:
        ctx = SkillContext(
            input={
                "stock_name": "中简科技",
                "stock_code": "300777",
                "source_intake_enabled": False,
                "source_intake_config": {"enabled": False},
            }
        )
        result = a_stock_source_intake_skill(ctx)

    mock_collect.assert_not_called()
    assert result.get("source_intake_status") == "disabled"
    assert result.get("source_intake_items") == []
    assert result.get("source_intake_summary")["status"] == "disabled"


def test_enabled_skill_calls_helper_and_sets_ctx():
    fake_result = {
        "status": "ok",
        "items": [],
        "source_statuses": {
            "cninfo_announcements": {"status": "ok", "count": 2, "error": ""},
            "eastmoney_stock_news": {"status": "empty", "count": 0, "error": ""},
            "eastmoney_research_reports": {"status": "error", "count": 0, "error": "boom"},
        },
        "warnings": [],
    }

    with patch("a_stock_source_intake.collect_a_stock_source_items") as mock_collect:
        mock_collect.return_value = fake_result
        ctx = SkillContext(
            input={
                "stock_name": "中简科技",
                "stock_codes": {"中简科技": "300777"},
                "source_intake_enabled": True,
                "source_intake_config": {"enabled": True},
            }
        )
        result = a_stock_source_intake_skill(ctx)

    mock_collect.assert_called_once()
    assert result.get("source_intake_status") == "ok"
    assert result.get("source_intake_items") == []
    assert result.get("source_intake_summary")["cninfo_announcements"]["count"] == 2
    assert result.get("source_intake_error") == ""


def test_enabled_skill_uses_stock_codes_mapping():
    fake_result = {
        "status": "ok",
        "items": [],
        "source_statuses": {},
        "warnings": [],
    }

    with patch("a_stock_source_intake.collect_a_stock_source_items") as mock_collect:
        mock_collect.return_value = fake_result
        ctx = SkillContext(
            input={
                "stock_name": "中简科技",
                "stock_codes": {"中简科技": "300777"},
                "source_intake_enabled": True,
                "source_intake_config": {"enabled": True},
            }
        )
        a_stock_source_intake_skill(ctx)

    call_kwargs = mock_collect.call_args.kwargs
    assert call_kwargs["stock_name"] == "中简科技"
    assert call_kwargs["stock_code"] == "300777"


def test_missing_stock_code_returns_error():
    with patch("a_stock_source_intake.collect_a_stock_source_items") as mock_collect:
        ctx = SkillContext(
            input={
                "stock_name": "中简科技",
                "stock_codes": {},
                "source_intake_enabled": True,
                "source_intake_config": {"enabled": True},
            }
        )
        result = a_stock_source_intake_skill(ctx)

    mock_collect.assert_not_called()
    assert result.get("source_intake_status") == "error"
    assert "stock_code" in result.get("source_intake_error", "")
