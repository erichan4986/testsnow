"""Tests for curated external display overclaim lint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_display_lint import lint_curated_external_display_text


def _make_synthesis(text, citations):
    return {
        "industry_logic": text,
        "fundamentals": "",
        "valuation_debate": "",
        "funding_sentiment": "",
        "events_catalysts": "",
        "citations": citations,
    }


def test_curated_only_strong_confirmation_fails():
    synthesis = _make_synthesis(
        "微信公众号文章确认公司订单已经落地[^1]。",
        {
            1: {
                "source": "微信公众号精选观察",
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 55,
            }
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is False
    assert result["violations"]


def test_official_announcement_strong_confirmation_passes():
    synthesis = _make_synthesis(
        "公告显示公司营收同比增长20%[^1]。",
        {
            1: {
                "source": "公告",
                "source_type": "announcement",
                "source_credit": 95,
            }
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True
    assert not result["violations"]


def test_mixed_official_and_curated_passes():
    synthesis = _make_synthesis(
        "公告显示营收增长[^1]，同时微信公众号文章也确认了这一趋势[^2]。",
        {
            1: {"source": "公告", "source_type": "announcement", "source_credit": 95},
            2: {
                "source": "微信公众号精选观察",
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 55,
            },
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True
    assert not result["violations"]


def test_cautious_wording_passes():
    synthesis = _make_synthesis(
        "微信公众号文章观察到订单可能增加[^1]，但仍需公告验证。",
        {
            1: {
                "source": "微信公众号精选观察",
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 55,
            }
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True
    assert not result["violations"]


def test_neutral_confirmation_substrings_pass():
    synthesis = _make_synthesis(
        "外部文章讨论交付确定性、未确认客户占比和不锁定单一芯片厂商的采购策略[^1]。",
        {
            1: {
                "source": "微信公众号精选观察",
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 55,
            }
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True
    assert not result["violations"]


def test_negated_official_confirmation_context_passes():
    synthesis = _make_synthesis(
        "外部材料提示该合作尚未得到官方确认，具体落地时间仍需跟踪[^1]。",
        {
            1: {
                "source": "雪球专栏观察",
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 55,
            }
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True
    assert not result["violations"]


def test_assertive_confirmation_terms_still_fail():
    synthesis = _make_synthesis(
        "微信公众号文章认为公司确定获得订单，并已锁定核心客户[^1]。",
        {
            1: {
                "source": "微信公众号精选观察",
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 55,
            }
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is False
    assert result["violations"]


def test_strong_term_without_citation_does_not_fail():
    synthesis = _make_synthesis(
        "公司订单已经落地。",
        {},
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True


def test_non_numeric_citations_do_not_crash():
    synthesis = _make_synthesis(
        "微信公众号文章确认增长[^verified]。",
        {"verified": {"source_type": "curated_external_analysis_evidence", "source_credit": 55}},
    )
    result = lint_curated_external_display_text(synthesis)
    # No numeric citation means the sentence has no citations; should not fail.
    assert result["ok"] is True


def test_credit_above_threshold_not_treated_as_curated():
    synthesis = _make_synthesis(
        "某来源确认公司订单[^1]。",
        {
            1: {
                "source_type": "curated_external_analysis_evidence",
                "source_credit": 70,
            }
        },
    )
    # source_credit > 65, so citation is not considered curated external.
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is True


def test_unresolved_numeric_citation_fails():
    synthesis = _make_synthesis(
        "微信公众号文章观察到商业化进展[^3]。",
        {},
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is False
    assert result["violations"][0]["term"] == "unresolved_citation"
    assert result["violations"][0]["refs"] == [3]


def test_multiple_sentences_only_flags_violating_one():
    synthesis = _make_synthesis(
        "微信公众号文章观察到行业景气[^1]。某消息确认公司订单落地[^2]。",
        {
            1: {"source_type": "curated_external_analysis_evidence", "source_credit": 55},
            2: {"source_type": "curated_external_analysis_evidence", "source_credit": 55},
        },
    )
    result = lint_curated_external_display_text(synthesis)
    assert result["ok"] is False
    assert len(result["violations"]) == 1
    assert "确认" in result["violations"][0]["sentence"]
