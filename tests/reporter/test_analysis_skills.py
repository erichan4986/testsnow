import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from report_skills.analysis_skills import cross_source_consolidation_skill, scoring_skill
from source_adapter import SynthesisItem


def test_cross_source_consolidation_empty():
    ctx = SkillContext(input={
        "keep_posts": [],
        "stock_raw": {},
    })
    result = cross_source_consolidation_skill(ctx)
    assert result.get("consolidated") is not None
    assert result.get("cross_source_summary") == ""


def test_cross_source_consolidation_disables_topic_llm(monkeypatch):
    calls = {}

    class _Consolidator:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def consolidate(self, items):
            return items

        def generate_cross_source_summary(self, items):
            return ""

    monkeypatch.setattr("content_consolidator.ContentConsolidator", _Consolidator)
    cross_source_consolidation_skill(
        SkillContext(input={"keep_posts": [], "stock_raw": {}, "report_llm_enabled": False})
    )

    assert calls["use_llm_topics"] is False


def test_scoring_skill_basic():
    ctx = SkillContext(input={
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {"composite_score": 7, "trend": "多头"},
                },
            },
        },
        "keep_posts": [
            {"title": "t1", "like": 100, "comment": 50, "content": "c1"},
        ],
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "ps": None,
    })
    result = scoring_skill(ctx)
    pillar = result.get("pillar_scores")
    assert pillar is not None
    assert "valuation" in pillar
    assert "technical" in pillar
    assert result.get("total_score") is not None


def test_scoring_skill_does_not_consume_periodic_report_fulltext_items(monkeypatch):
    captured = {}

    def fake_compute_pillar_scores(stock_raw, keep_posts, quote, consensus, ind_fwd_pe, ps):
        captured["stock_raw"] = stock_raw
        captured["keep_posts"] = keep_posts
        captured["quote"] = quote
        captured["consensus"] = consensus
        captured["ind_fwd_pe"] = ind_fwd_pe
        captured["ps"] = ps
        return {
            "valuation": 5,
            "technical": 5,
            "sentiment": 5,
            "fundamental": 5,
            "fundflow": 5,
        }

    import reporter.scoring_engine as scoring_engine

    monkeypatch.setattr(scoring_engine, "compute_pillar_scores", fake_compute_pillar_scores)

    fulltext_item = SynthesisItem(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="不应进入评分。",
        author="",
        source_platform="定期报告全文",
        url="",
        publish_time="",
        interaction_score=0,
        extra={"source_type": "periodic_report_fulltext_analysis"},
    )
    ctx = SkillContext(input={
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {"composite_score": 7, "trend": "多头"},
                },
            },
        },
        "keep_posts": [{"title": "t1", "like": 100, "comment": 50, "content": "c1"}],
        "periodic_report_fulltext_items": [fulltext_item],
        "quote": {"pe_ttm": 20.0},
        "consensus": {},
        "ind_fwd_pe": 25.0,
        "ps": None,
    })

    scoring_skill(ctx)

    assert captured["keep_posts"] == [{"title": "t1", "like": 100, "comment": 50, "content": "c1"}]
    assert "periodic_report_fulltext_items" not in captured["stock_raw"]
    assert ctx.get("periodic_report_fulltext_items") == [fulltext_item]
