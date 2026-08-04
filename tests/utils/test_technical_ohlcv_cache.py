import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from technical_ohlcv_cache import (  # noqa: E402
    load_ohlcv_cache,
    normalize_ohlcv_frame,
    write_ohlcv_cache,
)


SHANGHAI = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 3, 16, 0, tzinfo=SHANGHAI)


def _raw(dates):
    size = len(dates)
    return {
        "date": list(dates),
        "open": [10.0 + i for i in range(size)],
        "high": [10.5 + i for i in range(size)],
        "low": [9.5 + i for i in range(size)],
        "close": [10.2 + i for i in range(size)],
        "volume": [1000 + i for i in range(size)],
        "amount": [10200 + i for i in range(size)],
    }


def _write_stock(tmp_path, fetched_at="2026-08-03T15:00:00+08:00"):
    return write_ohlcv_cache(
        _raw(["2026-08-01", "2026-08-03"]),
        weekly_data=_raw(["2026-07-25", "2026-08-01"]),
        asset_type="stock", symbol="300308", market=0,
        source="akshare", adjustment="qfq", fetched_at=fetched_at,
        cache_dir=tmp_path, now=NOW,
    )


def test_normalizer_uses_canonical_volume_when_mootdx_has_vol_and_volume():
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-08-01", "2026-08-03"]),
        "open": [10, 11], "high": [11, 12], "low": [9, 10],
        "close": [10.5, 11.5], "vol": [1, 2], "volume": [100, 200],
    })
    result = normalize_ohlcv_frame(
        frame, source="mootdx", adjustment="raw", limit=120,
    )
    assert result["volume"].tolist() == [100, 200]
    assert result.attrs == {"data_source": "mootdx", "adjustment": "raw"}


def test_normalizer_detaches_mootdx_date_column_from_named_datetime_index():
    dates = pd.to_datetime(["2026-08-01", "2026-08-03"])
    frame = pd.DataFrame({
        "date": dates,
        "open": [10, 11], "high": [11, 12], "low": [9, 10],
        "close": [10.5, 11.5], "vol": [1, 2], "volume": [100, 200],
    }, index=pd.DatetimeIndex(dates, name="date"))

    result = normalize_ohlcv_frame(
        frame, source="mootdx_index", adjustment="raw", limit=120,
    )

    assert result["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-08-01", "2026-08-03",
    ]
    assert result["volume"].tolist() == [100, 200]


def test_stock_round_trip_projects_raw_fields_and_attrs(tmp_path):
    path = _write_stock(tmp_path)
    loaded = load_ohlcv_cache(
        "stock", "300308", 0, cache_dir=tmp_path, now=NOW,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "stock-0-300308.json"
    assert path.parent.name == "v2"
    assert loaded["status"] == "same_day"
    assert loaded["daily"]["amount"].tolist() == [10200, 10201]
    assert loaded["weekly"]["close"].tolist() == [10.2, 11.2]
    assert loaded["daily"].attrs == {"data_source": "akshare", "adjustment": "qfq"}
    assert set(payload) == {
        "schema_version", "asset_type", "symbol", "market", "source",
        "adjustment", "fetched_at", "latest_date", "daily_data", "weekly_data",
    }
    assert payload["schema_version"] == "technical_market_ohlcv_cache.v2"
    assert not list(path.parent.glob("*.tmp"))


def test_index_none_weekly_serializes_empty_and_cannot_collide_with_stock(tmp_path):
    index_path = write_ohlcv_cache(
        _raw(["2026-08-01", "2026-08-03"]),
        asset_type="index", symbol="000001", market="cn",
        source="akshare_index", adjustment="raw", cache_dir=tmp_path, now=NOW,
    )
    stock_path = write_ohlcv_cache(
        _raw(["2026-08-01", "2026-08-03"]),
        asset_type="stock", symbol="000001", market=0,
        source="mootdx", adjustment="raw", cache_dir=tmp_path, now=NOW,
    )
    payload = json.loads(index_path.read_text(encoding="utf-8"))

    assert index_path.name == "index-cn-000001.json"
    assert stock_path.name == "stock-0-000001.json"
    assert index_path != stock_path
    assert payload["weekly_data"] == {}
    assert load_ohlcv_cache(
        "index", "000001", "cn", cache_dir=tmp_path, now=NOW,
    )["weekly"] is None


def test_index_rejects_nonempty_weekly_on_write_and_read(tmp_path):
    assert write_ohlcv_cache(
        _raw(["2026-08-03"]), weekly_data=_raw(["2026-08-01"]),
        asset_type="index", symbol="000001", market="cn",
        source="mootdx_index", adjustment="raw", cache_dir=tmp_path, now=NOW,
    ) is None

    path = tmp_path / "v2" / "index-cn-000001.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "schema_version": "technical_market_ohlcv_cache.v2",
        "asset_type": "index", "symbol": "000001", "market": "cn",
        "source": "mootdx_index", "adjustment": "raw",
        "fetched_at": NOW.isoformat(), "latest_date": "2026-08-03",
        "daily_data": _raw(["2026-08-03"]),
        "weekly_data": _raw(["2026-08-01"]),
    }), encoding="utf-8")
    assert load_ohlcv_cache(
        "index", "000001", "cn", cache_dir=tmp_path, now=NOW,
    )["status"] == "invalid"


def test_exact_three_day_cache_is_fallback_eligible(tmp_path):
    friday = datetime(2026, 7, 31, 16, 0, tzinfo=SHANGHAI)
    write_ohlcv_cache(
        _raw(["2026-07-31"]), asset_type="index", symbol="000001", market="cn",
        source="akshare_index", adjustment="raw", fetched_at=friday.isoformat(),
        cache_dir=tmp_path, now=friday,
    )
    loaded = load_ohlcv_cache(
        "index", "000001", "cn", cache_dir=tmp_path, now=NOW,
    )
    assert loaded["status"] == "fallback_eligible"
    assert loaded["fetched_at"] == friday.isoformat()


def test_cache_older_than_three_days_is_stale(tmp_path):
    _write_stock(tmp_path)
    loaded = load_ohlcv_cache(
        "stock", "300308", 0, cache_dir=tmp_path,
        now=datetime(2026, 8, 7, 9, 0, tzinfo=SHANGHAI),
    )
    assert loaded["status"] == "stale"
    assert loaded["daily"] is None


def test_v1_is_ignored_and_invalid_v2_identity_is_rejected(tmp_path):
    (tmp_path / "0-300308.json").write_text(json.dumps({
        "schema_version": "technical_ohlcv_cache.v1", "code": "300308", "market": 0,
    }), encoding="utf-8")
    assert load_ohlcv_cache(
        "stock", "300308", 0, cache_dir=tmp_path, now=NOW,
    )["status"] == "missing"

    path = _write_stock(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["symbol"] = "688385"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_ohlcv_cache(
        "stock", "300308", 0, cache_dir=tmp_path, now=NOW,
    )["status"] == "invalid"


def test_cache_rejects_bad_identity_source_and_future_data(tmp_path):
    assert write_ohlcv_cache(
        _raw(["2026-08-03"]), asset_type="stock", symbol="300308", market="0",
        source="akshare", adjustment="qfq", cache_dir=tmp_path, now=NOW,
    ) is None
    assert write_ohlcv_cache(
        _raw(["2026-08-03"]), asset_type="index", symbol="000001", market="cn",
        source="akshare", adjustment="qfq", cache_dir=tmp_path, now=NOW,
    ) is None
    assert write_ohlcv_cache(
        _raw(["2026-08-04"]), asset_type="stock", symbol="300308", market=0,
        source="akshare", adjustment="qfq", cache_dir=tmp_path, now=NOW,
    ) is None
