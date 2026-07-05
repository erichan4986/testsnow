"""市场/板块共振框架 — Phase 3 完整版。"""

import json
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

__all__ = [
    "evaluate_market_resonance",
    "load_market_index_map",
    "_prefix_fallback",
    "analyze_index_trend",
]


def _prefix_fallback(stock_code: str) -> dict:
    """代码前缀 fallback 判定所属市场/主题指数。"""
    prefix = stock_code[:3] if len(stock_code) >= 3 else stock_code
    result = {"market": None, "sector": None, "thematic": None, "source": "prefix_fallback"}

    if prefix in ["600", "601", "603", "605"]:
        result["market"] = {"code": "000001", "name": "上证综指", "source": "fallback"}
    elif prefix in ["000", "001", "002", "003"]:
        result["market"] = {"code": "399001", "name": "深证成指", "source": "fallback"}
    elif prefix == "300":
        result["market"] = {"code": "399006", "name": "创业板指", "source": "fallback"}
        result["thematic"] = {"code": "399006", "name": "创业板指", "source": "fallback"}
    elif prefix == "688":
        result["market"] = {"code": "000001", "name": "上证综指", "source": "fallback"}
        result["thematic"] = {"code": "000688", "name": "科创50", "source": "fallback"}
    else:
        result["market"] = {"code": "000001", "name": "上证综指", "source": "default"}

    return result


def load_market_index_map(stock_code: str, map_path: str | None = None) -> dict:
    """加载市场/行业/主题映射。优先本地 map，缺失走 prefix fallback。"""
    if map_path is None:
        map_path = str(Path(__file__).parent.parent.parent.parent / "config" / "market_index_map.json")

    try:
        with open(map_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"_meta": {"source": "prefix_fallback"}}

    entry = data.get(stock_code)
    if entry:
        return {
            "market": entry.get("market"),
            "sector": entry.get("sector"),
            "thematic": entry.get("thematic"),
            "source": "map",
            "confidence": entry.get("confidence", "中"),
        }

    return _prefix_fallback(stock_code)


def analyze_index_trend(
    df_daily: pd.DataFrame,
    df_weekly: pd.DataFrame | None = None,
) -> dict:
    """对指数复用中期趋势状态机。"""
    if df_daily is None or df_daily.empty:
        return {
            "trend_state": {"primary_state": "未知", "stage": "未知"},
            "weekly_background": {"trend": "未知"},
            "daily_structure": {},
            "trend_health": {"score": 0, "grade": "未知"},
            "missing": ["index daily data missing"],
        }

    try:
        from .technical_structure import (
            resample_daily_to_weekly,
            compute_weekly_trend,
            compute_ma_direction,
        )
        from .technical_state_machine import (
            classify_trend_state,
            compute_trend_health,
        )
    except ImportError:
        from technical_structure import (
            resample_daily_to_weekly,
            compute_weekly_trend,
            compute_ma_direction,
        )
        from technical_state_machine import (
            classify_trend_state,
            compute_trend_health,
        )

    if df_weekly is None or df_weekly.empty:
        df_weekly = resample_daily_to_weekly(df_daily)

    close = df_daily["close"]
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    indicators = {
        "close": float(close.iloc[-1]),
        "ma_20": float(ma20.iloc[-1]) if len(ma20.dropna()) else None,
        "ma_60": float(ma60.iloc[-1]) if len(ma60.dropna()) else None,
        "ma20_direction": compute_ma_direction(ma20),
        "ma60_direction": compute_ma_direction(ma60),
    }

    weekly = compute_weekly_trend(df_weekly)

    daily_structure = {
        "ma20_direction": indicators["ma20_direction"],
        "ma60_direction": indicators["ma60_direction"],
        "price_vs_ma20": (
            "站上" if indicators["ma_20"] and indicators["close"] >= indicators["ma_20"] else "跌破"
        ),
        "price_vs_ma60": (
            "站上" if indicators["ma_60"] and indicators["close"] >= indicators["ma_60"] else "跌破"
        ),
    }

    trend_state = classify_trend_state(
        weekly_trend=weekly.get("weekly_trend", "未知"),
        daily_structure=daily_structure,
        indicators=indicators,
        divergence=None,
    )

    try:
        trend_health = compute_trend_health(
            weekly_trend=weekly.get("weekly_trend", "未知"),
            daily_structure=daily_structure,
            indicators=indicators,
            df_daily=df_daily,
        )
    except TypeError:
        trend_health = compute_trend_health(
            weekly_trend=weekly.get("weekly_trend", "未知"),
            daily_structure=daily_structure,
            indicators=indicators,
        )

    return {
        "trend_state": trend_state,
        "weekly_background": weekly,
        "daily_structure": daily_structure,
        "trend_health": trend_health,
        "missing": [],
    }


def evaluate_market_resonance(
    stock_trend_state: dict,
    market_trend_state: dict | None = None,
    sector_trend_state: dict | None = None,
    theme_trend_state: dict | None = None,
    mapping_meta: dict | None = None,
) -> dict:
    """个股 vs 市场/行业/主题趋势共振。"""
    critical_missing = []
    if market_trend_state is None:
        critical_missing.append("market index data missing")

    # 行业缺失但主题可用时，用主题指数代理，不再显示 raw missing
    sector_proxy_note = None
    theme_name = "主题指数"
    if mapping_meta and mapping_meta.get("thematic") and mapping_meta["thematic"].get("name"):
        theme_name = mapping_meta["thematic"]["name"]

    if sector_trend_state is None:
        if theme_trend_state is not None:
            sector_proxy_note = f"以{theme_name}代理行业共振"
        else:
            critical_missing.append("sector index data missing")

    optional_missing = []
    if theme_trend_state is None:
        optional_missing.append("theme index data missing")
    elif sector_proxy_note:
        optional_missing.append(sector_proxy_note)

    if market_trend_state is None and sector_trend_state is None:
        return {
            "state": "未知",
            "confidence": "低",
            "market_trend": market_trend_state,
            "sector_trend": sector_trend_state,
            "theme_trend": theme_trend_state,
            "relative_strength": "未知",
            "evidence": [],
            "missing": critical_missing + optional_missing,
            "impact": "暂未接入完整市场/行业数据，本次共振分析仅作占位。",
            "action_hint": "继续观察",
        }

    missing = critical_missing + optional_missing

    def _strength(state):
        if not state:
            return 0
        stage = state.get("stage", "")
        primary = state.get("primary_state", "")
        if primary == "上升趋势":
            return 2 if stage in ["主升期", "加速期", "启动期"] else 1
        elif primary == "下降趋势":
            return -2 if stage in ["破坏期", "转弱期"] else -1
        return 0

    s_str = _strength(stock_trend_state)
    m_str = _strength(market_trend_state)
    c_str = _strength(sector_trend_state)
    t_str = _strength(theme_trend_state)

    # 行业缺失时用主题指数替代，用于规则判断
    effective_sector = c_str if c_str != 0 else t_str

    # 相对行业强弱（优先用行业，缺失用主题）
    if effective_sector > 0:
        relative = "强于行业" if s_str >= effective_sector else "弱于行业"
    elif effective_sector < 0:
        relative = "强于行业" if s_str > effective_sector else "弱于行业"
    else:
        relative = "同步"

    # 共振规则矩阵
    if s_str > 0 and m_str > 0 and effective_sector > 0:
        state = "顺风共振"; impact = "趋势信号可信度上调"; conf = "高"
    elif s_str > 0 and m_str <= 0 and effective_sector <= 0:
        state = "逆风独立"; impact = "独立行情，波动风险上升"; conf = "中"
    elif s_str < 0 and effective_sector > 0:
        state = "弱于板块"; impact = "个股弱于行业，优先级下降"; conf = "中"
    elif s_str < 0 and m_str < 0 and effective_sector < 0:
        state = "系统性压力"; impact = "中期修复难度较大"; conf = "高"
    elif s_str == 0 and effective_sector > 0:
        state = "等待补涨确认"; impact = "观察是否突破 MA20"; conf = "中"
    elif s_str == 0 and effective_sector < 0:
        state = "震荡偏弱"; impact = "降低技术信号权重"; conf = "低"
    else:
        state = "未知"; impact = "信号复杂，继续观察"; conf = "低"

    evidence = [f"个股趋势：{stock_trend_state.get('stage', '未知')}"]
    if market_trend_state:
        evidence.append(f"大盘趋势：{market_trend_state.get('stage', '未知')}")
    if sector_trend_state:
        evidence.append(f"行业趋势：{sector_trend_state.get('stage', '未知')}")

    return {
        "state": state,
        "confidence": conf,
        "market_trend": market_trend_state,
        "sector_trend": sector_trend_state,
        "theme_trend": theme_trend_state,
        "relative_strength": relative,
        "evidence": evidence,
        "missing": missing,
        "impact": impact,
        "action_hint": "继续观察" if state in ["未知", "震荡偏弱"] else ("趋势跟随" if state == "顺风共振" else "保持谨慎"),
    }
