"""Pipeline skill that derives structured risk signals from claim verification.

This skill sits between ``SynthesisSkill`` and ``scoring_skill``. It builds a
full ``ClaimVerificationPlan`` from the local knowledge base (dry-run only) and
converts it to ``structured_risk_signals`` via the conservative helper in
``claim_risk_signals``. It never calls LLMs, fetches URLs, or writes to the
knowledge base.
"""

import logging
from pathlib import Path
from typing import Any, Dict

if __name__.startswith("utils."):
    from ..claim_risk_signals import derive_structured_risk_signals_from_plan
    from ..claim_verification import build_claim_verification_plan, summarize_claim_verification_plan
    from ..skill_pipeline import skill, SkillContext
else:
    from claim_risk_signals import derive_structured_risk_signals_from_plan
    from claim_verification import build_claim_verification_plan, summarize_claim_verification_plan
    from skill_pipeline import skill, SkillContext

logger = logging.getLogger(__name__)


def _set_state(
    ctx: SkillContext,
    status: str,
    signals: list = None,
    summary: Dict[str, Any] = None,
    claim_verification_summary: Dict[str, Any] = None,
    error: str = "",
) -> SkillContext:
    if signals is None:
        signals = []
    if summary is None:
        summary = {"signal_count": len(signals), "signals": []}
    ctx.set("structured_risk_signals", signals)
    ctx.set("claim_risk_signal_status", status)
    ctx.set("claim_risk_signal_summary", summary)
    ctx.set("claim_risk_signal_error", error)
    if claim_verification_summary:
        ctx.set("claim_verification_summary", claim_verification_summary)
    logger.info(f"[claim_risk_signal] status={status} count={len(signals)} error={error}")
    return ctx


@skill(name="claim_risk_signal")
def claim_risk_signal_skill(ctx: SkillContext) -> SkillContext:
    """Derive structured risk signals from the full claim verification plan.

    Reads ``stock_name`` and optional ``claim_verification_base_dir`` from ctx.
    When disabled, writes empty signals and status ``disabled``.
    """
    if not bool(ctx.get("enable_claim_risk_signals", False)):
        return _set_state(ctx, "disabled")

    stock_name = ctx.get("stock_name", "")
    if not stock_name:
        return _set_state(ctx, "error", error="missing stock_name")

    base_dir = ctx.get("claim_verification_base_dir")
    if not base_dir:
        base_dir = Path(__file__).resolve().parents[3] / "knowledge"
    base_dir = Path(base_dir)

    try:
        plan = build_claim_verification_plan(stock_name, base_dir, dry_run=True)
        signals = derive_structured_risk_signals_from_plan(plan)
        claim_verification_summary = summarize_claim_verification_plan(plan)
        summary = {
            "signal_count": len(signals),
            "signals": [
                {"name": s["name"], "status": s["status"], "confidence": s["confidence"]}
                for s in signals
            ],
        }
        status = "ok" if signals else "empty"
        return _set_state(
            ctx,
            status,
            signals=signals,
            summary=summary,
            claim_verification_summary=claim_verification_summary,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[claim_risk_signal] failed to derive risk signals")
        return _set_state(ctx, "error", error=str(exc))
