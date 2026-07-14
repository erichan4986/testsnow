"""趋势状态机模块 — 状态判定、健康度、技术判断和失效条件。"""

from typing import Any, Dict

import pandas as pd

__all__ = [
    "classify_trend_state", "apply_previous_state",
    "compute_trend_health", "compute_invalidation",
    "evaluate_bias_extreme", "detect_false_rebound",
    "detect_false_breakout", "evaluate_sell_three_factors",
    "build_technical_judgment", "ensure_technical_judgment", "is_valid_technical_judgment",
    "resolve_target_display_mode",
]


def _score_volume_confirmation(df_daily: pd.DataFrame | None) -> tuple[int, str]:
    """基于实际成交量动态评分。

    规则：
    - 最新成交量 >= 1.5×MA20：放量确认，9-10分
    - 1.2×MA20 <= 最新 < 1.5×MA20：温和放量，7-8分
    - 0.8×MA20 <= 最新 < 1.2×MA20：正常，5-6分
    - 最新 < 0.8×MA20：缩量，3-4分
    - 近5日量能递增：+1分
    - 近5日量能递减：-1分
    """
    if df_daily is None or df_daily.empty or "volume" not in df_daily.columns:
        return 8, "成交额温和（数据不足，默认评分）"

    try:
        vol = df_daily["volume"].astype(float)
        if len(vol) < 20:
            return 8, "成交额温和（数据不足，默认评分）"

        latest_vol = float(vol.iloc[-1])
        ma20_vol = float(vol.tail(20).mean())
        if ma20_vol <= 0:
            return 8, "成交额温和（数据不足，默认评分）"

        ratio = latest_vol / ma20_vol

        # 基础分
        if ratio >= 1.5:
            base_score = 9
            evidence = f"放量（量能比{ratio:.1f}×MA20）"
        elif ratio >= 1.2:
            base_score = 7
            evidence = f"温和放量（量能比{ratio:.1f}×MA20）"
        elif ratio >= 0.8:
            base_score = 6
            evidence = f"量能正常（量能比{ratio:.1f}×MA20）"
        else:
            base_score = 4
            evidence = f"缩量（量能比{ratio:.1f}×MA20）"

        # 趋势修正（近5日）
        if len(vol) >= 6:
            recent = vol.tail(5).tolist()
            if all(recent[i] >= recent[i - 1] for i in range(1, 5)):
                base_score = min(10, base_score + 1)
                evidence += "，近5日递增"
            elif all(recent[i] <= recent[i - 1] for i in range(1, 5)):
                base_score = max(0, base_score - 1)
                evidence += "，近5日递减"

        return base_score, evidence
    except Exception:
        return 8, "成交额温和（计算异常，默认评分）"


def evaluate_bias_extreme(
    bias_5: float | None,
    bias_5_extreme_high: bool,
    bias_5_extreme_low: bool,
    bias_10: float | None = None,
    bias_10_extreme_high: bool = False,
    bias_10_extreme_low: bool = False,
) -> dict | None:
    """评估 BIAS 是否处于极端状态。

    必须返回 direction: "high" | "low"，供卖出三要素使用。
    """
    if bias_5_extreme_high or bias_10_extreme_high:
        return {
            "warning": "BIAS 创近120日新高，极端超买",
            "level": "严重",
            "direction": "high",
            "affects": "卖出三要素之强弱偏离度",
            "evidence": {
                "bias_5": bias_5,
                "bias_10": bias_10,
                "threshold_desc": "120日回看期内最高值",
                "window": "120日",
            },
        }
    if bias_5_extreme_low or bias_10_extreme_low:
        return {
            "warning": "BIAS 创近120日新低，极端超卖",
            "level": "严重",
            "direction": "low",
            "affects": "买入参考，不构成买入信号",
            "evidence": {
                "bias_5": bias_5,
                "bias_10": bias_10,
                "threshold_desc": "120日回看期内最低值",
                "window": "120日",
            },
        }
    return None


def detect_false_rebound(
    df_recent: pd.DataFrame,
    boll_state: str,
    volume_ma20: float,
) -> dict | None:
    """检测假反弹（冷不丁单根阳线）。

    规则：
    1. 最新一根K线 close > open（阳线）
    2. 前一根K线 close <= open（非阳线）
    3. BOLL 状态不是 "开口"
    4. 最新成交量 < volume_ma20 * 1.2（未放量）
    """
    if df_recent is None or len(df_recent) < 6:
        return None

    latest = df_recent.iloc[-1]
    prev = df_recent.iloc[-2]

    # 1. 最新阳线
    if not (latest["close"] > latest["open"]):
        return None

    # 2. 前一日非阳线
    if not (prev["close"] <= prev["open"]):
        return None

    # 3. BOLL 未开口
    if boll_state == "开口":
        return None

    # 4. 未放量
    latest_volume = float(latest["volume"])
    if latest_volume >= volume_ma20 * 1.2:
        return None

    return {
        "type": "假反弹预警",
        "confidence": "中",
        "signal": "疑似假反弹，观望为宜",
        "reason": "单根阳线+BOLL未张口+未放量",
    }


def detect_false_breakout(
    close: float,
    ma5: float,
    prev_close: float,
    prev_ma5: float,
) -> dict | None:
    """检测假突破：前一日站上 MA5，今日跌破 MA5。"""
    if prev_close > prev_ma5 and close < ma5:
        return {
            "type": "假突破预警",
            "confidence": "中",
            "signal": "突破MA5后回落，停止加仓",
            "reason": "前一日站上MA5，今日跌破MA5",
        }
    return None


def evaluate_sell_three_factors(
    valuation_overpriced: bool | None,
    ma_breakdown: bool,
    bias_extreme_high: bool,
    rsi_value: float | None = None,
) -> dict:
    """
    卖出三要素决策框架。
    三要素：估值定价、均线信号、强弱偏离度。
    RSI 严重超买并入"强弱偏离度"，不得成为第四个要素。
    至少满足两条才给出明确卖出建议。
    """
    factors = []

    if valuation_overpriced:
        factors.append("估值定价：极度高估")

    if ma_breakdown:
        factors.append("均线信号：已触发破位")

    deviation_extreme = bias_extreme_high or (rsi_value is not None and rsi_value > 80)
    if deviation_extreme:
        if bias_extreme_high and rsi_value is not None and rsi_value > 80:
            factors.append(f"强弱偏离度：BIAS高位极端且RSI严重超买（RSI={rsi_value:.1f}）")
        elif bias_extreme_high:
            factors.append("强弱偏离度：BIAS创近120日高位极值")
        else:
            factors.append(f"强弱偏离度：RSI严重超买（RSI={rsi_value:.1f}）")

    met = len(factors)

    if met >= 2:
        recommendation = "建议卖出"
    elif met == 1:
        recommendation = "部分信号出现，建议减仓观察"
    else:
        recommendation = "观望，不满足卖出条件"

    return {
        "factors": factors,
        "met_count": met,
        "recommendation": recommendation,
        "rule": "卖出三要素：估值定价、均线信号、强弱偏离度；至少满足两条才给出明确卖出建议",
    }


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

    # 2. 转弱期 / 震荡转弱观察
    if price_vs_ma20 == "跌破" and (ma20_dir == "走平" or ma20_dir == "向下"):
        # 周线仍为震荡且 MA60 仍向上，不宜过早输出完整“下降趋势”
        if weekly_trend == "震荡" and ma60_dir == "向上":
            return {
                "primary_state": "震荡转弱",
                "stage": "临界破坏观察期",
                "action_hint": "降低预期",
                "state_changed": None,
                "previous_state": None,
                "summary": "日线跌破MA20，中期结构转弱，需观察能否收回MA60。",
            }
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

    # 7. 高位回撤后的震荡转弱观察（MA60 仍向上但被短期跌破 MA20）
    if (
        ma20_dir == "向上"
        and ma60_dir == "向上"
        and price_vs_ma20 == "跌破"
        and price_vs_ma60 == "站上"
    ):
        return {
            "primary_state": "震荡转弱",
            "stage": "回撤观察期",
            "action_hint": "降低预期",
            "state_changed": None,
            "previous_state": None,
            "summary": "高位回撤至MA20下方，但MA60仍向上，中期结构未破坏，观察能否重新站上MA20。",
        }

    # 8. 盘整期
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
    df_daily: pd.DataFrame | None = None,
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
    price_vs_ma60 = daily_structure.get("price_vs_ma60", "未知")
    if ma20_dir == "向上" and price_vs_ma20 == "站上":
        components["daily_ma_alignment"] = {"score": 20, "max": 25, "evidence": "MA20向上，价格站上"}
        score += 20
    elif ma20_dir == "向上" and price_vs_ma20 == "跌破":
        # MA20 仍向上但价格跌破，属于短线转弱，不要写成 MA20向下
        components["daily_ma_alignment"] = {"score": 12, "max": 25, "evidence": "MA20向上，但价格跌破MA20，短线转弱"}
        score += 12
    elif ma20_dir == "走平":
        if price_vs_ma20 == "站上":
            components["daily_ma_alignment"] = {"score": 12, "max": 25, "evidence": "MA20走平，价格站上"}
            score += 12
        else:
            components["daily_ma_alignment"] = {"score": 8, "max": 25, "evidence": "MA20走平，价格跌破"}
            score += 8
    elif ma20_dir == "向下":
        components["daily_ma_alignment"] = {"score": 5, "max": 25, "evidence": "MA20向下"}
        score += 5
    else:
        components["daily_ma_alignment"] = {"score": 5, "max": 25, "evidence": "日线MA结构偏弱"}
        score += 5

    structure_type = daily_structure.get("structure_type", "无明显结构")
    if structure_type in ["上升通道", "平台整理"]:
        components["price_structure"] = {"score": 12, "max": 15, "evidence": structure_type}
        score += 12
    else:
        components["price_structure"] = {"score": 5, "max": 15, "evidence": structure_type}
        score += 5

    # 动态成交量确认评分
    vol_score, vol_evidence = _score_volume_confirmation(df_daily)
    components["volume_confirmation"] = {"score": vol_score, "max": 10, "evidence": vol_evidence}
    score += vol_score

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

    # 当中期均线仍向上且价格在MA60上方时，健康度评级不应低于"转弱观察"
    if ma60_dir == "向上" and price_vs_ma60 == "站上" and score < 50:
        score = min(50, score + 15)

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

    # 评级冲突修正：MA60仍向上且价格在MA60上方时，不使用"破坏风险高"
    if ma60_dir == "向上" and price_vs_ma60 == "站上" and grade == "破坏风险高":
        grade = "转弱观察"

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
    hard_source = "MA60"
    distance_pct = None
    distance_str = None
    if hard_price and hard_price > 0:
        distance_pct = round((close - hard_price) / hard_price * 100, 2)
        distance_str = f"{distance_pct:.1f}%"
    elif support_zone and support_zone.get("zone_low"):
        hard_price = support_zone["zone_low"]
        hard_source = "支撑区"
        distance_pct = round((close - hard_price) / close * 100, 2)
        distance_str = f"{distance_pct:.1f}%"

    is_invalidated = False
    status = "safe"
    message = ""
    if hard_price is not None:
        if close < hard_price:
            is_invalidated = True
            status = "broken"
            message = f"当前收盘价已跌破{hard_source}（{hard_price:.2f}），中期结构破坏确认。"
        elif close < hard_price * 1.03:
            status = "near_above"
            message = f"当前收盘价位于{hard_source}（{hard_price:.2f}）上方但安全垫不足，需观察能否保持。"
        else:
            message = f"当前收盘价位于{hard_source}（{hard_price:.2f}）上方，距离约 {distance_str}。"

    return {
        "soft_warning": soft,
        "hard_invalid": hard,
        "hard_invalid_price": hard_price,
        "hard_invalid_source": hard_source,
        "distance_pct": distance_pct,
        "is_invalidated": is_invalidated,
        "status": status,
        "message": message,
        "structure_break": struct_break,
        "current_distance_to_invalid": distance_str or "未知",
    }


_CONFIDENCE_ORDER = {"unavailable": 0, "observation": 1, "low": 2, "medium": 3, "high": 4}
_TARGET_STATUSES = {"ready", "observe", "blocked", "invalid", "unavailable"}
_EXECUTION_STATES = {"triggered", "pending", "blocked", "invalid", "observe", "unavailable"}
_ACTION_STATES = {"follow", "wait_for_entry", "wait_for_confirmation", "risk_control", "unavailable"}
_CHECK_STATES = {"pass", "pending", "fail", "unknown"}
_TREND_LABELS = {
    "strong_up": "强势上行", "weak_up": "弱势上行", "transition": "趋势转折",
    "range": "震荡观察", "down": "下降趋势", "invalid": "趋势失效", "unknown": "未知",
}
_CONFIDENCE_LABELS = {
    "high": "高", "medium": "中", "low": "低", "observation": "观察位", "unavailable": "不可用",
}


def _min_confidence(left: str, right: str) -> str:
    if left not in _CONFIDENCE_ORDER or right not in _CONFIDENCE_ORDER or "unavailable" in (left, right):
        return "unavailable"
    return min((left, right), key=lambda value: _CONFIDENCE_ORDER[value])


def resolve_target_display_mode(
    direction: str,
    effective_confidence: str,
    execution_state: str,
) -> str:
    """Resolve the only target display mode used by report consumers."""
    if execution_state in {"blocked", "invalid"}:
        return "blocked"
    if execution_state == "unavailable" or effective_confidence == "unavailable":
        return "unavailable"
    if direction == "bearish":
        return "levels_only"
    if effective_confidence == "observation":
        return "levels_only" if execution_state in {"observe", "pending"} else "unavailable"
    if direction != "bullish":
        return "unavailable"
    if effective_confidence == "high" and execution_state == "triggered":
        return "full_targets"
    if effective_confidence in {"high", "medium"} and execution_state == "pending":
        return "core_targets" if effective_confidence == "high" else "conditional_range"
    if effective_confidence == "medium" and execution_state == "triggered":
        return "core_targets"
    if effective_confidence == "low" and execution_state == "pending":
        return "conditional_range"
    return "unavailable"


def _trend_judgment(resonance: Dict) -> Dict:
    trend_state = resonance.get("trend_state") or {}
    health = resonance.get("trend_health") or {}
    invalidation = resonance.get("invalidation") or {}
    if invalidation.get("is_invalidated") or invalidation.get("status") == "broken":
        state = "invalid"
    elif trend_state.get("primary_state") == "下降趋势" or trend_state.get("stage") == "破坏期":
        state = "down"
    elif trend_state.get("primary_state") == "震荡转弱":
        state = "transition"
    elif trend_state.get("primary_state") == "上升趋势":
        score = health.get("score")
        if isinstance(score, (int, float)) and score >= 65:
            state = "strong_up"
        elif isinstance(score, (int, float)) and score >= 50:
            state = "weak_up"
        else:
            state = "transition"
    else:
        state = "unknown"
    return {
        "state": state,
        "label": _TREND_LABELS.get(state, "未知"),
        "stage": trend_state.get("stage", ""),
        "health_score": health.get("score"),
        "health_grade": health.get("grade", ""),
        "invalidation_state": invalidation.get("status", "unknown"),
        "summary": trend_state.get("summary", _TREND_LABELS.get(state, "未知")),
    }


def _quality_cap(resonance: Dict, indicators: Dict) -> str:
    analysis = resonance.get("analysis_confidence") or indicators.get("analysis_confidence") or {}
    if isinstance(analysis, str):
        level = analysis
        data_quality = {}
    else:
        level = analysis.get("level", "")
        data_quality = analysis.get("data_quality", {}) or {}
    sample_cap = {"高": "high", "中": "medium", "低": "low"}.get(level, "unavailable")
    lineage = resonance.get("price_data_lineage") or {}
    lineage = lineage or data_quality
    effective_adjustment = lineage.get("effective_adjustment")
    validation = resonance.get("price_adjustment_validation")
    requires_qfq = bool((validation or {}).get("requires_qfq"))
    has_gap = bool((validation or {}).get("price_gaps", {}).get("possible_exrights_gap"))
    applied = lineage.get("price_adjustment_applied")
    if requires_qfq and not applied:
        adjustment_cap = "unavailable"
    elif effective_adjustment == "local_qfq_approx" or (effective_adjustment == "qfq" and has_gap):
        adjustment_cap = "low"
    elif effective_adjustment in {"qfq", "hfq"} or (effective_adjustment == "raw" and not requires_qfq and not has_gap):
        adjustment_cap = "high"
    else:
        adjustment_cap = "unavailable"
    return _min_confidence(sample_cap, adjustment_cap)


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _daily_series(daily_data: Any, field: str) -> pd.Series:
    values = daily_data.get(field) if isinstance(daily_data, (pd.DataFrame, dict)) else None
    return pd.to_numeric(pd.Series(values), errors="coerce") if values is not None else pd.Series(dtype=float)


def _check(status: str, detail: str, **values: object) -> Dict:
    return {"status": status, "detail": detail, **values}


def _trigger_checks(
    resonance: Dict,
    target: Dict,
    indicators: Dict,
    daily_data: Any,
    direction: str,
    market: str | None,
) -> Dict:
    supplied = resonance.get("trigger_checks") or target.get("trigger_checks") or {}
    supplied = {name: dict(value) for name, value in supplied.items() if isinstance(value, dict)}
    required = ("price", "trend", "volume", "momentum")
    if all(supplied.get(name, {}).get("status") in _CHECK_STATES for name in required):
        checks = {name: supplied[name] for name in required}
    else:
        risk = target.get("profit_risk") if isinstance(target.get("profit_risk"), dict) else {}
        trigger = _number(risk.get("trigger_price"))
        neckline = _number(risk.get("neckline"))
        atr = _number(risk.get("daily_atr"))
        opening = _daily_series(daily_data, "open")
        closing = _daily_series(daily_data, "close")
        if None in {trigger, neckline, atr} or opening.empty or closing.empty:
            price = _check("unknown", "缺少触发价、颈线或日线数据")
        else:
            open_price, close_price = _number(opening.iloc[-1]), _number(closing.iloc[-1])
            if open_price is None or close_price is None:
                price = _check("unknown", "最新日线价格不可用")
            elif direction not in {"bullish", "bearish"}:
                price = _check("unknown", "目标方向不可用")
            else:
                body_ok = abs(close_price - open_price) >= 0.3 * atr
                passed = (
                    close_price >= trigger and min(open_price, close_price) > neckline
                    if direction == "bullish"
                    else close_price <= trigger and max(open_price, close_price) < neckline
                ) and body_ok
                price = _check("pass" if passed else "pending", "已满足突破条件" if passed else "尚未满足突破条件")

        weekly = resonance.get("weekly_trend") or target.get("weekly_trend") or {}
        adx, plus_di, minus_di = (_number(weekly.get(name)) for name in ("adx", "plus_di", "minus_di"))
        if None in {adx, plus_di, minus_di}:
            trend = _check("unknown", "ADX>=25")
        else:
            aligned = plus_di > minus_di if direction == "bullish" else minus_di > plus_di if direction == "bearish" else False
            trend = _check("pass" if adx >= 25 and aligned else "pending", "ADX>=25", adx=adx)

        volumes = _daily_series(daily_data, "volume").dropna()
        if len(volumes) < 21:
            volume = _check("unknown", "成交量历史不足")
        else:
            average, latest = _number(volumes.iloc[-21:-1].mean()), _number(volumes.iloc[-1])
            if average is None or latest is None or average <= 0:
                volume = _check("unknown", "成交量不可用")
            else:
                is_hk = market == "hk"
                ratio, ratio_threshold = latest / average, 1.3 if is_hk else 1.5
                amounts = _daily_series(daily_data, "amount").dropna()
                if amounts.empty:
                    volume = _check("pass" if ratio >= ratio_threshold else "pending", "成交额未核验", volume_ratio=ratio)
                else:
                    amount_threshold = 30_000_000 if is_hk else 100_000_000
                    volume = _check(
                        "pass" if ratio >= ratio_threshold and amounts.iloc[-1] >= amount_threshold else "pending",
                        f"量比>={ratio_threshold}", volume_ratio=ratio, amount=float(amounts.iloc[-1]),
                    )

        macd, signal = _number(indicators.get("macd")), _number(indicators.get("macd_signal", indicators.get("macds")))
        rsi = _number(indicators.get("rsi_14"))
        if None in {macd, signal, rsi}:
            momentum = _check("unknown", "缺少MACD或RSI")
        elif direction == "bullish":
            passed = macd >= signal and 40 <= rsi <= 70
            momentum = _check("pass" if passed else "pending", "MACD与RSI满足方向条件" if passed else "MACD或RSI尚未满足方向条件")
        elif direction == "bearish":
            passed = macd <= signal and 30 <= rsi <= 60
            momentum = _check("pass" if passed else "pending", "MACD与RSI满足方向条件" if passed else "MACD或RSI尚未满足方向条件")
        else:
            momentum = _check("unknown", "目标方向不可用")
        checks = {"price": price, "trend": trend, "volume": volume, "momentum": momentum}
    for name in required:
        checks.setdefault(name, _check("unknown", "数据不足"))
    if target.get("structure_confidence") == "low":
        checks["price"] = _check("unknown", "结构精度不足，不判定精确突破位")
    if not checks["trend"].get("detail"):
        checks["trend"]["detail"] = "ADX>=25"
    if checks["volume"].get("amount_missing"):
        checks["volume"]["detail"] = "成交额未核验"
    return checks


def _execution_state(target: Dict, checks: Dict, trend: Dict) -> str:
    status = target.get("producer_status", "unavailable")
    if status == "invalid" or trend["state"] == "invalid":
        return "invalid"
    if status in {"blocked", "unavailable"}:
        return status
    if status == "observe" or target.get("effective_confidence") == "observation":
        return "observe"
    states = [checks.get(name, {}).get("status") for name in ("price", "trend", "volume", "momentum")]
    if any(value == "unknown" for value in states):
        return "pending"
    if all(value == "pass" for value in states):
        return "triggered"
    return "pending"


def _action_state(trend: Dict, target: Dict) -> tuple[str, str]:
    direction = target.get("direction")
    producer = target.get("producer_status")
    execution = target.get("execution_state")
    confidence = target.get("effective_confidence")
    if trend["state"] in {"invalid", "down"} or execution == "invalid" or direction == "bearish":
        return "risk_control", "技术方向偏空，以防守或观望为主"
    if producer == "blocked" or execution == "blocked":
        return "wait_for_entry", "目标结构存在，但当前不满足入场条件"
    if "unavailable" in {producer, execution, confidence}:
        return "unavailable", "技术证据不足，无法形成可执行判断"
    if producer == "observe" or execution in {"pending", "observe"} or trend["state"] == "range":
        return "wait_for_confirmation", "技术目标尚未形成可执行确认"
    if execution == "triggered" and confidence in {"high", "medium"} and direction == "bullish" and trend["state"] in {"strong_up", "weak_up"}:
        return "follow", "趋势与技术目标均满足跟踪条件"
    return "unavailable", "技术判断组合未定义，安全降级"


def build_technical_judgment(
    resonance: Dict | None,
    price_target: Dict | None,
    indicators: Dict | None = None,
    daily_data: Any = None,
    market: str | None = None,
) -> Dict:
    """Build the single deterministic technical decision contract."""
    resonance = resonance if isinstance(resonance, dict) else {}
    price_target = price_target if isinstance(price_target, dict) else {}
    indicators = indicators if isinstance(indicators, dict) else {}
    trend = _trend_judgment(resonance)
    producer_status = price_target.get("status") if price_target.get("status") in _TARGET_STATUSES else "unavailable"
    reason_code = str(price_target.get("reason_code") or "untrusted_or_malformed_judgment")
    direction = price_target.get("direction") if price_target.get("direction") in {"bullish", "bearish", "neutral"} else "neutral"
    structure = price_target.get("structure_confidence") or (
        "observation" if (price_target.get("structure_evidence") or {}).get("method_family") == "fib_only" else "unavailable"
    )
    if structure not in _CONFIDENCE_ORDER:
        structure = "unavailable"
    cap = _quality_cap(resonance, indicators)
    effective = _min_confidence(structure, cap)
    checks = _trigger_checks(resonance, price_target, indicators, daily_data, direction, market)
    target = {
        "direction": direction,
        "producer_status": producer_status,
        "reason_code": reason_code,
        "structure_confidence": structure,
        "effective_confidence": effective,
        "structure_label": _CONFIDENCE_LABELS[structure],
        "effective_label": _CONFIDENCE_LABELS[effective],
        "basis": [price_target.get("method")] if price_target.get("method") else [],
        "trigger_checks": checks,
        "data_quality_cap": cap,
        "reason": price_target.get("reason", ""),
    }
    target["execution_state"] = _execution_state(target, checks, trend)
    target["display_mode"] = resolve_target_display_mode(direction, effective, target["execution_state"])
    action, action_summary = _action_state(trend, target)
    return {
        "schema": "technical_judgment.v1",
        "trend": trend,
        "target": target,
        "action": {"state": action, "summary": action_summary},
        "limitations": list((resonance.get("analysis_confidence") or {}).get("limitations", [])) if isinstance(resonance.get("analysis_confidence"), dict) else [],
    }


def is_valid_technical_judgment(value: Any) -> bool:
    """Accept only internally consistent, fully derived v1 judgments."""
    if not isinstance(value, dict) or value.get("schema") != "technical_judgment.v1":
        return False
    trend = value.get("trend", {})
    target = value.get("target", {})
    action = value.get("action", {})
    trigger_checks = target.get("trigger_checks")
    checks = (
        trend.get("state") in {"strong_up", "weak_up", "transition", "range", "down", "invalid", "unknown"},
        target.get("direction") in {"bullish", "bearish", "neutral"},
        target.get("producer_status") in _TARGET_STATUSES,
        bool(target.get("reason_code")),
        target.get("structure_confidence") in _CONFIDENCE_ORDER,
        target.get("effective_confidence") in _CONFIDENCE_ORDER,
        target.get("execution_state") in _EXECUTION_STATES,
        target.get("display_mode") == resolve_target_display_mode(target.get("direction"), target.get("effective_confidence"), target.get("execution_state")),
        isinstance(trigger_checks, dict) and all(
            trigger_checks.get(name, {}).get("status") in _CHECK_STATES
            for name in ("price", "trend", "volume", "momentum")
        ),
        action.get("state") in _ACTION_STATES,
        action.get("state") == _action_state(trend, target)[0],
    )
    return all(checks)


def ensure_technical_judgment(
    judgment: Dict | None = None,
    resonance: Dict | None = None,
    price_target: Dict | None = None,
    indicators: Dict | None = None,
    daily_data: Any = None,
    market: str | None = None,
) -> Dict:
    """Trust a complete v1 judgment, otherwise rebuild or fail closed."""
    if is_valid_technical_judgment(judgment):
        return judgment
    if isinstance(judgment, dict) and not resonance and "trend_state" in judgment:
        resonance = judgment
    return build_technical_judgment(resonance, price_target, indicators, daily_data, market)
