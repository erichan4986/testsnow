"""Deterministic executive-summary data shared by text and image output."""

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class SummaryNode:
    title: str
    detail: str
    substantive: bool


@dataclass(frozen=True)
class ExecutiveSummaryViewModel:
    stock_name: str
    date_str: str
    total_score: str
    ev: str
    recommendation: str
    recommendation_sentence: str
    risk_level: str
    position_cap: str
    fundamental: SummaryNode
    valuation: SummaryNode
    technical: SummaryNode
    action: str

    @property
    def image_ready(self) -> bool:
        return sum(node.substantive for node in (
            self.fundamental, self.valuation, self.technical
        )) >= 2


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _position_cap(*texts: str) -> str:
    for text in texts:
        match = re.search(r"(\d+(?:\.\d+)?)[ \t]*[-–—至][ \t]*(\d+(?:\.\d+)?)[ \t]*%", text or "")
        if match:
            return f"{match.group(1)}-{match.group(2)}%"
    return "证据不足"


def _node(title: str, parts: list[str], substantive: bool) -> SummaryNode:
    return SummaryNode(title, "｜".join(parts) if parts else "证据不足", substantive)


def build_executive_summary_view(ctx: Any) -> ExecutiveSummaryViewModel:
    """Project existing owners without recalculating a report decision."""
    decision = ctx.get("recommendation_decision")
    pillar = ctx.get("pillar") or ctx.get("pillar_scores") or {}
    quote = ctx.get("quote") or {}
    ev = getattr(decision, "ev", None)
    risk = getattr(decision, "risk", None)
    entry = getattr(decision, "entry_constraint", None)
    total = _number(getattr(decision, "total_score", None))
    recommendation = str(getattr(decision, "display_recommendation", "") or "证据不足")
    risk_level = str(getattr(risk, "level", "") or "证据不足")
    position = _position_cap(
        str(getattr(entry, "position_cap_note", "") or ""),
        str(getattr(risk, "position_advice", "") or ""),
    )

    fundamental_score = _number(pillar.get("fundamental"))
    if fundamental_score is None:
        fundamental_title = "基本面证据不足"
    elif fundamental_score >= 8:
        fundamental_title = "结构化基本面信号较强"
    elif fundamental_score >= 6:
        fundamental_title = "结构化基本面信号中性偏强"
    elif fundamental_score >= 4:
        fundamental_title = "结构化基本面信号中性"
    else:
        fundamental_title = "结构化基本面信号偏弱"
    fundamental = _node(
        fundamental_title,
        [f"基本面评分 {fundamental_score:g}/10"] if fundamental_score is not None else [],
        fundamental_score is not None,
    )

    forward_pe = _number(pillar.get("fwd_pe"))
    pe_ttm = _number(quote.get("pe_ttm"))
    eps_growth = _number(pillar.get("eps_growth"))
    valuation_parts = []
    if forward_pe is not None:
        valuation_parts.append(f"Forward PE {forward_pe:.1f}x")
    elif pe_ttm is not None:
        valuation_parts.append(f"PE(TTM) {pe_ttm:.1f}x")
    if eps_growth is not None:
        valuation_parts.append(f"预期 EPS 增速 {eps_growth:+.1f}%")
    valuation = _node(
        "盈利增长正在消化估值" if forward_pe is not None and (eps_growth or 0) > 0 else "估值与盈利预期",
        valuation_parts,
        bool(valuation_parts or getattr(ev, "targets", None)),
    )

    resonance = (((ctx.get("stock_raw") or {}).get("technical") or {}).get("indicators") or {}).get("_resonance") or {}
    trend_state, trend_health = resonance.get("trend_state") or {}, resonance.get("trend_health") or {}
    stage, grade = str(trend_state.get("stage") or "").strip(), str(trend_health.get("grade") or "").strip()
    health = _number(trend_health.get("score"))
    technical_parts = []
    if health is not None:
        technical_parts.append(f"趋势健康度 {health:g}/100")
    if risk_level != "证据不足":
        technical_parts.append(f"风险{risk_level.removesuffix('风险')}")
    if position != "证据不足":
        technical_parts.append(f"仓位 {position}")
    technical = _node(
        " / ".join(filter(None, (grade, stage))) or "技术与风险证据不足",
        technical_parts,
        bool(stage or grade or technical_parts),
    )

    return ExecutiveSummaryViewModel(
        stock_name=str(ctx.get("stock_name") or ""), date_str=str(ctx.get("date_str") or ""),
        total_score=f"{total:g} / 10" if total is not None else "证据不足",
        ev=str(getattr(ev, "ev_display", "") or "证据不足"),
        recommendation=recommendation,
        recommendation_sentence=str(getattr(decision, "recommendation_sentence", "") or recommendation),
        risk_level=risk_level, position_cap=position,
        fundamental=fundamental, valuation=valuation, technical=technical,
        action=recommendation,
    )
