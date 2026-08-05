# Chapter 4 Broker Read-Model Consolidation G2 Design

> **Date**: 2026-08-05
> **Owner**: Codex
> **Baseline**: `77dd423`
> **Status**: Implemented under user-approved review waiver

## 1. Goal

Remove the remaining formal-thin raw `broker_research_memo` rendering bypass.
Formal-thin must render broker sections, forecasts, and risks from the same
global-ref `MaterialSnapshot` used by annual and external Chapter 4 material,
without changing visible broker content, single-institution disclosure, source
order, citation identity, profile routing, or selection policy.

Target runtime reduction: 20-40 lines across the snapshot and renderer. Stop if
the green implementation increases runtime or creates another projection
shape.

## 2. Current Pipeline And Defect

```text
broker digest items
  -> broker_research_memo
  -> _broker_rows() -> MaterialRow + snapshot-global refs
       -> formal-medium 4.2 (MaterialRow)
       -> external owner comparison (MaterialRow)

broker_research_memo
  -> formal-thin _broker_research_memo_section() (raw dict bypass)
```

The bypass exists because forecast adaptation currently flattens
`metric + period` into `MaterialRow.title`. The formal-thin formatter needs the
two values separately to reproduce:

```text
{institution}研报预计：{metric} {period} {range}
```

The bypass also forces `broker_citation_offset`, `_max_snapshot_ref()`, and a
second local-ref rendering path even though snapshot broker refs are already
global within Chapter 4.

## 3. Alternatives

### A. Add lossless broker fields to MaterialRow (selected)

Add three optional fields with empty defaults:

```python
broker_metric: str = ""
broker_period: str = ""
broker_memo_status: str = ""
```

`body` remains the forecast range/body. `_broker_rows()` copies metric, period,
and memo status verbatim. This mirrors the existing external-specific fields
already carried by `MaterialRow` and keeps formatting type-safe.

### B. Parse the flattened title

Rejected. Values such as `归母净利润2026E` have no reliable boundary. Regex
reconstruction would reintroduce the heuristic the G1 design explicitly
deferred.

### C. Store broker fields in diagnostics

Rejected. `diagnostics` is audit metadata; making visible output depend on it
would hide the display contract and weaken type checking.

### D. Reuse formal-medium output wholesale

Rejected. Formal-medium adds `机构关注重点`, `关键盈利假设`, and risk-group
headings, while formal-thin currently presents a compact list and a
single-institution disclosure. G2 is a read-model consolidation, not a report
layout change.

## 4. Locked Runtime Design

### 4.1 Snapshot adaptation

In `_broker_rows()`:

- preserve current row order: `sections`, `forecast_ranges`, `risks`;
- preserve all current refs, attribution, title, body, role, and source credit;
- set `broker_metric` and `broker_period` only for forecast rows;
- set `broker_memo_status` on every broker row to the memo status;
- do not modify `broker_research_memo.v1` or `SynthesisSkill`.

`MaterialSnapshot.schema` remains `deep_analysis_material_snapshot.v1`. The
new dataclass fields are optional, internal, and backward-compatible for all
existing constructors.

### 4.2 Formal-thin orchestration

After building or reading the full snapshot:

```python
broker_material_rows = tuple(
    row for row in material_snapshot.rows if row.source_layer == "broker"
)
```

Pass those rows to formal-thin. Do not call `_select_broker_display_rows()`:
that selector owns the formal-medium editorial budget, while the existing
formal-thin memo renderer displays all admitted memo rows. The memo builder
currently emits at most six total rows, but the no-loss contract must not rely
on that cap.

External owner comparison continues to use attributed broker rows from the
same snapshot. Annual and external selection behavior is unchanged.

### 4.3 Formal-thin broker formatting

Replace `_broker_research_memo_section(memo, offset)` with a row-based
formatter, `_formal_thin_broker_section(material_rows, citation_offset)`.

Rules:

1. Empty rows render the current fallback sentence.
2. If any row has `broker_memo_status == "single_institution"`, render the
   current `单篇研报观点 / 单机构观点` disclosure once.
3. Normalize `row.attribution` to a display author before formatting:
   `"研报"`, `"券商"`, and `"机构"` mean no named institution; every other
   non-empty value is the named institution. This prevents output such as
   `研报研报预计` while preserving the existing unnamed `研报预计` wording.
4. `broker_assumption`: preserve current title and attribution normalization.
5. `broker_forecast`: render
   `{attribution}研报预计：{broker_metric} {broker_period} {body}` with empty
   components omitted but without parsing title text. When there is no named
   institution, the prefix is exactly `研报预计`.
6. `broker_risk`: preserve current risk attribution normalization.
7. Attach each row's snapshot-global refs plus the single baseline citation
   offset.
8. Keep source order and do not apply a renderer cap or dedupe.

An accepted memo status with zero valid rows is treated as unavailable and
renders the fallback sentence. The old raw renderer emitted only a
single-institution label for that malformed state; G2 intentionally fails
closed instead of adding snapshot-level status or a sentinel row solely to
preserve an empty disclosure.

This formatter is profile-specific presentation, not a second selector.

### 4.4 Citation formula

Let `B` be the maximum baseline synthesis citation ID and `S` a snapshot-global
row ref.

```text
visible Chapter 4 ref = B + S
```

This same formula applies to annual, broker, and external rows. Delete:

- `broker_citation_offset` state and parameters;
- `_max_snapshot_ref()`;
- raw memo local-ref offset calculation.

The final citation merge remains:

```python
offset_citations(material_snapshot.citations, max(baseline_citations))
```

Do not renumber or filter `material_snapshot.citations` before the existing
visible-citation pass.

## 5. Allowed Scope

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

Workflow documents for G2 may be added under `docs/agent_workflow/`.

## 6. Forbidden Scope

- Do not modify `synthesis_skills.py`, broker digest producers, memo schema, or
  note formats.
- Do not change `_select_broker_display_rows()` or formal-medium admission.
- Do not change annual/external selectors, owner comparison, or narratives.
- Do not change profile routing, pipeline order, LLM prompts, scoring,
  technical analysis, target price, risk, recommendation, source policy,
  configuration, data, knowledge, or reports.
- Do not infer metric/period from title strings.
- Do not add a new broker compatibility adapter beside `MaterialRow`.

## 7. TDD Plan And Required Tests

### Task 1: Lossless snapshot fields

RED test: build a snapshot from a memo forecast with distinct metric, period,
and range. Assert the broker row preserves all three values and memo status.

GREEN: add optional fields and populate them in `_broker_rows()`.

### Task 2: Prove formal-thin no longer reads raw memo

RED test: provide a prebuilt snapshot containing broker rows and a conflicting
`broker_research_memo={"status": "absent"}`. Assert formal-thin renders the
snapshot section, forecast, risk, and single-institution disclosure. Current
code must fail because it reads the absent memo.

Use two forecast fixtures: one with a named institution and one whose snapshot
attribution is the generic `研报` fallback. Assert the latter renders exactly
`研报预计`, never `研报研报预计`. Also assert an empty broker-row tuple renders the
existing unavailable fallback.

GREEN: pass full snapshot broker rows to the row-based formatter.

### Task 3: Lock global citation identity

Use baseline refs plus annual, broker, and external snapshot refs. Assert:

- each visible broker ref equals `B + S`;
- source rows resolve to the same shifted IDs;
- existing external `[^5]` / `[^6]` regression tests remain unchanged;
- broker source order remains section -> forecast -> risk.

### Task 4: Delete bypass and offset plumbing

Hygiene must assert absence of:

- `_broker_research_memo_section`;
- `_broker_row_author`;
- `_max_snapshot_ref`;
- `broker_citation_offset` in the renderer source.

Retain `_select_broker_display_rows()` because formal-medium uses it.

### Task 5: Regression gates

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/test_runtime_hygiene.py -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke
```

## 8. Failure Modes

| Failure mode | Visible symptom | Required guard |
|---|---|---|
| forecast fields flattened again | metric/period wording changes or disappears | distinct field snapshot test |
| raw memo remains authoritative | conflicting memo overrides snapshot | prebuilt-snapshot RED test |
| broker refs double shifted | broker source points to annual/external citation | baseline + snapshot-ref identity test |
| external refs renumbered | existing `[^5]`/`[^6]` output changes | existing formal-thin offset tests |
| single-institution disclosure lost | one report looks like consensus | snapshot-only disclosure test |
| generic attribution duplicated | output says `研报研报预计` | unnamed forecast fixture |
| accepted-but-empty memo leaks a label | disclosure appears without evidence | empty-row fail-closed fixture |
| formal-medium cap changes | extra/missing 4.2 rows | existing view-model and renderer tests |
| source order changes | risk appears before forecast/section | exact order assertion |
| missing broker material crashes | thin report fails instead of fallback | empty-row fallback test |

## 9. Runtime Ledger And Stop Conditions

Expected replacement:

- add 3 optional `MaterialRow` fields and 3 adapter assignments;
- replace the raw-dict broker formatter with a shorter row formatter;
- remove raw memo reads, broker-local offset plumbing, `_broker_row_author()`,
  and `_max_snapshot_ref()`.

Target net runtime reduction: 20-40 lines. Stop and return to design if:

- runtime grows after tests are green;
- preserving output requires modifying the memo producer or synthesis skill;
- any metric/period title parsing is introduced;
- formal-medium selection/output changes;
- external citation IDs change;
- a second normalized broker row type is introduced;
- a forbidden-scope file must change.

## 10. Design Self-Review Pass 1: Correctness

- The memo already contains separate metric, period, and range fields; the
  snapshot adapter can copy them without producer changes.
- Snapshot refs are globally allocated annual -> broker -> external, so one
  baseline offset is sufficient.
- Full broker snapshot rows preserve formal-thin's no-loss behavior; the
  formal-medium selector remains untouched.
- A row-level memo status is redundant but explicit, immutable, and avoids
  making rendering depend on diagnostics or raw memo state.
- Existing positional `MaterialRow` constructors remain compatible because all
  new fields have defaults at the end of the dataclass.

## 11. Design Self-Review Pass 2: Simplicity And Scope

- No `Chapter4ViewModel` expansion is needed.
- No schema bump, producer migration, cache refresh, or report acceptance run
  is needed for implementation verification.
- Profile-specific formatting is retained, but source admission and citation
  identity have one owner.
- The design does not chase the earlier 45-65 line estimate; it uses a smaller
  credible 20-40 line target rather than compressing formatting into opaque
  branches.
- No unresolved placeholder or hidden compatibility path remains.

## 12. Review Gate

This task changes a shared read-model schema and citation orchestration, so it
requires a Level 3 review record. The user explicitly instructed Codex to
self-review, fix, and implement directly after receiving the external review
prompt. That approval is recorded in
`2026-08-05-chapter4-broker-read-model-consolidation-g2-user-waiver.md`; it
waives only the external reviewer, not TDD, scope, stop conditions, or final
verification.
