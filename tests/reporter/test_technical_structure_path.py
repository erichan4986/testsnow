import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_indicators import atr
from technical_analyzer import advanced_medium_term_resonance
from technical_structure import (
    analyze_terminal_shock,
    build_structure_path,
    build_volume_context,
)


def _config():
    return {
        "technical": {
            "divergence": {
                "lookback": 20,
                "swing_left": 1,
                "swing_right": 1,
                "price_tolerance_pct": 0.01,
                "price_atr_multiplier": 0.5,
            },
            "structure_path": {
                "shock": {
                    "min_range_atr": 1.5,
                    "min_body_range": 0.65,
                    "close_extreme_pct": 0.2,
                },
            },
        },
    }


def _daily_frame(closes):
    close = pd.Series(closes, dtype=float)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=len(close), freq="B"),
        "open": close,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": [100.0] * len(close),
    })


def _shock_frame():
    frame = _daily_frame([100.0] * 21)
    frame.loc[20, ["open", "high", "low", "close", "volume"]] = [100.0, 101.0, 90.0, 91.0, 200.0]
    return frame


def _long_daily_frame():
    closes = [100.0 + index * 0.08 + (index % 7 - 3) * 0.35 for index in range(150)]
    frame = _daily_frame(closes)
    frame["volume"] = [100.0 + index % 11 for index in range(len(frame))]
    return frame


def test_path_uses_confirmed_pivots_and_latest_close_only():
    result = build_structure_path(_daily_frame([100, 104, 98, 106, 101, 108, 103, 107]), _config())

    assert result["status"] == "ready"
    assert result["segments"][-1]["end_kind"] == "latest_close"
    assert result["pivot_sequence"][-1]["date"] != result["as_of"]


def test_path_relations_preserve_exact_lower_highs_and_lows():
    result = build_structure_path(_daily_frame([100, 120, 112, 115, 105, 110, 100, 105]), _config())

    high = result["pivot_relations"]["high"]
    low = result["pivot_relations"]["low"]
    assert high["status"] == "lower"
    assert high["previous"] == {"date": "2026-01-06", "price": 116.0}
    assert high["latest"] == {"date": "2026-01-08", "price": 111.0}
    assert low["status"] == "lower"
    assert low["previous"] == {"date": "2026-01-07", "price": 104.0}
    assert low["latest"] == {"date": "2026-01-09", "price": 99.0}
    assert result["segments"][-1]["start_kind"] == "low"


def test_path_relations_detect_higher_and_sub_material_flat_pairs():
    higher = build_structure_path(_daily_frame([100, 110, 102, 115, 107, 120, 112, 118]), _config())
    flat = build_structure_path(_daily_frame([100, 120, 112, 120.1, 112.1, 118]), _config())

    assert higher["pivot_relations"]["high"]["status"] == "higher"
    assert higher["pivot_relations"]["low"]["status"] == "higher"
    assert flat["pivot_relations"]["high"]["status"] == "flat"
    assert flat["pivot_relations"]["low"]["status"] == "flat"


def test_path_relation_is_unavailable_without_two_same_kind_pivots():
    result = build_structure_path(_daily_frame([10, 20, 12, 18]), _config())

    assert result["pivot_relations"]["high"]["status"] == "unavailable"
    assert result["pivot_relations"]["low"]["status"] == "unavailable"


def test_unconfirmed_right_edge_extreme_does_not_enter_path_relations():
    base = _daily_frame([100, 120, 112, 115, 105, 110, 100, 105])
    candidate = pd.concat([base, _daily_frame([130]).assign(date=pd.Timestamp("2026-01-13"))], ignore_index=True)

    result = build_structure_path(candidate, _config())

    assert result["pivot_relations"]["high"]["latest"] == {"date": "2026-01-08", "price": 111.0}
    assert result["segments"][-1]["end_kind"] == "latest_close"


def test_dual_extreme_bar_is_omitted_not_ordered_twice():
    frame = _daily_frame([100, 101, 100, 100, 100, 101, 100])
    frame.loc[3, ["high", "low"]] = [120.0, 80.0]

    result = build_structure_path(frame, _config())

    assert "dual_extreme_bar_omitted" in result["limitations"]
    assert len({item["date"] for item in result["pivot_sequence"]}) == len(result["pivot_sequence"])


def test_terminal_downside_shock_uses_prior_atr_and_shared_volume_context():
    frame = _shock_frame()
    volume = build_volume_context(frame, {"price_vs_ma20": "跌破"})

    shock = analyze_terminal_shock(frame, atr(frame), volume, _config())

    assert shock["status"] == "ready"
    assert shock["direction"] == "down"
    assert shock["volume_ratio"] == volume["ratio"]
    assert shock["range_atr_ratio"] >= 1.5


def test_unreliable_volume_does_not_hide_price_shock():
    shock = analyze_terminal_shock(
        _shock_frame(),
        atr(_shock_frame()),
        {"status": "unreliable", "ratio": None, "context": "unknown"},
        _config(),
    )

    assert shock["status"] == "ready"
    assert shock["volume_status"] == "unreliable"
    assert all("量能比" not in fact for fact in shock["facts"])


def test_analyzer_attaches_one_volume_context_path_and_shock():
    result = advanced_medium_term_resonance(
        _long_daily_frame(),
        quote={"adjustment": "qfq", "data_source": "fixture"},
    )

    resonance = result["resonance"]
    assert resonance["volume_context"]["status"] in {"ready", "unreliable", "insufficient"}
    assert resonance["structure_path"]["status"] in {"ready", "sparse", "unavailable"}
    assert resonance["terminal_shock"]["status"] in {"ready", "ordinary", "unavailable"}
    assert resonance["trend_health"]["components"]["volume_confirmation"]["score"] in range(0, 11)
