"""市场/板块共振框架 — Phase 2 占位版，不访问外部数据。"""

from typing import Dict, Optional

__all__ = ["evaluate_market_resonance"]


def evaluate_market_resonance(
    stock_trend_state: dict,
    sector_trend: str | None = None,
    market_trend: str | None = None,
) -> dict:
    """
    评估个股与板块/大盘的共振状态。
    Phase 2 占位版：未接入外部数据时稳定返回占位信息，不报错。
    """
    if sector_trend is None and market_trend is None:
        return {
            "resonance_signals": [],
            "sector_trend": "未接入",
            "market_trend": "未接入",
            "impact": "暂未接入市场/行业数据，本次技术分析仅基于个股自身K线结构。",
        }

    signals = []
    primary_state = stock_trend_state.get("primary_state", "")

    if primary_state == "上升趋势" and sector_trend == "上涨" and market_trend == "上涨":
        signals.append("共振上涨，信号增强")
    elif primary_state == "上升趋势" and (sector_trend != "上涨" or market_trend != "上涨"):
        signals.append("独立行情，注意共振回落风险")

    return {
        "resonance_signals": signals,
        "sector_trend": sector_trend or "未接入",
        "market_trend": market_trend or "未接入",
        "impact": (
            "个股与板块/大盘共振良好，信号增强"
            if signals and "共振上涨" in signals[0]
            else "个股独立运行，注意外部风险"
        ),
    }
