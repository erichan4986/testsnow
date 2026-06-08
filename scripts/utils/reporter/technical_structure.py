"""结构分析模块 — BIAS、BOLL状态、K线特征、MA方向、周线趋势、支撑阻力。"""

import logging
from collections import Counter
from typing import Dict

import numpy as np
import pandas as pd

__all__ = [
    "compute_bias", "compute_boll_state", "compute_candle_features",
    "compute_ma_direction", "resample_daily_to_weekly",
    "compute_weekly_trend", "find_support_resistance",
    "evaluate_sr_transformation",
]

logger = logging.getLogger(__name__)


def evaluate_sr_transformation(close, support_zone, resistance_zone, recent_closes):
    """Placeholder for support/resistance transformation rules."""
    return None


def compute_bias(df: pd.DataFrame, windows=(5, 10, 20), lookback=120) -> Dict:
    """计算 BIAS(5/10/20)，并标记120日极值（防 look-ahead）。"""
    close = df["close"].astype(float)
    out = {}
    for n in windows:
        ma = close.rolling(n, min_periods=n).mean()
        bias = (close / ma - 1.0) * 100
        cur = bias.iloc[-1]
        out[f"bias_{n}"] = None if pd.isna(cur) else round(float(cur), 2)
        if n in (5, 10):
            hist = bias.shift(1).rolling(lookback, min_periods=min(60, lookback))
            prev_max = hist.max().iloc[-1]
            prev_min = hist.min().iloc[-1]
            out[f"bias_{n}_extreme_high"] = bool(
                pd.notna(cur) and pd.notna(prev_max) and cur > prev_max
            )
            out[f"bias_{n}_extreme_low"] = bool(
                pd.notna(cur) and pd.notna(prev_min) and cur < prev_min
            )
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
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
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

    if len(df) < 30:
        return {"support_zone": None, "resistance_zone": None}

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
        return {"support_zone": None, "resistance_zone": None}

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
        return pd.Series(valid)

    max_prices_raw = recent_high[local_max_mask].dropna()
    min_prices_raw = recent_low[local_min_mask].dropna()

    max_prices = _valid_touches(max_prices_raw, is_support=False)
    min_prices = _valid_touches(min_prices_raw, is_support=True)

    if len(max_prices) < min_touches or len(min_prices) < min_touches:
        return {"support_zone": None, "resistance_zone": None}

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

    return {
        "support_zone": support_zone,
        "resistance_zone": resistance_zone,
    }
