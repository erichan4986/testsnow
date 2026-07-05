"""Pipeline skill for structured A-share source intake."""

import logging
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
    from ..source_adapter import SynthesisItem
    from .. import a_stock_source_intake as _a_stock_source_intake
else:
    from skill_pipeline import skill, SkillContext
    from source_adapter import SynthesisItem
    import a_stock_source_intake as _a_stock_source_intake

logger = logging.getLogger(__name__)


@skill(name="a_stock_source_intake")
def a_stock_source_intake_skill(ctx: SkillContext) -> SkillContext:
    """Collect structured A-share sources and write normalized items to ctx.

    Reads ``source_intake_enabled`` and ``source_intake_config`` from ctx.
    When disabled, writes empty/disabled state and exits without importing
    akshare or making network calls.
    """
    stock_name = ctx.get("stock_name", "")
    stock_codes = ctx.get("stock_codes", {}) or {}
    stock_code = stock_codes.get(stock_name, "")
    enabled = bool(ctx.get("source_intake_enabled", False))
    config = ctx.get("source_intake_config", {}) or {}

    if not enabled:
        ctx.set("source_intake_status", "disabled")
        ctx.set("source_intake_items", [])
        ctx.set("source_intake_summary", {"status": "disabled", "count": 0})
        ctx.set("source_intake_error", "")
        return ctx

    if not stock_code:
        ctx.set("source_intake_status", "error")
        ctx.set("source_intake_items", [])
        ctx.set("source_intake_summary", {"status": "error", "count": 0})
        ctx.set("source_intake_error", "missing stock_code")
        logger.warning("[a_stock_source_intake] enabled but stock_code missing")
        return ctx

    try:
        result = _a_stock_source_intake.collect_a_stock_source_items(
            stock_name=stock_name,
            stock_code=stock_code,
            config=config,
        )
    except Exception as exc:
        logger.exception("[a_stock_source_intake] helper failed")
        ctx.set("source_intake_status", "error")
        ctx.set("source_intake_items", [])
        ctx.set("source_intake_summary", {"status": "error", "count": 0})
        ctx.set("source_intake_error", str(exc))
        return ctx

    items = result.get("items", [])
    if not isinstance(items, list):
        items = []

    # Defensive copy to avoid mutating helper output.
    ctx.set("source_intake_status", result.get("status", "ok"))
    ctx.set("source_intake_items", list(items))
    ctx.set("source_intake_summary", result.get("source_statuses", {}))
    ctx.set("source_intake_error", "; ".join(result.get("warnings", [])))
    logger.info(f"[a_stock_source_intake] status={result.get('status')} items={len(items)}")
    return ctx
