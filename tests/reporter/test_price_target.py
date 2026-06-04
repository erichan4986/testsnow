import pandas as pd
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
from price_target import zigzag


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
