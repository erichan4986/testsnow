# Annual Coverage Repair - Claude Round 2 Review Notes

## Verdict

ok

## Round 1 Closure Matrix

| Finding | closed | evidence | remaining concern |
| --- | --- | --- | --- |
| MF-01: schema must own usage-to-family mapping and producer must delete `_USAGE_FALLBACKS` | yes | Design §5.1 makes `annual_argument_schema.py` the sole owner of `canonical_family_for_usage()`, `is_high_value_narrative_usage()`, and `has_concrete_annual_anchor()`. It lists the exact high-value narrative usages, requires the schema table to reproduce every current producer `_USAGE_FALLBACKS` pair, and explicitly states the producer imports the helpers and deletes `_USAGE_FALLBACKS`. | The compatibility test that locks the complete mapping must be written *before* the producer table is removed, or a mapping drift could silently change admission behavior. |
| MF-02: A-share marker-tail extraction must be exact and one-SourceUnit-only | yes | Design §5.4 defines `extract_a_share_causal_tail(unit, usage)` with strict boundaries: runs only for `document_style == "a_share_annual"`, inspects one materialized SourceUnit, requires exactly one contiguous checkbox-marker run, keeps only the direct suffix after the final marker, ends at the existing sentence terminator, restricts to operating/technology/financial usages, requires a concrete family anchor, and forces the suffix through existing noise guards. | Ensure `has_concrete_annual_anchor()` is calibrated so the anchor check does not become a weaker gate than the existing `_has_atomic_anchor()` path. |
| MF-03: HK implicit-subject admission must be style-gated and predicate-anchored | yes | Design §5.5 passes envelope `document_style` to producer admission and limits implicit-subject relaxation to `hkex_annual` + the three HK narrative usages (`hk_business_overview`, `hk_customer_ecosystem`, `hk_product_progress`). A named platform/product/solution/ecosystem anchor and an action/capability/customer/market predicate are both required in the same SourceUnit; standalone labels fail. | None significant; current `_looks_like_hk_report()` markers are already narrow, but a regression test for `unknown` style inputs remains important. |
| MF-04: v1/v2 coverage proof must share normalization and require exact SourceUnit fragments | yes | Design §5.6 adds shared `normalize_annual_source_text(text)` (`re.sub(r"\\s+", " ", text).strip()`), splits legacy excerpts into sentence/semicolon fragments, filters out headings/checkbox/boilerplate/short spans, requires `has_concrete_annual_anchor()` per fragment, and demands each meaningful fragment be an exact normalized substring of one v2 SourceUnit or an ordered contiguous SourceUnit sequence from the same `source_block_id`. `needs_recovery` keeps the v1 adapter active and emits diagnostics. | The material pack currently uses a different, lossier `_normalize_text()`; the switch to the shared helper must be total so that punctuation differences do not create false recovery obligations. |

## Remaining Blockers

No remaining blockers. The revised design does not require a separate HK producer, a second card selector, stock/industry-specific allowlists, fuzzy v1 matching, an unbounded evidence pack, or any prohibited business-path change.

## Remaining Must-fix

No remaining must-fix items. All four Round 1 findings are closed by precise design text rather than restatement.

## Scope and Budget Audit

- prohibited-path risk: |
    Low. The design explicitly keeps scoring, target price, risk, technical analysis, executive summary, recommendation, LLM prompts, collection, network access, browser/CDP, renderer wording, and legacy note archival out of scope. Changes are confined to evidence-pack allocation/style metadata, schema-owned usage metadata, producer source-boundary admission, and material-pack migration diagnostics.

- source-substring/provenance risk: |
    Low. Every new path preserves direct source substrings: the A-share extractor returns a suffix of the same SourceUnit with recalculated block-relative offsets; the HK rule retains Traditional Chinese text and offsets exactly; the coverage proof uses exact normalized SourceUnit substrings. No paraphrasing or cross-unit concatenation is introduced.

- second-selector/taxonomy risk: |
    Low. The family reservation is explicitly an allocator, not a selector: blocks are selected once, and `resolve_argument_family(...)` remains the sole v2 card-family resolver. The only taxonomy risk is implementation-level drift if the producer's `_USAGE_FALLBACKS` is deleted before the schema compatibility test locks the full mapping; the design mandates the test first.

- runtime-budget assessment: |
    The +80 target / +100 hard stop is plausible but tight. The design correctly instructs implementers to replace the existing `blocks[:30]` slice and exact-only shadow logic rather than layering a parallel allocator or migration system. Even so, four files are touched (`annual_argument_schema.py`, `periodic_report_evidence_pack.py`, `periodic_report_narrative_evidence_cards.py`, `annual_report_material_pack.py`) and new helpers/tests are added. If the net delta exceeds +100 lines, the design's own stop condition must be honored and the plan revisited.

## Recommendation

- design ready for implementation planning: yes
- next step: |
    Proceed to implementation planning with the following guardrails:
    1. Write the schema compatibility test that locks the full `_USAGE_FALLBACKS` mapping before deleting the producer's local table.
    2. Implement `normalize_annual_source_text()` in `annual_argument_schema.py` and use it everywhere—producer SourceUnit materialization, A-share extractor, and material-pack coverage comparison.
    3. Add the synthetic allocator test (business overview ranked below old 30 cap but surviving under 48 cap) and the HK/A-share regression fixtures from the design's test matrix.
    4. Measure net line delta after replacing old cap/shadow code; return to design if it exceeds +100 lines.
    5. After implementation, run the eight-stock local-cache refresh acceptance to confirm `v1_needs_recovery_count == 0` for all configured stocks before Batch B adapter removal is reconsidered.
