# Annual Coverage Repair - Claude Round 1 Review Notes

## Verdict

needs_revision

## Blockers

No blockers. The design stays within one v2 producer, one selector, one schema,
no stock/industry allowlists, no separate HK producer, and a bounded 48-block
evidence pack. It does not reach scoring, target price, risk, technical analysis,
executive summary, recommendation, LLM prompts, collection, or renderer wording.

## Must-fix

- id: MF-01
  issue: |
    The producer and the evidence pack must share a single usage-to-family table.
    Right now `periodic_report_narrative_evidence_cards.py` keeps its own
    `_USAGE_FALLBACKS` dict while the design proposes new helpers
    `canonical_family_for_usage()` and `is_high_value_narrative_usage()` in
    `annual_argument_schema.py`. Unless the producer imports these helpers and
    deletes its local fallback table, the two layers can drift into two
    taxonomies and the allocator can reserve blocks for families the producer no
    longer maps the same way.
  design evidence: |
    Section 5.1 says `annual_argument_schema.py` becomes the owner of the shared
    usage metadata and that `resolve_argument_family(...)` remains the sole
    v2 card-family resolver. Invariant #3 says the family reservation is only an
    allocator.
  code evidence: |
    `periodic_report_narrative_evidence_cards.py:28-58` defines `_USAGE_FALLBACKS`
    with the same usages the design wants to own centrally.
    `annual_argument_schema.py` currently exposes no public
    `canonical_family_for_usage()` or `is_high_value_narrative_usage()`.
  required change: |
    Add the two helpers to `annual_argument_schema.py`, export them, and make the
    producer use them. Remove or inline `_USAGE_FALLBACKS` from the producer so
    there is exactly one owner.

- id: MF-02
  issue: |
    The A-share causal-tail rule is under-specified. Without a precise
    line/span boundary and a strict "what is not promoted" guard, the repair
    could accidentally admit checkbox/table-only answers or generic boilerplate
    that the current noise tests are designed to reject.
  design evidence: |
    Section 5.4 says a child narrative block may be emitted only when the span is
    a direct contiguous substring, contains a concrete anchor, is not a table
    header/checkbox-only answer, and the parent usage is narrative-compatible.
  code evidence: |
    `periodic_report_narrative_evidence_cards.py:517-525`
    (`_looks_like_checkbox_or_page_marker`) currently rejects the whole unit;
    there is no positive path that extracts a causal tail after a marker.
  required change: |
    Specify and implement a deterministic extractor (e.g.
    `extract_a_share_causal_tail(block) -> Optional[block]`) that returns a child
    block only when the four Section 5.4 conditions are met. The child must keep
    the original usage and adjusted source offsets, and must not concatenate
    fragments from multiple alternating marker lines.

- id: MF-03
  issue: |
    HK implicit-subject admission must be style-gated inside the producer, not a
    generic relaxation of self-containment. The design requires both a named
    platform/product/solution/ecosystem and an action/capability/customer
    predicate in the same source unit, and limits it to HK narrative usages.
  design evidence: |
    Section 5.5 and invariant #8. The rule is only for `hkex_annual` and must not
    use stock, industry, issuer, or product-name allowlists.
  code evidence: |
    `periodic_report_evidence_pack.py:840-841` detects HK style, but the envelope
    field `document_style` does not exist yet and the producer never receives it.
    `periodic_report_narrative_evidence_cards.py:751-759` requires explicit
    company context for `business_structure`, which is why the Black Sesame
    platform paragraph is currently rejected.
  required change: |
    Add `document_style` to the evidence-pack envelope and pass it to the
    producer. In the producer, allow implicit-subject admission only when
    `document_style == "hkex_annual"`, the usage is an HK narrative usage, and the
    unit contains a named anchor plus a predicate from the allowed set.

- id: MF-04
  issue: |
    The material-pack coverage proof must use the same normalization as v2
    SourceUnits and must consider only meaningful legacy fragments. A naive
    substring match could mark a v1 note as covered when only a short sub-phrase
    appears in v2 while the full sentence is actually lost.
  design evidence: |
    Section 5.6 defines `covered_by_v2_units` as "every meaningful legacy fragment
    is an exact normalized substring of one v2 SourceUnit or an ordered contiguous
    v2 SourceUnit sequence from that block." It explicitly excludes checkbox-only
    noise, headings, empty fragments, and generic boilerplate.
  code evidence: |
    `annual_report_material_pack.py:584-593` only performs exact-shadow matching
    by `card_id` or `source:{block_id}:{normalized_excerpt}`. There is no
    SourceUnit-sequence coverage branch and no recovery-diagnostics emission.
  required change: |
    Implement `_coverage_classification(record, v2_records)` that (a) normalizes
    whitespace exactly as v2 SourceUnits do, (b) splits the legacy excerpt into
    sentence/semicolon fragments, (c) requires a concrete fact anchor per fragment,
    (d) checks each fragment against ordered v2 SourceUnits of the same block,
    and (e) returns one of `exact_shadowed`, `covered_by_v2_units`, or
    `needs_recovery`. Emit the diagnostics listed in Section 5.6.

## Nice-to-have

- id: NH-01
  suggestion: |
    Add a synthetic allocator test that constructs a report where the only
    business-structure candidate ranks below the old 30-block cap while several
    high-priority financial tables rank above it, then assert that the business
    block survives and no top financial table is dropped.
  rationale: |
    Directly gates the stated failure mode "Reservation crowds out financial
    evidence" and makes the 48-cap/family-reserve trade-off reviewable.

- id: NH-02
  suggestion: |
    Provide a concrete line-boundary spec for A-share causal-tail extraction,
    e.g. "scan backward from the first marker occurrence, split at the next
    sentence terminator before the marker, and forward from the marker to the
    next sentence terminator; keep the forward span only if it passes anchor
    tests."
  rationale: |
    Removes ambiguity during implementation and makes the negative cases
    (multiple alternating markers, table-only answers) easier to test.

- id: NH-03
  suggestion: |
    Add a style-classification regression test for `document_style=unknown`
    inputs such as a semiannual report or a non-HK annual report without A-share
    section headings.
  rationale: |
    Prevents the HK implicit-subject rule from leaking into non-HK inputs if
    style detection misfires.

- id: NH-04
  suggestion: |
    Expose `document_style` as a stable envelope-diagnostic key and add a schema
    validation test that forbids it on individual v2 cards.
  rationale: |
    Reinforces invariant #10 (style is envelope-only, not a card-schema field).

## Requirement-Test Matrix

| Requirement | Design location | Existing evidence | Missing test or acceptance gate |
| --- | --- | --- | --- |
| 48-block hard cap | Section 5.3 | `test_caps_block_length_and_count` asserts `<= 30` | New test asserting `len(blocks) <= 48` and deterministic output |
| Family reserve: one high-value narrative block per populated family | Section 5.3 | None | Synthetic fixture where business overview ranks below old cap and tables dominate |
| No synthetic placeholder for missing family | Invariant #4 | None | Report with no candidate in a family must not fabricate a block |
| Tables/structural usages excluded from family reserve | Section 5.1, 5.3 | `_TABLE_HEADER_TOKENS` / `_TABLE_STRUCTURAL_TOKENS` | Explicit assertion that `segment_table`, `rd_investment_table`, etc. never reserve a slot |
| `a_share_annual` causal tail after marker kept | Section 5.4 | `test_applicability_checkbox_marker_rejects_the_structural_fragment` (negative) | Positive fixture preserving Zhongjian-like payment-method/cash-flow cause without checkbox boilerplate |
| `a_share_annual` checkbox/table noise still rejected | Section 5.4 | Multiple checkbox-rejection tests | Regression test with new extraction path active |
| `hkex_annual` implicit-subject admission | Section 5.5 | HK narrative tests use explicit subjects | Black-Sesame-like platform paragraph admitted as `business_structure` or `technology_product_progress` |
| `hkex_annual` platform-only label rejected | Section 5.5 | `test_hk_narrative_rejects_sustainability_privacy_boilerplate` | Negative fixture: short "SESAMEX" label without predicate must not become a card |
| `covered_by_v2_units` suppresses duplicate v1 | Section 5.6 | `test_v2_note_shadows_matching_v1_note_without_adapter_use` (exact only) | Shengbang-like long product excerpt split across multiple v2 SourceUnits -> `v1_unit_covered_count` |
| `needs_recovery` surfaces omitted fragments | Section 5.6 | `test_same_block_different_excerpt_does_not_shadow_v1` | Zhongji-like omitted business paragraph -> `v1_needs_recovery_count` and recovery diagnostics |
| No v1 deletion/archival in this batch | Section 3, Invariant #7 | Existing tests only check adapter count | Acceptance gate confirming active v1 note files are untouched |
| `document_style` envelope field | Section 5.2 | None | Tests for `a_share_annual`, `hkex_annual`, `unknown` |
| `argument_complete` / 4.4 boundary unchanged | Invariant #6 | Existing v2 tests for `argument_complete` | Acceptance gate after refresh showing atomic rows still excluded from 4.4 |
| Runtime budget <= +100 net lines | Section 8 | None | Post-implementation line-count gate |

## Scope Audit

- prohibited-path changes implied by the design: |
    None. The proposed changes are confined to:
    - `periodic_report_evidence_pack.py` (allocator, style metadata, source-boundary helpers);
    - `annual_argument_schema.py` (shared usage-to-family helpers);
    - `periodic_report_narrative_evidence_cards.py` (style-aware admission only);
    - `annual_report_material_pack.py` (coverage audit diagnostics).
    Scoring, target price, risk, technical analysis, executive summary,
    recommendation, LLM prompts, collection, network access, browser/CDP, and
    renderer wording are all explicitly out of scope.

- duplicate selector/taxonomy risk: |
    Low if MF-01 is enforced. The risk is that the producer keeps
    `_USAGE_FALLBACKS` while the evidence pack uses a new schema-owned table,
    creating two taxonomies. The design itself avoids a second card selector, but
    the implementation must delete the producer's local fallback table.

- source-substring/provenance risk: |
    Moderate. Both the A-share causal-tail and HK implicit-subject changes work
    with direct source substrings, which is consistent with v2 invariants. The
    risk is that the A-share extractor could trim or join non-contiguous spans
    when multiple markers are present, or that the HK rule could admit a
    standalone label without a predicate. MF-02 and MF-03 specify guards against
    this.

- runtime budget assessment: |
    The +80 target / +100 hard stop is plausible but tight. The design must
    replace the current `blocks[:30]` slice and exact-only shadow logic rather
    than layer a parallel allocator. However, adding deterministic A-share
    source-boundary extraction, HK implicit-subject predicates, and the material-
    pack coverage audit is non-trivial. The implementation should measure net
    line delta after the old cap/shadow code is removed and return to design if
    it exceeds +100.

## Recommendation

- Round 2 required: yes
- Exact next step: |
    Address MF-01 through MF-04 in the design: add the schema-owned helpers,
    specify the A-share causal-tail boundary predicate, add the HK style gate and
    implicit-subject predicate, and define the fragment-level coverage audit.
    Update the test matrix with concrete fixtures for each missing gate, then
    proceed to implementation planning.
