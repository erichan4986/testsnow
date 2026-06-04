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
