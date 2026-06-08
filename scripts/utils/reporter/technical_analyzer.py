"""技术分析引擎 — 纯 pandas 实现，无外部依赖。

支持：趋势/动量/波动/量价指标 + 形态识别 + 多指标共振。
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. 基础指标计算
# ---------------------------------------------------------------------------

def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=1).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def _adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """返回 (adx, plus_di, minus_di)"""
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()

    plus_di = 100 * (plus_dm.rolling(window=period, min_periods=1).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period, min_periods=1).mean() / atr)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fillna(0)
    adx = dx.rolling(window=period, min_periods=1).mean()
    return adx, plus_di, minus_di


def _cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(window=period, min_periods=1).mean()
    mad = tp.rolling(window=period, min_periods=1).apply(lambda x: np.abs(x - x.mean()).mean(), raw=False)
    return (tp - sma) / (0.015 * mad)


def _williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    highest_high = df["high"].rolling(window=period, min_periods=1).max()
    lowest_low = df["low"].rolling(window=period, min_periods=1).min()
    return -100 * (highest_high - df["close"]) / (highest_high - lowest_low)


def _stoch_rsi(close: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[pd.Series, pd.Series]:
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    stoch = (rsi - rsi.rolling(window=period, min_periods=1).min()) / (
        rsi.rolling(window=period, min_periods=1).max() - rsi.rolling(window=period, min_periods=1).min()
    )
    stoch = stoch.fillna(0)
    k = _sma(stoch, smooth_k)
    d = _sma(k, smooth_d)
    return k, d


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


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    obv = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i - 1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=close.index)


def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bollinger(close: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    mid = _sma(close, period)
    std = close.rolling(window=period, min_periods=1).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


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


def analyze(df: pd.DataFrame) -> Dict:
    """
    对日 K DataFrame 做完整技术分析。

    Args:
        df: DataFrame with columns [open, high, low, close, volume, amount(optional)]

    Returns:
        {
            "indicators": {最新指标值},
            "resonance": {多指标共振判断},
            "patterns": [检测到的形态],
            "levels": {"support": ..., "resistance": ...},
        }
    """
    if df is None or df.empty or len(df) < 30:
        logger.warning("数据不足 30 条，无法做完整技术分析")
        return {}

    # 标准化列名
    df = df.copy()
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            logger.error(f"缺少必要列: {col}")
            return {}

    close = df["close"]

    # --- 计算指标 ---
    indicators = _compute_base_indicators(df)

    # --- 形态识别 ---
    patterns = []
    dtop = detect_double_top(close)
    if dtop:
        patterns.append(dtop)
    dbot = detect_double_bottom(close)
    if dbot:
        patterns.append(dbot)

    # --- 支撑/阻力 ---
    support, resistance = _is_support_resistance(close)

    # --- 共振分析 ---
    resonance = multi_indicator_resonance(indicators)

    return {
        "indicators": indicators,
        "resonance": resonance,
        "patterns": patterns,
        "levels": {
            "support": round(support, 2) if support else None,
            "resistance": round(resistance, 2) if resistance else None,
        },
    }


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))
