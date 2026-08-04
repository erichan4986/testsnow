"""Versioned raw OHLCV normalization and multi-asset cache."""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

SCHEMA_VERSION = "technical_market_ohlcv_cache.v2"
SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "technical_ohlcv"
REQUIRED = ("date", "open", "high", "low", "close", "volume")
SOURCE_PAIRS = {
    "stock": {("akshare", "qfq"), ("mootdx", "raw")},
    "index": {("akshare_index", "raw"), ("mootdx_index", "raw")},
}


def _now(value=None):
    return value.astimezone(SHANGHAI) if value else datetime.now(SHANGHAI)


def _valid_identity(asset_type, symbol, market):
    return (
        asset_type in SOURCE_PAIRS
        and bool(re.fullmatch(r"[0-9]{6}", str(symbol)))
        and ((asset_type == "stock" and type(market) is int and market in (0, 1))
             or (asset_type == "index" and market == "cn"))
    )


def _path(cache_dir, asset_type, symbol, market):
    return Path(cache_dir or DEFAULT_CACHE_DIR) / "v2" / f"{asset_type}-{market}-{symbol}.json"


def normalize_ohlcv_frame(frame, *, source, adjustment, limit):
    if frame is None or frame.empty:
        return None
    result = frame.copy().rename(columns={
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount",
    })
    if "volume" not in result.columns and "vol" in result.columns:
        result = result.rename(columns={"vol": "volume"})
    if "date" not in result.columns:
        if "datetime" in result.columns:
            result["date"] = result["datetime"]
        elif isinstance(result.index, pd.DatetimeIndex):
            result["date"] = result.index
    result = result.reset_index(drop=True)
    if any(field not in result.columns for field in REQUIRED):
        return None
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    fields = [*REQUIRED, *(["amount"] if "amount" in result.columns else [])]
    for field in fields[1:]:
        result[field] = pd.to_numeric(result[field], errors="coerce")
    result = (
        result[fields].dropna(subset=REQUIRED).sort_values("date")
        .drop_duplicates("date", keep="last").tail(limit).reset_index(drop=True)
    )
    if result.empty:
        return None
    result.attrs.update(data_source=source, adjustment=adjustment)
    return result


def _from_raw(data, source, adjustment):
    if not isinstance(data, dict) or not data:
        return None
    if any(not isinstance(data.get(field), list) for field in REQUIRED):
        return None
    lengths = {len(data[field]) for field in REQUIRED}
    if len(lengths) != 1 or not next(iter(lengths)):
        return None
    if "amount" in data and (not isinstance(data["amount"], list) or len(data["amount"]) not in lengths):
        return None
    fields = [*REQUIRED, *(["amount"] if "amount" in data else [])]
    return normalize_ohlcv_frame(
        pd.DataFrame({field: data[field] for field in fields}),
        source=source, adjustment=adjustment, limit=next(iter(lengths)),
    )


def _raw(frame):
    if frame is None or frame.empty:
        return {}
    fields = [field for field in (*REQUIRED, "amount") if field in frame.columns]
    return {
        field: ([value.date().isoformat() for value in frame[field]] if field == "date"
                else [float(value) for value in frame[field]])
        for field in fields
    }


def load_ohlcv_cache(asset_type, symbol, market, *, cache_dir=None, now=None):
    result = {"status": "missing", "daily": None, "weekly": None}
    if not _valid_identity(asset_type, symbol, market):
        return {**result, "status": "invalid"}
    path = _path(cache_dir, asset_type, symbol, market)
    if not path.exists():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("schema_version") != SCHEMA_VERSION
            or payload.get("asset_type") != asset_type
            or str(payload.get("symbol")) != str(symbol)
            or payload.get("market") != market
        ):
            raise ValueError("cache identity mismatch")
        source, adjustment = str(payload.get("source", "")), str(payload.get("adjustment", ""))
        if (source, adjustment) not in SOURCE_PAIRS[asset_type]:
            raise ValueError("cache provenance mismatch")
        weekly_data = payload.get("weekly_data")
        if asset_type == "index" and weekly_data:
            raise ValueError("index cache cannot contain weekly rows")
        daily = _from_raw(payload.get("daily_data"), source, adjustment)
        weekly = _from_raw(weekly_data, source, adjustment) if weekly_data else None
        if daily is None or (weekly_data and weekly is None):
            raise ValueError("invalid OHLCV arrays")
        fetched = datetime.fromisoformat(payload["fetched_at"])
        if fetched.tzinfo is None:
            raise ValueError("cache timestamp must be zoned")
        current, latest = _now(now), daily["date"].iloc[-1].date()
        if str(payload.get("latest_date")) != latest.isoformat():
            raise ValueError("latest date mismatch")
        fetched = fetched.astimezone(SHANGHAI)
        latest_age, fetched_age = (current.date() - latest).days, (current.date() - fetched.date()).days
        if fetched > current or latest_age < 0 or fetched_age < 0:
            raise ValueError("future cache")
        same_day = fetched.date() == current.date() and latest_age <= 7
        status = "same_day" if same_day else (
            "fallback_eligible" if latest_age <= 3 and fetched_age <= 3 else "stale"
        )
        result.update(
            status=status, daily=daily if status != "stale" else None,
            weekly=weekly if status != "stale" else None, source=source,
            adjustment=adjustment, fetched_at=payload["fetched_at"],
            latest_date=latest.isoformat(), path=path,
        )
        return result
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return {**result, "status": "invalid"}


def write_ohlcv_cache(
    daily_data, *, asset_type, symbol, market, source, adjustment,
    weekly_data=None, fetched_at=None, cache_dir=None, now=None,
):
    if (
        not _valid_identity(asset_type, symbol, market)
        or (source, adjustment) not in SOURCE_PAIRS.get(asset_type, set())
        or (asset_type == "index" and bool(weekly_data))
    ):
        return None
    daily = _from_raw(daily_data, source, adjustment)
    weekly = _from_raw(weekly_data, source, adjustment) if weekly_data else None
    if daily is None or (weekly_data and weekly is None):
        return None
    current, latest = _now(now), daily["date"].iloc[-1].date()
    if not 0 <= (current.date() - latest).days <= 7:
        return None
    fetched_at = str(fetched_at or current.isoformat())
    try:
        fetched = datetime.fromisoformat(fetched_at)
        if fetched.tzinfo is None or fetched.astimezone(SHANGHAI) > current:
            return None
    except ValueError:
        return None
    payload = {
        "schema_version": SCHEMA_VERSION, "asset_type": asset_type,
        "symbol": str(symbol), "market": market, "source": source,
        "adjustment": adjustment, "fetched_at": fetched_at,
        "latest_date": latest.isoformat(), "daily_data": _raw(daily),
        "weekly_data": _raw(weekly),
    }
    path = _path(cache_dir, asset_type, symbol, market)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
        return path
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()
