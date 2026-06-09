"""形态与预警模块 — 双顶/双底、BOLL超买预警、K线位置评估。"""

from typing import Dict, Optional, Tuple

import pandas as pd

__all__ = [
    "detect_double_top", "detect_double_bottom",
    "detect_boll_overextension", "evaluate_candle_at_key_levels",
    "multi_indicator_resonance",
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


def multi_indicator_resonance(indicators: Dict) -> Dict:
    """
    综合判断趋势、动量、量价配合（legacy，保留向后兼容）。
    """
    signals = []
    score = 5.0

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

    boll_upper = indicators.get("boll_upper")
    boll_lower = indicators.get("boll_lower")
    if boll_upper is not None and boll_lower is not None and close is not None:
        if close > boll_upper:
            score -= 0.3
            signals.append("价格突破布林带上轨，短期超买")
        elif close < boll_lower:
            score += 0.3
            signals.append("价格跌破布林带下轨，短期超卖")

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
