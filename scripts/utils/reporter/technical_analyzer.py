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
        detect_trend_structure_health, detect_channel_or_box_structure,
        evaluate_bottoming_region,
    )
except ImportError:
    from technical_structure import (
        compute_bias, compute_boll_state, compute_candle_features,
        compute_ma_direction, resample_daily_to_weekly,
        compute_weekly_trend, find_support_resistance,
        evaluate_sr_transformation,
        detect_trend_structure_health, detect_channel_or_box_structure,
        evaluate_bottoming_region,
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
    from .technical_resonance import (
        evaluate_market_resonance,
        load_market_index_map,
        analyze_index_trend,
    )
except ImportError:
    from technical_resonance import (
        evaluate_market_resonance,
        load_market_index_map,
        analyze_index_trend,
    )

try:
    from .price_target import analyze_price_target
except ImportError:
    try:
        from price_target import analyze_price_target
    except ImportError:
        analyze_price_target = None

try:
    from .price_adjustment_validator import validate_adjustment, apply_qfq_adjustment
except ImportError:
    from price_adjustment_validator import validate_adjustment, apply_qfq_adjustment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _min_confidence(current: str, cap: str) -> str:
    """Take the lower of two confidence levels."""
    order = {"低": 0, "中": 1, "高": 2}
    reverse = {0: "低", 1: "中", 2: "高"}
    return reverse[min(order.get(current, 0), order.get(cap, 0))]


def _build_advisors(indicators: dict) -> dict:
    """根据当前指标动态生成 advisor 文案，避免模板残留。"""
    close = indicators.get("close", 0)

    # BIAS — 历史极值优先 + ATR波动率归一化辅助
    bias_5 = indicators.get("bias_5")
    bias_5_extreme_low = indicators.get("bias_5_extreme_low", False)
    bias_5_extreme_high = indicators.get("bias_5_extreme_high", False)
    atr_14 = indicators.get("atr_14")

    if bias_5 is not None:
        direction = "负" if bias_5 < 0 else "正" if bias_5 > 0 else ""
        bias_5_pct = indicators.get("bias_5_pct")

        if bias_5_extreme_low and bias_5 < 0:
            bias_state = "严重负偏离（创120日极值）"
            bias_meaning = "BIAS创近期新低，短线超卖迹象明显，但不单独构成买入信号"
        elif bias_5_extreme_high and bias_5 > 0:
            bias_state = "严重正偏离（创120日极值）"
            bias_meaning = "BIAS创近期新高，短线超买迹象明显，但不单独构成卖出信号"
        elif bias_5_pct is not None and bias_5_pct < 10 and bias_5 < 0:
            bias_state = "严重负偏离（处于10%极端分位）"
            bias_meaning = "BIAS处于近期极端低位，关注技术性修复可能，但不单独构成买入信号"
        elif bias_5_pct is not None and bias_5_pct > 90 and bias_5 > 0:
            bias_state = "严重正偏离（处于90%极端分位）"
            bias_meaning = "BIAS处于近期极端高位，追高风险较大，但不单独构成卖出信号"
        elif close and atr_14 is not None and atr_14 > 0:
            atr_pct = atr_14 / close * 100
            normalized = abs(bias_5) / atr_pct if atr_pct > 0 else 0
            if normalized >= 2.0:
                bias_state = f"{direction}偏离（{normalized:.1f}倍日波幅）"
                bias_meaning = "偏离幅度超过2个日波动，关注技术性修复可能"
            elif normalized >= 1.0:
                bias_state = f"{direction}偏离（轻度）"
                bias_meaning = "偏离在1-2个日波动幅度内，属正常区间"
            else:
                bias_state = "正常"
                bias_meaning = "价格与均线偏离在正常波动范围内"
        elif bias_5 <= -2:
            bias_state = "负偏离"
            bias_meaning = "价格低于均线，提示短线已有回撤"
        elif bias_5 > 3:
            bias_state = "偏高"
            bias_meaning = "价格高于均线，追高性价比下降"
        else:
            bias_state = "正常"
            bias_meaning = "价格与均线偏离适中"
    else:
        bias_state = "正常"
        bias_meaning = "价格与均线偏离适中"

    # BOLL
    boll_lower = indicators.get("boll_lower")
    boll_upper = indicators.get("boll_upper")
    boll_state = indicators.get("boll_state", "正常")

    boll_position = "中轨附近"
    if boll_lower is not None and boll_upper is not None and boll_upper > boll_lower:
        boll_range = boll_upper - boll_lower
        boll_pct = (close - boll_lower) / boll_range
        dist_to_lower_pct = abs(close - boll_lower) / close if close > 0 else 0
        dist_to_upper_pct = abs(close - boll_upper) / close if close > 0 else 0
        if boll_pct > 0.85 or dist_to_upper_pct < 0.06:
            boll_position = "接近上轨"
        elif boll_pct < 0.15 or dist_to_lower_pct < 0.06:
            boll_position = "接近下轨"
    elif boll_lower is not None and close <= boll_lower * 1.05:
        boll_position = "接近下轨"
    elif boll_upper is not None and close >= boll_upper * 0.95:
        boll_position = "接近上轨"

    if boll_state == "开口":
        boll_meaning = f"{boll_position}，波动有所放大（提示短线承压，不单独构成趋势判断）"
    elif boll_state == "缩口":
        boll_meaning = f"{boll_position}，波动收敛（提示等待方向选择）"
    else:
        boll_meaning = f"{boll_position}，波动正常"

    # MACD
    macd = indicators.get("macd", 0)
    macd_hist = indicators.get("macd_hist", 0)
    if macd > 0 and macd_hist < 0:
        macd_state = "多头动能衰减"
    elif macd > 0:
        macd_state = "多头延续"
    elif macd < 0 and macd_hist > 0:
        macd_state = "空头动能衰减"
    else:
        macd_state = "空头延续"

    # RSI
    rsi_value = indicators.get("rsi_14")
    if rsi_value is not None:
        if rsi_value < 30:
            rsi_state = "超卖"
            rsi_meaning = "RSI进入超卖区，存在技术性反弹可能，但不单独构成买入信号"
        elif rsi_value > 70:
            rsi_state = "超买/强势钝化"
            rsi_meaning = "强趋势中不单独构成卖出信号"
        else:
            rsi_state = "正常"
            rsi_meaning = "RSI处于中性区间"
    else:
        rsi_state = "正常"
        rsi_meaning = "RSI处于中性区间"

    return {
        "macd": {
            "state": macd_state,
            "meaning": "仅作趋势确认，不单独构成买卖信号",
        },
        "rsi": {
            "value": rsi_value,
            "state": rsi_state,
            "meaning": rsi_meaning,
        },
        "bias": {
            "state": bias_state,
            "meaning": bias_meaning,
        },
        "boll": {
            "state": boll_state,
            "meaning": boll_meaning,
        },
    }


def _apply_gap_based_qfq_approximation(df: pd.DataFrame, gap_details: list) -> pd.DataFrame:
    """
    基于检测到的价格缺口做近似前复权修复。
    不需要 xdxr 除权记录，直接利用相邻交易日的跳变比例反推。
    多个缺口时累积调整（从最早到最近逐条应用）。
    """
    if not gap_details:
        return df.copy()

    df = df.copy()

    # 确保 date 列为 datetime
    if "date" not in df.columns:
        df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])

    price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
    if not price_cols:
        return df

    # 按缺口日期升序（最早优先），累积调整系数
    gaps = sorted(gap_details, key=lambda g: pd.to_datetime(g["date"]))

    for gap in gaps:
        gap_date = pd.to_datetime(gap["date"])
        prev_close = float(gap["prev_close"])
        close = float(gap["close"])
        if close == 0:
            continue
        ratio = close / prev_close
        mask = df["date"] < gap_date
        for col in price_cols:
            df.loc[mask, col] = df.loc[mask, col] * ratio

    return df


def _fetch_index_kline(symbol: str, days: int = 120) -> pd.DataFrame | None:
    """获取指数日K数据。优先 akshare，失败回退 mootdx，再失败返回 None。"""
    from datetime import datetime, timedelta

    # ---- Priority 1: akshare ----
    try:
        import akshare as ak
        helper = None
        try:
            from ..data_collector import AkshareHelper
            helper = AkshareHelper()
        except Exception:
            try:
                from data_collector import AkshareHelper
                helper = AkshareHelper()
            except Exception:
                pass

        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        if helper is not None:
            df = helper.call(ak.index_zh_a_hist, symbol=symbol, period="daily", start_date=start_date)
        else:
            df = ak.index_zh_a_hist(symbol=symbol, period="daily", start_date=start_date)

        if df is not None and not df.empty:
            column_map = {
                "日期": "date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume",
            }
            df = df.rename(columns=column_map)
            for col in ["open", "high", "low", "close", "volume"]:
                if col not in df.columns:
                    logger.warning(f"指数 {symbol} 返回数据缺少列: {col}")
                    return None
            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)
            return df
    except Exception as e:
        logger.warning(f"akshare 获取指数 {symbol} 失败: {e}")

    # ---- Priority 2: mootdx (TCP 7709，不依赖 HTTP 代理) ----
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market="std")
        # market: 0=深圳, 1=上海; 指数代码 symbol 直接传 6 位
        market_flag = 1 if symbol.startswith(("0", "6")) else 0
        end = datetime.now()
        begin = end - timedelta(days=days * 3)
        df = client.k(
            symbol=symbol,
            market=market_flag,
            begin=begin.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        if df is not None and not df.empty and all(c in df.columns for c in ["open", "high", "low", "close", "volume"]):
            if "date" not in df.columns and df.index.name is not None:
                df = df.reset_index()
            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)
            logger.info(f"mootdx 获取指数 {symbol} 成功，共 {len(df)} 条")
            return df
    except Exception as e:
        logger.warning(f"mootdx 获取指数 {symbol} 失败: {e}")

    return None


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


def analyze(
    df: pd.DataFrame,
    df_weekly: pd.DataFrame | None = None,
    quote: Dict | None = None,
) -> Dict:
    """对日K DataFrame做完整技术分析（中期趋势版）。"""
    if df is None or df.empty or len(df) < 30:
        logger.warning("数据不足30条，无法做完整技术分析")
        return {}

    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            logger.error(f"缺少必要列: {col}")
            return {}

    return advanced_medium_term_resonance(df_daily=df, df_weekly=df_weekly, quote=quote)


def advanced_medium_term_resonance(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame | None = None,
    quote: Dict | None = None,
    previous_state: Dict | None = None,
    config: Dict | None = None,
) -> Dict:
    """中期趋势技术分析主入口。"""
    if config is None:
        try:
            from .technical_config import load_technical_config
            config = load_technical_config()
        except ImportError:
            try:
                from technical_config import load_technical_config
                config = load_technical_config()
            except ImportError:
                config = {"technical": {}}

    # ---- Price adjustment quality gate (pure computation, no network) ----
    input_adjustment = (
        (quote or {}).get("adjustment")
        or (getattr(df_daily, "attrs", None) or {}).get("adjustment")
        or "raw"
    )
    data_source = (
        (quote or {}).get("data_source")
        or (getattr(df_daily, "attrs", None) or {}).get("data_source")
        or "unknown"
    )

    corporate_action_warning = None
    price_adjustment_validation = None
    effective_adjustment = input_adjustment
    adjustment_source = data_source
    price_adjustment_applied = False
    weekly_resampled_from_adjusted_daily = False

    if df_daily is not None and len(df_daily) >= 2:
        raw_validation = validate_adjustment(
            df_daily, adjustment=input_adjustment, quote=quote
        )
        price_adjustment_validation = raw_validation

    has_gap = bool(
        price_adjustment_validation
        and price_adjustment_validation.get("price_gaps", {}).get("possible_exrights_gap")
    )
    requires_qfq = bool(
        price_adjustment_validation
        and price_adjustment_validation.get("requires_qfq")
    )

    # Local repair attempt (pure function, no network)
    if input_adjustment == "raw" and requires_qfq:
        df_repaired = None
        repair_method_used = None
        try:
            # 1. 优先用精确 xdxr 修复（如果有）
            xdxr_df = (quote or {}).get("xdxr_df")
            df_repaired = apply_qfq_adjustment(df_daily, xdxr_df)
            if df_repaired is not None and not df_repaired.empty and len(df_repaired) == len(df_daily):
                # 检查是否真的有变化（xdxr 存在时应该不同）
                if not df_repaired["close"].equals(df_daily["close"]):
                    repair_method_used = "xdxr_qfq"

            # 2. xdxr 无变化或缺失，用缺口比例近似修复
            if repair_method_used is None:
                _pg = price_adjustment_validation.get("price_gaps", {}) if price_adjustment_validation else {}
                gap_details = _pg.get("gap_details", [])
                if gap_details:
                    df_repaired = _apply_gap_based_qfq_approximation(df_daily, gap_details)
                    if not df_repaired["close"].equals(df_daily["close"]):
                        repair_method_used = "gap_ratio_approx"

            if df_repaired is not None and repair_method_used is not None:
                df_daily = df_repaired
                effective_adjustment = "local_qfq_approx"
                adjustment_source = f"local_gap_repair ({repair_method_used})"
                price_adjustment_applied = True

                # CRITICAL: recompute weekly from repaired daily
                df_weekly = resample_daily_to_weekly(df_daily)
                weekly_resampled_from_adjusted_daily = True
                weekly_count = len(df_weekly) if df_weekly is not None else 0

                _pg = price_adjustment_validation.get("price_gaps", {}) if price_adjustment_validation else {}
                corporate_action_warning = {
                    "has_recent_action": True,
                    "message": price_adjustment_validation.get(
                        "warning_message",
                        "raw 价格序列疑似存在除权断点，已使用本地近似前复权修复。",
                    ),
                    "repair_method": repair_method_used,
                    "note": "本地近似复权，非精确前复权",
                    "latest_gap": price_adjustment_validation.get("latest_gap"),
                    "largest_gap": price_adjustment_validation.get("largest_gap"),
                    "gap_date": _pg.get("gap_date"),
                    "gap_pct": _pg.get("max_gap_pct"),
                }
            else:
                effective_adjustment = "raw"
                _pg = price_adjustment_validation.get("price_gaps", {}) if price_adjustment_validation else {}
                corporate_action_warning = {
                    "has_recent_action": True,
                    "message": price_adjustment_validation.get(
                        "warning_message",
                        "raw 价格序列疑似存在除权断点，且未能完成本地修复。",
                    ),
                    "repair_method": None,
                    "note": "未修复",
                    "latest_gap": price_adjustment_validation.get("latest_gap"),
                    "largest_gap": price_adjustment_validation.get("largest_gap"),
                    "gap_date": _pg.get("gap_date"),
                    "gap_pct": _pg.get("max_gap_pct"),
                }
        except Exception as e:
            logger.warning(f"本地近似复权修复失败: {e}")
            effective_adjustment = "raw"
            _pg = price_adjustment_validation.get("price_gaps", {}) if price_adjustment_validation else {}
            corporate_action_warning = {
                "has_recent_action": True,
                "message": price_adjustment_validation.get(
                    "warning_message",
                    "raw 价格序列疑似存在除权断点。",
                ),
                "repair_method": None,
                "note": f"修复失败: {e}",
                "latest_gap": price_adjustment_validation.get("latest_gap"),
                "largest_gap": price_adjustment_validation.get("largest_gap"),
                "gap_date": _pg.get("gap_date"),
                "gap_pct": _pg.get("max_gap_pct"),
            }

    elif input_adjustment == "qfq" and has_gap:
        # qfq data still shows gaps — warn, do not repair again, but cap confidence
        effective_adjustment = "qfq"
        _pg = price_adjustment_validation.get("price_gaps", {}) if price_adjustment_validation else {}
        corporate_action_warning = {
            "has_recent_action": True,
            "message": "当前标记为前复权数据，但仍检测到异常价格断点，建议核查数据源。",
            "repair_method": "qfq",
            "note": "已使用前复权但仍检测到断点",
            "latest_gap": price_adjustment_validation.get("latest_gap"),
            "largest_gap": price_adjustment_validation.get("largest_gap"),
            "gap_date": _pg.get("gap_date"),
            "gap_pct": _pg.get("max_gap_pct"),
        }

    # 1. 数据质量
    daily_count = len(df_daily) if df_daily is not None else 0

    # 2. 自动 resample 周线（如果未传入）
    if df_weekly is None and df_daily is not None and len(df_daily) >= 5:
        df_weekly = resample_daily_to_weekly(df_daily)
    weekly_count = len(df_weekly) if df_weekly is not None else 0
    sufficient = daily_count >= 120 and weekly_count >= 20

    # 3. 计算全部旧指标（复用 Task 2）
    indicators = _compute_base_indicators(df_daily)
    _resonance = {}

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
        df_daily=df_daily,
    )

    # 10. 失效条件
    invalidation = compute_invalidation(
        close=indicators["close"],
        ma20=indicators.get("ma_20"),
        ma60=indicators.get("ma_60"),
        support_zone=sr_result.get("support_zone"),
        config=config,
    )

    # Divergence / strong-signal confidence caps based on adjustment quality
    if divergence and effective_adjustment == "raw" and has_gap:
        divergence["confidence"] = "低可信度"
        divergence["action"] = "未使用前复权数据，此预警仅供参考"
        _resonance["strong_signal_suppressed"] = True
        _resonance["suppressed_signals"] = [
            "divergence_scan",
            "bias_extreme",
            "support_resistance_strength",
            "trend_structure_break",
        ]
    elif divergence and effective_adjustment == "local_qfq_approx":
        divergence["confidence"] = _min_confidence(
            divergence.get("confidence", "中"), "中"
        )
        divergence["action_note"] = "基于本地近似复权序列，可信度最高为中"

    # 11. 分析可信度
    base_confidence = (
        "高" if daily_count >= 250 and weekly_count >= 60
        else "中" if daily_count >= 120 and weekly_count >= 20
        else "低"
    )

    limitations = []
    if daily_count < 120:
        limitations.append("日线数据不足120根")
    if weekly_count < 20:
        limitations.append("周线数据不足20根")
    if not sufficient:
        limitations.append("不满足完整中期趋势分析条件")

    if effective_adjustment == "raw" and has_gap:
        confidence_level = "低"
        limitations.append("未使用前复权数据，技术指标可能失真")
    elif effective_adjustment == "local_qfq_approx":
        confidence_level = _min_confidence(base_confidence, "中")
        limitations.append("本地近似复权，非精确前复权数据，可信度最高为中")
    elif effective_adjustment == "qfq" and has_gap:
        confidence_level = _min_confidence(base_confidence, "中")
        limitations.append("前复权数据仍存在异常断点，需核查数据源")
    else:
        confidence_level = base_confidence

    analysis_confidence = {
        "level": confidence_level,
        "reasons": [
            f"日线{daily_count}根",
            f"周线{weekly_count}根",
            f"复权状态:{effective_adjustment}",
        ],
        "limitations": limitations,
        "data_quality": {
            "input_adjustment": input_adjustment,
            "effective_adjustment": effective_adjustment,
            "adjustment_source": adjustment_source,
        },
    }

    _pg = price_adjustment_validation.get("price_gaps", {}) if price_adjustment_validation else {}
    price_data_lineage = {
        "input_adjustment": input_adjustment,
        "effective_adjustment": effective_adjustment,
        "input_data_source": data_source,
        "adjustment_source": adjustment_source,
        "price_adjustment_applied": price_adjustment_applied,
        "weekly_resampled_from_adjusted_daily": weekly_resampled_from_adjusted_daily,
        "gap_date": _pg.get("gap_date"),
        "gap_pct": _pg.get("max_gap_pct"),
        "price_adjusted_columns": ["open", "high", "low", "close"] if price_adjustment_applied else [],
        "volume_adjusted": False,
        "amount_adjusted": False,
    }

    # 12. 组装 _resonance
    _resonance.update({
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
            "diagnostics": sr_result.get("diagnostics"),
            "medium_term_invalid": invalidation.get("hard_invalid_price"),
        },
        "invalidation": invalidation,
        # 11. 市场共振（占位）
        "market_regime": evaluate_market_resonance(
            stock_trend_state=trend_state,
        ),
        "advisors": _build_advisors(indicators),
        "divergence_scan": divergence,
        "basis_rules": ["周线优先原则", "MA20/MA60 中期结构判定", "有效突破/跌破去抖动规则", "均线为王，谋士辅助"],
        "risk_reminder": "本模块用于日线—周线级别的中期趋势提醒，不用于日内或短线高频择时。",
        "corporate_action_warning": corporate_action_warning,
        "price_adjustment_validation": price_adjustment_validation,
        "price_data_lineage": price_data_lineage,
    })

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

    # Phase 3: 趋势结构健康度
    structure_health = detect_trend_structure_health(df_daily)
    channel_status = detect_channel_or_box_structure(df_daily)
    bottom_signal = evaluate_bottoming_region(
        df_daily, df_weekly, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=_resonance.get("weekly_background"),
    )

    # Phase 3: 分批观察框架
    try:
        from .technical_strategy import evaluate_dart_strategy
    except ImportError:
        from technical_strategy import evaluate_dart_strategy
    dart_strategy = evaluate_dart_strategy(
        bottom_signal, trend_state, indicators, invalidation
    )

    # Phase 3: 市场共振（个股 vs 市场/主题指数）
    stock_code = quote.get("code") if quote else None
    mapping = load_market_index_map(stock_code) if stock_code else {}

    market_index_state = None
    theme_index_state = None
    sector_index_state = None

    market_meta = mapping.get("market")
    if market_meta and market_meta.get("code"):
        df_market = _fetch_index_kline(market_meta["code"], days=daily_count if daily_count else 120)
        if df_market is not None and not df_market.empty:
            market_index_state = analyze_index_trend(df_market).get("trend_state")

    thematic_meta = mapping.get("thematic")
    if thematic_meta and thematic_meta.get("code"):
        df_theme = _fetch_index_kline(thematic_meta["code"], days=daily_count if daily_count else 120)
        if df_theme is not None and not df_theme.empty:
            theme_index_state = analyze_index_trend(df_theme).get("trend_state")

    # 行业指数当前未接入（需要行业 map），保持 None，evaluate_market_resonance 会识别为缺失
    market_resonance = evaluate_market_resonance(
        stock_trend_state=trend_state,
        market_trend_state=market_index_state,
        sector_trend_state=sector_index_state,
        theme_trend_state=theme_index_state,
        mapping_meta=mapping,
    )

    _resonance.update({
        "structure_health": structure_health,
        "channel_status": channel_status,
        "bottom_signal": bottom_signal,
        "dart_strategy": dart_strategy,
        "market_resonance": market_resonance,
    })

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

    # 价格目标分析
    price_target_result = None
    if analyze_price_target is not None and df_weekly is not None:
        try:
            price_target_result = analyze_price_target(
                df_daily=df_daily,
                df_weekly=df_weekly,
                current_price=indicators.get("close", 0),
                daily_indicators=indicators,
            )
        except Exception:
            pass

    return {
        "indicators": indicators,
        "resonance": _resonance,
        "price_target": price_target_result,
        "patterns": [],
        "levels": {
            "support": sr_result["support_zone"]["price"] if sr_result.get("support_zone") else None,
            "resistance": sr_result["resistance_zone"]["price"] if sr_result.get("resistance_zone") else None,
        },
    }
