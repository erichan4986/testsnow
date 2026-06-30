# Evidence Note Pipeline Integration Phase 3 — Implementation Notes

**Date**: 2026-06-12  
**Task**: Implement Evidence Note Pipeline Integration Phase 3: add an optional pipeline skill that writes or dry-runs Agent-Reach evidence notes after the quality gate.

---

## Files Changed

| File | Change Type | Reason |
|---|---|---|
| `scripts/utils/report_skills/evidence_note_skill.py` | Created | New pipeline skill wrapping `write_evidence_notes`. |
| `tests/reporter/test_evidence_note_skill.py` | Created | Unit tests covering status machine, dry-run, real write, completed, exception handling, read-only lists, and default base dir. |
| `scripts/utils/report_skills/__init__.py` | Modified | Imported/exported `evidence_note_writer_skill`, added `enable_evidence_notes` parameter, conditionally inserted skill. |
| `scripts/utils/stock_reporter.py` | Modified | Read per-stock `evidence_notes` config and passed `enable_evidence_notes` / `evidence_notes_dry_run` / `knowledge_base_dir` to pipeline. |
| `tests/reporter/test_pipeline_integration.py` | Modified | Added tests for 15-skill pipeline and evidence note writer ordering. |
| `tests/reporter/test_stock_reporter_agent_reach_config.py` | Modified | Updated existing assertions to include `enable_evidence_notes=False`; added 4 new evidence-notes config tests. |
| `docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-implementation-claude-notes.md` | Created | This file. |

---

## Test Results

### Focused Tests

```bash
python3 -m pytest tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/utils/test_evidence_note_writer.py -q
```

**67 passed**

### Broader Tests

```bash
python3 -m pytest tests/utils \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

**168 passed**

No failures, no warnings.

---

## Behavior Summary

### New Skill: `evidence_note_writer_skill`

- Defined in `scripts/utils/report_skills/evidence_note_skill.py`.
- Decorated with `@skill(name="evidence_note_writer")`.
- Pure wrapper: no network/LLM/browser/subprocess calls.
- Reads `agent_reach_keep_items` and `agent_reach_demote_items` defensively (copies them, never mutates).
- Catches all `write_evidence_notes` exceptions internally and returns `status="error"` without re-raising, so the pipeline continues.
- Uses `datetime.now().isoformat()` for `collected_at`.
- Defaults `knowledge_base_dir` to repo-root `knowledge` via `Path(__file__).resolve().parents[3] / "knowledge"`.
- Converts `EvidenceWritePlan` to a plain dict with `dataclasses.asdict(plan)` before storing in `ctx`.

### Status Machine

| Condition | Status | Reason |
|---|---|---|
| `enable_evidence_notes=False` | `disabled` | `disabled` |
| `agent_reach_enabled=False` | `skipped` | `agent_reach_disabled` |
| `agent_reach_quality_status != "ok"` | `skipped` | `agent_reach_quality_status=<status>` |
| keep + demote empty | `empty` | `no_keep_or_demote_items` |
| `evidence_notes_dry_run=True` | `dry_run` | `dry_run` |
| `dry_run=False` and `written_count > 0` | `written` | `written` |
| `dry_run=False` and `written_count == 0` | `completed` | `no_new_files` |
| writer raises | `error` | `writer_error` |

### Pipeline Builder

- `build_stock_report_pipeline()` → 11 skills.
- `build_stock_report_pipeline(enable_agent_reach=True)` → 14 skills.
- `build_stock_report_pipeline(enable_agent_reach=True, enable_evidence_notes=True)` → 15 skills.
- `build_stock_report_pipeline(enable_agent_reach=False, enable_evidence_notes=True)` → 11 skills.
- Insertion order: query → fetch → quality → evidence_note_writer → cross_source_consolidation.

### PerStockReporter Wiring

- Reads `agent_reach_configs[stock]["evidence_notes"]`.
- `enable_evidence_notes` is only passed to the builder when both Agent-Reach and evidence notes are enabled.
- Passes `enable_evidence_notes`, `evidence_notes_dry_run` (default `True`), and optional `knowledge_base_dir` in pipeline input.
- `config/stocks.json` was **not** modified.

---

## Real Knowledge Base Writes

- All real-write tests use `tmp_path` as `knowledge_base_dir`.
- No files were written to the real `knowledge/10-Stocks/**` directory by the new tests.
- The default `knowledge_base_dir` resolves to the repo-root `knowledge/` directory, but it is only exercised in tests via monkeypatch or by explicitly passing `tmp_path`.

---

## Boundary Compliance

The following files were **not modified** in this task:

- `scripts/utils/knowledge_synthesizer.py` ✓
- `scripts/utils/report_skills/synthesis_skills.py` ✓
- `scripts/utils/report_skills/agent_reach_skill.py` ✓
- `scripts/utils/report_skills/agent_reach_quality_skill.py` ✓
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` ✓
- `scripts/utils/reporter/scoring_engine.py` ✓
- `scripts/run_黑芝麻智能.py` ✓
- `scripts/xueqiu_monitor_v2.py` ✓
- `config/stocks.json` ✓
- `knowledge/10-Stocks/**` ✓
- `reports/**` ✓

`xueqiu_monitor_v2.py` was **not run**.

---

## Deviations From Task

None. The implementation follows the task file exactly, including:

- Test-first order.
- Allowed file set only.
- Status machine and data handling rules.
- Plain dict write plan.
- Read-only keep/demote handling.
- Internal exception catching.
- Repo-root knowledge dir resolution.

---

## Notes

- The focused test suite runs slower than the broader suite because `test_evidence_note_skill.py` exercises the real `write_evidence_notes` path (including YAML frontmatter rendering and file I/O) rather than always monkeypatching it.
- The default base-dir test (`test_default_base_dir_resolves_to_repo_root_knowledge`) uses a monkeypatched writer and asserts the received `base_dir` ends with `/testsnow/knowledge`, confirming the `parents[3]` traversal is correct for the repo layout.

---

## Codex Validation Addendum

Codex review found one small shape-consistency gap after implementation:

- no-op statuses (`disabled`, `skipped`, `empty`, and `error`) initially stored `evidence_note_summary` as only `{"reason": ...}`.
- the design describes `evidence_note_summary` as a stable dict with counts, dry-run flag, base dir, reason, and collected_at.

Fix applied during Codex validation:

- `scripts/utils/report_skills/evidence_note_skill.py`
  - added `_default_plan_dict()`
  - added `_resolve_base_dir(ctx)`
  - changed `_set_terminal_state()` so no-op/error statuses also write a stable summary shape
- `tests/reporter/test_evidence_note_skill.py`
  - added `test_noop_status_summary_has_stable_shape`

Additional verification after the fix:

```bash
python3 -m pytest tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py \
  tests/utils/test_evidence_note_writer.py -q
```

Result: `68 passed`

```bash
python3 -m pytest tests/utils \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_agent_reach_evidence_renderer.py -q
```

Result: `168 passed`

Codex also checked:

- importing `utils.report_skills.evidence_note_skill` from `scripts/` cwd works
- default base dir resolves to `/Users/erichan/testsnow/knowledge`
- no files exist under `knowledge/10-Stocks/**/evidence/`

Note: the working tree already contains non-evidence `knowledge/10-Stocks/**` changes dated 2026-06-12 12:32-12:33. These appear unrelated to Phase 3 evidence-note tests, but they should be handled separately before any commit.
