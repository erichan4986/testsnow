"""Pipeline skill for writing Agent-Reach evidence notes to the knowledge base.

This skill is a thin wrapper around ``write_evidence_notes``. It is intentionally
optional and gated: it only runs when both Agent-Reach and evidence notes are
enabled. It does not call LLMs, fetch URLs, or run subprocesses.

All writer exceptions are caught internally so that a knowledge-base write
failure does not abort the rest of the report pipeline.
"""

import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import skill, SkillContext
    from ..evidence_note_writer import write_evidence_notes
else:
    from skill_pipeline import skill, SkillContext
    from evidence_note_writer import write_evidence_notes

logger = logging.getLogger(__name__)


TERMINAL_STATUSES = (
    "disabled",
    "skipped",
    "empty",
    "dry_run",
    "written",
    "completed",
    "error",
)


def _default_plan_dict() -> Dict[str, List[Any]]:
    return {"written": [], "skipped_existing": [], "filtered": []}


def _resolve_base_dir(ctx: SkillContext) -> Path:
    base_dir = ctx.get("knowledge_base_dir")
    if not base_dir:
        base_dir = Path(__file__).resolve().parents[3] / "knowledge"
    return Path(base_dir)


def _make_summary(
    plan_dict: Dict[str, Any],
    dry_run: bool,
    base_dir: Path,
    reason: str,
    collected_at: str,
) -> Dict[str, Any]:
    return {
        "written_count": len(plan_dict.get("written", [])),
        "skipped_existing_count": len(plan_dict.get("skipped_existing", [])),
        "filtered_count": len(plan_dict.get("filtered", [])),
        "dry_run": dry_run,
        "base_dir": str(base_dir),
        "reason": reason,
        "collected_at": collected_at,
    }


def _set_terminal_state(
    ctx: SkillContext,
    status: str,
    reason: str,
    plan_dict: Dict[str, Any] = None,
    summary: Dict[str, Any] = None,
    error: str = "",
) -> SkillContext:
    if plan_dict is None:
        plan_dict = _default_plan_dict()
    if summary is None:
        summary = _make_summary(
            plan_dict=plan_dict,
            dry_run=bool(ctx.get("evidence_notes_dry_run", True)),
            base_dir=_resolve_base_dir(ctx),
            reason=reason,
            collected_at="",
        )
    ctx.set("evidence_note_status", status)
    ctx.set("evidence_note_write_plan", plan_dict)
    ctx.set("evidence_note_summary", summary)
    ctx.set("evidence_note_error", error)
    logger.info(f"[evidence_note_writer] status={status} reason={reason}")
    return ctx


@skill(name="evidence_note_writer")
def evidence_note_writer_skill(ctx: SkillContext) -> SkillContext:
    """Write or dry-run Agent-Reach evidence notes after the quality gate.

    Reads keep/demote items from ctx, calls ``write_evidence_notes``, and writes
    status/plan/summary/error back to ctx. Never mutates the original keep/demote
    lists. Catches all writer exceptions so the pipeline continues.
    """
    stock_name = ctx.get("stock_name", "")
    stock_codes = ctx.get("stock_codes", {}) or {}
    stock_code = stock_codes.get(stock_name, "")

    enable_evidence_notes = bool(ctx.get("enable_evidence_notes", False))
    agent_reach_enabled = bool(ctx.get("agent_reach_enabled", False))
    quality_status = ctx.get("agent_reach_quality_status", "")

    # 1. Disabled gate
    if not enable_evidence_notes:
        return _set_terminal_state(ctx, "disabled", "disabled")

    # 2. Agent-Reach disabled (defensive; builder normally prevents this path)
    if not agent_reach_enabled:
        return _set_terminal_state(ctx, "skipped", "agent_reach_disabled")

    # 3. Quality gate did not produce usable items
    if quality_status != "ok":
        return _set_terminal_state(
            ctx,
            "skipped",
            f"agent_reach_quality_status={quality_status}",
        )

    # Read keep/demote lists defensively and copy them to avoid mutation.
    keep_items: List[Any] = list(ctx.get("agent_reach_keep_items", []) or [])
    demote_items: List[Any] = list(ctx.get("agent_reach_demote_items", []) or [])
    items = keep_items + demote_items

    # 4. No items to process
    if not items:
        return _set_terminal_state(ctx, "empty", "no_keep_or_demote_items")

    dry_run = bool(ctx.get("evidence_notes_dry_run", True))
    base_dir = _resolve_base_dir(ctx)

    collected_at = datetime.now().isoformat()

    try:
        plan = write_evidence_notes(
            stock_name=stock_name,
            stock_code=stock_code,
            items=items,
            base_dir=base_dir,
            collected_at=collected_at,
            dry_run=dry_run,
        )
    except Exception as exc:
        logger.exception("[evidence_note_writer] write_evidence_notes failed")
        return _set_terminal_state(
            ctx,
            "error",
            "writer_error",
            error=str(exc),
        )

    plan_dict = asdict(plan)

    if dry_run:
        status = "dry_run"
        reason = "dry_run"
    else:
        if len(plan_dict.get("written", [])) > 0:
            status = "written"
            reason = "written"
        else:
            status = "completed"
            reason = "no_new_files"

    summary = _make_summary(plan_dict, dry_run, base_dir, reason, collected_at)
    return _set_terminal_state(ctx, status, reason, plan_dict, summary)
