# Chapter 4 Read-Model Consolidation Batch G1 Design

> **Date**: 2026-08-05
> **Owner**: Codex
> **Status**: Locked For Implementation

## 1. Goal

Remove the duplicate annual Chapter 4 projection logic and unused renderer
plumbing while preserving report content, profile routing, and citation
identity. The canonical `MaterialSnapshot` selector becomes the only owner of
annual admission and portrait selection; the renderer only groups already
selected annual rows and formats them.

The batch targets a net runtime reduction of 80-130 lines. It must not create
a replacement compatibility path merely to meet the line target.

## 2. Alternatives Considered

### A. Annual-owner consolidation (selected)

Keep the current snapshot, broker memo, and profile APIs. Render selected
annual rows directly and remove parameters that are provably unused by the
broker/external formatters.

Trade-off: the formal-thin broker memo path remains for a later structured-row
task because the current `MaterialRow` does not preserve forecast `metric` and
`period` as separate values.

### B. Snapshot-backed formal-thin broker rendering

This would remove more code, but the current thin renderer emits memo
`sections`, `forecast_ranges`, and `risks`. Forecast rows lose the original
metric/period boundary when adapted to `MaterialRow`; switching now would
silently alter visible output or require new hidden metadata. Defer it.

### C. Extend `Chapter4ViewModel` to every profile

Architecturally cleaner, but it would also change profile-specific broker
admission, headings, disclaimers, and section metadata. It is too broad for a
behavior-preserving cleanup.

### D. Remove annual/broker memos and build snapshot rows from producer packs

Potentially removes more code, but changes the synthesis/profile contract and
the in-memory annual-card fallback. It requires report-content acceptance and
is deferred.

## 3. Non-Goals

- Do not change `SynthesisSkill`, annual/broker/external producers, or memo
  schemas.
- Do not change profile routing or pipeline order.
- Do not change external narrative selection, owner-delta filtering, source
  order, or paragraph aggregation.
- Do not change LLM prompts, synthesis, scoring, technical analysis, target
  price, risk, recommendation, or source policy.
- Do not modify data, knowledge, reports, configuration, or user-owned dirty
  files.
- Do not split large files merely to move line count.

## 4. Current Context

| Area | Current behavior | Problem |
|---|---|---|
| Annual selector | `select_annual_display_rows()` rejects noise, applies role budgets, dedupes, and assigns `editorial_slot="portrait"` | Renderer converts rows back to memo dicts and can select a portrait again |
| Formal-medium | Uses `Chapter4ViewModel` and selected `MaterialRow` objects | Annual formatter still passes through memo-shaped projection |
| Formal-thin annual/external | Uses a full snapshot and public selectors | Correct ownership, but orchestration is repeated in renderer |
| Formal-thin broker | Reads all three memo groups: sections, forecast ranges, and risks | Retained because `MaterialRow` does not preserve all forecast structure |
| Citations | Snapshot refs form one namespace ordered annual, broker, external | Thin broker uses local memo refs plus a computed offset |
| Unused plumbing | Broker/external map methods accept citation dictionaries they never read; thin body accepts an unused curated display | Deterministic signature cleanup |
| Dead code | `_truncate_title()` and the trivial `_material_snapshot()` wrapper add no behavior | Deterministic deletion candidates |

## 5. Proposed Design

### 5.1 Annual rows render directly

Rewrite `_annual_material_profile_section()` to consume only preselected
`MaterialRow` objects.

Algorithm:

1. Find the row whose `editorial_slot == "portrait"`; do not score or select a
   fallback portrait in the renderer.
2. Render that row once under `一句话画像`.
3. Group remaining rows by `render_role` in the existing display order:
   `business_structure`, `operating_progress` plus
   `market_competition_outlook`, `technology_product_progress`, and
   `financial_quality_explanation`.
4. When requested, append `formal_fact` rows to the financial group.
5. Preserve the current visible-text dedupe after compact formatting so rows
   that collapse to the same sentence remain visible once.
6. Preserve title prefix behavior for informative financial titles.
7. Attach the row's snapshot refs plus the single Chapter 4 citation offset.
8. Return the existing fallback only when no row renders.

Delete the renderer's memo-shaped annual projection and portrait selector.
Tests that call `_select_annual_portrait_row()` directly move to the public
snapshot selector contract.

### 5.2 Suspicious zero remains an admission concern

The old renderer filtered suspicious `0.00亿元` revenue/profit/cash-flow rows only from
confirmed financial rows. Move this exact boundary into
`select_annual_display_rows()`:

- reject only `claim_status == "formal_fact"` rows where the body contains
  `0.00亿元` and the title identifies revenue, income, profit, or cash flow;
- retain explanation rows containing the same literal so a valid explanation
  is not discarded;
- report the rejection reason as `suspicious_zero_financial_fact`.

This keeps the behavior while placing admission under the snapshot owner.

### 5.3 Preserve formal-thin broker and citation semantics

Do not replace `_broker_research_memo_section()` in G1. It currently renders:

- memo `sections` with titles and attribution;
- `forecast_ranges` with separate metric, period, and range text;
- `risks` with attributed risk wording;
- the single-institution disclosure.

Keep `broker_citation_offset`, `_max_snapshot_ref()`, and the existing final
snapshot citation merge. The `[^5]`/`[^6]` fixtures remain unchanged and guard
against accidental offset drift caused by the annual refactor.

### 5.4 Remove unused arguments and wrappers

The following parameters are not read and can be removed with their call-site
arguments:

- `citations` from `_formal_medium_broker_assumption_section()`;
- `citations` from `_formal_medium_external_variable_map()`;
- `annual_material_citations` from `_formal_thin_external_rich_body()` and
  `_deep_analysis()` plumbing;
- `curated_display` from `_formal_thin_external_rich_body()` only. The
  `curated_external_display` argument remains on `_deep_analysis()` because
  formal-rich uses it.

Inline the single call to `_material_snapshot(ctx, True)` and delete the
wrapper. Do not alter citation allocation or merge formulas.

### 5.5 Deterministic dead helper deletion

Delete `_truncate_title()` and add hygiene assertions for the deleted helper
and annual compatibility projection methods.

## 6. Ownership After G1

| Component | Responsibility |
|---|---|
| `SynthesisSkill` | Produce annual memo, broker memo, external display, and profile |
| `build_deep_analysis_material_snapshot()` | Adapt all material to `MaterialRow` and allocate snapshot refs |
| snapshot selectors | Admit, dedupe, rank, budget, and assign annual portrait |
| `DeepAnalysisRenderer` | Apply profile headings and format preselected annual rows; retain broker memo formatting |

No new module or selector is introduced.

## 7. Files Expected To Change

| File | Change |
|---|---|
| `scripts/utils/deep_analysis_material_snapshot.py` | Admit suspicious-zero formal facts under the canonical annual selector |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | Direct annual rendering, unused-argument cleanup, wrapper/dead-helper removal; retain thin broker behavior |
| `tests/utils/test_deep_analysis_material_snapshot.py` | Lock zero-fact boundary and selector-owned portrait behavior |
| `tests/reporter/test_deep_analysis_renderer.py` | Replace private selector tests with public rendering contracts; lock thin broker refs/status |
| `tests/test_runtime_hygiene.py` | Lock deleted compatibility helpers |

Only these five files plus implementation notes may change.

## 8. Failure Modes And Tests

| Failure mode | Symptom | Required test |
|---|---|---|
| Renderer selects a second portrait | A different or weak row leads 4.1 | Snapshot-selected portrait is rendered exactly once |
| No portrait exists | Renderer invents a fallback portrait | Preselected rows without `editorial_slot` render groups without `一句话画像` |
| Hidden annual rows reappear | 4.1 becomes a material dump | Role-budget selection count and public render count |
| Valid explanation containing `0.00亿元` is lost | Annual explanation disappears | Formal fact rejected; formal explanation retained |
| Thin broker output changes accidentally | Forecast/risk or single-institution text changes | Existing path remains; add parity fixture covering all three memo groups |
| External refs shift | `[^5]`/`[^6]` regressions fail | Existing full-snapshot offset tests unchanged |
| Formal-rich changes | Legacy 4.1-4.4 output changes | Formal-rich renderer regression suite |
| New projection path appears | Complexity is moved, not removed | Hygiene/source audit and runtime ledger |

## 9. TDD Sequence

1. RED: add snapshot tests for suspicious-zero formal fact rejection and
   explanation retention.
2. GREEN: move the narrow guard into annual snapshot admission.
3. RED: add public renderer tests proving annual rows require the selector's
   `editorial_slot`; remove direct tests of renderer portrait scoring.
4. GREEN: render annual MaterialRows directly and delete the duplicate annual
   helpers.
5. Characterization GREEN: add a formal-thin broker parity fixture covering
   section, forecast, risk, single-institution, and citation output before any
   signature cleanup; retain the broker memo path unchanged.
6. RED/GREEN: add source-hygiene assertions, then remove provably unused
   formatter parameters, inline the snapshot wrapper, and delete
   `_truncate_title()`.
7. Run focused, downstream, full-suite, CI, whitespace, and offline smoke
   gates.

## 10. Runtime Ledger And Stop Conditions

Target net runtime reduction: 80-130 lines across the two runtime files.

Stop and return to design if:

- implementation requires modifying `synthesis_skills.py`, a producer, profile
  routing, or pipeline order;
- a third annual/broker projection path is introduced;
- formal-thin broker content, citation IDs, or citation identities change;
- formal-rich output changes outside whitespace;
- net runtime reduction is less than 65 lines after tests are green;
- focused or downstream failures require broad compatibility logic;
- any data, knowledge, report, configuration, prompt, scoring, technical,
  target, risk, or recommendation file must change.

## 11. Acceptance Gates

Required commands:

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

The offline smoke may write only to its existing temporary output location.
No formal report refresh, network, browser, LLM, or PDF run is required.

## 12. Design Self-Review

- Placeholder scan: no TBD/TODO or unresolved choice.
- Ownership: annual admission stays in the snapshot selector; the existing
  broker memo render path is unchanged in G1.
- Citation semantics: no offset or merge formula changes in G1.
- Scope: two runtime files, three test files, no synthesis behavior.
- Ambiguity resolved: thin broker renders sections, forecasts, and risks and is
  deliberately retained because `MaterialRow` cannot reproduce all three
  shapes losslessly.
- Budget: replacement deletes named helpers instead of adding adapters beside
  them.

## 13. Design Delta From Codex Self-Review

Accepted:

- Keep annual portrait/admission solely in the snapshot selector.
- Remove unused citation-map arguments and deterministic dead helpers.

Revised:

- Deferred formal-thin broker unification after verifying that the existing
  renderer consumes `sections`, `forecast_ranges`, and `risks`, not sections
  alone.
- Added cash-flow metrics to the exact suspicious-zero compatibility boundary.
- Reduced the deletion target from 100-150 to 80-130 lines.

Rejected:

- Do not reconstruct forecast metric/period from flattened `MaterialRow.title`
  with regex or hidden renderer heuristics.

Deferred:

- A future broker read-model task must preserve structured metric, period,
  range, risk kind, and institution disclosure before deleting the memo path.

## 14. Claude Review Log

External Claude review was waived by the user on 2026-08-05 with the explicit
instruction `推进实现`. The waiver record is stored in
`2026-08-05-chapter4-read-model-consolidation-batch-g1-claude-review-round1-notes.md`.

Pending.

### Design Delta After Round 1

- accepted: pending
- rejected: pending
- deferred: pending
- R2 required: pending

### Final Implementation Readiness

Pending Round 1 review.
