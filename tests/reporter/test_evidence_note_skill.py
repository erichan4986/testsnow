import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from source_adapter import SynthesisItem
from report_skills.evidence_note_skill import evidence_note_writer_skill


def _make_item(
    title="黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证",
    url="https://www.blacksesame.com/zh/list_10/972.html",
    source_credit=85,
    source_type="company_official",
    knowledge_eligible=True,
    quality_action="keep",
    **kwargs,
) -> SynthesisItem:
    extra = {
        "raw": {},
        "source_credit": source_credit,
        "source_type": source_type,
        "source_domain": "blacksesame.com",
        "verification_status": "primary_source",
        "credit_reasons": ["公司官网域名: blacksesame.com"],
        "knowledge_eligible": knowledge_eligible,
        "report_eligible": True,
        "agent_reach_quality_score": 70,
        "agent_reach_quality_action": quality_action,
    }
    extra.update(kwargs.get("extra", {}))
    return SynthesisItem(
        title=title,
        content=kwargs.get("content", "内容摘要。"),
        author=kwargs.get("author", ""),
        source_platform=kwargs.get("source_platform", "AgentReach(web)"),
        url=url,
        publish_time=kwargs.get("publish_time", "2026-06-08"),
        interaction_score=kwargs.get("interaction_score", 0),
        extra=extra,
    )


def _ctx_with_items(items, dry_run=True, enable_evidence_notes=True, quality_status="ok"):
    return SkillContext(
        input={
            "stock_name": "黑芝麻智能",
            "stock_codes": {"黑芝麻智能": "02533"},
            "agent_reach_enabled": True,
            "agent_reach_quality_status": quality_status,
            "agent_reach_keep_items": [i for i in items if i.extra.get("agent_reach_quality_action") == "keep"],
            "agent_reach_demote_items": [i for i in items if i.extra.get("agent_reach_quality_action") == "demote"],
            "enable_evidence_notes": enable_evidence_notes,
            "evidence_notes_dry_run": dry_run,
        }
    )


def test_disabled_does_not_call_writer(monkeypatch):
    called = False

    def fake_writer(*args, **kwargs):
        nonlocal called
        called = True
        return MagicMock()

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([_make_item()], enable_evidence_notes=False)
    result = evidence_note_writer_skill(ctx)

    assert called is False
    assert result.get("evidence_note_status") == "disabled"
    assert result.get("evidence_note_summary")["reason"] == "disabled"
    assert result.get("evidence_note_error") == ""


def test_noop_status_summary_has_stable_shape(monkeypatch):
    def fake_writer(*args, **kwargs):
        raise AssertionError("writer should not be called")

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([_make_item()], enable_evidence_notes=False)
    result = evidence_note_writer_skill(ctx)

    summary = result.get("evidence_note_summary")
    assert summary["written_count"] == 0
    assert summary["skipped_existing_count"] == 0
    assert summary["filtered_count"] == 0
    assert summary["dry_run"] is True
    assert summary["base_dir"].endswith("/testsnow/knowledge")
    assert summary["reason"] == "disabled"
    assert summary["collected_at"] == ""


def test_agent_reach_disabled_skips(monkeypatch):
    called = False

    def fake_writer(*args, **kwargs):
        nonlocal called
        called = True
        return MagicMock()

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([_make_item()])
    ctx.input["agent_reach_enabled"] = False
    result = evidence_note_writer_skill(ctx)

    assert called is False
    assert result.get("evidence_note_status") == "skipped"
    assert result.get("evidence_note_summary")["reason"] == "agent_reach_disabled"


def test_quality_status_not_ok_skips(monkeypatch):
    called = False

    def fake_writer(*args, **kwargs):
        nonlocal called
        called = True
        return MagicMock()

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([_make_item()], quality_status="empty")
    result = evidence_note_writer_skill(ctx)

    assert called is False
    assert result.get("evidence_note_status") == "skipped"
    assert "agent_reach_quality_status=empty" in result.get("evidence_note_summary")["reason"]


def test_empty_keep_demote_returns_empty(monkeypatch):
    called = False

    def fake_writer(*args, **kwargs):
        nonlocal called
        called = True
        return MagicMock()

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([])
    result = evidence_note_writer_skill(ctx)

    assert called is False
    assert result.get("evidence_note_status") == "empty"
    assert result.get("evidence_note_summary")["reason"] == "no_keep_or_demote_items"


def test_dry_run_returns_status_dry_run_and_plain_dict_plan(tmp_path, monkeypatch):
    item = _make_item()
    ctx = _ctx_with_items([item], dry_run=True)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    result = evidence_note_writer_skill(ctx)

    assert result.get("evidence_note_status") == "dry_run"
    plan = result.get("evidence_note_write_plan")
    assert isinstance(plan, dict)
    assert len(plan["written"]) == 1
    assert not (tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence").exists()
    summary = result.get("evidence_note_summary")
    assert summary["dry_run"] is True
    assert summary["collected_at"]


def test_real_write_returns_status_written_and_creates_file(tmp_path):
    item = _make_item()
    ctx = _ctx_with_items([item], dry_run=False)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    result = evidence_note_writer_skill(ctx)

    assert result.get("evidence_note_status") == "written"
    plan = result.get("evidence_note_write_plan")
    assert plan["written"]
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    assert evidence_dir.exists()
    files = list(evidence_dir.glob("*.md"))
    assert len(files) == 1
    summary = result.get("evidence_note_summary")
    assert summary["written_count"] == 1


def test_real_write_existing_evidence_returns_completed(tmp_path):
    item = _make_item()
    # First write
    ctx1 = _ctx_with_items([item], dry_run=False)
    ctx1.input["knowledge_base_dir"] = str(tmp_path)
    evidence_note_writer_skill(ctx1)

    # Second write with same canonical URL
    ctx2 = _ctx_with_items([item], dry_run=False)
    ctx2.input["knowledge_base_dir"] = str(tmp_path)
    result = evidence_note_writer_skill(ctx2)

    assert result.get("evidence_note_status") == "completed"
    assert result.get("evidence_note_summary")["written_count"] == 0
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    assert len(list(evidence_dir.glob("*.md"))) == 1


def test_keep_and_demote_both_passed_to_writer(tmp_path, monkeypatch):
    keep = _make_item(title="Keep item", quality_action="keep")
    demote = _make_item(title="Demote item", quality_action="demote", source_credit=45, source_type="social_discussion")

    captured = {}

    def fake_writer(stock_name, stock_code, items, base_dir, collected_at=None, dry_run=False):
        captured["items"] = items
        captured["dry_run"] = dry_run
        # Return a real plan-like object
        from evidence_note_writer import EvidenceWritePlan
        return EvidenceWritePlan(written=[{"title": i.title} for i in items], skipped_existing=[], filtered=[])

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([keep, demote], dry_run=False)
    ctx.input["knowledge_base_dir"] = str(tmp_path)
    result = evidence_note_writer_skill(ctx)

    assert len(captured["items"]) == 2
    titles = {i.title for i in captured["items"]}
    assert titles == {"Keep item", "Demote item"}
    assert result.get("evidence_note_status") == "written"


def test_keep_demote_lists_unchanged_after_skill_runs(tmp_path):
    keep = _make_item(title="Keep item", quality_action="keep")
    demote = _make_item(title="Demote item", quality_action="demote", source_credit=45, source_type="social_discussion")

    ctx = _ctx_with_items([keep, demote], dry_run=False)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    original_keep = ctx.input["agent_reach_keep_items"]
    original_demote = ctx.input["agent_reach_demote_items"]

    evidence_note_writer_skill(ctx)

    assert ctx.input["agent_reach_keep_items"] is original_keep
    assert ctx.input["agent_reach_demote_items"] is original_demote
    assert len(ctx.input["agent_reach_keep_items"]) == 1
    assert len(ctx.input["agent_reach_demote_items"]) == 1


def test_writer_exception_returns_error_and_does_not_raise(monkeypatch):
    def fake_writer(*args, **kwargs):
        raise RuntimeError("writer boom")

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([_make_item()], dry_run=False)
    result = evidence_note_writer_skill(ctx)

    assert result.get("evidence_note_status") == "error"
    assert "writer boom" in result.get("evidence_note_error")
    assert result.get("evidence_note_summary")["reason"] == "writer_error"


def test_default_base_dir_resolves_to_repo_root_knowledge(monkeypatch):
    captured = {}

    def fake_writer(stock_name, stock_code, items, base_dir, collected_at=None, dry_run=False):
        captured["base_dir"] = base_dir
        from evidence_note_writer import EvidenceWritePlan
        return EvidenceWritePlan(written=[], skipped_existing=[], filtered=[])

    monkeypatch.setattr(
        "report_skills.evidence_note_skill.write_evidence_notes",
        fake_writer,
    )

    ctx = _ctx_with_items([_make_item()], dry_run=False)
    # Do not set knowledge_base_dir
    evidence_note_writer_skill(ctx)

    assert str(captured["base_dir"]).endswith("/testsnow/knowledge")


def test_summary_counts_match_plan(tmp_path):
    keep = _make_item(title="Keep A", quality_action="keep")
    demote = _make_item(title="Demote B", quality_action="demote", source_credit=45, source_type="social_discussion")

    ctx = _ctx_with_items([keep, demote], dry_run=True)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    result = evidence_note_writer_skill(ctx)
    summary = result.get("evidence_note_summary")
    plan = result.get("evidence_note_write_plan")

    assert summary["written_count"] == len(plan["written"])
    assert summary["skipped_existing_count"] == len(plan["skipped_existing"])
    assert summary["filtered_count"] == len(plan["filtered"])
    assert summary["dry_run"] is True
    assert summary["base_dir"] == str(tmp_path)


def _ctx_with_external_items(items, dry_run=True, enable_evidence_notes=True):
    return SkillContext(
        input={
            "stock_name": "中简科技",
            "stock_codes": {"中简科技": "300777"},
            "agent_reach_enabled": False,
            "agent_reach_quality_status": "",
            "agent_reach_keep_items": [],
            "agent_reach_demote_items": [],
            "enable_evidence_notes": enable_evidence_notes,
            "evidence_notes_dry_run": dry_run,
            "external_evidence_keep_items": items,
            "external_evidence_demote_items": [],
        }
    )


def test_source_intake_only_can_write_evidence_notes_without_agent_reach(tmp_path):
    item = _make_item(title="cninfo公告", source_credit=95, source_type="exchange_announcement")
    ctx = _ctx_with_external_items([item], dry_run=True)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    result = evidence_note_writer_skill(ctx)

    assert result.get("evidence_note_status") == "dry_run"
    plan = result.get("evidence_note_write_plan")
    assert len(plan["written"]) == 1


def test_source_intake_empty_merged_buckets_returns_empty_not_agent_reach_disabled(tmp_path):
    ctx = _ctx_with_external_items([], dry_run=True)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    result = evidence_note_writer_skill(ctx)

    assert result.get("evidence_note_status") == "empty"
    assert result.get("evidence_note_summary")["reason"] == "no_keep_or_demote_items"


def test_prefers_external_evidence_over_agent_reach_buckets():
    external_item = _make_item(title="external", source_credit=95, source_type="exchange_announcement")
    agent_item = _make_item(title="agent", source_credit=70, source_type="web")

    captured = {}

    def fake_writer(stock_name, stock_code, items, base_dir, collected_at=None, dry_run=False):
        captured["items"] = items
        from evidence_note_writer import EvidenceWritePlan
        return EvidenceWritePlan(written=[{"title": i.title} for i in items], skipped_existing=[], filtered=[])

    import report_skills.evidence_note_skill as ens

    original_writer = ens.write_evidence_notes
    ens.write_evidence_notes = fake_writer
    try:
        ctx = SkillContext(
            input={
                "stock_name": "中简科技",
                "stock_codes": {"中简科技": "300777"},
                "agent_reach_enabled": True,
                "agent_reach_quality_status": "ok",
                "agent_reach_keep_items": [agent_item],
                "agent_reach_demote_items": [],
                "enable_evidence_notes": True,
                "evidence_notes_dry_run": True,
                "external_evidence_keep_items": [external_item],
                "external_evidence_demote_items": [],
            }
        )
        evidence_note_writer_skill(ctx)
    finally:
        ens.write_evidence_notes = original_writer

    assert len(captured["items"]) == 1
    assert captured["items"][0].title == "external"


def test_falls_back_to_agent_reach_when_external_evidence_missing():
    agent_item = _make_item(title="agent", source_credit=70, source_type="web")

    captured = {}

    def fake_writer(stock_name, stock_code, items, base_dir, collected_at=None, dry_run=False):
        captured["items"] = items
        from evidence_note_writer import EvidenceWritePlan
        return EvidenceWritePlan(written=[{"title": i.title} for i in items], skipped_existing=[], filtered=[])

    import report_skills.evidence_note_skill as ens
    original_writer = ens.write_evidence_notes
    ens.write_evidence_notes = fake_writer
    try:
        ctx = _ctx_with_items([agent_item], dry_run=True)
        evidence_note_writer_skill(ctx)
    finally:
        ens.write_evidence_notes = original_writer

    assert len(captured["items"]) == 1
    assert captured["items"][0].title == "agent"


def test_source_intake_only_with_evidence_notes_disabled_is_disabled(tmp_path):
    item = _make_item(title="cninfo公告", source_credit=95, source_type="exchange_announcement")
    ctx = _ctx_with_external_items([item], enable_evidence_notes=False)
    ctx.input["knowledge_base_dir"] = str(tmp_path)

    result = evidence_note_writer_skill(ctx)

    assert result.get("evidence_note_status") == "disabled"
