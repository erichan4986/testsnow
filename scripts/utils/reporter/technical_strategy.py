"""策略信号模块 — 分批观察框架等策略判断。"""


def evaluate_dart_strategy(
    bottom_signal: dict,
    trend_state: dict,
    indicators: dict,
    invalidation: dict,
) -> dict | None:
    """分批观察框架。不直接输出买入建议。"""
    if not bottom_signal or bottom_signal.get("state") not in ["bottom_candidate", "bottom_strengthened"]:
        return None

    weekly_stage = trend_state.get("stage", "")
    if weekly_stage == "破坏期":
        return None

    close = indicators.get("close")
    ma5 = indicators.get("ma_5")
    if close is None or ma5 is None or close < ma5:
        return None

    hard_price = invalidation.get("hard_invalid_price") if invalidation else None
    if hard_price is None:
        return None

    evidence = []
    if bottom_signal["state"] == "bottom_strengthened":
        evidence.append("底部信号增强")
    else:
        evidence.append("底部候选信号出现")
    evidence.append("价格已站上MA5")
    evidence.append("周线非单边下跌")

    return {
        "state": "active",
        "confidence": "中",
        "evidence": evidence,
        "missing": [],
        "action_hint": "底部区域观察成立，可采用分批观察框架",
        "steps": [
            {"level": 1, "condition": "重新站上MA5", "action": "进入观察清单"},
            {"level": 2, "condition": "站上MA10且量能改善", "action": "提高关注度"},
            {"level": 3, "condition": "站上MA20", "action": "视为中期修复确认"},
        ],
        "invalid_if": "跌破最近swing low",
    }
