"""Tests for ExecutiveSummaryRenderer."""

from types import SimpleNamespace

import pytest
from scripts.utils.reporter.sections import ExecutiveSummaryRenderer
from scripts.utils.reporter.executive_summary_view import build_executive_summary_view


def _decision_fixture():
    return SimpleNamespace(
        render_header=lambda: "### 综合评分: 6.1/10 | EV: +8.00%（谨慎持有）",
        recommendation_sentence="当前建议谨慎持有，并等待更好的入场条件。",
        entry_constraint=SimpleNamespace(
            display_note="当前入场质量不足。",
            position_cap_note="建议仓位 5-10%。",
        ),
        risk=SimpleNamespace(
            level="中等风险",
            position_advice="控制仓位。",
        ),
    )


def _view_context(image_path=None):
    ctx = {
        "stock_name": "测试股",
        "date_str": "20260719",
        "recommendation_decision": SimpleNamespace(
            total_score=5.3,
            ev=SimpleNamespace(ev_display="+8.00%", targets={"base": 42.0}),
            display_recommendation="谨慎持有",
            recommendation_sentence="谨慎持有，等待趋势确认。",
            entry_constraint=SimpleNamespace(position_cap_note="建议仓位 5-10%。"),
            risk=SimpleNamespace(level="中等风险", position_advice="控制仓位。"),
        ),
        "pillar": {"fundamental": 7.0, "fwd_pe": 28.0, "eps_growth": 20.0},
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "转弱期"},
                        "trend_health": {"grade": "转弱观察", "score": 47},
                    }
                }
            }
        },
        "evidence_freshness": {
            "summary_candidate": {
                "claim": "客户订单节奏仍需验证",
                "citation_refs": [4],
            }
        },
        "chart_paths": {"executive_summary": image_path} if image_path else {},
    }
    ctx["executive_summary_view"] = build_executive_summary_view(ctx)
    return ctx


def test_view_projection_prefers_image_and_omits_legacy_summary_blocks():
    result = ExecutiveSummaryRenderer().render(
        _view_context("/tmp/测试股_20260719_decision.png")
    )

    assert "> **一句话结论**：谨慎持有，等待趋势确认。" in result
    assert "![测试股 投资决策链](/tmp/测试股_20260719_decision.png)" in result
    assert "**近期待验证变量**" in result and "[^4]" in result
    assert "**基本面判断**" not in result
    assert "**估值与业绩预期**" not in result
    assert "### 多空论点对比" not in result


def test_view_projection_falls_back_to_compact_text_chain():
    result = ExecutiveSummaryRenderer().render(_view_context())

    assert "**基本面**：结构化基本面信号中性偏强" in result
    assert "**估值**：盈利增长正在消化估值" in result
    assert "**技术与风险**：转弱观察 / 转弱期" in result
    assert "**当前行动**：谨慎持有。" in result
    assert "**基本面判断**" not in result


def test_required_keys():
    renderer = ExecutiveSummaryRenderer()
    assert renderer.required_keys() == ["stock_name"]


def test_render_without_synthesis_still_has_deterministic_summary(monkeypatch):
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda *args, **kwargs: [],
    )
    renderer = ExecutiveSummaryRenderer()

    result = renderer.render({"stock_name": "测试股"})

    assert "**基本面判断**：" in result
    assert "**估值与业绩预期**：" in result
    assert "**交易状态与风险**：" in result
    assert "> **一句话结论**：" in result
    assert "尚未形成可由高信用来源支撑的核心事实基座" in result


def test_deterministic_summary_uses_supported_core_fact_and_structured_valuation(monkeypatch):
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda *args, **kwargs: [],
    )
    ctx = {
        "stock_name": "测试股",
        "synthesis": {},
        "core_facts": [{
            "fact": "2025年营业收入",
            "data": "同比增长16.2%",
            "provenance_status": "verified",
        }],
        "pillar": {
            "valuation": 6.0,
            "technical": 4.0,
            "sentiment": 5.0,
            "fundamental": 8.0,
            "fundflow": 5.0,
            "fwd_pe": 42.8,
            "eps_growth": 65.5,
        },
        "recommendation_decision": _decision_fixture(),
    }

    result = ExecutiveSummaryRenderer().render(ctx)

    assert "2025年营业收入：同比增长16.2%" in result
    assert "Forward PE 42.8 倍" in result
    assert "预期 EPS 增速 65.5%" in result
    assert "当前入场质量不足" in result
    assert "风险等级为中等风险。" in result
    assert "当前建议谨慎持有，并等待更好的入场条件。" in result


def test_summary_rounds_consensus_values_and_frames_unsupported_score():
    result = ExecutiveSummaryRenderer().render({
        "stock_name": "中际旭创",
        "pillar": {
            "valuation": 7.0,
            "technical": 4.7,
            "sentiment": 3.0,
            "fundamental": 10.0,
            "fundflow": 5.0,
            "fwd_pe": 45.7466,
            "eps_growth": 65.4705,
        },
    })

    assert "Forward PE 45.7 倍" in result
    assert "预期 EPS 增速 65.5%" in result
    assert "45.7466" not in result
    assert "65.4705" not in result
    assert (
        "当前基本面评分为 10/10，反映结构化基本面输入；"
        "高信用核心事实基座尚未完整形成，因此该评分不构成正式材料确认。"
    ) in result


def test_summary_renders_one_framed_freshness_candidate_after_fundamental_judgment():
    result = ExecutiveSummaryRenderer().render({
        "stock_name": "测试股",
        "synthesis": {},
        "evidence_freshness": {
            "summary_candidate": {
                "claim": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
                "citation_refs": [4, 5],
            }
        },
    })

    assert "**近期待验证变量**：外部材料称，客户订单节奏出现变化，需等待正式材料验证。[^4][^5]（外部待验证，不替代官方确认，不参与评分、风险评分或目标价）。" in result
    assert result.count("**近期待验证变量**") == 1


def test_summary_omits_freshness_candidate_when_overlay_is_empty():
    result = ExecutiveSummaryRenderer().render({
        "stock_name": "测试股",
        "synthesis": {},
        "evidence_freshness": {"summary_candidate": None},
    })
    assert "**近期待验证变量**" not in result


def test_summary_deduplicates_entry_text_and_punctuates_risk_sentence():
    decision = SimpleNamespace(
        render_header=lambda: "### 综合评分: 5.9/10 | EV: +45.69%（风险控制优先）",
        recommendation_sentence="风险控制优先。",
        entry_constraint=SimpleNamespace(
            state="risk_control",
            display_note="技术方向偏空，以防守或观望为主。",
            position_cap_note="技术方向偏空，以防守或观望为主，建议 0-5%",
        ),
        risk=SimpleNamespace(level="低风险"),
    )

    result = ExecutiveSummaryRenderer().render({
        "stock_name": "中际旭创",
        "recommendation_decision": decision,
    })

    assert result.count("技术方向偏空，以防守或观望为主") == 1
    assert "建议 0-5%。风险等级为低风险。" in result
    assert "0-5%风险等级" not in result


def test_summary_bridges_positive_consensus_and_constrained_entry():
    decision = _decision_fixture()
    decision.entry_constraint.state = "wait_for_entry"

    result = ExecutiveSummaryRenderer().render({
        "stock_name": "测试股",
        "pillar": {"fwd_pe": 42.8, "eps_growth": 20.0},
        "recommendation_decision": decision,
    })

    assert "一致预期仍显示盈利增长空间" in result
    assert "当前技术入场条件未满足，仓位继续受上述约束" in result


def test_deterministic_summary_states_when_consensus_is_missing(monkeypatch):
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda *args, **kwargs: [],
    )
    result = ExecutiveSummaryRenderer().render({
        "stock_name": "测试股",
        "synthesis": {},
        "pillar": {
            "valuation": 4.0,
            "technical": 5.0,
            "sentiment": 5.0,
            "fundamental": 5.0,
            "fundflow": 5.0,
        },
    })

    assert "估值判断证据不足" in result
    assert "暂按观望处理" in result


def test_render_missing_keys_returns_empty():
    renderer = ExecutiveSummaryRenderer()
    assert renderer.render({}) == ""
    result = renderer.render({"stock_name": "Test"})
    assert "## 执行摘要" in result
    assert "**基本面判断**：" in result


def test_render_basic():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "估值合理，增长空间大。",
            "fundamentals": "基本面稳健，业绩持续增长。",
        },
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 执行摘要" in result
    assert "核心投资论点" in result


def test_render_with_pillar():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "估值合理。",
            "fundamentals": "基本面稳健。",
        },
        "pillar": {
            "valuation": 7.0,
            "technical": 6.5,
            "sentiment": 5.0,
            "fundamental": 8.0,
            "fundflow": 4.0,
        },
    }
    result = renderer.render(ctx)
    assert "综合评分" in result


def test_formal_thin_without_core_facts_filters_unsupported_numeric_bullish_claims(monkeypatch):
    """Formal-thin summaries must not promote ungrounded percentage claims as bullish facts."""

    def fake_llm_extract_thesis(text):
        return {
            "bullish": [
                {"text": "公告显示公司营收同比增长15%，净利润增长20%，基本面稳健", "stars": 4},
                {"text": "公告披露新订单增长30%，产能利用率达90%", "stars": 4},
                {"text": "年报经营线索仍需更多正式披露验证", "stars": 2},
            ],
            "bearish": [],
            "conclusion": "订单增长30%支撑高成长",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm_extract_thesis,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "core_facts": [],
        "synthesis": {
            "valuation_debate": "估值需等待验证。",
            "fundamentals": "当前未形成可由高信用来源支撑的核心事实基座。",
        },
    }

    result = renderer.render(ctx)

    assert "营收同比增长15%" not in result
    assert "净利润增长20%" not in result
    assert "新订单增长30%" not in result
    assert "产能利用率达90%" not in result
    assert "订单增长30%支撑高成长" not in result
    assert "年报经营线索仍需更多正式披露验证" in result


def test_formal_thin_filters_numeric_bullish_claim_unmatched_by_core_facts(monkeypatch):
    """A supported annual fact must not admit unrelated market-share bullish claims."""

    def fake_llm_extract_thesis(text):
        return {
            "bullish": [
                {"text": "行业研报指出市场需求扩大，公司市占率有望提升至20%", "stars": 3},
                {"text": "年报显示营业收入同比增长16.2%", "stars": 3},
            ],
            "bearish": [],
            "conclusion": "市占率提升至20%支撑看多",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm_extract_thesis,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "core_facts": [
            {
                "fact": "营业收入",
                "data": "同比增长16.2%",
                "provenance_status": "supported",
            }
        ],
        "synthesis": {
            "fundamentals": "年报显示营业收入同比增长16.2%。",
            "valuation_debate": "行业研报指出市场需求扩大，公司市占率有望提升至20%。",
        },
    }

    result = renderer.render(ctx)

    assert "市占率有望提升至20%" not in result
    assert "市占率提升至20%支撑看多" not in result
    assert "营业收入同比增长16.2%" in result


def test_formal_thin_filters_unsupported_qualitative_bullish_fact(monkeypatch):
    """Formal-thin summaries must not promote ungrounded product/revenue forecasts."""

    def fake_llm_extract_thesis(text):
        return {
            "bullish": [
                {"text": "公司新产品获行业认证，预计下半年贡献收入增量", "stars": 3},
                {"text": "年报经营线索仍需更多正式披露验证", "stars": 2},
            ],
            "bearish": [],
            "conclusion": "新产品预计贡献收入增量支撑看多",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm_extract_thesis,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "core_facts": [
            {
                "fact": "营业收入",
                "data": "同比增长16.2%",
                "provenance_status": "supported",
            }
        ],
        "synthesis": {
            "fundamentals": "当前未形成可由高信用来源支撑的核心事实基座。",
            "valuation_debate": "外部材料称新产品可能带来增量，但仍需正式披露验证。",
        },
    }

    result = renderer.render(ctx)

    assert "新产品获行业认证" not in result
    assert "预计下半年贡献收入增量" not in result
    assert "新产品预计贡献收入增量支撑看多" not in result
    assert "年报经营线索仍需更多正式披露验证" in result


def test_formal_rich_keeps_numeric_bullish_claims(monkeypatch):
    """The sanitizer must not remove numeric thesis points when high-credit facts exist."""

    def fake_llm_extract_thesis(text):
        return {
            "bullish": [
                {"text": "公告显示公司营收同比增长15%，净利润增长20%", "stars": 4},
            ],
            "bearish": [],
            "conclusion": "",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm_extract_thesis,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "测试股",
        "deep_analysis_evidence_profile": {"profile": "formal_rich"},
        "core_facts": [
            {
                "fact": "营业收入",
                "data": "同比增长15%",
                "provenance_status": "supported",
            }
        ],
        "synthesis": {
            "valuation_debate": "估值讨论。",
            "fundamentals": "公告显示公司营收同比增长15%。",
        },
    }

    result = renderer.render(ctx)

    assert "营收同比增长15%" in result
    assert "净利润增长20%" in result


def test_extract_thesis_points_sanitizes_status_markers(monkeypatch):
    """Non-numeric citation markers must be stripped before LLM extraction."""
    captured = []

    def spy_llm_extract_thesis(text):
        captured.append(text)
        return {"bullish": [{"text": "增长", "stars": 3}], "bearish": [], "conclusion": ""}

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        spy_llm_extract_thesis,
    )

    from scripts.utils.reporter.sections.executive_summary_renderer import (
        _extract_thesis_points,
    )

    text = "收入增长[^1]，社区讨论[^supported]，风险[^needs_review]。"
    _extract_thesis_points(text, "bullish")

    assert len(captured) == 1
    assert "[^supported]" not in captured[0]
    assert "[^needs_review]" not in captured[0]
    assert "[^1]" in captured[0]


def test_llm_extract_thesis_prompt_excludes_unverified_for_bullish(monkeypatch):
    """The LLM prompt must instruct that only verified high-credit facts are bullish confirmed."""
    import os

    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-for-test")

    captured = []

    class FakeChoice:
        def __init__(self):
            self.message = type("M", (), {"content": '{"bullish": [], "bearish": [], "conclusion": ""}'})()

    class FakeCompletions:
        def create(self, **kwargs):
            captured.append(kwargs)
            return type("R", (), {"choices": [FakeChoice()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeClient)

    from scripts.utils.reporter.sections.executive_summary_renderer import _llm_extract_thesis

    _llm_extract_thesis("some text")

    assert len(captured) == 1
    prompt = captured[0]["messages"][1]["content"]
    assert "verified" in prompt or "已验证" in prompt
    assert "supported" in prompt or "部分支持" in prompt
    assert "unverified" in prompt or "未验证" in prompt
    assert "needs_review" in prompt or "需复核" in prompt
    assert "看多" in prompt


def test_render_marks_supported_claim_bullish_point_as_non_official(monkeypatch):
    """Supported claim content must not render as an unqualified bullish fact."""
    def fake_llm_extract_thesis(text):
        return {
            "bullish": [
                {"text": "2026年一季报净利润同比增长106.96%，业绩弹性释放", "stars": 3},
            ],
            "bearish": [],
            "conclusion": "",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm_extract_thesis,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "圣邦股份",
        "synthesis": {
            "valuation_debate": "估值争议。",
            "fundamentals": "该线索获得部分支持，但仍非官方确认。",
        },
        "claim_verification_summary": {
            "supported_claims": [
                {
                    "claim_text": "圣邦 2026 年一季报净利润 1.24 亿元，同比增长 106.96%",
                    "confidence": 54,
                }
            ]
        },
    }

    result = renderer.render(ctx)

    assert "2026年一季报净利润同比增长106.96%" in result
    assert "部分支持，非官方确认" in result


def test_render_prefers_synthesis_display(monkeypatch):
    captured = []

    def spy_extract(text, direction, claim_verification_summary=None):
        captured.append(text)
        return []

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        spy_extract,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "baseline 估值。",
            "fundamentals": "baseline 基本面。",
        },
        "synthesis_display": {
            "valuation_debate": "enhanced 年报全文 估值。",
            "fundamentals": "enhanced 年报全文 基本面。",
        },
    }
    renderer.render(ctx)

    assert captured
    assert any("enhanced 年报全文" in t for t in captured)
    assert all("baseline" not in t for t in captured)


def test_render_falls_back_to_synthesis_when_no_display(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda text, direction, claim_verification_summary=None: captured.append(text) or [],
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "baseline 估值。",
            "fundamentals": "baseline 基本面。",
        },
    }
    renderer.render(ctx)

    assert any("baseline" in t for t in captured)


def _fake_llm_with_pe_spread(text):
    return {
        "bullish": [{"text": "PE(TTM)83.26倍远高于新易盛15倍", "stars": 3}],
        "bearish": [],
        "conclusion": "",
    }


def test_pe_spread_rewritten_when_structured_peer_metrics_available(monkeypatch):
    """A compressed spread '15倍' must be rewritten as peer PE + spread points."""
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        _fake_llm_with_pe_spread,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "valuation_debate": "估值争议。",
            "fundamentals": "基本面。",
        },
        "peer_comparison_material": {
            "schema": "peer_comparison_material.v1",
            "target": "中际旭创",
            "peers": ["新易盛"],
            "rows": [
                {
                    "dimension": "估值水平",
                    "target": "中际旭创",
                    "peer": "新易盛",
                    "metric": "pe_ttm",
                    "target_value": 83.26,
                    "peer_value": 68.29,
                    "period": "latest",
                    "unit": "倍",
                }
            ],
        },
    }
    result = renderer.render(ctx)

    assert "远高于新易盛15倍" not in result
    assert "新易盛为 68.29 倍" in result
    assert "高出约 15 个 PE 倍数点" in result


def test_pe_spread_removed_when_peer_metrics_unavailable(monkeypatch):
    """Without structured peer metrics the misleading spread clause must not survive."""
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        _fake_llm_with_pe_spread,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "valuation_debate": "估值争议。",
            "fundamentals": "基本面。",
        },
    }
    result = renderer.render(ctx)

    assert "远高于新易盛15倍" not in result
    assert "PE(TTM)83.26倍" not in result


def test_valid_peer_pe_is_not_rewritten_as_spread(monkeypatch):
    """A plainly stated peer PE must be left untouched."""

    def fake_llm(text):
        return {
            "bullish": [{"text": "新易盛 PE(TTM) 为 68.29 倍，估值相对合理", "stars": 3}],
            "bearish": [],
            "conclusion": "",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "valuation_debate": "估值争议。",
            "fundamentals": "基本面。",
        },
        "peer_comparison_material": {
            "schema": "peer_comparison_material.v1",
            "rows": [
                {
                    "metric": "pe_ttm",
                    "target": "中际旭创",
                    "peer": "新易盛",
                    "target_value": 83.26,
                    "peer_value": 68.29,
                    "unit": "倍",
                }
            ],
        },
    }
    result = renderer.render(ctx)

    assert "新易盛 PE(TTM) 为 68.29 倍" in result
    assert "高出约" not in result
    assert "个 PE 倍数点" not in result


def test_pe_spread_rewrite_preserves_stock_name_when_clause_has_prefix(monkeypatch):
    """A prefixed stock name must not be swallowed by the replacement."""

    def fake_llm(text):
        return {
            "bullish": [{"text": "中际旭创PE(TTM)83.26倍远高于新易盛15倍", "stars": 3}],
            "bearish": [],
            "conclusion": "",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "valuation_debate": "估值争议。",
            "fundamentals": "基本面。",
        },
        "peer_comparison_material": {
            "schema": "peer_comparison_material.v1",
            "rows": [
                {
                    "metric": "pe_ttm",
                    "target": "中际旭创",
                    "peer": "新易盛",
                    "target_value": 83.26,
                    "peer_value": 68.29,
                    "unit": "倍",
                }
            ],
        },
    }
    result = renderer.render(ctx)

    assert "中际旭创 PE(TTM) 为 83.26 倍" in result
    assert "- PE(TTM) 为 83.26 倍，新易盛" not in result


def test_pe_spread_rewrites_parenthesized_current_pe_clause(monkeypatch):
    """Executive summary prose may say 当前PE（TTM 83.26倍）高于peer约15倍."""

    def fake_llm(text):
        return {
            "bullish": [{"text": "当前PE（TTM 83.26倍）高于新易盛约15倍", "stars": 3}],
            "bearish": [],
            "conclusion": "",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {"valuation_debate": "估值争议。", "fundamentals": "基本面。"},
        "peer_comparison_material": {
            "schema": "peer_comparison_material.v1",
            "rows": [
                {
                    "metric": "pe_ttm",
                    "target": "中际旭创",
                    "peer": "新易盛",
                    "target_value": 83.26,
                    "peer_value": 68.29,
                    "unit": "倍",
                }
            ],
        },
    }
    result = renderer.render(ctx)

    assert "高于新易盛约15倍" not in result
    assert "新易盛为 68.29 倍" in result
    assert "高出约 15 个 PE 倍数点" in result
