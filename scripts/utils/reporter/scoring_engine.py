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


def _technical_score_from_indicators(indicators: Dict[str, Any]) -> tuple[float, str]:
    """Compute technical pillar score from the richest available signal.

    The advanced technical analyzer writes trend health into
    indicators["_resonance"]["trend_health"]. When present, that score is the
    canonical medium-term technical view and should drive the report-level
    pillar. Older cached payloads fall back to RSI/MACD/MA20.
    """
    resonance = indicators.get("_resonance", {}) if isinstance(indicators, dict) else {}
    trend_health = resonance.get("trend_health", {}) if isinstance(resonance, dict) else {}
    health_score = trend_health.get("score") if isinstance(trend_health, dict) else None

    if isinstance(health_score, (int, float)):
        score = round(max(0.0, min(10.0, float(health_score) / 10.0)), 1)
        trend_state = resonance.get("trend_state", {}) if isinstance(resonance, dict) else {}
        primary = trend_state.get("primary_state", "") if isinstance(trend_state, dict) else ""
        stage = trend_state.get("stage", "") if isinstance(trend_state, dict) else ""
        if primary == "下降趋势" or stage == "破坏期":
            score = min(score, 4.0)
        return score, "trend_health"

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
    return round(max(0.0, min(10.0, tech_score)), 1), "legacy_indicators"


def compute_pillar_scores(
    stock_raw: Dict,
    posts: List[Dict],
    quote: Optional[Dict],
    consensus: Optional[Dict],
    industry_fwd_pe: Optional[float],
    ps: Optional[float] = None,
) -> Optional[Dict]:
    """计算五维度得分（0-10 制），返回各维度分和原始中间值。
    当 quote 缺失或 price 为 0 时返回 None（数据不足，无法评分）。
    """
    if not quote:
        return None

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
    tech_score, technical_score_source = _technical_score_from_indicators(indicators)

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
        "technical_score_source": technical_score_source,
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
    pillar: Optional[Dict] = None,
    recommendation_decision: Optional["RecommendationDecision"] = None,
) -> str:
    """
    G = B + M 综合评分（0-10） + EV Expectation Model + 目标价区间 + AI 推荐。
    如果传入 pillar 则直接使用，否则基于 posts 重新计算。
    如果传入 recommendation_decision，header 和推荐标签直接采用该决策，避免与摘要不一致。
    """
    if recommendation_decision is not None:
        header_line = recommendation_decision.render_header()
        display_rec_cn = recommendation_decision.display_recommendation
        recommendation_sentence = recommendation_decision.recommendation_sentence
        # For table bodies, still compute a local pillar if not already provided.
        if pillar is None:
            ps = quote.get("ps") if quote else None
            pillar = compute_pillar_scores(stock_raw, posts, quote, consensus, industry_fwd_pe, ps)
        if pillar is None:
            return "\n## 一、综合评分与推荐\n\n> **数据不足，暂无法评分。**\n\n"
    else:
        if pillar is None:
            ps = quote.get("ps") if quote else None
            pillar = compute_pillar_scores(stock_raw, posts, quote, consensus, industry_fwd_pe, ps)
        if pillar is None:
            return "\n## 一、综合评分与推荐\n\n> **数据不足，暂无法评分。**\n\n"
        ev = ev_expectation(pillar, consensus)
        total_score = round(
            pillar["valuation"] * 0.30 +
            pillar["technical"] * 0.25 +
            pillar["sentiment"] * 0.20 +
            pillar["fundamental"] * 0.15 +
            pillar["fundflow"] * 0.10,
            1,
        )
        rec_cn = ev.get("recommendation_cn", "N/A")
        display_rec_cn = rec_cn
        entry_guardrail = _entry_quality_guardrail(stock_raw)
        entry_composite_note = ""
        if entry_guardrail and entry_guardrail.get("level") == "entry_blocked" and rec_cn in ("强烈看多", "看多"):
            display_rec_cn = entry_guardrail["composite_label"]
            entry_composite_note = entry_guardrail["composite_note"]
        ev_pct = ev.get('ev_pct')
        ev_str = f"{ev_pct:+.2f}%" if ev_pct is not None else 'N/A'
        header_line = f"### 综合评分: {total_score}/10 | EV: {ev_str}（{display_rec_cn}）"

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

        bullish_pct = pillar.get("bullish_pct", 0) or 0
        if bullish_pct > 60:
            reasons.append(f"社区情绪偏乐观（看多 {bullish_pct:.0f}%）")
        elif bullish_pct < 30:
            reasons.append(f"社区情绪偏谨慎（看多 {bullish_pct:.0f}%）")

        recommendation_sentence = (
            f"**{display_rec_cn}** — 加权 EV {ev.get('ev_pct', 'N/A'):+.2f}%。"
            f"{'；'.join(reasons)}。"
            f"{entry_composite_note}"
            f"当前风险评分请参考「综合风险评分」板块。"
        ) if ev.get("ev_pct") is not None else (
            f"**{display_rec_cn}** — {'；'.join(reasons)}。"
            f"{entry_composite_note}"
            f"数据不足，无法计算 EV。"
        )

    ev = ev_expectation(pillar, consensus)

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

    fwd_pe_str = f"{pillar['fwd_pe']:.1f}" if pillar.get('fwd_pe') else 'N/A'
    ind_pe_str = f"{pillar['industry_fwd_pe']:.1f}" if pillar.get('industry_fwd_pe') else 'N/A'
    eps_str = f"{pillar['eps_growth']:.1f}" if pillar.get('eps_growth') else 'N/A'
    indicators = pillar.get("indicators") or {}
    rsi_val = indicators.get('rsi_14')
    macd_val = indicators.get('macd')
    rsi_str = f"{rsi_val:.1f}" if isinstance(rsi_val, (int, float)) else 'N/A'
    macd_str = f"{macd_val:.1f}" if isinstance(macd_val, (int, float)) else 'N/A'
    tech_desc = f"RSI {rsi_str}, MACD {macd_str}"
    if pillar.get("technical_score_source") == "trend_health":
        resonance = indicators.get("_resonance", {}) if isinstance(indicators, dict) else {}
        trend_health = resonance.get("trend_health", {}) if isinstance(resonance, dict) else {}
        trend_state = resonance.get("trend_state", {}) if isinstance(resonance, dict) else {}
        health_score = trend_health.get("score")
        grade = trend_health.get("grade", "")
        stage = trend_state.get("stage", "")
        parts = []
        if health_score is not None:
            parts.append(f"趋势健康度 {health_score}/100")
        if grade:
            parts.append(f"等级 {grade}")
        if stage:
            parts.append(f"阶段 {stage}")
        if parts:
            tech_desc = "，".join(parts)

    # 亏损股：用 PS 替代 PE 显示
    if pillar.get("uses_ps"):
        ps_str = f"{pillar.get('ps', 'N/A')}" if pillar.get('ps') is not None else 'N/A'
        val_desc = f"PS(TTM) {ps_str}（亏损股，PE 不适用）"
    else:
        val_desc = f"Forward PE {fwd_pe_str} vs 行业均值 {ind_pe_str}"

    lines = [
        "## 一、综合评分与推荐",
        "",
        header_line,
        "",
        "| 维度 | 权重 | 得分(0-10) | 说明 |",
        "|------|------|------------|------|",
        f"| 估值健康度(B) | 30% | {pillar['valuation']} | {val_desc} |",
        f"| 技术面强度(M) | 25% | {pillar['technical']} | {tech_desc} |",
        f"| 情绪面温度(M) | 20% | {pillar['sentiment']} | 看多 {pillar.get('bullish_pct', 0):.0f}% / 看空 {pillar.get('bearish_pct', 0):.0f}% |",
        f"| 基本面趋势(B) | 15% | {pillar['fundamental']} | 预期 EPS 增速 {eps_str}% |",
        f"| 资金关注度(M) | 10% | {pillar['fundflow']} | 近5日主力净流入 {'有' if pillar.get('has_fund') else '无数据'} |",
        "",
        f"> **AI 综合推荐**：{recommendation_sentence}",
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


def _technical_position_guardrail(stock_raw: Dict) -> Optional[Dict]:
    """Classify technical regime weakness for position-advice capping.

    Returns a dict with level, capped advice, and explanatory note when the
    technical state is weak; returns None when no guardrail applies.

    Numeric thresholds (score < 30 severe, 30 <= score < 45 moderate) are
    heuristics tied to the current technical analyzer output and are not a
    formal cross-module scoring contract.
    """
    tech = stock_raw.get("technical", {}) if isinstance(stock_raw, dict) else {}
    indicators = tech.get("indicators", {}) if isinstance(tech, dict) else {}
    resonance = indicators.get("_resonance", {}) if isinstance(indicators, dict) else {}
    trend_state = resonance.get("trend_state", {}) if isinstance(resonance, dict) else {}
    trend_health = resonance.get("trend_health", {}) if isinstance(resonance, dict) else {}

    stage = trend_state.get("stage", "") if isinstance(trend_state, dict) else ""
    primary_state = trend_state.get("primary_state", "") if isinstance(trend_state, dict) else ""
    grade = trend_health.get("grade", "") if isinstance(trend_health, dict) else ""
    score = trend_health.get("score") if isinstance(trend_health, dict) else None

    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    numeric_score: Optional[float] = None
    if _is_number(score):
        try:
            numeric_score = float(score)
        except (TypeError, ValueError):
            numeric_score = None

    # Severe guardrail: broken trend / downtrend / trend failure
    if (
        stage == "破坏期"
        or primary_state == "下降趋势"
        or grade == "趋势失效"
        or (numeric_score is not None and numeric_score < 30)
    ):
        return {
            "level": "severe",
            "advice": "趋势破坏期，以观望或防守仓位为主，建议 0-5%",
            "note": "技术状态为 下降趋势 / 破坏期，风险分不低估趋势破坏带来的仓位限制。",
        }

    # Moderate guardrail: weakening trend / elevated breakdown risk
    if (
        stage == "转弱期"
        or grade == "破坏风险高"
        or (numeric_score is not None and 30 <= numeric_score < 45)
    ):
        return {
            "level": "moderate",
            "advice": "趋势转弱，控制仓位，建议 5-10%",
            "note": "技术健康度偏弱，仓位建议已按技术状态降级。",
        }

    return None


def _entry_quality_guardrail(stock_raw: Dict) -> Optional[Dict]:
    """Classify poor entry quality without changing score or EV math."""
    tech = stock_raw.get("technical", {}) if isinstance(stock_raw, dict) else {}
    if not isinstance(tech, dict):
        return None

    price_target = tech.get("price_target", {})
    if isinstance(price_target, dict):
        error_text = str(price_target.get("error", ""))
        reason = str(price_target.get("reason", ""))
        if error_text == "关注/不操作" and "盈亏比不足" in reason:
            return {
                "level": "entry_blocked",
                "advice": "当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%",
                "note": "技术面提示关注/不操作或追高风险，仓位建议已按入场质量降级。",
                "composite_label": "看多但等待入场",
                "composite_note": "技术面提示当前不适合追高，需等待回调或盈亏比改善。",
            }

    indicators = tech.get("indicators", {})
    if not isinstance(indicators, dict):
        return None
    if indicators.get("bias_5_extreme_high") or indicators.get("bias_10_extreme_high"):
        return {
            "level": "overheated_entry",
            "advice": "BIAS严重正偏离，追高风险较大，仓位 5-10%",
            "note": "BIAS处于近期极端高位，仓位建议已按追高风险降级。",
        }

    return None


# Qualitative risk definitions used by risk scoring and structured signal paths.
_QUALITATIVE_SIGNAL_DEFS = {
    "业绩预期下调": ("业绩预期下调", ["下调", "不及预期", "miss", "净利润为负", "亏损加剧"], 1.5),
    "竞争格局恶化": ("竞争格局恶化", ["竞争格局恶化", "价格战", "降价", "挤压", "洗牌"], 1.5),
    "盈利压力": ("盈利压力", ["盈利压力", "毛利率承压", "费用扩张", "利润侵蚀"], 1.0),
    "资金流出": ("资金流出", ["净流出", "减持", "做空", "流出压力", "退通"], 1.0),
    "技术路线风险": ("技术路线风险", ["技术路线", "架构迭代", "不确定性", "替代"], 1.0),
}


def build_risk_assessment(
    stock_name: str,
    posts: List[Dict],
    stock_raw: Dict,
    quote: Optional[Dict],
    consensus: Optional[Dict],
    industry_fwd_pe: Optional[float],
    synthesis_text: str = "",
    structured_risk_signals: Optional[List[Dict]] = None,
    score_llm_keyword_risks: bool = False,
    entry_constraint: Optional[object] = None,
    display_only_external_risks: Optional[List[object]] = None,
) -> "RiskAssessment":
    """Construct a structured risk assessment.

    Mirrors the additive math historically used by `risk_score_section`, but
    routes entry/technical guardrails through the shared `EntryConstraint` so
    the risk section's position advice cannot drift from the recommendation
    label.
    """
    from .recommendation_decision import (
        DisplayOnlyExternalRiskSignal,
        EntryConstraint,
        RiskAssessment,
    )

    if entry_constraint is None:
        entry_constraint = EntryConstraint(
            state="ok",
            label_suffix="",
            display_note="",
            position_cap_note="",
            source="none",
            raw_reason="",
        )
    if display_only_external_risks is None:
        display_only_external_risks = []

    technical_unavailable_reason = _technical_unavailable_reason(stock_raw)
    if technical_unavailable_reason:
        display_only_notes = _display_only_risk_notes(display_only_external_risks)
        return RiskAssessment(
            score=None,
            level="无法评估",
            position_advice="技术行情数据缺失，暂不输出积极配置建议；建议观望或防守仓位 0-5%",
            factors=[],
            formal_notes=[f"技术行情数据缺失：{technical_unavailable_reason}"],
            display_only_notes=display_only_notes,
            special_risk_notes=[],
            keyword_observations=[],
            structured_observations=[],
        )

    tech = stock_raw.get("technical", {}) if isinstance(stock_raw, dict) else {}
    indicators = tech.get("indicators", {}) if isinstance(tech, dict) else {}
    sentiment = sentiment_ratio(posts)

    price = quote.get("price", 0) if isinstance(quote, dict) else 0
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

    factors: List[Dict[str, Any]] = []
    total_risk = 0.0

    if fwd_pe and industry_fwd_pe and fwd_pe > industry_fwd_pe * 2:
        factors.append({
            "name": "估值过高",
            "status": f"Forward PE {fwd_pe:.1f} > 行业均值 {industry_fwd_pe:.1f} 的 2 倍",
            "score": 2.0,
        })
        total_risk += 2.0
    elif peg and peg > 2:
        factors.append({"name": "估值过高", "status": f"PEG {peg:.2f} > 2", "score": 2.0})
        total_risk += 2.0

    if monthly_return is not None and monthly_return > 30:
        factors.append({"name": "涨幅过大", "status": f"近一月涨幅 {monthly_return:.1f}% > 30%", "score": 2.0})
        total_risk += 2.0

    bullish_pct = sentiment.get("bullish", 0)
    if bullish_pct > 80:
        factors.append({"name": "情绪过热", "status": f"雪球看多占比 {bullish_pct:.0f}% > 80%", "score": 1.5})
        total_risk += 1.5

    if close and ma20 and close < ma20:
        factors.append({"name": "技术破位", "status": f"当前价 {close:.2f} < MA20 {ma20:.2f}", "score": 1.0})
        total_risk += 1.0

    if avg_amount is not None and avg_amount < 5:
        factors.append({"name": "流动性差", "status": f"近20日日均成交 {avg_amount:.2f} 亿 < 5 亿", "score": 1.0})
        total_risk += 1.0

    entry_risk_factor = _entry_constraint_current_risk_factor(entry_constraint)
    if entry_risk_factor:
        factors.append(entry_risk_factor)
        total_risk += entry_risk_factor["score"]

    # Collect free-text keyword observations regardless of scoring mode
    keyword_observations: List[tuple] = []
    if synthesis_text:
        text_lower = synthesis_text.lower()
        for signal_name, keywords, score in _QUALITATIVE_SIGNAL_DEFS.values():
            matched = [kw for kw in keywords if kw in text_lower]
            if matched:
                keyword_observations.append((signal_name, matched, score))

    if score_llm_keyword_risks:
        for signal_name, matched, score in keyword_observations:
            if not any(f["name"] == signal_name for f in factors):
                factors.append({
                    "name": signal_name,
                    "status": f"LLM关键词命中: {matched[0]}",
                    "score": score,
                })
                total_risk += score

    # Process structured risk signals
    structured_signals = structured_risk_signals or []
    structured_scored: Dict[str, Dict[str, Any]] = {}
    structured_observations_dict: Dict[str, Dict[str, Any]] = {}
    for signal in structured_signals:
        if not isinstance(signal, dict):
            continue
        name = str(signal.get("name", "")).strip()
        if not name:
            continue

        status = str(signal.get("status", "")).strip().lower()
        confidence = signal.get("confidence", 0)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            confidence = 0

        signal_score = signal.get("score", 0)
        if isinstance(signal_score, bool) or not isinstance(signal_score, (int, float)):
            signal_score = 0

        max_score = _QUALITATIVE_SIGNAL_DEFS.get(name, (name, [], 0))[2]
        known_name = name in _QUALITATIVE_SIGNAL_DEFS

        source = _normalize_structured_risk_source(signal.get("source"))

        evidence_text = _sanitize_citation_markers(str(signal.get("evidence_text", "") or "")).strip()
        matched_terms = signal.get("matched_terms", []) or []
        if isinstance(matched_terms, str):
            matched_terms = [matched_terms]
        elif not isinstance(matched_terms, (list, tuple, set)):
            matched_terms = []
        sanitized_terms = [_sanitize_citation_markers(str(t)) for t in matched_terms]

        effective_score = 0.0
        if known_name and confidence >= 60:
            if status == "verified":
                effective_score = min(float(signal_score), max_score)
            elif status == "supported":
                effective_score = min(float(signal_score) * 0.5, max_score)
                effective_score = round(effective_score * 2) / 2

        current_best = structured_scored.get(name)
        if current_best is None or effective_score > current_best["effective_score"]:
            structured_scored[name] = {
                "name": name,
                "status": status,
                "confidence": confidence,
                "source": source,
                "evidence_text": evidence_text,
                "matched_terms": sanitized_terms,
                "effective_score": effective_score,
                "known_name": known_name,
                "max_score": max_score,
            }

        current_obs = structured_observations_dict.get(name)
        if current_obs is None:
            structured_observations_dict[name] = {
                "name": name,
                "status": status,
                "confidence": confidence,
                "source": source,
                "evidence_text": evidence_text,
                "matched_terms": sanitized_terms,
                "signal_score": signal_score,
                "effective_score": effective_score,
            }
        else:
            if (confidence > current_obs["confidence"] or
                (confidence == current_obs["confidence"] and signal_score > current_obs["signal_score"])):
                structured_observations_dict[name] = {
                    "name": name,
                    "status": status,
                    "confidence": confidence,
                    "source": source,
                    "evidence_text": evidence_text,
                    "matched_terms": sanitized_terms,
                    "signal_score": signal_score,
                    "effective_score": effective_score,
                }

    for info in structured_scored.values():
        if info["effective_score"] > 0:
            display_status = info["status"]
            evidence = info["evidence_text"] or "外部来源"
            factors.append({
                "name": info["name"],
                "status": f"{display_status} / {info['source']} / {evidence}",
                "score": info["effective_score"],
            })
            total_risk += info["effective_score"]

    total_risk = min(10.0, round(total_risk, 1))

    if total_risk <= 2.5:
        risk_level = "低风险"
        position_advice = "积极配置，最大仓位 20%"
    elif total_risk <= 5:
        risk_level = "中等风险"
        position_advice = "谨慎持有，仓位 10-15%"
    elif total_risk <= 7.5:
        risk_level = "偏高风险"
        position_advice = "控制仓位，5-10%"
    elif total_risk <= 9:
        risk_level = "高风险"
        position_advice = "建议减仓或不买入"
    else:
        risk_level = "极高风险"
        position_advice = "建议减仓或不买入"

    # Apply shared entry constraint to position advice
    guardrail_note = ""
    if entry_constraint.state == "severe_technical":
        if position_advice != "建议减仓或不买入":
            position_advice = entry_constraint.position_cap_note
            guardrail_note = entry_constraint.display_note
    elif entry_constraint.state == "weak_trend":
        if position_advice in ("积极配置，最大仓位 20%", "谨慎持有，仓位 10-15%"):
            position_advice = entry_constraint.position_cap_note
            guardrail_note = entry_constraint.display_note
    elif entry_constraint.state in ("wait_for_entry", "overheated"):
        if position_advice == "积极配置，最大仓位 20%":
            position_advice = entry_constraint.position_cap_note
            guardrail_note = entry_constraint.display_note

    formal_notes: List[str] = []
    if guardrail_note:
        formal_notes.append(guardrail_note)

    display_only_notes = _display_only_risk_notes(display_only_external_risks)

    return RiskAssessment(
        score=total_risk,
        level=risk_level,
        position_advice=position_advice,
        factors=factors,
        formal_notes=formal_notes,
        display_only_notes=display_only_notes,
        special_risk_notes=[],
        keyword_observations=keyword_observations if not score_llm_keyword_risks else [],
        structured_observations=list(structured_observations_dict.values()),
    )


def _entry_constraint_current_risk_factor(entry_constraint: object) -> Optional[Dict[str, Any]]:
    """Translate entry/technical constraints into current trading risk points."""
    state = getattr(entry_constraint, "state", "")
    raw_reason = str(getattr(entry_constraint, "raw_reason", "") or "")
    if state == "severe_technical":
        return {
            "name": "趋势失效/破坏期",
            "status": raw_reason or "技术状态为下降趋势、破坏期或趋势失效",
            "score": 4.0,
        }
    if state == "weak_trend":
        return {
            "name": "趋势转弱",
            "status": raw_reason or "技术健康度偏弱",
            "score": 2.0,
        }
    if state == "wait_for_entry":
        return {
            "name": "入场质量不足",
            "status": raw_reason or "价格目标提示关注/不操作",
            "score": 1.5,
        }
    if state == "overheated":
        return {
            "name": "追高风险",
            "status": raw_reason or "BIAS 处于极端高位",
            "score": 2.0,
        }
    return None


def _technical_unavailable_reason(stock_raw: object) -> str:
    if not isinstance(stock_raw, dict):
        return ""
    reason = str(stock_raw.get("technical_unavailable_reason") or "").strip()
    if reason:
        return reason
    technical = stock_raw.get("technical")
    if isinstance(technical, dict):
        return str(technical.get("unavailable_reason") or "").strip()
    return ""


def _display_only_risk_notes(display_only_external_risks: List[object]) -> List[str]:
    from .recommendation_decision import DisplayOnlyExternalRiskSignal

    validated_risks = [
        r for r in display_only_external_risks
        if isinstance(r, DisplayOnlyExternalRiskSignal) and getattr(r, "name", None)
    ]
    if not validated_risks:
        return []
    names = "、".join(r.name for r in validated_risks)
    return [
        "外部观察为 display-only，不计入综合风险评分；"
        f"相关变量（{names}）仅作为人工跟踪项。"
    ]


def render_risk_assessment(
    assessment: "RiskAssessment",
    watch_points_md: str = "",
    keyword_observations: Optional[List[tuple]] = None,
    structured_observations: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Render a RiskAssessment to the legacy Markdown format."""
    keyword_observations = keyword_observations if keyword_observations is not None else assessment.keyword_observations
    structured_observations = structured_observations if structured_observations is not None else assessment.structured_observations
    if assessment.score is None:
        score_line = "### 风险等级: 数据不足（无法评估）"
    else:
        score_line = f"### 风险等级: {assessment.score:.1f}/10（{assessment.level}）"
    lines = [
        "## 综合风险评分",
        "",
        score_line,
        "",
        "> **口径说明**: 综合风险评分衡量本期模型已计分的交易/风控风险因子；"
        "低综合风险不等于买入安全，仍需结合 EV、趋势状态、入场质量与专项风险。",
        "",
        f"> **仓位建议**: {assessment.position_advice}",
    ]
    for note in assessment.formal_notes:
        if "技术行情数据缺失" in note:
            prefix = "> **数据缺口**: "
        else:
            prefix = "> **仓位约束**: " if "趋势" in note or "技术状态" in note or "技术健康度" in note else "> **入场约束**: "
        lines.append(f"{prefix}{note}")
    lines.append("")

    factors = assessment.factors
    if factors:
        lines.extend([
            "| 风险因子 | 状态 | 加分 |",
            "|----------|------|------|",
        ])
        for factor in factors:
            lines.append(f"| {factor['name']} | {factor['status']} | +{factor['score']} |")
        lines.append("")
    elif assessment.score is None:
        lines.append("当前技术行情数据缺失，综合风险评分暂无法评估；不得据此判断为低风险。")
        lines.append("")
    else:
        lines.append("当前未触发主要风险因子，整体风险可控。")
        lines.append("")

    if structured_observations:
        any_scored = any(obs.get("effective_score", 0) > 0 for obs in structured_observations)
        title = "结构化风险观察"
        if not any_scored:
            title = "结构化风险观察（不计分）"
        lines.extend([
            f"### {title}",
            "",
            "| 风险信号 | 来源 | 状态 | 置信度 | 证据 |",
            "|----------|------|------|--------|------|",
        ])
        for obs in structured_observations:
            terms = ", ".join(obs.get("matched_terms", [])) if obs.get("matched_terms") else "—"
            evidence = obs.get("evidence_text") or "—"
            lines.append(
                f"| {obs['name']} | {obs['source']} | {obs['status']} | {obs['confidence']} | {evidence} / {terms} |"
            )
        lines.append("")

    if keyword_observations:
        lines.extend([
            "### LLM文本风险观察（不计分）",
            "",
            "| 风险信号 | 命中词 | 说明 |",
            "|----------|--------|------|",
        ])
        for signal_name, matched, _score in keyword_observations:
            terms = ", ".join(matched)
            lines.append(f"| {signal_name} | {terms} | 自由文本命中，仅提示人工复核 |")
        lines.append("")

    if assessment.display_only_notes:
        for note in assessment.display_only_notes:
            lines.extend(["> **外部观察说明**: " + note, ""])

    if watch_points_md:
        if "### 关注要点" in watch_points_md:
            watch_section = watch_points_md.split("### 关注要点")[-1]
        elif "- " in watch_points_md:
            lines_in = watch_points_md.split("\n")
            watch_lines = [l for l in lines_in if l.strip().startswith("-") or l.strip().startswith("*")]
            watch_section = "\n".join(watch_lines) if watch_lines else ""
        else:
            watch_section = ""
        if watch_section:
            lines.append("### 关注要点")
            lines.append(watch_section.strip())
            lines.append("")

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
    structured_risk_signals: Optional[List[Dict]] = None,
    score_llm_keyword_risks: bool = False,
) -> str:
    """
    综合风险评分 0-10（加法模型）。
    watch_points_md: 可选的关注要点 Markdown（由调用方提供）。
    synthesis_text: LLM 合成叙事文本，用于提取定性风险信号。
    structured_risk_signals: 结构化定性风险信号，按规则影响评分。
    score_llm_keyword_risks: 是否允许 LLM 关键词命中直接加分（旧行为兼容开关，默认关闭）。

    兼容性包装：内部使用 build_risk_assessment + render_risk_assessment，但输出格式
    与历史版本保持一致。
    """
    from .recommendation_decision import EntryConstraint, _classify_entry_constraint

    entry_constraint = _classify_entry_constraint(stock_raw)

    assessment = build_risk_assessment(
        stock_name=stock_name,
        posts=posts,
        stock_raw=stock_raw,
        quote=quote,
        consensus=consensus,
        industry_fwd_pe=industry_fwd_pe,
        synthesis_text=synthesis_text,
        structured_risk_signals=structured_risk_signals,
        score_llm_keyword_risks=score_llm_keyword_risks,
        entry_constraint=entry_constraint,
    )

    return render_risk_assessment(
        assessment,
        watch_points_md=watch_points_md,
    )


def _sanitize_citation_markers(text: str) -> str:
    """Remove inline citation markers like [1] or [^1] from rendered text."""
    import re as _re
    return _re.sub(r"\[\^?\d+\]", "", text)


def _normalize_structured_risk_source(source: object) -> str:
    """Return a conservative display label for structured risk signal source."""
    source_text = str(source or "").strip()
    allowed = {
        "claim_verification",
        "manual",
        "risk_model",
        "structured_risk_signal",
    }
    if source_text in allowed:
        return source_text
    return "外部来源"


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
        f"## 行业特有风险因子评估（{category}专项）",
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
        f"**长期结构性专项风险评分: {avg_score}/10**",
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
