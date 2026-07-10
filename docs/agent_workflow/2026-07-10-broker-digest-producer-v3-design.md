# Broker Digest Producer V3 Design

> **Date**: 2026-07-10
> **Owner**: Codex
> **Status**: Under Round 2 Review

## 1. Goal

Improve deterministic broker-research excerpts so each visible card preserves a
coherent analyst claim, its supporting evidence, and the main difference from
other cards. The producer must reject damaged fragments instead of repairing
them into synthetic-looking prose.

Success is measured in the structured card and persisted note, before Chapter 4
rendering. This batch does not add an LLM memo.

## 2. Invariants

- Keep the existing four card families: core view, product driver, earnings
  forecast, and risk note. Broaden their content coverage through selection,
  not through new section types.
- Broker content remains `professional_analysis`, never confirmed fact.
- Cards remain outside scoring, risk scoring, target price, recommendation, and
  technical-analysis inputs.
- Preserve original sentence order and wording. The producer may remove noise
  and omit units, but must not paraphrase or join non-contiguous clauses into a
  new factual claim.
- Do not add stock-specific OCR replacements.
- Do not modify renderer, evidence-profile routing, `KnowledgeSynthesizer`
  prompts, source collection, or PDF download behavior.
- Keep runtime growth bounded per implementation batch: target at most 80 net
  new runtime lines and stop at 100. New logic must replace the legacy helpers
  listed in Section 9 rather than run beside them.

## 3. Current Failure

The producer currently finds heading spans, cleans each span into one string,
condenses the first signal-bearing units, and assigns a single integer score.
That creates three failure modes:

1. A high-keyword but damaged span can outrank a coherent analyst paragraph.
2. The first five signal units need not form a claim-and-evidence pair.
3. Diagnostics expose only one total score, so poor output cannot be traced to
   completeness, OCR damage, boilerplate, or weak evidence.

The renderer then receives a short label-like excerpt and cannot recover the
discarded argument.

## 4. Options

### A. Expand the OCR replacement table

Small change, but source-specific and unbounded. It can silently invent words
inside damaged financial claims. Rejected.

### B. Add an LLM broker memo

Potentially readable, but combines extraction, rewriting, attribution, and
citation risk before the deterministic producer is trustworthy. Deferred.

### C. Score and select complete source units

Keep deterministic extraction, but select complete sentence/paragraph units
with explicit score components and complementary coverage. Chosen.

## 5. Candidate Contract

Each heading occurrence remains one heading candidate. Its cleaned source span
is split into ordered source units using paragraph, bullet, and Chinese sentence
boundaries. A unit is eligible only when it is a complete source substring and
contains enough semantic signal for the target card family.

Internally each candidate carries:

```text
heading, order, excerpt, selected_units,
score_parts = {
  signal, evidence, completeness, coherence,
  ocr_penalty, noise_penalty
},
total_score, status, reason
```

`total_score` is the sum of positive components minus penalties. Diagnostics
persist both the total and the score parts. No score component changes source
credit or guardrails.

## 6. Unit Selection

### 6.1 Complete units

- Prefer units ending in `。`, `；`, `！`, or `？`.
- A final unit without terminal punctuation may be admitted only when it is a
  complete bullet or short heading body and has no dangling numeric/text marker.
- Never cut with `text[:N]` when a preceding sentence boundary is available.
- A bounded extension beyond the preferred length is allowed to reach the next
  nearby sentence boundary.

### 6.2 Card-family intent

- **Core view**: one directional conclusion plus at least one business or
  financial reason.
- **Product driver**: product/demand/customer/capacity claim plus evidence or a
  second distinct driver cluster.
- **Earnings forecast**: forecast/rating claim plus period, metric, assumption,
  or valuation evidence.
- **Risk note**: named risk plus its transmission mechanism or affected metric.

Cards should normally contain two to five complete units. A single unit is
allowed only when it already contains both claim and evidence.

### 6.3 Complementarity

For card families that admit multiple units, selection preserves original order
and prefers coverage of different semantic roles. Near-duplicate units or units
from the same viewpoint cluster do not consume the excerpt budget twice.

The producer may choose non-adjacent complete units only when they remain
separate sentences in original order. It must not splice partial clauses.

## 7. Quality Scoring

Positive components:

- `signal`: target-family terms and directional language;
- `evidence`: complete numbers, periods, products, customers, orders, capacity,
  margins, or explicit causal support;
- `completeness`: terminal punctuation and grammatical sentence shape;
- `coherence`: claim/evidence pairing and complementary semantic roles.

Penalties:

- `ocr_penalty`: Chinese character gaps, dangling decimals, broken year/unit
  sequences, isolated conjunctions, or incomplete numeric comparisons;
- `noise_penalty`: tables, ratings boilerplate, analyst metadata, repeated page
  headers, source labels, and disclaimers.

A candidate with severe OCR or numeric damage is rejected even if its total
keyword score is high. Generic OCR detection should identify damage; it should
not guess replacement text.

## 8. Diagnostics And Refresh

- Add `selection_version: broker_digest_v3` to cards and note frontmatter.
- Persist score parts in `Selection Diagnostics` in a compact stable form.
- `_render_note()` writes both `excerpt_cleaner_version: broker_ocr_v2` and
  `selection_version: broker_digest_v3` during the transition.
- `_has_current_diagnostics_note_shape()` requires the current selection
  version in addition to the existing schema, cleaner, reason, and diagnostics
  markers. Notes missing it are refreshed by the report-flow writer.
- `_is_legacy_broker_digest_note()` continues to identify and archive old broker
  notes; a current-schema note missing only `selection_version` is refreshed in
  place rather than treated as an unrelated file.
- `source_excerpt_hash` and `card_id` derive from the final selected excerpt.

Diagnostics are debug metadata only and do not render in Chapter 4.

## 9. Implementation Batches And Replacement Budget

### 9.1 Batch A: Candidate Integrity And Diagnostics

Batch A delivers:

- boundary-safe excerpt construction with no final `[:900]` slicing;
- explicit score parts and total score;
- severe OCR/numeric-damage rejection;
- `selection_version` card/note persistence and stale-note refresh;
- diagnostics that explain selected, skipped, and rejected candidates.

It replaces these producer helpers rather than adding a parallel path:

- `_condense_excerpt`
- `_quality_score`
- `_section_candidate_score`
- `_diagnostic_entry`

It modifies these writer functions in place:

- `_render_note`
- `_has_current_diagnostics_note_shape`
- `_is_legacy_broker_digest_note` only if needed to preserve archive semantics

The four replaced producer helpers currently occupy about 50 runtime lines.
Batch A may introduce at most 130 replacement lines across both runtime files,
for a target net delta of at most +80 and hard stop at +100.

### 9.2 Batch B: Semantic Pairing And Complementarity

Batch B delivers:

- source-unit semantic roles;
- card-family claim/evidence admission;
- complementary unit selection in source order;
- the same complete-unit rules for no-heading fallback.

It replaces or folds these helpers:

- `_select_section_candidates`
- `_fallback_excerpt`
- `_is_valid_excerpt`
- `_is_valid_product_driver_excerpt`
- `_is_valid_forecast_excerpt`
- `_is_valid_risk_excerpt`
- `_unit_has_signal` where its role is absorbed by family-specific scoring

These helpers currently occupy about 100 runtime lines. Batch B targets no more
than +80 net runtime lines and stops at +100. If a third selection path is
needed, implementation stops instead of adding it.

Batch A must pass before Batch B starts. Batch A may improve candidate integrity
without yet satisfying the final family-pairing acceptance criteria; the v3
feature is complete only after both batches pass.

## 10. Implementation Scope

Allowed runtime files:

- `scripts/utils/broker_research_digest.py`
- `scripts/utils/broker_research_digest_note_writer.py`

Allowed tests:

- `tests/utils/test_broker_research_digest.py`
- `tests/utils/test_broker_research_digest_note_writer.py`
- narrow reader/refresh tests only if the version field requires them

No other runtime file may change without stopping for review.

## 11. Failure Modes And Gates

| Failure | Visible symptom | Required gate |
| --- | --- | --- |
| Mid-sentence truncation | excerpt ends in a partial clause or number | sentence-boundary tests with short and long limits |
| Synthetic recombination | two source fragments become one unsupported sentence | assert selected sentences are ordered source substrings |
| OCR-heavy candidate wins | broken number/word appears in 4.2 | clean-vs-damaged candidate ranking test |
| Over-strict filtering | useful report produces no cards | coherent single-unit and no-heading fallback tests |
| Forecast/risk intent lost | wrong family wins or evidence disappears | one focused test per card family |
| Diagnostics cannot explain choice | note has only total score | score-part and selection-version writer tests |
| Stale notes survive v3 | report still loads v2 excerpt | note refresh test for missing/old selection version |
| Source boundary regression | broker claim becomes official/scoring input | existing source-boundary and CI grep gates |

Batch A additionally requires tests proving that severe OCR damage produces a
`rejected` diagnostic rather than merely a lower selected score, and that a
normal multi-digit citation or financial number is not mistaken for damage.

Batch B additionally requires one claim-without-evidence rejection test per card
family and a source-substring assertion for every selected unit.

## 12. Verification

Focused tests:

```text
tests/utils/test_broker_research_digest.py
tests/utils/test_broker_research_digest_note_writer.py
tests/utils/test_broker_research_digest_synthesis_items.py
tests/reporter/test_synthesis_skills.py
tests/reporter/test_deep_analysis_renderer.py
tests/reporter/test_report_source_boundary.py
tests/reporter/test_report_quality.py
```

Then run `tools/ci_grep_gates.sh` and `git diff --check`.

CI acceptance uses deterministic synthetic fixtures. The newly generated
中际旭创 report remains a local post-implementation acceptance step; its mtime
must be later than the final producer commit, but CI does not depend on that
mtime or report artifact.

Formal report acceptance uses a newly generated 中际旭创 report. The run must
prove the report mtime is later than the producer commit. Review 4.2 for coherent
claim/evidence pairs, broken numbers, OCR gaps, attribution, and citation hygiene.

## 13. Stop Conditions

Stop and return to design if implementation requires:

- an LLM rewrite;
- changes to renderer or evidence-profile routing;
- source-specific OCR word guessing;
- new card families;
- altered scoring, target price, risk, recommendation, or technical paths;
- more than 100 net new runtime lines in either batch.

## 14. Design Delta After Round 1

### Accepted

- Made `selection_version` writer and freshness-check ownership explicit.
- Retained `excerpt_cleaner_version` during migration.
- Split implementation into two bounded batches and listed the legacy helpers
  each batch replaces.
- Added explicit severe-damage rejection, complete-boundary, score-part,
  source-substring, family-pairing, stale-refresh, and hash tests.
- Clarified that report mtime validation is local acceptance, not a CI gate.

### Rejected

- The review described missing runtime implementation as separate design
  blockers. Those items remain implementation requirements, not evidence that
  the target architecture is invalid. They are now assigned to Batch A or B.

### Deferred

- Removing `excerpt_cleaner_version`; it remains useful while v2 notes exist.
- LLM rewriting and new card families.

### Round 2 Required

Yes. Round 1 contained blockers and the implementation was split into two
batches, which materially changes delivery and budget enforcement.
