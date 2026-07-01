# Recommendation / EV / Entry / Risk Consistency Design

Date: 2026-06-30

Status: revised after Claude review round 1

Chosen direction: Option C, introduce a central recommendation decision model.

## Design Delta After Round 1 Review

Accepted:

- **B1 accepted**: `EntryConstraint` must drive both the final recommendation
  label and the risk-section position advice. The implementation must not keep a
  narrow risk guardrail that only recognizes `盈亏比不足` while the label
  guardrail recognizes every `关注/不操作` reason.
- **B2 accepted**: display-only external risk notes must be driven by structured
  metadata loaded before rendering, not by scanning rendered 4.4 Markdown.
- **M1/M2/M3 accepted**: summary and section 1 must both render the constrained
  decision label; `ExecutiveSummaryRenderer` must stop reading
  `ev.get("signal")`; total score and EV math must be computed once by the
  decision builder.
- **M4 accepted**: the risk split must preserve existing public strings and keep
  `risk_score_section(...)` as a compatibility wrapper.
- **Implementation order adjusted**: build the decision first inside
  `ReportAssemblySkill` to reduce pipeline churn, then promote to a dedicated
  `decision_skill` only after Markdown gates are stable.

Rejected:

- None.

Deferred:

- HTML/dashboard integration remains out of the first implementation. Markdown
  is the release gate; HTML drift is documented follow-up work.
- `consistency_notes` display can be deferred unless it is useful during
  debugging. It must not become dead mandatory structure.

R2 required: **no**, if implementation follows this revised design and does not
change EV formula weights, risk weights, technical algorithms, or 4.4
display-only eligibility.

## Background

Recent report audits found recurring consistency problems:

- Executive summary and section 1 can show different recommendation labels.
  Example: `EV: +49.83%（N/A）` in the summary but `EV: +49.83%（强烈看多）`
  in section 1.
- Reports can show `EV: N/A%`, which is a formatting error.
- Technical entry state can say `关注/不操作`, while the composite
  recommendation still says `强烈看多`.
- 4.4 display-only external observations can contain risk variables while the
  formal risk score stays low, with insufficient explanation for readers.
- Special risk overlays, composite risk score, EV, target price, and technical
  entry state are rendered by separate modules, so each section can drift.

The current implementation has multiple independent decision paths:

- `ExecutiveSummaryRenderer` computes EV directly via `ev_expectation(...)`.
- `CompositeScoreRenderer` calls `composite_score_section(...)`, which computes
  EV, recommendation, target range, and entry guardrails again.
- `risk_score_section(...)` computes risk score and position advice separately.
- `TechnicalRenderer` and price target logic produce entry signals that are only
  partially reflected in the recommendation.
- 4.4 display-only risk observations are intentionally excluded from scoring,
  but the risk section does not always explain this separation.

This design makes the report recommendation a single structured decision, then
lets renderers display that decision instead of recomputing labels locally.

## Goals

1. Create one source of truth for:
   - total score,
   - EV value and EV display string,
   - raw EV-derived recommendation,
   - final display recommendation after entry/risk constraints,
   - technical entry state,
   - position advice,
   - formal risk score and risk level,
   - display-only external risk note.
2. Remove duplicated EV / recommendation formatting from individual renderers.
3. Prevent visible contradictions:
   - `N/A%`,
   - summary label different from section 1 label,
   - strong positive recommendation when technical entry is blocked,
   - low formal risk score next to 4.4 risk observations without explanation.
4. Preserve existing scoring formulas unless explicitly changed in a later
   design. This phase is a unification of decision semantics, not a model
   rewrite.
5. Keep 4.4 display-only isolation: external observations may adjust explanatory
   notes, but they must not change formal risk score, EV, or final advice unless
   a later design explicitly allows it.

## Non-Goals

- Do not change EV formula weights.
- Do not change technical indicator calculations.
- Do not change risk-factor score weights.
- Do not make 4.4 external viewpoints scoring-eligible.
- Do not alter source-intake collection or live API behavior.
- Do not redesign the whole report template.

## Proposed Architecture

### New Module

Add:

```text
scripts/utils/reporter/recommendation_decision.py
```

This module owns all decision construction and label formatting. It should be
pure and deterministic: no network calls, no LLM calls, no file writes.

Core data shapes:

```python
@dataclass(frozen=True)
class EvDecision:
    ev_pct: float | None
    ev_display: str              # "+49.83%" or "N/A"
    raw_label: str               # "强烈看多" / "看多" / "持有" / "谨慎" / "回避" / "N/A"
    raw_code: str                # STRONG_BUY / BUY / HOLD / AVOID / STRONG_AVOID / N_A
    targets: dict[str, float]
    details: dict[str, Any]


@dataclass(frozen=True)
class EntryConstraint:
    state: str                   # ok / wait_for_entry / overheated / weak_trend / severe_technical / unknown
    label_suffix: str            # e.g. "但等待入场"
    display_note: str
    position_cap_note: str
    source: str                  # price_target / trend_health / bias / none
    raw_reason: str


@dataclass(frozen=True)
class RiskAssessment:
    score: float | None
    level: str                   # 低风险 / 中等风险 / 高风险 / 极高风险 / N/A
    position_advice: str
    position_constraint_note: str
    entry_constraint_state: str
    factors: list[dict[str, Any]]
    formal_notes: list[str]
    display_only_notes: list[str]
    special_risk_notes: list[str]


@dataclass(frozen=True)
class DisplayOnlyExternalRiskSignal:
    present: bool
    source: str                   # structured metadata source, not rendered Markdown
    topics: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class RecommendationDecision:
    stock_name: str
    total_score: float | None
    total_score_display: str
    ev: EvDecision
    raw_recommendation: str
    display_recommendation: str
    recommendation_sentence: str
    entry_constraint: EntryConstraint
    risk: RiskAssessment
    consistency_notes: list[str]
```

### Decision Builder

Add one builder:

```python
build_recommendation_decision(
    stock_name: str,
    posts: list[dict],
    stock_raw: dict,
    quote: dict | None,
    consensus: dict | None,
    industry_fwd_pe: float | None,
    pillar: dict | None,
    structured_risk_signals: list[dict] | None = None,
    synthesis_text: str = "",
    display_only_external_risk: DisplayOnlyExternalRiskSignal | None = None,
) -> RecommendationDecision
```

The builder should:

1. Reuse existing `compute_pillar_scores(...)` and `ev_expectation(...)`.
2. Compute `total_score` once.
3. Normalize EV display:
   - if `ev_pct is None`: `ev_display = "N/A"`;
   - else: `ev_display = f"{ev_pct:+.2f}%"`.
4. Derive entry constraint from existing technical data:
   - any `technical.price_target.error == "关注/不操作"` means
     `state = wait_for_entry`, regardless of whether the reason is
     `盈亏比不足`, `MACD死叉扩张`, or another blocked-entry phrase;
   - `BIAS` extreme-high flags mean `state = overheated`;
   - severe trend-health breakdown means `state = severe_technical`;
   - moderate weak trend means `state = weak_trend`.
5. Apply label constraints:
   - raw `强烈看多` or `看多` + `wait_for_entry` -> `看多但等待入场`;
   - raw `强烈看多` or `看多` + `overheated` -> `看多但避免追高`;
   - raw positive + `severe_technical` -> `风险控制优先`;
   - non-positive labels should not be upgraded by entry logic.
6. Build formal `RiskAssessment` with the same risk-factor math currently used
   by `risk_score_section(...)`, but return structure before Markdown.
7. Route `EntryConstraint` into risk position advice:
   - `wait_for_entry` must cap or soften the risk section's position language
     even when the raw risk score is low;
   - `overheated` must prevent "积极配置" style wording;
   - `severe_technical` must prioritize risk-control wording;
   - this must be the same `EntryConstraint` object used by the final display
     recommendation, so section 1 and risk section cannot diverge.
8. Add a display-only note when structured 4.4 metadata reports risk-like
   observations:
   - "4.4 外部观察为 display-only，不计入综合风险评分；相关变量仅作为人工跟踪项。"
9. Return all render-ready display strings through `RecommendationDecision`.

### Display-Only External Risk Metadata Producer

`display_only_external_risk` must come from structured upstream metadata, not
from rendered report text.

Allowed producers:

- curated external narrative/digest JSON metadata, such as paragraph topic keys,
  claim types, or explicit stats fields generated before Markdown rendering;
- report input metadata loaded from `data/curated_external/...`;
- future source-intake metadata explicitly marked
  `synthesis_display_only=True`, `risk_score_eligible=False`.

Forbidden producer:

- scanning rendered 4.4 Markdown or the final report body for risk keywords.

If the structured metadata is missing, the builder must treat the flag as absent
and avoid inferring it from display text. In that case the quality checker may
still warn on a visible report contradiction, but production decision logic must
not scrape display-only prose.

## Renderer Integration

### ExecutiveSummaryRenderer

Before:

- computes EV independently,
- reads `ev.get("signal")`,
- can render `EV: +49.83%（N/A）`.

After:

- reads `ctx["recommendation_decision"]`,
- renders:

```text
### 综合评分: 6.2/10 | EV: +49.83%（看多但等待入场）
```

- if no EV:

```text
### 综合评分: 4.1/10 | EV: N/A（N/A）
```

No `N/A%`.

### CompositeScoreRenderer

Before:

- calls `composite_score_section(...)`, which computes and formats EV and
  recommendation.

After:

- either:
  - passes `RecommendationDecision` into `composite_score_section(...)`, or
  - replaces the recommendation/header portion with a new renderer helper using
    the decision object.
- section 1 must display the same score, EV display, and label as the executive
  summary.

### RiskRenderer / risk_score_section

Before:

- `risk_score_section(...)` computes risk score and Markdown together.

After:

- split into:

```python
build_risk_assessment(...) -> RiskAssessment
render_risk_assessment(...) -> str
```

- `risk_score_section(...)` can remain as a compatibility wrapper.
- if `RecommendationDecision.risk.display_only_notes` is non-empty, risk section
  renders a short explanatory note without changing score.
- position advice and entry/position constraint notes must be derived from
  `RecommendationDecision.entry_constraint`, not from an independent narrower
  guardrail.

### Price Target / Technical Sections

No formula changes. They should continue to render their own technical details,
but their entry conclusion must be surfaced into `EntryConstraint` so the final
recommendation label can be constrained consistently.

### HTML Dashboard

Initial implementation may leave HTML unchanged if Markdown is the release gate.
Follow-up should make dashboard read `RecommendationDecision` too; otherwise HTML
can drift from Markdown.

## Data Flow

```text
stock_raw / quote / consensus / pillar / structured risk signals / 4.4 metadata
        ↓
build_recommendation_decision(...)
        ↓
ctx["recommendation_decision"]
        ↓
ExecutiveSummaryRenderer
CompositeScoreRenderer
RiskRenderer
HTMLDashboardRenderer (follow-up)
Quality checks
```

`RecommendationDecision` should be built once before section renderers run.
First implementation should create it at the start of
`ReportAssemblySkill._assemble_markdown(...)`, because all inputs are already in
`ctx` there and this avoids an extra pipeline-ordering change.

Interim placement:

```text
synthesis / claim risk signal / charts / display metadata
        ↓
ReportAssemblySkill builds ctx["recommendation_decision"]
        ↓
section renderers
```

Follow-up placement, after Markdown gates are stable:

```text
scripts/utils/report_skills/decision_skill.py
```

## Quality Gates

Add deterministic checks to `check_report_quality.py` or a dedicated helper:

1. `ev_na_percent`
   - fail on `EV: N/A%`.
2. `summary_score_label_mismatch`
   - execution summary score/EV/label must match section 1 score/EV/label.
3. `blocked_entry_strong_recommendation`
   - if technical section contains `关注/不操作`, section 1 and summary cannot
     display bare `强烈看多` or bare `看多`.
4. `display_only_risk_without_explanation`
   - if structured 4.4 display-only metadata indicates risk-like observations
     and risk score is low, risk section must contain a display-only
     explanation.
5. `risk_position_label_mismatch`
   - if final label says `等待入场`, `避免追高`, or `风险控制优先`, risk section
     cannot render an unconstrained aggressive position recommendation.

These checks should be deterministic and should not call LLMs.

## Failure Modes And Required Tests

| Failure mode | How it appears | Required test |
| --- | --- | --- |
| Summary and section 1 compute labels separately | summary shows `N/A`, section 1 shows `强烈看多` | fixture renders both from one `RecommendationDecision` |
| Missing EV renders as `N/A%` | black sesame header shows `EV: N/A%` | no-consensus decision returns `ev_display == "N/A"` |
| Blocked entry still shows strong positive label | technical says `关注/不操作`, section 1 says `强烈看多` | MACD blocked-entry fixture downgrades to `看多但等待入场` |
| Only `盈亏比不足` is recognized | MACD/dead-cross blocked entry bypasses guardrail | price target error `关注/不操作` with arbitrary reason triggers wait state |
| Risk section ignores entry constraint | section 1 says `看多但等待入场`, risk says `积极配置 20%` | MACD blocked-entry fixture caps risk position via same `EntryConstraint` |
| Display-only external risks look like scored risks | structured 4.4 metadata has risk observation, risk score low, no explanation | metadata flag requires risk note without changing score |
| Display-only risk flag is inferred from prose | risk note appears because renderer scanned 4.4 text | metadata false + risky wording does not create decision note |
| Formal risk score changes due to 4.4 | external viewpoint changes total risk | builder keeps score unchanged but adds display-only note |
| Risk section and section 1 give different position advice | risk says wait, score says aggressive | decision object feeds both renderers |
| Existing risk tests break | old `risk_score_section(...)` callers fail | compatibility wrapper preserves previous public function |
| HTML drifts from Markdown | dashboard still shows old label | follow-up test or documented deferred work |
| Summary uses old EV key | summary reads `ev.get("signal")` and shows `N/A` | grep-style test rejects `ev.get("signal")` in summary renderer |

## Implementation Phases

### Phase 1: Decision Model And Unit Tests

- Add `recommendation_decision.py`.
- Move only formatting/label logic first.
- Write tests for EV display, entry constraint classification, label downgrade,
  and no-consensus cases.
- Include an entry-blocked positive fixture that expects the literal constrained
  label `看多但等待入场`.
- Do not touch renderers until the decision object is green.

### Phase 2: Assembly-Level Decision And Markdown Header Integration

- Build `ctx["recommendation_decision"]` at the start of
  `ReportAssemblySkill._assemble_markdown(...)`.
- Wire decision into `ExecutiveSummaryRenderer`.
- Wire decision into `CompositeScoreRenderer`.
- Ensure both headers are generated from the same decision.
- Remove the summary renderer's direct `ev_expectation(...)` call and
  `ev.get("signal")` read.
- Add report-fragment tests for summary/section 1 consistency.

### Phase 3: Risk Assessment Split

- Extract `build_risk_assessment(...)` from `risk_score_section(...)`.
- Keep `risk_score_section(...)` as a wrapper for compatibility.
- Feed the same `EntryConstraint` into risk position advice.
- Add display-only risk explanatory notes from structured metadata only.
- Preserve existing risk tests; add tests for display-only risk note.

### Phase 4: Quality Gates And Compatibility Checks

- Update quality gates.
- Add guard checks for `EV: N/A%`, summary/section 1 mismatch, bare positive
  labels under blocked entry, and unconstrained risk position under blocked
  entry.
- Add a grep-style test that rejects `ev.get("signal")` in
  `ExecutiveSummaryRenderer`.
- Run focused tests.

### Phase 5: Report Validation

Run local Claude / real report validation only after unit tests pass:

1. 中际旭创:
   - technical `关注/不操作` should downgrade bare positive label;
   - no `contradiction_blocked_entry_strong_recommendation`.
2. 黑芝麻智能:
   - no `EV: N/A%`;
   - special risk table vs composite low risk has clear wording.
3. 圣邦股份:
   - summary and section 1 labels match;
   - source boundary still passes after regeneration.

### Phase 6: Optional Pipeline Skill Promotion

- Promote assembly-level creation to `decision_skill` only after Phase 5 is
  stable.
- This phase is not required for the first consistency fix.

## Backward Compatibility

- Keep public functions:
  - `ev_expectation(...)`,
  - `composite_score_section(...)`,
  - `risk_score_section(...)`.
- Existing callers may continue using them, but new renderers should prefer
  `RecommendationDecision`.
- Do not remove existing risk table rendering.
- Do not change public report entrypoints.

## Stop Conditions

Stop and return to design review if implementation requires:

- changing EV formula weights;
- changing technical indicator algorithms;
- changing formal/source boundary policy;
- making 4.4 scoring-eligible;
- reading rendered 4.4 Markdown to compute display-only risk flags;
- making risk position advice use a different entry guardrail than section 1;
- removing public entrypoints;
- broad template rewrite beyond summary / section 1 / risk section;
- adding live API calls or LLM calls to the decision builder.

## Design Review Questions

1. Should HTML dashboard be in scope for the first implementation, or may it
   follow after Markdown consistency is fixed?
2. Should `decision_skill` be added to the pipeline immediately, or should the
   first patch build the decision in `ReportAssemblySkill` to reduce pipeline
   churn?
3. Should `关注/不操作` always downgrade positive recommendation labels, even
   when EV is very high, or should severe upside preserve `强烈看多` with an
   entry warning?

Recommended default answers:

1. Defer HTML dashboard to follow-up unless Markdown gates pass.
2. Build in `ReportAssemblySkill` first; promote to `decision_skill` only after
   Markdown consistency is stable.
3. Always downgrade bare positive labels when entry is blocked. Keep EV number
   visible, but make the action label reflect entry quality.
