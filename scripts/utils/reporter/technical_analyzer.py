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

try:
    from .technical_structure import (
        compute_bias, compute_boll_state, compute_candle_features,
        compute_ma_direction, resample_daily_to_weekly,
        compute_weekly_trend, find_support_resistance,
        evaluate_sr_transformation,
    )
except ImportError:
    from technical_structure import (
        compute_bias, compute_boll_state, compute_candle_features,
        compute_ma_direction, resample_daily_to_weekly,
        compute_weekly_trend, find_support_resistance,
        evaluate_sr_transformation,
    )

try:
    from .technical_state_machine import (
        classify_trend_state, apply_previous_state,
        compute_trend_health, compute_invalidation,
        evaluate_bias_extreme, evaluate_sell_three_factors,
        detect_false_rebound, detect_false_breakout,
    )
except ImportError:
    from technical_state_machine import (
        classify_trend_state, apply_previous_state,
        compute_trend_health, compute_invalidation,
        evaluate_bias_extreme, evaluate_sell_three_factors,
        detect_false_rebound, detect_false_breakout,
    )

try:
    from .technical_patterns import (
        detect_double_top, detect_double_bottom,
        detect_boll_overextension, evaluate_candle_at_key_levels,
        multi_indicator_resonance,
    )
except ImportError:
    from technical_patterns import (
        detect_double_top, detect_double_bottom,
        detect_boll_overextension, evaluate_candle_at_key_levels,
        multi_indicator_resonance,
    )

try:
    from .technical_resonance import evaluate_market_resonance
except ImportError:
    from technical_resonance import evaluate_market_resonance


# ---------------------------------------------------------------------------
# Main entry points
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

    bias_extreme = evaluate_bias_extreme(
        bias_5=indicators.get("bias_5"),
        bias_5_extreme_high=indicators.get("bias_5_extreme_high", False),
        bias_5_extreme_low=indicators.get("bias_5_extreme_low", False),
        bias_10=indicators.get("bias_10"),
        bias_10_extreme_high=indicators.get("bias_10_extreme_high", False),
        bias_10_extreme_low=indicators.get("bias_10_extreme_low", False),
    )
    if bias_extreme:
        _resonance["bias_extreme"] = bias_extreme

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

    # 支撑阻力转化
    sr_transform = evaluate_sr_transformation(
        close=indicators["close"],
        support_zone=sr_result.get("support_zone"),
        resistance_zone=sr_result.get("resistance_zone"),
        recent_closes=df_daily["close"].astype(float).tail(5).tolist(),
    )
    if sr_transform:
        _resonance["sr_transformation"] = sr_transform

    # 6.5 K线形态信号（只在关键位置）
    atr_series = _atr(df_daily)
    candle_features = compute_candle_features(df_daily, atr_series)
    candle_signal = evaluate_candle_at_key_levels(
        candle=candle_features,
        key_levels=sr_result,
        close=indicators["close"],
        boll_state=indicators.get("boll_state", "正常"),
        boll_lower=indicators.get("boll_lower"),
        boll_upper=indicators.get("boll_upper"),
    )
    if candle_signal:
        daily_structure["candle_signal"] = candle_signal

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
        # 11. 市场共振（占位）
        "market_regime": evaluate_market_resonance(
            stock_trend_state=trend_state,
        ),
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
        "basis_rules": ["周线优先原则", "MA20/MA60 中期结构判定", "有效突破/跌破去抖动规则", "均线为王，谋士辅助"],
        "risk_reminder": "本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。",
    }

    # 卖出三要素评估
    bias_extreme_high = (
        bias_extreme is not None
        and bias_extreme.get("direction") == "high"
    )

    sell_assessment = evaluate_sell_three_factors(
        valuation_overpriced=None,
        ma_breakdown=trend_state.get("stage") == "破坏期",
        bias_extreme_high=bias_extreme_high,
        rsi_value=indicators.get("rsi_14"),
    )
    _resonance["sell_assessment"] = sell_assessment

    # 假反弹检测
    volume_ma20 = float(df_daily["volume"].tail(20).mean())
    false_rebound = detect_false_rebound(
        df_recent=df_daily.tail(10),
        boll_state=indicators.get("boll_state", "正常"),
        volume_ma20=volume_ma20,
    )
    if false_rebound:
        _resonance["false_rebound"] = false_rebound

    # 假突破检测
    if len(df_daily) >= 2:
        prev = df_daily.iloc[-2]
        cur = df_daily.iloc[-1]
        ma5_series = _sma(df_daily["close"].astype(float), 5)
        false_breakout = detect_false_breakout(
            close=float(cur["close"]),
            ma5=float(ma5_series.iloc[-1]),
            prev_close=float(prev["close"]),
            prev_ma5=float(ma5_series.iloc[-2]),
        )
        if false_breakout:
            _resonance["false_breakout"] = false_breakout

    return {
        "indicators": indicators,
        "resonance": _resonance,
        "patterns": [],
        "levels": {
            "support": sr_result["support_zone"]["price"] if sr_result.get("support_zone") else None,
            "resistance": sr_result["resistance_zone"]["price"] if sr_result.get("resistance_zone") else None,
        },
    }
