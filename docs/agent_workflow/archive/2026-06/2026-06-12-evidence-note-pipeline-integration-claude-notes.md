# Evidence Note Pipeline Integration Review Round 1

**Date**: 2026-06-12  
**Design file reviewed**: `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-design.md`  
**Scope**: Phase 3 — wire `write_evidence_notes()` into the single-stock deep-report pipeline as an optional, gated skill.

---

## Status

**Ready with changes.**

The overall architecture is sound: the skill is optional, gated by both `enable_agent_reach` and `enable_evidence_notes`, defaults to dry-run, does not touch `KnowledgeSynthesizer`, and preserves the existing 11-skill / 14-skill behavior. A few implementation details must be tightened before coding starts, especially around exception handling and read-only access to the Agent-Reach quality gate outputs.

---

## Findings

### High

- None.

### Medium

1. **Exception handling must be internal to the skill to keep the pipeline non-blocking.**
   - The current `@skill` decorator in `scripts/utils/skill_pipeline.py` logs exceptions and **re-raises** them. If `evidence_note_writer_skill` does not wrap `write_evidence_notes()` in its own `try/except`, a writer failure will abort the entire report pipeline, contradicting the design's "status=error, report generation continues" requirement.
   - **Required clarification**: the design should explicitly state that `evidence_note_skill.py` catches all exceptions internally, writes `evidence_note_status="error"` and `evidence_note_error=<traceback/str>`, and returns the unmodified `ctx`.

2. **The skill must read `agent_reach_keep_items` / `agent_reach_demote_items` without mutating them.**
   - The skill is inserted immediately before `cross_source_consolidation_skill`, which likely consumes the same keep/demote lists. Any mutation (e.g., filtering, popping, or in-place modification) inside the evidence skill could silently change downstream behavior.
   - **Required clarification**: specify that the skill copies or concatenates the lists read-only (`items = list(keep) + list(demote)`), and only writes new `evidence_note_*` keys to `ctx.output`.

3. **Source of `collected_at` is unspecified.**
   - `write_evidence_notes()` takes an optional `collected_at` datetime string. The design does not say where this comes from in the skill context.
   - **Recommendation**: use `ctx.get("date_str")` combined with the current wall-clock time (e.g., `f"{date_str}T{now_iso}"`) or simply use `datetime.now().isoformat()`. Document the chosen fallback so tests can assert deterministic behavior.

4. **`status=written` is slightly ambiguous when no files are physically written.**
   - Status rule 6 says `dry_run=False` with at least "written or skipped/filtered successfully" results in `status="written"`. If all items are skipped due to existing files, the status still says "written" even though zero new files were created.
   - **Recommendation**: either rename the success status to `"completed"`, or add a `written_count` check and use `"written"` only when `written_count > 0`, falling back to `"completed"` (or `"skipped"`) when only existing items are seen. This makes the `evidence_note_summary` easier to interpret.

### Low

1. **Defensive `agent_reach_enabled=False` path may be unreachable via the builder.**
   - The skill is only inserted when `enable_agent_reach=True and enable_evidence_notes=True`, so the `skipped / reason=agent_reach_disabled` branch is mainly testable by calling the skill directly. This is fine, but the design could note that the branch is a safety guard rather than a normal pipeline path.

2. **`evidence_note_write_plan` must be converted from `EvidenceWritePlan` dataclass to a plain dict.**
   - The design correctly asks for a plain dict in `ctx`. The implementation notes should remind the coder to call `dataclasses.asdict(plan)` or an equivalent before `ctx.set("evidence_note_write_plan", ...)`, because `SkillContext` consumers may serialize `ctx.output` to JSON.

3. **`knowledge_base_dir` default should be resolved robustly.**
   - The design says default is "repo root `knowledge`". In the skill, `Path(base_dir).resolve()` or `Path.cwd() / "knowledge"` should be used carefully so tests with `tmp_path` do not accidentally resolve to the real repo. The safest pattern is:
     ```python
     base_dir = ctx.get("knowledge_base_dir") or Path.cwd() / "knowledge"
     ```
     and tests pass an absolute `tmp_path`.

4. **Consider surfacing the `reason` for `skipped` states in `evidence_note_summary`.**
   - Currently only `evidence_note_error` captures the reason for `error`. For `skipped` states (agent_reach_disabled, quality_status not ok), the reason is only in `evidence_note_status`. Adding `reason` to the summary would help debugging in report dumps.

5. **No mention of logging when status is `disabled`/`skipped`/`empty`.**
   - These are silent no-ops. A single `logger.info` line per status would help operators confirm the gate worked as intended without cluttering output.

---

## Required Changes Before Implementation

1. **Add explicit exception-handling requirement.**
   - In `evidence_note_skill.py`, wrap the entire writer call in `try/except Exception`. On failure, set `evidence_note_status="error"`, `evidence_note_error=str(e)`, return `ctx` unchanged otherwise. Do not re-raise.

2. **Specify read-only handling of keep/demote lists.**
   - The skill must copy the lists before passing them to `write_evidence_notes()` and must not modify `ctx.output["agent_reach_keep_items"]` or `ctx.output["agent_reach_demote_items"]`.

3. **Clarify `collected_at` sourcing.**
   - Document that the skill uses `datetime.now().isoformat()` (or `ctx.get("date_str") + current time`) as `collected_at` when calling `write_evidence_notes()`.

4. **Tighten `status=written` semantics or rename the success state.**
   - Either use `"completed"` for all successful non-error/non-dry-run outcomes, or split into `"written"` (when `written_count > 0`) and `"completed"` (when only skips/filters occurred). Update tests accordingly.

5. **Document dataclass-to-dict conversion.**
   - Add a note that `EvidenceWritePlan` is converted to a plain dict before being stored in `ctx`.

---

## Nice To Have

- Add `reason` field to `evidence_note_summary` for all terminal statuses (`disabled`, `skipped`, `empty`, `error`, `dry_run`, `written`).
- Add `logger.info` calls for each terminal status so pipeline execution is auditable.
- Provide a minimal manual smoke-test command using `run_黑芝麻智能.py --fast-test` with `evidence_notes.dry_run=true` only, keeping real writes out of the default validation path.

---

## Files Reviewed

- `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-design.md`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/skill_pipeline.py`
- `scripts/utils/evidence_note_writer.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `docs/agent_workflow/2026-06-12-evidence-note-writer-design.md`
- `docs/agent_workflow/2026-06-12-evidence-note-writer-implementation-claude-notes.md`

---

## Boundary Compliance Check

| Boundary | Design compliant? | Notes |
|---|---|---|
| `KnowledgeSynthesizer` untouched | ✓ | Evidence notes do not enter synthesis. |
| `SynthesisSkill._build_synthesis_items()` untouched | ✓ | Writer only reads keep/demote lists. |
| No LLM calls in evidence skill | ✓ | Writer is pure; skill is a thin wrapper. |
| No scoring/technical/renderer changes | ✓ | Only `__init__.py`, `stock_reporter.py`, and new skill file change. |
| `xueqiu_monitor_v2.py` not used | ✓ | Manual validation uses `run_黑芝麻智能.py --fast-test`. |
| `config/stocks.json` not forced to change | ✓ | Default config leaves feature disabled. |
| Default pipeline remains 11 skills | ✓ | `enable_evidence_notes=False` by default. |
| Agent-Reach-only remains 14 skills | ✓ | Both flags needed to reach 15 skills. |
| Evidence without Agent-Reach falls back to 11 skills | ✓ | Builder ignores `enable_evidence_notes` when Agent-Reach is off. |
| Tests use `tmp_path` for real writes | ✓ | Design specifies `tmp_path` knowledge base dir. |

---

## Round 2 Review

### Status

**Ready to implement.**

All Round 1 required changes have been incorporated into the design. The revised state machine, knowledge-base directory resolution, and test plan are coherent and sufficient for a safe Phase 3 implementation.

---

### Remaining Findings

#### High

- None.

#### Medium

- None.

#### Low

- None.

---

### Implementation Guardrails

Use the guardrails already listed in the design, with the following confirmations:

1. **Knowledge-base directory resolution is correct.**
   - `Path(__file__).resolve().parents[3] / "knowledge"` from `scripts/utils/report_skills/evidence_note_skill.py` resolves to the repo root (`parents[3]` walks up from `report_skills` → `utils` → `scripts` → repo root). This is the right default.

2. **Status machine is complete and unambiguous.**
   - `disabled` → `enable_evidence_notes=False`.
   - `skipped` → `agent_reach_enabled=False` or `agent_reach_quality_status != "ok"`.
   - `empty` → quality ok but no keep/demote items.
   - `dry_run` → `evidence_notes_dry_run=True`.
   - `written` → `dry_run=False` and `written_count > 0`.
   - `completed` → `dry_run=False`, writer succeeded, but `written_count == 0`.
   - `error` → writer raised an exception (caught internally, no pipeline abort).

3. **Test plan covers the critical regression surfaces.**
   - Default pipeline: 11 skills.
   - Agent-Reach only: 14 skills.
   - Agent-Reach + evidence notes: 15 skills.
   - Evidence notes without Agent-Reach: 11 skills.
   - Error status does not escape or abort pipeline.
   - `evidence_note_write_plan` is a plain dict, not an `EvidenceWritePlan` dataclass.
   - Real writes use `tmp_path`, preventing contamination of the real `knowledge/` directory.

4. **No implementation blockers remain.**
   - Boundary compliance is preserved: no changes to `KnowledgeSynthesizer`, `SynthesisSkill`, scoring, renderer, entry scripts, `config/stocks.json`, or `xueqiu_monitor_v2.py`.
