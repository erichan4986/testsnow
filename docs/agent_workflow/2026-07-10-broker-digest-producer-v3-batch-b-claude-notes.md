<!-- markdownlint-disable MD013 -->

# Broker Digest Producer V3 Batch B Implementation Notes

> Date: 2026-07-10
> Status: completed
> Verdict: Batch B passes; producer v3 is ready for a newly generated 中际旭创 report

## Changed Files

**Runtime file (within budget):**

- `scripts/utils/broker_research_digest.py`

**Test file:**

- `tests/utils/test_broker_research_digest.py`

No note writer, renderer, synthesis/profile, scoring, target-price, risk, technical,
recommendation, collection, LLM prompt, report, data, or knowledge files were modified.

## RED / GREEN Process

### Task 1: Lock Family Admission With Failing Tests

1. Added `test_digest_rejects_claim_without_evidence_per_family` (parametrized):
   asserts that one-clause claim-only paragraphs under each family heading produce
   no card of that family.
2. Added `test_digest_admits_claim_with_evidence_per_family` (parametrized):
   asserts that the minimum positive claim/evidence shapes from the task doc produce
   exactly one matching card containing the original sentence.
3. Ran only the new tests → RED:
   - `broker_core_view` positive failed (old length validator rejected the 38-char sentence).
   - `broker_product_driver` positive failed (same length validator).
   - `broker_risk_note` and `broker_earnings_forecast` positives already passed, locking
     behavior.

### Task 2: Lock Complementary Selection And Source Fidelity

1. Added `test_digest_selects_complementary_units_and_drops_semantic_duplicate`:
   a `产品布局` section with demand claim, customer/order evidence, and a repeated
   demand sentence must keep the first two and drop the third while preserving order.
2. Added `test_digest_selected_units_are_ordered_source_substrings_in_cleaned_text`:
   splits the final excerpt by terminators and asserts every unit occurs verbatim in
   the cleaned source at monotonically increasing positions.
3. Added `test_digest_preserves_cross_heading_product_driver_complementarity`:
   `产业趋势` demand content and `竞争格局` technology/customer content must both survive.
4. Ran only the new tests → RED: the old condenser kept the semantic duplicate, and
   the cross-heading selector only retained one heading candidate.

### Task 3 & 4: Replace Helpers With One Selector

1. Implemented `_unit_roles`, `_complete_source_units`, `_family_requirements_met`,
   `_unit_token_overlap`, and `_select_excerpt_units`.
2. Replaced `_condense_excerpt` and `_unit_has_signal` with `_complete_source_units`.
3. Replaced the four legacy `_is_valid_*` validators with `_family_requirements_met`
   plus preserved table/rating/risk-only guards inside `_select_excerpt_units`.
4. Replaced `_select_section_candidates` to retain up to two non-duplicate product-driver
   heading candidates; all other families keep the best admitted candidate.
5. Replaced `_fallback_excerpt` to call `_select_excerpt_units` for `broker_core_view`
   then `broker_product_driver`.
6. Threaded `card_type` through `_extract_section_candidates` and cleaned each heading
   occurrence through `_select_excerpt_units` before scoring.
7. For product-driver headings, joined the selected heading excerpts and applied only
   `_bounded_complete_excerpt` so cross-heading complementarity is preserved.
8. Deleted `_extract_section`, `_condense_excerpt`, `_unit_has_signal`, `_is_valid_excerpt`,
   `_is_valid_product_driver_excerpt`, `_is_valid_forecast_excerpt`, and `_is_valid_risk_excerpt`.
9. Ran all producer tests → GREEN.

## Deleted Legacy Helpers

- `_extract_section`
- `_select_section_candidates` (replaced)
- `_condense_excerpt`
- `_unit_has_signal`
- `_fallback_excerpt` (replaced)
- `_is_valid_excerpt`
- `_is_valid_product_driver_excerpt`
- `_is_valid_forecast_excerpt`
- `_is_valid_risk_excerpt`

## Family Admission Test Results

| Family | Negative (claim only) | Positive (claim + evidence) |
| --- | --- | --- |
| `broker_core_view` | rejected | admitted, original sentence preserved |
| `broker_product_driver` | rejected | admitted, original sentence preserved |
| `broker_earnings_forecast` | rejected | admitted, original sentence preserved |
| `broker_risk_note` | rejected | admitted, original sentence preserved |

All negative and positive cases pass after implementation.

## Source Substring / Order Proof

- `_complete_source_units` splits only on `。；;！？!?`, preserving the terminator.
- Every returned unit is `clean_broker_research_excerpt_text`-cleaned but otherwise a
  verbatim slice of the cleaned source.
- `_select_excerpt_units` selects units in source order; the final excerpt is joined
  with spaces and bounded by `_bounded_complete_excerpt`.
- `test_digest_selected_units_are_ordered_source_substrings_in_cleaned_text` verifies
  that every non-empty unit in the final excerpt occurs verbatim in the cleaned source
  and at monotonically increasing positions.

## Test Results

### Focused tests

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_broker_research_digest.py \
  tests/utils/test_broker_research_digest_note_writer.py \
  tests/utils/test_broker_research_digest_synthesis_items.py \
  -q -p no:cacheprovider

75 passed, 3 skipped in 0.65s
```

### Downstream contract tests

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_report_quality.py \
  -q -p no:cacheprovider

283 passed in 2.94s
```

### Repository gates

```text
bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# no output (no whitespace errors)
```

## Runtime Additions / Deletions / Net Delta

Measured against the Batch A commit (`a564898`) for the only modified runtime file:

| File | Additions | Deletions | Net |
| --- | --- | --- | --- |
| `scripts/utils/broker_research_digest.py` | 214 | 165 | **+49** |

Target was ≤ +80 net runtime lines; hard stop was +100. Combined Batch B net is **+49**,
well within target.

## Requirement-Test Matrix

| Requirement | Implementation | Test / result |
| --- | --- | --- |
| Claim-without-evidence rejection per family | `_family_requirements_met()` role contract | `test_digest_rejects_claim_without_evidence_per_family` → pass |
| Claim/evidence admission per family | `_family_requirements_met()` role contract | `test_digest_admits_claim_with_evidence_per_family` → pass |
| Within-section role complementarity | `_select_excerpt_units()` source-order role-novelty + redundancy check | `test_digest_selects_complementary_units_and_drops_semantic_duplicate` → pass |
| Core view requires evidence or causal mechanism | `_family_requirements_met()` does not treat a driver topic alone as support | `test_digest_rejects_claim_without_evidence_per_family`, `test_digest_core_view_accepts_causal_business_reason_without_numbers` → pass |
| Distinct forecast facts survive deduplication | `_units_redundant()` preserves units with different numeric fact sets | `test_digest_keeps_same_wording_forecasts_with_distinct_periods_and_values` → pass |
| Cross-heading product-driver complementarity | `_select_section_candidates()` retains two non-duplicate heading candidates; joined excerpt preserves both | `test_digest_preserves_cross_heading_product_driver_complementarity` → pass |
| Source substring / original order preserved | `_complete_source_units()` + order-preserving selection | `test_digest_selected_units_are_ordered_source_substrings_in_cleaned_text` → pass |
| Coherent fallback admitted | `_fallback_excerpt()` calls `_select_excerpt_units()` | `test_digest_falls_back_to_first_meaningful_pages_when_no_headings` → pass |
| Incoherent fallback rejected | `_fallback_excerpt()` returns empty when family contract not met | `test_digest_rejects_incoherent_fallback_without_business_reason` → pass |
| Single selector, no parallel paths | `_select_excerpt_units()` is the only admission/selection owner | code review + all tests pass |
| Table/rating/risk guards preserved | `_select_excerpt_units()` early returns for forecast tables, generic risks, and risk-only product text | `test_generic_risk_with_financial_table_is_dropped_but_specific_risk_survives`, `test_table_only_earnings_forecast_is_dropped`, `test_digest_does_not_classify_risk_sentence_as_product_driver` → pass |
| Runtime budget | net +49 runtime lines | `git diff --numstat` → within +80 target |

## Blocker / Warning / Deviation

- **Blockers:** None.
- **Stop conditions:** None triggered. No second/third semantic selector, no source text
  paraphrasing, no stock/industry-specific role dictionaries, no changes outside the
  allowed runtime/test files.
- **Deviation from task pseudocode:**
  - The task's `_select_excerpt_units` pseudocode sorted units by `_section_candidate_score`
    and skipped units with no new roles. In practice that dropped distinct evidence units
    (e.g., second and third core-view sentences) and selected a later semantic duplicate
    over an earlier one. The implementation uses a source-order pass with role novelty and
    a generic token-overlap redundancy check (threshold 0.5) to drop near-duplicate units
    while keeping complementary content. This is still a single selector function.
  - The task suggested re-running `_select_excerpt_units` on joined product-driver heading
    excerpts. Doing so dropped the second heading's content when its roles were already
    covered. Instead, the implementation joins the already-admitted heading excerpts and
    applies only `_bounded_complete_excerpt` for boundary safety, preserving cross-heading
    complementarity.
- **Budget note:** Net +49 leaves ample headroom; no risk of exceeding the +100 hard stop.

## Ready For 中际旭创 Report Generation

Yes. Batch B focused tests, downstream contract tests, CI grep gates, and
`git diff --check` all pass. The producer now enforces an explicit claim/evidence
contract for all four broker card families, preserves source order and verbatim
source substrings, drops semantic duplicates, and keeps complementary cross-heading
product-driver content. Runtime net growth is +49 lines, within the +80 target.

## Codex Acceptance Addendum

Codex reviewed the actual Batch B diff and found two correctness gaps before
commit:

1. Character-set overlap could classify two otherwise identical forecast
   sentences for different years and values as duplicates. `_units_redundant()`
   now refuses deduplication when the units carry different numeric fact sets.
2. The core-view contract accepted `claim + driver`, allowing a sentence such
   as “核心产品市场需求有望增长” without a supporting reason. Core views now
   require `claim + evidence` or `claim + causal mechanism`; generic causal
   terms such as “推动 / 带动 / 支撑 / 来自 / 受益于” populate the mechanism
   role without adding stock-specific vocabulary.

Fresh acceptance results are 75 passed / 3 skipped for producer tests, 283
passed downstream, all CI grep gates passed, and `git diff --check` is clean.
Batch B runtime net growth is +49 lines.
