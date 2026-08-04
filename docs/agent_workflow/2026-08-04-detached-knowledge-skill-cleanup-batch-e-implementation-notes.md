# Batch E Implementation Notes

## Scope

Removed the detached `KnowledgePersistenceSkill` implementation and its isolated tests. The active report pipeline, `ReportRunPlan`, `PerStockReporter`, and the specialized evidence/narrative/broker note writers were left unchanged.

Independent Claude review was skipped at the user's explicit request. Two Codex self-review passes were completed before implementation.

## Files Changed

- Deleted `scripts/utils/report_skills/knowledge_skills.py`.
- Deleted `tests/reporter/test_knowledge_skills.py`.
- Updated `tests/test_runtime_hygiene.py` with absence and stale-reference guards.
- Renamed the stale persistence-oriented test in `tests/reporter/test_synthesis_skills.py` without changing its behavioral assertion.
- Removed obsolete references from `README.md`, `tools/ci_grep_gates.sh`, and `docs/agent_workflow/context_index.md`.
- Added the Batch E design and self-review notes.

## TDD Evidence

1. RED: `test_batch_e_detached_knowledge_skill_is_absent` failed while the module still existed.
2. GREEN: after deleting the detached module and references, the target test passed.
3. Focused suite: `112 passed`.
4. First full suite: `1 failed, 2874 passed, 10 skipped`. The failure exposed a stale active path in `docs/agent_workflow/context_index.md`.
5. Repaired the active index and extended the hygiene assertion to cover it.
6. Final full suite: `2875 passed, 10 skipped`.

## Verification

- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- `python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke`: exit 0; Markdown and HTML generated under `/tmp/testsnow_offline_smoke/reports/`.
- Active pipeline core files have zero diff:
  - `scripts/utils/report_skills/__init__.py`
  - `scripts/utils/stock_reporter.py`
  - `scripts/utils/report_run_plan.py`
- Repository search found no active production references to the deleted skill/module.

## Runtime Ledger

| File | Added | Removed | Net |
| --- | ---: | ---: | ---: |
| `scripts/utils/report_skills/knowledge_skills.py` | 0 | 296 | -296 |

Batch E adds no replacement runtime module. Combined with Batch D's `-155` lines, the two cleanup batches remove 451 runtime lines.

## Blockers, Warnings, Deviations

- Blockers: none.
- Warning: the first full-suite run found an active workflow-index reference omitted from the initial allowed-file list; it was removed because retaining a reference to a deleted runtime file would leave repository validation broken.
- Deviation: `docs/agent_workflow/context_index.md` was added to the implementation scope for that repair. No runtime boundary changed.
- Pre-existing knowledge-note replacements, old report modifications, and plan-packet artifacts were not modified or reverted.
