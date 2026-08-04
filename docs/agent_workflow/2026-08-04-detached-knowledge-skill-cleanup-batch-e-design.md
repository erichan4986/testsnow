# Detached Knowledge Skill Cleanup Batch E Design

## 1. Objective

Delete the dormant `KnowledgePersistenceSkill` path from the report pipeline
codebase. The module has never been inserted into the active pipeline and has
no production caller. This is a deletion batch, not a replacement knowledge
architecture.

The working baseline includes the completed but uncommitted Batch D changes.
Existing user-owned broker notes, old reports, plan packets, and historical
knowledge files remain out of scope.

## 2. Evidence

Repository-wide static and history checks found:

- `scripts/utils/report_skills/knowledge_skills.py` contains 296 runtime lines;
- `build_stock_report_pipeline()` does not import or instantiate it;
- `report_skills.__all__` does not export it;
- `PerStockReporter`, `ReportRunPlan`, entries, previews, and smoke scripts do
  not import it;
- no dynamic registry or `import_module()` path names it;
- its only executable caller is `tests/reporter/test_knowledge_skills.py`;
- README and `tools/ci_grep_gates.sh` still name the file as if active;
- git history shows the module was added in the baseline commit and was never
  wired into pipeline assembly;
- three historical tracked knowledge notes exist, but deleting runtime must not
  delete or rewrite those artifacts.

Current evidence-note, annual narrative, broker digest, and external-material
writers are separate active owners. They do not reproduce the dormant skill's
four-note format, and this design does not claim that they do. The safety claim
is narrower: removing code that is never called cannot change current report or
knowledge output.

## 3. Selected Change

Delete:

- `scripts/utils/report_skills/knowledge_skills.py`
- `tests/reporter/test_knowledge_skills.py`

Update active references:

- remove the `knowledge_skills.py` row and test-list entry from `README.md`;
- remove the nonexistent target from both file arrays in
  `tools/ci_grep_gates.sh`;
- remove its active `path-check` entry from
  `docs/agent_workflow/context_index.md`;
- rename the stale synthesis test
  `test_periodic_report_fulltext_knowledge_persistence_would_receive_baseline`
  to describe its actual active contract: display-only fulltext material does
  not mutate baseline synthesis;
- add a runtime-hygiene assertion that the deleted module and class remain
  absent and are not exported by `report_skills`.

Do not modify generated handoff manifests under `docs/codex_handoff/`; they are
historical snapshots, not active documentation.

## 4. Explicitly Preserved

- `PerStockReporter`, `ReportRunPlan`, and `build_stock_report_pipeline`;
- every active skill and exact pipeline order/count;
- `SkillContext`, `BaseSkill`, `skill`, and `SkillPipeline.add` public APIs;
- evidence-note and producer-specific knowledge writers;
- report Markdown/HTML/PDF and assembly sidecars;
- all existing files under `knowledge/`, including the three historical notes;
- scoring, technical analysis, targets, risk, recommendations, citations,
  prompts, providers, configs, data, and reports.

## 5. Allowed Files

- delete `scripts/utils/report_skills/knowledge_skills.py`;
- delete `tests/reporter/test_knowledge_skills.py`;
- update `README.md`;
- update `tools/ci_grep_gates.sh`;
- update `docs/agent_workflow/context_index.md`;
- update `tests/reporter/test_synthesis_skills.py` only for the stale test name
  and docstring;
- update `tests/test_runtime_hygiene.py`;
- add Batch E workflow notes.

No new runtime file or compatibility adapter is allowed.

## 6. TDD And Verification

### Task 1: RED absence contract

Add a runtime-hygiene test asserting:

- `knowledge_skills.py` does not exist;
- `KnowledgePersistenceSkill` is not exported from `report_skills`;
- active README and CI gate text no longer reference the file/class.

Run it and confirm RED against the existing module.

### Task 2: GREEN deletion

Delete the runtime and its isolated tests. Remove active README/CI references
and rename the stale synthesis test. Do not alter the synthesis assertion body.

### Task 3: Focused verification

Run:

- `tests/test_runtime_hygiene.py`
- `tests/test_skill_pipeline.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_report_run_plan.py`
- the renamed synthesis test
- `tests/reporter/test_evidence_note_skill.py`

Then run full pytest, `tools/ci_grep_gates.sh`, `git diff --check`, and the
existing offline report smoke. The pipeline skill names and counts must stay
identical to their existing integration-test expectations.

## 7. Budget

- Runtime deletion target: exactly 296 lines.
- New runtime lines: 0.
- Test deletion: the isolated test file; new hygiene coverage is outside the
  runtime budget.
- Hard stop: any runtime addition, replacement adapter, or change to pipeline
  construction.

## 8. Failure Modes

| Failure | Symptom | Detection |
|---|---|---|
| Hidden production caller exists | import/runtime failure | repository search + full pytest + smoke |
| Pipeline order changes | different skill count or position | integration suite |
| Active knowledge writer is removed | missing evidence/producer notes | scope diff + evidence-note tests |
| CI gate is weakened for active files | source isolation regression | gate script + file-array diff |
| Stale public export remains | import points to missing module | hygiene test |
| Historical artifacts are deleted | knowledge diff appears | git status/diff audit |
| Code is replaced instead of deleted | runtime line count does not fall 296 | numstat |

## 9. Stop Conditions

Stop if:

- any non-test runtime import or dynamic caller is discovered;
- deletion requires changing pipeline construction or report behavior;
- an active writer depends on this class;
- any file under `knowledge/`, `data/`, or `reports/` would need modification;
- runtime net deletion is below 296 lines.
