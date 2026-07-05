"""价格目标与触发条件板块渲染器。"""

from typing import Any, Dict


class PriceTargetRenderer:
    """价格目标与触发条件板块 — 基于 price_target 分析结果。"""

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_raw = ctx.get("stock_raw", {})
        pt = stock_raw.get("price_target")
        if not pt or not isinstance(pt, dict):
            return ""

        if pt.get("error"):
            lines = ["\n## 价格目标与触发条件\n", f"> **{pt['error']}**"]
            reason = pt.get("reason", "")
            if reason:
                lines.append(f"> {reason}")
            weekly = pt.get("weekly_trend", {})
            if weekly:
                wdir = weekly.get("direction", "")
                wadx = weekly.get("adx", "")
                if wdir and wadx:
                    lines.append(f"> 周线趋势: {wdir} (ADX={wadx})")
            lines.append("")
            return "\n".join(lines)

        lines = ["\n## 价格目标与触发条件\n"]

        # Direction + confidence + profit/risk
        direction = pt.get("direction", "")
        confidence = pt.get("confidence", "")
        conf_score = pt.get("confidence_score", 0)
        pr_ratio = pt.get("profit_risk_ratio")
        pr_text = f" | **盈亏比**: {pr_ratio}:1" if pr_ratio else ""

        lines.append(f"**方向**: {direction} | **置信度**: {confidence}（{conf_score}/10）{pr_text}")
        lines.append("")

        # Momentum status line
        momentum = pt.get("momentum_status", "")
        if momentum:
            lines.append(f"**动量状态**: {momentum}")
            if "MACD死叉" in momentum and ("RSI" in momentum or "MA多头" in momentum):
                lines.append("⚠️ **动量信号分歧，建议等待一致**")
            lines.append("")

        # Target table
        lines.append("| 目标 | 价格 | 推导依据 | 验证源 |")
        lines.append("|------|------|---------|--------|")

        conservative = pt.get("conservative")
        base = pt.get("base")
        aggressive = pt.get("aggressive")
        aggressive_raw = pt.get("aggressive_raw")
        method = pt.get("method", "")

        if conservative:
            lines.append(f"| 保守 | {conservative} | {method} | 综合 |")
        if base:
            lines.append(f"| 基准 | {base} | {method} | A+B交叉验证 |")
        if aggressive:
            if pt.get("is_far_target"):
                lines.append(f"| 激进 | {aggressive_raw}（久远，暂不可达） | 周K斐波那契1.618扩展 | 周线大结构 |")
            else:
                lines.append(f"| 激进 | {aggressive} | 周K斐波那契1.618扩展 | 周线大结构 |")

        lines.append("")

        # Trigger conditions
        trigger = pt.get("trigger_conditions", {})
        if trigger:
            parts = []
            if trigger.get("price"):
                parts.append(trigger["price"])
            if trigger.get("trend"):
                parts.append(trigger["trend"])
            if trigger.get("volume"):
                parts.append(trigger["volume"])
            if trigger.get("momentum"):
                parts.append(trigger["momentum"])
            if parts:
                lines.append(f"**触发**: {' + '.join(parts)}")

        # Stop loss
        stop = pt.get("stop_loss", "")
        if stop:
            lines.append(f"**止损**: {stop}")

        # Failure conditions
        failures = pt.get("failure_conditions", [])
        if failures:
            lines.append(f"**失效**: {' / '.join(failures)}")

        # Time estimate
        time_est = pt.get("time_estimate", {})
        if time_est:
            parts = []
            if time_est.get("conservative"):
                parts.append(f"保守{time_est['conservative']}")
            if time_est.get("base"):
                parts.append(f"基准{time_est['base']}")
            if time_est.get("aggressive"):
                parts.append(f"激进{time_est['aggressive']}")
            if parts:
                lines.append(f"**时间预期**: {' / '.join(parts)}")

        lines.append("")
        return "\n".join(lines)
