# Claude Round 1: Annual Coverage Repair Design Review

## Mode

Read-only design review. Do not modify code, tests, config, reports, raw data,
or Knowledge notes. Do not refresh notes or generate reports. Do not access the
network, Xueqiu, Chrome, or CDP.

## Read First

1. `docs/agent_workflow/2026-07-12-annual-coverage-repair-design.md`
2. `docs/agent_workflow/2026-07-11-annual-producer-v2-design.md`
3. `scripts/utils/periodic_report_evidence_pack.py`
4. `scripts/utils/annual_argument_schema.py`
5. `scripts/utils/periodic_report_narrative_evidence_cards.py`
6. `scripts/utils/annual_report_material_pack.py`
7. Relevant tests under `tests/utils/test_periodic_report_evidence_pack.py`,
   `tests/utils/test_periodic_report_narrative_evidence_cards.py`,
   `tests/utils/test_annual_argument_schema.py`, and
   `tests/utils/test_annual_report_material_pack.py`.

## Context

Annual Producer v2 Batch A is implemented, but Batch B removal of the v1
adapter is blocked by a local-cache refresh acceptance. The acceptance found:

- Zhongji's main-business narrative was removed upstream because it ranked 33rd
  behind the evidence-pack cap of 30.
- A Black Sesame HKEX annual-report platform paragraph reached the evidence pack
  but was rejected because its otherwise complete Traditional Chinese paragraph
  did not repeat an explicit company subject.
- A Zhongjian cash-flow explanation was rejected with surrounding A-share
  applicable/not-applicable form markers.
- A Shengbang legacy v1 product note was already covered by split v2 SourceUnits,
  but exact excerpt equality made it look uncovered and left the adapter active.

The proposed repair does not change LLM prompts, collection, profile routing,
Chapter 4 renderer wording, scoring, target price, risk, technical analysis,
executive summary, or recommendation.

## What To Review

Assess whether the design is safe and sufficiently precise before implementation:

1. **Single-selection invariant**
   - Does the family-reserved 48-block allocator merely allocate evidence-pack
     inputs, rather than create a second card selector or taxonomy?
   - Does the shared usage metadata avoid drift between the evidence pack and
     producer?

2. **Evidence coverage and cap**
   - Is one high-value narrative block per populated canonical family the right
     deterministic protection?
   - Does the proposed 48 cap preserve bounded behavior without reintroducing
     the Zhongji failure?
   - Are table/structural blocks kept out of the family-reserve path while still
     retaining the normal priority fill path?

3. **A-share and HKEX boundaries**
   - Is `a_share_annual` causal-tail extraction strict enough not to admit
     checkbox/table noise?
   - Is `hkex_annual` implicit-subject admission narrow enough to avoid a
     stock-specific or overly permissive rule?
   - Does the design preserve direct source substrings and Traditional Chinese
     text exactly?

4. **Migration coverage proof**
   - Is `covered_by_v2_units` strong enough to suppress duplicate v1 adaptation?
   - Can `needs_recovery` still surface a truly omitted factual fragment rather
     than hiding it because a semantically similar v2 card exists?
   - Is it correct that no v1 note is deleted or archived in this batch?

5. **Scope and tests**
   - Check that no prohibited path is inadvertently modified.
   - Check whether the test matrix and eight-stock local-cache acceptance are
     enough to gate later Batch B adapter removal.
   - Check whether the +80 target / +100 hard-stop runtime budget is credible.

## Required Output

Write review notes only to:

`docs/agent_workflow/2026-07-12-annual-coverage-repair-claude-review-round1-notes.md`

Use exactly this structure:

```markdown
# Annual Coverage Repair - Claude Round 1 Review Notes

## Verdict

ok | needs_revision | blocked

## Blockers

- id:
  issue:
  design evidence:
  code evidence:
  required change:

## Must-fix

- id:
  issue:
  design evidence:
  code evidence:
  required change:

## Nice-to-have

- id:
  suggestion:
  rationale:

## Requirement-Test Matrix

| Requirement | Design location | Existing evidence | Missing test or acceptance gate |
| --- | --- | --- | --- |

## Scope Audit

- prohibited-path changes implied by the design:
- duplicate selector/taxonomy risk:
- source-substring/provenance risk:
- runtime budget assessment:

## Recommendation

- Round 2 required: yes | no
- Exact next step:
```

## Stop Conditions

Stop and report `blocked` if the design cannot preserve direct source text,
requires a separate HK producer or a second card selector, needs stock/industry
allowlists, needs an unbounded evidence pack, or cannot keep the repair outside
the prohibited paths.
