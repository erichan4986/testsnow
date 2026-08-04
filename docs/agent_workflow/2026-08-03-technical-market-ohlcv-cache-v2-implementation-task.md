# Technical Market OHLCV Cache v2 Implementation Task

## Goal

Hard-cut the uncommitted stock-only v1 cache to the approved generic multi-asset
v2 contract and make same-day A-share warm runs perform zero stock/index OHLCV
provider calls.

Read first:

- `docs/agent_workflow/2026-08-03-technical-market-ohlcv-cache-v2-design.md`
- `docs/agent_workflow/2026-08-03-technical-market-ohlcv-cache-v2-claude-review-round1-notes.md`

## Allowed Runtime Files

- `scripts/utils/technical_ohlcv_cache.py`
- `scripts/utils/data_collector.py`
- `scripts/utils/report_skills/technical_skills.py`
- `scripts/utils/reporter/technical_analyzer.py`

## Allowed Test Files

- `tests/utils/test_technical_ohlcv_cache.py`
- `tests/test_data_collector.py`
- `tests/reporter/test_technical_skills_contract.py`
- `tests/reporter/test_market_resonance_integration.py`

Implementation notes may be written to:

- `docs/agent_workflow/2026-08-03-technical-market-ohlcv-cache-v2-implementation-notes.md`

## Prohibited

- No v1 reader, migration, wrapper, dual writer, or old-cache deletion command.
- No scoring, target, risk, position, recommendation, indicator, resonance,
  provider-order, prompt, config, renderer, data, knowledge, or report changes.
- No network during deterministic tests and no formal report generation before
  all deterministic gates and runtime budgets pass.
- Do not revert or format unrelated dirty-worktree changes.

## Batch A: Generic Cache v2

1. RED: replace v1 tests with v2 contract fixtures covering stock/index paths,
   identity, source pairs, v1 rejection, index weekly rules, exact 3-day
   freshness, malformed/future/stale data, attrs, canonical `volume`, raw-only
   projection, and atomic writes.
2. Run the cache test file and record expected failures against v1.
3. GREEN: implement `normalize_ohlcv_frame`, `load_ohlcv_cache`, and
   `write_ohlcv_cache`; delete `_frame` and both v1 public functions.
4. Run the cache test file to green.

## Batch B: Stock Cutover and Parameter Chain

1. RED: update collector/skill tests to require the generic API, one shared
   normalizer, v2 stock identity, explicit cache-directory propagation through
   collector methods, and unchanged HK no-stock-cache behavior.
2. Run the two focused files and record expected failures.
3. GREEN: delete `TechnicalCollector._normalize_ohlcv_frame`, import the shared
   normalizer, migrate skill reads/writes, and propagate optional `cache_dir`
   through `collect`, `build_collection_payload`, `build_technical_payload`, and
   `_run_technical_analyzer` into quote.
4. Run cache/collector/skill tests to green.

## Batch C: Index Cache and Full-path Warm Proof

1. RED: add fixtures for same-day short-circuit, cold live write, malformed
   Akshare fall-through, recent fallback, stale rejection, write failure,
   disabled HK cache, duplicate-symbol reuse, cold/warm resonance identity, and
   full-path zero stock/index provider calls.
2. Run the resonance test file and record expected failures.
3. GREEN: migrate `_fetch_index_kline` to the generic cache and pass
   `index_cache_enabled` plus cache directory from quote. Update the one strict
   fake signature; leave the variadic corporate-action patch unchanged.
4. Run all four focused files plus technical state-machine/renderer/resonance
   downstream tests.

## Batch D: Gates and Stops

Run:

```text
python3 -m pytest tests/utils/test_technical_ohlcv_cache.py tests/test_data_collector.py tests/reporter/test_technical_skills_contract.py tests/reporter/test_market_resonance_integration.py -q -p no:cacheprovider
python3 -m pytest tests/reporter/test_technical_state_machine.py tests/reporter/test_technical_renderer.py tests/reporter/test_market_resonance.py tests/reporter/test_technical_resonance.py tests/reporter/test_corporate_action_adjustment.py -q -p no:cacheprovider
python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
```

Measure runtime net delta from the current pre-v2 worktree and from `b784b96`.
Stop before report generation if this batch exceeds `+110` runtime lines or the
four runtime files exceed `+300` net lines versus `b784b96`.

Write implementation notes containing RED/GREEN evidence, test results,
runtime numstat, deleted-owner audit, requirement-test matrix, deviations, and
whether local cold/warm acceptance is allowed.
