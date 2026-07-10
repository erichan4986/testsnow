verdict: needs_revision

summary:
The v3 design correctly diagnoses the current producer's main weaknesses: a single
integer score, hard 900-char truncation that can cut mid-sentence, no explicit
claim/evidence pairing, and diagnostics that cannot explain why a candidate was
rejected. The proposed move to complete source units, six score parts, and a
selection_version freshness marker is architecturally consistent with the existing
two-file runtime boundary and the professional_analysis source guardrails.

However, several design contracts are not yet supported by the current
implementation:

1. `selection_version` is proposed as the stale-note trigger, but the note writer
does not write or check it.
2. Score parts are not computed or persisted; diagnostics carry only a single
integer total.
3. Unit selection still slices to 900 chars and does not enforce the
terminal-punctuation / boundary-extension rules.
4. Existing validators check term presence and length, not the claim+evidence
pairing required for each card family.
5. Severe OCR/numeric damage is penalized but not rejected.
6. Complementarity is implemented across heading candidates, not across distinct
semantic roles within a section.

These gaps are fixable inside the allowed runtime files, but they require more
than a 60-line delta and likely more than 100 net new runtime lines unless
equivalent legacy logic (`_condense_excerpt`, `_quality_score`,
`_section_candidate_score`, `_diagnostic_entry`, and the writer's freshness check)
is explicitly replaced. The design should be revised to list those replacements
and confirm the net-line target before coding begins.

blockers:
  - id: B1
    issue: selection_version refresh contract is not implementable with the current note writer
    evidence: |
      `broker_research_digest_note_writer.py:193-203` `_has_current_diagnostics_note_shape`
      checks `schema_version`, `selection_reason`, `excerpt_cleaner_version`, and the
      `## Selection Diagnostics` heading, but never `selection_version`.
      `_is_legacy_broker_digest_note` (`:206-215`) also ignores `selection_version`.
      Design §8 says "Existing notes without the current selection version are
      refreshed by the existing report-flow writer."
    suggested_fix: |
      Add `selection_version: broker_digest_v3` to `_render_note` frontmatter and update
      `_has_current_diagnostics_note_shape` / `_is_legacy_broker_digest_note` to require
      it. Add a test that a note missing `selection_version` is refreshed while a note
      with `broker_digest_v3` is skipped.

  - id: B2
    issue: Runtime line budget is at high risk of exceeding the 100-line stop condition
    evidence: |
      Implementing complete-unit splitting, boundary extension, six score parts,
      OCR-damage rejection, family-specific claim/evidence validators, and
      `selection_version` plumbing touches both allowed runtime files. The current
      producer (`broker_research_digest.py`) is ~1,260 lines; the legacy helpers
      `_condense_excerpt`, `_quality_score`, `_section_candidate_score`, and
      `_diagnostic_entry` must be replaced rather than augmented to stay near the
      60-line preference and within the 100-line stop condition in Design §12.
    suggested_fix: |
      Revise the design to explicitly list the legacy functions to be replaced and the
      exact net-line target. Confirm the scope is achievable before coding; otherwise
      split the batch.

must_fix:
  - id: M1
    issue: Unit truncation at 900 chars violates the complete-unit invariant
    evidence: |
      `broker_research_digest.py:737` returns `text[:900].strip()` and `:762` returns
      `" ".join(selected)[:900].strip()`. Both can end mid-sentence or mid-number.
      Design §6.1 says "Never cut with text[:N] when a preceding sentence boundary is
      available" and allows bounded extension to the next nearby sentence boundary.
    suggested_fix: |
      Replace final slicing with boundary-aware extension: when the 900-char window ends
      before a terminator (`。`, `；`, `！`, `？`), extend to the next nearby boundary or
      retreat to the previous one; never return a dangling unit.

  - id: M2
    issue: Diagnostics do not expose score parts
    evidence: |
      `_diagnostic_entry` (`broker_research_digest.py:694-700`) stores only
      `heading`, `score`, `status`, `reason`. Tests assert only the total score.
      Design §5 and §7 require persisting `signal`, `evidence`, `completeness`,
      `coherence`, `ocr_penalty`, `noise_penalty`.
    suggested_fix: |
      Extend `_diagnostic_entry` with a compact `score_parts` dict, populate it in
      `_section_selection_diagnostics`, and render it in the note writer's
      `## Selection Diagnostics` section. Update tests to assert each part is present.

  - id: M3
    issue: Claim/evidence pairing is not enforced per card family
    evidence: |
      `_is_valid_excerpt`, `_is_valid_product_driver_excerpt`,
      `_is_valid_forecast_excerpt`, and `_is_valid_risk_excerpt`
      (`broker_research_digest.py:836-900`) check length, digit count, and term
      presence, but do not verify that the excerpt contains both a claim and
      supporting evidence as required by Design §6.2.
    suggested_fix: |
      Add family-specific claim/evidence checks: core view needs directional
      conclusion + business/financial reason; product driver needs product/demand
      claim + evidence or second driver cluster; forecast needs forecast/rating +
      period/metric/assumption/valuation evidence; risk needs named risk +
      transmission mechanism or affected metric.

  - id: M4
    issue: Severe OCR/numeric damage is not rejected
    evidence: |
      `_section_candidate_score` (`broker_research_digest.py:641-643`) applies
      penalties for Chinese char gaps and dangling decimals but continues to select
      high-keyword candidates. Design §7 says "A candidate with severe OCR or numeric
      damage is rejected even if its total keyword score is high."
    suggested_fix: |
      Add an `ocr_penalty` threshold or explicit damage detector (Chinese char gaps,
      broken year/unit sequences, isolated conjunctions, incomplete numeric
      comparisons) that marks the candidate `status: rejected` regardless of keyword
      score.

  - id: M5
    issue: Complementarity is across headings, not semantic roles within a section
    evidence: |
      `_select_section_candidates` (`broker_research_digest.py:646-666`) selects up to
      two heading candidates for `broker_product_driver` by near-duplicate fingerprint,
      not different semantic roles within one section. Design §6.3 wants coverage of
      different semantic roles in original order.
    suggested_fix: |
      Split a section into complete units, label each unit's semantic role, and select
      non-adjacent units that cover distinct roles while preserving original order.

  - id: M6
    issue: No-heading fallback does not guarantee a coherent single unit
    evidence: |
      `_fallback_excerpt` (`broker_research_digest.py:810-819`) joins any valid chunks
      up to 280 chars without terminal-punctuation or claim/evidence checks. Design
      §6.2 allows single-unit cards only when the unit already contains both claim and
      evidence.
    suggested_fix: |
      Apply the same complete-unit and claim/evidence rules to fallback excerpts; reject
      the fallback if it cannot form a coherent single unit.

  - id: M7
    issue: Note writer still uses excerpt_cleaner_version as the freshness key
    evidence: |
      `broker_research_digest_note_writer.py:141` writes
      `excerpt_cleaner_version: broker_ocr_v2` and does not write `selection_version`.
      The stale-refresh test
      `test_broker_digest_writer_refreshes_current_note_missing_cleaner_version` keys
      on cleaner version, not selection version.
    suggested_fix: |
      Add `selection_version: broker_digest_v3` to `_render_note` and update the
      current-shape / legacy checks to require it, as covered in B1.

nice_to_have:
  - id: N1
    issue: Keep excerpt_cleaner_version for backward compatibility during transition
    suggested_fix: |
      Write both `excerpt_cleaner_version: broker_ocr_v2` and
      `selection_version: broker_digest_v3` until all legacy notes are archived, then
      remove the older field in a later cleanup.

  - id: N2
    issue: Add focused tests for long-report boundary extension and multiple heading occurrences with score parts
    suggested_fix: |
      Add tests for (a) an excerpt whose 900-char limit lands mid-sentence and (b) two
      occurrences of the same heading that produce different `score_parts`.

  - id: N3
    issue: Formal report acceptance test depends on a newly generated 中际旭创 report
    suggested_fix: |
      Clarify how the reviewer validates report mtime > producer commit in CI. Consider
      adding a deterministic synthetic acceptance test so the gate does not require
      manual report generation.

requirement_test_gaps:
  - requirement: selection_version written to cards and notes
    missing_test: assert `selection_version: broker_digest_v3` in rendered note frontmatter and in the returned card dict
  - requirement: stale notes without selection_version are refreshed
    missing_test: write a note without `selection_version`, run the writer, assert the file is rewritten
  - requirement: score parts persisted in Selection Diagnostics
    missing_test: assert each diagnostic entry contains `score_parts` with signal/evidence/completeness/coherence/ocr_penalty/noise_penalty
  - requirement: complete units ending in terminal punctuation
    missing_test: assert the final character of `source_excerpt` is `。`, `；`, `！`, or `？` (or a documented complete-bullet exception)
  - requirement: bounded extension to next sentence boundary
    missing_test: feed text where the 900-char window ends mid-sentence; assert the excerpt extends to the next boundary or retreats
  - requirement: claim/evidence pairing per family
    missing_test: one test per family with an excerpt that has claim but no evidence and is rejected
  - requirement: severe OCR damage rejected
    missing_test: damaged candidate outranks clean candidate only after damage rejection, not merely after penalty
  - requirement: complementary unit selection within a section
    missing_test: section with multiple semantic roles produces a card containing units covering distinct roles in original order
  - requirement: no-heading fallback produces coherent single unit
    missing_test: fallback text without claim+evidence is rejected
  - requirement: card_id and source_excerpt_hash derive from final selected excerpt
    missing_test: explicit test that changing the selected units changes `source_excerpt_hash` and `card_id`

recommended_next_step:
Revise the design to (1) replace the legacy `_condense_excerpt`, `_quality_score`,
`_section_candidate_score`, and `_diagnostic_entry` implementations rather than
adding beside them, (2) make the note writer's `selection_version` check explicit,
and (3) add the missing tests before any runtime changes. Then re-review the
revised design against the 100-line runtime budget and the source-boundary
invariants.
