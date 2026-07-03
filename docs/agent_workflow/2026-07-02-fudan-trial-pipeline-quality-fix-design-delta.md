# Fudan Trial Pipeline Quality Fix — Design Delta After Round 1

## Source

- Design: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
- Round 1 review: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-notes.md`

## Verdict

Round 1 feedback accepted. The design remains `needs_r2_review` before implementation because the review contained blockers.

## Accepted Changes

1. **Config completion is now an explicit pre-batch.**
   - Added Batch 1.5 before any Direct-Only filtering.
   - Requires `industry/competitors/product_exposure_terms` for 复旦微电、中际旭创、圣邦股份.
   - Defines keyword fallback only after stripping generic terms.

2. **4.3 root cause moved from quality gate to renderer.**
   - `DeepAnalysisRenderer` fallback is now the primary fix.
   - Quality gate remains a second-line check only.
   - Added four fallback modes for 4.3: both funding/events, funding-only, events-only, neither.

3. **Header source corrected.**
   - Header uses `stock_config` first.
   - Falls back to `INDUSTRY_MAP/COMPETITOR_MAP`.
   - Only displays `—` when both layers are missing.

4. **Direct-Only fallback clarified.**
   - `product_exposure_terms` is preferred.
   - Missing terms can fallback to de-genericized `stock_config.keywords`.
   - Filtering underflow is a warning/controlled degradation, not a silent skip.

5. **Financial unit root cause moved upstream.**
   - Batch C must inspect table/cell parser unit extraction.
   - `_filing_fact()` formatting alone is not sufficient.
   - Fact pack must carry normalized amount/unit and raw source hints.

6. **Financial missing-data gate is metric-specific.**
   - Revenue/profit contradictions can fail when facts exist.
   - Orders/customers/expense ratio/guidance can remain missing if no fact exists.

7. **Renderer tests added to plan.**
   - `test_deep_analysis_renderer.py` now covers fallback behavior.
   - `test_assembly_skills.py` covers header config and fallback.

## Rejected Changes

None.

## Deferred

- Multi-hop industry chain inference remains deferred. It requires a separate deterministic chain validator and manifest-match quality gate.
- In this batch, multi-hop materials may only remain in source intake or 4.4 display-only as tentative observations.

## Revised Batch Order

1. Batch 1.5: config completion.
2. Batch D: header config-first + renderer fallback.
3. Batch A: quality gates.
4. Batch B: Direct-Only relevance filtering.
5. Batch C: financial fact pack + unit normalization.
6. Batch E: smoke and regression.

## R2 Required

Yes. Round 2 should only review whether B1-B3 and MF1-MF5 are now fully closed and whether the revised batch order is implementable.
