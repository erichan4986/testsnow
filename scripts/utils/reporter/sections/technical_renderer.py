"""技术面分析板块渲染器 — 支持中期趋势新版 + 旧版降级。"""

from typing import Any, Dict


class TechnicalRenderer:
    """技术面分析板块 — 中期趋势提醒系统。"""

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        stock_raw = ctx.get("stock_raw", {})
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})

        if resonance.get("trend_state") and resonance.get("trend_health"):
            mode = ctx.get("technical_render_mode", "full")
            if mode == "full":
                return self._render_full(resonance, stock_name, ctx)
            return self._render_compact(resonance, stock_name, ctx)

        return self._render_legacy(resonance, indicators, stock_name, ctx)

    def _render_compact(self, resonance: Dict, stock_name: str, ctx: Dict) -> str:
        ts = resonance.get("trend_state", {})
        th = resonance.get("trend_health", {})
        inv = resonance.get("invalidation", {})
        kl = resonance.get("key_levels", {})
        advisors = resonance.get("advisors", {})
        conf = resonance.get("analysis_confidence", {})

        lines = ["## 技术面分析：中期趋势提醒", ""]

        if conf.get("level"):
            lines.append(f"**分析可信度**：{conf['level']}")
            if conf.get("limitations"):
                lines.append(f"限制因素：{'；'.join(conf['limitations'])}")
            lines.append("")

        stage = ts.get("stage", "未知")
        primary = ts.get("primary_state", "未知")
        score = th.get("score", 0)
        grade = th.get("grade", "未知")
        summary = ts.get("summary", "")

        lines.append(
            f"当前处于【{primary} / {stage}】，趋势健康度【{score}/100，{grade}】。"
        )
        if summary:
            lines.append(summary)
        lines.append("")

        lines.append("**关键观察位**：")
        sz = kl.get("support_zone")
        rz = kl.get("resistance_zone")
        if sz:
            lines.append(f"- 支撑区：【{sz.get('zone_low', '—')} - {sz.get('zone_high', '—')}】（{sz.get('strength', '弱')}）")
        else:
            lines.append("- 支撑区：暂无可靠支撑区，原因：历史数据不足或有效触及次数不足。")
        if rz:
            lines.append(f"- 压力区：【{rz.get('zone_low', '—')} - {rz.get('zone_high', '—')}】（{rz.get('strength', '弱')}）")
        else:
            lines.append("- 压力区：暂无可靠压力区，原因：历史数据不足或有效触及次数不足。")
        if inv.get("current_distance_to_invalid"):
            lines.append(f"- 中期失效参考：【{inv['current_distance_to_invalid']}】")
        lines.append("")

        sr_transform = resonance.get("sr_transformation")
        if sr_transform:
            for sig in sr_transform.get("signals", []):
                lines.append(f"**{sig['signal']}**")
            lines.append("")

        lines.append("**趋势失效条件**：")
        if inv.get("soft_warning"):
            lines.append(f"- 第一警戒：【{inv['soft_warning']}】")
        if inv.get("hard_invalid"):
            lines.append(f"- 中期失效：【{inv['hard_invalid']}】")
        lines.append("")

        deductions = th.get("deductions", [])
        if deductions:
            lines.append(f"**主要风险**：【{'，'.join(deductions)}】")
            lines.append("")

        ds = resonance.get("daily_structure", {})
        candle_signal = ds.get("candle_signal")
        if candle_signal:
            lines.append(f"**K线形态**：{candle_signal['signal']}（位置：{candle_signal['location']}）")
            lines.append("")

        # Phase 3 新增模块渲染
        structure = resonance.get("structure_health")
        if structure and structure.get("state") != "无法判断":
            sh_state = structure.get("state", "")
            sh_conf = structure.get("confidence", "")
            lines.append(f"**趋势结构**：{sh_state}（置信度：{sh_conf}）")
            for ev in structure.get("evidence", [])[:3]:
                lines.append(f"- {ev}")
            lines.append(f"- 提示：{structure.get('action_hint', '')}")
            lines.append("")

        channel = resonance.get("channel_status")
        if channel and channel.get("state") not in ["无明显通道", "未知"]:
            ch_state = channel.get("state", "")
            ch_conf = channel.get("confidence", "")
            pos = channel.get("position", "")
            lines.append(f"**通道/箱体**：{ch_state}（置信度：{ch_conf}）")
            lines.append(f"- 位置：{pos}")
            if channel.get("breakout_status") != "未突破":
                lines.append(f"- 突破状态：{channel['breakout_status']}")
            lines.append(f"- 提示：{channel.get('action_hint', '')}")
            lines.append("")

        bottom = resonance.get("bottom_signal")
        if bottom and bottom.get("state") != "none":
            b_state = bottom.get("state", "")
            b_conf = bottom.get("confidence", "")
            display_state = {"bottom_watch": "底部区域观察", "bottom_candidate": "底部候选", "bottom_strengthened": "底部信号增强"}.get(b_state, b_state)
            lines.append(f"**底部区域**：{display_state}（置信度：{b_conf}）")
            for ev in bottom.get("evidence", [])[:3]:
                lines.append(f"- {ev}")
            if bottom.get("missing"):
                lines.append(f"- 尚缺：{'; '.join(bottom['missing'][:2])}")
            lines.append(f"- 提示：{bottom.get('action_hint', '')}")
            lines.append("")

        dart = resonance.get("dart_strategy")
        if dart:
            lines.append("**底部区域观察框架**：")
            for step in dart.get("steps", []):
                lines.append(f"- 第{step['level']}层：{step['condition']} → {step['action']}")
            lines.append(f"- 失效条件：{dart.get('invalid_if', '')}")
            lines.append("")

        mr = resonance.get("market_resonance")
        if mr and mr.get("state") != "未知":
            mr_state = mr.get("state", "")
            mr_conf = mr.get("confidence", "")
            lines.append(f"**市场共振**：{mr_state}（置信度：{mr_conf}）")
            for ev in mr.get("evidence", [])[:3]:
                lines.append(f"- {ev}")
            lines.append(f"- 提示：{mr.get('action_hint', '')}")
            lines.append("")

        lines.append("**结论**：趋势仍可跟踪，但不适合将 RSI 超买、BIAS 偏高或 MACD 背离单独视为卖出信号。")
        lines.append("")

        sell_assessment = resonance.get("sell_assessment")
        if sell_assessment and sell_assessment.get("met_count", 0) >= 1:
            met = sell_assessment["met_count"]
            rec = sell_assessment["recommendation"]
            lines.append(f"**卖出三要素**：满足 {met}/3 条，{rec}。")
            lines.append("")

        adv_lines = []
        for name, info in advisors.items():
            meaning = info.get("meaning", "")
            adv_lines.append(f"{name.upper()}：{info.get('state', '—')}（{meaning}）")
        if adv_lines:
            lines.append("**谋士团**：" + " | ".join(adv_lines))
            lines.append("")

        bias_extreme = resonance.get("bias_extreme")
        if bias_extreme:
            lines.append(f"**BIAS预警**：{bias_extreme['warning']}（{bias_extreme['level']}）")
            lines.append("")

        false_rebound = resonance.get("false_rebound")
        if false_rebound:
            lines.append(f"**假反弹预警**：{false_rebound['signal']}（{false_rebound['confidence']}）")
            lines.append("")

        false_breakout = resonance.get("false_breakout")
        if false_breakout:
            lines.append(f"**假突破预警**：{false_breakout['signal']}（{false_breakout['confidence']}）")
            lines.append("")

        div = resonance.get("divergence_scan")
        if div:
            lines.append(f"**背离预警**：{div.get('type', '')}（{div.get('confidence', '')}）")
            lines.append(f"处置：{div.get('action', '观望')}")
            lines.append("")

        chart_paths = ctx.get("chart_paths", {})
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)

    def _render_full(self, resonance: Dict, stock_name: str, ctx: Dict) -> str:
        """完整版渲染，包含更多细节。"""
        lines = self._render_compact(resonance, stock_name, ctx).split("\n")
        ts = resonance.get("trend_state", {})
        wb = resonance.get("weekly_background", {})
        ds = resonance.get("daily_structure", {})

        insert_idx = 2
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, "### 1. 趋势背景")
        lines.insert(insert_idx + 2, f"- 周线大背景：{wb.get('trend', '未知')}")
        lines.insert(insert_idx + 3, f"- MA 结构：{wb.get('ma_structure', '未知')}")
        lines.insert(insert_idx + 4, "")
        lines.insert(insert_idx + 5, "### 2. 日线结构")
        lines.insert(insert_idx + 6, f"- MA20 方向：{ds.get('ma20_direction', '未知')}")
        lines.insert(insert_idx + 7, f"- MA60 方向：{ds.get('ma60_direction', '未知')}")
        lines.insert(insert_idx + 8, f"- 价格位置：{ds.get('price_vs_ma20', '未知')} MA20")
        lines.insert(insert_idx + 9, "")
        lines.insert(insert_idx + 10, "### 3. 健康度评分")
        th = resonance.get("trend_health", {})
        _cn = {
            "weekly_structure": "周线结构",
            "daily_ma_alignment": "日线MA趋势",
            "price_structure": "价格结构",
            "volume_confirmation": "成交量确认",
            "volatility_condition": "波动率条件",
        }
        for name, comp in th.get("components", {}).items():
            label = _cn.get(name, name)
            lines.insert(insert_idx + 11, f"- {label}：{comp.get('score', 0)}/{comp.get('max', 0)} ({comp.get('evidence', '')})")
        lines.insert(insert_idx + 12, "")

        # After health score section
        sell_assessment = resonance.get("sell_assessment")
        if sell_assessment and sell_assessment.get("met_count", 0) >= 1:
            lines.insert(insert_idx + 13, "### 卖出三要素评估")
            lines.insert(insert_idx + 14, "")
            offset = insert_idx + 15
            for f in sell_assessment.get("factors", []):
                lines.insert(offset, f"- {f}")
                offset += 1
            lines.insert(offset, f"- 结论：{sell_assessment['recommendation']}（满足 {sell_assessment['met_count']}/3 条）")
            lines.insert(offset + 1, "")

        return "\n".join(lines)

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
