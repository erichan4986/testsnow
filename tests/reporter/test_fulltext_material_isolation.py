from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from reporter.scoring_engine import risk_score_section
from reporter.sections import ExecutiveSummaryRenderer
from report_skills.synthesis_skills import SynthesisSkill
from skill_pipeline import SkillContext
from source_adapter import SynthesisItem


class _DualSynthesizer:
    def __init__(self) -> None:
        self.calls = []

    def synthesize(self, stock_name, all_data):
        items = all_data["items"]
        self.calls.append(list(items))
        has_fulltext = any(
            (getattr(item, "extra", {}) or {}).get("source_type")
            == "periodic_report_fulltext_analysis"
            for item in items
        )
        has_narrative = any(
            (getattr(item, "extra", {}) or {}).get("source_type")
            == "periodic_report_narrative_evidence"
            for item in items
        )
        if has_fulltext or has_narrative:
            return {
                "industry_logic": "enhanced 年报全文 降价 毛利率承压 净流出 narrative cards",
                "fundamentals": "enhanced fundamentals",
                "valuation_debate": "",
                "funding_sentiment": "",
                "events_catalysts": "",
                "core_facts": [
                    {"fact_id": 1, "fact": "enhanced fact", "data": "", "confidence": "高"},
                ],
                "citations": {},
            }
        return {
            "industry_logic": "baseline narrative",
            "fundamentals": "baseline fundamentals",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [
                {"fact_id": 1, "fact": "baseline fact", "data": "", "confidence": "高"},
            ],
            "citations": {},
        }


def _fulltext_item() -> SynthesisItem:
    return SynthesisItem(
        title="2025 年报全文摘要",
        content="年报全文材料层：收入、毛利率、现金流。",
        author="公司公告",
        source_platform="定期报告全文",
        url="https://example.com/annual.pdf",
        publish_time="2026-04-01",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "experimental": True,
        },
    )


def _ctx_with_fulltext_enabled() -> SkillContext:
    return SkillContext(input={
        "stock_name": "测试股",
        "include_periodic_report_fulltext_in_synthesis": True,
        "periodic_report_fulltext_items": [_fulltext_item()],
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })


def _write_narrative_card_note(base_dir, stock_name="测试股"):
    notes_dir = Path(base_dir) / "10-Stocks" / stock_name / "periodic_narrative_cards"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / "2025-annual-management-market-view-0.md"
    path.write_text(
        "---\n"
        f"stock: {stock_name}\n"
        "code: 000001\n"
        "source_type: periodic_report_narrative_evidence\n"
        "card_id: periodic:000001:2025:annual:narrative:management_market_view:0\n"
        "schema_version: periodic_report_narrative_evidence_card.v1\n"
        "card_type: management_market_view\n"
        "title: 管理层市场判断\n"
        "report_year: 2025\n"
        "report_type: annual\n"
        "source_credit: 75\n"
        "source_block_id: market_demand_outlook-0\n"
        "evidence_refs:\n"
        "  - market_demand_outlook-0\n"
        "source_excerpt_hash: \"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"\n"
        "knowledge_fact_status: narrative_evidence\n"
        "knowledge_eligible: false\n"
        "knowledge_persisted: true\n"
        "synthesis_eligible: false\n"
        "experimental: true\n"
        "---\n\n"
        f"# {stock_name} 2025 annual management_market_view\n\n"
        "## Narrative Evidence\n\n"
        "> 年报卡片显示客户流失与净流出风险词只应进入 display synthesis。\n\n"
        "## Source\n\n"
        "- source_credit: 75\n",
        encoding="utf-8",
    )
    return path


def _ctx_with_narrative_cards_enabled(tmp_path: Path) -> SkillContext:
    _write_narrative_card_note(tmp_path)
    return SkillContext(input={
        "stock_name": "测试股",
        "knowledge_base_dir": str(tmp_path),
        "include_periodic_narrative_cards_in_synthesis_display": True,
        "stock_raw": {
            "reports": [{"title": "研报", "content": "研发投入增加", "institution": "测试证券"}],
            "announcements": [],
            "fundflow": [],
            "news": [],
            "zhihu": {"report_items": []},
        },
        "keep_posts": [],
    })


def _run_synthesis_with_fulltext_enabled() -> SkillContext:
    ctx = _ctx_with_fulltext_enabled()
    SynthesisSkill(synthesizer=_DualSynthesizer()).run(ctx)
    return ctx


def test_material_layer_fulltext_keeps_canonical_synthesis_baseline() -> None:
    ctx = _run_synthesis_with_fulltext_enabled()

    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"
    assert ctx.get("core_facts")[0]["fact"] == "baseline fact"
    assert ctx.get("synthesis_display")["industry_logic"].startswith("enhanced 年报全文")


def test_material_layer_fulltext_keeps_risk_keyword_scan_on_baseline_text() -> None:
    ctx = _run_synthesis_with_fulltext_enabled()

    baseline_text = ctx.get("synthesis_text")
    assert "baseline narrative" in baseline_text
    assert "降价" not in baseline_text
    assert "毛利率承压" not in baseline_text
    assert "净流出" not in baseline_text
    assert "降价" in ctx.get("synthesis_text_with_periodic_report_fulltext")

    risk = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw={"technical": {"indicators": {}}},
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        synthesis_text=baseline_text,
        score_llm_keyword_risks=True,
    )
    assert "风险等级: 0.0/10" in risk
    assert "竞争格局恶化" not in risk


def test_material_layer_fulltext_does_not_persist_enhanced_synthesis_to_knowledge() -> None:
    ctx = _run_synthesis_with_fulltext_enabled()

    knowledge_input = ctx.get("synthesis")
    flattened = "\n".join(str(value) for value in knowledge_input.values())
    assert "baseline narrative" in flattened
    assert "enhanced 年报全文" not in flattened
    assert "毛利率承压" not in flattened


def test_material_layer_narrative_cards_keeps_canonical_synthesis_baseline(tmp_path: Path) -> None:
    ctx = _ctx_with_narrative_cards_enabled(tmp_path)
    SynthesisSkill(synthesizer=_DualSynthesizer()).run(ctx)

    assert ctx.get("synthesis")["industry_logic"] == "baseline narrative"
    assert ctx.get("core_facts")[0]["fact"] == "baseline fact"
    assert "narrative cards" in ctx.get("synthesis_display")["industry_logic"]


def test_material_layer_narrative_cards_keeps_risk_keyword_scan_on_baseline_text(tmp_path: Path) -> None:
    ctx = _ctx_with_narrative_cards_enabled(tmp_path)
    SynthesisSkill(synthesizer=_DualSynthesizer()).run(ctx)

    baseline_text = ctx.get("synthesis_text")
    assert "baseline narrative" in baseline_text
    assert "净流出" not in baseline_text
    assert "客户流失" not in baseline_text
    assert "narrative cards" in ctx.get("synthesis_text_with_periodic_narrative_cards")

    risk = risk_score_section(
        stock_name="测试股",
        posts=[],
        stock_raw={"technical": {"indicators": {}}},
        quote=None,
        consensus=None,
        industry_fwd_pe=None,
        synthesis_text=baseline_text,
        score_llm_keyword_risks=True,
    )
    assert "风险等级: 0.0/10" in risk


def test_material_layer_narrative_cards_does_not_persist_enhanced_synthesis_to_knowledge(tmp_path: Path) -> None:
    ctx = _ctx_with_narrative_cards_enabled(tmp_path)
    SynthesisSkill(synthesizer=_DualSynthesizer()).run(ctx)

    knowledge_input = ctx.get("synthesis")
    flattened = "\n".join(str(value) for value in knowledge_input.values())
    assert "baseline narrative" in flattened
    assert "客户流失" not in flattened
    assert "narrative cards" not in flattened


def test_material_layer_fulltext_is_allowed_in_display_renderer(monkeypatch) -> None:
    captured = []

    monkeypatch.setattr(
        "reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda text, direction, claim_verification_summary=None: captured.append(text) or [],
    )
    monkeypatch.setattr(
        "reporter.sections.executive_summary_renderer._extract_conclusion",
        lambda stock_name, text: "",
    )

    renderer = ExecutiveSummaryRenderer()
    renderer.render({
        "stock_name": "测试股",
        "synthesis": {"fundamentals": "baseline fundamentals"},
        "synthesis_display": {"fundamentals": "enhanced 年报全文 fundamentals"},
    })

    assert captured
    assert any("enhanced 年报全文" in text for text in captured)
    assert all("baseline fundamentals" not in text for text in captured)
