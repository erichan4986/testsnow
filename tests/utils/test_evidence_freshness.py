from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "utils"))

from evidence_freshness import assess_layer, build_freshness_overlay, canonical_dynamic_topic, has_unnegated_strong_confirmation, parse_explicit_date


def _item(publish_time="2026-07-01", **extra): return {"publish_time": publish_time, "extra": extra}
def _citation(url, credit=60, date_value="2026-07-01"):
    return {"url": url, "date": date_value, "source_credit": credit, "synthesis_display_only": True,
            "scoring_eligible": False, "risk_score_eligible": False, "quality_action": "preview_only",
            "verification_status": "professional_observation"}
def _display(*, date_value="2026-07-01", families=("demand_customer",)):
    return {"_curated_external_argument_cards": [{"coverage_families": list(families),
             "evidence_units": [{"text": "外部材料称客户订单节奏出现变化，需等待正式材料验证。"}], "citation_refs": [1]}],
            "citations": {1: _citation("https://example.com/a", date_value=date_value)}}


def test_parse_and_layer_date_boundaries_fail_closed():
    assert parse_explicit_date("2026-07-14 10:30") == date(2026, 7, 14)
    assert parse_explicit_date("发布时间约四个月前") is None
    assert assess_layer([_item("2026-03-16")], as_of_date=date(2026, 7, 14))["status"] == "fresh"
    assert assess_layer([_item("2026-03-15")], as_of_date=date(2026, 7, 14))["status"] == "stale"


def test_dynamic_topics_and_confirmation_are_metadata_and_negation_aware():
    assert canonical_dynamic_topic("客户订单与交付") == "order_customer"
    assert canonical_dynamic_topic("其他") == "other"
    assert not has_unnegated_strong_confirmation("不替代官方确认，外部材料称订单变化")
    assert has_unnegated_strong_confirmation("外部材料称订单已落地")


def test_overlay_promotes_one_fresh_v3_card_only_when_formal_layers_are_stale():
    overlay = build_freshness_overlay(profile="formal_medium", as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")], broker_items=[], external_display=_display())
    assert overlay["summary_candidate"]["citation_refs"] == [1]
    assert overlay["summary_candidate"]["reason_code"] == "official_stale_broker_missing_external_fresh"
    assert overlay["dynamic_topics"] == {"order_customer": "needs_recent_support"}


def test_overlay_v3_missing_date_or_confirmation_does_not_promote():
    missing = build_freshness_overlay(profile="formal_medium", as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")], broker_items=[], external_display=_display(date_value=""))
    assert missing["external"]["status"] == "unknown" and missing["summary_candidate"] is None
    display = _display(); display["_curated_external_argument_cards"][0]["evidence_units"][0]["text"] = "外部材料称订单已落地。"
    assert build_freshness_overlay(profile="formal_medium", as_of_date=date(2026, 7, 14),
        official_items=[_item("2026-01-01")], broker_items=[], external_display=display)["summary_candidate"] is None


def test_overlay_is_noop_for_formal_rich():
    assert build_freshness_overlay(profile="formal_rich", as_of_date=date(2026, 7, 14),
        official_items=[], broker_items=[], external_display=_display())["preface"] is False
