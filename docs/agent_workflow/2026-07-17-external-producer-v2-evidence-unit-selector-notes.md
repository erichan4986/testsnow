# External Producer V3 Offline Notes

## Status

Offline implementation and code-only legacy cleanup are complete. Production
cutover remains blocked on the unpassed Gate B2 live validation; no production
config, cache, or report artifact was modified.

## Modified Files

Runtime changes are limited to the task allow-list. The old narrative/digest
runtime and preview modules were deleted, and the remaining external path now
uses only `curated_external_argument_pack.v3` and
`curated_external_argument_card.v3`.

Tests were reduced to V3 contracts. In particular, 57 renderer tests that
translated deleted V1/V2 fixtures into V3 at test time were removed. The
remaining renderer coverage includes V3 exact evidence, formal-thin snapshot
citation offsets, and fail-closed legacy-input negative cases.

## RED / GREEN

1. Removing the test-only legacy renderer adapter produced three expected
   failures: the fixtures supplied legacy generic display text instead of V3
   cards. Replacing those fixtures with V3 cards restored the intended Preview
   and citation assertions.
2. The new formal-thin V3 citation regression first rejected a non-incremental
   external fact, as designed. Adding the test-only `2026Q3` anchor made it an
   incremental variable; it rendered as `[^5]` after four annual snapshot refs.
3. Removing the historical external-bucket priority made one snapshot test
   fail because it expected a V1/V2 bucket preference. The V3 expectation is
   now that distinct admitted variables remain visible, and the test is green.

## Requirement / Test Matrix

| Requirement | Evidence |
| --- | --- |
| Exact source-unit materialization and deterministic enrichment | `tests/utils/test_curated_external_argument_cards.py` |
| Selector batch/retry/completeness and no prose fields | `tests/utils/test_curated_external_full_body_viewpoint_claims.py` |
| V3 pack reader/display fail-closed isolation | `tests/utils/test_curated_external_display.py` |
| Preview writes only V3 pack outside the repository | `tests/reporter/test_curated_external_full_body_viewpoint_preview.py` |
| Target-only profile routing and no legacy fallback | `tests/reporter/test_synthesis_skills.py`, `tests/reporter/test_stock_reporter_source_intake_config.py` |
| Snapshot adapter, external incrementality, and V3 citation allocation | `tests/utils/test_deep_analysis_material_snapshot.py` |
| Formal-rich/formal-thin renderer evidence and citation offsets | `tests/reporter/test_deep_analysis_renderer.py` |
| External freshness/risk consumers remain display-only | `tests/utils/test_evidence_freshness.py`, `tests/reporter/test_recommendation_decision.py` |

## Verification

- `tests/utils`: `1310 passed, 3 skipped`
- `tests/reporter`: `1110 passed, 12 skipped`
- top-level tests: `26 passed, 1 skipped`
- external/downstream focused suite: `265 passed`
- Chapter 4 quality/source suite: `168 passed`
- `bash tools/ci_grep_gates.sh`: PASS
- `git diff --check`: PASS
- Runtime numstat vs `62be6bf`: `+813 / -3829 / net -3016`

The V3 reader/display tests use persisted temporary packs only. No report-time
path opens source packets, legacy narrative files, or an LLM.

## Design Delta

The task originally deferred Batch E deletion until Gate B2. The user explicitly
approved a code-only pull-forward after the interim runtime delta reached
`+768`. Legacy runtime, previews, and compatibility tests were therefore
deleted without changing `config/stocks.json`, local caches, or production
reports. This restores the final runtime budget, but is not production
promotion.

## Blockers / Warnings / Deviations

- **Blocker:** Gate B2 remains `needs_revision`: the previous live Fudan sample
  lacked stable target-family coverage and included unsupported prose. Do not
  enable V3 in `config/stocks.json` until two identical local-input live runs
  meet the acceptance matrix.
- **Warning:** existing production stock configuration still names removed
  narrative/digest paths. They are deliberately ignored by the V3-only code;
  this is safe fail-closed behavior, but means external display is not enabled
  for a normal report until a later, explicit config cutover.
- **Deviation:** code-only Batch E deletion was pulled forward with user
  approval to eliminate duplicate systems and satisfy the runtime budget. No
  cache deletion, live model call, report generation, or config promotion was
  performed.

## Live Gate Commands (Do Not Run Here)

Set `EXTERNAL_SELECTOR_MODEL`, `EXTERNAL_SELECTOR_BASE_URL`, and
`EXTERNAL_SELECTOR_API_KEY_ENV` to the approved local credentials. Run each
command twice against identical local source packets and baselines, writing
only `/tmp` packs:

```bash
python3 scripts/previews/curated_external_full_body_viewpoint_preview.py --source-jsonl "$ZHONGJI_SOURCE_JSONL" --baseline-synthesis-file "$ZHONGJI_BASELINE_SYNTHESIS" --stock 中际旭创 --pack-output /tmp/zhongji-curated-external-argument-pack-v3-run1.json --llm-model "$EXTERNAL_SELECTOR_MODEL" --llm-base-url "$EXTERNAL_SELECTOR_BASE_URL" --llm-api-key-env "$EXTERNAL_SELECTOR_API_KEY_ENV" --max-sources 0
python3 scripts/previews/curated_external_full_body_viewpoint_preview.py --source-jsonl "$ZHONGJI_SOURCE_JSONL" --baseline-synthesis-file "$ZHONGJI_BASELINE_SYNTHESIS" --stock 中际旭创 --pack-output /tmp/zhongji-curated-external-argument-pack-v3-run2.json --llm-model "$EXTERNAL_SELECTOR_MODEL" --llm-base-url "$EXTERNAL_SELECTOR_BASE_URL" --llm-api-key-env "$EXTERNAL_SELECTOR_API_KEY_ENV" --max-sources 0
python3 scripts/previews/curated_external_full_body_viewpoint_preview.py --source-jsonl "$FUDAN_SOURCE_JSONL" --baseline-synthesis-file "$FUDAN_BASELINE_SYNTHESIS" --stock 复旦微电 --pack-output /tmp/fudan-curated-external-argument-pack-v3-run1.json --llm-model "$EXTERNAL_SELECTOR_MODEL" --llm-base-url "$EXTERNAL_SELECTOR_BASE_URL" --llm-api-key-env "$EXTERNAL_SELECTOR_API_KEY_ENV" --max-sources 0
python3 scripts/previews/curated_external_full_body_viewpoint_preview.py --source-jsonl "$FUDAN_SOURCE_JSONL" --baseline-synthesis-file "$FUDAN_BASELINE_SYNTHESIS" --stock 复旦微电 --pack-output /tmp/fudan-curated-external-argument-pack-v3-run2.json --llm-model "$EXTERNAL_SELECTOR_MODEL" --llm-base-url "$EXTERNAL_SELECTOR_BASE_URL" --llm-api-key-env "$EXTERNAL_SELECTOR_API_KEY_ENV" --max-sources 0
python3 scripts/previews/curated_external_full_body_viewpoint_preview.py --source-jsonl "$HEIZHIMA_SOURCE_JSONL" --baseline-synthesis-file "$HEIZHIMA_BASELINE_SYNTHESIS" --stock 黑芝麻智能 --pack-output /tmp/heizhima-curated-external-argument-pack-v3-run1.json --llm-model "$EXTERNAL_SELECTOR_MODEL" --llm-base-url "$EXTERNAL_SELECTOR_BASE_URL" --llm-api-key-env "$EXTERNAL_SELECTOR_API_KEY_ENV" --max-sources 0
python3 scripts/previews/curated_external_full_body_viewpoint_preview.py --source-jsonl "$HEIZHIMA_SOURCE_JSONL" --baseline-synthesis-file "$HEIZHIMA_BASELINE_SYNTHESIS" --stock 黑芝麻智能 --pack-output /tmp/heizhima-curated-external-argument-pack-v3-run2.json --llm-model "$EXTERNAL_SELECTOR_MODEL" --llm-base-url "$EXTERNAL_SELECTOR_BASE_URL" --llm-api-key-env "$EXTERNAL_SELECTOR_API_KEY_ENV" --max-sources 0
```

Before production cutover, compare both runs for identical target coverage and
profile routing, verify every persisted evidence unit is an exact source
substring with a valid hash/ref, and manually review the displayed samples.
