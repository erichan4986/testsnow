"""Central recommendation decision model.

Pure and deterministic: no network calls, no LLM calls, no file writes.
This module owns all decision construction and label formatting for the
report's recommendation, EV, entry constraint, and risk assessment.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _total_score_from_pillar(pillar: Dict[str, Any]) -> Optional[float]:
    """Compute the canonical weighted total score from pillar values."""
    try:
        return round(
            pillar["valuation"] * 0.30
            + pillar["technical"] * 0.25
            + pillar["sentiment"] * 0.20
            + pillar["fundamental"] * 0.15
            + pillar["fundflow"] * 0.10,
            1,
        )
    except (KeyError, TypeError):
        return None


@dataclass(frozen=True)
class EvDecision:
    ev_pct: Optional[float]
    ev_display: str
    raw_label: str
    raw_code: str
    targets: Dict[str, float] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EntryConstraint:
    state: str
    label_suffix: str
    display_note: str
    position_cap_note: str
    source: str
    raw_reason: str


@dataclass(frozen=True)
class RiskAssessment:
    score: Optional[float]
    level: str
    position_advice: str
    factors: List[Dict[str, Any]] = field(default_factory=list)
    formal_notes: List[str] = field(default_factory=list)
    display_only_notes: List[str] = field(default_factory=list)
    special_risk_notes: List[str] = field(default_factory=list)
    keyword_observations: List[tuple] = field(default_factory=list)
    structured_observations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DisplayOnlyExternalRiskSignal:
    name: str
    source_kind: str = ""
    evidence_text: str = ""


@dataclass(frozen=True)
class RecommendationDecision:
    stock_name: str
    total_score: Optional[float]
    total_score_display: str
    ev: EvDecision
    raw_recommendation: str
    display_recommendation: str
    recommendation_sentence: str
    entry_constraint: EntryConstraint
    risk: RiskAssessment
    consistency_notes: List[str] = field(default_factory=list)

    def render_header(self) -> str:
        """Render the canonical `### 综合评分: X/10 | EV: ...（...）` header."""
        score_part = f"{self.total_score}/10" if self.total_score is not None else "数据不足"
        return f"### 综合评分: {score_part} | EV: {self.ev.ev_display}（{self.display_recommendation}）"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _classify_entry_constraint(stock_raw: Dict) -> EntryConstraint:
    """Classify entry/technical constraint from raw technical payload.

    Order matters: severe breakdown is the strongest state; blocked entry and
    overheated are mutually informative but severe always wins.
    """
    tech = stock_raw.get("technical", {}) if isinstance(stock_raw, dict) else {}
    if not isinstance(tech, dict):
        tech = {}

    indicators = tech.get("indicators", {}) if isinstance(tech, dict) else {}
    if not isinstance(indicators, dict):
        indicators = {}

    resonance = indicators.get("_resonance", {}) if isinstance(indicators, dict) else {}
    if not isinstance(resonance, dict):
        resonance = {}

    trend_state = resonance.get("trend_state", {}) if isinstance(resonance, dict) else {}
    if not isinstance(trend_state, dict):
        trend_state = {}
    trend_health = resonance.get("trend_health", {}) if isinstance(resonance, dict) else {}
    if not isinstance(trend_health, dict):
        trend_health = {}

    stage = str(trend_state.get("stage", ""))
    primary_state = str(trend_state.get("primary_state", ""))
    grade = str(trend_health.get("grade", ""))
    score = trend_health.get("score")
    numeric_score: Optional[float] = None
    if _is_number(score):
        try:
            numeric_score = float(score)
        except (TypeError, ValueError):
            numeric_score = None

    # Severe technical breakdown
    if (
        stage == "破坏期"
        or primary_state == "下降趋势"
        or grade == "趋势失效"
        or (numeric_score is not None and numeric_score < 30)
    ):
        return EntryConstraint(
            state="severe_technical",
            label_suffix="风险控制优先",
            display_note="技术状态为 下降趋势 / 破坏期，风险分不低估趋势破坏带来的仓位限制。",
            position_cap_note="趋势破坏期，以观望或防守仓位为主，建议 0-5%",
            source="trend_health",
            raw_reason=f"stage={stage},primary_state={primary_state},grade={grade},score={score}",
        )

    price_target = tech.get("price_target", {}) if isinstance(tech, dict) else {}
    if isinstance(price_target, dict):
        error_text = str(price_target.get("error", ""))
        reason = str(price_target.get("reason", ""))
        if error_text == "关注/不操作":
            return EntryConstraint(
                state="wait_for_entry",
                label_suffix="但等待入场",
                display_note="技术面提示关注/不操作或追高风险，仓位建议已按入场质量降级。",
                position_cap_note="当前入场质量不足，建议等待回调或盈亏比改善，仓位 5-10%",
                source="price_target",
                raw_reason=reason,
            )

    bias_5 = bool(indicators.get("bias_5_extreme_high"))
    bias_10 = bool(indicators.get("bias_10_extreme_high"))
    if bias_5 or bias_10:
        return EntryConstraint(
            state="overheated",
            label_suffix="但避免追高",
            display_note="BIAS处于近期极端高位，仓位建议已按追高风险降级。",
            position_cap_note="BIAS严重正偏离，追高风险较大，仓位 5-10%",
            source="bias",
            raw_reason="bias_5_extreme_high" if bias_5 else "bias_10_extreme_high",
        )

    # Moderate weak trend
    if (
        stage == "转弱期"
        or grade == "破坏风险高"
        or (numeric_score is not None and 30 <= numeric_score < 45)
    ):
        return EntryConstraint(
            state="weak_trend",
            label_suffix="趋势转弱",
            display_note="技术健康度偏弱，仓位建议已按技术状态降级。",
            position_cap_note="趋势转弱，控制仓位，建议 5-10%",
            source="trend_health",
            raw_reason=f"stage={stage},grade={grade},score={score}",
        )

    return EntryConstraint(
        state="ok",
        label_suffix="",
        display_note="",
        position_cap_note="",
        source="none",
        raw_reason="",
    )


_POSITIVE_LABELS = {"强烈看多", "看多"}


def _apply_entry_constraint(raw_label: str, constraint: EntryConstraint) -> str:
    """Apply entry constraint to a positive raw label.

    Non-positive labels must never be upgraded.
    """
    if raw_label not in _POSITIVE_LABELS:
        return raw_label

    if constraint.state == "wait_for_entry":
        return "看多但等待入场"
    if constraint.state == "overheated":
        return "看多但避免追高"
    if constraint.state == "severe_technical":
        return "风险控制优先"
    return raw_label


def _build_recommendation_sentence(
    raw_label: str,
    display_label: str,
    ev: EvDecision,
    entry_constraint: EntryConstraint,
) -> str:
    """Build a concise recommendation sentence matching section 1 style."""
    if ev.ev_pct is not None:
        sentence = f"**{display_label}** — 加权 EV {ev.ev_display}。"
    else:
        sentence = f"**{display_label}** — 数据不足，无法计算 EV。"
    if entry_constraint.display_note:
        sentence += entry_constraint.display_note
    return sentence


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_recommendation_decision(
    stock_name: str,
    posts: List[Dict],
    stock_raw: Dict,
    quote: Optional[Dict],
    consensus: Optional[Dict],
    industry_fwd_pe: Optional[float],
    pillar: Optional[Dict] = None,
    synthesis_text: str = "",
    structured_risk_signals: Optional[List[Dict]] = None,
    score_llm_keyword_risks: bool = False,
    display_only_external_risks: Optional[List[DisplayOnlyExternalRiskSignal]] = None,
) -> RecommendationDecision:
    """Build a single source of truth for recommendation, EV, entry, and risk."""
    from .scoring_engine import build_risk_assessment, compute_pillar_scores, ev_expectation

    # Ensure we have a pillar; if missing, compute it from upstream data.
    if pillar is None:
        ps = quote.get("ps") if isinstance(quote, dict) else None
        pillar = compute_pillar_scores(stock_raw, posts, quote, consensus, industry_fwd_pe, ps)

    total_score: Optional[float] = None
    total_score_display = "数据不足"
    ev = EvDecision(
        ev_pct=None,
        ev_display="N/A",
        raw_label="N/A",
        raw_code="N/A",
        targets={},
        details={},
    )

    if pillar is not None:
        total_score = _total_score_from_pillar(pillar)
        if total_score is not None:
            total_score_display = str(total_score)

        ev_result = ev_expectation(pillar, consensus)
        ev_pct = ev_result.get("ev_pct")
        if ev_pct is None:
            ev_display = "N/A"
        else:
            ev_display = f"{ev_pct:+.2f}%"
        raw_label = ev_result.get("recommendation_cn") or "N/A"
        raw_code = ev_result.get("recommendation") or "N/A"
        ev = EvDecision(
            ev_pct=ev_pct,
            ev_display=ev_display,
            raw_label=raw_label,
            raw_code=raw_code,
            targets=ev_result.get("targets", {}),
            details=ev_result.get("details", {}),
        )

    entry_constraint = _classify_entry_constraint(stock_raw)
    display_recommendation = _apply_entry_constraint(ev.raw_label, entry_constraint)

    # Build risk assessment using the same entry constraint so label and
    # position advice cannot drift.
    risk = build_risk_assessment(
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
        display_only_external_risks=display_only_external_risks,
    )

    recommendation_sentence = _build_recommendation_sentence(
        ev.raw_label, display_recommendation, ev, entry_constraint
    )

    return RecommendationDecision(
        stock_name=stock_name,
        total_score=total_score,
        total_score_display=total_score_display,
        ev=ev,
        raw_recommendation=ev.raw_label,
        display_recommendation=display_recommendation,
        recommendation_sentence=recommendation_sentence,
        entry_constraint=entry_constraint,
        risk=risk,
    )
