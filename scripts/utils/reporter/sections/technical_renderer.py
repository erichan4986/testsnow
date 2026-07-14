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

        # Corporate action warning
        corp_warning = resonance.get("corporate_action_warning")
        if corp_warning and corp_warning.get("has_recent_action"):
            lines.append(f"> **数据提醒**：{corp_warning['message']}")
            if corp_warning.get("note"):
                lines.append(f"> **注意**：{corp_warning['note']}")
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

        # 评分子项表格
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
            # P2-5: 综合评分雷达摘要
            radar_text = self._build_radar_summary(components, score)
            if radar_text:
                lines.append(f"📊 **综合评分摘要**：{radar_text}")
                lines.append("")

        # P2-1: 信号优先级排序 — 多个预警并存时突出最重要的一条
        priority = self._pick_priority_signal(resonance)
        if priority:
            lines.append(f"> **优先关注 — {priority['emoji']}**：{priority['text']}**")
            if priority.get('detail'):
                lines.append(f"> 依据：{priority['detail']}")
            lines.append("")

        lines.append("**关键观察位**：")
        sz = kl.get("support_zone")
        rz = kl.get("resistance_zone")
        sr_diag = kl.get("diagnostics")
        if sz:
            lines.append(f"- 支撑区：【{sz.get('zone_low', '—')} - {sz.get('zone_high', '—')}】（{sz.get('strength', '弱')}）")
        else:
            lines.append("- 支撑区：暂无可靠支撑区")
            if sr_diag:
                reason = sr_diag.get('reason')
                if reason:
                    lines.append(f"  - 原因：{reason}")
                touches = sr_diag.get('valid_support_touches')
                req = sr_diag.get('required_touches')
                if touches is not None and req is not None:
                    if touches < req:
                        lines.append(f"  - 诊断：满足有效反弹条件的谷点仅 {touches} 次（需≥{req} 次）")
                    else:
                        lines.append(f"  - 诊断：谷点触及 {touches} 次已满足要求，但分布在多个价位未形成聚集区")
                raw_v = sr_diag.get('raw_valleys')
                if raw_v is not None:
                    lines.append(f"  - 原始极值点：{raw_v} 个谷点（部分因反弹幅度不足被过滤）")
        if rz:
            lines.append(f"- 压力区：【{rz.get('zone_low', '—')} - {rz.get('zone_high', '—')}】（{rz.get('strength', '弱')}）")
        else:
            lines.append("- 压力区：暂无可靠压力区")
            if sr_diag:
                reason = sr_diag.get('reason')
                if reason:
                    lines.append(f"  - 原因：{reason}")
                touches = sr_diag.get('valid_resistance_touches')
                req = sr_diag.get('required_touches')
                if touches is not None and req is not None:
                    if touches < req:
                        lines.append(f"  - 诊断：满足有效回落条件的峰点仅 {touches} 次（需≥{req} 次）")
                    else:
                        lines.append(f"  - 诊断：峰点触及 {touches} 次已满足要求，但分布在多个价位未形成聚集区")
                raw_p = sr_diag.get('raw_peaks')
                if raw_p is not None:
                    lines.append(f"  - 原始极值点：{raw_p} 个峰点（部分因回落幅度不足被过滤）")

        # 当支撑/压力区缺失时，补充 MA 观察位
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

        raw_daily_structure = resonance.get("daily_structure", {})
        if isinstance(raw_daily_structure, str) and raw_daily_structure:
            lines.append(f"**日线结构**：{raw_daily_structure}")
            lines.append("")
        ds = self._as_dict(raw_daily_structure)
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
            # P2-4: 水平箱体时给出具体操作建议
            if ch_state == "水平箱体" and channel.get("breakout_status") == "未突破":
                upper = channel.get("upper")
                lower = channel.get("lower")
                if upper is not None and lower is not None:
                    if pos == "接近上轨":
                        lines.append(f"- 建议：箱体上沿（{upper:.2f}）附近承压，若无量能配合突破，宜减仓或观望")
                    elif pos == "接近下轨":
                        lines.append(f"- 建议：箱体下沿（{lower:.2f}）附近关注支撑有效性，若企稳可观察低吸机会")
                    elif pos == "中部":
                        lines.append(f"- 建议：箱体中部（{lower:.2f}-{upper:.2f}）方向不明，观望等待突破确认")
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

        # P2-2: 市场/板块共振 — 表格化三线并排
        mr = resonance.get("market_resonance")
        if mr:
            mr_state = mr.get("state", "未知")
            mr_conf = mr.get("confidence", "低")
            impact = mr.get("impact", "")
            relative = mr.get("relative_strength", "未知")
            missing = mr.get("missing", [])

            # 从 evidence 解析个股/大盘/行业趋势
            trend_map = {}
            for ev in mr.get("evidence", []):
                if "：" in ev:
                    k, v = ev.split("：", 1)
                    trend_map[k] = v

            lines.append(f"**市场/板块共振**：{mr_state}（置信度：{mr_conf}）")
            lines.append("| 维度 | 趋势状态 | 备注 |")
            lines.append("|------|----------|------|")
            stock_stage = trend_map.get("个股趋势", ts.get("stage", "未知"))
            lines.append(f"| 个股 | {stock_stage} | — |")
            if "大盘趋势" in trend_map:
                lines.append(f"| 大盘 | {trend_map['大盘趋势']} | — |")
            if "行业趋势" in trend_map:
                rel = relative if relative != "未知" else "—"
                lines.append(f"| 行业 | {trend_map['行业趋势']} | 个股相对行业：{rel} |")
            lines.append("")

            if impact:
                lines.append(f"- 影响：{impact}")
            proxy_notes = [m for m in missing if m.startswith("以")]
            if proxy_notes:
                lines.append(f"- 说明：{'; '.join(proxy_notes[:2])}")
            lines.append(f"- 提示：{mr.get('action_hint', '')}")
            lines.append("")

        # 所属概念板块
        tech_raw = ctx.get("stock_raw", {}).get("technical", {})
        concept_blocks = tech_raw.get("concept_blocks")
        if concept_blocks and concept_blocks.get("concept_tags"):
            tags = concept_blocks["concept_tags"][:8]
            lines.append(f"**所属概念板块**：{', '.join(tags)}")
            lines.append("")

        # 近5日资金流向
        fund_flow = tech_raw.get("fund_flow")
        if fund_flow and isinstance(fund_flow, list) and len(fund_flow) > 0:
            lines.append("**近5日资金流向**（万元）：")
            for row in fund_flow[:5]:
                date = row.get("date", "")
                main_in = row.get("main_in", "")
                change = row.get("change_pct", "")
                lines.append(f"- {date}: 主力净流入 {main_in}万，涨跌 {change}%")
            lines.append("")

        # 动态结论：基于实际状态生成，避免模板残留无关内容
        conclusion = self._build_conclusion(ts, th, inv, advisors, bottom, resonance)
        lines.append(f"**结论**：{conclusion}")
        lines.append("")

        sell_assessment = resonance.get("sell_assessment")
        if sell_assessment and sell_assessment.get("met_count", 0) >= 1:
            met = sell_assessment["met_count"]
            rec = sell_assessment["recommendation"]
            lines.append(f"**卖出三要素**：满足 {met}/3 条，{rec}。")
            lines.append("")

        if advisors:
            lines.append("**谋士团**：")
            lines.append("| 指标 | 状态 | 含义 |")
            lines.append("|------|------|------|")
            for name, info in advisors.items():
                lines.append(f"| {name.upper()} | {info.get('state', '—')} | {info.get('meaning', '')} |")
            lines.append("")

        bias_extreme = resonance.get("bias_extreme")
        if bias_extreme:
            lines.append(f"**BIAS预警**：{bias_extreme['warning']}（{bias_extreme['level']}）")
            ev = bias_extreme.get("evidence")
            if ev:
                lines.append(f"- BIAS(5) = {ev.get('bias_5', 'N/A')}% | BIAS(10) = {ev.get('bias_10', 'N/A')}%")
                lines.append(f"- 判定标准：{ev.get('threshold_desc', 'N/A')}（回看窗口：{ev.get('window', 'N/A')}）")
            lines.append("")

        false_rebound = resonance.get("false_rebound")
        if false_rebound:
            lines.append(f"**假反弹预警**：{false_rebound['signal']}（{false_rebound['confidence']}）")
            lines.append(f"- 触发依据：{false_rebound.get('reason', 'N/A')}")
            lines.append("")

        false_breakout = resonance.get("false_breakout")
        if false_breakout:
            lines.append(f"**假突破预警**：{false_breakout['signal']}（{false_breakout['confidence']}）")
            lines.append(f"- 触发依据：{false_breakout.get('reason', 'N/A')}")
            lines.append("")

        div = resonance.get("divergence_scan")
        if div:
            lines.append(f"**背离预警**：{div.get('type', '')}（{div.get('confidence', '')}）")
            ev = div.get("evidence")
            if ev:
                boll = ev.get("boll")
                if boll:
                    lines.append(f"- BOLL：收盘价 {boll.get('price', 'N/A')} {boll.get('state', '')}（上轨 {boll.get('upper', 'N/A')} / 下轨 {boll.get('lower', 'N/A')}）")
                rsi = ev.get("rsi")
                if rsi:
                    rsi_val = rsi.get('value')
                    rsi_str = f"{rsi_val:.2f}" if isinstance(rsi_val, (int, float)) else str(rsi_val)
                    lines.append(f"- RSI：{rsi_str} → {rsi.get('state', '')}")
                macd = ev.get("macd")
                if macd:
                    macd_hist = macd.get('hist')
                    macd_str = f"{macd_hist:.2f}" if isinstance(macd_hist, (int, float)) else str(macd_hist)
                    lines.append(f"- MACD柱线：{macd_str} → {macd.get('state', '')}")
            lines.append(f"- 处置：{div.get('action', '观望')}")
            lines.append("")

        price_target = tech_raw.get("price_target")
        lines.extend(self._render_target_judgment(resonance, price_target, tech_raw.get("indicators", {})))

        chart_paths = ctx.get("chart_paths", {})
        tech_chart = chart_paths.get("technical")
        if tech_chart:
            lines.append("### 技术面综合图")
            lines.append("")
            lines.append(f"![{stock_name} 技术面分析]({tech_chart})")
            lines.append("")

        return "\n".join(lines)

    def _render_target_judgment(self, resonance: Dict, price_target: Any, indicators: Dict) -> list[str]:
        if not isinstance(price_target, dict) and not resonance.get("judgment"):
            return []
        raw_target = price_target if isinstance(price_target, dict) else {}
        judgment = _technical_judgment(resonance, raw_target, indicators)
        target = judgment["target"]
        mode = target["display_mode"]
        lines = ["**价格目标分析**", ""]
        if mode == "unavailable":
            return lines + ["> 当前技术证据不足，暂不展示目标价。", ""]
        if mode == "blocked":
            return lines + [f"> 当前目标被阻断：{target['reason_code']}。等待阻断条件消除后重新评估。", ""]
        if mode == "levels_only":
            return lines + ["> 当前仅展示支撑、压力与失效条件，不展示精确目标价。", ""]

        values = raw_target.get("targets") if isinstance(raw_target.get("targets"), dict) else raw_target
        labels = [("conservative", "保守"), ("base", "基准")]
        if mode == "full_targets":
            labels.append(("aggressive", "激进"))
        rows = []
        for key, label in labels:
            value = values.get(key)
            if isinstance(value, (int, float)):
                rows.append(f"| {label} | {value:.2f} |")
        if mode == "conditional_range":
            return lines + ([f"> 条件测算区间：{rows[0].split('|')[2].strip()} 至 {rows[-1].split('|')[2].strip()}，尚待触发确认。", ""] if len(rows) >= 2 else ["> 当前结构仅支持条件观察。", ""])
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

    def _render_full(self, resonance: Dict, stock_name: str, ctx: Dict) -> str:
        """完整版渲染，包含更多细节。"""
        lines = self._render_compact(resonance, stock_name, ctx).split("\n")
        ts = resonance.get("trend_state", {})
        wb = self._as_dict(resonance.get("weekly_background", {}))
        raw_daily_structure = resonance.get("daily_structure", {})
        ds = self._as_dict(raw_daily_structure)
        daily_summary = raw_daily_structure if isinstance(raw_daily_structure, str) else ""

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
        if daily_summary:
            lines.insert(insert_idx + 9, f"- 结构摘要：{daily_summary}")
            lines.insert(insert_idx + 10, "")
        else:
            lines.insert(insert_idx + 9, "")
        # After daily structure section
        sell_assessment = resonance.get("sell_assessment")
        if sell_assessment and sell_assessment.get("met_count", 0) >= 1:
            lines.insert(insert_idx + 10, "### 卖出三要素评估")
            lines.insert(insert_idx + 11, "")
            offset = insert_idx + 12
            for f in sell_assessment.get("factors", []):
                lines.insert(offset, f"- {f}")
                offset += 1
            lines.insert(offset, f"- 结论：{sell_assessment['recommendation']}（满足 {sell_assessment['met_count']}/3 条）")
            lines.insert(offset + 1, "")

        return "\n".join(lines)

    def _pick_priority_signal(self, resonance: Dict) -> Dict | None:
        """从多个预警中选出优先级最高的一条。"""
        candidates = []

        div = resonance.get("divergence_scan")
        if div:
            candidates.append({
                "rank": 1,
                "emoji": "背离预警",
                "text": div.get("type", "背离预警"),
                "detail": f"置信度 {div.get('confidence', '')}，处置：{div.get('action', '观望')}",
            })

        bias = resonance.get("bias_extreme")
        if bias:
            candidates.append({
                "rank": 2,
                "emoji": "BIAS预警",
                "text": bias.get("warning", "BIAS极端"),
                "detail": f"等级：{bias.get('level', '')}",
            })

        fb = resonance.get("false_breakout")
        if fb:
            candidates.append({
                "rank": 3,
                "emoji": "假突破预警",
                "text": fb.get("signal", "假突破"),
                "detail": fb.get("reason", ""),
            })

        fr = resonance.get("false_rebound")
        if fr:
            candidates.append({
                "rank": 4,
                "emoji": "假反弹预警",
                "text": fr.get("signal", "假反弹"),
                "detail": fr.get("reason", ""),
            })

        if not candidates:
            return None
        best = min(candidates, key=lambda x: x["rank"])
        return best

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

    def _build_conclusion(self, ts: dict, th: dict, inv: dict, advisors: dict, bottom: dict | None, resonance: dict) -> str:
        """基于实际状态生成结论文案，避免模板残留无关内容。"""
        primary = ts.get("primary_state", "")
        stage = ts.get("stage", "")
        score = th.get("score", 0)

        is_weak = score < 50 or stage == "破坏期" or primary == "下降趋势"

        if is_weak:
            parts = ["中期趋势已走弱" if primary == "下降趋势" else "趋势结构转弱"]
        else:
            parts = ["趋势仍可跟踪"]

        active_warnings = []

        bias = advisors.get("bias", {})
        bias_state = bias.get("state", "")
        if "偏高" in bias_state or "正偏离" in bias_state:
            active_warnings.append("BIAS 偏高")
        elif "负偏离" in bias_state:
            active_warnings.append("BIAS 负偏离")

        rsi = advisors.get("rsi", {})
        rsi_state = rsi.get("state", "")
        if "超买" in rsi_state or "钝化" in rsi_state:
            active_warnings.append("RSI 超买/钝化")
        elif "超卖" in rsi_state:
            active_warnings.append("RSI 超卖")

        divergence = resonance.get("divergence_scan")
        if divergence and "背离" in divergence.get("type", ""):
            active_warnings.append("MACD 背离")

        if active_warnings:
            parts.append(f"但不适合将 {'、'.join(active_warnings)} 单独视为买卖信号")

        if primary == "震荡转弱" and "临界" in stage:
            parts.append("日线跌破MA20，中期结构转弱，需观察能否收回MA60；若连续收盘无法收回，则中期结构破坏风险进一步上升")
        elif primary == "下降趋势":
            parts.append("建议降低仓位或观望")

        if bottom and bottom.get("state") != "none":
            parts.append("底部区域仅作观察，不构成买入信号")

        return "。".join(parts) + "。"
