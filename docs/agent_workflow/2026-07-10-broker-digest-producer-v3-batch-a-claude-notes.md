# Broker Digest Producer V3 Batch A Implementation Notes

> Date: 2026-07-10
> Status: completed
> Verdict: Batch A passes; Batch B may start

## Changed Files

**Runtime files (within budget):**

- `scripts/utils/broker_research_digest.py`
- `scripts/utils/broker_research_digest_note_writer.py`

**Test files:**

- `tests/utils/test_broker_research_digest.py`
- `tests/utils/test_broker_research_digest_note_writer.py`

No renderer, synthesis/profile, scoring, target-price, risk, technical, recommendation,
collection, LLM prompt, report, data, or knowledge files were modified.

## RED / GREEN Process

### Task 1: Version Cards And Note Freshness

1. Added `test_digest_cards_include_selection_version` asserting
   `card["selection_version"] == "broker_digest_v3"`.
2. Added `test_broker_digest_writer_refreshes_current_note_missing_selection_version`
   and `test_broker_digest_writer_skips_existing_note_with_selection_version`.
3. Ran selected tests → RED (3 failures: missing card key, missing frontmatter field,
   stale note treated as current).
4. Implemented:
   - `SELECTION_VERSION = "broker_digest_v3"` in producer.
   - Added `"selection_version": SELECTION_VERSION` to `_build_card()`.
   - Imported `SELECTION_VERSION` into note writer.
   - `_render_note()` now writes both `excerpt_cleaner_version: broker_ocr_v2`
     and `selection_version: broker_digest_v3`.
   - `_has_current_diagnostics_note_shape()` requires the current selection version.
5. Ran selected tests → GREEN.

### Task 2: Explainable Scoring And Severe-Damage Rejection

1. Added `test_digest_diagnostics_explain_score_parts` asserting all six score parts
   and correct arithmetic.
2. Added `test_digest_rejects_severe_ocr_damage_candidate` with a keyword-heavy
   damaged heading occurrence and a clean competing occurrence.
3. Added `test_digest_valid_numbers_are_not_rejected_as_severe_damage` as a
   negative control for `2026年`、`57.3亿元`、`262.3%` and `1.6T光模块`.
4. Ran selected tests → RED (missing `score_parts`, no rejected status).
5. Implemented:
   - Added `SCORE_PART_KEYS` and `_EXCERPT_TERMINATORS` module constants.
   - Added `_candidate_score_parts`, `_candidate_total`, `_has_severe_ocr_damage`.
   - Replaced `_quality_score` and `_section_candidate_score` with score-parts-based
     implementations.
   - Replaced `_diagnostic_entry()` to include `score_parts` and require `text`.
   - Updated `_section_selection_diagnostics()` to assign
     `status="rejected", reason="rejected_ocr_damage"` before selected/skipped logic.
   - Updated `_select_section_candidates()` to exclude severely damaged candidates.
   - Updated generic-driver and fallback diagnostic call sites to pass `text`.
   - Note writer imports `SCORE_PART_KEYS` and renders them compactly in diagnostics.
   - Updated existing refresh test assertions for the new diagnostic line format.
6. Ran selected tests → GREEN.

### Task 3: Boundary-Safe Excerpts

1. Added `test_digest_retreats_to_sentence_boundary_when_900_falls_mid_clause`.
2. Added `test_digest_extends_to_nearby_sentence_boundary_within_limit`.
3. Added `test_digest_selected_units_are_ordered_source_substrings`.
4. Added `test_digest_rejects_long_clause_without_sentence_boundary`.
5. Ran selected tests → RED (`[:900]` slicing produced mid-sentence endings).
6. Implemented:
   - Added `_bounded_complete_excerpt(text, limit=900, extension=80)` with extend-or-retreat
     policy; returns empty string when no boundary exists.
   - Replaced `_condense_excerpt` to use `_bounded_complete_excerpt` and to drop a trailing
     incomplete unit that lacks terminal punctuation.
   - Updated `_clean_excerpt` finalization from `text[:900].strip()` to
     `_bounded_complete_excerpt(text)`.
   - Updated `_fallback_excerpt` finalization to use `_bounded_complete_excerpt`.
   - Adjusted `clean_broker_research_excerpt_text` so it no longer strips terminal
     sentence punctuation (`。；;`) from either end; leading/trailing colon/space cleanup
     is preserved.
7. Ran selected tests → GREEN.

## Test Results

### Focused tests

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_broker_research_digest.py \
  tests/utils/test_broker_research_digest_note_writer.py \
  tests/utils/test_broker_research_digest_synthesis_items.py \
  -q -p no:cacheprovider

60 passed, 3 skipped in 0.51s
```

### Downstream contract tests

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_report_quality.py \
  -q -p no:cacheprovider

283 passed in 3.79s
```

### Repository gates

```text
bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# no output (no whitespace errors)
```

## Runtime Additions / Deletions / Net Delta

| File | Additions | Deletions | Net |
| --- | --- | --- | --- |
| `scripts/utils/broker_research_digest.py` | 100 | 30 | +70 |
| `scripts/utils/broker_research_digest_note_writer.py` | 9 | 0 | +9 |
| **Combined runtime** | **109** | **30** | **+79** |

Target was ≤ +80 net runtime lines; hard stop was +100. Combined net is **+79**, within target.

## Requirement-Test Matrix

| Requirement | Implementation | Test / result |
| --- | --- | --- |
| `selection_version` on cards | `scripts/utils/broker_research_digest.py:_build_card()` adds `selection_version` | `test_digest_cards_include_selection_version` → pass |
| `selection_version` on notes | `scripts/utils/broker_research_digest_note_writer.py:_render_note()` writes frontmatter | `test_broker_digest_writer_skips_existing_note_with_selection_version` → pass |
| Stale note refresh (missing `selection_version`) | `_has_current_diagnostics_note_shape()` requires current selection version | `test_broker_digest_writer_refreshes_current_note_missing_selection_version` → pass |
| Six score parts persisted | `_candidate_score_parts()` + `_diagnostic_entry()` include `score_parts` | `test_digest_diagnostics_explain_score_parts` → pass |
| Severe OCR/numeric damage rejected | `_has_severe_ocr_damage()` threshold; `_select_section_candidates()` excludes; diagnostics mark `rejected_ocr_damage` | `test_digest_rejects_severe_ocr_damage_candidate` → pass |
| Valid numbers not mistaken for damage | generic defect regexes ignore well-formed numbers/years | `test_digest_valid_numbers_are_not_rejected_as_severe_damage` → pass |
| Normal PDF line wraps not treated as severe damage | Chinese-gap weight remains a weak signal; severe threshold requires many gaps or a strong numeric/year defect | `test_digest_clean_pdf_line_wraps_are_not_severe_ocr_damage` → pass |
| Retreat to sentence boundary at 900 | `_bounded_complete_excerpt()` retreats to previous terminator | `test_digest_retreats_to_sentence_boundary_when_900_falls_mid_clause` → pass |
| Extend to nearby boundary within 80 chars | `_bounded_complete_excerpt()` extends when next terminator is in extension window | `test_digest_extends_to_nearby_sentence_boundary_within_limit` → pass |
| Source substring / original order preserved | `_condense_excerpt()` keeps complete units verbatim | `test_digest_selected_units_are_ordered_source_substrings` → pass |
| Long clause without boundary rejected/empty | `_bounded_complete_excerpt()` returns `""` when no terminator exists | `test_digest_rejects_long_clause_without_sentence_boundary` → pass |
| Card identity follows final excerpt | `_build_card()` hashes the selected boundary-safe excerpt | `test_digest_card_identity_hashes_final_selected_excerpt` → pass |
| Source boundaries unchanged | producer still sets `professional_analysis`, `confirmed_fact=false`, `scoring_eligible=false`, `risk_score_eligible=false` | `test_digest_extracts_high_value_sections_and_is_professional_analysis` + downstream source-boundary tests → pass |
| Runtime budget | net +79 runtime lines | `git diff --numstat` → within +80 target |

## Blocker / Warning / Deviation

- **Blockers:** None.
- **Stop conditions:** None triggered. No third runtime file, no stock-specific OCR replacement,
  no LLM rewriting, no renderer/profile/scoring/target/risk/technical/recommendation/collection
  changes, and output remains composed of ordered source substrings.
- **Deviation:** `clean_broker_research_excerpt_text()` no longer strips trailing `。；;`. This is
  intentional: boundary-safe excerpts must preserve terminal punctuation. Note writer/reader tests
  still pass because they assert content, not trailing punctuation.
- **Budget note:** Net +79 is at the upper end of the +80 target. Batch B must stay similarly tight
  and stop at +100.

## Ready For Batch B

Yes. Batch A focused tests, downstream contract tests, CI grep gates, and `git diff --check` all
pass. Runtime net growth is +79 lines (within the +80 target and under the +100 hard stop).

Before starting Batch B, verify that the existing `test_digest_prefers_clean_candidate_instead_of_`
family of tests still behaves as expected under the new score parts, since Batch B will replace
`_select_section_candidates`, `_fallback_excerpt`, and the family validators.

## Codex Acceptance Addendum

Codex reviewed the actual diff rather than relying on this summary and found two
coverage/correctness gaps before commit:

1. The original retreat/extension tests passed through `_condense_excerpt()` and
   did not force `_bounded_complete_excerpt()` to its 900/980-character limits.
   They now call the boundary owner directly and assert exact retreat/extension
   output.
2. Three ordinary CJK line wraps produced the old severe threshold of 24 and
   could reject a clean PDF paragraph. A new failing negative-control test was
   added. CJK gaps now contribute 4 points each, while dangling decimals and
   broken years contribute 40 points each; the severe threshold is 40. This
   preserves strong numeric rejection while requiring many whitespace gaps to
   reject on spacing alone.

Fresh acceptance results are 60 passed / 3 skipped for producer tests, 283
passed downstream, all CI grep gates passed, and `git diff --check` is clean.
Runtime net growth remains +79 lines.
