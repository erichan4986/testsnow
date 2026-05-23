import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from data_collector import TechnicalCollector, ReportCollector, AnnouncementCollector

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

def test_fetch_reports_300661():
    """Test research report fetching for 圣邦股份."""
    collector = ReportCollector()
    reports = collector.collect(code="300661", months=4)
    assert isinstance(reports, list)
    if len(reports) > 0:
        assert "title" in reports[0]
        assert "institution" in reports[0]

def test_fetch_announcements_300661():
    """Test announcement fetching for 圣邦股份."""
    collector = AnnouncementCollector()
    announcements = collector.collect(code="300661", months=3)
    assert isinstance(announcements, list)
    if len(announcements) > 0:
        assert "title" in announcements[0]
        assert "date" in announcements[0]
