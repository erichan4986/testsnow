"""价格目标与触发条件核心引擎 — 纯 pandas 实现。"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from .technical_analyzer import _adx, _sma, _atr, _macd, _bollinger
except ImportError:
    from technical_analyzer import _adx, _sma, _atr, _macd, _bollinger

logger = logging.getLogger(__name__)


def zigzag(close: pd.Series, min_pct: float = 0.05) -> List[Dict]:
    """
    识别主要波段转折点（Zigzag）。
    min_pct: 最小转折幅度（日线5%，周线10%基线/芯片股12%）
    返回: [{idx, price, type: 'peak'/'valley'}, ...]
    """
    if len(close) < 3:
        return []

    pivots = []
    direction = 0  # 0=unknown, 1=up, -1=down
    last_pivot_idx = 0
    last_pivot_price = close.iloc[0]
    last_pivot_type = "valley"  # start as valley

    for i in range(1, len(close)):
        price = close.iloc[i]
        change = (price - last_pivot_price) / last_pivot_price

        if direction == 0:
            if abs(change) >= min_pct:
                direction = 1 if change > 0 else -1
                # Initial pivot type depends on first move direction
                initial_type = "valley" if direction == 1 else "peak"
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": initial_type})
                last_pivot_type = "peak" if direction == 1 else "valley"
                last_pivot_idx = i
                last_pivot_price = price
        elif direction == 1:
            if price > last_pivot_price:
                last_pivot_idx = i
                last_pivot_price = price
            elif (last_pivot_price - price) / last_pivot_price >= min_pct:
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": "peak"})
                direction = -1
                last_pivot_type = "valley"
                last_pivot_idx = i
                last_pivot_price = price
        elif direction == -1:
            if price < last_pivot_price:
                last_pivot_idx = i
                last_pivot_price = price
            elif (price - last_pivot_price) / last_pivot_price >= min_pct:
                pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": "valley"})
                direction = 1
                last_pivot_type = "peak"
                last_pivot_idx = i
                last_pivot_price = price

    # Add final pivot if different from last recorded
    if pivots and last_pivot_idx != pivots[-1]["idx"]:
        final_type = "peak" if last_pivot_price > pivots[-1]["price"] else "valley"
        pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": final_type})
    elif not pivots:
        pivots.append({"idx": last_pivot_idx, "price": last_pivot_price, "type": last_pivot_type})

    return pivots


def fib_extension(low: float, high: float, level: float) -> float:
    """从波段低点到高点的斐波那契扩展。"""
    return high + (high - low) * (level - 1)


def fib_targets_with_convergence(
    bands: List[Dict], level: float = 1.272, convergence_pct: float = 0.03
) -> List[Dict]:
    """
    计算多个波段的同向扩展位，检查是否形成汇聚区。
    bands: [{low, high}, ...]
    返回: [{price, band_idx, in_convergence: bool}, ...]
    """
    targets = []
    for i, band in enumerate(bands):
        price = fib_extension(band["low"], band["high"], level)
        targets.append({"price": round(price, 2), "band_idx": i, "in_convergence": False})

    # 检查汇聚：≥2个目标落在 convergence_pct 价格区间内
    n = len(targets)
    for i in range(n):
        for j in range(i + 1, n):
            p1, p2 = targets[i]["price"], targets[j]["price"]
            diff = abs(p1 - p2) / max(p1, p2, 1e-9)
            if diff <= convergence_pct:
                targets[i]["in_convergence"] = True
                targets[j]["in_convergence"] = True

    return targets


def pattern_target(neckline: float, extreme: float, is_bullish: bool) -> float:
    """形态测距：双顶/双底/头肩等。"""
    height = abs(extreme - neckline)
    return neckline + height if is_bullish else neckline - height


def extract_pattern_info(pattern: Dict) -> Optional[Dict]:
    """
    从 technical_analyzer 的形态 dict 中提取颈线价和测距所需信息。
    支持双底（bottom1, bottom2, peak=neckline）和双顶（top1, top2, valley=neckline）。
    """
    ptype = pattern.get("pattern", "")
    if ptype == "双底":
        return {
            "type": "double_bottom",
            "is_bullish": True,
            "neckline": pattern.get("peak"),
            "extreme": min(pattern.get("bottom1", float("inf")), pattern.get("bottom2", float("inf"))),
        }
    elif ptype == "双顶":
        return {
            "type": "double_top",
            "is_bullish": False,
            "neckline": pattern.get("valley"),
            "extreme": max(pattern.get("top1", 0), pattern.get("top2", 0)),
        }
    return None


def weekly_trend_analysis(df_weekly: pd.DataFrame) -> Dict:
    """
    周线趋势分析：ADX方向、+DI/-DI、MA排列、BOLL带宽。
    返回: {direction, adx, adx_score, plus_di, minus_di, is_ranging}
    """
    if df_weekly is None or len(df_weekly) < 14:
        return {"direction": "数据不足", "adx": None, "adx_score": 0, "plus_di": None, "minus_di": None, "is_ranging": True}

    close = df_weekly["close"]
    adx, plus_di, minus_di = _adx(df_weekly)
    latest_adx = float(adx.iloc[-1])
    latest_plus = float(plus_di.iloc[-1])
    latest_minus = float(minus_di.iloc[-1])

    # ADX scoring for confidence
    if latest_adx > 30 and latest_plus > latest_minus:
        adx_score = 10
        direction = "多头"
    elif latest_adx > 25 and latest_plus > latest_minus:
        adx_score = 7
        direction = "多头"
    elif latest_adx > 20 and latest_plus > latest_minus:
        adx_score = 4
        direction = "多头"
    elif latest_adx > 30 and latest_plus < latest_minus:
        adx_score = 10
        direction = "空头"
    elif latest_adx > 25 and latest_plus < latest_minus:
        adx_score = 7
        direction = "空头"
    elif latest_adx > 20 and latest_plus < latest_minus:
        adx_score = 4
        direction = "空头"
    else:
        adx_score = 0
        direction = "震荡"

    # Ranging check: ADX<20 for 4 weeks AND BOLL bandwidth < 8%
    recent_adx = adx.tail(4)
    is_ranging = bool((recent_adx < 20).all())
    if is_ranging:
        boll_up, boll_mid, boll_low = _bollinger(close, period=20)
        bandwidth = (boll_up.iloc[-1] - boll_low.iloc[-1]) / boll_mid.iloc[-1]
        is_ranging = is_ranging and (bandwidth < 0.08)
        if is_ranging:
            direction = "震荡"

    return {
        "direction": direction,
        "adx": round(latest_adx, 1),
        "adx_score": adx_score,
        "plus_di": round(latest_plus, 1),
        "minus_di": round(latest_minus, 1),
        "is_ranging": is_ranging,
    }


def synthesize_targets(
    daily_pattern: Optional[Dict],
    weekly_pattern: Optional[Dict],
    daily_fib: Dict,
    weekly_fib: Dict,
    current_price: float,
    is_bullish: bool,
) -> Dict:
    """
    标准化目标合成表（Spec Section 3）。
    返回: {direction, conservative, base, aggressive, aggressive_raw, is_far_target, method}
    """
    daily_has = daily_pattern is not None
    weekly_has = weekly_pattern is not None

    # Daily pattern target
    daily_pt = None
    if daily_has:
        daily_pt = pattern_target(daily_pattern["neckline"], daily_pattern["extreme"], is_bullish)

    # Weekly pattern target
    weekly_pt = None
    if weekly_has:
        weekly_pt = pattern_target(weekly_pattern["neckline"], weekly_pattern["extreme"], is_bullish)

    if daily_has and weekly_has:
        # 共振：同向有形态
        conservative = min(
            weekly_fib.get("1.0", float("inf")),
            daily_pattern["neckline"],
        )
        base = (daily_pt + weekly_fib.get("1.272", daily_pt)) / 2
        aggressive = weekly_fib.get("1.618", weekly_pt or base)
        method = "A+B交叉验证（日K形态+周K形态共振）"
    elif daily_has or weekly_has:
        # 仅一方有形态
        has_pt = daily_pt if daily_has else weekly_pt
        has_neck = daily_pattern["neckline"] if daily_has else weekly_pattern["neckline"]
        no_fib = weekly_fib if daily_has else daily_fib
        conservative = min(has_neck, no_fib.get("1.0", has_neck))
        base = has_pt
        aggressive = has_pt * 1.3 if has_pt is not None else no_fib.get("1.618", base)
        method = f"{'日K' if daily_has else '周K'}形态主导"
    else:
        # 双方都无形态，只有波段
        fib = weekly_fib if weekly_fib else daily_fib
        conservative = fib.get("1.0", current_price)
        base = fib.get("1.272", current_price * 1.1)
        aggressive = fib.get("1.618", current_price * 1.2)
        method = "纯斐波那契扩展（无形态）"

    # 激进目标上限：不超过当前价+50%（科技股+60%）
    agg_limit = current_price * 1.5
    # NOTE: actual sector detection (tech=60%) happens at caller level
    aggressive_capped = min(aggressive, agg_limit) if aggressive is not None else None
    is_far = aggressive is not None and aggressive > agg_limit

    return {
        "direction": "中线看多" if is_bullish else "中线看空",
        "conservative": round(conservative, 2) if conservative is not None else None,
        "base": round(base, 2) if base is not None else None,
        "aggressive": round(aggressive_capped, 2) if aggressive_capped is not None else None,
        "aggressive_raw": round(aggressive, 2) if aggressive is not None else None,
        "is_far_target": is_far,
        "method": method,
    }
