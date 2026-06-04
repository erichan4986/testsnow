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


def profit_risk_filter(
    conservative_target: float,
    neckline: float,
    daily_atr: float,
    min_ratio: float = 1.5,
) -> Dict:
    """
    盈亏比过滤（Spec Section 4）。
    用预估触发价（颈线 + 0.3×ATR）和预估止损价（颈线 - 1.5×ATR）计算。
    """
    trigger_price = neckline + 0.3 * daily_atr
    stop_price = neckline - 1.5 * daily_atr
    potential_gain = abs(conservative_target - trigger_price)
    initial_risk = abs(trigger_price - stop_price)

    if initial_risk <= 0:
        return {"pass": False, "ratio": 0.0, "trigger_price": trigger_price, "stop_price": stop_price}

    ratio = potential_gain / initial_risk
    return {
        "pass": ratio >= min_ratio,
        "ratio": round(ratio, 2),
        "trigger_price": round(trigger_price, 2),
        "stop_price": round(stop_price, 2),
        "potential_gain": round(potential_gain, 2),
        "initial_risk": round(initial_risk, 2),
    }


def confidence_score(
    resonance: int,
    pattern_quality: int,
    breakout_quality: int,
    weekly_adx: int,
    momentum: int,
    fib_convergence: int,
) -> float:
    """
    六因子加权评分，返回0-10分。
    权重：共振30% + 形态20% + 突破20% + 周线ADX15% + 动量5% + 斐波那契汇聚10%
    """
    score = (
        resonance * 0.30 +
        pattern_quality * 0.20 +
        breakout_quality * 0.20 +
        weekly_adx * 0.15 +
        momentum * 0.05 +
        fib_convergence * 0.10
    )
    return round(score, 1)


def confidence_level(score: float, aggressive_is_far: bool = False) -> str:
    """
    置信度映射。若激进目标超远，上限锁为"中"。
    """
    if aggressive_is_far and score >= 8.0:
        return "中"  # 上限锁定
    if score >= 8.0:
        return "高"
    elif score >= 6.0:
        return "中"
    elif score >= 4.0:
        return "低"
    return "观望"


def estimate_time(
    target_price: float,
    current_price: float,
    daily_atr: float,
    macd_momentum: str = "flat",
    rsi: float = 50.0,
) -> Tuple[float, float]:
    """
    基于ATR估算到达目标价所需时间范围（Spec Section 8）。
    动量修正：MACD柱线斜率和RSI区间微调。
    """
    distance = abs(target_price - current_price)
    if daily_atr <= 0:
        return 0.0, 0.0

    min_days = distance / daily_atr
    base_low, base_high = min_days * 1.5, min_days * 2.0

    multiplier = 1.0
    if macd_momentum == "expanding":
        multiplier *= 0.85
    elif macd_momentum == "contracting":
        multiplier *= 1.25

    if rsi > 65:
        multiplier *= 1.1
    elif rsi < 40:
        multiplier *= 0.9

    return round(base_low * multiplier, 1), round(base_high * multiplier, 1)


def analyze_price_target(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame,
    current_price: float,
    stock_sector: str = "general",
    is_hk: bool = False,
) -> Dict:
    """
    主入口：对日K+周K做完整价格目标分析。

    Args:
        df_daily: 日K DataFrame (open/high/low/close/volume)
        df_weekly: 周K DataFrame (same columns)
        current_price: 最新收盘价
        stock_sector: "tech_chip" 或其他，决定激进目标上限（50% vs 60%）
        is_hk: 是否港股，影响量能阈值

    Returns:
        完整的分析结果字典，可直接用于报告渲染。
    """
    if df_daily is None or len(df_daily) < 30:
        return {"error": "日线数据不足"}
    if df_weekly is None or len(df_weekly) < 10:
        return {"error": "周线数据不足"}

    # --- 1. 周线趋势 ---
    weekly_trend = weekly_trend_analysis(df_weekly)
    if weekly_trend.get("is_ranging"):
        return {"error": "震荡格局，暂不做目标", "weekly_trend": weekly_trend}

    # --- 2. 日线/周线形态识别（复用 technical_analyzer） ---
    try:
        from .technical_analyzer import detect_double_top, detect_double_bottom
    except ImportError:
        from technical_analyzer import detect_double_top, detect_double_bottom

    daily_close = df_daily["close"]
    weekly_close = df_weekly["close"]

    daily_patterns = []
    dp = detect_double_bottom(daily_close)
    if dp:
        daily_patterns.append(dp)
    dt = detect_double_top(daily_close)
    if dt:
        daily_patterns.append(dt)

    weekly_patterns = []
    wp = detect_double_bottom(weekly_close)
    if wp:
        weekly_patterns.append(wp)
    wt = detect_double_top(weekly_close)
    if wt:
        weekly_patterns.append(wt)

    daily_pattern_info = extract_pattern_info(daily_patterns[0]) if daily_patterns else None
    weekly_pattern_info = extract_pattern_info(weekly_patterns[0]) if weekly_patterns else None

    # 判断方向（简化：以第一个形态方向为准，或默认 bullish）
    is_bullish = True
    if daily_pattern_info:
        is_bullish = daily_pattern_info["is_bullish"]
    elif weekly_pattern_info:
        is_bullish = weekly_pattern_info["is_bullish"]

    # --- 3. Zigzag + 斐波那契 ---
    daily_zigzag = zigzag(daily_close, min_pct=0.05)
    weekly_zigzag = zigzag(weekly_close, min_pct=0.10)

    def _bands_from_zigzag(pivots, n=3):
        """从zigzag pivots取最近n个波段。"""
        bands = []
        if len(pivots) < 2:
            return bands
        # 取最近n个完整波段（valley->peak 或 peak->valley）
        for i in range(max(0, len(pivots) - n - 1), len(pivots) - 1):
            p1, p2 = pivots[i], pivots[i + 1]
            low, high = min(p1["price"], p2["price"]), max(p1["price"], p2["price"])
            bands.append({"low": low, "high": high})
        return bands

    daily_bands = _bands_from_zigzag(daily_zigzag, 3)
    weekly_bands = _bands_from_zigzag(weekly_zigzag, 3)

    # 取各档斐波那契目标（用weekly为主）
    weekly_fib = {}
    for level_name, level in [("1.0", 1.0), ("1.272", 1.272), ("1.618", 1.618)]:
        targets = fib_targets_with_convergence(weekly_bands, level=level) if weekly_bands else []
        if targets:
            # 用汇聚区的均值，无汇聚用最后一个
            conv = [t["price"] for t in targets if t["in_convergence"]]
            weekly_fib[level_name] = sum(conv) / len(conv) if conv else targets[-1]["price"]
        else:
            weekly_fib[level_name] = None

    daily_fib = {}
    for level_name, level in [("1.0", 1.0), ("1.272", 1.272), ("1.618", 1.618)]:
        targets = fib_targets_with_convergence(daily_bands, level=level) if daily_bands else []
        if targets:
            conv = [t["price"] for t in targets if t["in_convergence"]]
            daily_fib[level_name] = sum(conv) / len(conv) if conv else targets[-1]["price"]
        else:
            daily_fib[level_name] = None

    # --- 4. 目标合成 ---
    targets = synthesize_targets(
        daily_pattern_info, weekly_pattern_info,
        daily_fib, weekly_fib, current_price, is_bullish,
    )

    # --- 5. 盈亏比过滤 ---
    neckline = None
    if daily_pattern_info:
        neckline = daily_pattern_info["neckline"]
    elif weekly_pattern_info:
        neckline = weekly_pattern_info["neckline"]

    # 无形态时用最近波段低点近似
    if neckline is None and weekly_zigzag:
        last_valley = next((p for p in reversed(weekly_zigzag) if p["type"] == "valley"), None)
        if last_valley:
            neckline = last_valley["price"]

    # 计算日线ATR
    try:
        from .technical_analyzer import _atr
    except ImportError:
        from technical_analyzer import _atr
    daily_atr = float(_atr(df_daily).iloc[-1])

    pr_filter = None
    if neckline and targets.get("conservative"):
        pr_filter = profit_risk_filter(
            conservative_target=targets["conservative"],
            neckline=neckline,
            daily_atr=daily_atr,
        )

    if pr_filter and not pr_filter["pass"]:
        return {
            "error": "关注/不操作",
            "reason": f"形态存在但盈亏比不足（{pr_filter['ratio']}:1），等待更好的入场点",
            "weekly_trend": weekly_trend,
            "targets": targets,
            "profit_risk": pr_filter,
        }

    # --- 6. 动量评估（用于置信度和时间修正） ---
    try:
        from .technical_analyzer import _macd, _rsi, _sma
    except ImportError:
        from technical_analyzer import _macd, _rsi, _sma

    macd_line, macd_sig, macd_hist = _macd(daily_close)
    # 判定前3日柱线趋势（shift(1)取突破前数据）
    hist_prev = macd_hist.shift(1).tail(3)
    hist_diff = hist_prev.diff().dropna()
    macd_momentum = "flat"
    if len(hist_diff) >= 2:
        if all(h > 0 for h in hist_diff):
            macd_momentum = "expanding" if abs(hist_prev.iloc[-1]) > abs(hist_prev.iloc[0]) else "contracting"
        elif all(h < 0 for h in hist_diff):
            macd_momentum = "contracting" if abs(hist_prev.iloc[-1]) < abs(hist_prev.iloc[0]) else "expanding"

    rsi_val = float(_rsi(daily_close, 14).iloc[-1])
    ma5 = _sma(daily_close, 5).iloc[-1]
    ma20 = _sma(daily_close, 20).iloc[-1]
    ma60 = _sma(daily_close, 60).iloc[-1]
    ma_bull = ma5 > ma20 > ma60

    # KDJ 简化判定（从 technical_analyzer 已有数据推算或简化）
    # 这里用价格相对位置近似
    kdj_golden = False  # TODO: 如需精确KDJ，从 technical_analyzer.analyze() 传入

    # --- 7. 置信度评分 ---
    # 共振分
    resonance_score = 10 if (daily_pattern_info and weekly_pattern_info) else (
        6 if (daily_pattern_info or weekly_pattern_info) else 0
    )
    # 形态完整性
    pattern_score = 10  # 简化：有形态=10（2次触及标准）
    # 突破质量（无实际突破K线时用预估）
    breakout_score = 6  # 简化：预估突破=6
    # 周线ADX
    adx_score = weekly_trend.get("adx_score", 0)
    # 斐波那契汇聚
    fib_conv_score = 10 if weekly_fib.get("1.272") and any(
        t.get("in_convergence") for t in fib_targets_with_convergence(weekly_bands, 1.272)
    ) else 0

    conf_score = confidence_score(
        resonance=resonance_score,
        pattern_quality=pattern_score,
        breakout_quality=breakout_score,
        weekly_adx=adx_score,
        momentum=6,  # simplified; detailed momentum scoring done at caller level
        fib_convergence=fib_conv_score,
    )
    conf_level = confidence_level(conf_score, aggressive_is_far=targets.get("is_far_target", False))

    # --- 8. 时间预期 ---
    time_conservative = estimate_time(
        targets["conservative"], current_price, daily_atr, macd_momentum, rsi_val,
    ) if targets.get("conservative") else (0, 0)
    time_base = estimate_time(
        targets["base"], current_price, daily_atr, macd_momentum, rsi_val,
    ) if targets.get("base") else (0, 0)
    time_aggressive = estimate_time(
        targets["aggressive_raw"] or targets.get("aggressive", current_price),
        current_price, daily_atr, macd_momentum, rsi_val,
    ) if targets.get("aggressive") else (0, 0)

    # --- 9. 止损/失效条件文本 ---
    stop_loss_text = ""
    if neckline:
        entry_stop = max(pr_filter["stop_price"], neckline - 1.5 * daily_atr) if pr_filter else neckline - 1.5 * daily_atr
        stop_loss_text = f"初始止损{entry_stop:.1f}（预估）/ 跟踪止损：最高收盘价回撤2×ATR"
    else:
        stop_loss_text = f"跟踪止损：最高收盘价回撤{2*daily_atr:.1f}（{2*daily_atr/current_price*100:.1f}%）"

    return {
        "direction": targets["direction"],
        "confidence": conf_level,
        "confidence_score": conf_score,
        "profit_risk_ratio": pr_filter["ratio"] if pr_filter else None,
        "conservative": targets["conservative"],
        "base": targets["base"],
        "aggressive": targets["aggressive"],
        "aggressive_raw": targets.get("aggressive_raw"),
        "is_far_target": targets.get("is_far_target", False),
        "method": targets["method"],
        "trigger_conditions": {
            "price": f"收盘价站稳{neckline:.1f}+实体完全在颈线上方+实体≥0.3×ATR" if neckline else "等待形态确认",
            "trend": f"周线ADX>{weekly_trend['adx']}且+DI>-DI" if weekly_trend.get("adx") else "",
            "volume": "量比>1.5且金额≥1亿" if not is_hk else "量比>1.3且金额≥3000万港币",
            "momentum": "MACD非死叉 + RSI健康区间",  # simplified for now
        },
        "stop_loss": stop_loss_text,
        "failure_conditions": [
            f"周线ADX从峰值回落>10且+DI下穿-DI",
            "创20日新高但OBV未同步创新高",
            "连续5日低于20MA均量且跌破10日线",
        ],
        "time_estimate": {
            "conservative": f"约{time_conservative[0]:.0f}-{time_conservative[1]:.0f}个交易日",
            "base": f"约{time_base[0]:.0f}-{time_base[1]:.0f}个交易日",
            "aggressive": f"约{time_aggressive[0]:.0f}-{time_aggressive[1]:.0f}个交易日",
        },
        "momentum_status": f"MACD {macd_momentum} | RSI {rsi_val:.0f} | {'MA多头排列' if ma_bull else 'MA非多头'}",
        "weekly_trend": weekly_trend,
        "daily_pattern": daily_patterns[0] if daily_patterns else None,
        "weekly_pattern": weekly_patterns[0] if weekly_patterns else None,
    }
