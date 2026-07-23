# External Producer v4 Batch D2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and execute each task in order. Each task has a RED command before its GREEN implementation step.

**Goal:** Finish the External Producer v4 deletion/compression exit gate with a version-neutral external risk provenance label, a single static cutover/owner guard, and a net-negative pack cleanup.

**Architecture:** `external_pack.py` remains the sole strict v4 builder/reader. `assembly_skills.py` changes only the provenance label attached to display-only external risk signals. The existing v4 cutover test becomes the one static owner for retired-path, schema/source-kind, unique-owner, and unique-display-writer checks.

**Tech Stack:** Python 3, `pytest`, `ast`, shell CI grep gates.

---

## File Map

- Modify: `scripts/utils/report_skills/assembly_skills.py`
  - Change the stale display-only external risk provenance label.
- Modify: `scripts/utils/external_pack.py`
  - Merge identical failure-pack construction without changing output contracts.
- Modify: `tests/reporter/test_recommendation_decision.py`
  - Pin the neutral provenance value and rename stale v3-oriented test names.
- Modify: `tests/utils/test_external_v4_cutover.py`
  - Extend the sole static cutover/ownership guard.
- Modify: `tests/utils/test_external_pack.py`
  - Pin selector-incomplete/degraded failure-pack field contracts.
- Create: `docs/agent_workflow/2026-07-23-external-producer-v4-batch-d2-notes.md`
  - Record runtime numstat, tests, owner audit, and deviations.

No pack JSON, configuration, data, knowledge, report, prompt, source acquisition, scoring, target-price, technical, or recommendation file may change.

## Task 1: Lock the v4 Cutover and Version-Neutral Provenance

**Files:**

- Modify: `tests/reporter/test_recommendation_decision.py:720-752`
- Modify: `tests/utils/test_external_v4_cutover.py`
- Modify: `scripts/utils/report_skills/assembly_skills.py:362-369`

- [ ] **Step 1: Write the failing contract tests**

Rename `test_assembly_does_not_infer_display_only_risk_note_from_v3_evidence_text` to
`test_assembly_does_not_infer_display_only_risk_note_from_structured_evidence_text` and rename
`test_assembly_collects_v3_structured_risk_card_without_changing_risk_score_input` to
`test_assembly_collects_structured_risk_card_without_changing_risk_score_input`.

Append this assertion to the latter test after the existing name-set assertion:

```python
assert {
    row.name: row.source_kind for row in rows
}["capacity_delivery"] == "curated_external_argument"
```

In `tests/utils/test_external_v4_cutover.py`, replace the current constants with explicit retired module and
literal sets:

```python
LEGACY_MODULES = {
    "curated_external_argument_cards",
    "curated_external_display_projection",
    "curated_external_topic_narrative",
    "curated_external_to_synthesis_items",
}
LEGACY_LITERALS = (
    "curated_external_argument_v2",
    "curated_external_argument_v3",
    "curated_external_argument_pack.v2",
    "curated_external_argument_pack.v3",
    "curated_external_argument_pack.v3.1",
    "curated_external_argument_card.v2",
    "curated_external_argument_card.v3",
    "curated_external_unit_selection.v1",
)
OWNED_FUNCTIONS = {
    "resolve_external_scope": "utils/external_scope.py",
    "external_family_title": "utils/external_evidence.py",
    "validate_external_evidence_unit": "utils/external_evidence.py",
    "build_external_argument_pack_v4": "utils/external_pack.py",
    "read_external_argument_pack_v4": "utils/external_pack.py",
    "build_curated_external_argument_display": "utils/curated_external_display.py",
}
```

Add helpers that iterate `RUNTIME_ROOT.rglob("*.py")` but skip any path whose relative parts contain `"archive"`.
Use AST to collect imports, function definitions, and dictionary string keys. Assert that retired imports/literals are
empty, every owned function is defined exactly in its expected relative path, and
`_curated_external_argument_cards` occurs as a dictionary key exactly once in
`utils/curated_external_display.py`.

- [ ] **Step 2: Run both focused tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_recommendation_decision.py::test_assembly_collects_structured_risk_card_without_changing_risk_score_input -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_external_v4_cutover.py -q -p no:cacheprovider
```

Expected: both fail because the runtime still emits `curated_external_argument_v3`.

- [ ] **Step 3: Make the minimal runtime change**

Replace only the structured-card literal in `_collect_display_only_external_risks`:

```python
append_signal(
    card.get("primary_family") or "外部待验证变量",
    "curated_external_argument",
    " ".join(str(unit.get("text") or "") for unit in card.get("evidence_units") or []),
)
```

Do not change the risk-card classifier, dedupe key, risk score flow, or rendered Markdown.

- [ ] **Step 4: Run both focused tests to verify GREEN**

Run the Step 2 commands.

Expected: both pass; current `curated_external_unit_selection.v2` and archived scripts remain allowed.

## Task 2: Preserve Failure-Pack Contracts While Removing Duplication

**Files:**

- Modify: `tests/utils/test_external_pack.py:130-148, 191-213`
- Modify: `scripts/utils/external_pack.py:100-145, 391-411`

- [ ] **Step 1: Strengthen failure-contract characterization tests**

In `test_selector_group_cannot_cross_source_or_block`, add:

```python
assert pack["source_documents"] == documents
assert pack["cards"] == []
assert pack["citations"] == {}
```

In `test_pack_rejects_cutover_when_any_comparative_source_is_degraded`, add:

```python
assert "rejection_reasons" not in pack["diagnostics"]
```

Run both tests before refactoring; they must already pass because they characterize the correct existing behavior
that the cleanup must preserve.

- [ ] **Step 2: Replace duplicate failure builders**

Replace `_incomplete` and `_source_input_degraded` with:

```python
def _failure_pack(
    status: str,
    stock_name: str,
    prepared: Mapping[str, Any],
    *,
    source_documents: Iterable[Mapping[str, Any]] = (),
    rejection_reason: str | None = None,
) -> dict:
    diagnostics = dict(prepared.get("diagnostics") or {})
    if rejection_reason:
        diagnostics["rejection_reasons"] = [rejection_reason]
    return {
        "schema_version": ARGUMENT_PACK_SCHEMA,
        "status": status,
        "stock_name": stock_name,
        "validator_version": PACK_VALIDATOR_VERSION,
        "source_documents": list(source_documents),
        "cards": [],
        "citations": {},
        "diagnostics": diagnostics,
    }
```

Update the two selector-incomplete returns to call:

```python
_failure_pack(
    "selector_incomplete", stock_name, prepared,
    source_documents=valid_documents, rejection_reason=reason,
)
```

Update the source-degraded return to call:

```python
_failure_pack("source_input_degraded", stock_name, prepared)
```

Delete the two replaced helpers.

- [ ] **Step 3: Remove the zero-value target wrapper**

In `prepare_external_argument_material_v4`, replace:

```python
"target_cards": _build_target_cards(stock_name, target),
```

with:

```python
"target_cards": _cards_from_runs(stock_name, target, _target_unit_scope),
```

Then delete `_build_target_cards`. Keep `_target_unit_scope` because it encodes the target-versus-target-with-peer
context decision.

- [ ] **Step 4: Run pack tests to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_external_pack.py -q -p no:cacheprovider
```

Expected: all tests pass, including preserved source-document and diagnostics contracts.

## Task 3: Integrated Verification and Notes

**Files:**

- Create: `docs/agent_workflow/2026-07-23-external-producer-v4-batch-d2-notes.md`

- [ ] **Step 1: Run focused and downstream tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_external_pack.py \
  tests/utils/test_external_v4_cutover.py \
  tests/utils/test_external_source_document.py \
  tests/utils/test_external_evidence.py \
  tests/utils/test_external_scope.py \
  tests/utils/test_external_narrative_plan.py \
  tests/utils/test_external_v4_display.py \
  tests/utils/test_external_v4_snapshot.py \
  tests/reporter/test_recommendation_decision.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full offline verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: full suite passes or only pre-existing skips remain; CI gate passes; diff check emits no output.

- [ ] **Step 3: Run explicit ownership audit**

Run:

```bash
rg -n '"_curated_external_argument_cards"\\s*:' scripts --glob '*.py'
rg -n 'curated_external_argument_(v2|v3)|curated_external_argument_pack\\.v(2|3|3\\.1)|curated_external_to_synthesis_items' scripts --glob '*.py'
```

Expected: one writer in `scripts/utils/curated_external_display.py`; no active legacy external hits.

- [ ] **Step 4: Write completion notes**

Record changed files, RED/GREEN evidence, focused/full/CI results, runtime `git diff --numstat` for the two runtime
files, owner audit results, deviations, and the explicit statement that reports/canonical packs/data were untouched.

Do not commit or generate reports in this task. Leave the final commit decision to the user after acceptance.
