# Knowledge Persistence Slimming 6A4 Codex Notes

verdict: implemented_gate_blocked

## Implementation

- Added versioned producer-owned decisions for every materialized annual SourceUnit.
- Kept aggregate producer diagnostics compatible while recording exact selected-card
  ownership and narrow direct rejection reasons.
- Added exact stale-source resolution by identity, same-block ordered hash sequence,
  then unique cross-block ordered hash sequence. Missing and ambiguous mappings fail
  closed; no fuzzy matching or legacy-text candidate path exists.
- Added six mutually exclusive source-resolution states and actual legacy/pack output
  drift records to the read-only acceptance path.
- No admission, family, continuation, or bundling predicate changed, so
  `SELECTION_VERSION` remains `annual_argument_selection.v2`.
- No Knowledge note was moved, deleted, or changed. Packs and note projections used
  for the eleven-stock audit were refreshed only in a temporary copy.

## TDD And Self-Review

- Batch 1 RED/GREEN: SourceUnit decision version, selected ownership, direct
  regulatory rejection, and broad industry-barrier fail-closed behavior.
- Batch 2 RED/GREEN: unique reindex resolution, ambiguous sequence rejection, and
  direct structural versus broad policy rejection.
- Batch 3 RED/GREEN: acceptance consumes persisted pack decisions, reports all new
  states, and preserves concrete actual-output drift for a reindexed stale note.
- Self-review 1 fixed missing persisted-decision data flow and added explicit
  legacy-only / pack-only material identities.
- Self-review 2 fixed the multi-unit audit contract by recording disposition, reason,
  and selected owner per mapped SourceUnit; the CLI now renders both drift lists.
- Final sanity review replaced membership-based drift with one-to-one multiset
  accounting, preventing identical duplicate notes from disappearing from the ledger.

## Verification

- Focused 6A4 suite: 279 passed.
- Downstream snapshot/renderer/quality/source-boundary suite: 242 passed.
- `tools/ci_grep_gates.sh`: passed.
- `py_compile`: passed for all four allowed runtime files.
- `git diff --check`: passed.
- Runtime baseline: 2,743 lines; final: 2,861 lines; local delta: +118.
  The +120 hard stop is met. No second selector or parser was added.

## Eleven-Stock Local-Cache Gate

- Explicit cache root:
  `/Users/erichan/testsnow/data/raw/periodic_reports`
- Temporary migration root:
  `/private/tmp/testsnow-6a4-acceptance-6pcG9S`
- Acceptance artifact:
  `/private/tmp/testsnow-6a4-acceptance-6pcG9S/acceptance.md`
- Network access: none.
- Actual Knowledge writes, archive moves, or deletes: none.

The six original-orphan resolution states total exactly 127:

| state | count |
| --- | ---: |
| stale_resolved_selected | 0 |
| stale_resolved_structural | 0 |
| stale_resolved_mixed | 0 |
| stale_recovery_required | 125 |
| stale_source_missing | 2 |
| stale_source_ambiguous | 0 |

Per-stock blockers:

| stock | recovery_required | source_missing | legacy_only | pack_only |
| --- | ---: | ---: | ---: | ---: |
| 黑芝麻智能 | 18 | 0 | 87 | 0 |
| 长春高新 | 20 | 0 | 82 | 0 |
| 三花智控 | 22 | 0 | 65 | 0 |
| 中简科技 | 17 | 1 | 83 | 0 |
| 圣邦股份 | 25 | 0 | 97 | 0 |
| 乐鑫科技 | 11 | 0 | 70 | 0 |
| 中际旭创 | 4 | 1 | 46 | 0 |
| 复旦微电 | 8 | 0 | 38 | 0 |
| 华大九天 | 0 | 0 | 0 | 0 |
| 德邦科技 | 0 | 0 | 0 | 0 |
| 赛微微电 | 0 | 0 | 0 | 0 |

Actual selected-material and synthesis parity pass for 3/11 stocks. The eight stale
stocks contain 568 legacy-only selected records and zero pack-only records. Drift
uses one-to-one multiset accounting, so duplicate projections remain visible.

Rejected-unit reason occurrences are `not_self_contained=104`,
`no_family_signal=20`, and `table_or_ocr=13`. Counts are unit occurrences and can
repeat within one stale card. The ledger contains both actionable omissions and
material that must remain rejected: for example, 黑芝麻智能 has current-source
income/order/platform facts mixed with compliance boilerplate, while 三花智控 and
圣邦股份 include visibly interleaved OCR table fragments. The two missing exact
sequences are 中简科技 production/sales-mode material and 中际旭创 customer/R&D-mode
material.

## Gate Decision

- 6A4 instrumentation and classification accepted: yes.
- Current producer recovery complete: no.
- Archive manifest safe to execute: no.
- 6B pack-first implementation allowed: no.

The stop condition is genuine. Broadly promoting `not_self_contained`,
`no_family_signal`, or `table_or_ocr` would admit compliance text and damaged tables
alongside useful facts. The next task must separately design raw-source bundle
recovery for narrative omissions and source-span-aware table handling. It must not
extend this batch beyond the locked +120 budget or treat legacy Markdown as a
producer candidate.
