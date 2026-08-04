# Chapter 4 Annual Display Selection: Codex Implementation Review

Date: 2026-07-13
Verdict: `needs_revision`

## Summary

The implementation keeps the annual producer and memo layers intact, shares one annual selector across formal-medium and formal-thin, and preserves the formal-thin full-snapshot citation offsets. Fresh focused, downstream, CI, and whitespace checks pass.

It is not ready to proceed because the locked runtime hard stop was exceeded and three behavioral contracts remain unmet.

## Findings

### B1 - Runtime hard stop exceeded

The task sets a runtime hard stop at net `+120` lines across the two allowed runtime files. Current numstat against `HEAD` is:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 176 | 12 | +164 |
| `deep_analysis_renderer.py` | 64 | 62 | +2 |
| **Total** | **240** | **74** | **+166** |

The implementation exceeds the hard stop by 46 net lines. Functional tests passing does not override this stop condition.

### M1 - `formal_fact` bypasses all display-noise and role checks

`_annual_segment_rejection_reason()` returns immediately for every `formal_fact`. Audit boilerplate, disclosure/governance text, document noise, routine process text, catalogs, generic industry context, and role mismatch are therefore never evaluated for confirmed rows.

Fresh reproduction: a `formal_fact` row containing the full audit-opinion shape was selected with an empty rejection map.

Required fix: confirmed financial facts must remain visible, but `formal_fact` cannot be a blanket bypass. Apply structural noise checks first, then admit a confirmed row only when it is a concrete financial or role-compatible fact.

### M2 - Formal-medium 4.4 omits the required selected-row fallback

The locked task requires 4.4 annual selection to search `argument_complete=True` rows first, then all selected rows in the same role order. The implementation only searches complete rows with `fallback=False`.

Fresh reproduction: an incomplete but selected `business_structure` row appears in 4.1 and no annual row appears in 4.4.

Required fix: perform a second role-priority search over all selected annual rows. This is not an arbitrary `row_list[0]` fallback.

### M3 - Routine `经营模式` noise regressed

The removed renderer cleaner handled `经营模式`, `直接销售模式`, and `代理销售`. The new selector's routine markers omit `经营模式` and `代理销售`, and the new test explicitly expects a generic direct/dealer operating-mode suffix to remain visible.

Fresh reproduction: `公司提供工业控制设备并服务大型制造客户，经营模式包括直销和经销。` survives unchanged.

Required fix: keep the valuable business segment while rejecting a separable routine operating/sales-mode segment. Update the regression test to assert the useful business statement survives without the routine suffix.

### W1 - Source-text preservation contract is under-tested

The selector normalizes whitespace and performs phrase-level regex rewrites before projection. The task says retained source segments must preserve source text and order verbatim, with only rejected segments removed. Existing tests prove this for one mixed product/standard example but do not cover heading/disclosure cleanup paths.

Before approval, add an assertion that every retained segment is an ordered substring of the original normalized source, or narrow the contract explicitly if display-only prefix cleanup is intended.

## Closed / Verified

- One public annual selector is used by formal-medium and formal-thin.
- Formal-thin builds the full snapshot before selection.
- Snapshot citation refs are not renumbered after selection.
- Highest rejected annual ref does not shift broker/external refs in the focused regression.
- No annual row cap or fuzzy/embedding/LLM dedupe was added.
- Renderer no longer owns the main annual admission rules.
- No producer, memo schema, synthesis prompt, profile, scoring, target, risk, technical, recommendation, data, knowledge, or report file was changed by this implementation batch.

## Fresh Verification

- Focused snapshot + renderer tests: `109 passed`
- Downstream report quality + source boundary tests: `97 passed`
- `bash tools/ci_grep_gates.sh`: passed
- `git diff --check`: clean
- Formal reports: not generated, as required by the implementation task

## Required Next Step

Return to a compact revision of the same two runtime files. The revision must:

1. reduce runtime net delta to `<= +120` before continuing;
2. remove the `formal_fact` blanket bypass;
3. restore 4.4's selected-row role-priority fallback;
4. restore routine operating/sales-mode projection without reintroducing renderer admission logic;
5. rerun the focused/downstream/CI/diff checks.

Do not generate formal reports until this review is closed.
