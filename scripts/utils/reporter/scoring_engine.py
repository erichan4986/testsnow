"""评分引擎 — 纯计算逻辑，无外部 I/O，无副作用。"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def classify_sentiment(posts: List[Dict]) -> tuple:
    """简单情感分类"""
    bullish_keywords = ["涨", "利好", "突破", "买入", "看好", "反弹", "业绩", "增长",
                        "目标", "翻倍", "冲锋", "加油", "坚定", "持有", "难得", "龙头"]
    bearish_keywords = ["跌", "利空", "卖出", "看空", "下跌", "暴雷", "减持", "亏损",
                        "爆仓", "割", "陷阱", "恶心", "砸", "做空", "退", "不敢买"]

    bullish = []
    bearish = []
    neutral = []

    for p in posts:
        text = p.get("title", "") + " " + p.get("content", "")
        b_score = sum(1 for k in bullish_keywords if k in text)
        e_score = sum(1 for k in bearish_keywords if k in text)

        if b_score > e_score:
            bullish.append(p)
        elif e_score > b_score:
            bearish.append(p)
        else:
            neutral.append(p)

    return bullish, bearish, neutral


def sentiment_ratio(posts: List[Dict]) -> Dict[str, float]:
    """计算雪球帖子看多/看空/中性比例。"""
    bullish, bearish, neutral = classify_sentiment(posts)
    total = len(posts)
    if total == 0:
        return {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0, "total": 0}
    return {
        "bullish": round(len(bullish) / total * 100, 1),
        "bearish": round(len(bearish) / total * 100, 1),
        "neutral": round(len(neutral) / total * 100, 1),
        "total": total,
    }


def compute_pillar_scores(
    stock_raw: Dict,
    posts: List[Dict],
    quote: Optional[Dict],
    consensus: Optional[Dict],
    industry_fwd_pe: Optional[float],
    ps: Optional[float] = None,
) -> Dict:
    """计算五维度得分（0-10 制），返回各维度分和原始中间值。"""
    tech = stock_raw.get("technical", {})
    indicators = tech.get("indicators", {}) if isinstance(tech, dict) else {}
    fund = stock_raw.get("fundflow", [])
    sentiment = sentiment_ratio(posts)

    price = quote.get("price", 0) if quote else 0
    fwd_pe = None
    peg = None
    eps_growth = None
    if consensus and consensus.get("eps_current") and price:
        fwd_pe = price / consensus["eps_current"]
        if consensus.get("eps_next") and consensus["eps_current"]:
            eps_growth = ((consensus["eps_next"] / consensus["eps_current"]) - 1) * 100
            peg = fwd_pe / eps_growth if eps_growth else None

    # 1. 估值健康度 (B) — 0-10
    valuation_score = 5.0
    uses_ps = False
    pe_ttm = quote.get("pe_ttm") if quote else None

    # 亏损股：fwd_pe <= 0 或 pe_ttm <= 0 时，用 PS 替代 PE
    is_loss_making = (fwd_pe is not None and fwd_pe <= 0) or (pe_ttm is not None and pe_ttm <= 0)
    if is_loss_making:
        uses_ps = True
        if ps and ps > 0:
            if ps < 3:
                valuation_score = 10.0
            elif ps < 5:
                valuation_score = 8.0
            elif ps < 8:
                valuation_score = 6.0
            elif ps < 12:
                valuation_score = 4.0
            elif ps < 20:
                valuation_score = 2.0
            else:
                valuation_score = 0.0
        else:
            valuation_score = 1.0  # 亏损且无 PS 数据，给最低分
    elif fwd_pe and industry_fwd_pe and industry_fwd_pe > 0:
        ratio = fwd_pe / industry_fwd_pe
        if ratio <= 1.0:
            valuation_score = 10.0
        elif ratio >= 2.5:
            valuation_score = 0.0
        else:
            valuation_score = 10.0 * (2.5 - ratio) / 1.5
    elif fwd_pe:
        if fwd_pe < 30:
            valuation_score = 9.0
        elif fwd_pe < 50:
            valuation_score = 7.0
        elif fwd_pe < 80:
            valuation_score = 5.0
        elif fwd_pe < 120:
            valuation_score = 3.0
        else:
            valuation_score = 1.0
    valuation_score = round(max(0.0, min(10.0, valuation_score)), 1)

    # 2. 技术面强度 (M) — 0-10
    tech_score = 5.0
    rsi = indicators.get("rsi_14")
    macd = indicators.get("macd")
    ma20 = indicators.get("ma_20")
    close = indicators.get("close")
    if rsi is not None:
        if 45 <= rsi <= 65:
            tech_score += 1.5
        elif rsi > 70 or rsi < 30:
            tech_score -= 1.5
    if macd is not None:
        tech_score += 1.0 if macd > 0 else -1.0
    if close and ma20:
        tech_score += 1.0 if close > ma20 else -1.0
    tech_score = round(max(0.0, min(10.0, tech_score)), 1)

    # 3. 情绪面温度 (M) — 0-10（中性偏乐观最佳，过热扣分）
    bullish_pct = sentiment.get("bullish", 0)
    if bullish_pct > 80:
        sentiment_score = 8.0
    elif bullish_pct > 50:
        sentiment_score = 7.0
    elif bullish_pct > 30:
        sentiment_score = 5.0
    else:
        sentiment_score = 3.0
    sentiment_score = round(max(0.0, min(10.0, sentiment_score)), 1)

    # 4. 基本面趋势 (B) — 0-10
    fundamental_score = 5.0
    if eps_growth is not None:
        if eps_growth > 50:
            fundamental_score = 10.0
        elif eps_growth > 30:
            fundamental_score = 8.0
        elif eps_growth > 10:
            fundamental_score = 6.0
        elif eps_growth > 0:
            fundamental_score = 4.0
        else:
            fundamental_score = 2.0
    fundamental_score = round(max(0.0, min(10.0, fundamental_score)), 1)

    # 5. 资金关注度 (M) — 0-10
    fund_score = 5.0
    if fund:
        recent = fund[:5]
        total_main = sum(f.get("main_inflow", 0) for f in recent)
        if total_main > 50000:
            fund_score = 9.0
        elif total_main > 0:
            fund_score = 7.0
        elif total_main > -30000:
            fund_score = 4.0
        else:
            fund_score = 2.0
    fund_score = round(max(0.0, min(10.0, fund_score)), 1)

    return {
        "valuation": valuation_score,
        "technical": tech_score,
        "sentiment": sentiment_score,
        "fundamental": fundamental_score,
        "fundflow": fund_score,
        "fwd_pe": fwd_pe,
        "peg": peg,
        "eps_growth": eps_growth,
        "industry_fwd_pe": industry_fwd_pe,
        "price": price,
        "bullish_pct": bullish_pct,
        "bearish_pct": sentiment.get("bearish", 0),
        "has_fund": bool(fund),
        "indicators": indicators,
        "ps": ps,
        "uses_ps": uses_ps,
    }


def ev_expectation(pillar: Dict, consensus: Optional[Dict]) -> Dict:
    """
    EV Expectation Model（AlphaGBM 启发）
    EV = upside_prob * upside_range - downside_prob * downside_range
    Weighted = 50% short-term(1w) + 30% medium-term(1m) + 20% long-term(3m)
    """
    price = pillar.get("price", 0)
    fwd_pe = pillar.get("fwd_pe")
    if not price or not fwd_pe or not consensus or not consensus.get("eps_next"):
        return {"ev": None, "ev_pct": None, "recommendation": "N/A", "details": {}}

    eps_next = consensus["eps_next"]
    target_opt = fwd_pe * eps_next * 1.2
    target_base = fwd_pe * eps_next
    target_pes = fwd_pe * eps_next * 0.7

    upside_range = target_opt / price - 1
    downside_range = max(0.0, 1 - target_pes / price)

    v = pillar["valuation"]
    t = pillar["technical"]
    s = pillar["sentiment"]
    f = pillar["fundamental"]
    fd = pillar["fundflow"]

    p_up_short = (t * 0.6 + fd * 0.4) / 10.0
    p_down_short = 1.0 - p_up_short
    ev_short = p_up_short * upside_range - p_down_short * downside_range

    p_up_medium = (s * 0.5 + f * 0.5) / 10.0
    p_down_medium = 1.0 - p_up_medium
    upside_medium = target_base / price - 1
    ev_medium = p_up_medium * upside_medium - p_down_medium * downside_range

    p_up_long = v / 10.0
    p_down_long = 1.0 - p_up_long
    ev_long = p_up_long * upside_medium - p_down_long * downside_range

    weighted_ev = ev_short * 0.5 + ev_medium * 0.3 + ev_long * 0.2
    ev_pct = round(weighted_ev * 100, 2)

    if ev_pct > 8:
        rec = "STRONG_BUY"
        rec_cn = "强烈看多"
    elif ev_pct > 3:
        rec = "BUY"
        rec_cn = "看多"
    elif ev_pct > -3:
        rec = "HOLD"
        rec_cn = "持有"
    elif ev_pct > -8:
        rec = "AVOID"
        rec_cn = "谨慎"
    else:
        rec = "STRONG_AVOID"
        rec_cn = "回避"

    return {
        "ev": round(weighted_ev, 4),
        "ev_pct": ev_pct,
        "recommendation": rec,
        "recommendation_cn": rec_cn,
        "details": {
            "short": {"p_up": round(p_up_short, 2), "ev": round(ev_short, 4), "weight": 0.5},
            "medium": {"p_up": round(p_up_medium, 2), "ev": round(ev_medium, 4), "weight": 0.3},
            "long": {"p_up": round(p_up_long, 2), "ev": round(ev_long, 4), "weight": 0.2},
            "upside_range": round(upside_range * 100, 1),
            "downside_range": round(downside_range * 100, 1),
        },
        "targets": {
            "optimistic": round(target_opt, 1),
            "base": round(target_base, 1),
            "pessimistic": round(target_pes, 1),
        },
    }


def composite_score_section(
    stock_name: str,
    posts: List[Dict],
    stock_raw: Dict,
    quote: Optional[Dict],
    consensus: Optional[Dict],
    industry_fwd_pe: Optional[float],
) -> str:
    """
    G = B + M 综合评分（0-10） + EV Expectation Model + 目标价区间 + AI 推荐。
    """
    ps = quote.get("ps") if quote else None
    pillar = compute_pillar_scores(stock_raw, posts, quote, consensus, industry_fwd_pe, ps)
    ev = ev_expectation(pillar, consensus)

    total_score = round(
        pillar["valuation"] * 0.30 +
        pillar["technical"] * 0.25 +
        pillar["sentiment"] * 0.20 +
        pillar["fundamental"] * 0.15 +
        pillar["fundflow"] * 0.10,
        1,
    )

    price_lines = []
    targets = ev.get("targets", {})
    if targets and pillar["price"]:
        price = pillar["price"]
        for key, label in [("optimistic", "乐观"), ("base", "基准"), ("pessimistic", "悲观")]:
            val = targets.get(key)
            if val is not None:
                pct = (val / price - 1) * 100
                price_lines.append(f"| {label} | {val:.1f} 元 | {'+' if pct >= 0 else ''}{pct:.1f}% |")

    ev_details = ev.get("details", {})
    ev_lines = []
    if ev.get("ev_pct") is not None:
        ev_lines = [
            "",
            "### EV Expectation（预期价值模型）",
            "",
            "| 期限 | 权重 | 上涨概率 | EV |",
            "|------|------|----------|-----|",
            f"| 短期(1周) | {ev_details.get('short', {}).get('weight', 0.5):.0%} | {ev_details.get('short', {}).get('p_up', 0):.0%} | {ev_details.get('short', {}).get('ev', 0) * 100:+.2f}% |",
            f"| 中期(1月) | {ev_details.get('medium', {}).get('weight', 0.3):.0%} | {ev_details.get('medium', {}).get('p_up', 0):.0%} | {ev_details.get('medium', {}).get('ev', 0) * 100:+.2f}% |",
            f"| 长期(3月) | {ev_details.get('long', {}).get('weight', 0.2):.0%} | {ev_details.get('long', {}).get('p_up', 0):.0%} | {ev_details.get('long', {}).get('ev', 0) * 100:+.2f}% |",
            f"| **加权 EV** | — | — | **{ev['ev_pct']:+.2f}%** |",
            "",
            f"*Upside Range: {ev_details.get('upside_range', 0):.1f}% / Downside Range: {ev_details.get('downside_range', 0):.1f}%*",
        ]

    rec_cn = ev.get("recommendation_cn", "N/A")
    reasons = []
    if pillar["valuation"] >= 7:
        reasons.append("估值健康度良好")
    elif pillar["valuation"] <= 3:
        reasons.append("估值偏高需警惕")

    if pillar["technical"] >= 7:
        reasons.append("技术面偏强")
    elif pillar["technical"] <= 3:
        reasons.append("技术面偏弱")

    if pillar["fundamental"] >= 7:
        reasons.append("基本面趋势向上")
    elif pillar["fundamental"] <= 3:
        reasons.append("基本面承压")

    if pillar["bullish_pct"] > 60:
        reasons.append(f"社区情绪偏乐观（看多 {pillar['bullish_pct']:.0f}%）")
    elif pillar["bullish_pct"] < 30:
        reasons.append(f"社区情绪偏谨慎（看多 {pillar['bullish_pct']:.0f}%）")

    recommendation = (
        f"**{rec_cn}** — 加权 EV {ev.get('ev_pct', 'N/A'):+.2f}%。"
        f"{'；'.join(reasons)}。当前风险评分请参考「综合风险评分」板块。"
    ) if ev.get("ev_pct") is not None else (
        f"**{rec_cn}** — {'；'.join(reasons)}。数据不足，无法计算 EV。"
    )

    fwd_pe_str = f"{pillar['fwd_pe']:.1f}" if pillar.get('fwd_pe') else 'N/A'
    ind_pe_str = f"{pillar['industry_fwd_pe']:.1f}" if pillar.get('industry_fwd_pe') else 'N/A'
    eps_str = f"{pillar['eps_growth']:.1f}" if pillar.get('eps_growth') else 'N/A'
    rsi_val = pillar['indicators'].get('rsi_14')
    macd_val = pillar['indicators'].get('macd')
    rsi_str = f"{rsi_val:.1f}" if isinstance(rsi_val, (int, float)) else 'N/A'
    macd_str = f"{macd_val:.1f}" if isinstance(macd_val, (int, float)) else 'N/A'

    ev_pct = ev.get('ev_pct')
    ev_str = f"{ev_pct:+.2f}" if ev_pct is not None else 'N/A'

    # 亏损股：用 PS 替代 PE 显示
    if pillar.get("uses_ps"):
        ps_str = f"{pillar.get('ps', 'N/A')}" if pillar.get('ps') is not None else 'N/A'
        val_desc = f"PS(TTM) {ps_str}（亏损股，PE 不适用）"
    else:
        val_desc = f"Forward PE {fwd_pe_str} vs 行业均值 {ind_pe_str}"

    lines = [
        "## 一、综合评分与推荐",
        "",
        f"### 综合评分: {total_score}/10 | EV: {ev_str}%（{rec_cn}）",
        "",
        "| 维度 | 权重 | 得分(0-10) | 说明 |",
        "|------|------|------------|------|",
        f"| 估值健康度(B) | 30% | {pillar['valuation']} | {val_desc} |",
        f"| 技术面强度(M) | 25% | {pillar['technical']} | RSI {rsi_str}, MACD {macd_str} |",
        f"| 情绪面温度(M) | 20% | {pillar['sentiment']} | 看多 {pillar['bullish_pct']:.0f}% / 看空 {pillar['bearish_pct']:.0f}% |",
        f"| 基本面趋势(B) | 15% | {pillar['fundamental']} | 预期 EPS 增速 {eps_str}% |",
        f"| 资金关注度(M) | 10% | {pillar['fundflow']} | 近5日主力净流入 {'有' if pillar['has_fund'] else '无数据'} |",
        "",
        f"> **AI 综合推荐**：{recommendation}",
    ]

    if price_lines:
        lines.extend([
            "",
            "### 目标价区间（基于一致预期 EPS）",
            "",
            "| 情景 | 目标价 | 相对当前潜在涨跌 |",
            "|------|--------|------------------|",
        ])
        lines.extend(price_lines)

    lines.extend(ev_lines)
    return "\n".join(lines)


def risk_score_section(
    stock_name: str,
    posts: List[Dict],
    stock_raw: Dict,
    quote: Optional[Dict],
    consensus: Optional[Dict],
    industry_fwd_pe: Optional[float],
    watch_points_md: str = "",
    synthesis_text: str = "",
) -> str:
    """
    综合风险评分 0-10（加法模型）。
    watch_points_md: 可选的关注要点 Markdown（由调用方提供）。
    synthesis_text: LLM 合成叙事文本，用于提取定性风险信号。
    """
    tech = stock_raw.get("technical", {})
    indicators = tech.get("indicators", {}) if isinstance(tech, dict) else {}
    sentiment = sentiment_ratio(posts)

    price = quote.get("price", 0) if quote else 0
    fwd_pe = None
    peg = None
    if consensus and consensus.get("eps_current") and price:
        fwd_pe = price / consensus["eps_current"]
        if consensus.get("eps_next") and consensus["eps_current"]:
            growth = ((consensus["eps_next"] / consensus["eps_current"]) - 1) * 100
            peg = fwd_pe / growth if growth else None

    monthly_return = indicators.get("monthly_return_pct")
    avg_amount = indicators.get("avg_amount_yi")
    close = indicators.get("close")
    ma20 = indicators.get("ma_20")

    risk_factors = []
    total_risk = 0.0

    if fwd_pe and industry_fwd_pe and fwd_pe > industry_fwd_pe * 2:
        risk_factors.append(("估值过高", f"Forward PE {fwd_pe:.1f} > 行业均值 {industry_fwd_pe:.1f} 的 2 倍", 2.0))
        total_risk += 2.0
    elif peg and peg > 2:
        risk_factors.append(("估值过高", f"PEG {peg:.2f} > 2", 2.0))
        total_risk += 2.0

    if monthly_return is not None and monthly_return > 30:
        risk_factors.append(("涨幅过大", f"近一月涨幅 {monthly_return:.1f}% > 30%", 2.0))
        total_risk += 2.0

    bullish_pct = sentiment.get("bullish", 0)
    if bullish_pct > 80:
        risk_factors.append(("情绪过热", f"雪球看多占比 {bullish_pct:.0f}% > 80%", 1.5))
        total_risk += 1.5

    if close and ma20 and close < ma20:
        risk_factors.append(("技术破位", f"当前价 {close:.2f} < MA20 {ma20:.2f}", 1.0))
        total_risk += 1.0

    if avg_amount is not None and avg_amount < 5:
        risk_factors.append(("流动性差", f"近20日日均成交 {avg_amount:.2f} 亿 < 5 亿", 1.0))
        total_risk += 1.0

    # 从 LLM 合成文本中提取定性风险信号
    if synthesis_text:
        text_lower = synthesis_text.lower()
        qualitative_signals = [
            ("业绩预期下调", ["下调", "不及预期", "miss", "净利润为负", "亏损加剧"], 1.5),
            ("竞争格局恶化", ["竞争格局恶化", "价格战", "降价", "挤压", "洗牌"], 1.5),
            ("盈利压力", ["盈利压力", "毛利率承压", "费用扩张", "利润侵蚀"], 1.0),
            ("资金流出", ["净流出", "减持", "做空", "流出压力", "退通"], 1.0),
            ("技术路线风险", ["技术路线", "架构迭代", "不确定性", "替代"], 1.0),
        ]
        for signal_name, keywords, score in qualitative_signals:
            if any(kw in text_lower for kw in keywords):
                # 避免重复加分（检查是否已存在类似因子）
                if not any(f[0] == signal_name for f in risk_factors):
                    risk_factors.append((signal_name, "LLM 合成文本识别", score))
                    total_risk += score

    total_risk = min(10.0, round(total_risk, 1))

    if total_risk <= 2:
        risk_level = "低风险"
        position_advice = "积极配置，最大仓位 20%"
    elif total_risk <= 5:
        risk_level = "中等风险"
        position_advice = "谨慎持有，仓位 10-15%"
    elif total_risk <= 7:
        risk_level = "高风险"
        position_advice = "控制仓位，5-10%"
    else:
        risk_level = "极高风险"
        position_advice = "建议减仓或不买入"

    lines = [
        "## 六、综合风险评分",
        "",
        f"### 风险等级: {total_risk}/10（{risk_level}）",
        "",
        f"> **仓位建议**: {position_advice}",
        "",
    ]

    if risk_factors:
        lines.extend([
            "| 风险因子 | 状态 | 加分 |",
            "|----------|------|------|",
        ])
        for name, status, score in risk_factors:
            lines.append(f"| {name} | {status} | +{score} |")
        lines.append("")
    else:
        lines.append("当前未触发主要风险因子，整体风险可控。")
        lines.append("")

    if watch_points_md:
        if "### 关注要点" in watch_points_md:
            watch_section = watch_points_md.split("### 关注要点")[-1]
        elif "- " in watch_points_md:
            lines_in = watch_points_md.split("\n")
            watch_lines = [l for l in lines_in if l.strip().startswith("-") or l.strip().startswith("*")]
            if watch_lines:
                watch_section = "\n".join(watch_lines)
            else:
                watch_section = ""
        else:
            watch_section = ""
        if watch_section:
            lines.append("### 关注要点")
            lines.append(watch_section.strip())
            lines.append("")

    return "\n".join(lines)


def valuation_industry_judgment(stock_name: str, pe_ttm: float, pe_fwd: float, peg: Optional[float], mcap: float) -> str:
    """基于产业逻辑给出估值判断"""
    judgments = {
        "黑芝麻智能": f"- **产业视角**: 黑芝麻智能为港股智驾芯片标的，当前市值 {mcap:.0f} 亿港币。智驾芯片行业处于渗透率快速提升期，高成长赛道通常可享受更高估值溢价。但需警惕港股通退通风险对估值体系的压制。",
        "长春高新": f"- **产业视角**: 长春高新当前 PE-TTM {pe_ttm:.1f} 已处于历史低位，反映市场对集采和竞争格局恶化的极度悲观。若业绩能企稳回升，存在估值修复空间；但若继续下滑，低估值陷阱风险仍在。",
        "三花智控": f"- **产业视角**: 三花智控作为特斯拉机器人核心供应商，当前估值包含大量未来订单预期。Forward PE {pe_fwd:.1f} 是否合理，取决于 5-6 月订单催化能否兑现。若订单落地，估值有望切换至 2027 年；若落空，存在业绩和估值双杀风险。",
        "中简科技": f"- **产业视角**: 中简科技为军工碳纤维高端标的，军工行业订单具有强季节性，PE 波动较大。当前估值需结合 Q2 订单恢复情况判断。若航空发动机碳纤维应用取得突破，将打开十倍级市场空间，当前估值远未反映。",
        "圣邦股份": f"- **产业视角**: 模拟芯片行业正处于周期反转+国产替代双击窗口。圣邦作为龙头，Forward PE {pe_fwd:.1f} 在周期上行阶段具有合理性。但需跟踪杰华特在 MOS 领域的竞争进展，以及涨价周期能否持续。",
        "乐鑫科技": f"- **产业视角**: 乐鑫科技当前市值 {mcap:.0f} 亿，市场仍将其视为'Wi-Fi 芯片商'。若端侧 AI 平台定位获得认可，估值体系有望从硬件 PE 切换至平台型 PS。S31 新品的导入进度是估值重构的关键催化剂。",
    }
    return judgments.get(stock_name, f"- **产业视角**: 当前估值需结合行业景气度和公司基本面综合判断。Forward PE {pe_fwd:.1f} 是否合理，取决于业绩增速能否达到市场预期。")


# ---------------------------------------------------------------------------
# 行业特有风险因子评估（亏损芯片企业专项）
# ---------------------------------------------------------------------------

def _黑芝麻智能_chip_risk_table() -> str:
    """黑芝麻智能 —— 亏损智驾芯片企业特有风险因子"""
    factors = [
        ("毛利率远低于同行", "41% vs 地平线64.5%，差距23.5pct，产品议价能力弱", 8.0),
        ("研发烧钱率畸高", "研发14.17亿 / 营收8.22亿 = 172%，远超自身造血能力", 9.0),
        ("规模效应不足", "营收8.22亿仅为地平线37.6亿的21.8%，固定成本摊薄困难", 7.0),
        ("大客户自研替代", "比亚迪自研4nm璇玑A3（700+TOPS），黑芝麻C1236面临被替换风险", 9.0),
        ("客户集中度极高", "高度依赖比亚迪供应链，单一客户收入占比过高", 7.0),
        ("国际巨头降维打击", "英伟达N1X、高通舱驾一体方案在高端市场压制国产芯片空间", 6.0),
        ("解禁持续抛压", "2025年2月解禁后，低成本股份持续套现，压制股价估值", 8.0),
        ("核心人物减持", "前三人物行权并减持期权股份，内部人卖出信号强烈", 7.0),
        ("港股通退通风险", "市值110亿港币，退通红线约65亿，股价跌至10港币即触发", 6.0),
        ("应收周转恶化", "应收周转165.9天，同行Mobileye仅28.8天，资金占用严重", 5.0),
    ]
    return _build_chip_risk_table("黑芝麻智能", "亏损智驾芯片企业", factors)


def _build_chip_risk_table(stock_name: str, category: str, factors: List[tuple]) -> str:
    """构建亏损芯片企业特有风险因子 Markdown 表格。"""
    avg_score = round(sum(f[2] for f in factors) / len(factors), 1) if factors else 0.0

    lines = [
        f"## 五、行业特有风险因子评估（{category}专项）",
        "",
        f"> 本模块针对 **{stock_name}** 作为 {category} 的特殊风险结构，补充传统 PE/PEG 模型无法覆盖的维度。",
        "",
        "| 风险因子 | 现状 | 风险等级(0-10) |",
        "|---------|------|---------------|",
    ]
    for name, status, score in factors:
        # 用星级可视化
        stars = "★" * int(score // 2) + "☆" * (5 - int(score // 2))
        lines.append(f"| {name} | {status} | **{score:.1f}** {stars} |")

    lines.extend([
        "",
        f"**综合特有风险评分: {avg_score}/10**",
        "",
        "> 评分说明：10分为极其严重影响，0分为无影响。上述评分与传统加法风险模型形成互补参考，",
        "> 反映的是亏损芯片企业在财务替代指标、竞争格局、客户结构和资本市场层面的结构性风险。",
        "",
    ])
    return "\n".join(lines)


def industry_specific_risk_table(stock_name: str) -> str:
    """
    行业/个股特有风险因子分析表。
    针对亏损芯片企业等特殊情况，补充传统估值指标无法捕捉的风险维度。
    返回 Markdown 字符串；如该股票无特定定义，返回空字符串。
    """
    tables = {
        "黑芝麻智能": _黑芝麻智能_chip_risk_table,
    }
    fn = tables.get(stock_name)
    return fn() if fn else ""
