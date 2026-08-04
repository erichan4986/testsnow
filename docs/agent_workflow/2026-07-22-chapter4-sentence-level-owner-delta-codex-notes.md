# Chapter 4 Sentence-Level Owner Delta Implementation Notes

日期：2026-07-22  
状态：implemented, locally verified

## Modified Files

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`

Workflow:

- `docs/agent_workflow/2026-07-22-chapter4-sentence-level-owner-delta-implementation-plan.md`
- this notes file

## RED / GREEN Evidence

1. Owner-aware projection tests first failed because
   `select_external_topic_narratives()` accepted only two arguments.
2. View-model wiring then failed because the owner-equivalent narrative part was
   still present.
3. Renderer tests failed because an empty narrative left its topic heading and
   formal-thin still exposed the earlier hidden citation.
4. After implementation, the two focused files pass: `120 passed in 1.65s`.

## Implementation

- `select_external_topic_narratives()` remains the sole narrative display
  selector. It validates full plan coverage, performs existing external-source
  deduplication, then compares only target parts with visible annual/broker owner
  units.
- Conservative comparison preserves a part when it adds a period, concrete
  anchor, financial metric, stage/event, polarity/constraint, relationship, or
  materially richer text.
- Full/half-width punctuation is normalized only for comparison; retained source
  quotes remain unchanged. `H1/H2` are recognized as time anchors.
- An all-equivalent validated narrative is represented by `parts=()`; the
  renderer skips that topic and does not revive raw rows.
- Peer/industry narratives bypass target-owner comparison.
- Formal-medium and formal-thin pass their existing visible owner rows into the
  same selector. Formal-thin citation offsets continue to use the full snapshot.
- Original external rows are unchanged and remain available to Chapter 4.4.

## Requirement-Test Matrix

| Requirement | Test |
|---|---|
| Exact owner fact hidden, new period retained | `test_external_narrative_hides_owner_equivalent_part_and_keeps_new_period` |
| Same year but different half retained | `test_external_narrative_keeps_same_year_different_reporting_period` |
| Metric/stage/polarity/relation/richer facts retained verbatim | `test_external_narrative_keeps_protected_owner_deltas` |
| Full/half-width punctuation compares consistently | `test_external_narrative_normalizes_full_and_half_width_punctuation_for_owner_match` |
| Complete plan required before filtering | `test_external_narrative_rejects_incomplete_plan_before_owner_filtering` |
| All-equivalent topic produces suppression sentinel | `test_external_narrative_returns_empty_sentinel_when_all_parts_match_owner` |
| Peer narrative bypasses target owner | `test_external_peer_narrative_bypasses_target_owner_comparison` |
| 4.4 rows and owner citations stay unchanged | `test_view_model_projects_owner_equivalent_parts_without_changing_price_path_rows` |
| Empty sentinel cannot trigger raw fallback | `test_external_variable_map_empty_narrative_skips_topic_without_raw_fallback` |
| Formal-thin keeps full-snapshot offset | `test_formal_thin_owner_filter_keeps_full_snapshot_external_citation_offset` |

## Verification

- Focused: `120 passed`
- External v4 downstream: `4 passed`
- Report quality/source/prose downstream: `129 passed`
- Full offline suite: `2599 passed, 16 skipped`
- `bash tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean
- Fresh formal rerun:
  - `reports/复旦微电_20260722.md`, 15,278 bytes, mtime 17:40:23
  - `reports/中际旭创_20260722.md`, 21,499 bytes, mtime 17:41:48
- Both reports pass report quality and source-boundary checks. Prose checks pass
  with the existing theme-overlap warnings.

Runtime numstat against `cc254a8`:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 60 | 4 | +56 |
| `deep_analysis_renderer.py` | 7 | 3 | +4 |
| Total | 67 | 7 | +60 |

The `+60` runtime delta is within the `+70` target and below the `+100` stop
condition.

## Self-Review Repairs

Round 1 found that comparison normalization did not explicitly unify internal
full/half-width punctuation. A comparison-only translation and regression test
were added; source text is not rewritten.

Round 2 found that the plan's incomplete-coverage negative case was not locked by
a test. The missing-unit fixture was added, together with an assertion that 4.1
owner citation refs remain unchanged.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: Fudan switched from `formal_medium` on 2026-07-21 to
  `formal_thin_external_rich` on 2026-07-22 after the earlier external-material
  expansion. Its 4.4 section is therefore absent in the fresh report. This diff
  does not own profile routing or formal-thin section composition, so the issue
  is recorded for a separate profile/layout task.
- Warning: the Fudan FPAI external SourceUnit remains intact because it adds the
  CPU/FPGA/NPU architecture and a product-release event. Its `4-128TOPS` phrase
  consequently still overlaps 4.1. The selector does not perform clause-level
  rewriting, and the external unit never contained the annual report's
  `50K-4000K` detail; that detail was not removed by this implementation.
- Deviation: none in runtime scope or behavior. The same-year reporting-period
  test passed when first introduced because the existing anchor extraction was
  already conservative for that fixture; all behavior-changing paths had RED
  evidence.
- Implementation made no canonical pack, producer, scoring, technical,
  risk/target/recommendation, or LLM prompt changes. Formal report reruns changed
  only ignored report artifacts; worktree source status remained unchanged.
