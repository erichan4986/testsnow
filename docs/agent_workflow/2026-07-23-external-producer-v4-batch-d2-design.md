# External Producer v4 Batch D2 Final Cleanup Design

Date: 2026-07-23
Status: approved for planning
Branch: `codex/pipeline-stabilization`

## 1. Goal

Finish the deletion/compression exit gate for External Producer v4 without changing pack content, selector behavior,
report prose, or the stable display envelope.

Batch D1 removed the unused preview-to-synthesis bridge. D2 removes the remaining v3 identity leak, prevents old
external schemas and deleted paths from returning, and performs only readability-preserving local compression in
the strict v4 pack owner.

## 2. Invariants

1. `curated_external_argument_pack.v4` remains the only active external argument pack schema.
2. `external_scope.py` remains the only scope owner.
3. `external_evidence.py` remains the only family owner.
4. `external_pack.py` remains the only strict pack builder/reader owner.
5. `curated_external_display.py` remains the only display-envelope writer.
6. The stable envelope keys consumed by freshness, synthesis, and assembly do not change.
7. No LLM call, source acquisition, canonical-pack rewrite, report generation, or prompt change is permitted.
8. No behavior is removed merely to satisfy a line-count target.

## 3. Approaches Considered

### A. Contract-first local cleanup (selected)

Replace the stale v3 source-kind label with a version-neutral identity, extend the existing v4 cutover guard against
retired external schemas/paths, and merge only exact duplicate pack-failure construction and zero-value wrappers.

This gives the strongest rollback and review story with the smallest behavioral surface.

### B. Split `external_pack.py`

Rejected. A new reader module would reduce one file's length while increasing total runtime and making the single
reader ownership rule easier to violate.

### C. Aggressive inlining

Rejected. It would reduce lines but make strict source, scope, citation, and narrative validation harder to audit.

## 4. Runtime Changes

### 4.1 Version-neutral risk provenance

In `scripts/utils/report_skills/assembly_skills.py`, structured external risk signals use
`curated_external_argument` instead of `curated_external_argument_v3`.

This is the sole allowed externally observable change in D2: provenance metadata changes from a stale versioned
label to a version-neutral label. It must not affect signal count, risk score, recommendation, target price, or
display eligibility. The assembly contract test must assert the exact new value and preserve the existing signal
set.

### 4.2 Strict pack cleanup

In `scripts/utils/external_pack.py`:

- replace `_incomplete` and `_source_input_degraded` with one private failure-pack constructor with the contract
  `_failure_pack(status, stock_name, prepared, *, source_documents=(), rejection_reason=None)`;
- `selector_incomplete` retains the validated source documents and adds exactly one `rejection_reasons` entry;
- `source_input_degraded` retains no source documents and does not add `rejection_reasons`;
- remove the `_build_target_cards` pass-through wrapper and call the existing run builder directly;
- preserve every current validation branch, reason code, field, ordering rule, citation rule, and narrative-plan
  check.

The roughly-350-line module target is advisory. D2 must not split the reader or compress validation into opaque
expressions merely to meet it.

### 4.3 Regression guard

Extend the existing `tests/utils/test_external_v4_cutover.py` static guard rather than creating a second grep owner.
It rejects active runtime schema/source-kind literals and imports of:

- `curated_external_argument_v2` or `curated_external_argument_v3`;
- `curated_external_argument_pack.v2`, `.v3`, or `.v3.1`;
- deleted runtime module names from the v4 cutover and D1 bridge removal, including imports of
  `curated_external_to_synthesis_items`.

The guard scans active Python runtime under `scripts/`, explicitly excluding `scripts/archive/`. It must not reject
the current `curated_external_unit_selection.v2` contract or unrelated versioned components such as Broker Digest
v3. Module names are checked as imports; schema and source-kind identities are checked as exact text literals. This
avoids rejecting explanatory comments while still blocking static or dynamic schema fallback. The same test also
asserts the following exact owner map by AST function-definition scan:

- `resolve_external_scope` -> `external_scope.py`;
- `external_family_title` and `validate_external_evidence_unit` -> `external_evidence.py`;
- `build_external_argument_pack_v4` and `read_external_argument_pack_v4` -> `external_pack.py`;
- `build_curated_external_argument_display` -> `curated_external_display.py`.

The writer assertion additionally uses AST dictionary-key inspection to prove that
`_curated_external_argument_cards` is assigned once in active runtime and in `curated_external_display.py`.
`tools/ci_grep_gates.sh` remains unchanged and still runs as an independent existing gate.

## 5. Tests

TDD order:

1. RED: update the assembly contract test to assert that the structured external risk source kind is
   version-neutral while the signal set is unchanged; rename the two stale `v3` test names in the same file.
2. RED: extend the existing v4 cutover guard and prove the existing v3 label fails it.
3. GREEN: replace the stale label.
4. Strengthen the existing failure-pack tests to assert source-document retention and the exact presence/absence of
   `rejection_reasons`.
5. Refactor pack failure construction and target-card delegation with the existing `test_external_pack.py` suite
   green before and after each change.

Required verification:

- focused external-pack and assembly tests;
- complete v4 external suite;
- complete offline `pytest` suite;
- `bash tools/ci_grep_gates.sh`;
- `git diff --check`;
- static owner/writer guard plus repository search proving no retired external schema/path in active runtime.

## 6. Failure Modes

| Failure | Observable symptom | Gate |
|---|---|---|
| Versioned provenance remains | `curated_external_argument_v3` appears in active runtime | assembly test + cutover guard |
| Guard is overbroad | current selection v2, unrelated Broker Digest or archived code fails | cutover guard fixture/scan |
| Failure-pack fields change | selector-incomplete/degraded fixtures fail | external-pack tests |
| Degraded input keeps source documents | fail-closed contract changes | existing degraded-source tests |
| Citation or card ordering changes | strict reader tests fail | external-pack suite |
| A second owner or writer appears | duplicate owner definition or envelope assignment found | static cutover guard |
| Cleanup changes report behavior | snapshot/renderer contract tests fail | downstream focused suite |

## 7. Scope

Allowed runtime and gate files:

- `scripts/utils/external_pack.py`
- `scripts/utils/report_skills/assembly_skills.py`

Allowed tests:

- `tests/utils/test_external_pack.py`
- `tests/utils/test_external_v4_cutover.py`
- `tests/reporter/test_recommendation_decision.py`
- no fixture or canonical-pack rewrites.

Forbidden:

- selector prompt/schema changes;
- source acquisition or LLM logic changes;
- canonical pack, config, data, knowledge, or report changes;
- scoring, target price, technical analysis, recommendation, and risk-score changes;
- new compatibility branches or a second reader/resolver/writer.

## 8. Budget and Stop Conditions

Target runtime change: net deletion across the two allowed runtime files. Test and design lines are reported
separately and do not count toward the runtime budget.

Stop and return to design if:

- preserving behavior requires a new module or compatibility branch;
- any existing reason code, pack field, card order, citation identity, or envelope key must change;
- the full offline suite exposes an unrelated regression;
- runtime grows;
- the grep gate cannot distinguish retired external identifiers from legitimate unrelated versions.

## 9. Acceptance

D2 is accepted when all required tests and gates pass, active runtime contains only the v4 pack/card identities and
the current v2 ID-only selection contract, the display envelope has one writer, and the runtime diff is net-negative
with no report or canonical-pack changes.

## 10. Self-Review Record

### Round 1

Closed:

- removed the proposed duplicate shell grep owner and reused the existing v4 cutover test;
- defined the version-neutral `source_kind` as the only allowed observable metadata change;
- fixed the exact failure-pack constructor contract and diagnostics behavior;
- listed the three focused test files explicitly.

### Round 2

Closed:

- replaced an informal call-graph check with exact AST-owned symbol assertions;
- made display-envelope writer uniqueness mechanically testable through AST dictionary keys;
- limited retired module checks to imports and schema/source-kind checks to exact literals;
- clarified that the current ID-only selection schema remains v2 and must not be rejected;
- confirmed that the 350-line module target is advisory and cannot justify a new reader module.

Remaining blocker: none.
Remaining ambiguity: none.
Ready for implementation planning: yes.
