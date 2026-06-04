import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
from price_target import zigzag, fib_extension, fib_targets_with_convergence, pattern_target, extract_pattern_info


def test_zigzag_basic():
    """Zigzag should find peaks and valleys with 5% minimum reversal."""
    close = pd.Series([100, 105, 110, 100, 95, 100, 110, 115, 105, 100, 95, 100])
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) >= 2
    types = [p["type"] for p in pivots]
    assert "peak" in types
    assert "valley" in types
    # Check that consecutive pivots alternate
    for i in range(1, len(pivots)):
        assert pivots[i]["type"] != pivots[i - 1]["type"]


def test_zigzag_no_small_noise():
    """Moves smaller than min_pct should not create pivots."""
    close = pd.Series([100, 101, 102, 101, 100, 101, 102])  # all < 3%
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) <= 1  # only start point


def test_zigzag_monotonic_up_final_pivot_is_peak():
    """Monotonically increasing series: final pivot must be typed 'peak'."""
    close = pd.Series([100, 106, 112, 120])  # monotonic up, >5% each step
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) >= 2
    assert pivots[-1]["type"] == "peak"


def test_zigzag_monotonic_down_final_pivot_is_valley():
    """Monotonically decreasing series: final pivot must be typed 'valley'."""
    close = pd.Series([120, 114, 108, 100])  # monotonic down, >5% each step
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) >= 2
    assert pivots[-1]["type"] == "valley"


def test_zigzag_first_move_down_alternates():
    """First move down: initial pivot typed 'peak', no consecutive same types."""
    close = pd.Series([100, 94, 88, 90, 95, 100])  # first move down >=5%, then up
    pivots = zigzag(close, min_pct=0.05)
    types = [p["type"] for p in pivots]
    for i in range(1, len(pivots)):
        assert pivots[i]["type"] != pivots[i - 1]["type"], f"consecutive same types at index {i}: {types}"


def test_zigzag_v_shape_pivots():
    """Simple V-shape should produce 3 alternating pivots with correct types."""
    close = pd.Series([100, 90, 100])  # down 10%, up 11.1%
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) == 3
    assert pivots[0]["type"] == "peak"
    assert pivots[0]["price"] == 100
    assert pivots[0]["idx"] == 0
    assert pivots[1]["type"] == "valley"
    assert pivots[1]["price"] == 90
    assert pivots[1]["idx"] == 1
    assert pivots[2]["type"] == "peak"
    assert pivots[2]["price"] == 100
    assert pivots[2]["idx"] == 2


def test_zigzag_inverted_v_shape_pivots():
    """Simple inverted V-shape (^) should produce 3 alternating pivots with correct types."""
    close = pd.Series([100, 110, 100])  # up 10%, down 9.1%
    pivots = zigzag(close, min_pct=0.05)
    assert len(pivots) == 3
    assert pivots[0]["type"] == "valley"
    assert pivots[0]["price"] == 100
    assert pivots[0]["idx"] == 0
    assert pivots[1]["type"] == "peak"
    assert pivots[1]["price"] == 110
    assert pivots[1]["idx"] == 1
    assert pivots[2]["type"] == "valley"
    assert pivots[2]["price"] == 100
    assert pivots[2]["idx"] == 2


def test_zigzag_exact_indices_and_prices():
    """Known input should yield exact pivot indices, prices, and types."""
    # Series: start 100, up to 110 (10%), down to 95 (~13.6%), up to 105 (~10.5%)
    close = pd.Series([100, 105, 110, 105, 100, 95, 100, 105])
    pivots = zigzag(close, min_pct=0.05)
    # First confirmed move is up at idx 2 (110), so initial valley at 0, peak at 2
    # Then down move confirmed at idx 5 (95), valley at 5
    # Then up move confirmed at idx 7 (105), peak at 7
    assert pivots[0] == {"idx": 0, "price": 100, "type": "valley"}
    assert pivots[1] == {"idx": 2, "price": 110, "type": "peak"}
    assert pivots[2] == {"idx": 5, "price": 95, "type": "valley"}
    assert pivots[3] == {"idx": 7, "price": 105, "type": "peak"}


def test_zigzag_short_series_empty():
    """Series with fewer than 3 points should return empty list."""
    assert zigzag(pd.Series([100, 105]), min_pct=0.05) == []
    assert zigzag(pd.Series([100]), min_pct=0.05) == []
    assert zigzag(pd.Series([]), min_pct=0.05) == []


def test_fib_extension():
    """Fibonacci extension from low=100 to high=120."""
    assert fib_extension(100, 120, 1.0) == 120.0
    assert fib_extension(100, 120, 1.272) == 125.44
    assert abs(fib_extension(100, 120, 1.618) - 132.36) < 0.01


def test_fib_convergence():
    """Multiple bands pointing to similar prices within 3% should converge."""
    bands = [
        {"low": 100, "high": 120},   # 1.272 = 125.44
        {"low": 105, "high": 122},   # 1.272 = 123.62
    ]
    targets = fib_targets_with_convergence(bands, level=1.272, convergence_pct=0.03)
    # 125.44 vs 123.62: diff = 1.46%, within 3% -> should have convergence info
    assert any(t["in_convergence"] for t in targets)


def test_fib_no_convergence():
    """Bands with prices far apart should NOT converge."""
    bands = [
        {"low": 100, "high": 120},   # 1.272 = 125.44
        {"low": 50, "high": 80},     # 1.272 = 118.16
    ]
    targets = fib_targets_with_convergence(bands, level=1.272, convergence_pct=0.03)
    assert not any(t["in_convergence"] for t in targets)


def test_double_bottom_target():
    """Double bottom: neckline=100, bottom=90 -> target=110."""
    assert pattern_target(100, 90, is_bullish=True) == 110.0


def test_double_top_target():
    """Double top: neckline=90, top=100 -> target=80."""
    assert pattern_target(90, 100, is_bullish=False) == 80.0


def test_extract_double_bottom():
    """Extract pattern info from a double bottom dict."""
    pattern = {"pattern": "双底", "bottom1": 90, "bottom2": 88, "peak": 100}
    info = extract_pattern_info(pattern)
    assert info["type"] == "double_bottom"
    assert info["is_bullish"] is True
    assert info["neckline"] == 100
    assert info["extreme"] == 88  # should pick the lower bottom


def test_extract_double_top():
    """Extract pattern info from a double top dict."""
    pattern = {"pattern": "双顶", "top1": 100, "top2": 102, "valley": 90}
    info = extract_pattern_info(pattern)
    assert info["type"] == "double_top"
    assert info["is_bullish"] is False
    assert info["neckline"] == 90
    assert info["extreme"] == 102  # should pick the higher top


def test_extract_unknown_pattern():
    """Unknown pattern should return None."""
    pattern = {"pattern": "三角形"}
    assert extract_pattern_info(pattern) is None


from price_target import weekly_trend_analysis


def test_weekly_trend_strong_bullish():
    """ADX>30, +DI>-DI -> strong bullish trend."""
    # Build a strong upward weekly series (need >=14 points for ADX)
    base = list(range(100, 128))
    df = pd.DataFrame({
        "high": [b + 2 for b in base],
        "low": [b - 2 for b in base],
        "close": base,
    })
    trend = weekly_trend_analysis(df)
    assert trend["direction"] == "多头"
    assert trend["adx_score"] == 10
    assert trend["is_ranging"] is False


def test_weekly_trend_short_data():
    """Less than 14 data points should return insufficient data."""
    df = pd.DataFrame({
        "high": [110, 112],
        "low": [105, 107],
        "close": [108, 110],
    })
    trend = weekly_trend_analysis(df)
    assert trend["direction"] == "数据不足"
    assert trend["is_ranging"] is True


def test_weekly_trend_ranging():
    """ADX<20 for 4 weeks with tight BOLL -> ranging."""
    # Flat-ish series with low ADX
    df = pd.DataFrame({
        "high": [102, 103, 102, 103, 102, 103, 102, 103, 102, 103, 102, 103, 102, 103, 102],
        "low": [98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98, 99, 98],
        "close": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
    })
    trend = weekly_trend_analysis(df)
    assert trend["direction"] == "震荡"
    assert bool(trend["is_ranging"]) is True


def test_weekly_trend_strong_bearish():
    """ADX>30, +DI<-DI -> strong bearish trend."""
    base = list(range(128, 100, -1))
    df = pd.DataFrame({
        "high": [b + 2 for b in base],
        "low": [b - 2 for b in base],
        "close": base,
    })
    trend = weekly_trend_analysis(df)
    assert trend["direction"] == "空头"
    assert trend["adx_score"] == 10
    assert trend["is_ranging"] is False


def test_weekly_trend_adx_boundary_score():
    """ADX between 25 and 30 with +DI>-DI -> score 7."""
    # Construct a moderate uptrend: 3 steps +0.3, then 1 step -0.5
    # This yields ADX ~27.5, score 7 (between the >25 and >30 thresholds)
    close = [100]
    for i in range(1, 30):
        close.append(close[-1] + (0.3 if i % 4 != 0 else -0.5))
    df = pd.DataFrame({
        "high": [c + 1.5 for c in close],
        "low": [c - 1.5 for c in close],
        "close": close,
    })
    trend = weekly_trend_analysis(df)
    assert trend["direction"] == "多头"
    assert trend["adx_score"] == 7


def test_weekly_trend_boll_bandwidth_gate():
    """ADX<20 for 4 weeks but BOLL bandwidth >=8% -> is_ranging=False."""
    # Oscillating close with amplitude 3 yields BOLL bandwidth ~11%
    # while ADX stays low (~7) due to lack of directional trend
    close = [100]
    for i in range(1, 30):
        close.append(100 + (3 if i % 3 == 0 else -3))
    df = pd.DataFrame({
        "high": [c + 1.0 for c in close],
        "low": [c - 1.0 for c in close],
        "close": close,
    })
    trend = weekly_trend_analysis(df)
    # ADX low but BOLL wide -> should NOT be ranging
    assert bool(trend["is_ranging"]) is False
