# Annual Producer v2 Coverage Completion - Codex Notes

## Recovery From The Stopped Implementation

- Restored punctuation-based SourceUnit materialization; line-aware splitting
  had changed stable unit ordinals and bypassed whole-block table guards.
- Kept whole-block table/boilerplate rejection except for the two mixed
  narrative usages that require unit-level admission.
- Added narrow business, concrete-risk, R&D narrative, expense-subject, and
  argument-continuation handling without a second selector or new family.
- Replaced tests that asserted incidental `uN` ordinals with exact owned source
  text assertions for the two mixed full-block fixtures.
- Consolidated the opposite bundle predicates into one continuation decision.

## Verification

- Annual schema/evidence/producer/material-pack tests: `292 passed`.
- Renderer/quality/source-boundary downstream tests: `187 passed`.
- `bash tools/ci_grep_gates.sh`: passed.
- `git diff --check`: passed.
- Runtime delta versus `aa7bdd9`: `+359` across the four governed files. This
  exceeds the `+259 + 50` review trigger. No structural stop was introduced,
  but the batch remains over its preferred complexity budget.

## Eight-Stock Local-Cache Gate

The eight previews were regenerated from the existing local cache only. No
network access or report generation occurred.

| Stock | Actionable recovery fragments | Adapter uses |
| --- | ---: | ---: |
| Black Sesame | 6 | 3 |
| Changchun High-Tech | 0 | 0 |
| Sanhua Intelligent Controls | 0 | 0 |
| Zhongjian Technology | 3 | 3 |
| SGT Micro | 6 | 4 |
| Espressif | 11 | 7 |
| Zhongji Innolight | 2 | 1 |
| Fudan Microelectronics | 0 | 0 |

## Stop Result

`Batch B allowed: no`.

Five stocks remain nonzero, so v1 notes were not archived, the adapter was not
deleted, and reports were not generated. The remaining samples are not one
uniform producer failure:

- true omitted narrative units, including Black Sesame product roadmaps and
  SGT product-portfolio facts;
- facts partly represented by adjacent v2 SourceUnits but not exactly covered,
  including Zhongjian cash-flow commentary;
- legacy OCR/table fragments whose admission cannot be widened safely, such as
  SGT's broken product table row.

The next design must classify these groups separately. It must not weaken exact
coverage, use v1 notes to select producer cards, add another recovery pass, or
label concrete facts invalid merely to clear the gate.
