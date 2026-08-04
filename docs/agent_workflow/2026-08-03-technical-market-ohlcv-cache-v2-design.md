# Technical Market OHLCV Cache v2 Design

## 1. Decision

Replace the uncommitted stock-only `technical_ohlcv_cache.v1` implementation
with one generic multi-asset cache. The v2 cache owns raw OHLCV persistence for
both A-share stocks and the mainland market/thematic indices used by technical
resonance.

This is a hard cutover. The runtime does not read, migrate, shadow, or rewrite v1
files. Existing v1 files are disposable local artifacts and a later cold run may
rebuild v2 files naturally.

## 2. Success Contract

1. A cold A-share report run may request stock and index OHLCV and writes valid
   v2 cache entries after each successful source fetch.
2. A second same-day run performs no stock, market-index, or thematic-index
   provider request.
3. Every indicator, technical judgment, and market-resonance result is recomputed
   from cached raw frames by current runtime code.
4. Fund-flow, concept, news, and non-technical sources remain outside this cache
   and outside the zero-technical-network assertion.
5. Cache failures can reduce market-resonance completeness but cannot discard a
   usable stock technical analysis or abort report generation.

## 3. Non-goals

- No indicator, trend, price-target, scoring, risk, position, or recommendation
  changes.
- No provider-order change: stocks remain Akshare then mootdx; indices remain
  Akshare then mootdx.
- No cache for computed indicators, `technical_judgment`, resonance, fund flow,
  concept data, or report output.
- No A-share cache substitution for Hong Kong stocks or their Wind benchmarks.
- No v1 reader, migration adapter, dual writer, or stale-file cleanup command.

## 4. Cache Contract

### 4.1 Public API

`scripts/utils/technical_ohlcv_cache.py` exposes only the generic API:

```python
normalize_ohlcv_frame(
    frame, *, source, adjustment, limit,
) -> DataFrame | None

load_ohlcv_cache(
    asset_type, symbol, market, *, cache_dir=None, now=None,
) -> dict

write_ohlcv_cache(
    daily_data, *, asset_type, symbol, market, source, adjustment,
    weekly_data=None, fetched_at=None, cache_dir=None, now=None,
) -> Path | None
```

The v1 `load_technical_ohlcv_cache()` and
`write_technical_ohlcv_cache()` names are deleted. Callers must migrate to the
generic API; compatibility wrappers are prohibited.

`normalize_ohlcv_frame()` becomes the sole stock/index frame-normalization
owner. It replaces `TechnicalCollector._normalize_ohlcv_frame()` and the local
index renaming/coercion branch. It supports Akshare Chinese columns, mootdx
`vol`, canonical `volume`, `date`, `datetime`, and a dated index. When both
`vol` and `volume` exist, canonical `volume` wins. It coerces OHLCV, drops
invalid/duplicate dates, sorts ascending, tails to `limit`, and attaches source
and adjustment attrs.

The old cache-private `_frame()` and
`TechnicalCollector._normalize_ohlcv_frame()` are deleted, not retained as
wrappers. Cache-array validation and provider-frame normalization may share
small private coercion primitives inside this module, but there is one public
normalization owner and no duplicate field/alias policy elsewhere.

`daily_data` and `weekly_data` are raw dict-of-list OHLCV arrays. The cache
module remains the sole owner of validation, canonical field projection,
freshness, identity checks, path construction, and atomic persistence.

### 4.2 Identity and Paths

Schema version: `technical_market_ohlcv_cache.v2`.

Required identity fields:

```json
{
  "asset_type": "stock | index",
  "symbol": "300308 | 000001",
  "market": "0 | 1 | cn"
}
```

The JSON type of stock `market` is an integer (`0` or `1`); index `market` is
the string `"cn"`. String values `"0"` and `"1"` are not accepted.

Paths under `data/processed/technical_ohlcv/v2/` are:

- `stock-0-300308.json`
- `stock-1-688385.json`
- `index-cn-000001.json`
- `index-cn-000688.json`

`asset_type` is an enum, `symbol` must be six ASCII digits, and `market` must be
`0` or `1` for stocks and exactly `cn` for indices. These checks prevent path
injection and ensure the Shanghai Composite index cannot collide with stock
`000001`.

### 4.3 Payload

```json
{
  "schema_version": "technical_market_ohlcv_cache.v2",
  "asset_type": "index",
  "symbol": "000001",
  "market": "cn",
  "source": "akshare_index",
  "adjustment": "raw",
  "fetched_at": "2026-08-03T16:30:00+08:00",
  "latest_date": "2026-08-03",
  "daily_data": {},
  "weekly_data": {}
}
```

Stocks require non-empty daily data and may carry weekly data. Indices require
non-empty daily data. An index write serializes `weekly_data=None` as `{}`;
non-empty index weekly data is rejected on both write and read. Allowed
source/adjustment pairs are:

- stock: `akshare/qfq`, `mootdx/raw`;
- index: `akshare_index/raw`, `mootdx_index/raw`.

Recursive sources such as `cache:mootdx`, unknown source labels, mismatched
adjustments, derived fields, unequal column lengths, invalid numerics, duplicate
identity, and future timestamps are rejected.

### 4.4 Freshness

- `same_day`: `fetched_at` is today in Asia/Shanghai and the latest bar is no
  more than seven natural days old. It may be returned before any provider call.
- `fallback_eligible`: both `fetched_at` and the latest bar are no more than
  three natural days old, but the cache is not `same_day`. It may be returned
  only after all configured providers fail.
- `stale`: older than three natural days. Frames are not returned.
- future `fetched_at` or future latest bar: `invalid`.

A fallback read never refreshes `fetched_at` or file mtime.

## 5. Runtime Data Flow

### 5.1 Stock OHLCV

`technical_fetching_skill()` preserves its owner order:

1. explicit `stock_raw["technical"]`;
2. fresh local Wind package;
3. A-share v2 stock `same_day` cache;
4. live collector;
5. A-share v2 stock `fallback_eligible` cache after live failure;
6. unavailable.

The skill converts the live technical payload's raw `daily_data` and
`weekly_data` into one `write_ohlcv_cache(asset_type="stock", ...)` call. Cache
reuse calls `build_collection_payload()` and recomputes all current analysis.

### 5.2 Explicit Cache-directory Propagation

The existing `ctx["technical_ohlcv_cache_dir"]` test/local override is passed
explicitly through:

```text
technical_fetching_skill
  -> TechnicalCollector.collect / build_collection_payload
  -> build_technical_payload
  -> _run_technical_analyzer
  -> quote["technical_ohlcv_cache_dir"]
  -> advanced_medium_term_resonance
  -> _fetch_index_kline
```

All new parameters default to `None`, preserving direct callers. No environment
variable, mutable module global, CLI flag, or hidden context singleton is added.

The fresh Wind path passes the same cache directory into technical analysis.
Existing Wind-provided benchmark projection remains unchanged; Hong Kong paths
do not read or write the mainland index cache. Because the existing prefix
fallback can map an unknown Hong Kong code to `000001`, the quote explicitly
carries `index_cache_enabled=False` for `market="hk"`. This disables only cache
read/write; it does not change the pre-existing live-index behavior in this
batch.

### 5.3 Index OHLCV

For each mainland market or thematic symbol,
`_fetch_index_kline(symbol, days, cache_dir, now)` performs:

1. read `asset_type=index, market=cn`;
2. return a `same_day` frame without importing/calling either provider;
3. call Akshare;
4. if successful, normalize, tag `akshare_index/raw`, write v2, and return;
5. otherwise call mootdx;
6. if successful, normalize, tag `mootdx_index/raw`, write v2, and return;
7. after both fail, return an unchanged `fallback_eligible` frame;
8. otherwise return `None`.

The function also accepts `index_cache_enabled=True`. A disabled cache follows the
existing live provider sequence without reading or writing v2. The same-day
cache branch executes before importing Akshare or initializing mootdx. A
non-empty provider frame that fails canonical normalization counts as that
provider failing and continues to the next provider; it must not return early.

If market and thematic mappings resolve to the same symbol, the first successful
fetch writes cache and the second lookup uses that same-day entry. Index cache
write failure logs a warning and returns the live frame.

`days` controls provider request size, normalization tailing, and newly written
rows. A cache read returns the valid stored frame as-is; it does not synthesize
missing history when a later caller requests a larger `days` value. Current
report callers request approximately 120 rows.

## 6. Failure Modes and Guards

| Failure | Required behavior | Test proof |
|---|---|---|
| v1 file exists | ignored; no migration or rewrite | v1 rejection fixture |
| stock/index share `000001` | distinct identity and path | collision test |
| wrong asset/market/symbol | invalid, no frames returned | identity matrix |
| malformed/truncated JSON | invalid, continue provider flow | malformed fixture |
| index payload contains weekly rows | reject write/read | index shape fixture |
| stock payload lacks daily rows | reject | stock shape fixture |
| derived keys leak into payload | writer projects only raw fields | key-set assertion |
| same-day index cache exists | zero Akshare/mootdx calls | provider call-count test |
| Akshare returns malformed non-empty index frame | continue to mootdx | provider fall-through test |
| providers fail, recent cache exists | return fallback without touching file | mtime/fetched-at test |
| providers fail, cache is stale | return `None`; resonance degrades | stale integration test |
| index cache write fails | use live index frame | write-failure test |
| stock cache path reused | current stock behavior remains green | skill contract tests |
| cached vs live index input | identical market-resonance structure | cold/warm identity fixture |
| HK Wind package | no mainland cache read/write | HK regression test |
| test monkeypatch accepts old two-argument shape | update the one strict fake; variadic fakes remain valid | downstream signature audit |
| Friday cache read on Monday | `fallback_eligible`, provider attempted first | exact three-day fixture |
| cached frame attrs | preserve upstream source/adjustment | attrs assertion |

## 7. TDD Batches

### Batch A: Generic v2 Cache

Modify:

- `scripts/utils/technical_ohlcv_cache.py`
- `tests/utils/test_technical_ohlcv_cache.py`

RED fixtures lock v1 rejection, stock/index identity separation, source pairs,
shape constraints including index `None` to `{}`, exact three-day freshness,
frame attrs, atomic writes, and raw-only projection. GREEN replaces the v1
public API, deletes private `_frame()`, and removes its wrappers in the same
batch.

### Batch B: Stock Caller Cutover

Modify:

- `scripts/utils/report_skills/technical_skills.py`
- `scripts/utils/data_collector.py`
- `tests/reporter/test_technical_skills_contract.py`
- `tests/test_data_collector.py`

RED tests require generic v2 calls and explicit cache-directory propagation.
GREEN migrates callers, deletes
`TechnicalCollector._normalize_ohlcv_frame()`, and imports the sole shared
normalizer without changing provider selection or analysis formulas.

### Batch C: Index Cache and Zero-network Warm Path

Modify:

- `scripts/utils/reporter/technical_analyzer.py`
- `tests/reporter/test_market_resonance_integration.py`

RED tests prove same-day short-circuit, live write, recent fallback, stale reject,
write-failure tolerance, malformed-Akshare fall-through, disabled HK cache,
duplicate-symbol single fetch, and cold/warm resonance identity. GREEN adds no
second cache implementation. The existing strict `_fake_fetch_index(symbol,
days)` test double is updated to accept the new cache keyword; production does
not add a compatibility call branch merely for a mock signature. The audit also
records the variadic patch in `test_corporate_action_adjustment.py`; it requires
no signature change.

Batch C includes one deterministic full-path warm test. With valid same-day
stock and index caches present, it exercises the real collector/analyzer path
while patching stock Akshare, index Akshare, and mootdx factory calls as counters;
all remain zero. This complements the isolated index call-count test.

### Batch D: Verification

Run focused cache, collector, skill, resonance, state-machine, and renderer tests;
then full pytest, CI grep gates, and `git diff --check`.

Local acceptance starts with no v2 entries for the two stocks and their mapped
indices. It records the union of mapped indices, runs both cold reports in
sequence so every unique stock/index entry is materialized at most once, then
runs both reports warm without deleting anything. The warm logs must contain
zero stock/index OHLCV provider calls; every v2 cache file must keep identical
mtime and `fetched_at`; both reports must retain complete technical and
market-resonance sections and pass report quality/source/prose gates.

Acceptance records two intentional properties: a same-day cache may remain
intraday-stale until the next cold fetch, and warm stock-cache runs keep
`include_optional=False`, so optional Baidu fund-flow/concept fields may be
empty. Neither property weakens the zero stock/index OHLCV network assertion.

## 8. Scope and Budget

Allowed runtime files:

- `scripts/utils/technical_ohlcv_cache.py`
- `scripts/utils/data_collector.py`
- `scripts/utils/report_skills/technical_skills.py`
- `scripts/utils/reporter/technical_analyzer.py`

Allowed tests are the four corresponding files named in Section 7. No config,
prompt, scoring, risk, target, renderer, data, knowledge, or report file may be
modified by implementation.

Relative to the current dirty worktree immediately before v2 implementation
(measured runtime delta `+179` versus `b784b96`):

- runtime net target: `<= +90` lines;
- runtime hard stop: `+110` lines;
- total runtime hard stop relative to `b784b96`: `+300` lines;
- if the hard stop is exceeded, stop before local report generation and return
  to design with a replacement/deletion ledger.

The runtime budget excludes tests. Tests should replace v1 fixtures where the
contract changed and avoid repeated setup helpers, but correctness fixtures are
not deleted to meet a line target.

No network is required for deterministic tests. Local cold/warm report
acceptance is a separate post-test step and must not be faked with hand-written
cache files.

## 9. Design Delta After Independent Review

### Accepted

- Re-baselined the runtime stops to `+110` for this batch and `+300` total.
- Made deletion of both old normalization owners explicit.
- Unified the function and quote field as `index_cache_enabled`.
- Locked index `weekly_data=None` serialization to `{}` and rejection of any
  non-empty index weekly payload.
- Added the full-path zero-provider test, exact three-day boundary fixture,
  loaded-frame attrs assertion, and both existing fetch patch sites to the
  audit.

### Rejected

- None of the must-fix findings.

### Deferred

- Removing the pre-existing Hong Kong fallback to mainland index `000001`.
- Intraday cache expiry and requested-row-aware cache refetch.
- Caching optional Baidu fund-flow or concept data.

These are independent behavior changes and are not required for the A-share
zero-technical-network contract.

### Round 2 Required

No. There is no blocker, all must-fix findings are resolved without changing
provider order, cache scope, HK policy, or scoring/technical algorithms.
