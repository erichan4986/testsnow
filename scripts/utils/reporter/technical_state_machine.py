"""趋势状态机模块 — 状态判定、健康度评分、失效条件。"""

from typing import Dict

import pandas as pd

__all__ = [
    "classify_trend_state", "apply_previous_state",
    "compute_trend_health", "compute_invalidation",
    "evaluate_bias_extreme", "detect_false_rebound",
    "detect_false_breakout", "evaluate_sell_three_factors",
]


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
        }
    if bias_5_extreme_low or bias_10_extreme_low:
        return {
            "warning": "BIAS 创近120日新低，极端超卖",
            "level": "严重",
            "direction": "low",
            "affects": "买入参考，不构成买入信号",
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


def evaluate_sell_three_factors(*args, **kwargs):
    """Placeholder for sell three-factors framework."""
    return None


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
