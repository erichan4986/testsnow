# Recommendation Risk Consistency Design Review Round 1

Reviewer: Claude Code (read-only design review)
Date: 2026-07-01
Design under review: `docs/agent_workflow/2026-06-30-recommendation-risk-consistency-design.md`

## Verdict

- overall: **needs_revision**

The direction (central `RecommendationDecision` as single source of truth) is
sound and correctly targets the observed defects. All five reported symptoms
were reproduced from the current code + reports (see evidence below). But the
design contains two internal contradictions that would let the inconsistency
re-appear in a *different* place if implemented literally. Fix those two, then
proceed.

Reproduced evidence (current tree):

| Symptom | Evidence |
| --- | --- |
| summary vs section 1 label mismatch | `中际旭创_20260630.md:12` `EV: +49.83%（N/A）` vs `:35` `EV: +49.83%（强烈看多）`; `圣邦股份_20260630.md:12` `（N/A）` vs `:35` `（看多但等待入场）` |
| `N/A%` formatting | `黑芝麻智能_20260630.md:12` and `:35` `EV: N/A%（N/A）` |
| blocked entry + strong positive | `中际旭创_20260630.md:206` `关注/不操作（MACD死叉扩张…）` while `:35`/`:45` show bare `强烈看多` |
| 4.4 risk vs low formal risk | `中际旭创_20260630.md:431` `风险等级: 0.0/10（低风险）` with no display-only explanation |
| separate decision paths | root cause below |

Root cause located: `executive_summary_renderer.py:276` reads
`ev.get("signal")`, a key `ev_expectation(...)` never returns (it returns
`recommendation_cn`, see `scoring_engine.py:287`), so the summary label is
**always** `N/A`; `executive_summary_renderer.py:277-278` appends `%`
unconditionally, so a `None` EV renders `N/A%`. The design's problem statement is
accurate.

## Blockers

- **B1. Entry constraint is generalized for the label but NOT for risk position
  advice — this creates a new mismatch the design's own gate 5 would fail.**
  - Evidence: design step 6 says build `RiskAssessment` "with the same
    risk-factor math currently used by `risk_score_section(...)`". That math
    (`scoring_engine.py:750-766`) derives position advice from
    `_technical_position_guardrail` (severity: score<30 / stage) **plus** the
    narrow `_entry_quality_guardrail` (`scoring_engine.py:525-554`), which only
    fires on `error=="关注/不操作" and "盈亏比不足" in reason`. Meanwhile design
    step 4 generalizes `EntryConstraint` to *any* `关注/不操作` reason.
  - Why it breaks: for 中际旭创 (reason `MACD死叉扩张`, not `盈亏比不足`) the new
    `EntryConstraint` becomes `wait_for_entry` and the label downgrades to
    `看多但等待入场`, but the risk section — still on the narrow guardrail —
    keeps `积极配置，最大仓位 20%` (`中际旭创_20260630.md:433`). Section 1 now
    says "wait for entry" while the risk section says "aggressive 20%". That is
    exactly `risk_position_label_mismatch` (design gate 5), self-inflicted.
  - Suggested fix: make `EntryConstraint` the single input to BOTH the label
    constraint and the risk-section position cap. Either (a) route
    `build_risk_assessment(...)` position advice through the same
    `EntryConstraint` object, or (b) widen `_entry_quality_guardrail` to accept
    any `关注/不操作` reason and have both consumers call it. Do not leave two
    guardrail predicates with different trigger conditions.

- **B2. `has_display_only_external_risk` is an input flag with no defined,
  deterministic, isolation-safe producer.**
  - Evidence: builder signature takes `has_display_only_external_risk: bool =
    False` (design line ~147) and step 7 adds a note when true, but nothing in
    the design says *who computes it* or *from what*. The only source of 4.4
    risk terms is the display-only Preview body.
  - Why it breaks: if the producer re-scans rendered 4.4 Markdown for risk
    keywords, that re-couples formal decision logic to display-only content and
    risks violating the 4.4 display-only boundary that the source-policy work
    just established. If it silently defaults to `False`, gate 4
    (`display_only_risk_without_explanation`) never has anything to assert and
    the feature is dead.
  - Suggested fix: define the producer as reading a *structured* upstream flag
    (e.g. a boolean already attached to curated-external metadata in `ctx`),
    computed at intake/synthesis time, never by scraping the 4.4 Markdown. State
    explicitly that this flag is derived from metadata, not from rendered text,
    so display-only isolation is preserved.

## Must-Fix

- **M1. Summary must render the *constrained* label, and a test must assert the
  downgraded form matches — not just that both sides equal `N/A`.**
  - Evidence: today `ExecutiveSummaryRenderer` computes no entry constraint at
    all and always emits `N/A`. Design failure-mode table row 1 only tests "both
    render from one `RecommendationDecision`" and the `N/A` case.
  - Why it breaks: a test that only checks the `N/A`/`N/A` case would pass even
    if the summary printed the *raw* `强烈看多` while section 1 printed
    `看多但等待入场`. The regression that matters (圣邦: summary must show
    `看多但等待入场`, not `看多`) is not pinned.
  - Suggested fix: add a fragment test asserting summary label == section 1
    label == `RecommendationDecision.display_recommendation` for the
    entry-blocked positive case.

- **M2. Preserve `ev_expectation(...)` return keys; the summary bug is a wrong
  key, not a missing formatter.**
  - Evidence: `executive_summary_renderer.py:276` `ev.get("signal")`.
  - Why it breaks: if the decision object exposes a field named differently from
    what renderers read, the same class of bug recurs. Any migration must delete
    the `ev.get("signal")` read, not shadow it.
  - Suggested fix: in Phase 2, remove the local `ev_expectation` call and
    `signal` read from the summary renderer entirely; read only
    `ctx["recommendation_decision"]`. Add a grep-style guard test that
    `signal` is no longer referenced.

- **M3. `composite_score_section(...)` currently owns total_score, EV table,
  targets, reasons, and label in one function. The decision must not duplicate
  `total_score`/EV math and let the two drift.**
  - Evidence: `scoring_engine.py:324-331` computes `total_score`;
    `executive_summary_renderer.py:267-274` computes the *same* formula
    independently. Two copies already exist.
  - Why it breaks: introducing a third computation site (the builder) without
    removing the two existing ones means three formulas to keep in sync.
  - Suggested fix: the builder computes `total_score` once; both renderers read
    it from the decision. Delete the duplicated formula in the summary renderer
    in Phase 2. Keep `composite_score_section` as a wrapper that *accepts* the
    decision rather than recomputing (design already allows this as option a).

- **M4. Compatibility of `risk_score_section(...)` string output is
  test-locked; the Phase 3 split must reproduce byte-level markers.**
  - Evidence: `tests/reporter/test_scoring_engine_risk.py` asserts exact
    strings: `风险等级: X/10`, `> **仓位建议**: …`, `> **仓位约束**: …`,
    `> **入场约束**: …`, `结构化风险观察（不计分）`, `LLM文本风险观察（不计分）`.
    ~40 assertions depend on these.
  - Why it breaks: extracting `build_risk_assessment(...)` and re-rendering can
    easily change spacing/wording and break all of them.
  - Suggested fix: keep `render_risk_assessment(...)` emitting identical
    literals, and keep `risk_score_section(...)` as a thin wrapper
    (`render_risk_assessment(build_risk_assessment(...))`). Run
    `test_scoring_engine_risk.py` unchanged as the gate.

## Nice-To-Have

- **N1. HTML dashboard deferral.** Benefit: smaller first patch. Deferrable
  because the release gate is Markdown (design Q1 default). Note explicitly in
  the design that HTML may still show the old label until the follow-up, and add
  a TODO/known-drift line so it is not mistaken for done.
- **N2. `consistency_notes` surfacing.** The decision carries
  `consistency_notes: list[str]`, but no renderer is assigned to display them.
  Benefit: debuggability. Deferrable: not required for correctness. Either wire
  it to one section or drop the field to avoid dead structure.
- **N3. `raw_code` enum reuse.** `EvDecision.raw_code` duplicates the
  `STRONG_BUY/BUY/...` codes already produced at `scoring_engine.py:268-282`.
  Benefit: single enum. Deferrable: cosmetic.

## Architecture Assessment

- **central `RecommendationDecision` — reasonable?** Yes. It is the correct
  boundary: pure, deterministic, no I/O (design is explicit), and it sits
  exactly where the duplication is (summary + section 1 + risk position). The
  five sub-shapes (`EvDecision`, `EntryConstraint`, `RiskAssessment`,
  `RecommendationDecision`) map cleanly onto the real decision surface.
- **Should `RiskAssessment` be extracted this round?** Yes — it must be, not
  optionally. B1 shows label consistency and risk position advice share the same
  `EntryConstraint`; you cannot fix the label mismatch correctly while leaving
  risk position advice on a divergent guardrail. Extracting `RiskAssessment` is
  the mechanism that keeps gate 5 satisfiable. Do it in the same arc, but land
  it behind the compatibility wrapper (M4) so tests stay green.
- **`decision_skill` vs `ReportAssemblySkill` build location.** Prefer building
  in `ReportAssemblySkill._assemble_markdown(...)` **first** (the design's
  interim option), then promote to `decision_skill` once green. Rationale: the
  builder needs `pillar`, `consensus`, `stock_raw`, `quote`, and 4.4 metadata —
  all already assembled in `ctx` by assembly time. Adding a pipeline stage first
  increases churn and ordering risk (charts/claim-risk must run before it).
  Assembly-level keeps the blast radius to one function and one `ctx` key.
- **Smaller correct landing order:** Phase 1 (decision + unit tests) → build in
  assembly, wire summary + section 1 only (Phase 2) → prove summary/section 1
  match on all three fixtures → then Phase 3 risk split + gate 5. This delivers
  the two most visible bugs (`N/A%`, label mismatch) before touching risk math.

## Test Matrix Review

Design's failure-mode table is a good start but under-specifies three cases.

Sufficient as designed:
- `EV: N/A` → `ev_display == "N/A"`, no `%` (covers 黑芝麻智能).
- `关注/不操作` with arbitrary reason → wait state (directly closes the
  `MACD死叉扩张` gap; good).
- compatibility wrapper preserves `risk_score_section(...)` public callers.

Must add:
- **T1 (for M1):** entry-blocked positive → summary label == section 1 label ==
  `看多但等待入场` (assert the *downgraded* string, not just equality on `N/A`).
- **T2 (for B1):** `MACD死叉扩张` `关注/不操作` case → risk-section position
  advice is capped AND section 1 label downgraded from the **same**
  `EntryConstraint` (guards against the self-inflicted gate-5 mismatch).
- **T3 (for B2):** display-only risk note is driven by a structured metadata
  flag; assert that a report whose 4.4 body contains risk words but whose
  metadata flag is `False` does **not** fabricate a note (isolation preserved),
  and vice-versa.
- **T4 (for M2):** grep guard — `ev.get("signal")` no longer referenced in
  `executive_summary_renderer.py`.

Can be deferred:
- HTML dashboard drift test (N1) — deferred with documented known-drift.
- `consistency_notes` rendering test (N2).

Existing tests that MUST stay green unchanged: all of
`tests/reporter/test_scoring_engine_risk.py` and
`tests/reporter/test_report_quality.py`
(`contradiction_blocked_entry_strong_recommendation`,
`contradiction_weak_trend_high_*`). These are the compatibility contract.

## Stop Conditions

Stop and return to design review if implementation requires any of:
- Changing EV formula weights (`scoring_engine.py:265`), pillar weights
  (`:324-331`), or risk-factor additive weights (`:597-733`).
- Widening `_entry_quality_guardrail` in a way that changes an existing passing
  assertion in `test_scoring_engine_risk.py` (e.g. flipping a case that
  currently returns `None`). If widening the guardrail breaks an existing test,
  stop — the generalization is changing scored behavior, not just labels.
- Needing to read rendered 4.4 Markdown to compute
  `has_display_only_external_risk` (B2) — that means the metadata producer is
  missing; stop rather than scrape display-only text.
- Any change that makes 4.4 external viewpoints alter `total_risk`, EV, or
  `total_score` (design non-goal + source-policy boundary).
- Removing or changing the signature of `ev_expectation`,
  `composite_score_section`, or `risk_score_section`.

## Final Recommendation

- **Proceed to implementation after B1 and B2 are resolved in the design.** The
  architecture is right and the bugs are real and reproduced; the blockers are
  internal contradictions, not dead-ends. They are cheap to fix on paper (unify
  the entry constraint across label + risk; define a metadata-based producer for
  the 4.4 flag).
- Suggested phase order (adjusted from the design):
  1. `recommendation_decision.py` + unit tests (EV display, entry
     classification incl. non-`盈亏比不足` reasons, label downgrade, no-consensus).
  2. Build the decision in `ReportAssemblySkill` (interim), wire
     `ExecutiveSummaryRenderer` + `CompositeScoreRenderer`; delete the summary's
     local `ev_expectation`/`signal` read; add T1/T4. Prove all three reports'
     summary == section 1.
  3. Extract `build_risk_assessment(...)` / `render_risk_assessment(...)` behind
     the `risk_score_section(...)` wrapper; route position advice through the
     shared `EntryConstraint`; add T2/T3; keep existing risk tests unchanged.
  4. Add deterministic quality gates (`ev_na_percent`,
     `summary_score_label_mismatch`, `blocked_entry_strong_recommendation`,
     `display_only_risk_without_explanation`, `risk_position_label_mismatch`).
  5. Promote to `decision_skill` only if assembly-level shows churn; real-report
     validation on 中际旭创 / 黑芝麻智能 / 圣邦股份 last.
