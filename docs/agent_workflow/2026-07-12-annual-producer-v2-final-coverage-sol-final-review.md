# Annual Producer v2 Final Coverage Final Review

## Final Sign-Off

- `verdict: blocked`
- `Batch B allowed: no`
- Fresh focused verification: `2 failed, 297 passed`.
- Runtime versus `aa7bdd9`: `+393`, above the locked `+334` ceiling.
- Downstream, CI grep, diff check, and the eight-stock gate were not run because
  focused and runtime gates failed first. No report was generated.

The current worktree is not acceptable as the final implementation. It contains
salvageable source-boundary work, but it is not a better integration point than
the pre-Luna `+359 / 292-green` state: it is `+34` runtime lines larger, has an
original-suite contract still red after the intended uncapped behavior change,
has an unsafe C4 invalid classifier, and has no eight-stock `0/0` evidence.

## Independent Evidence

The required focused command was rerun unchanged:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest \
  tests/utils/test_annual_argument_schema.py \
  tests/utils/test_periodic_report_evidence_pack.py \
  tests/utils/test_periodic_report_narrative_evidence_cards.py \
  tests/utils/test_annual_report_material_pack.py -q -p no:cacheprovider
```

Result: `2 failed, 297 passed in 1.49s`.

The real scoped numstat is:

| Runtime file | Added | Deleted | Net | Pre-Luna net | Change from pre-Luna | Ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `annual_argument_schema.py` | 73 | 0 | +73 | +54 | +19 | +62 |
| `annual_report_material_pack.py` | 120 | 28 | +92 | +84 | +8 | +92 |
| `periodic_report_evidence_pack.py` | 33 | 3 | +30 | +30 | 0 | +30 |
| `periodic_report_narrative_evidence_cards.py` | 361 | 163 | +198 | +191 | +7 | +150 |
| **Total** | **587** | **194** | **+393** | **+359** | **+34** | **+334** |

The bounded fix reduced schema from `+93` to `+73` (`-20`) but grew producer
from `+180` to `+198` (`+18`). It therefore removed only two net runtime lines,
from `+395` to `+393`, instead of the 61 needed to reach `+334`. The exact
remaining excess is schema `+11` plus producer `+48`.

The four governed tests are `+1020` net lines versus `aa7bdd9`, and collection
is 299 tests versus the pre-Luna 292. There is no pre-Luna checkpoint from which
to compute an exact Luna-only test numstat, but the identifiable final-batch
growth includes duplicate source-tail coverage, the large incomplete synthetic
coverage fixture, three overlapping no-semantic-dedup contracts, and the
malformed multiline C4 fixture.

The overall worktree is not scoped-clean: before this review note it contained
609 porcelain entries: 4 runtime modifications, 4 governed test modifications,
2 tracked workflow-document modifications, 34 untracked workflow documents,
and 565 untracked `knowledge/` paths. Those unrelated/generated paths were not
modified by this review and must not be mixed into a manual rollback.

## Remaining Failures

### 1. Definition-like body test

`test_definition_like_body_terms_are_rejected_without_reordering_strategy_text`
is now a stale test contract, not a producer defect under the locked design.

The producer correctly rejects both definition units in `industry_outlook-0`
and admits two disjoint valid market units: `industry_outlook-1` and
`future_strategy-0`. The test still passes `max_cards_per_type=1` and expects
one card, but the final design explicitly ignores legacy limits, deletes
cross-block semantic collapse, and admits every valid selected-block unit.
Both admitted texts satisfy the locked market subject-plus-relation rule.

The minimum repair is test-only: expect those two block IDs, assert the
definition block is absent, and assert unique exact SourceUnit ownership. This
is inside the locked design. It does not justify adding another runtime filter.

### 2. Interleaved R&D C4 test

`test_sgt_interleaved_rd_ocr_is_invalid_but_wrapped_rd_is_actionable` does not
send the claimed full damaged block to the classifier. `_write_note()` prefixes
only the first physical line with `>`, while
`_extract_narrative_evidence_excerpt()` stops at the next non-blockquote line.
Independent probes show:

```text
full damaged fixture -> interleaved_rd_table
extracted test excerpt -> first line only
first line only -> no invalid reason
```

Quoting every damaged line is the minimum fixture repair and remains inside the
locked design. That alone is insufficient for sign-off: the current C4 branch
also classifies the normal spaced sentence
`研发团队 持续推进 高性能 电平转换 产品开发 并完成验证。` as
`interleaved_rd_table`. It therefore still violates the required C4-only
boundary. A conforming minimum runtime change would narrow the existing C4
predicate to all locked conjuncts, including explicit subject and complete
subject-relation negatives; it must not add another pass or selector.

## Complexity Assessment

Necessary and worth preserving as isolated changes:

- the `competitive_position` line budget `12 -> 20`, with `_MAX_BLOCKS == 48`,
  `_MAX_CHARS_PER_BLOCK == 2000`, and the sole selector unchanged;
- the public bounded `annual_source_tail()` contract, exact normalized-source
  substring result, terminal punctuation gate, and producer offset re-find via
  `cleaned.find()`;
- exact C3 tail proof through the unchanged same-block contiguous
  `_proof_unit_ids()` path;
- passing original block text to block-level noise checks;
- deletion of producer cross-block semantic dedup and one concise regression
  proving disjoint exact SourceUnits survive;
- the complete-financial-comparison table-noise exemption concept;
- candidate validation, exclusive ownership, and fail-closed invariant checks.

Luna-only expansion that is not justified by the accepted result:

- broad rewrites and accumulated exceptions in `_primary_family()`,
  `_mapped_family_has_seed_signal()`, `_family_signals()`,
  `_continues_same_argument()`, `_is_self_contained_atomic_fact()`, and the four
  concrete business/technology/market/financial predicates;
- parallel/interacting C4 decisions in producer noise and material invalid
  classification without a safe normal-spaced R&D negative control;
- the oversized source-prefix implementation form above the schema ceiling;
- duplicate or incomplete final-coverage tests, especially the large synthetic
  fixture and malformed material C4 fixture.

The bounded fix restored many prior behaviors by adding 18 producer net lines
after the first review, instead of restoring the pre-Luna predicate bodies and
then keeping only narrow C1-C4 deltas. That is why it improved 23 failures to 2
but did not converge on the replacement-oriented complexity contract.

## Source Boundary

| Invariant | Result | Evidence |
| --- | --- | --- |
| Exact source tail | Holds | `annual_source_tail()` returns a terminal exact substring of normalized source; producer re-finds it within original unit bounds. |
| Exact material proof | Holds | `_proof_unit_ids()` filters by the same `source_block_id`, resets on ordinal gaps, and uses exact substring search only. |
| C4 invalid only | **Does not hold** | Full damaged fixture is invalid, but normal spaced R&D prose can also be invalidated. |
| One evidence selector | Holds | Evidence pack calls `_select_bounded_blocks()` once; cap remains 48. |
| One producer path | Holds | One block loop, one unit-preparation loop, and one adjacent bundle scan; no rejected-unit pass. |
| No v1-guided producer | Holds | Producer discards `raw_text`, reads only selected evidence blocks, and does not read v1 notes or material diagnostics. |
| No fuzzy/semantic/cross-block proof | Holds | No such proof path was found; material Jaccard remains limited to adapted-v1 record dedup after classification. |

Foreign-block and arbitrary-prefix material-proof negatives are still not
explicitly covered in the governed tests, although the current proof code is
same-block and exact. This is a residual test gap, not permission to run Batch B.

## Safe Close-Out

Do not retain the current Luna state wholesale and do not continue with another
coverage implementation round. Manually return to the pre-Luna green behavior,
without reset/checkout and without touching unrelated workflow or `knowledge/`
paths, then stop this batch.

Preserve only the isolated items listed above. For the producer, manually
restore the pre-Luna bodies of `_primary_family()`,
`_mapped_family_has_seed_signal()`, `_family_signals()`,
`_continues_same_argument()`, `_is_self_contained_atomic_fact()`,
`_has_concrete_business_fact()`, `_has_concrete_market_fact()`, and
`_has_concrete_financial_fact()`. Remove Luna-only fallback/exception layering.
Do not preserve the current unsafe C4 branch. If the consolidated technology
predicate cannot be retained while restoring the original 292 behavior, prefer
the known green baseline over preserving that consolidation.

For tests, retain the exact C1 cap/window test, bounded source-tail cases, the
real C3 producer-to-material boundary, and one concise no-semantic-dedup exact
ownership test. Manually remove or revert duplicate source-tail cases, the
incomplete giant final-coverage fixture, malformed C4 fixture, and redundant
predicate-specific Luna expansion. The old one-card definition expectation
must not drive a runtime filter; either align it with uncapped behavior if that
behavior is retained, or restore it only together with the full pre-Luna
behavioral baseline.

The safe stopping target is the pre-Luna `292 passed, 0 failed` behavioral
surface and its `+359` runtime envelope, not two more local patches on top of
`+393`. Any future C1-C4 completion would require a separately bounded task;
it is not part of this final close-out.
