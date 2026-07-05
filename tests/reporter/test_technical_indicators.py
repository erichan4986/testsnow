import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
import pytest

from technical_indicators import sma, ema, atr, adx, cci, williams_r, stoch_rsi, obv, macd, bollinger, rsi


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    result = sma(s, 3)
    assert result.iloc[-1] == 4.0


def test_rsi_range():
    close = pd.Series([100.0 + i for i in range(20)] + [80.0])
    result = rsi(close, 14)
    assert 0 <= result.iloc[-1] <= 100


def test_bollinger_structure_non_constant():
    """BOLL on non-constant prices must have upper > mid > lower."""
    close = pd.Series([100.0 + i for i in range(30)])
    upper, mid, lower = bollinger(close, 20, 2)
    assert upper.iloc[-1] > mid.iloc[-1] > lower.iloc[-1]


def test_old_private_alias_still_available():
    """technical_analyzer still re-exports _sma, _macd, etc."""
    from technical_analyzer import _sma, _macd, _bollinger, _rsi
    s = pd.Series([1, 2, 3])
    assert _sma(s, 2).iloc[-1] == 2.5
    assert callable(_macd)
    assert callable(_bollinger)
    assert callable(_rsi)
