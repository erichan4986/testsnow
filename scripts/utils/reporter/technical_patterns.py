"""形态与预警模块 — 双顶/双底、BOLL超买预警、K线位置评估。"""

from typing import Dict, Optional, Tuple

import pandas as pd

__all__ = [
    "detect_double_top", "detect_double_bottom",
    "detect_boll_overextension", "evaluate_candle_at_key_levels",
]

# Placeholder for Task 6 (Phase 2B):
def evaluate_candle_at_key_levels(candle, key_levels, close, boll_state, boll_lower=None, boll_upper=None):
    """Placeholder for candle pattern evaluation at key levels."""
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
