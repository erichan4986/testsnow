from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "utils"))

from evidence_freshness import (
    assess_layer,
    build_freshness_overlay,
    canonical_dynamic_topic,
    has_unnegated_strong_confirmation,
    parse_explicit_date,
)


def _item(publish_time="2026-07-01", **extra):
    return {"publish_time": publish_time, "extra": extra}


def _citation(url, topic="订单", credit=60, date_value="2026-07-01"):
    return {
        "url": url,
        "topic": topic,
        "date": date_value,
        "source_credit": credit,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "quality_action": "preview_only",
        "verification_status": "professional_observation",
    }


def test_parse_explicit_date_accepts_prefix_and_rejects_inferred_text():
    assert parse_explicit_date("2026-07-14 10:30") == date(2026, 7, 14)
    assert parse_explicit_date("2026年7月14日") == date(2026, 7, 14)
    assert parse_explicit_date("发布时间约四个月前") is None


def test_assess_layer_uses_boundary_and_future_dates_fail_closed_for_official():
    status = assess_layer(
        [_item("2026-03-01"), _item(""), _item("2026-08-01")],
        as_of_date=date(2026, 7, 14),
        layer="official",
    )
    assert status["status"] == "unknown"
    assert status["latest_date"] == "2026-03-01"


def test_assess_layer_marks_exact_120_days_fresh_and_oldest_latest_is_excluded():
    status = assess_layer(
        [_item("2026-03-16")],
        as_of_date=date(2026, 7, 14),
        layer="broker",
    )
    assert status["status"] == "fresh"
    assert status["latest_date"] == "2026-03-16"
    assert assess_layer(
        [_item("2026-03-15")], as_of_date=date(2026, 7, 14), layer="broker"
    )["status"] == "stale"


def test_canonical_dynamic_topic_reads_only_topic_metadata():
    assert canonical_dynamic_topic("客户订单与交付") == "order_customer"
    assert canonical_dynamic_topic("公司毛利率改善") == "margin_cost"
    assert canonical_dynamic_topic("行业需求") == "demand_cycle"
    assert canonical_dynamic_topic("其他") == "other"


def test_confirmation_helper_ignores_negated_boundary_wording():
    assert not has_unnegated_strong_confirmation("不替代官方确认，外部材料称订单变化")
    assert has_unnegated_strong_confirmation("外部材料称订单已落地")


def test_overlay_promotes_one_fully_dated_fresh_dynamic_paragraph_only():
    display = {
        "_curated_external_narrative_paragraphs": [
            {
                "paragraph_index": 0,
                "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
                "topic_keys": ["order_customer"],
                "citation_refs": [1, 2],
            }
        ],
        "citations": {
            1: _citation("https://example.com/a", date_value="2026-07-01"),
            2: _citation("https://example.com/b", date_value="2026-07-02"),
        },
    }
    overlay = build_freshness_overlay(
        profile="formal_medium",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[],
        external_display=display,
    )
    assert overlay["summary_candidate"]["paragraph_index"] == 0
    assert overlay["summary_candidate"]["citation_refs"] == [1, 2]
    assert overlay["summary_candidate"]["reason_code"] == "official_stale_broker_missing_external_fresh"
    assert "order_customer" in overlay["dynamic_topics"]


def test_overlay_does_not_promote_legacy_or_mixed_external_citations():
    display = {
        "_curated_external_narrative_paragraphs": [
            {
                "paragraph_index": 0,
                "text": "外部材料称需求变化，需等待正式材料验证。",
                "topic_keys": ["demand_cycle"],
                "citation_refs": [1, 2],
            }
        ],
        "citations": {
            1: _citation("https://example.com/a", topic="需求", date_value="2026-07-01"),
            2: {"url": "https://example.com/b", "topic": "需求", "source_credit": 60},
        },
    }
    overlay = build_freshness_overlay(
        profile="formal_thin_external_rich",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[],
        external_display=display,
    )
    assert overlay["summary_candidate"] is None
    assert overlay["external"]["status"] == "unknown"


def test_overlay_does_not_infer_topic_from_paragraph_body():
    display = {
        "_curated_external_narrative_paragraphs": [{
            "paragraph_index": 0,
            "text": "外部材料称订单变化，需等待正式材料验证。",
            "topic_keys": ["other"],
            "citation_refs": [1],
        }],
        "citations": {1: _citation("https://example.com/a")},
    }
    overlay = build_freshness_overlay(
        profile="formal_medium",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[],
        external_display=display,
    )
    assert overlay["summary_candidate"] is None


def test_fresh_official_or_broker_suppresses_external_promotion():
    display = {
        "_curated_external_narrative_paragraphs": [{
            "paragraph_index": 0,
            "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
            "topic_keys": ["order_customer"],
            "citation_refs": [1],
        }],
        "citations": {1: _citation("https://example.com/a")},
    }
    for official, broker in (
        ([_item("2026-07-01")], []),
        ([_item("2026-01-01")], [_item("2026-07-01", card_type="broker_core_view")]),
    ):
        overlay = build_freshness_overlay(
            profile="formal_medium",
            as_of_date=date(2026, 7, 14),
            official_items=official,
            broker_items=broker,
            external_display=display,
        )
        assert overlay["summary_candidate"] is None
        assert overlay["preface"] is False


def test_overlay_is_noop_for_formal_rich():
    overlay = build_freshness_overlay(
        profile="formal_rich",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[],
        external_display={},
    )
    assert overlay["summary_candidate"] is None
    assert overlay["preface"] is False


def test_candidate_dedup_uses_source_identity_without_reference_number():
    display = {
        "_curated_external_narrative_paragraphs": [{
            "paragraph_index": 0,
            "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
            "topic_keys": ["order_customer"],
            "citation_refs": [1, 2],
        }],
        "citations": {
            1: _citation("", date_value="2026-07-01") | {"source": "观察", "author": "甲", "title": "订单"},
            2: _citation("", date_value="2026-07-01") | {"source": "观察", "author": "甲", "title": "订单"},
        },
    }
    overlay = build_freshness_overlay(
        profile="formal_medium",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[],
        external_display=display,
    )
    assert overlay["summary_candidate"]["citation_refs"] == [1]


def test_broker_risk_cards_are_excluded_for_mapping_items():
    overlay = build_freshness_overlay(
        profile="formal_medium",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[{"publish_time": "2026-07-01", "extra": {"card_type": "broker_risk_note"}}],
        external_display={},
    )
    assert overlay["broker"]["status"] == "unknown"


def test_duplicate_identity_is_still_rejected_when_any_copy_breaks_boundary():
    display = {
        "_curated_external_narrative_paragraphs": [{
            "paragraph_index": 0,
            "text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。",
            "topic_keys": ["order_customer"],
            "citation_refs": [1, 2],
        }],
        "citations": {
            1: _citation("https://example.com/order"),
            2: _citation("https://example.com/order") | {"quality_action": "knowledge_only"},
        },
    }
    overlay = build_freshness_overlay(
        profile="formal_medium",
        as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")],
        broker_items=[],
        external_display=display,
    )
    assert overlay["summary_candidate"] is None
