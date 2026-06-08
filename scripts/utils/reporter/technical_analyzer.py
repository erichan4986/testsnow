"""技术分析引擎 — 纯 pandas 实现，无外部依赖。

支持：趋势/动量/波动/量价指标 + 形态识别 + 多指标共振。
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from .technical_indicators import (
        sma as _sma, ema as _ema, atr as _atr, adx as _adx,
        cci as _cci, williams_r as _williams_r, stoch_rsi as _stoch_rsi,
        obv as _obv, macd as _macd, bollinger as _bollinger, rsi as _rsi,
    )
except ImportError:
    from technical_indicators import (
        sma as _sma, ema as _ema, atr as _atr, adx as _adx,
        cci as _cci, williams_r as _williams_r, stoch_rsi as _stoch_rsi,
        obv as _obv, macd as _macd, bollinger as _bollinger, rsi as _rsi,
    )


# ---------------------------------------------------------------------------
# 1. 基础指标计算（已从 technical_indicators 重新导出）
# ---------------------------------------------------------------------------

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

    from collections import Counter
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


# ---------------------------------------------------------------------------
# 2. 形态识别
# ---------------------------------------------------------------------------

def detect_double_top(close: pd.Series, lookback: int = 30, tolerance: float = 0.03) -> Optional[Dict]:
    """双顶：两个相近高点中间一个低谷。"""
    if len(close) < lookback + 5:
        return None
    window = close.iloc[-lookback:]
    # 找局部极大值
    local_max = window[(window.shift(1) < window) & (window.shift(-1) < window)]
    if len(local_max) < 2:
        return None
    # 取最大的两个峰值
    top1_idx, top1_val = local_max.nlargest(2).index[0], local_max.nlargest(2).iloc[0]
    top2_idx, top2_val = local_max.nlargest(2).index[1], local_max.nlargest(2).iloc[1]
    #  valley between them
    between = window.loc[top1_idx:top2_idx]
    if between.empty or len(between) < 3:
        return None
    valley = between.min()
    # 两个顶高度接近
    if abs(top1_val - top2_val) / top1_val > tolerance:
        return None
    # valley 明显低于两个顶
    if valley > min(top1_val, top2_val) * 0.97:
        return None
    return {
        "pattern": "双顶",
        "confidence": "中",
        "top1": round(top1_val, 2),
        "top2": round(top2_val, 2),
        "valley": round(valley, 2),
        "description": f"两个高点 {round(top1_val,2)} / {round(top2_val,2)} 接近，颈线 {round(valley,2)}，跌破颈线确认看跌",
    }


def detect_double_bottom(close: pd.Series, lookback: int = 30, tolerance: float = 0.03) -> Optional[Dict]:
    """双底：两个相近低点中间一个高峰。"""
    if len(close) < lookback + 5:
        return None
    window = close.iloc[-lookback:]
    local_min = window[(window.shift(1) > window) & (window.shift(-1) > window)]
    if len(local_min) < 2:
        return None
    bot1_idx, bot1_val = local_min.nsmallest(2).index[0], local_min.nsmallest(2).iloc[0]
    bot2_idx, bot2_val = local_min.nsmallest(2).index[1], local_min.nsmallest(2).iloc[1]
    between = window.loc[bot1_idx:bot2_idx]
    if between.empty or len(between) < 3:
        return None
    peak = between.max()
    if abs(bot1_val - bot2_val) / bot1_val > tolerance:
        return None
    if peak < max(bot1_val, bot2_val) * 1.03:
        return None
    return {
        "pattern": "双底",
        "confidence": "中",
        "bottom1": round(bot1_val, 2),
        "bottom2": round(bot2_val, 2),
        "peak": round(peak, 2),
        "description": f"两个低点 {round(bot1_val,2)} / {round(bot2_val,2)} 接近，颈线 {round(peak,2)}，突破颈线确认看涨",
    }


def _is_support_resistance(close: pd.Series, window: int = 20, touches: int = 3) -> Tuple[Optional[float], Optional[float]]:
    """找最近 N 天的支撑位和阻力位（基于多次触碰的价格水平）。"""
    if len(close) < window:
        return None, None
    recent = close.iloc[-window:]
    # 简单实现：用 local min/max 近似
    local_min = recent[(recent.shift(1) > recent) & (recent.shift(-1) > recent)]
    local_max = recent[(recent.shift(1) < recent) & (recent.shift(-1) < recent)]
    support = local_min.mean() if not local_min.empty else None
    resistance = local_max.mean() if not local_max.empty else None
    return support, resistance


# ---------------------------------------------------------------------------
# 3. 多指标共振
# ---------------------------------------------------------------------------

def multi_indicator_resonance(indicators: Dict) -> Dict:
    """
    综合判断趋势、动量、量价配合。
    返回：{
        trend: "多头"/"空头"/"震荡",
        momentum: "超买"/"超卖"/"中性",
        volume_price: "确认"/"背离"/"中性",
        composite_score: 0-10,
        signals: [" bullish 信号1", "bearish 信号2", ...],
    }
    """
    signals = []
    score = 5.0

    # --- 趋势判断 (ADX + MA 排列) ---
    adx = indicators.get("adx")
    plus_di = indicators.get("plus_di")
    minus_di = indicators.get("minus_di")
    ma5 = indicators.get("ma_5")
    ma20 = indicators.get("ma_20")
    ma60 = indicators.get("ma_60")
    close = indicators.get("close")

    trend = "震荡"
    if adx is not None and adx > 25:
        if plus_di is not None and minus_di is not None and plus_di > minus_di:
            trend = "多头"
            score += 1.0
            signals.append(f"ADX={adx:.1f} 强趋势，+DI > -DI，多头排列")
        elif plus_di is not None and minus_di is not None and plus_di < minus_di:
            trend = "空头"
            score -= 1.0
            signals.append(f"ADX={adx:.1f} 强趋势，-DI > +DI，空头排列")
    else:
        adx_str = f"{adx:.1f}" if adx is not None else "N/A"
        signals.append(f"ADX={adx_str} 趋势偏弱，震荡格局")

    if ma5 is not None and ma20 is not None and ma60 is not None and close is not None:
        if ma5 > ma20 > ma60 and close > ma5:
            if trend != "多头":
                trend = "多头"
            score += 0.5
            signals.append("MA 多头排列（5>20>60）")
        elif ma5 < ma20 < ma60 and close < ma5:
            if trend != "空头":
                trend = "空头"
            score -= 0.5
            signals.append("MA 空头排列（5<20<60）")

    # --- 动量判断 (RSI + StochRSI + Williams %R) ---
    rsi = indicators.get("rsi_14")
    stoch_k = indicators.get("stoch_rsi_k")
    williams = indicators.get("williams_r")

    momentum = "中性"
    if rsi is not None and rsi > 70:
        momentum = "超买"
        score -= 0.5
        signals.append(f"RSI={rsi:.1f} 超买，短期回调风险")
    elif rsi is not None and rsi < 30:
        momentum = "超卖"
        score += 0.5
        signals.append(f"RSI={rsi:.1f} 超卖，短期反弹机会")
    else:
        if rsi is not None:
            signals.append(f"RSI={rsi:.1f} 中性区间")

    if stoch_k is not None:
        if stoch_k > 0.8:
            score -= 0.3
            signals.append(f"StochRSI K={stoch_k:.2f} 接近超买")
        elif stoch_k < 0.2:
            score += 0.3
            signals.append(f"StochRSI K={stoch_k:.2f} 接近超卖")

    if williams is not None:
        if williams > -20:
            score -= 0.3
            signals.append(f"Williams %R={williams:.1f} 超买区")
        elif williams < -80:
            score += 0.3
            signals.append(f"Williams %R={williams:.1f} 超卖区")

    # --- MACD 动量 ---
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    macd_hist = indicators.get("macd_hist")
    if macd is not None and macd_signal is not None:
        if macd > macd_signal and macd_hist is not None and macd_hist > 0:
            score += 0.5
            signals.append("MACD 金叉且柱线扩张，动量向上")
        elif macd < macd_signal and macd_hist is not None and macd_hist < 0:
            score -= 0.5
            signals.append("MACD 死叉且柱线收缩，动量向下")
        elif macd > macd_signal and macd_hist is not None and macd_hist < 0:
            signals.append("MACD 金叉但柱线收缩，动量减弱")
        elif macd < macd_signal and macd_hist is not None and macd_hist > 0:
            signals.append("MACD 死叉但柱线收缩，下跌动能减弱")

    # --- 量价配合 (OBV vs Price) ---
    obv_slope = indicators.get("obv_slope_5")
    price_slope = indicators.get("price_slope_5")
    volume_price = "中性"
    if obv_slope is not None and price_slope is not None:
        if price_slope > 0 and obv_slope > 0:
            volume_price = "确认"
            score += 0.5
            signals.append("量价齐升，上涨趋势获成交量确认")
        elif price_slope > 0 and obv_slope < 0:
            volume_price = "背离"
            score -= 0.8
            signals.append("⚠️ 量价背离：价格上涨但 OBV 下降，上涨乏力")
        elif price_slope < 0 and obv_slope < 0:
            volume_price = "确认"
            score -= 0.5
            signals.append("量价齐跌，下跌趋势获成交量确认")
        elif price_slope < 0 and obv_slope > 0:
            volume_price = "背离"
            score += 0.8
            signals.append("✅ 底背离：价格下跌但 OBV 上升，吸筹迹象")

    # --- 布林带位置 ---
    boll_upper = indicators.get("boll_upper")
    boll_lower = indicators.get("boll_lower")
    if boll_upper is not None and boll_lower is not None and close is not None:
        if close > boll_upper:
            score -= 0.3
            signals.append("价格突破布林带上轨，短期超买")
        elif close < boll_lower:
            score += 0.3
            signals.append("价格跌破布林带下轨，短期超卖")

    # --- 波动率 (ATR) ---
    atr = indicators.get("atr_14")
    if atr is not None and close is not None:
        atr_pct = atr / close * 100
        if atr_pct > 5:
            signals.append(f"ATR={atr_pct:.1f}% 高波动，注意风控")
        elif atr_pct < 1.5:
            signals.append(f"ATR={atr_pct:.1f}% 低波动，可能酝酿突破")

    score = round(max(0.0, min(10.0, score)), 1)

    return {
        "trend": trend,
        "momentum": momentum,
        "volume_price": volume_price,
        "composite_score": score,
        "signals": signals,
    }


# ---------------------------------------------------------------------------
# 4. 主入口
# ---------------------------------------------------------------------------

def _compute_base_indicators(df: pd.DataFrame) -> Dict:
    """计算全部旧版指标。被 analyze() 和 advanced_medium_term_resonance() 复用。"""
    close = df["close"]
    volume = df["volume"]

    macd_line, macd_sig, macd_hist = _macd(close)
    boll_up, boll_mid, boll_low = _bollinger(close)
    adx, plus_di, minus_di = _adx(df)
    cci = _cci(df)
    williams = _williams_r(df)
    stoch_k, stoch_d = _stoch_rsi(close)
    atr = _atr(df)
    obv_series = _obv(close, volume)

    indicators = {
        "close": float(close.iloc[-1]),
        "volume": int(volume.iloc[-1]),
        "macd": float(macd_line.iloc[-1]),
        "macd_signal": float(macd_sig.iloc[-1]),
        "macd_hist": float(macd_hist.iloc[-1]),
        "rsi_14": float(_rsi(close, 14).iloc[-1]),
        "stoch_rsi_k": float(stoch_k.iloc[-1]),
        "stoch_rsi_d": float(stoch_d.iloc[-1]),
        "williams_r": float(williams.iloc[-1]),
        "cci_20": float(cci.iloc[-1]),
        "adx": float(adx.iloc[-1]),
        "plus_di": float(plus_di.iloc[-1]),
        "minus_di": float(minus_di.iloc[-1]),
        "atr_14": float(atr.iloc[-1]),
        "obv": int(obv_series.iloc[-1]),
        "obv_slope_5": float(obv_series.diff().tail(5).mean()),
        "price_slope_5": float(close.diff().tail(5).mean()),
        "ma_5": float(_sma(close, 5).iloc[-1]),
        "ma_10": float(_sma(close, 10).iloc[-1]),
        "ma_20": float(_sma(close, 20).iloc[-1]),
        "ma_60": float(_sma(close, 60).iloc[-1]),
        "ema_20": float(_ema(close, 20).iloc[-1]),
        "ema_60": float(_ema(close, 60).iloc[-1]),
        "boll_upper": float(boll_up.iloc[-1]),
        "boll_mid": float(boll_mid.iloc[-1]),
        "boll_lower": float(boll_low.iloc[-1]),
    }

    if len(df) >= 22:
        indicators["monthly_return_pct"] = round(
            (close.iloc[-1] - close.iloc[-22]) / close.iloc[-22] * 100, 2
        )
    if len(df) >= 20 and "amount" in df.columns:
        avg_amount = float(df["amount"].tail(20).mean())
        indicators["avg_amount_yi"] = round(avg_amount / 100000000, 2)
    elif len(df) >= 20:
        avg_vol = float(volume.tail(20).mean())
        avg_close = float(close.tail(20).mean())
        indicators["avg_amount_yi"] = round(avg_vol * avg_close / 100000000, 2)

    return indicators


def analyze(df: pd.DataFrame, df_weekly: pd.DataFrame | None = None) -> Dict:
    """对日K DataFrame做完整技术分析（中期趋势版）。"""
    if df is None or df.empty or len(df) < 30:
        logger.warning("数据不足30条，无法做完整技术分析")
        return {}

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            logger.error(f"缺少必要列: {col}")
            return {}

    return advanced_medium_term_resonance(df_daily=df, df_weekly=df_weekly)


def classify_trend_state(
    weekly_trend: str,
    daily_structure: Dict,
    indicators: Dict,
    divergence: Dict | None,
) -> Dict:
    """趋势状态机。按优先级判定唯一阶段。price_vs_ma60=='跌破' 直接判定破坏期。"""
    price_vs_ma20 = daily_structure.get("price_vs_ma20", "未知")
    price_vs_ma60 = daily_structure.get("price_vs_ma60", "未知")
    ma20_dir = daily_structure.get("ma20_direction", "未知")
    ma60_dir = daily_structure.get("ma60_direction", "未知")
    boll_state = indicators.get("boll_state", "正常")
    rsi = indicators.get("rsi_14", 50)
    close = indicators.get("close", 0)
    ma20 = indicators.get("ma_20", 0)
    ma60 = indicators.get("ma_60", 0)

    # 1. 破坏期（最高优先级）
    if price_vs_ma60 == "跌破" or weekly_trend in ["单边下跌"]:
        return {
            "primary_state": "下降趋势",
            "stage": "破坏期",
            "action_hint": "趋势失效",
            "state_changed": None,
            "previous_state": None,
            "summary": "中期趋势结构已破坏，日线有效跌破MA60或周线转弱。",
        }

    # 2. 转弱期
    if price_vs_ma20 == "跌破" and (ma20_dir == "走平" or ma20_dir == "向下"):
        return {
            "primary_state": "下降趋势",
            "stage": "转弱期",
            "action_hint": "降低预期",
            "state_changed": None,
            "previous_state": None,
            "summary": "日线跌破MA20，中期趋势进入观察。",
        }

    # 3. 高位钝化期
    if price_vs_ma20 == "站上" and rsi is not None and rsi > 70 and boll_state == "开口":
        if close > ma20 * 1.05:
            return {
                "primary_state": "上升趋势",
                "stage": "高位钝化期",
                "action_hint": "持有跟踪",
                "state_changed": None,
                "previous_state": None,
                "summary": "趋势仍在MA20上方，但RSI高位、BOLL扩张，警惕过热。",
            }

    # 4. 加速期
    if price_vs_ma20 == "站上" and boll_state == "开口" and close > ma20 * 1.03:
        return {
            "primary_state": "上升趋势",
            "stage": "加速期",
            "action_hint": "持有跟踪",
            "state_changed": None,
            "previous_state": None,
            "summary": "趋势加速，BOLL开口扩大，价格远离MA20。",
        }

    # 5. 主升期
    if price_vs_ma20 == "站上" and ma20_dir == "向上" and ma60_dir in ["向上", "走平"]:
        return {
            "primary_state": "上升趋势",
            "stage": "主升期",
            "action_hint": "持有跟踪",
            "state_changed": None,
            "previous_state": None,
            "summary": "周线多头结构完整，日线沿MA20稳步上行。",
        }

    # 6. 启动期
    if price_vs_ma20 == "站上" and weekly_trend in ["趋势修复中", "震荡"]:
        return {
            "primary_state": "上升趋势",
            "stage": "启动期",
            "action_hint": "趋势确认",
            "state_changed": None,
            "previous_state": None,
            "summary": "刚从震荡/下跌修复，均线刚开始多头排列。",
        }

    # 7. 盘整期
    return {
        "primary_state": "震荡趋势",
        "stage": "盘整期",
        "action_hint": "观察",
        "state_changed": None,
        "previous_state": None,
        "summary": "无明显趋势方向，以观望为主。",
    }


def apply_previous_state(trend_state: Dict, previous_state: Dict | None) -> None:
    """根据上一次分析结果更新 state_changed 和 previous_state。"""
    if previous_state is None:
        trend_state["state_changed"] = None
        trend_state["previous_state"] = None
        return
    old_stage = previous_state.get("trend_state", {}).get("stage")
    cur_stage = trend_state.get("stage")
    trend_state["state_changed"] = old_stage != cur_stage
    trend_state["previous_state"] = old_stage


def compute_trend_health(
    weekly_trend: str,
    daily_structure: Dict,
    indicators: Dict,
    config: Dict | None = None,
) -> Dict:
    """计算趋势健康度评分（0-100）。"""
    if config is None:
        config = {"technical": {"scoring": {
            "weekly_structure_weight": 30, "daily_ma_weight": 25,
            "price_structure_weight": 15, "volume_weight": 10,
            "volatility_weight": 10, "risk_penalty_weight": 10,
        }}}
    sc = config.get("technical", {}).get("scoring", {})

    score = 0
    components = {}
    penalties = {}
    deductions = []

    if weekly_trend == "单边上涨":
        components["weekly_structure"] = {"score": 25, "max": 30, "evidence": "周线多头排列"}
        score += 25
    elif weekly_trend == "震荡":
        components["weekly_structure"] = {"score": 10, "max": 30, "evidence": "周线震荡"}
        score += 10
    else:
        components["weekly_structure"] = {"score": 5, "max": 30, "evidence": f"周线{weekly_trend}"}
        score += 5

    ma20_dir = daily_structure.get("ma20_direction", "未知")
    ma60_dir = daily_structure.get("ma60_direction", "未知")
    price_vs_ma20 = daily_structure.get("price_vs_ma20", "未知")
    if ma20_dir == "向上" and price_vs_ma20 == "站上":
        components["daily_ma_alignment"] = {"score": 20, "max": 25, "evidence": "MA20向上，价格站上"}
        score += 20
    elif ma20_dir == "走平":
        components["daily_ma_alignment"] = {"score": 10, "max": 25, "evidence": "MA20走平"}
        score += 10
    else:
        components["daily_ma_alignment"] = {"score": 5, "max": 25, "evidence": "MA20向下或价格跌破"}
        score += 5

    structure_type = daily_structure.get("structure_type", "无明显结构")
    if structure_type in ["上升通道", "平台整理"]:
        components["price_structure"] = {"score": 12, "max": 15, "evidence": structure_type}
        score += 12
    else:
        components["price_structure"] = {"score": 5, "max": 15, "evidence": structure_type}
        score += 5

    components["volume_confirmation"] = {"score": 8, "max": 10, "evidence": "成交额温和"}
    score += 8

    boll_state = indicators.get("boll_state", "正常")
    if boll_state == "开口":
        components["volatility_condition"] = {"score": 7, "max": 10, "evidence": "BOLL开口，趋势波动放大"}
        score += 7
    else:
        components["volatility_condition"] = {"score": 5, "max": 10, "evidence": f"BOLL{boll_state}"}
        score += 5

    rsi = indicators.get("rsi_14")
    if rsi is not None and rsi > 75:
        penalties["overextension"] = {"score": -5, "min": -10, "evidence": f"RSI={rsi:.1f} 偏高"}
        score -= 5
        deductions.append("RSI偏高")

    bias_5 = indicators.get("bias_5")
    if bias_5 is not None and bias_5 > 5:
        penalties["overextension"] = penalties.get("overextension", {"score": 0, "min": -10, "evidence": ""})
        penalties["overextension"]["score"] -= 3
        penalties["overextension"]["evidence"] += f" BIAS(5)={bias_5:.1f}%"
        score -= 3
        deductions.append("BIAS偏高")

    score = max(0, min(100, score))

    if score >= 80:
        grade = "趋势强健"
    elif score >= 65:
        grade = "健康"
    elif score >= 50:
        grade = "转弱观察"
    elif score >= 30:
        grade = "破坏风险高"
    else:
        grade = "趋势失效"

    return {
        "score": score,
        "grade": grade,
        "summary": f"趋势健康度{score}/100，{grade}。",
        "components": components,
        "penalties": penalties,
        "deductions": deductions,
    }


def compute_invalidation(
    close: float,
    ma20: float | None,
    ma60: float | None,
    support_zone: Dict | None,
    config: Dict | None = None,
) -> Dict:
    """生成趋势失效条件。hard_invalid_price 是价格位，current_distance_to_invalid 是距离百分比。"""
    if config is None:
        config = {"technical": {"ma": {"ma20_warning_confirm_days": 3, "ma60_break_confirm_days": 2}}}
    ma_cfg = config.get("technical", {}).get("ma", {})

    soft = f"日线连续{ma_cfg.get('ma20_warning_confirm_days', 3)}日收盘跌破MA20"
    hard = "周线收盘跌破MA10，或日线有效跌破MA60"
    struct_break = "跌破前期平台下沿"

    hard_price = ma60 if ma60 and ma60 > 0 else None
    distance = None
    if hard_price and hard_price > 0:
        distance = f"{(close - hard_price) / hard_price * 100:.1f}%"
    elif support_zone and support_zone.get("zone_low"):
        hard_price = support_zone["zone_low"]
        distance = f"{(close - hard_price) / close * 100:.1f}%"

    return {
        "soft_warning": soft,
        "hard_invalid": hard,
        "hard_invalid_price": hard_price,
        "structure_break": struct_break,
        "current_distance_to_invalid": distance or "未知",
    }


def detect_boll_overextension(
    df: pd.DataFrame,
    indicators: Dict,
    weekly_trend: str,
    config: Dict | None = None,
) -> Dict | None:
    """简化版背离/超买预警。检测价格突破 BOLL 上轨 + RSI 极端值。"""
    if config is None:
        config = {"technical": {"divergence": {
            "boll_upper_tolerance": 1.01,
        }}}
    boll_tol = config.get("technical", {}).get("divergence", {}).get("boll_upper_tolerance", 1.01)

    close = indicators.get("close", 0)
    boll_upper = indicators.get("boll_upper")
    boll_lower = indicators.get("boll_lower")
    rsi = indicators.get("rsi_14")
    macd_hist = indicators.get("macd_hist")

    warnings = []
    evidence = {}

    # BOLL 超买/超卖
    if boll_upper and close > boll_upper * boll_tol:
        warnings.append("boll_overextension")
        evidence["boll"] = {"price": close, "upper": boll_upper, "state": "突破上轨"}
    elif boll_lower and close < boll_lower / boll_tol:
        warnings.append("boll_overextension")
        evidence["boll"] = {"price": close, "lower": boll_lower, "state": "跌破下轨"}

    # RSI 极端
    if rsi is not None and rsi > 75:
        warnings.append("rsi_overbought")
        evidence["rsi"] = {"value": rsi, "state": "超买区"}
    elif rsi is not None and rsi < 25:
        warnings.append("rsi_oversold")
        evidence["rsi"] = {"value": rsi, "state": "超卖区"}

    # MACD 柱线收缩
    if macd_hist is not None and macd_hist < 0:
        warnings.append("macd_hist_shrinking")
        evidence["macd"] = {"hist": macd_hist, "state": "柱线翻绿"}

    if len(warnings) >= 2:
        return {
            "type": "超买预警" if close > (boll_upper or close) else "超卖预警",
            "confidence": "强烈" if len(warnings) >= 3 else "中度",
            "matched": len(warnings),
            "total": 3,
            "evidence": evidence,
            "missing": [],
            "action": "均线为王，仅作中期风险预警" if weekly_trend == "单边上涨" else "建议减仓观察",
        }
    elif len(warnings) == 1:
        return {
            "type": "单一预警",
            "confidence": "轻度",
            "matched": 1,
            "total": 3,
            "evidence": evidence,
            "missing": [],
            "action": "观望",
        }

    return None


def advanced_medium_term_resonance(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame | None = None,
    quote: Dict | None = None,
    previous_state: Dict | None = None,
    config: Dict | None = None,
) -> Dict:
    """中期趋势技术分析主入口。"""
    if config is None:
        from technical_config import load_technical_config
        config = load_technical_config()

    # 1. 数据质量
    daily_count = len(df_daily) if df_daily is not None else 0

    # 2. 自动 resample 周线（如果未传入）
    if df_weekly is None and df_daily is not None and len(df_daily) >= 5:
        df_weekly = resample_daily_to_weekly(df_daily)
    weekly_count = len(df_weekly) if df_weekly is not None else 0
    sufficient = daily_count >= 120 and weekly_count >= 20

    # 3. 计算全部旧指标（复用 Task 2）
    indicators = _compute_base_indicators(df_daily)

    # BIAS
    bias_result = compute_bias(df_daily)
    indicators.update(bias_result)

    # BOLL state
    close = df_daily["close"].astype(float)
    boll_up, boll_mid, boll_low = _bollinger(close)
    df_boll = pd.DataFrame({"boll_upper": boll_up, "boll_mid": boll_mid, "boll_lower": boll_low})
    boll_result = compute_boll_state(df_boll, config)
    indicators.update(boll_result)
    indicators["boll_upper"] = float(boll_up.iloc[-1])
    indicators["boll_mid"] = float(boll_mid.iloc[-1])
    indicators["boll_lower"] = float(boll_low.iloc[-1])

    # 成交额
    if "amount" in df_daily.columns:
        indicators["amount"] = float(df_daily["amount"].iloc[-1])
        indicators["amount_ma20"] = float(df_daily["amount"].tail(20).mean())
    elif "turnover" in df_daily.columns:
        indicators["turnover_ma20"] = float(df_daily["turnover"].tail(20).mean())

    # 4. 周线趋势
    weekly_result = compute_weekly_trend(df_weekly) if df_weekly is not None and len(df_weekly) >= 20 else {
        "weekly_trend": "未知", "weekly_close": None, "weekly_ma5": None,
        "weekly_ma10": None, "weekly_ma20": None, "ma20_direction": "未知",
        "weekly_trend_evidence": {"reason": "周线数据不足"},
    }
    indicators["weekly_close"] = weekly_result.get("weekly_close")
    indicators["weekly_ma5"] = weekly_result.get("weekly_ma5")
    indicators["weekly_ma10"] = weekly_result.get("weekly_ma10")
    indicators["weekly_ma20"] = weekly_result.get("weekly_ma20")
    indicators["weekly_trend"] = weekly_result.get("weekly_trend")

    # 5. 日线结构
    price_vs_ma20 = "站上" if indicators["close"] > indicators["ma_20"] else "跌破"
    price_vs_ma60 = "站上" if indicators["close"] > indicators["ma_60"] else "跌破"
    daily_structure = {
        "ma20_direction": compute_ma_direction(_sma(close, 20)),
        "ma60_direction": compute_ma_direction(_sma(close, 60)),
        "price_vs_ma20": price_vs_ma20,
        "price_vs_ma60": price_vs_ma60,
        "structure_type": "无明显结构",
        "boll_state": indicators.get("boll_state", "正常"),
        "price_position": "中轨附近",
    }

    # 6. 支撑阻力
    sr_result = find_support_resistance(df_daily, config)

    # 7. 简化背离扫描
    divergence = detect_boll_overextension(df_daily, indicators, weekly_result["weekly_trend"], config)

    # 8. 趋势状态机
    trend_state = classify_trend_state(
        weekly_trend=weekly_result["weekly_trend"],
        daily_structure=daily_structure,
        indicators=indicators,
        divergence=divergence,
    )
    apply_previous_state(trend_state, previous_state)

    # 9. 趋势健康度
    trend_health = compute_trend_health(
        weekly_trend=weekly_result["weekly_trend"],
        daily_structure=daily_structure,
        indicators=indicators,
        config=config,
    )

    # 10. 失效条件
    invalidation = compute_invalidation(
        close=indicators["close"],
        ma20=indicators.get("ma_20"),
        ma60=indicators.get("ma_60"),
        support_zone=sr_result.get("support_zone"),
        config=config,
    )

    # 11. 分析可信度
    limitations = []
    if daily_count < 120:
        limitations.append("日线数据不足120根")
    if weekly_count < 20:
        limitations.append("周线数据不足20根")
    if not sufficient:
        limitations.append("不满足完整中期趋势分析条件")

    analysis_confidence = {
        "level": "高" if sufficient and not limitations else ("中" if daily_count >= 60 else "低"),
        "reasons": [f"日线{daily_count}根", f"周线{weekly_count}根"] if sufficient else [],
        "limitations": limitations,
    }

    # 12. 组装 _resonance
    _resonance = {
        "trend": "多头" if trend_state["primary_state"] == "上升趋势" else ("空头" if trend_state["primary_state"] == "下降趋势" else "震荡"),
        "momentum": "偏强" if trend_health["score"] >= 65 else "偏弱",
        "volume_price": "确认",
        "composite_score": round(min(10, max(0, trend_health["score"] / 10)), 1),
        "signals": [f"趋势阶段：{trend_state['stage']}"],

        "analysis_horizon": "中期（日线-周线）",
        "analysis_confidence": analysis_confidence,
        "trend_state": trend_state,
        "weekly_background": {
            "trend": weekly_result["weekly_trend"],
            "ma_structure": weekly_result["weekly_trend_evidence"].get("ma_order", "未知"),
            "weekly_close_position": "站上MA10" if weekly_result.get("weekly_close") and weekly_result.get("weekly_ma10") and weekly_result["weekly_close"] > weekly_result["weekly_ma10"] else "未知",
            "evidence": weekly_result["weekly_trend_evidence"],
        },
        "daily_structure": daily_structure,
        "trend_health": trend_health,
        "key_levels": {
            "support_zone": sr_result.get("support_zone"),
            "resistance_zone": sr_result.get("resistance_zone"),
            "medium_term_invalid": invalidation.get("hard_invalid_price"),
        },
        "invalidation": invalidation,
        "market_regime": {
            "market_trend": "未知",
            "sector_trend": "未知",
            "relative_strength": "未知",
            "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
        },
        "advisors": {
            "macd": {"state": "多头延续" if indicators.get("macd", 0) > 0 else "空头延续",
                     "meaning": "仅作趋势确认，不单独构成买卖信号"},
            "rsi": {"value": indicators.get("rsi_14"),
                    "state": "强势钝化" if indicators.get("rsi_14", 50) > 70 else "正常",
                    "meaning": "强趋势中不单独构成卖出信号"},
            "bias": {"state": "偏高" if indicators.get("bias_5", 0) > 3 else "正常",
                     "meaning": "短线追高性价比下降，但中期趋势未破坏"},
            "boll": {"state": indicators.get("boll_state", "正常"),
                     "meaning": "开口=趋势加速，缩口=等待方向"},
        },
        "divergence_scan": divergence,
        "sell_assessment": None,
        "basis_rules": ["周线优先原则", "MA20/MA60 中期结构判定", "有效突破/跌破去抖动规则", "均线为王，谋士辅助"],
        "risk_reminder": "本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。",
    }

    return {
        "indicators": indicators,
        "resonance": _resonance,
        "patterns": [],
        "levels": {
            "support": sr_result["support_zone"]["price"] if sr_result.get("support_zone") else None,
            "resistance": sr_result["resistance_zone"]["price"] if sr_result.get("resistance_zone") else None,
        },
    }
