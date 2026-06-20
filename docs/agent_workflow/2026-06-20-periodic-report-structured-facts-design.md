# Periodic Report Structured Facts Design

> **Date**: 2026-06-20
> **Owner**: Codex
> **Status**: Phase A Implemented

---

## 1. Goal

Turn annual/semiannual report content from a display-only fulltext summary into an explicit structured fact channel.

The current `periodic_report_fulltext_analysis` item is useful material, but it mixes company disclosures, deterministic metrics, LLM judgments, and risk interpretation. It must remain material-layer only. This design introduces a separate path for exact, evidence-bound annual-report facts that can later enter Knowledge and scoring safely.

The first implementation should be a thin spike:

- extract `revenue`, `net_profit`, and `operating_cash_flow`;
- bind each value to deterministic evidence;
- compute one signed derived metric, `operating_cash_flow_to_net_profit`;
- emit one typed risk signal, `cashflow_quality_weak`, only when the signed cash-flow rule crosses a documented threshold;
- keep the existing fulltext material-layer invariant unchanged.

---

## 2. Non-Goals

- Do not persist the existing `periodic_report_fulltext_analysis` item to Knowledge.
- Do not score risk by scanning fulltext summary prose.
- Do not change `KnowledgeSynthesizer` prompts.
- Do not rewrite `scoring_engine.py` in the first helper-only spike.
- Do not add network fetching. Use local fulltext/cache inputs and existing required-metrics helpers.
- Do not build the full annual-report metric universe in the first pass.
- Do not support every HK/A-share table layout before the thin slice proves the interface.
- Do not register `periodic_report_filing_fact` as a confirmed source type in Phase A.
- Do not raise annual-report filing facts to `fact_candidate` through `source_credit` alone in Phase A.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Fulltext material | Builds one `SynthesisItem` with `source_type=periodic_report_fulltext_analysis`, credit 75, `professional_analysis`, display-only | `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py` |
| Required business metrics | Deterministically extracts segment/region/sales/customer/supplier/inventory tables | `scripts/utils/periodic_report_required_metrics.py` |
| Required financial metrics | Extracts financial risk metrics and derived financial ratios | `scripts/utils/periodic_report_required_financial_metrics.py` |
| Source Intake display | Renders fulltext item in a dedicated experimental Source Intake subsection | `scripts/utils/reporter/sections/source_intake_evidence_renderer.py` |
| Synthesis display | Lets fulltext affect `ctx["synthesis_display"]` only; canonical `ctx["synthesis"]` and `ctx["synthesis_text"]` stay baseline | `scripts/utils/report_skills/synthesis_skills.py` |
| Guardrails | Gate and tests prevent material-layer leakage into scoring/risk/Knowledge | `tools/ci_grep_gates.sh`, `tests/reporter/test_fulltext_material_isolation.py` |
| Knowledge notes | Existing note writer filters material fulltext out via `knowledge_eligible=False` and source-type guard | `scripts/utils/evidence_note_writer.py` |

Important current limitation: `periodic_report_required_financial_metrics.py` extracts financial metrics from a flattened source string and currently returns value cells without `source_block_id`, `evidence_refs`, or bounded excerpts. Phase A must solve this before emitting filing facts for `revenue`, `net_profit`, or `operating_cash_flow`.

---

## 4. Proposed Design

### 4.1 Source-Type Split

Keep two separate annual-report paths.

| Path | Source Type | Can Display | Can Enter Knowledge | Can Enter Scoring/Risk | Notes |
|------|-------------|-------------|---------------------|------------------------|-------|
| Fulltext material | `periodic_report_fulltext_analysis` | Yes | No | No | Existing mixed LLM/rule summary, credit 75 |
| Filing fact | `periodic_report_filing_fact` | Yes | Phase B only, after exact evidence binding | Later, via structured consumers | Original report disclosure |
| Derived fact | `periodic_report_derived_fact` | Yes | Deferred beyond Phase B | Later, via structured consumers | Computed from filing facts; display/compute-only until invalidation exists |
| Risk signal | `periodic_report_risk_signal` | Yes | Optional | Yes, only as typed signal | No prose keyword scanning |

Bucket 1 tests must stay anchored to `periodic_report_fulltext_analysis`; they must not block future structured facts.

### 4.2 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| `periodic_report_structured_facts.py` | Build filing facts, derived facts, and typed signals from deterministic required metrics | raw fulltext or existing packs, stock code/name, report type/year | `PeriodicReportStructuredFactPack` dict |
| Filing fact builder | Normalize exact report values | required financial/business metrics | `filing_facts[]` |
| Evidence anchor resolver | Resolve financial values back to exact source blocks/excerpts | evidence-pack blocks, raw matches, normalized values | anchored cells or diagnostics |
| Derived fact builder | Compute ratios from filing fact ids | `filing_facts[]` | `derived_facts[]` |
| Risk signal builder | Apply explicit numeric rules | `filing_facts[]`, `derived_facts[]` | `filing_risk_signals[]` |
| Validation helper | Reject facts without evidence, unit, period, or stable id | fact pack | validation result |
| Later Knowledge adapter | Persist eligible facts without touching fulltext material item | validated fact pack | Knowledge entries |
| Later scoring bridge | Consume typed risk signals only | validated risk signals | risk-score contribution |

### 4.3 Thin Spike Schema

Filing fact:

```python
{
    "schema_version": "periodic_report_structured_fact.v1",
    "source_type": "periodic_report_filing_fact",
    "fact_id": "periodic:300777:2025:annual:revenue",
    "stock_code": "300777",
    "stock_name": "中简科技",
    "report_year": 2025,
    "report_type": "annual",
    "metric_key": "revenue",
    "label": "营业收入",
    "value": "8.46亿元",
    "normalized_value": "84600万元",
    "unit": "万元",
    "currency": "CNY",
    "period": "2025",
    "value_basis": "as_reported",
    "source_block_id": "financial_summary-0",
    "evidence_refs": ["financial_summary-0"],
    "source_excerpt": "2025年公司实现营业收入8.46亿元...",
    "confidence": "high",
    "source_credit": 75,
    "knowledge_eligible": False,
}
```

Phase A uses `confidence` to describe extraction confidence and keeps `source_credit`/`knowledge_eligible` conservative. Phase B may register `periodic_report_filing_fact` into Knowledge with explicit tests; it should not rely on a credit bump alone.

Derived fact:

```python
{
    "schema_version": "periodic_report_structured_fact.v1",
    "source_type": "periodic_report_derived_fact",
    "fact_id": "periodic:300777:2025:annual:operating_cash_flow_to_net_profit",
    "metric_key": "operating_cash_flow_to_net_profit",
    "label": "经营现金流/归母净利润",
    "value": "279.37%",
    "unit": "pct",
    "signed_value": "279.37%",
    "input_refs": [
        "periodic:300777:2025:annual:operating_cash_flow",
        "periodic:300777:2025:annual:net_profit"
    ],
    "calculation": "operating_cash_flow / abs(net_profit)",
    "knowledge_eligible": False,
}
```

The ratio preserves the sign of operating cash flow. Do not use `abs(operating_cash_flow)` for `cashflow_quality_weak`; a negative operating cash flow against positive net profit is one of the key weak-quality cases.

Risk signal:

```python
{
    "schema_version": "periodic_report_risk_signal.v1",
    "source_type": "periodic_report_risk_signal",
    "signal_id": "periodic:300777:2025:annual:cashflow_quality_weak",
    "signal_type": "cashflow_quality_weak",
    "severity": "medium",
    "rationale": "经营现金流为负，或经营现金流/归母净利润低于 50%",
    "input_refs": [
        "periodic:300777:2025:annual:operating_cash_flow_to_net_profit"
    ],
    "scoring_eligible": False
}
```

In the first helper-only spike, risk signals should default to `scoring_eligible=False`. Scoring integration should be a later explicit phase.

### 4.4 Data Flow

```text
local periodic report text/cache
  -> build_periodic_report_fulltext_pack(...)
  -> build_required_financial_risk_metrics(...)
  -> build_required_business_metrics(...)
  -> build_periodic_report_structured_fact_pack(...)
      -> filing_facts
      -> derived_facts
      -> filing_risk_signals
  -> validation
  -> later: Knowledge adapter / scoring bridge
```

### 4.5 Phasing

Phase A: helper-only thin spike.

- New helper and tests.
- No pipeline registration.
- No Knowledge writes.
- No scoring writes.
- Produce fact pack for `revenue`, `net_profit`, `operating_cash_flow`, one derived ratio, and one disabled scoring signal.
- If any of the three filing facts cannot be anchored to a source block/excerpt, skip that fact and emit a diagnostic.

Phase B: Knowledge integration.

- Persist only `periodic_report_filing_fact` through a structured path.
- Keep `periodic_report_fulltext_analysis` blocked.
- Keep `periodic_report_derived_fact` display/compute-only until invalidation/version handling exists.

Phase C: scoring/risk bridge.

- Consume `periodic_report_risk_signal` only.
- No prose keyword scanning.
- Add explicit scoring contribution tests and report rendering.

---

## 5. Evidence And Validation Rules

Every `filing_fact` must have:

- stable `fact_id`;
- `schema_version`;
- `source_type`;
- `metric_key`;
- normalized value and display value;
- period and report type;
- `value_basis`: `as_reported`, `restated`, or `adjusted_unknown`;
- source evidence ref or source block id;
- bounded `source_excerpt`.
- `source_credit` must stay conservative in Phase A. Use `confidence` for extraction confidence; do not make credit alone the Knowledge/scoring gate.

Evidence anchoring options for Phase A:

1. Extend the financial metrics helper so each amount cell includes `source_block_id`, `source_excerpt`, and optionally match offsets.
2. Or have `periodic_report_structured_facts.py` re-anchor each normalized value to one evidence-pack block by searching for the original matched display value.

Either approach is acceptable, but the validator must skip unanchored facts. It must not create placeholder evidence refs.

Every `derived_fact` must have:

- `schema_version`;
- stable `fact_id`;
- `input_refs`;
- calculation string or calculation key;
- deterministic numeric result;
- recomputable inputs.
- `knowledge_eligible=False` in Phase A and Phase B until invalidation machinery exists.

Every `filing_risk_signal` must have:

- `signal_type`;
- rule name or threshold;
- `input_refs`;
- explicit `scoring_eligible` boolean.
- signed cash-flow inputs when the signal depends on cash-flow direction.

Facts without evidence, unit, period, or source type should be skipped with diagnostics, not silently promoted.

---

## 6. Failure Modes And Tests

| Failure Mode | User/Runtime Symptom | Test Or Check That Catches It |
|--------------|----------------------|-------------------------------|
| Fulltext material path gets promoted as structured fact | LLM summary enters Knowledge/scoring as if confirmed | Existing `test_fulltext_material_isolation.py` plus new source-type split tests |
| Filing fact has no evidence ref | Fabrication risk; value cannot be traced | Validator test rejects fact without `source_block_id`/`evidence_refs` |
| Wrong unit or scale | Revenue becomes 8.46万元 instead of 8.46亿元 | Normalization tests with CNY/万元/亿元 fixtures |
| Derived fact stale after formula change | Old ratio persists across runs | `schema_version` and `input_refs` test; derived facts include calculation key |
| Negative OCF hidden by abs() | Weak cash-flow quality is missed | Fixture with negative OCF and positive net profit asserts signed ratio and signal |
| Restated prior-year value treated as current-year value | Wrong growth/ratio base | Phase A fixture asserts ambiguous restated/current-year cases default to `adjusted_unknown`; true restated detection is out of scope |
| Risk signal emitted from prose phrase | Narrative wording changes risk score | Test ensures signal builder reads only facts/derived facts |
| Division by zero or missing denominator | Runtime error or nonsense ratio | Derived builder test skips and records diagnostic |
| Scoring accidentally consumes disabled signal | Risk score changes before Phase C | Test confirms Phase A signals default `scoring_eligible=False` |

---

## 7. Files Expected To Change

Phase A only:

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/periodic_report_structured_facts.py` | Add | Helper-only fact pack builder |
| `tests/utils/test_periodic_report_structured_facts.py` | Add | Thin spike schema, extraction, derived, signal tests |
| `scripts/utils/periodic_report_required_financial_metrics.py` | Modify if needed | Add source block/excerpt provenance for spike financial fields, or expose enough match data for re-anchoring |
| `tests/utils/test_periodic_report_required_financial_metrics.py` | Modify if needed | Cover financial metric provenance if helper is extended |
| `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md` | Update | Review log and design deltas |

Later phases may require:

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/evidence_note_writer.py` or a new structured note writer | Modify/Add | Persist structured facts, not material summaries |
| `scripts/utils/report_skills/__init__.py` | Modify | Register optional structured fact skill if needed |
| `scripts/utils/reporter/scoring_engine.py` | Modify | Phase C typed signal scoring bridge only |
| `scripts/utils/reporter/sections/risk_renderer.py` | Modify | Render typed periodic-report risk contribution |

---

## 8. Files That Must Not Change In Phase A

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/knowledge_synthesizer.py` | No LLM prompt or synthesis behavior change |
| `scripts/utils/reporter/scoring_engine.py` | Phase A is helper-only |
| `scripts/utils/reporter/sections/risk_renderer.py` | No risk scoring bridge yet |
| `scripts/utils/report_skills/knowledge_skills.py` | No Knowledge writes yet |
| `scripts/utils/report_skills/synthesis_skills.py` | Existing material-layer display contract should remain stable |
| `data/raw`, `reports`, `knowledge` | No runtime artifacts or persisted facts in Phase A |

---

## 9. Acceptance Gates

Phase A tests:

```bash
python3 -m pytest tests/utils/test_periodic_report_structured_facts.py -q
python3 -m pytest tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py -q
python3 -m pytest tests/reporter/test_fulltext_material_isolation.py tests/utils/test_ci_grep_gates.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

### Phase A Preview Validation Notes

Read-only preview run over local caches produced:

- `/tmp/zhongjian_2025_structured_facts_preview.md`
- `/tmp/shengbang_2025_structured_facts_preview.md`
- `/tmp/yingjixin_2025_structured_facts_preview.md`
- `/tmp/black_sesame_2025_structured_facts_preview.md`

Findings:

- 圣邦股份 produced all three filing facts and a signed cash-flow ratio of 85.24%.
- 中简科技 produced revenue and operating cash flow, but upstream required financial metrics did not extract net profit.
- 英集芯 had operating cash flow in the evidence block, but anchoring failed because Jina split the Chinese label with spaces (`经 营 活 动...`).
- 黑芝麻智能 HK cache did not produce relevant evidence-pack financial blocks, so Phase A should treat HK support as a non-goal until HK evidence-pack extraction improves.

Follow-up fixes:

- Normalize spaces when matching labels in `_anchor_cell_to_block`.
- Distinguish `missing_net_profit_for_cashflow_ratio` from `non_positive_net_profit_for_cashflow_ratio`.
- Keep the existing conservative rule: unanchored facts are skipped rather than emitted with placeholder refs.

Implemented follow-up:

- Added a Jina-style spaced-label fixture and normalized label matching in `_anchor_cell_to_block`.
- Added a missing-net-profit fixture and `missing_net_profit_for_cashflow_ratio` diagnostic.

No report generation is required for Phase A because it is helper-only and not pipeline-registered.

Before Phase B/Knowledge integration:

- run a review specifically on Knowledge persistence and claim-verification backflow;
- prove `periodic_report_fulltext_analysis` still cannot enter Knowledge;
- prove `periodic_report_filing_fact` can enter only through the structured source type.

Before Phase C/scoring integration:

- add a scoring no-leak test for material fulltext;
- add a typed-signal scoring test;
- show before/after risk contribution in a generated sample report.

---

## 10. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| Should Phase A fact ids use stock code only, or include announcement id when available? | R1 Review | Use stable `periodic:<code>:<year>:<type>:<metric>`; keep announcement id outside the id. |
| Should filing facts use `source_credit=85` or a separate confidence field only? | R1 Review | Use separate `confidence`; keep `source_credit` conservative until Phase B explicitly registers the source type. |
| Should derived facts be Knowledge-eligible in Phase B, or should only filing facts persist first? | R1 Review | Persist only filing facts in Phase B; keep derived facts display/compute-only until invalidation exists. |
| What threshold should `cashflow_quality_weak` use in the first scoring bridge? | Later Phase C | Pending |

---

## 11. Claude Review Log

### Round 1 Feedback

Reviewer: Claude (read-only design review, 2026-06-20)

Status: Must-fix before task

Decision:
- R2 recommended: Yes (lightweight, scoped to the evidence-binding resolution only)
- Reason: The approach is sound and the leakage risk is well contained, but the
  thin-spike schema cannot be filled by reusing the existing helper as written.
  That one resolution changes schema feasibility, so a short R2 confirm is worth it.

Findings:

- [Must-fix] Evidence binding is not reusable for the spike fields.
  `revenue` / `net_profit` / `operating_cash_flow` are produced by
  `scripts/utils/periodic_report_required_financial_metrics.py`, which concatenates
  all evidence-pack blocks **and** `raw_text` into a single `source_text` string
  (`_source_text`) and regexes over it. Its output cells are only
  `{"text", "unit", "normalized"}` (`_amount_cell` / `_value_cell`) — there is
  **no** `source_block_id`, no excerpt, no offset. So the schema fields
  `source_block_id`, `evidence_refs`, and `source_excerpt` cannot be populated by
  reuse for exactly the three fields the spike picks. By contrast,
  `periodic_report_required_metrics.py` (business metrics) already carries
  `source_block_id` / `source_usage` / `source_excerpt` on its concentration
  structures. Resolution: either (a) extend the financial helper to return the
  match's block id + bounded excerpt, or (b) have the fact builder re-anchor each
  normalized value back to a specific block via substring search. Either way the
  validator must **skip** any fact it cannot anchor and emit a diagnostic — it must
  never emit a placeholder/empty `evidence_refs`. Add a test that an unanchored
  value is dropped, not fabricated.

- [Must-fix] `abs()` discards the sign that defines `cashflow_quality_weak`.
  The existing `_build_derived_financial_metrics` uses `abs(numerator)` by
  convention, and the design's `abs(operating_cash_flow) / abs(net_profit)` follows
  it. But the weak-quality case is precisely a **negative** operating cash flow
  against a positive net profit; `abs/abs` turns that into a healthy-looking
  positive ratio and can suppress the very signal it should raise. The derived
  metric and the signal rule must preserve the sign of operating cash flow (e.g.
  trigger when `ocf < 0` OR signed `ocf/np` below threshold). Add a fixture with
  negative OCF + positive net profit and assert the signal fires.

- [Must-fix] Knowledge/scoring gating for `periodic_report_filing_fact` is
  under-specified and collides with existing gates. At `source_credit=85` a filing
  fact still fails `is_core_fact_supporting_source`
  (`scripts/utils/synthesis_credit.py`) because `periodic_report_filing_fact` is not
  in `_CONFIRMED_SOURCE_TYPES`; meanwhile `evidence_note_writer._claim_status_for_item`
  only downgrades `periodic_report_fulltext_analysis` / `periodic_report_excerpt`, so
  a credit-85 filing fact would silently pass through as `fact_candidate`. Pin this
  in Phase B: prefer a **separate `confidence` field** over raising `source_credit`
  (which participates in existing gates), and only register the new source_type in
  the confirmed sets when Phase B wires it with explicit tests. This answers
  open-question #2: keep `confidence` separate; do not lean on `source_credit=85`
  alone.

- [Nice-to-have] `fact_id` stability (open-question #1): keep
  `periodic:<code>:<year>:<type>:<metric>` and **exclude** announcement id — the
  intake path already uses the cache filename stem as an announcement-id fallback
  (`periodic_report_fulltext_intake_skill.py`), which is not stable across
  re-fetches. Keep announcement id as a separate evidence field, not part of the id.

- [Nice-to-have] `value_basis`: the existing extractors do not detect restated /
  retrospectively-adjusted values; they take the first/nearest match. In Phase A
  `value_basis` will realistically be `as_reported` or `adjusted_unknown` only. Make
  real `restated` detection explicitly out-of-scope for Phase A, and have the
  restated fixture assert "defaults to `adjusted_unknown` when both years are
  present and ambiguous" rather than implying true restated parsing.

- [Nice-to-have] Derived-fact persistence (open-question #3 / review Q3): persist
  **only `filing_facts` in Phase B**; defer `derived_facts` Knowledge eligibility
  until invalidation machinery actually exists. `schema_version` + `input_refs`
  enable invalidation but the machinery is not built yet, so persisting derived
  facts now risks propagating stale/compounding errors across runs. Display +
  compute-on-read is the safer interim state.

- [Confirm-safe] Phase A helper-only scope genuinely clears the guardrails:
  `tools/ci_grep_gates.sh` only scans `scoring_engine.py` / `risk_renderer.py` /
  `knowledge_skills.py` for `periodic_report_fulltext|synthesis_display`; the new
  helper is not scanned and contains neither string; no pipeline/`__init__`
  registration; no writes to data/raw/reports/knowledge. The forward-compat
  requirement in the roadmap (anchor the prohibition to
  `periodic_report_fulltext_analysis`, not "all annual-report content") is the right
  guard and is preserved here.

Reuse to name explicitly in the design (currently only implied):
- normalization/ratio anchors: `_amount_in_wan`, `_ratio_cell`, `_value_cell`,
  `_normalize_numeric` in `periodic_report_required_financial_metrics.py`.
- provenance template: the concentration blocks in
  `periodic_report_required_metrics.py` already model `source_block_id` +
  `source_excerpt`; mirror that shape on the financial path.
- note that `operating_cash_flow_to_net_profit` is **not** currently produced by
  `_build_derived_financial_metrics` (it computes `operating_cash_outflow_to_cash`
  against monetary funds). The spike adds a new ratio — fine, but say so rather than
  implying reuse.

Phase A implementation readiness: proceed **after** folding in the three Must-fix
items (evidence-binding resolution, signed-cashflow rule, deferred credit/source_type
gating). The helper-only boundary itself is safe to implement as designed.

### Design Delta After Round 1

Accepted:
- Evidence binding must be solved for the three Phase A financial fields before emitting facts. The design now requires either extending `periodic_report_required_financial_metrics.py` with block/excerpt provenance or re-anchoring values to evidence-pack blocks. Unanchored facts must be skipped with diagnostics.
- The `operating_cash_flow_to_net_profit` derived metric is signed. The signal should catch negative operating cash flow against positive profit; the design no longer uses `abs(operating_cash_flow)`.
- `periodic_report_filing_fact` no longer relies on `source_credit=85` in Phase A. The design uses a separate `confidence` field and keeps `source_credit`/`knowledge_eligible` conservative until Phase B has explicit Knowledge/scoring tests.
- Phase B will persist only original `filing_facts`; `derived_facts` remain display/compute-only until invalidation machinery exists.
- `fact_id` excludes announcement id for stability. Announcement id can remain separate evidence metadata.
- Phase A `value_basis` treats ambiguous restatement cases as `adjusted_unknown`; true restated parsing is out of scope.

Rejected:
- None.

Deferred:
- Scoring/risk consumption of `periodic_report_risk_signal` is deferred to Phase C.
- Knowledge persistence for `derived_facts` is deferred until schema-version invalidation and recomputation behavior exists.
- True restated/as-reported parsing is deferred beyond Phase A.

R2 Required:
- Yes. Run a lightweight R2 focused on evidence anchoring and the revised Phase A gate semantics.

### Round 2 Feedback

Reviewer: Claude (read-only design review, 2026-06-20)

Status: Ready to implement

Decision:
- Phase A implementation allowed: Yes
- Reason: All three Round 1 must-fix items are resolved at the design level, and no
  new blocker was introduced by the changes. The remaining items are implementation
  notes, not design gaps.

Findings:

- [Resolved] Evidence anchoring. Section 3 now records the financial-helper
  limitation; §4.2 adds an "Evidence anchor resolver"; §4.5 and §5 require skipping
  unanchored facts with a diagnostic and forbid placeholder refs; §6 adds the
  validator test; §7 lists the financial helper + its test as "modify if needed".
  This fully closes the R1 must-fix. The schema's `source_block_id:
  "financial_summary-0"` is illustrative — the implementer must use the real block
  ids emitted by `build_periodic_report_evidence_pack`, not a literal.

- [Resolved] Signed cash-flow rule. Goal, §4.3 (`calculation:
  "operating_cash_flow / abs(net_profit)"` plus `signed_value` and the explicit "do
  not use abs(operating_cash_flow)" note), the signal `rationale` ("经营现金流为负，
  或 …低于 50%"), §5, and the §6 negative-OCF fixture all agree. A negative OCF now
  yields a negative ratio that crosses the threshold and fires the signal. Correct.

- [Resolved] Phase A gating. Non-goals #34–35, the schema (`source_credit: 75`,
  `knowledge_eligible: False`, separate `confidence`), §4.1 ("Phase B only"), §5,
  and open-question #2 keep filing facts out of Knowledge/scoring and keep
  `confidence` separate from `source_credit`. Note `source_credit: 75` is itself
  defensively safe: at 75 a filing fact fails `is_core_fact_supporting_source`
  (needs ≥80 + confirmed type) and maps to `professional_analysis`, not
  `fact_candidate`, even if it reached `evidence_note_writer`. Phase A stays
  helper-only: §7 adds only the new helper + tests (and the optional financial-helper
  change); §8 freezes synthesis/knowledge/scoring/risk; no `__init__` registration.

- [Resolved] Phase B / derived facts. §4.1, Phase B (#185–187), §5 (#227), and
  open-question #3 all state Phase B persists only `filing_facts` and keeps
  `derived_facts` display/compute-only until invalidation machinery exists.

Implementation Notes (Phase A implementer must follow):

- If extending `periodic_report_required_financial_metrics.py` (anchoring option a),
  make the change **additive only** — add `source_block_id`/`source_excerpt` as new
  optional keys; do not rename or drop the existing `text`/`unit`/`normalized` cell
  keys. The fulltext material path (`render_periodic_report_fulltext_markdown`,
  `build_periodic_report_fulltext_intake_item`) consumes these cells; a shape change
  would regress it. Re-run `tests/utils/test_periodic_report_required_financial_metrics.py`,
  `tests/reporter/test_fulltext_material_isolation.py`, and `bash tools/ci_grep_gates.sh`.
- Reuse `_amount_in_wan`, `_ratio_cell`, `_value_cell`, `_normalize_numeric` for
  normalization/ratio; mirror the `source_block_id` + `source_excerpt` shape already
  used by the concentration blocks in `periodic_report_required_metrics.py`.
- Specify the `value_basis` default rule in code: `as_reported` when a single clear
  value is found near the label; `adjusted_unknown` when multiple year columns are
  present and cannot be disambiguated. `restated` is out of scope for Phase A.
- Edge to document (nice-to-have): with `abs(net_profit)` in the denominator, a
  loss-making company (net profit < 0) can produce a misleading ratio. `cashflow_quality_weak`
  targets cash-vs-earnings quality; if net profit ≤ 0, prefer recording a diagnostic
  / separate handling rather than emitting a ratio that reads as healthy.
- Keep the new helper free of `requests.get`/`yaml.load`/secret literals so the AST
  gate stays green, and free of the strings `periodic_report_fulltext`/`synthesis_display`.

### Final Implementation Readiness

Phase A (helper-only) is approved for implementation. Build via TDD: write the
failing validator/anchoring/signed-ratio/signal tests first, then the helper. Do not
register the skill, write Knowledge/scoring, or change synthesis in this phase.
Phase B and Phase C remain gated behind their own pre-integration reviews (§9).

### Phase A Implementation Record

Implemented on 2026-06-20.

Files:

- `scripts/utils/periodic_report_structured_facts.py`
- `tests/utils/test_periodic_report_structured_facts.py`
- `docs/agent_workflow/context_index.md`

Implemented behavior:

- builds `filing_facts` for `revenue`, `net_profit`, and `operating_cash_flow`;
- re-anchors each filing fact to a real evidence-pack block id and bounded excerpt;
- skips unanchored facts with `unanchored_filing_fact` diagnostics;
- builds signed `operating_cash_flow_to_net_profit`;
- skips the ratio with `non_positive_net_profit_for_cashflow_ratio` when net profit is non-positive;
- emits disabled `cashflow_quality_weak` risk signal for weak signed cash-flow quality;
- keeps Phase A conservative: `source_credit=75`, `knowledge_eligible=False`, `scoring_eligible=False`;
- does not register pipeline skill, write Knowledge/scoring, or change synthesis.

Verification:

```bash
python3 -m pytest tests/utils/test_periodic_report_structured_facts.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py -q
python3 -m pytest tests/reporter/test_fulltext_material_isolation.py tests/utils/test_ci_grep_gates.py tests/utils/test_agent_workflow_docs.py -q
bash tools/ci_grep_gates.sh
git diff --check
```
