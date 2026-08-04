# Technical Market OHLCV Cache v2 Implementation Notes

## Result

Deterministic implementation, live-acceptance repair, and the final local
cold/warm report acceptance are complete.

## Runtime Changes

- `scripts/utils/technical_ohlcv_cache.py`
  - hard-cut schema `technical_market_ohlcv_cache.v2`;
  - generic stock/index identity and collision-proof v2 paths;
  - sole `normalize_ohlcv_frame()` owner;
  - exact source/adjustment, shape, timestamp, freshness, and atomic-write rules.
- `scripts/utils/data_collector.py`
  - deleted collector-local OHLCV normalizer;
  - migrated all stock normalization to the shared owner;
  - explicitly propagates cache directory and HK index-cache policy.
- `scripts/utils/report_skills/technical_skills.py`
  - migrated stock cache reads/writes to the generic v2 API;
  - propagates cache directory through live and cached analysis paths.
- `scripts/utils/reporter/technical_analyzer.py`
  - same-day index cache before provider initialization;
  - Akshare -> mootdx -> recent-cache fallback;
  - malformed Akshare frames continue to mootdx;
  - disabled HK cache and write-failure tolerance;
  - no market-resonance formula change.

## Live Acceptance Repair

The first local cold/warm run wrote both stock caches but no index caches.
Real mootdx frames exposed two deterministic defects that fixtures had missed:

- `date` was both a column and the named `DatetimeIndex`, making
  `sort_values("date")` ambiguous;
- the fallback used `client.k()`, which reads security bars, rather than
  mootdx's dedicated `client.index_bars()` endpoint. This returned an empty
  frame for Shenzhen index `399006`.

Two tests failed before the repair and pass after it. The shared normalizer now
detaches the provider index after materializing the canonical date column, and
the index fallback calls `index_bars(frequency=9, start=0, offset=days)`. The
warm integration fixture was also made independent of the calendar date.

## Final Local Acceptance

The post-repair local rerun passed:

- cold report runs wrote `index-cn-399006.json`, `index-cn-000001.json`, and
  `index-cn-000688.json`, each with 120 ordered mootdx index rows;
- all three payloads use the v2 index identity, `mootdx_index/raw`, empty weekly
  data, and contain no derived technical fields;
- warm report runs made zero stock and zero index provider requests, while all
  three index cache hashes, mtimes, and `fetched_at` values remained unchanged;
- both reports restored computed market/sector resonance and no longer showed
  the insufficient-resonance fallback;
- report quality, CI grep gates, and `git diff --check` passed.

The remaining chart warning (`Timestamp` is not JSON serializable) predates and
is independent of the OHLCV cache contract.

## RED / GREEN

| Batch | RED evidence | GREEN evidence |
|---|---|---|
| A generic v2 cache | collection error: `load_ohlcv_cache` missing | `8 passed` |
| B stock caller cutover | collection error: skill imported deleted v1 API | cache/collector/skill `29 passed, 1 skipped` |
| C index cache | `5 failed, 3 passed`: missing signature, repeated provider calls, warm network calls | resonance integration `8 passed`; final focused `39 passed, 1 skipped` |
| downstream | old top-level analyzer import failed in 6 tests | `95 passed` after package-path import fix |

Implementation self-review added explicit write-failure and disabled-cache tests
after the initial Batch C GREEN. They required no runtime change and both pass;
this is a TDD sequencing deviation, not a behavior or scope deviation.

## Final Verification

- repair-focused cache/resonance: `20 passed`;
- full affected surface: `51 passed, 1 skipped`;
- downstream technical: `95 passed`;
- full pytest: `2851 passed, 10 skipped in 62.07s`;
- CI grep gates: all passed;
- `git diff --check`: clean.

## Runtime Budget

Relative to `b784b96`:

| Runtime file | Added | Removed | Net |
|---|---:|---:|---:|
| `data_collector.py` | 109 | 130 | -21 |
| `technical_skills.py` | 49 | 2 | +47 |
| `technical_analyzer.py` | 58 | 34 | +24 |
| `technical_ohlcv_cache.py` | 196 | 0 | +196 |
| **Total** | **412** | **166** | **+246** |

The pre-v2 dirty-worktree total was `+179`; this batch is `+67`. Both are below
the approved `+110` batch and `+300` total hard stops.

## Deleted-owner Audit

- no `load_technical_ohlcv_cache` or `write_technical_ohlcv_cache` runtime use;
- no cache-private `_frame()`;
- no `TechnicalCollector._normalize_ohlcv_frame()`;
- exactly one `def normalize_ohlcv_frame` under `scripts/utils`;
- the only `technical_ohlcv_cache.v1` reference is the rejection fixture.

## Requirement-test Matrix

| Requirement | Test proof |
|---|---|
| stock/index identity and `000001` separation | `test_index_none_weekly_serializes_empty_and_cannot_collide_with_stock` |
| v1 hard cut | `test_v1_is_ignored_and_invalid_v2_identity_is_rejected` |
| canonical `volume` wins over mootdx `vol` | `test_normalizer_uses_canonical_volume_when_mootdx_has_vol_and_volume` |
| named date index plus date column is unambiguous | `test_normalizer_detaches_mootdx_date_column_from_named_datetime_index` |
| exact three-day fallback boundary | `test_exact_three_day_cache_is_fallback_eligible` |
| index weekly `None` -> `{}`, non-empty rejected | two index weekly cache tests |
| stock v2 same-day reuse and cache-dir propagation | `test_same_day_a_share_cache_recomputes_without_network` |
| network-first recent stock fallback | `test_recent_cache_falls_back_only_after_network_failure` |
| index same-day zero provider calls | `test_index_same_day_cache_skips_both_providers` |
| malformed Akshare -> mootdx and live write | `test_malformed_akshare_index_falls_through_and_writes_mootdx` |
| Shenzhen index uses dedicated mootdx index API | `test_shenzhen_index_fallback_uses_mootdx_index_bars` |
| recent index fallback preserves mtime | `test_index_uses_recent_cache_only_after_provider_failure` |
| duplicate index fetched once, cold/warm semantics equal | `test_duplicate_index_mapping_fetches_once_then_reuses_cache` |
| write failure preserves live frame | `test_index_cache_write_failure_keeps_live_frame` |
| HK/disabled cache does not read or write v2 | `test_disabled_index_cache_uses_live_provider_without_touching_file` |
| full warm stock+index zero technical providers | `test_full_warm_skill_path_makes_zero_stock_or_index_provider_calls` |

## Blocker / Warning / Deviation

- Blocker: none in deterministic implementation.
- Warning: old v1 files remain ignored local artifacts and are intentionally not
  migrated or deleted.
- Warning: warm cache paths intentionally omit optional Baidu fund-flow/concept
  calls; this is outside the OHLCV zero-network contract.
- Deviation: the two implementation-self-review tests noted above were added
  after initial GREEN.
- Local acceptance: passed for 中际旭创 and 复旦微电, including immutable warm
  index caches and zero stock/index provider calls.
