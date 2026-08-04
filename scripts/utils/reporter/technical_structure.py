"""结构分析模块 — BIAS、BOLL状态、K线特征、MA方向、周线趋势、支撑阻力。"""

import logging
from collections import Counter
from typing import Dict

import numpy as np
import pandas as pd

try:
    from .technical_indicators import atr as _atr
except ImportError:
    from technical_indicators import atr as _atr

__all__ = [
    "compute_bias", "compute_boll_state", "compute_candle_features",
    "compute_ma_direction", "resample_daily_to_weekly",
    "compute_weekly_trend", "find_support_resistance",
    "evaluate_sr_transformation", "confirmed_swing_indices", "detect_trend_structure_health",
    "detect_channel_or_box_structure", "evaluate_bottoming_region",
    "build_volume_context", "build_structure_path", "analyze_terminal_shock",
]

logger = logging.getLogger(__name__)


def confirmed_swing_indices(
    values: pd.Series,
    left: int,
    right: int,
    kind: str,
) -> list[int]:
    """Return strictly confirmed swing positions without using right-edge bars."""
    series = pd.to_numeric(values, errors="coerce").reset_index(drop=True)
    indices = []
    for i in range(left, len(series) - right):
        center = series.iloc[i]
        neighbors = pd.concat((series.iloc[i - left:i], series.iloc[i + 1:i + right + 1]))
        if pd.isna(center) or neighbors.isna().any():
            continue
        if (kind == "low" and center < neighbors.min()) or (kind == "high" and center > neighbors.max()):
            indices.append(i)
    return indices


def _finite(value: object) -> float | None:
    """Return a finite float without treating malformed market data as a value."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _source_dates(df_daily: pd.DataFrame) -> pd.Series | None:
    """Normalize real source dates; positional indices are never reportable dates."""
    dates = df_daily.get("date")
    if dates is None and isinstance(df_daily.index, pd.DatetimeIndex):
        dates = pd.Series(df_daily.index, index=df_daily.index)
    if dates is None:
        return None
    dates = pd.to_datetime(dates, errors="coerce").reset_index(drop=True)
    return None if dates.isna().any() else dates


def build_volume_context(
    df_daily: pd.DataFrame | None,
    daily_structure: Dict | None,
    volume_reliable: bool = True,
) -> dict:
    """Describe the completed-day volume context using the preceding 20 bars only."""
    empty = {"status": "insufficient", "ratio": None, "price_change": None, "context": "unknown"}
    if not volume_reliable:
        return {**empty, "status": "unreliable"}
    if df_daily is None or len(df_daily) < 21 or not {"close", "volume"}.issubset(df_daily.columns):
        return empty
    window = df_daily.tail(21)
    close = pd.to_numeric(window["close"], errors="coerce")
    volume = pd.to_numeric(window["volume"], errors="coerce")
    if close.iloc[-2:].isna().any() or volume.isna().any() or (volume <= 0).any():
        return empty
    baseline = float(volume.iloc[:-1].mean())
    if baseline <= 0:
        return empty
    change = float(close.iloc[-1] - close.iloc[-2])
    position = (daily_structure or {}).get("price_vs_ma20")
    context = "bullish" if change > 0 and position == "站上" else "bearish" if change < 0 and position == "跌破" else "mixed"
    return {
        "status": "ready", "ratio": float(volume.iloc[-1] / baseline),
        "price_change": change, "context": context,
    }


def build_structure_path(df_daily: pd.DataFrame | None, config: Dict | None) -> dict:
    """Build a source-ordered path from confirmed pivots plus the latest close."""
    unavailable_relation = {"status": "unavailable", "previous": None, "latest": None, "materiality_pct": None}
    empty = {
        "status": "unavailable", "as_of": None, "pivot_sequence": [], "segments": [], "limitations": [],
        "pivot_relations": {"high": dict(unavailable_relation), "low": dict(unavailable_relation)},
    }
    if df_daily is None or not {"high", "low", "close"}.issubset(df_daily.columns):
        return {**empty, "limitations": ["OHLC 数据不足"]}
    dates = _source_dates(df_daily)
    if dates is None:
        return {**empty, "limitations": ["缺少可解析交易日期"]}
    cfg = ((config or {}).get("technical") or {}).get("divergence") or {}
    lookback = int(cfg.get("lookback", 80))
    left, right = int(cfg.get("swing_left", 3)), int(cfg.get("swing_right", 3))
    frame = df_daily.tail(max(1, lookback)).reset_index(drop=True)
    dates = dates.tail(len(frame)).reset_index(drop=True)
    date_text = dates.dt.strftime("%Y-%m-%d")
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    if high.isna().any() or low.isna().any() or close.isna().any() or len(frame) < left + right + 2:
        return {**empty, "as_of": date_text.iloc[-1], "limitations": ["结构数据不足"]}

    high_indices = set(confirmed_swing_indices(high, left, right, "high"))
    low_indices = set(confirmed_swing_indices(low, left, right, "low"))
    dual_indices = high_indices & low_indices
    limitations = ["dual_extreme_bar_omitted"] if dual_indices else []
    candidates = [
        {"idx": index, "kind": kind, "price": float(high.iloc[index] if kind == "high" else low.iloc[index]), "date": date_text.iloc[index]}
        for kind, indices in (("high", high_indices), ("low", low_indices))
        for index in indices - dual_indices
        if index < len(frame) - 1
    ]
    candidates.sort(key=lambda item: item["idx"])
    pivots = []
    for candidate in candidates:
        if pivots and pivots[-1]["kind"] == candidate["kind"]:
            more_extreme = candidate["price"] > pivots[-1]["price"] if candidate["kind"] == "high" else candidate["price"] < pivots[-1]["price"]
            if more_extreme:
                pivots[-1] = candidate
            continue
        pivots.append(candidate)

    atr = _atr(frame)
    tolerance = float(cfg.get("price_tolerance_pct", 0.01))
    multiplier = float(cfg.get("price_atr_multiplier", 0.5))

    def segment(start: dict, end_price: float, end_idx: int, end_date: str, end_kind: str) -> dict:
        change_pct = (end_price / start["price"] - 1.0) if start["price"] else 0.0
        atr_value = _finite(atr.iloc[end_idx]) or 0.0
        threshold = max(tolerance, multiplier * atr_value / max(abs(end_price), 1e-9))
        move = "up" if change_pct > threshold else "down" if change_pct < -threshold else "flat"
        return {
            "start_date": start["date"], "end_date": end_date,
            "start_price": start["price"], "end_price": end_price,
            "start_kind": start["kind"], "end_kind": end_kind,
            "change_pct": float(change_pct), "move": move,
        }

    def relation(kind: str) -> dict:
        points = [pivot for pivot in pivots if pivot["kind"] == kind]
        if len(points) < 2:
            return dict(unavailable_relation)
        previous, latest = points[-2:]
        previous_price, latest_price = _finite(previous["price"]), _finite(latest["price"])
        atr_value = _finite(atr.iloc[latest["idx"]])
        if previous_price in {None, 0.0} or latest_price in {None, 0.0} or atr_value is None:
            return dict(unavailable_relation)
        threshold = max(tolerance, multiplier * atr_value / abs(latest_price))
        change = latest_price / previous_price - 1.0
        status = "higher" if change > threshold else "lower" if change < -threshold else "flat"
        point = lambda item: {"date": item["date"], "price": float(item["price"])}
        return {
            "status": status, "previous": point(previous), "latest": point(latest),
            "materiality_pct": float(threshold),
        }

    segments = [
        segment(start, end["price"], end["idx"], end["date"], end["kind"])
        for start, end in zip(pivots, pivots[1:])
    ]
    if pivots:
        segments.append(segment(pivots[-1], float(close.iloc[-1]), len(frame) - 1, date_text.iloc[-1], "latest_close"))
    return {
        "status": "ready" if len(pivots) >= 2 else "sparse", "as_of": date_text.iloc[-1],
        "pivot_sequence": [{key: value for key, value in pivot.items() if key != "idx"} for pivot in pivots],
        "segments": segments, "pivot_relations": {"high": relation("high"), "low": relation("low")},
        "limitations": limitations,
    }


def analyze_terminal_shock(
    df_daily: pd.DataFrame | None,
    atr_series: pd.Series | None,
    volume_context: dict | None,
    config: Dict | None,
) -> dict:
    """Identify a directional terminal shock using prior-row ATR only."""
    empty = {"status": "unavailable", "direction": "unknown", "facts": [], "volume_status": "insufficient"}
    required = {"open", "high", "low", "close"}
    if df_daily is None or len(df_daily) < 2 or not required.issubset(df_daily.columns) or atr_series is None:
        return empty
    row, previous = df_daily.iloc[-1], df_daily.iloc[-2]
    values = [_finite(row.get(key)) for key in ("open", "high", "low", "close")]
    open_, high, low, close, previous_close = (*values, _finite(previous.get("close")))
    prior_atr = _finite(pd.to_numeric(atr_series, errors="coerce").shift(1).iloc[-1])
    if None in (open_, high, low, close, previous_close, prior_atr) or high <= low or prior_atr <= 0:
        return empty
    true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
    range_atr_ratio = true_range / prior_atr
    body_ratio = abs(close - open_) / (high - low)
    close_location = (close - low) / (high - low)
    shock_cfg = (((config or {}).get("technical") or {}).get("structure_path") or {}).get("shock") or {}
    minimum_range = float(shock_cfg.get("min_range_atr", 1.5))
    minimum_body = float(shock_cfg.get("min_body_range", 0.65))
    extreme = float(shock_cfg.get("close_extreme_pct", 0.2))
    down = close < open_ and close < previous_close and close_location <= extreme
    up = close > open_ and close > previous_close and close_location >= 1 - extreme
    direction = "down" if down else "up" if up else "mixed"
    volume = volume_context or {}
    status = "ready" if direction in {"down", "up"} and range_atr_ratio >= minimum_range and body_ratio >= minimum_body else "ordinary"
    facts = []
    if status == "ready":
        facts.append(f"日内振幅为前一日ATR的{range_atr_ratio:.1f}倍，实体占比{body_ratio:.0%}")
        facts.append("收盘接近日内低位" if direction == "down" else "收盘接近日内高位")
        if volume.get("status") == "ready" and _finite(volume.get("ratio")) is not None:
            facts.append(f"量能比{float(volume['ratio']):.1f}×此前20日均量")
    return {
        "status": status, "direction": direction, "facts": facts,
        "range_atr_ratio": float(range_atr_ratio), "body_ratio": float(body_ratio),
        "close_location": float(close_location), "volume_ratio": volume.get("ratio"),
        "volume_status": volume.get("status", "insufficient"),
    }


def evaluate_sr_transformation(
    close: float,
    support_zone: dict | None,
    resistance_zone: dict | None,
    recent_closes: list[float],
) -> dict | None:
    """
    评估支撑/阻力转化。
    阻力被强突破 → 转为新支撑；支撑被有效跌破 → 转为新阻力。
    必须使用最近 3 日收盘价确认，不能只靠单日。
    """
    signals = []

    # 阻力转支撑
    if resistance_zone and len(recent_closes) >= 3:
        rz_high = resistance_zone.get("zone_high")
        if rz_high is not None:
            stood_above = all(c > rz_high for c in recent_closes[-3:])
            strong_break = close > rz_high * 1.01
            if stood_above and strong_break:
                signals.append({
                    "signal": "阻力突破，原阻力转为新支撑",
                    "type": "resistance_break",
                    "new_support": round(float(rz_high), 2),
                })

    # 支撑转阻力
    if support_zone and len(recent_closes) >= 3:
        sz_low = support_zone.get("zone_low")
        if sz_low is not None:
            stayed_below = all(c < sz_low for c in recent_closes[-3:])
            if stayed_below:
                signals.append({
                    "signal": "支撑告破，原支撑转为新阻力",
                    "type": "support_break",
                    "new_resistance": round(float(sz_low), 2),
                })

    if not signals:
        return None

    return {
        "signals": signals,
        "primary": signals[0],
    }


def compute_bias(df: pd.DataFrame, windows=(5, 10, 20), lookback=120) -> Dict:
    """计算 BIAS(5/10/20)，并标记120日极值与极端分位（防 look-ahead）。"""
    close = df["close"].astype(float)
    out = {}
    for n in windows:
        ma = close.rolling(n, min_periods=n).mean()
        bias = (close / ma - 1.0) * 100
        cur = bias.iloc[-1]
        out[f"bias_{n}"] = None if pd.isna(cur) else round(float(cur), 2)
        if n in (5, 10):
            shifted = bias.shift(1)
            hist_window = shifted.iloc[-lookback:].dropna()
            if len(hist_window) >= min(60, lookback) and pd.notna(cur):
                prev_max = hist_window.max()
                prev_min = hist_window.min()
                out[f"bias_{n}_extreme_high"] = bool(cur > prev_max)
                out[f"bias_{n}_extreme_low"] = bool(cur < prev_min)
                # 极端分位（<10% 或 >90%）也视为显著偏离
                pct = float((hist_window < cur).mean() * 100)
                out[f"bias_{n}_pct"] = round(pct, 1)
            else:
                out[f"bias_{n}_extreme_high"] = False
                out[f"bias_{n}_extreme_low"] = False
                out[f"bias_{n}_pct"] = 50.0
    return out


def compute_boll_state(df: pd.DataFrame, config: Dict | None = None) -> Dict:
    """计算布林宽度、开口/缩口/正常状态。前5日均宽不含当天。"""
    if config is None:
        config = {"technical": {"boll": {"open_ratio": 1.2, "squeeze_ratio": 0.8, "width_ma_window": 5}}}
    boll_cfg = config.get("technical", {}).get("boll", {})
    open_ratio = boll_cfg.get("open_ratio", 1.2)
    squeeze_ratio = boll_cfg.get("squeeze_ratio", 0.8)
    width_ma_window = boll_cfg.get("width_ma_window", 5)

    upper = df["boll_upper"]
    mid = df["boll_mid"].replace(0, np.nan)
    lower = df["boll_lower"]
    width = (upper - lower) / mid
    width_ma5_prev = width.shift(1).rolling(window=width_ma_window, min_periods=width_ma_window).mean()

    cur_width = width.iloc[-1]
    ref_width = width_ma5_prev.iloc[-1]

    if pd.isna(cur_width) or pd.isna(ref_width):
        state = "未知"
    elif cur_width > ref_width * open_ratio:
        state = "开口"
    elif cur_width < ref_width * squeeze_ratio:
        state = "缩口"
    else:
        state = "正常"

    return {
        "boll_width": None if pd.isna(cur_width) else round(float(cur_width), 4),
        "boll_width_ma5": None if pd.isna(ref_width) else round(float(ref_width), 4),
        "boll_state": state,
    }


def compute_candle_features(df: pd.DataFrame, atr: pd.Series | None = None) -> Dict:
    """计算K线实体、影线长度（归一化）。"""
    row = df.iloc[-1]
    open_, high, low, close = row["open"], row["high"], row["low"], row["close"]
    body = abs(close - open_)
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low
    full_range = high - low
    close_base = close if close else np.nan
    atr_cur = atr.iloc[-1] if atr is not None and len(atr) else np.nan
    return {
        "body_len": round(float(body), 4),
        "upper_shadow": round(float(upper_shadow), 4),
        "lower_shadow": round(float(lower_shadow), 4),
        "body_pct": None if not close_base else round(float(body / close_base), 4),
        "upper_shadow_pct": None if not close_base else round(float(upper_shadow / close_base), 4),
        "lower_shadow_pct": None if not close_base else round(float(lower_shadow / close_base), 4),
        "body_atr_ratio": None if pd.isna(atr_cur) or atr_cur == 0 else round(float(body / atr_cur), 2),
        "upper_shadow_atr_ratio": None if pd.isna(atr_cur) or atr_cur == 0 else round(float(upper_shadow / atr_cur), 2),
        "lower_shadow_atr_ratio": None if pd.isna(atr_cur) or atr_cur == 0 else round(float(lower_shadow / atr_cur), 2),
        "is_doji": full_range > 0 and body / full_range < 0.1,
        "is_long_upper_shadow": full_range > 0 and upper_shadow / full_range > 0.45,
        "is_long_lower_shadow": full_range > 0 and lower_shadow / full_range > 0.45,
    }


def compute_ma_direction(ma: pd.Series, lookback: int = 5, flat_threshold: float = 0.005) -> str:
    """判断均线方向：向上 / 向下 / 走平。"""
    if len(ma) < lookback + 1:
        return "未知"
    cur = ma.iloc[-1]
    prev = ma.iloc[-lookback - 1]
    if pd.isna(cur) or pd.isna(prev) or prev == 0:
        return "未知"
    change = cur / prev - 1
    if change > flat_threshold:
        return "向上"
    elif change < -flat_threshold:
        return "向下"
    else:
        return "走平"


def resample_daily_to_weekly(df: pd.DataFrame) -> pd.DataFrame | None:
    """从日线 resample 为周线（周五收盘）。"""
    if df is None or df.empty or len(df) < 5:
        return None
    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    elif not isinstance(df.index, pd.DatetimeIndex):
        return None

    weekly = df.resample("W-FRI").agg({
        "open": lambda x: x.iloc[0] if len(x) else None,
        "high": "max",
        "low": "min",
        "close": lambda x: x.iloc[-1] if len(x) else None,
        "volume": "sum",
    }).dropna()
    weekly = weekly.reset_index(drop=True)
    return weekly


def compute_weekly_trend(df_weekly: pd.DataFrame) -> Dict:
    """基于周线判定大背景。返回趋势 + evidence。"""
    close = df_weekly["close"].astype(float)
    ma5 = close.rolling(5, min_periods=5).mean()
    ma10 = close.rolling(10, min_periods=10).mean()
    ma20 = close.rolling(20, min_periods=20).mean()

    if len(df_weekly) < 20:
        return {
            "weekly_trend": "未知",
            "weekly_close": round(float(close.iloc[-1]), 4),
            "weekly_ma5": None, "weekly_ma10": None, "weekly_ma20": None,
            "ma20_direction": "未知",
            "weekly_trend_evidence": {"reason": "周线数据不足"},
        }

    weekly_close = close.iloc[-1]
    above_ma5_ma10_count = ((close > ma5) & (close > ma10)).tail(6).sum()
    below_ma5_ma10_count = ((close < ma5) & (close < ma10)).tail(6).sum()
    ma_order_up = ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]
    ma_order_down = ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1]

    ma5_slope_4w = ma5.iloc[-1] / ma5.iloc[-4] - 1 if ma5.iloc[-4] else np.nan
    ma10_slope_4w = ma10.iloc[-1] / ma10.iloc[-4] - 1 if ma10.iloc[-4] else np.nan

    cross_count = 0
    for i in range(-10, 0):
        crossed = False
        for ma in [ma5, ma10]:
            if pd.isna(ma.iloc[i]) or pd.isna(ma.iloc[i - 1]):
                continue
            prev_side = close.iloc[i - 1] - ma.iloc[i - 1]
            cur_side = close.iloc[i] - ma.iloc[i]
            if prev_side * cur_side < 0:
                crossed = True
        if crossed:
            cross_count += 1

    ma5_ma10_gap = abs(ma5.iloc[-1] - ma10.iloc[-1]) / ma10.iloc[-1] if ma10.iloc[-1] != 0 else 0

    is_uptrend = (
        above_ma5_ma10_count >= 5
        and ma_order_up
        and pd.notna(ma5_slope_4w) and ma5_slope_4w > 0
        and pd.notna(ma10_slope_4w) and ma10_slope_4w > 0
    )
    is_downtrend = (
        below_ma5_ma10_count >= 5
        and ma_order_down
        and pd.notna(ma5_slope_4w) and ma5_slope_4w < 0
        and pd.notna(ma10_slope_4w) and ma10_slope_4w < 0
    )
    is_choppy = cross_count >= 3 or ma5_ma10_gap < 0.02

    if is_uptrend:
        trend = "单边上涨"
    elif is_downtrend:
        trend = "单边下跌"
    elif is_choppy:
        trend = "震荡"
    else:
        trend = "趋势修复中"

    return {
        "weekly_trend": trend,
        "weekly_close": round(float(weekly_close), 4),
        "weekly_ma5": round(float(ma5.iloc[-1]), 4),
        "weekly_ma10": round(float(ma10.iloc[-1]), 4),
        "weekly_ma20": round(float(ma20.iloc[-1]), 4),
        "ma20_direction": compute_ma_direction(ma20, lookback=5, flat_threshold=0.005),
        "weekly_trend_evidence": {
            "weeks_above_ma5_ma10": int(above_ma5_ma10_count),
            "weeks_below_ma5_ma10": int(below_ma5_ma10_count),
            "ma_order": (
                "MA5>MA10>MA20" if ma_order_up
                else "MA5<MA10<MA20" if ma_order_down
                else "均线未形成顺序排列"
            ),
            "ma5_slope_4w": round(float(ma5_slope_4w), 4) if pd.notna(ma5_slope_4w) else None,
            "ma10_slope_4w": round(float(ma10_slope_4w), 4) if pd.notna(ma10_slope_4w) else None,
            "cross_count_10w": int(cross_count),
            "ma5_ma10_gap": round(float(ma5_ma10_gap), 4),
        },
    }


def find_support_resistance(
    df: pd.DataFrame,
    config: Dict | None = None,
) -> Dict:
    """基于ATR分箱识别支撑/阻力区间。要求触及后反向运行。"""
    if config is None:
        config = {
            "technical": {
                "support_resistance": {
                    "lookback": 250,
                    "local_extrema_window": 5,
                    "min_touches": 3,
                    "strong_touches": 5,
                    "reverse_pct": 0.02,
                    "reverse_atr_multiplier": 1.0,
                    "bucket_pct": 0.005,
                    "bucket_atr_multiplier": 0.5,
                    "low_liquidity_downgrade": True,
                }
            }
        }
    sr_cfg = config.get("technical", {}).get("support_resistance", {})
    lookback = sr_cfg.get("lookback", 250)
    min_touches = sr_cfg.get("min_touches", 3)
    reverse_pct = sr_cfg.get("reverse_pct", 0.02)
    reverse_atr_mult = sr_cfg.get("reverse_atr_multiplier", 1.0)
    bucket_pct = sr_cfg.get("bucket_pct", 0.005)
    bucket_atr_mult = sr_cfg.get("bucket_atr_multiplier", 0.5)

    diagnostics = {"lookback": lookback, "min_touches": min_touches}

    if len(df) < 30:
        diagnostics.update({"bars": len(df), "reason": f"数据仅{len(df)}根，不足30根"})
        return {"support_zone": None, "resistance_zone": None, "diagnostics": diagnostics}

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    recent = df.tail(min(lookback, len(df)))
    recent_close = recent["close"].astype(float)
    recent_high = recent["high"].astype(float)
    recent_low = recent["low"].astype(float)

    tr1 = recent_high - recent_low
    tr2 = (recent_high - recent_close.shift(1)).abs()
    tr3 = (recent_low - recent_close.shift(1)).abs()
    atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14, min_periods=1).mean().iloc[-1]
    cur_price = close.iloc[-1]
    bin_size = max(cur_price * bucket_pct, atr * bucket_atr_mult)

    if bin_size == 0:
        diagnostics.update({"bars": len(df), "atr": float(atr) if pd.notna(atr) else None, "reason": "ATR为零，无法计算支撑阻力区"})
        return {"support_zone": None, "resistance_zone": None, "diagnostics": diagnostics}

    window = sr_cfg.get("local_extrema_window", 5)
    local_max_mask = (recent_high == recent_high.rolling(window, center=True).max())
    local_min_mask = (recent_low == recent_low.rolling(window, center=True).min())

    reverse_threshold = max(cur_price * reverse_pct, atr * reverse_atr_mult)

    def _valid_touches(prices: pd.Series, is_support: bool) -> pd.Series:
        valid = []
        for idx, price in prices.items():
            future = recent_close.loc[idx:].iloc[:6]
            if len(future) < 2:
                continue
            future_max = future.max()
            future_min = future.min()
            if is_support:
                rebound = future_max - price
                if rebound >= reverse_threshold:
                    valid.append(price)
            else:
                drop = price - future_min
                if drop >= reverse_threshold:
                    valid.append(price)
        return pd.Series(valid, dtype=float)

    max_prices_raw = recent_high[local_max_mask].dropna()
    min_prices_raw = recent_low[local_min_mask].dropna()

    max_prices = _valid_touches(max_prices_raw, is_support=False)
    min_prices = _valid_touches(min_prices_raw, is_support=True)

    if len(max_prices) < min_touches and len(min_prices) < min_touches:
        diagnostics.update({
            "bars": len(df),
            "recent_bars": len(recent),
            "local_extrema_window": window,
            "raw_peaks": len(max_prices_raw),
            "raw_valleys": len(min_prices_raw),
            "valid_resistance_touches": len(max_prices),
            "valid_support_touches": len(min_prices),
            "required_touches": min_touches,
            "reason": (
                f"有效触及不足（峰 {len(max_prices)} 次 / 谷 {len(min_prices)} 次，需≥{min_touches} 次）"
            ),
        })
        return {"support_zone": None, "resistance_zone": None, "diagnostics": diagnostics}

    max_buckets = (max_prices / bin_size).round()
    min_buckets = (min_prices / bin_size).round()

    max_counts = Counter(max_buckets)
    min_counts = Counter(min_buckets)

    support_zone = None
    resistance_zone = None

    if min_counts:
        best_min_bucket = min_counts.most_common(1)[0]
        if best_min_bucket[1] >= min_touches:
            min_prices_in_bucket = min_prices[min_buckets == best_min_bucket[0]]
            support_zone = {
                "price": round(float(min_prices_in_bucket.mean()), 2),
                "zone_low": round(float(min_prices_in_bucket.min()), 2),
                "zone_high": round(float(min_prices_in_bucket.max()), 2),
                "strength": "强" if best_min_bucket[1] >= sr_cfg.get("strong_touches", 5) else "中",
                "touches": int(best_min_bucket[1]),
            }

    if max_counts:
        best_max_bucket = max_counts.most_common(1)[0]
        if best_max_bucket[1] >= min_touches:
            max_prices_in_bucket = max_prices[max_buckets == best_max_bucket[0]]
            resistance_zone = {
                "price": round(float(max_prices_in_bucket.mean()), 2),
                "zone_low": round(float(max_prices_in_bucket.min()), 2),
                "zone_high": round(float(max_prices_in_bucket.max()), 2),
                "strength": "强" if best_max_bucket[1] >= sr_cfg.get("strong_touches", 5) else "中",
                "touches": int(best_max_bucket[1]),
            }

    # 位置校验：支撑区必须在当前价格下方，压力区必须在上方
    invalid_reasons = []
    if support_zone and support_zone["zone_high"] > cur_price:
        invalid_reasons.append(
            f"识别出的支撑区（{support_zone['zone_low']}-{support_zone['zone_high']}）"
            f"位于当前价格（{cur_price:.2f}）上方，不构成有效支撑"
        )
        support_zone = None

    if resistance_zone and resistance_zone["zone_low"] < cur_price:
        invalid_reasons.append(
            f"识别出的压力区（{resistance_zone['zone_low']}-{resistance_zone['zone_high']}）"
            f"位于当前价格（{cur_price:.2f}）下方，不构成有效压力"
        )
        resistance_zone = None

    # 重叠检测：支撑区和压力区距离太近（<1% 当前价格）时降级
    if support_zone and resistance_zone:
        gap = resistance_zone["zone_low"] - support_zone["zone_high"]
        if gap >= 0 and gap / cur_price < 0.01:
            # 两者几乎重叠，降级为区间参考
            merged = {
                "price": round((support_zone["price"] + resistance_zone["price"]) / 2, 2),
                "zone_low": support_zone["zone_low"],
                "zone_high": resistance_zone["zone_high"],
                "strength": "弱",
                "touches": support_zone["touches"] + resistance_zone["touches"],
                "note": "支撑与压力区过近，视为震荡区间参考",
            }
            support_zone = merged
            resistance_zone = None
            invalid_reasons.append("支撑区与压力区过近（<1%），合并为震荡区间")

    # Build concise reason based on what was actually found after bucketing
    if support_zone and resistance_zone:
        reason = "支撑区与压力区均已识别"
    elif support_zone:
        reason = "支撑区已识别，压力区价位分散未形成聚集区"
    elif resistance_zone:
        reason = "压力区已识别，支撑区价位分散未形成聚集区"
    else:
        reason = "价位分散，未形成聚集区"
    if invalid_reasons:
        reason += "；" + "；".join(invalid_reasons)


    diagnostics.update({
        "bars": len(df),
        "recent_bars": len(recent),
        "local_extrema_window": window,
        "raw_peaks": len(max_prices_raw),
        "raw_valleys": len(min_prices_raw),
        "valid_resistance_touches": len(max_prices),
        "valid_support_touches": len(min_prices),
        "required_touches": min_touches,
        "reason": reason,
    })
    return {
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
        "diagnostics": diagnostics,
    }


def detect_trend_structure_health(
    df_daily: pd.DataFrame,
    lookback: int = 60,
    swing_left: int = 2,
    swing_right: int = 2,
    min_gap_days: int = 3,
    tolerance_pct: float = 0.01,
    atr_multiplier: float = 0.5,
) -> dict:
    """检测趋势结构健康度：回调低点是否抬升/走平/下移。"""
    if df_daily is None or len(df_daily) < lookback:
        return {
            "state": "无法判断",
            "is_healthy": None,
            "confidence": "低",
            "swing_lows": [],
            "last_low_relation": "unknown",
            "evidence": [],
            "missing": [f"数据不足，需要{lookback}根K线，实际{len(df_daily) if df_daily is not None else 0}根"],
            "action_hint": "证据不足，继续观察",
        }

    df = df_daily.iloc[-lookback:].copy().reset_index(drop=True)
    dates = df["date"] if "date" in df.columns else pd.Series(df.index)

    # 计算 ATR（简化版，用 high-low）
    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    threshold = max(tolerance_pct, atr_multiplier * (atr / df["close"].iloc[-1] if df["close"].iloc[-1] != 0 else 0))

    swing_lows = [
        {"idx": i, "price": float(df["low"].iloc[i]), "date": str(dates.iloc[i])}
        for i in confirmed_swing_indices(df["low"], swing_left, swing_right, "low")
    ]

    if len(swing_lows) < 2:
        return {
            "state": "无法判断",
            "is_healthy": None,
            "confidence": "低",
            "swing_lows": [{"date": s["date"], "price": s["price"]} for s in swing_lows],
            "last_low_relation": "unknown",
            "evidence": [],
            "missing": ["confirmed swing lows 不足2个"],
            "action_hint": "证据不足，继续观察",
        }

    # 过滤间隔不足的（只保留间隔 >= min_gap_days 的）
    filtered = [swing_lows[0]]
    short_gaps = []
    for s in swing_lows[1:]:
        gap = s["idx"] - filtered[-1]["idx"]
        if gap >= min_gap_days:
            filtered.append(s)
        else:
            short_gaps.append(gap)
    swing_lows = filtered

    if len(swing_lows) < 2:
        return {
            "state": "无法判断",
            "is_healthy": None,
            "confidence": "低",
            "swing_lows": [{"date": s["date"], "price": s["price"]} for s in swing_lows],
            "last_low_relation": "unknown",
            "evidence": [],
            "missing": ["confirmed swing lows 间隔过短，不足2个有效低点"],
            "action_hint": "证据不足，继续观察",
        }

    # 比较最后两个低点
    prev = swing_lows[-2]["price"]
    last = swing_lows[-1]["price"]
    diff = (last - prev) / prev

    if diff > threshold:
        state = "低点抬升"
        is_healthy = True
        last_rel = "higher"
    elif diff < -threshold:
        state = "低点下移"
        is_healthy = False
        last_rel = "lower"
    else:
        state = "低点走平"
        is_healthy = None
        last_rel = "flat"

    # 计算有效间隔用于置信度
    effective_gaps = [
        swing_lows[i]["idx"] - swing_lows[i - 1]["idx"]
        for i in range(1, len(swing_lows))
    ]
    min_effective_gap = min(effective_gaps) if effective_gaps else None

    if min_effective_gap is not None and min_effective_gap < 5:
        confidence = "中" if len(swing_lows) >= 3 else "低"
    elif len(swing_lows) >= 3:
        confidence = "高"
    else:
        confidence = "中"

    evidence = [f"最近两个回调低点：{prev:.2f} -> {last:.2f}"]
    if state == "低点抬升":
        evidence.append("回调低点逐步抬高，上升趋势结构健康")
    elif state == "低点下移":
        evidence.append("回调低点下移，结构转弱")

    return {
        "state": state,
        "is_healthy": is_healthy,
        "confidence": confidence,
        "swing_lows": [{"date": s["date"], "price": s["price"]} for s in swing_lows],
        "last_low_relation": last_rel,
        "evidence": evidence,
        "missing": [],
        "action_hint": "结构健康，回调低点抬升" if is_healthy else ("结构转弱，低点下移" if is_healthy is False else "证据不足，继续观察"),
    }


def detect_channel_or_box_structure(
    df_daily: pd.DataFrame,
    lookback: int = 40,
    slope_tolerance_pct: float = 0.005,
    confirm_days: int = 2,
) -> dict:
    """检测上升/下降通道或水平箱体。使用分位数拟合上下轨。"""
    if df_daily is None or len(df_daily) < lookback:
        return {
            "state": "无明显通道",
            "confidence": "低",
            "upper": None, "lower": None,
            "position": "未知", "breakout_status": "未突破",
            "evidence": [], "missing": ["数据不足"],
            "action_hint": "区间内观望",
        }

    df = df_daily.iloc[-lookback:].copy().reset_index(drop=True)
    x = np.arange(len(df))
    upper_prices = df["high"].values
    lower_prices = df["low"].values
    avg_price = df["close"].mean()

    def _fit_slope(y):
        if len(y) < 2:
            return 0, 0
        slope, intercept = np.polyfit(x, y, 1)
        return slope, intercept

    upper_slope, upper_intercept = _fit_slope(upper_prices)
    lower_slope, lower_intercept = _fit_slope(lower_prices)

    upper_norm_slope = upper_slope / avg_price if avg_price else 0
    lower_norm_slope = lower_slope / avg_price if avg_price else 0
    norm_diff = abs(upper_norm_slope - lower_norm_slope)

    # 上下轨
    upper = upper_intercept + upper_slope * (len(df) - 1)
    lower = lower_intercept + lower_slope * (len(df) - 1)

    # 用分位数拟合作为 fallback
    use_quantile = False
    if abs(upper_norm_slope) > 0.01 or abs(lower_norm_slope) > 0.01:
        upper = np.percentile(upper_prices, 95)
        lower = np.percentile(lower_prices, 5)
        use_quantile = True

    if use_quantile or (abs(upper_norm_slope) < slope_tolerance_pct and abs(lower_norm_slope) < slope_tolerance_pct):
        state = "水平箱体"
        conf = "高" if not use_quantile else "中"
    elif upper_norm_slope > 0 and lower_norm_slope > 0:
        state = "上升通道"
        conf = "高" if norm_diff <= slope_tolerance_pct else "低"
    elif upper_norm_slope < 0 and lower_norm_slope < 0:
        state = "下降通道"
        conf = "高" if norm_diff <= slope_tolerance_pct else "低"
    else:
        state = "无明显通道"
        conf = "低"

    if state == "无明显通道":
        return {
            "state": state, "confidence": conf,
            "upper": round(upper, 2), "lower": round(lower, 2),
            "position": "未知", "breakout_status": "未突破",
            "evidence": [], "missing": [], "action_hint": "区间内观望",
        }

    # 当前位置（用距离上轨/下轨的相对比例，避免 mid 阈值误判）
    last_close = float(df_daily["close"].iloc[-1])
    if upper is None or lower is None or upper <= lower:
        position = "未知"
    elif last_close > upper:
        position = "区间外（突破上轨）"
    elif last_close < lower:
        position = "区间外（跌破下轨）"
    else:
        range_ = upper - lower
        dist_to_upper = (upper - last_close) / range_
        dist_to_lower = (last_close - lower) / range_
        if dist_to_upper < 0.15:
            position = "接近上轨"
        elif dist_to_lower < 0.15:
            position = "接近下轨"
        else:
            position = "中部"

    # 突破检测（用 confirm_bars）
    confirm_bars = df_daily.iloc[-confirm_days:]
    breakout_status = "未突破"
    if len(confirm_bars) >= confirm_days:
        above_upper = all(c > upper for c in confirm_bars["close"].values)
        below_lower = all(c < lower for c in confirm_bars["close"].values)
        if above_upper:
            breakout_status = "向上突破确认" if confirm_days >= 2 else "向上突破待确认"
        elif below_lower:
            breakout_status = "向下跌破确认" if confirm_days >= 2 else "向下跌破待确认"

    action_hint = "区间内观望"
    if "向上" in breakout_status:
        action_hint = "趋势跟随"
    elif "向下" in breakout_status:
        action_hint = "风险警戒"
    elif position == "接近下轨":
        action_hint = "等待突破确认"

    return {
        "state": state,
        "confidence": conf,
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "position": position,
        "breakout_status": breakout_status,
        "evidence": [f"上轨≈{upper:.2f}，下轨≈{lower:.2f}", f"当前位置：{position}"],
        "missing": ["使用分位数拟合"] if use_quantile else [],
        "action_hint": action_hint,
    }


def evaluate_bottoming_region(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame | None,
    indicators: dict,
    trend_state: dict,
    structure_health: dict | None = None,
    weekly_background: dict | None = None,
) -> dict:
    """评估是否进入底部区域观察。不直接输出买入建议。"""
    score = 0
    evidence = []
    missing = []

    # 条件1: 波动率收敛
    if len(df_daily) >= 40:
        recent_amp = (df_daily["high"].iloc[-20:].max() - df_daily["low"].iloc[-20:].min()) / df_daily["close"].iloc[-20:].mean()
        prev_amp = (df_daily["high"].iloc[-40:-20].max() - df_daily["low"].iloc[-40:-20].min()) / df_daily["close"].iloc[-40:-20].mean()
        if prev_amp > 0 and recent_amp < prev_amp * 0.4:
            score += 1
            evidence.append("过去20日振幅明显收敛")
    else:
        missing.append("历史数据不足，无法判断波动率收敛")

    # 条件2: 长期支撑附近（周线 MA20/MA60 附近）
    close = indicators.get("close")
    if df_weekly is not None and len(df_weekly) >= 5 and close:
        wma20 = df_weekly["close"].rolling(20).mean().iloc[-1] if len(df_weekly) >= 20 else None
        wma60 = df_weekly["close"].rolling(60).mean().iloc[-1] if len(df_weekly) >= 60 else None
        near = False
        for ma_val, name in [(wma20, "MA20"), (wma60, "MA60")]:
            if ma_val is not None and ma_val > 0 and abs(close - ma_val) / ma_val < 0.05:
                near = True
                evidence.append(f"价格位于周线{name}附近")
                break
        if near:
            score += 1
        else:
            missing.append("价格尚未回到周线长期支撑附近")
    else:
        missing.append("周线数据不足")

    # 条件3: BIAS 负偏离但不再创新低
    bias_5 = indicators.get("bias_5")
    if bias_5 is not None and len(df_daily) >= 20:
        if bias_5 < 0:
            recent_biases = []
            for i in range(1, 6):
                if len(df_daily) >= i + 5:
                    c = df_daily["close"].iloc[-i]
                    ma5_i = df_daily["close"].iloc[-i-4:-i+1].mean() if len(df_daily) >= i + 4 else None
                    if ma5_i and ma5_i > 0:
                        recent_biases.append((c - ma5_i) / ma5_i * 100)
            min_20 = min([
                (df_daily["close"].iloc[j] - df_daily["close"].iloc[max(0, j-4):j+1].mean()) / df_daily["close"].iloc[max(0, j-4):j+1].mean() * 100
                for j in range(-20, 0) if len(df_daily) >= abs(j) + 5
            ]) if len(df_daily) >= 25 else None
            if recent_biases and min_20 is not None and min(recent_biases) >= min_20 - 0.5:
                score += 1
                evidence.append("BIAS负偏离但不再创新低")
            elif bias_5 < 0:
                missing.append("BIAS仍在创新低")
        else:
            missing.append("BIAS未出现负偏离")
    else:
        missing.append("BIAS数据不足")

    # 条件4: 价格不再有效跌破最近 swing low（区分盘中跌破和收盘跌破）
    swing_low_status = None
    if structure_health and structure_health.get("swing_lows"):
        swing_lows = structure_health["swing_lows"]
        if swing_lows:
            last_low = min(s["price"] for s in swing_lows)
            latest_low = df_daily["low"].iloc[-1] if len(df_daily) >= 1 else None
            if close is not None and last_low is not None:
                intraday_broke = latest_low is not None and latest_low < last_low * 0.99
                close_broke = close < last_low * 0.99
                swing_low_status = {
                    "last_swing_low": round(last_low, 2),
                    "latest_low": round(float(latest_low), 2) if latest_low is not None else None,
                    "latest_close": round(close, 2),
                    "intraday_broke": bool(intraday_broke),
                    "close_broke": bool(close_broke),
                }
                if not close_broke:
                    score += 1
                    if intraday_broke:
                        evidence.append("收盘未有效跌破最近回调低点，但盘中已下探")
                    else:
                        evidence.append("价格未有效跌破最近回调低点")
                else:
                    missing.append("价格已有效跌破最近回调低点")
            else:
                missing.append("close 或 swing_low 数据缺失")
        else:
            missing.append("swing_lows 为空")
    else:
        missing.append("structure_health 或 swing_lows 缺失，无法判断低点支撑")

    # 条件5: 短期修复迹象
    ma5 = indicators.get("ma_5")
    ma10 = indicators.get("ma_10")
    if close and ma5 and ma10:
        if close >= ma5:
            score += 1
            evidence.append("价格重新站上MA5")
        elif abs(ma5 - ma10) / ma10 < 0.01:
            score += 1
            evidence.append("MA5/MA10开始走平")
        else:
            missing.append("尚未出现短期修复迹象")
    else:
        missing.append("MA5/MA10 数据不足")

    # 状态分层
    weekly_trend = (weekly_background or {}).get("trend")
    if weekly_trend is None:
        is_weekly_downtrend = (
            trend_state.get("primary_state") == "下降趋势"
            and trend_state.get("stage") in ["破坏期", "转弱期"]
        )
    else:
        is_weekly_downtrend = weekly_trend == "单边下跌"

    if score >= 5 and indicators.get("volume", 0) > df_daily["volume"].iloc[-20:].mean() * 1.2 and close and indicators.get("ma_20") and close >= indicators["ma_20"]:
        state = "bottom_strengthened"
        conf = "高"
    elif score >= 4 and not is_weekly_downtrend:
        state = "bottom_candidate"
        conf = "中"
    elif score >= 3:
        state = "bottom_watch"
        conf = "低"
    else:
        state = "none"
        conf = "低"

    return {
        "state": state,
        "confidence": conf,
        "score": score,
        "total": 5,
        "evidence": evidence,
        "missing": missing,
        "swing_low_status": swing_low_status,
        "action_hint": "仅作底部区域观察，不构成买入信号",
        "risk": "若收盘有效跌破最近swing low，则底部观察失效",
    }
