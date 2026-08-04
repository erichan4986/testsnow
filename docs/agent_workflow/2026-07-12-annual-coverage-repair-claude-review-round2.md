# Claude Round 2: Annual Coverage Repair Design Review

## Mode

Read-only design review. Do not modify code, tests, config, reports, raw data,
or Knowledge notes. Do not refresh notes or generate reports. Do not access the
network, Xueqiu, Chrome, or CDP.

## Read First

1. `docs/agent_workflow/2026-07-12-annual-coverage-repair-design.md`
2. `docs/agent_workflow/2026-07-12-annual-coverage-repair-claude-review-round1-notes.md`
3. `scripts/utils/annual_argument_schema.py`
4. `scripts/utils/periodic_report_evidence_pack.py`
5. `scripts/utils/periodic_report_narrative_evidence_cards.py`
6. `scripts/utils/annual_report_material_pack.py`
7. The focused annual/periodic test files named in the design.

## Round 2 Purpose

Round 1 returned `needs_revision` with four must-fix items. The design has been
revised without code changes. Verify that the revised design closes, rather than
merely restates, every item:

| Round 1 id | Required closure |
| --- | --- |
| MF-01 | `annual_argument_schema.py` owns the full compatibility mapping; producer imports it and deletes `_USAGE_FALLBACKS`. |
| MF-02 | A-share marker tails are extracted only within one materialized SourceUnit, with exact suffix/terminator/noise boundaries, so structured evidence-pack consumers are untouched. |
| MF-03 | Envelope `document_style` reaches producer admission; only listed HK narrative usages with named anchor plus predicate receive implicit-subject admission. |
| MF-04 | Producer and material pack share whitespace normalization and an exact, meaningful-fragment SourceUnit coverage proof; no fuzzy similarity suppresses a v1 note. |

## Review Questions

1. Does the schema metadata contract now eliminate the two-taxonomy risk without
   introducing a second candidate selection path?
2. Is the one-SourceUnit A-share suffix rule exact enough to preserve the
   Zhongjian-like causal fact while rejecting multi-marker, table, and generic
   boilerplate cases?
3. Is the HKEX rule narrow enough for Black-Sesame-like platform paragraphs but
   resistant to standalone labels and non-HK leakage?
4. Does `covered_by_v2_units` require a strong enough proof to avoid masking a
   genuinely missing legacy fact? Does `needs_recovery` correctly preserve the
   v1 adapter as the fallback?
5. Are 48-block allocation, the acceptance matrix, and the +100 net runtime
   stop condition still adequate?
6. Does any proposed change leak into renderer wording, scoring, target, risk,
   technical analysis, recommendation, LLM prompts, or collection?

## Required Output

Write review notes only to:

`docs/agent_workflow/2026-07-12-annual-coverage-repair-claude-review-round2-notes.md`

Use exactly this structure:

```markdown
# Annual Coverage Repair - Claude Round 2 Review Notes

## Verdict

ok | needs_revision | blocked

## Round 1 Closure Matrix

| Finding | closed | evidence | remaining concern |
| --- | --- | --- | --- |

## Remaining Blockers

- id:
  issue:
  evidence:
  required change:

## Remaining Must-fix

- id:
  issue:
  evidence:
  required change:

## Scope and Budget Audit

- prohibited-path risk:
- source-substring/provenance risk:
- second-selector/taxonomy risk:
- runtime-budget assessment:

## Recommendation

- design ready for implementation planning: yes | no
- next step:
```

## Stop Conditions

Return `blocked` if the revised design requires a separate HK producer, a second
selector, stock/industry-specific rules, fuzzy v1 coverage matching, an
unbounded evidence pack, or any prohibited business-path change.
