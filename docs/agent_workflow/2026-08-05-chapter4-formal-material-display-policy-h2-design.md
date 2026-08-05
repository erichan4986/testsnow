# Chapter 4 Formal Material Display Policy H2 Design

## Status

`self_reviewed_ready_for_repository_review`

H1 removed the annual/broker memo schemas and made
`deep_analysis_material_snapshot.py` the sole Chapter 4 formal-material row
owner. H2 may now change the three content policies that H1 deliberately kept
frozen.

## Goal

Preserve every admitted formal-material argument in the canonical snapshot,
while keeping the final report concise through the existing Chapter 4 display
selectors.

H2 makes three narrow changes:

1. annual visible-text cleanup no longer cuts a canonical argument at 300
   characters;
2. broker projection no longer applies the hidden `selected[:6]` cap after the
   configured loader budget;
3. one guarded broker card is rendered as an attributed single-institution
   observation instead of being discarded as `absent`.

## Non-Goals

- no annual or broker producer changes;
- no note refresh, loader ordering, loader budget, or source guard changes;
- no new material family or selection path;
- no change to annual editorial role budgets;
- no change to the broker ViewModel display budget of five non-risk rows plus
  two risk rows;
- no profile-name, pipeline-order, citation-offset, scoring, target-price,
  risk, technical-analysis, recommendation, or LLM-prompt changes;
- no data, Knowledge-note, report, or configuration edits.

## Current Problem

### Annual

The canonical annual card contains complete source-owned units, but
`_clean_annual_excerpt()` cuts the body at 300 characters before the snapshot
is built. This loses the tail before the annual display selector can decide
which evidence is useful. The renderer later compacts visible bullets to 140
characters, so the snapshot cut is both premature and redundant.

### Broker

The loader already applies the explicit
`broker_research_digest_max_display_items` budget, default 8. The snapshot then
silently keeps only six items, and the ViewModel later applies its own five
non-risk plus two risk display budget. The middle cap has no independent owner.

A single guarded broker card is counted as usable for coverage/profile
diagnostics but receives `status=absent`, so the same material affects routing
while disappearing from 4.2.

## Locked Ownership

The layers remain:

1. producer/note reader: source validity, exact excerpt, card family and source
   metadata;
2. synthesis loader: explicit intake budget and one load per run;
3. material snapshot: complete admitted formal rows and global citations;
4. Chapter4 ViewModel: report-facing row budgets and exact-body dedupe;
5. renderer: sentence formatting and visible bullet compaction.

H2 must not add another selector, memo, compatibility adapter, or source reader.

Here, "every admitted argument" means every unique row surviving the existing
canonical guard and exact-key dedupe. H2 does not retain invalid or exact
duplicate material.

## Design

### 1. Annual cleaner becomes normalization-only

Replace `_clean_annual_excerpt(text, max_chars=300)` with
`_clean_annual_excerpt(text)`. Preserve all current PDF header, page marker,
table header, CJK whitespace, and repeated whitespace cleanup. Delete the
character-boundary branch entirely.

The cleaned body must remain a substring-derived display projection; H2 does
not rewrite facts or mutate producer cards. Exact full-body dedupe remains in
`_prepare_annual_material()`. Containment and financial-fact dedupe remain in
`select_annual_display_rows()`.

Expected behavior:

- snapshot annual rows may exceed 300 characters and retain the complete
  cleaned argument;
- final 4.1 row count remains bounded by `_ANNUAL_ROLE_BUDGETS`;
- renderer bullet compaction remains unchanged;
- canonical source cards in `ctx` remain byte-for-byte unchanged.

### 2. Remove broker's secondary snapshot cap

After guard and exact key dedupe, set `projected_items` to every selected item
when the broker status is admitted. Do not change the loader's default/configured
budget and do not change `_select_broker_display_rows()`.

Consequences:

- snapshot and citation diagnostics retain all guarded items returned by the
  loader;
- final formal-medium 4.2 remains limited to five non-risk plus two risk rows;
- formal-thin continues to receive the complete snapshot broker rows, matching
  its existing contract;
- `formal_citation_candidate_count` counts all projected broker rows.

### 3. Admit one guarded broker card without inventing consensus

Admission becomes `bool(selected)`. Status stays within the existing vocabulary:

- `ready`: multiple report titles and multiple institutions under the existing
  rule;
- `single_institution`: every other non-empty guarded selection, including one
  card;
- `absent`: no guarded selection.

This reuses the renderer's existing formal-thin label
`单篇研报观点 / 单机构观点`. Formal-medium already keeps the institution in each
row attribution. No consensus wording is added.

The one-card state remains display-only professional analysis:

- `confirmed_fact`, `scoring_eligible`, and `risk_score_eligible` guards remain;
- it does not enter scoring, target price, risk score, or recommendation;
- it does not become an official fact;
- broker usable count and evidence-profile routing remain unchanged because
  they already count guarded usable items independently of status.

Because broker rows are formal owners for the existing incremental external
selector, an admitted sparse broker row may suppress a 4.3 target observation
only when the external claim is textually/factually duplicate under the current
owner rules. An external row with a new concrete anchor or event variable must
remain visible. This is an expected ownership consequence, not a new dedupe
algorithm.

## Citation And Profile Contracts

- Citation allocation order remains annual, broker source order, external.
- External offsets remain based on the full snapshot.
- Removing the six-row cap may increase broker and external citation numbers;
  identities and references must remain valid.
- Coverage `memo_row_count` must equal the admitted projected broker row count;
  delete its compatibility-era `min(6, usable)` calculation in
  `SynthesisSkill` rather than leaving diagnostics on the old cap.
- Existing profile names and branch order remain unchanged.
- For a one-card fixture, `broker_usable_card_count` stays 1 before and after
  H2. `broker_status` changes from `absent` to `single_institution`, one broker
  row/citation becomes available, `memo_row_count` changes from 0 to 1, and
  `memo_refs_resolved` becomes true. These are expected diagnostics/display
  changes; the selected evidence-profile branch must remain unchanged.

## Allowed Files

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/report_skills/synthesis_skills.py` only to remove the stale
  `min(6, usable)` coverage calculation.

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_synthesis_skills.py` only if a profile-equivalence
  regression needs an explicit fixture;
- `tests/test_runtime_hygiene.py` only for removal assertions.

Workflow notes under `docs/agent_workflow/` are allowed.

## TDD Plan

### Batch 1: Complete annual snapshot body

RED:

- a canonical annual argument longer than 300 characters is currently cut;
- assert the snapshot row preserves its complete cleaned tail;
- assert source cards in `ctx` are unchanged;
- assert the Chapter4 ViewModel still respects role budgets.

GREEN:

- delete the `max_chars` argument and truncation branch only.

### Batch 2: Remove broker snapshot cap

RED:

- provide eight guarded broker items with distinct source identities;
- assert snapshot has all eight rows and eight broker citations;
- assert coverage `memo_row_count` reports eight rather than six;
- assert formal-medium ViewModel still has at most five non-risk and two risk
  rows;
- assert citation identities and external offsets remain valid.

GREEN:

- replace `selected[:6]` with the admitted complete selection.

### Batch 3: Sparse broker observation

RED:

- one guarded broker item yields `single_institution`, one attributed row, and
  unchanged usable count/profile;
- one rejected item still yields `absent` and no row;
- formal-thin output contains the existing single-institution label and the
  source citation.
- an external target row duplicating the sparse broker fact is rejected as an
  owner duplicate, while an external row with a new concrete anchor remains.

GREEN:

- admit every non-empty guarded selection and derive status without adding a
  new state.

## Requirement-Test Matrix

| Requirement | Test |
|---|---|
| Annual body is not cut at 300 | long canonical source-unit fixture |
| Cleaner still removes PDF/OCR display noise | existing A-share/HK cleanup fixtures |
| Producer cards are not mutated | deep-copy equality assertion |
| Annual final row count stays bounded | ViewModel role-budget assertion |
| All loader-returned broker items reach snapshot | eight-item snapshot fixture |
| Coverage row count follows the uncapped projection | synthesis coverage fixture |
| Final formal-medium broker budget is unchanged | five non-risk plus two risk assertion |
| One card renders as non-consensus observation | single-item status/renderer fixture |
| Sparse broker owns only duplicate external facts | duplicate-plus-delta external fixture |
| Rejected broker item remains absent | guard negative fixture |
| Profile routing is unchanged | one-item before/after usable-count fixture |
| Citation identities/offsets remain valid | mixed annual/broker/external fixture |
| No second selector/cap appears | runtime hygiene assertion or AST audit |

## Failure Modes And Stops

| Failure mode | Symptom | Guard/stop |
|---|---|---|
| Full annual body becomes report dump | 4.1 row count grows without bound | role-budget test; stop if selector must be redesigned |
| Cleaner removal restores OCR noise | PDF headers/CJK spacing visible | existing noisy fixtures |
| Broker cap merely moves elsewhere | snapshot still has fewer rows than loader output | eight-item test and runtime audit |
| Sparse card is written as consensus | unattributed/generalized broker sentence | exact institution/label renderer test |
| Sparse card hides incremental external evidence | 4.3 loses a new anchor/event | duplicate-plus-delta external fixture |
| Profile changes because status is reused incorrectly | one-card fixture changes profile | profile-equivalence test |
| Citation offsets drift | wrong or missing external refs | mixed-source citation test |
| Scope expands to producer/renderer/scoring | unrelated behavior change | stop and return to design |

Stop if implementation needs producer schema changes, renderer behavior
changes, profile branch changes, a new status consumed outside the snapshot,
or runtime files beyond the two named above. Runtime target is a net reduction;
stop if H2 adds more than 20 runtime lines.

## Verification

1. focused snapshot/renderer/synthesis tests;
2. full `pytest`;
3. `bash tools/ci_grep_gates.sh`;
4. `git diff --check`;
5. offline three-stock snapshot comparison for 中际旭创, 复旦微电, 黑芝麻智能;
6. before commit, run local-cache `--fast-test --no-pdf` reports for 中际旭创,
   复旦微电, and 黑芝麻智能; verify fresh reports, Chapter 4 row/citation
   integrity, and the three quality gates. Stop and report if the run requires
   unavailable network data rather than weakening the verification.

## Design Delta After Self-Review

Accepted:

- coverage diagnostics must remove their own `min(6, usable)` compatibility
  cap in the same batch;
- one-card admission explicitly changes display/citation diagnostics but not
  the evidence-profile branch;
- complete snapshot retention remains separate from existing final-layout
  budgets and renderer compaction;
- "all arguments" is defined as all unique, guarded arguments rather than raw
  or duplicate source material.

Rejected:

- removing the loader budget, because source intake needs one explicit bounded
  owner;
- removing annual role budgets or broker `5+2` display budgets, because that
  would turn H2 into a report-layout redesign;
- adding a new `sparse_observation` status, because the existing
  `single_institution` contract already conveys non-consensus material.

Deferred:

- any change to the renderer's 140/320/180 visible-text compaction;
- any quality-ranking or family-diversity change;
- visual PDF comparison; Markdown report reruns are required before commit.

Repository review required: `yes`. H2 changes visible formal-material policy
and citation counts even though its runtime scope is narrow.
