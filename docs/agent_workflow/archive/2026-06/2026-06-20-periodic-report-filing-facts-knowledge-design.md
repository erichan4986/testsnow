# Periodic Report Filing Facts Knowledge Integration Design

> **Date**: 2026-06-20
> **Owner**: Codex
> **Status**: Draft for Claude Round 1 Review

---

## 1. Goal

Persist validated `periodic_report_filing_fact` entries into Knowledge as exact,
evidence-bound annual/semiannual report facts.

This is **not** the same as persisting `periodic_report_fulltext_analysis`. The fulltext
summary remains material-layer only. Phase B should persist only exact filing facts such
as `revenue`, `net_profit`, and `operating_cash_flow` when they already have stable
`fact_id`, `normalized_value`, `source_block_id`, and bounded `source_excerpt`.

The first implementation should prove the safe seam:

- take an existing `PeriodicReportStructuredFactPack`;
- persist only `filing_facts[]`;
- preserve schema/version/evidence refs;
- keep `derived_facts[]` and `filing_risk_signals[]` out of Knowledge;
- keep fulltext material isolated from Knowledge, scoring, and risk scoring.

---

## 2. Non-Goals

- Do not persist `periodic_report_fulltext_analysis`.
- Do not persist `periodic_report_derived_fact` in Phase B.
- Do not persist `periodic_report_risk_signal` in Phase B.
- Do not modify `KnowledgeSynthesizer` prompts or LLM synthesis logic.
- Do not modify `scoring_engine.py`, `risk_renderer.py`, or risk scoring.
- Do not make filing facts affect final scores in Phase B.
- Do not fetch annual reports or call HKEX/CNINFO/network.
- Do not run report generation as part of the design task.
- Do not rewrite `KnowledgePersistenceSkill` deep-analysis output.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Structured facts | Helper-only pack emits `filing_facts`, `derived_facts`, `filing_risk_signals`; all are non-Knowledge by default | `scripts/utils/periodic_report_structured_facts.py` |
| Fulltext material | `periodic_report_fulltext_analysis` remains credit 75, `professional_analysis`, display-only | `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py` |
| Evidence notes | Writes `SynthesisItem` evidence notes when `knowledge_eligible=True`; claim tier currently tied to source credit | `scripts/utils/evidence_note_writer.py` |
| Knowledge persistence | Writes broad deep-analysis/core-data markdown from `ctx["synthesis"]` and quote data | `scripts/utils/report_skills/knowledge_skills.py` |
| Guardrails | Tests/gates stop fulltext material leaking into Knowledge/scoring/risk | `tests/reporter/test_fulltext_material_isolation.py`, `tools/ci_grep_gates.sh` |

Existing `evidence_note_writer.py` is useful as a reference, but filing facts should not be
forced into its generic claim-stub model. A filing fact already is a structured claim with
value, unit, period, evidence block id, and schema version. Phase B should preserve that
shape instead of collapsing it into title/excerpt prose.

---

## 4. Proposed Design

### 4.1 New Structured Fact Knowledge Writer

Create a narrow writer for periodic filing facts:

`scripts/utils/periodic_report_filing_fact_note_writer.py`

Responsibilities:

- input: `stock_name`, `stock_code`, `fact_pack`, `base_dir`, `dry_run`;
- filter: only `source_type == "periodic_report_filing_fact"`;
- reject facts missing required fields;
- write one deterministic Markdown note per fact under:

```text
knowledge/10-Stocks/{stock_name}/filing_facts/{report_year}-{report_type}-{metric_key}.md
```

Proposed note frontmatter:

```yaml
stock: 中简科技
code: "300777"
source_type: periodic_report_filing_fact
fact_id: periodic:300777:2025:annual:revenue
schema_version: periodic_report_structured_fact.v1
metric_key: revenue
label: 营业收入
normalized_value: 84601.52万元
unit: 万元
currency: CNY
period: "2025"
report_year: 2025
report_type: annual
value_basis: as_reported
confidence: high
source_credit: 75
source_block_id: financial_summary_table-0
evidence_refs:
  - financial_summary_table-0
knowledge_fact_status: filing_fact
knowledge_eligible: false
knowledge_persisted: true
verified_by: []
conflicts_with: []
input_schema_version: periodic_report_evidence_pack.v1
```

Body:

```markdown
# 中简科技 2025 annual revenue

## Fact

- 指标: 营业收入 (`revenue`)
- 数值: 84601.52万元
- 期间: 2025
- 口径: as_reported

## Evidence

> 2025年公司实现营业收入 846,015,199.43 元...

## Guardrails

- This note is an exact filing fact, not an LLM fulltext summary.
- Derived facts and risk signals are not persisted in Phase B.
```

### 4.2 Why Not Use Existing Evidence Notes Directly

The existing `evidence_note_writer.py` maps `source_credit >= 80` to `fact_candidate` and
builds a claim from title/excerpt. That is good for external source-intake items, but it is
not precise enough for structured filing facts:

- filing facts already have stable ids and exact numeric values;
- `source_credit` should stay conservative at 75;
- `confidence=high` should not silently become generic `fact_candidate`;
- the note should preserve `input_refs` / `source_block_id`, not prose-only claims.

Phase B can reuse small utilities later, but the first implementation should be a separate
writer with explicit tests.

### 4.3 Optional Pipeline Skill, Default Off

If Phase B includes pipeline registration, add a default-off skill:

`scripts/utils/report_skills/periodic_report_filing_fact_knowledge_skill.py`

Behavior:

- read `ctx["periodic_report_structured_fact_pack"]` or a configured input key;
- write/dry-run filing fact notes only when
  `enable_periodic_report_filing_fact_knowledge=True`;
- default `dry_run=True`;
- write status keys:
  - `ctx["periodic_report_filing_fact_knowledge_status"]`
  - `ctx["periodic_report_filing_fact_knowledge_plan"]`
  - `ctx["periodic_report_filing_fact_knowledge_summary"]`
- never mutate `external_evidence_keep_items`;
- never write `ctx["synthesis"]`, `ctx["synthesis_text"]`, or scoring/risk keys.

If this feels too large, Phase B may stop at writer-only. Pipeline registration can be
Phase B2.

### 4.4 Source-Type Contract

| Source Type | Knowledge Phase B | Reason |
|-------------|-------------------|--------|
| `periodic_report_fulltext_analysis` | No | Mixed LLM/material summary |
| `periodic_report_filing_fact` | Yes, exact writer only | Exact report disclosure with evidence block |
| `periodic_report_derived_fact` | No | Needs invalidation/recompute policy |
| `periodic_report_risk_signal` | No | Belongs to Phase C scoring/risk bridge |

Tests must assert this source-type split directly. Do not write tests that say "no annual
report content enters Knowledge"; that would break future filing facts. The invariant is:

> fulltext material never enters Knowledge; exact filing facts may enter only through the
> structured filing fact writer.

---

## 5. Validation Rules

The writer must skip a filing fact and emit diagnostics if any required field is missing:

- `source_type == "periodic_report_filing_fact"`;
- `fact_id`;
- `schema_version`;
- `metric_key`;
- `normalized_value`;
- `period`;
- `report_year`;
- `report_type`;
- `value_basis`;
- `source_block_id`;
- non-empty `evidence_refs`;
- bounded `source_excerpt`.

The writer must skip:

- `periodic_report_fulltext_analysis`;
- `periodic_report_derived_fact`;
- `periodic_report_risk_signal`;
- malformed dicts;
- duplicate output path when existing note already has the same `fact_id` and `schema_version`
  unless refresh is explicitly requested.

The writer must preserve:

- `source_credit=75`;
- `confidence=high`;
- `knowledge_fact_status=filing_fact`;
- `knowledge_eligible=false` in the note frontmatter. Filing facts stay
  non-eligible until invalidation machinery exists (matching the sister
  structured-facts design and the `_filing_fact` source object). Persistence is
  marked by `knowledge_fact_status=filing_fact` plus `knowledge_persisted=true`,
  not by flipping `knowledge_eligible`. This applies only after validation passes.

---

## 6. Failure Modes And Tests

| Failure Mode | Symptom | Test Or Check |
|--------------|---------|---------------|
| Fulltext summary leaks into Knowledge | `periodic_report_fulltext_analysis` note appears | Writer test passes mixed pack and asserts fulltext is filtered |
| Derived/risk objects persist | Stale ratios/signals become durable facts | Writer test asserts only `filing_facts[]` are written |
| Missing evidence ref persists | Knowledge fact cannot be traced | Validation test skips fact without `source_block_id` or excerpt |
| Source credit promotes to generic `fact_candidate` | Filing fact semantics lost | Note frontmatter uses `knowledge_fact_status=filing_fact`, not generic claim status |
| Duplicate facts create note spam | Repeated runs produce many copies | Test writes once, second run skips or refreshes deterministically |
| Knowledge deep-analysis receives enhanced fulltext | Fulltext LLM prose persists indirectly | Existing material isolation test plus new pipeline-skill test if skill is added |
| Derived facts become stale | Old ratios remain after formula changes | Phase B test asserts derived facts are not written |
| Path traversal via stock/fact fields | Knowledge write escapes stock dir | Filename sanitizer test with hostile metric key/fact id |

---

## 7. Files Expected To Change

Writer-only Phase B:

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/periodic_report_filing_fact_note_writer.py` | Create | Structured filing fact Knowledge-note writer |
| `tests/utils/test_periodic_report_filing_fact_note_writer.py` | Create | Writer validation, filtering, dedupe, rendering tests |
| `tools/ci_grep_gates.sh` | Modify | Add the new writer to gate (a) `LEAK_FILES` material-isolation watch |
| `tests/utils/test_ci_grep_gates.py` | Modify | Assert the gate rejects fulltext leakage in the new writer |
| `docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md` | Update | Review/implementation log + `knowledge_eligible` reconciliation |

Optional Phase B2 pipeline registration:

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/report_skills/periodic_report_filing_fact_knowledge_skill.py` | Create | Optional default-off pipeline wrapper |
| `scripts/utils/report_skills/__init__.py` | Modify | Register optional skill behind explicit switch |
| `tests/reporter/test_pipeline_integration.py` | Modify | Default-off/order/no-leak tests |
| `tests/reporter/test_fulltext_material_isolation.py` | Modify | Assert fulltext still excluded while filing facts are allowed |

---

## 8. Files That Must Not Change In Phase B

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/knowledge_synthesizer.py` | No prompt/LLM change |
| `scripts/utils/report_skills/synthesis_skills.py` | No synthesis-display change |
| `scripts/utils/reporter/scoring_engine.py` | Scoring is Phase C |
| `scripts/utils/reporter/sections/risk_renderer.py` | Risk rendering/scoring is Phase C |
| `scripts/utils/report_skills/knowledge_skills.py` | Do not mix filing facts into deep-analysis writer in Phase B |
| `scripts/utils/evidence_note_writer.py` | Avoid changing generic external-evidence semantics unless review approves reuse |
| `data/raw`, `reports` | No runtime artifacts |

`knowledge/` writes should appear only in tests using `tmp_path`, not in the real repo.

---

## 9. Acceptance Gates

Writer-only Phase B:

```bash
python3 -m pytest tests/utils/test_periodic_report_filing_fact_note_writer.py -q
python3 -m pytest tests/utils/test_periodic_report_structured_facts.py tests/reporter/test_fulltext_material_isolation.py -q
python3 -m pytest tests/utils/test_ci_grep_gates.py tests/utils/test_agent_workflow_docs.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

If optional pipeline wrapper is included:

```bash
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_fulltext_material_isolation.py -q
```

No real report run is required. No writes to real `knowledge/`, `reports/`, or `data/raw`.

---

## 10. Open Questions For Review

| Question | Preferred Answer | Why |
|----------|------------------|-----|
| Should Phase B include pipeline registration or stop at writer-only? | Writer-only first | Smaller safe seam; pipeline can be B2 |
| Should filing fact notes reuse `evidence_note_writer.py`? | No for v1 | Avoid claim-status/source-credit coupling |
| Should filing facts keep `source_credit=75`? | Yes | Use `confidence`/`knowledge_fact_status`, not credit inflation |
| Should derived facts persist? | No | Need invalidation/recompute policy first |
| Should `periodic_report_filing_fact` be added to confirmed source types? | No in Phase B | Knowledge persistence is not scoring/core-fact confirmation |

---

## 11. Claude Review Log

### Round 1 Feedback (Claude, 2026-06-20)

Status: Must-fix before task
R2 Needed: No (the must-fix items are doc/scope-level reconciliations, verifiable by the
existing acceptance gates; a full second round is not warranted)
Phase B implementation allowed: Yes — writer-only, after folding in the two must-fix items
Recommended seam: writer-only first; defer pipeline registration to Phase B2

The design is structurally sound and the safety intent is right. The source-type split,
the conservative `source_credit=75` stance, the no-derived/no-risk persistence rule, and
the separation from the deep-analysis writer are all correct and confirmed against the
code. Two items must be reconciled before implementation; both are cheap.

Blockers:

- None. No change to `KnowledgeSynthesizer` / synthesis / scoring / risk / fetchers is
  required to implement Phase B. The writer is standalone: it reads a
  `PeriodicReportStructuredFactPack` and renders Markdown under
  `knowledge/10-Stocks/{stock}/filing_facts/`, never touching `ctx["synthesis"]`,
  `synthesis_text`, or scoring keys. `periodic_report_fulltext_analysis` cannot enter
  Knowledge under this design — the writer's input is the fact pack (no fulltext item) and
  the source-type filter only admits `periodic_report_filing_fact`.
- Filing facts do NOT need `source_credit>75` or a confirmed source type to persist. The
  design correctly gates persistence on `knowledge_fact_status=filing_fact` + field
  validation, not on credit inflation (§4.2, §10, and the sister structured-facts design
  Non-Goal "Do not register `periodic_report_filing_fact` as a confirmed source type in
  Phase A / Do not raise to `fact_candidate` through `source_credit` alone"). This is the
  right alternative; keep it.

Must-fix:

1. `knowledge_eligible` contradiction between the two design docs. This design (§4.1
   frontmatter line ~102 and §5 "must preserve `knowledge_eligible=true` ... after
   validation passes") stamps `knowledge_eligible: true` into the persisted note. The
   sister design `2026-06-20-periodic-report-structured-facts-design.md` (§ validation,
   "`knowledge_eligible=False` in Phase A **and Phase B** until invalidation machinery
   exists") forbids that, and the fact object emitted by
   `periodic_report_structured_facts.py:_filing_fact` hard-codes `knowledge_eligible: False`.
   Stamping `true` into the note both contradicts the source object and risks a future
   Knowledge reader / claim-verification backflow treating the note as eligible to feed
   scoring — which Phase B explicitly forbids (Non-Goal "Do not make filing facts affect
   final scores").
   Resolution (preferred): keep `knowledge_eligible: false` in the note, and use
   `knowledge_fact_status: filing_fact` (already in the frontmatter) as the persistence
   marker. If a "this note was persisted" flag is wanted, use a note-local field such as
   `knowledge_persisted: true` that no scoring/verification consumer reads. Whichever way
   it lands, make both design docs state the same thing, and add a writer test asserting
   the persisted note's `knowledge_eligible` matches the agreed value (tie it to the
   source object so they can't drift).

2. The new Knowledge-writing surface is not covered by the fulltext-isolation gate.
   `tools/ci_grep_gates.sh` gate (a) greps a fixed `LEAK_FILES` list
   (`scoring_engine.py`, `risk_renderer.py`, `knowledge_skills.py`) for
   `periodic_report_fulltext|synthesis_display`. `periodic_report_filing_fact_note_writer.py`
   is a brand-new file that writes into `knowledge/`, yet nothing stops a future edit from
   pulling fulltext text into it. Add the new writer (and, if built, the B2 pipeline skill)
   to gate (a)'s `LEAK_FILES`, OR add an equivalent unit test asserting the writer module
   never references `periodic_report_fulltext` / `synthesis_display`. Treat this gate/test
   extension as in-scope for Phase B (it is a guardrail, consistent with §8's intent), and
   add it to §7's writer-only file list.

Nice-to-have:

- Reuse only the path-sanitizer, not the writer. `evidence_note_writer._safe_filename_segment`
  (lowercase, non-alnum→`-`, collapse, strip) is exactly the primitive the hostile-field /
  path-traversal test needs. Reusing it (or copying its logic into a shared helper) reduces
  the chance of a bespoke sanitizer with a traversal hole. The rest of
  `evidence_note_writer.py` should NOT be reused — see below.
- Make the "read only `filing_facts[]`" rule explicit and defense-in-depth: the writer
  should iterate `fact_pack["filing_facts"]` only (never `derived_facts[]` /
  `filing_risk_signals[]`) AND re-assert `source_type == "periodic_report_filing_fact"`
  per item. The §6 "only filing_facts written" test should use a pack that actually
  contains derived + risk entries so the filter is exercised, not vacuously true.
- Path-traversal test should include a hostile `stock_name` (it is a path segment in
  `knowledge/10-Stocks/{stock_name}/...`), not only `metric_key`/`fact_id`. §6 says
  "stock/fact fields" — good; make the stock-name case explicit in the test list.
- Dedupe determinism: §5 skips on matching `fact_id` + `schema_version` "unless refresh is
  explicitly requested". Add a test for the refresh path too (refresh rewrites in place,
  deterministic content), mirroring how `evidence_note_writer` handles
  `refreshed_existing_detail_content`.

Reuse judgment (Open Question 2) — confirmed correct, do not reuse `evidence_note_writer.py`:

- Its `_claim_status` maps `source_credit>=80 → fact_candidate`; filing facts are credit 75,
  so they would land as `professional_analysis` — semantically wrong for an exact
  as-reported disclosure.
- It is built around `SynthesisItem` + canonical-URL dedup + title/excerpt claim stubs.
  Filing facts have no URL, carry exact numeric values, `fact_id`, `source_block_id`, and
  `evidence_refs`; forcing them through the claim-stub model would discard that structure.
- A separate writer keyed on `fact_id` for dedup, preserving the structured frontmatter, is
  the smaller and safer option. The only safe shared primitive is the filename sanitizer
  (above).

Writer-only vs pipeline wrapper:

- Recommend writer-only for Phase B. It is the minimal safe seam and is fully testable
  without pipeline wiring. Defer registration to B2.
- If the pipeline wrapper is built in B2, the must-fix tests are: default-off
  (`enable_periodic_report_filing_fact_knowledge=False` → no write, dry_run default True);
  no-leak (a pack containing a fulltext-style item, or a run with fulltext enabled, persists
  zero fulltext notes); never mutate `external_evidence_keep_items`; never set
  `ctx["synthesis"]` / `synthesis_text` / scoring keys; deterministic ordering/idempotency
  on repeat runs. §7's B2 row already lists the right files — keep them.

Test results (read-only):

- `python3 -m pytest tests/utils/test_agent_workflow_docs.py tests/utils/test_ci_grep_gates.py
  tests/reporter/test_fulltext_material_isolation.py -q` → 13 passed.
- `bash tools/ci_grep_gates.sh` → all gates passed.
- `git diff --check` → clean.

Files changed by this review: only this design document
(`docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md`). No
source, test, config, prompt, data/raw, reports, or knowledge changes.

Recommendation: fold in the two must-fix items (reconcile `knowledge_eligible`; extend the
isolation gate to the new writer), then implement Phase B writer-only via TDD — write the
source-type-split / missing-evidence-skip / hostile-path tests red first, then the writer to
green, keeping the existing fulltext-isolation tests untouched and green.

### Implementation Log (Claude, 2026-06-20)

Phase B writer-only is implemented via TDD (tests red first, then writer to green).

Both must-fix items are resolved:

1. `knowledge_eligible` reconciled. The note frontmatter now stamps
   `knowledge_eligible: false` and uses `knowledge_fact_status: filing_fact` +
   `knowledge_persisted: true` as the persistence markers (§4.1, §5 updated). The writer
   hard-codes `false` regardless of the source object's value, and a test
   (`test_frontmatter_keeps_knowledge_eligible_false_and_status_filing_fact`) feeds a
   hostile `knowledge_eligible=True` fact and asserts the note still persists `false`. This
   matches `periodic_report_structured_facts._filing_fact` and the structured-facts design
   (`knowledge_eligible=False` in Phase A and Phase B). No edit to the structured-facts
   design was needed — it already stated `False`.
2. Isolation gate extended. `scripts/utils/periodic_report_filing_fact_note_writer.py` is
   added to `tools/ci_grep_gates.sh` gate (a) `LEAK_FILES`, and
   `tests/utils/test_ci_grep_gates.py` gains
   `test_ci_grep_gates_rejects_fulltext_leakage_in_filing_fact_writer`. The writer avoids the
   forbidden tokens entirely by using a positive allowlist
   (`source_type == "periodic_report_filing_fact"`) instead of naming material-layer source
   types, so the real-repo gate stays green.

Nice-to-haves folded in: the path sanitizer mirrors
`evidence_note_writer._safe_filename_segment` (metric/report-type) plus a CJK-preserving
`_safe_dir_segment` for the stock name, with a final parent-dir containment check; the
mixed-pack filter test includes derived + risk + material entries inside `filing_facts[]`;
the hostile-path test exercises both a hostile `stock_name` and a hostile `metric_key`; and
a refresh-path determinism test asserts byte-identical re-render.

Public API:

```python
write_periodic_report_filing_fact_notes(
    stock_name: str,
    stock_code: str,
    fact_pack: dict,
    base_dir: str | Path,
    collected_at: str | None = None,
    dry_run: bool = False,
    refresh_existing: bool = False,
) -> FilingFactWritePlan  # .written / .skipped_existing / .refreshed / .filtered
```

Scope held: writer-only, no pipeline registration, no `KnowledgeSynthesizer` / synthesis /
scoring / risk / fetcher changes, and no writes to real `knowledge/`, `reports/`, or
`data/raw` (tests use `tmp_path`).

Test results:

- `python3 -m pytest tests/utils/test_periodic_report_filing_fact_note_writer.py -q` → 8 passed.
- `python3 -m pytest tests/utils/test_periodic_report_structured_facts.py
  tests/reporter/test_fulltext_material_isolation.py -q` → passed (no regression).
- `python3 -m pytest tests/utils/test_ci_grep_gates.py tests/utils/test_agent_workflow_docs.py -q`
  → passed.
- `bash tools/ci_grep_gates.sh` → all gates passed.
- `git diff --check` → clean.

