"""技术面分析板块渲染器 — 支持中期趋势新版 + 旧版降级。"""

import sys
from pathlib import Path
from typing import Any, Dict


def _technical_judgment(resonance: Dict, price_target: Dict, indicators: Dict) -> Dict:
    try:
        from ..technical_state_machine import ensure_technical_judgment
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from technical_state_machine import ensure_technical_judgment
    return ensure_technical_judgment(resonance.get("judgment"), resonance=resonance, price_target=price_target, indicators=indicators)


def _valid_technical_judgment(value: Any) -> bool:
    try:
        from ..technical_state_machine import is_valid_technical_judgment
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from technical_state_machine import is_valid_technical_judgment
    return is_valid_technical_judgment(value)


class TechnicalRenderer:
    """技术面分析板块 — 中期趋势提醒系统。"""

    @staticmethod
    def _as_dict(value: Any) -> Dict:
        return value if isinstance(value, dict) else {}

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        stock_raw = ctx.get("stock_raw", {})
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})

        cached = resonance.get("judgment")
        if (resonance.get("trend_state") and resonance.get("trend_health")) or _valid_technical_judgment(cached):
            target = tech.get("price_target") if isinstance(tech.get("price_target"), dict) else {}
            judgment = _technical_judgment(resonance, target, indicators)
            return self._render_projection(
                resonance, judgment, target, stock_name, ctx,
                full=ctx.get("technical_render_mode", "full") == "full",
            )

        return self._render_legacy(resonance, indicators, stock_name, ctx)

    def _render_projection(
        self, resonance: Dict, judgment: Dict, price_target: Dict,
        stock_name: str, ctx: Dict, *, full: bool,
    ) -> str:
        interpretation = judgment.get("interpretation")
        if not isinstance(interpretation, dict):
            return self._render_core_judgment(judgment)
        ts = resonance.get("trend_state", {})
        th = resonance.get("trend_health", {})
        inv = resonance.get("invalidation", {})
        kl = resonance.get("key_levels", {})
        advisors = resonance.get("advisors", {})
        conf = resonance.get("analysis_confidence", {})
        lines = ["## 技术面分析：中期趋势提醒", ""]
        lines.extend(["**技术判断**", f"> {interpretation['headline']}", ""])
        action = judgment.get("action") or {}
        trend = judgment.get("trend") or {}
        lines.append(f"**当前行动**：{action.get('summary') or '技术证据不足，维持观察'}")
        health = trend.get("health_score")
        health_text = f"；趋势健康度 {health}/100（{trend.get('health_grade') or '未分级'}）" if health is not None else ""
        lines.append(f"**趋势状态**：{trend.get('label', '未知')} / {trend.get('stage') or '阶段未知'}{health_text}")
        if conf.get("level"):
            lines.append(f"**分析可信度**：{conf['level']}")
        limitations = list(dict.fromkeys([*(conf.get("limitations") or []), *(judgment.get("limitations") or [])]))
        if limitations:
            lines.append(f"限制因素：{'；'.join(limitations)}")
        lines.append("")

        corp_warning = resonance.get("corporate_action_warning")
        if corp_warning and corp_warning.get("has_recent_action"):
            lines.append(f"> **数据提醒**：{corp_warning['message']}")
            if corp_warning.get("note"):
                lines.append(f"> **注意**：{corp_warning['note']}")
            lines.append("")

        primary_evidence = interpretation.get("primary_evidence") or []
        self._append_evidence(lines, "主导证据", primary_evidence)
        self._append_evidence(lines, "反向线索", interpretation.get("counter_evidence"))
        confirmations = interpretation.get("confirmation_conditions") or []
        primary_texts = {item.get("text") for item in primary_evidence if isinstance(item, dict)}
        invalidations = [
            text for text in (interpretation.get("invalidation_conditions") or [])
            if text not in primary_texts
        ]
        if confirmations or invalidations:
            invalidated = trend.get("state") == "invalid"
            if invalidated and not confirmations:
                lines.append("**已触发的破坏条件**")
            else:
                lines.append("**确认条件与已触发的破坏条件**" if invalidated else "**确认与趋势失效条件**")
            lines.extend(f"- 确认：{text}" for text in confirmations)
            label = "已触发" if invalidated else "失效"
            lines.extend(f"- {label}：{text}" for text in invalidations)
            lines.append("")

        if full:
            weekly = self._as_dict(resonance.get("weekly_background"))
            daily_raw = resonance.get("daily_structure")
            daily = self._as_dict(daily_raw)
            lines.extend([
                "### 1. 趋势背景",
                f"- 周线大背景：{weekly.get('trend', '未知')}",
                f"- MA 结构：{weekly.get('ma_structure', '未知')}",
                "",
                "### 2. 日线结构",
                f"- MA20 方向：{daily.get('ma20_direction', '未知')}",
                f"- MA60 方向：{daily.get('ma60_direction', '未知')}",
                f"- 价格位置：{daily.get('price_vs_ma20', '未知')} MA20",
            ])
            if isinstance(daily_raw, str) and daily_raw:
                lines.append(f"- 结构摘要：{daily_raw}")
            lines.append("")

        lines.append("**趋势与位置**")
        daily_raw = resonance.get("daily_structure")
        if isinstance(daily_raw, str) and daily_raw:
            lines.extend([f"- 日线结构：{daily_raw}", ""])
        components = th.get("components", {})
        if components:
            _cn = {
                "weekly_structure": "周线结构",
                "daily_ma_alignment": "日线MA趋势",
                "price_structure": "价格结构",
                "volume_confirmation": "成交量确认",
                "volatility_condition": "波动率条件",
            }
            lines.append("| 维度 | 得分 | 说明 |")
            lines.append("|------|------|------|")
            for name, comp in components.items():
                label = _cn.get(name, name)
                lines.append(f"| {label} | {comp.get('score', 0)}/{comp.get('max', 0)} | {comp.get('evidence', '')} |")
            lines.append("")
            radar_text = self._build_radar_summary(components, th.get("score", 0))
            if radar_text:
                lines.extend([f"**综合评分摘要**：{radar_text}", ""])

        lines.append("**关键观察位**")
        sz = kl.get("support_zone")
        rz = kl.get("resistance_zone")
        if sz:
            lines.append(f"- 支撑区：【{sz.get('zone_low', '—')} - {sz.get('zone_high', '—')}】（{sz.get('strength', '弱')}）")
        else:
            lines.append("- 支撑区：暂无可靠支撑区")
        if rz:
            lines.append(f"- 压力区：【{rz.get('zone_low', '—')} - {rz.get('zone_high', '—')}】（{rz.get('strength', '弱')}）")
        else:
            lines.append("- 压力区：暂无可靠压力区")
        if not sz and not rz:
            raw_indicators = ctx.get("stock_raw", {}).get("technical", {}).get("indicators", {})
            close_val = raw_indicators.get("close")
            for ma_key, ma_label in [
                ("ma_5", "MA5"), ("ma_10", "MA10"), ("ma_20", "MA20"), ("ma_60", "MA60"),
            ]:
                ma_val = raw_indicators.get(ma_key)
                if close_val is not None and ma_val is not None and ma_val > 0:
                    diff_pct = round((close_val - ma_val) / ma_val * 100, 2)
                    rel = "站上" if diff_pct >= 0 else "跌破"
                    lines.append(f"- {ma_label}：约 {ma_val:.2f}（当前{rel}，距离 {diff_pct:+.2f}%）")
        if inv.get("hard_invalid_price") is not None:
            basis = inv.get("hard_invalid_source", "")
            price = inv["hard_invalid_price"]
            dist = inv.get("current_distance_to_invalid", "未知")
            msg = inv.get("message", "")
            lines.append(f"- 中期失效参考：日线 {basis} 约 {price:.2f}，当前距离约 {dist}")
            if msg:
                lines.append(f"  {msg}")
        lines.append("")
        structure = resonance.get("structure_health") or {}
        if structure.get("state") not in {None, "", "无法判断"}:
            lines.append(f"**局部趋势结构（辅助）**：{structure['state']}（置信度：{structure.get('confidence', '未知')}）")
            for evidence in (structure.get("evidence") or [])[:1]:
                lines.append(f"- {evidence}")
            lines.append("")
        channel = resonance.get("channel_status") or {}
        if channel.get("state") not in {None, "", "未知", "无明显通道"}:
            lines.append(f"**通道/箱体（辅助）**：{channel['state']}（位置：{channel.get('position', '未知')}）")
            if channel.get("breakout_status") not in {None, "", "未突破"}:
                lines.append(f"- 突破状态：{channel['breakout_status']}")
            lines.append("")
        market = interpretation.get("market_context") or {}
        if market.get("status") in {"ready", "partial"}:
            lines.extend([f"**市场/板块共振**：{market.get('summary', '')}", ""])
        priority = interpretation.get("priority_observation")
        if priority:
            lines.extend([f"> **短期优先观察：{priority.get('label', '')}**", f"> 依据：{priority.get('detail', '')}", ""])

        tech_raw = ctx.get("stock_raw", {}).get("technical", {})
        concept_blocks = tech_raw.get("concept_blocks")
        if concept_blocks and concept_blocks.get("concept_tags"):
            tags = concept_blocks["concept_tags"][:8]
            lines.append(f"**所属概念板块**：{', '.join(tags)}")
            lines.append("")
        fund_flow = tech_raw.get("fund_flow")
        if fund_flow and isinstance(fund_flow, list) and len(fund_flow) > 0:
            lines.append("**近5日资金流向**（万元）：")
            for row in fund_flow[:5]:
                date = row.get("date", "")
                main_in = row.get("main_in", "")
                change = row.get("change_pct", "")
                lines.append(f"- {date}: 主力净流入 {main_in}万，涨跌 {change}%")
            lines.append("")
        if advisors:
            lines.append("**谋士团**：")
            lines.append("| 指标 | 状态 | 含义 |")
            lines.append("|------|------|------|")
            for name, info in advisors.items():
                lines.append(f"| {name.upper()} | {info.get('state', '—')} | {info.get('meaning', '')} |")
            lines.append("")
        lines.extend(self._render_target_judgment(judgment, price_target))
        chart_paths = ctx.get("chart_paths", {})
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _append_evidence(lines: list[str], title: str, items: Any) -> None:
        if not items:
            return
        lines.append(f"**{title}**")
        lines.extend(f"- {item.get('text', '')}" for item in items if isinstance(item, dict) and item.get("text"))
        lines.append("")

    def _render_core_judgment(self, judgment: Dict) -> str:
        trend, target, action = judgment.get("trend") or {}, judgment.get("target") or {}, judgment.get("action") or {}
        target_text = {
            "observe": "当前仅形成观察结构，暂不展示精确目标价",
            "blocked": "当前目标条件尚未满足，暂不跟随",
            "invalid": "周期或形态方向冲突，当前目标无效",
            "unavailable": "证据不足，暂不展示目标价",
        }.get(target.get("producer_status"), "目标结构尚待确认")
        return "\n".join([
            "## 技术面分析：中期趋势提醒", "", "**技术判断**",
            f"> {action.get('summary') or '技术证据不足，维持观察'}", "",
            f"**趋势状态**：{trend.get('label') or '未知'} / {trend.get('stage') or '阶段未知'}", "",
            "**价格目标分析**", "", f"> {target_text}。", "",
        ])

    def _render_target_judgment(self, judgment: Dict, raw_target: Dict) -> list[str]:
        target = judgment["target"]
        lines = ["**价格目标分析**", ""]
        message = (judgment.get("interpretation") or {}).get("target_message") or {}
        if message.get("state") != "ready":
            return lines + [f"> {message.get('text') or '证据不足，暂不展示目标价'}。", ""]
        mode = target["display_mode"]
        values = raw_target.get("targets") if isinstance(raw_target.get("targets"), dict) else raw_target
        labels = [("conservative", "保守"), ("base", "基准")]
        if mode == "full_targets":
            labels.append(("aggressive", "激进"))
        rows = []
        for key, label in labels:
            value = values.get(key)
            if isinstance(value, (int, float)):
                rows.append(f"| {label} | {value:.2f} |")
        if rows:
            lines.extend(["| 目标 | 价格 |", "|------|------|", *rows, ""])
        checks = target.get("trigger_checks", {})
        if checks:
            lines.append("**触发检查**")
            for name, check in checks.items():
                if isinstance(check, dict):
                    lines.append(f"- {name}：{check.get('status', 'unknown')}（{check.get('detail', '数据不足')}）")
            lines.append("")
        if raw_target.get("stop_loss"):
            lines.extend([f"**止损**：{raw_target['stop_loss']}", ""])
        return lines

    def _render_legacy(self, resonance: Dict, indicators: Dict, stock_name: str, ctx: Dict) -> str:
        """旧版技术指标快照渲染（降级）。"""
        lines = ["## 技术面分析", ""]

        if resonance:
            trend = resonance.get("trend", "")
            momentum = resonance.get("momentum", "")
            score = resonance.get("composite_score", 0)
            signals = resonance.get("signals", [])

            trend_icon = {"多头": "", "空头": "", "震荡": ""}.get(trend, "")
            mom_icon = {"超买": "", "超卖": "", "中性": ""}.get(momentum, "")
            lines.append(
                f"**趋势**: {trend_icon} {trend} | **动量**: {mom_icon} {momentum} | **综合评分**: {score}/10"
            )
            lines.append("")
            if signals:
                lines.append("**关键信号：**")
                for sig in signals:
                    lines.append(f"- {sig}")
                lines.append("")

        lines.append("### 指标快照")
        lines.append("")
        lines.append("| 指标 | 数值 | 状态 |")
        lines.append("|------|------|------|")

        def _status(val, bull, bear):
            if val is None:
                return "N/A", "—"
            s = f"{val:.1f}"
            if bull and bear:
                if val > bull:
                    return s, " 超买"
                elif val < bear:
                    return s, " 超卖"
                return s, " 中性"
            return s, "—"

        rsi = indicators.get("rsi_14")
        v, st = _status(rsi, 70, 30)
        lines.append(f"| RSI(14) | {v} | {st} |")

        macd = indicators.get("macd")
        macd_hist = indicators.get("macd_hist")
        if macd is not None:
            macd_str = f"{macd:+.2f}"
            if macd_hist is not None:
                macd_str += f" (柱{macd_hist:+.2f})"
            macd_state = " 金叉扩张" if macd > 0 and macd_hist and macd_hist > 0 else (" 死叉收缩" if macd < 0 and macd_hist and macd_hist < 0 else " 观望")
            lines.append(f"| MACD | {macd_str} | {macd_state} |")

        adx = indicators.get("adx")
        plus_di = indicators.get("plus_di")
        minus_di = indicators.get("minus_di")
        if adx is not None:
            adx_str = f"{adx:.1f}"
            if plus_di is not None and minus_di is not None:
                adx_str += f" (+{plus_di:.1f}/-{minus_di:.1f})"
            adx_state = " 强趋势" if adx > 25 else " 弱趋势"
            lines.append(f"| ADX(14) | {adx_str} | {adx_state} |")

        cci = indicators.get("cci_20")
        v, st = _status(cci, 100, -100)
        lines.append(f"| CCI(20) | {v} | {st} |")

        wr = indicators.get("williams_r")
        v, st = _status(wr, -20, -80)
        lines.append(f"| Williams %R(14) | {v} | {st} |")

        stoch_k = indicators.get("stoch_rsi_k")
        stoch_d = indicators.get("stoch_rsi_d")
        if stoch_k is not None:
            stoch_str = f"{stoch_k:.2f}"
            if stoch_d is not None:
                stoch_str += f" / D={stoch_d:.2f}"
            stoch_state = " 超买" if stoch_k > 0.8 else (" 超卖" if stoch_k < 0.2 else " 中性")
            lines.append(f"| StochRSI(14) | {stoch_str} | {stoch_state} |")

        atr = indicators.get("atr_14")
        close = indicators.get("close")
        if atr is not None and close:
            atr_pct = atr / close * 100
            atr_state = " 高波动" if atr_pct > 5 else (" 低波动" if atr_pct < 1.5 else " 正常")
            lines.append(f"| ATR(14) | {atr:.2f} ({atr_pct:.1f}%) | {atr_state} |")

        lines.append("")

        levels = indicators.get("_levels", {})
        support = levels.get("support")
        resistance = levels.get("resistance")
        if support or resistance:
            lines.append("### 关键价位")
            lines.append("")
            if support:
                lines.append(f"- **支撑位**: {support}")
            if resistance:
                lines.append(f"- **阻力位**: {resistance}")
            if close and support and resistance:
                position = (close - support) / (resistance - support) * 100 if resistance != support else 50
                lines.append(f"- **当前位置**: 处于支撑-阻力区间的 **{position:.0f}%**")
            lines.append("")

        patterns = indicators.get("_patterns", [])
        if patterns:
            lines.append("### 形态识别")
            lines.append("")
            for p in patterns:
                conf = p.get("confidence", "")
                desc = p.get("description", "")
                lines.append(f"- **{p['pattern']}** ({conf}置信): {desc}")
            lines.append("")

        chart_paths = ctx.get("chart_paths", ctx.get("_chart_paths", {}))
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)

    def _build_radar_summary(self, components: dict, total_score: int) -> str:
        """根据评分子项生成一句话雷达摘要。"""
        if not components:
            return ""
        # 找出最强和最弱维度
        ratios = {}
        for name, comp in components.items():
            max_ = comp.get("max", 1)
            score = comp.get("score", 0)
            ratios[name] = score / max_ if max_ > 0 else 0

        if not ratios:
            return ""

        best = max(ratios, key=ratios.get)
        worst = min(ratios, key=ratios.get)
        _cn = {
            "weekly_structure": "周线结构",
            "daily_ma_alignment": "日线MA趋势",
            "price_structure": "价格结构",
            "volume_confirmation": "成交量确认",
            "volatility_condition": "波动率条件",
        }
        best_label = _cn.get(best, best)
        worst_label = _cn.get(worst, worst)

        best_ratio = ratios[best]
        worst_ratio = ratios[worst]

        if total_score >= 70:
            overall = "整体健康"
        elif total_score >= 50:
            overall = "结构尚可"
        else:
            overall = "结构偏弱"

        parts = [f"{overall}，{best_label}最强"]
        if worst_ratio < 0.4:
            parts.append(f"{worst_label}偏弱需关注")
        return "；".join(parts) + "。"
