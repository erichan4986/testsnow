import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from data_collector import TechnicalCollector

def test_fetch_kline_300661():
    """Test that we can fetch daily K-line for 圣邦股份."""
    collector = TechnicalCollector()
    df = collector.fetch_kline(code="300661", market=0, days=120)
    assert df is not None
    assert len(df) > 50
    assert "close" in df.columns

def test_compute_indicators():
    """Test indicator computation."""
    collector = TechnicalCollector()
    df = collector.fetch_kline(code="300661", market=0, days=120)
    result = collector.compute_indicators(df)
    assert "macd" in result
    assert "rsi_14" in result
    assert "ma_60" in result
    assert "boll_upper" in result
