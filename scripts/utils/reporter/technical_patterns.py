"""形态与预警模块 — 双顶/双底、BOLL超买预警、K线位置评估。"""

from typing import Dict, Optional, Tuple

import pandas as pd

try:
    from .technical_structure import confirmed_swing_indices
except ImportError:
    from technical_structure import confirmed_swing_indices

__all__ = [
    "detect_double_top", "detect_double_bottom",
    "classify_macd_histogram", "detect_boll_overextension",
    "detect_momentum_extreme", "detect_pivot_divergence",
    "evaluate_candle_at_key_levels",
]

def evaluate_candle_at_key_levels(
    candle: dict,
    key_levels: dict,
    close: float,
    boll_state: str,
    boll_lower: float | None = None,
    boll_upper: float | None = None,
) -> dict | None:
    """
    在关键位置评估 K 线形态信号。
    只在支撑区、阻力区、BOLL 上轨/下轨附近输出提示。
    """
    # Determine proximity to key levels (generous ±3% band for S/R, ±2% for BOLL)
    near_support = False
    below_support = False
    near_resistance = False
    above_resistance = False
    near_boll_lower = False
    near_boll_upper = False

    support_zone = key_levels.get("support_zone") if key_levels else None
    if support_zone is not None:
        zone_low = support_zone.get("zone_low")
        zone_high = support_zone.get("zone_high")
        if zone_low is not None and zone_high is not None:
            lower = zone_low * 0.97
            upper = zone_high * 1.03
            if zone_low <= close <= zone_high:
                near_support = True
            elif lower <= close < zone_low:
                near_support = True
                below_support = True

    resistance_zone = key_levels.get("resistance_zone") if key_levels else None
    if resistance_zone is not None:
        zone_low = resistance_zone.get("zone_low")
        zone_high = resistance_zone.get("zone_high")
        if zone_low is not None and zone_high is not None:
            lower = zone_low * 0.97
            upper = zone_high * 1.03
            if zone_low <= close <= zone_high:
                near_resistance = True
            elif zone_high < close <= upper:
                near_resistance = True
                above_resistance = True

    if boll_lower is not None:
        if close <= boll_lower * 1.02:
            near_boll_lower = True

    if boll_upper is not None:
        if close >= boll_upper * 0.98:
            near_boll_upper = True

    at_key_level = near_support or near_resistance or near_boll_lower or near_boll_upper
    if not at_key_level:
        return None

    is_doji = candle.get("is_doji", False)
    is_long_lower = candle.get("is_long_lower_shadow", False)
    is_long_upper = candle.get("is_long_upper_shadow", False)

    if is_doji:
        return {
            "signal": "十字星，多空胶着，变盘可能增加",
            "strength": "reversal_watch",
            "location": "关键位",
        }

    if is_long_lower and (near_support or near_boll_lower):
        if below_support:
            return {
                "signal": "长下影，价格已跌破原支撑区，下方承接力观察中",
                "strength": "support_confirm",
                "location": "支撑位下方",
            }
        return {
            "signal": "长下影，下方承接力较强",
            "strength": "support_confirm",
            "location": "支撑位",
        }

    if is_long_upper and (near_resistance or near_boll_upper):
        if above_resistance:
            return {
                "signal": "长上影，价格已突破原阻力区，上方抛压观察中",
                "strength": "resistance_warn",
                "location": "阻力位上方",
            }
        return {
            "signal": "长上影，上方抛压较重",
            "strength": "resistance_warn",
            "location": "阻力位",
        }

    return None


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


def classify_macd_histogram(current: float | None, previous: float | None) -> str:
    if current is None or previous is None or pd.isna(current) or pd.isna(previous) or current == previous:
        return "方向未确认"
    if current < 0:
        return "空头柱扩张" if current < previous else "空头柱收缩"
    if current > 0:
        return "多头柱扩张" if current > previous else "多头柱收缩"
    return "方向未确认"


def detect_momentum_extreme(
    df: pd.DataFrame,
    indicators: Dict,
    weekly_trend: str,
    config: Dict | None = None,
) -> Dict | None:
    cfg = (config or {}).get("technical", {}).get("divergence", {})
    tolerance = cfg.get("boll_upper_tolerance", 1.01)
    close, upper, lower = indicators.get("close", 0), indicators.get("boll_upper"), indicators.get("boll_lower")
    rsi = indicators.get("rsi_14")
    hist_state = classify_macd_histogram(indicators.get("macd_hist"), indicators.get("macd_hist_prev"))
    direction = (
        "overbought" if upper and close > upper * tolerance
        else "oversold" if lower and close < lower / tolerance
        else "overbought" if rsi is not None and rsi > 75
        else "oversold" if rsi is not None and rsi < 25
        else None
    )
    matched, evidence = [], {"macd": {"hist": indicators.get("macd_hist"), "state": hist_state}}
    if direction == "overbought":
        if upper and close > upper * tolerance:
            matched.append("boll"); evidence["boll"] = {"price": close, "upper": upper, "state": "突破上轨"}
        if rsi is not None and rsi > 75:
            matched.append("rsi"); evidence["rsi"] = {"value": rsi, "state": "超买区"}
        if hist_state == "多头柱收缩":
            matched.append("macd")
    elif direction == "oversold":
        if lower and close < lower / tolerance:
            matched.append("boll"); evidence["boll"] = {"price": close, "lower": lower, "state": "跌破下轨"}
        if rsi is not None and rsi < 25:
            matched.append("rsi"); evidence["rsi"] = {"value": rsi, "state": "超卖区"}
        if hist_state == "空头柱收缩":
            matched.append("macd")
    if not matched:
        return None
    return {
        "family": "momentum_extreme",
        "type": "超买预警" if direction == "overbought" else "超卖预警" if direction == "oversold" else "单一预警",
        "confidence": "强烈" if len(matched) == 3 else "中度" if len(matched) >= 2 else "轻度",
        "matched": len(matched), "total": 3, "evidence": evidence,
        "missing": [name for name in ("boll", "rsi", "macd") if name not in matched],
        "action": "均线为王，仅作中期风险预警" if weekly_trend == "单边上涨" else "建议观察确认",
    }


def detect_boll_overextension(
    df: pd.DataFrame,
    indicators: Dict,
    weekly_trend: str,
    config: Dict | None = None,
) -> Dict | None:
    """Compatibility alias for the canonical momentum-extreme scan."""
    return detect_momentum_extreme(df, indicators, weekly_trend, config)


def detect_pivot_divergence(
    df: pd.DataFrame,
    rsi_series: pd.Series,
    macd_hist_series: pd.Series,
    config: Dict | None = None,
) -> Dict | None:
    cfg = (config or {}).get("technical", {}).get("divergence", {})
    lookback, left, right = cfg.get("lookback", 80), cfg.get("swing_left", 3), cfg.get("swing_right", 3)
    max_age = cfg.get("max_signal_age", 10)
    frame = df.tail(lookback).reset_index(drop=True)
    rsi = pd.Series(rsi_series).tail(len(frame)).reset_index(drop=True)
    hist = pd.Series(macd_hist_series).tail(len(frame)).reset_index(drop=True)
    if len(frame) < left + right + 3 or len(rsi) != len(frame) or len(hist) != len(frame):
        return None
    tr = pd.concat((
        frame["high"] - frame["low"],
        (frame["high"] - frame["close"].shift(1)).abs(),
        (frame["low"] - frame["close"].shift(1)).abs(),
    ), axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=1).mean()
    dates = frame["date"] if "date" in frame.columns else pd.Series(frame.index)

    def candidate(kind: str) -> Dict | None:
        column = "low" if kind == "bullish" else "high"
        pivots = confirmed_swing_indices(frame[column], left, right, "low" if kind == "bullish" else "high")
        if len(pivots) < 2:
            return None
        first, second = pivots[-2:]
        if len(frame) - 1 - second > max_age:
            return None
        first_price, second_price = float(frame[column].iloc[first]), float(frame[column].iloc[second])
        if first_price <= 0 or second_price <= 0:
            return None
        materiality = max(
            cfg.get("price_tolerance_pct", 0.01),
            cfg.get("price_atr_multiplier", 0.5) * float(atr.iloc[second]) / abs(second_price),
        )
        price_change = (second_price - first_price) / abs(first_price)
        price_ok = price_change <= -materiality if kind == "bullish" else price_change >= materiality
        rsi_values, hist_values = rsi.iloc[[first, second]], hist.iloc[[first, second]]
        rsi_ok = bool(not rsi_values.isna().any() and (
            rsi_values.iloc[1] > rsi_values.iloc[0] if kind == "bullish" else rsi_values.iloc[1] < rsi_values.iloc[0]
        ))
        macd_ok = bool(not hist_values.isna().any() and (
            hist_values.iloc[1] > hist_values.iloc[0] if kind == "bullish" else hist_values.iloc[1] < hist_values.iloc[0]
        ))
        matched = 1 + int(bool(rsi_ok)) + int(bool(macd_ok)) if price_ok else 0
        if matched < cfg.get("min_matched", 2):
            return None
        pivot_rows = [
            {"date": str(dates.iloc[i]), "price": float(frame[column].iloc[i]),
             "rsi": None if pd.isna(rsi.iloc[i]) else float(rsi.iloc[i]),
             "macd_hist": None if pd.isna(hist.iloc[i]) else float(hist.iloc[i])}
            for i in (first, second)
        ]
        evidence = [f"价格关系变化 {price_change:.1%}"]
        if rsi_ok:
            evidence.append(f"RSI {rsi.iloc[first]:.1f}->{rsi.iloc[second]:.1f}")
        if macd_ok:
            evidence.append(f"MACD柱 {hist.iloc[first]:.3f}->{hist.iloc[second]:.3f}")
        return {
            "family": "pivot_divergence", "type": "底背离观察" if kind == "bullish" else "顶背离观察",
            "confidence": "强烈" if matched == 3 else "中度", "matched": matched, "total": 3,
            "pivots": pivot_rows,
            "evidence": evidence,
            "missing": [name for name, ok in (("rsi", rsi_ok), ("macd", macd_ok)) if not ok],
            "action": "仅作结构反向线索，等待趋势确认",
            "pivot_index": second,
        }

    candidates = [item for item in (candidate("bullish"), candidate("bearish")) if item]
    if not candidates:
        return None
    result = max(candidates, key=lambda item: item["pivot_index"])
    result.pop("pivot_index")
    return result
