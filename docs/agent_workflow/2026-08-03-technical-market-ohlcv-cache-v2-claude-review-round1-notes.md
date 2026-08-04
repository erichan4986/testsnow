# Technical Market OHLCV Cache v2 Claude Review Round 1

## Verdict

`needs_revision` — no blockers; the core design (identity, freshness, provider
order, hard-cut, HK disable, zero-network mechanism) is sound and the two
Codex self-reviews caught the right issues. A small set of must-fix items
(budget re-baseline, explicit single-normalization-owner deletion, parameter
naming consistency, index `weekly_data` serialization) should be reflected in
the design before implementation.

Method: read-only. Reviewed the v2 design, both Codex self-review notes, the
actual runtime (`technical_ohlcv_cache.py`, `data_collector.py`,
`report_skills/technical_skills.py`, `reporter/technical_analyzer.py`,
`reporter/technical_resonance.py`, `wind_kline_loader.py`), the four named
test files, `test_corporate_action_adjustment.py` (second `_fetch_index_kline`
patcher), git status/numstat vs HEAD `b784b96`, `.gitignore`, the index map
config, and mootdx/tdxpy column semantics from the installed packages. No code,
test, config, data, cache, knowledge, report, or prompt was modified.

## Blocker

None.

## Must-fix

1. **Budget is not credible for the mandated scope** (see Budget judgment).
   `+80` batch hard stop is likely tripped; `+260` total sits at the edge. The
   design's tripwire mitigation is sound, but the numbers should be
   re-baselined or the tripwire accepted explicitly before implementation.

2. **Single normalization owner must be an explicit deletion.** §4.1 says
   `normalize_ohlcv_frame()` becomes "the sole stock/index frame-normalization
   owner", but does not state that the v1 module's private `_frame()`
   (`technical_ohlcv_cache.py:23-44`) and `data_collector._normalize_ohlcv_frame()`
   (`data_collector.py:180-216`) are **deleted**. Leaving `_frame` alongside
   `normalize_ohlcv_frame` would recreate the exact two-owner duplication that
   Codex self-review Round 1 (item 1) was written to prevent. Make the deletion
   of both explicit in §4.1 and §7 Batch A/B.

3. **Parameter naming inconsistency.** §5.3 uses `_fetch_index_kline(..., cache_enabled=True)`;
   §5.2 uses the quote field `index_cache_enabled=False`. Pick one name and use
   it for both the function parameter and the quote key so the propagation
   chain is auditable.

4. **Index `weekly_data` serialization is ambiguous.** The public API defaults
   `weekly_data=None`; §4.3 requires indices to "have an empty `weekly_data`
   object". Specify that an index write serializes `None` as `{}` and that any
   non-empty index `weekly_data` is rejected on both write and read.

## Nice-to-have

1. **HK still fetches a mainland index.** For an HK stock (e.g. `02533`),
   `load_market_index_map` → `_prefix_fallback` maps any unknown 5-digit code to
   market index `000001` (SSE Composite) (`technical_resonance.py:56-62`), and
   the analyzer calls `_fetch_index_kline("000001", ...)` live even on the Wind
   path. The design's `index_cache_enabled=False` correctly prevents cache
   read/write, but the pre-existing live fetch is intentionally preserved.
   Out of scope per the non-goals; consider documenting it (or gating the whole
   index fetch for `market="hk"`) so HK reports don't hit the network for a
   mainland index at all.

2. **Intraday staleness of `same_day`.** A cache fetched at 10:00 is served for
   the rest of the trading day. Accepted tradeoff for stocks; worth a sentence
   for fast-moving indices.

3. **No test-line budget.** The four allowed test files are the largest real
   growth (v1 test files are already +451 lines vs HEAD; Batch A-C adds
   ~15-20 fixtures). The budget only constrains runtime lines. Decide
   explicitly whether tests are unbounded or add a test budget.

4. **Cache is length-insensitive on read.** `_fetch_index_kline(symbol, days=…)`
   returns a stored frame of whatever length was written. If a later run
   requests more rows (`days` = `daily_count`, which can exceed the write-time
   limit if a stock's data grows to 250), the cache returns the older, shorter
   frame. Both current callers pass ~120, so low risk — but state in §4.3/§5.3
   that `days` governs provider fetch and write truncation only, not cache read.

5. **Index `daily_data` gains `amount`.** Unified `normalize_ohlcv_frame` maps
   成交额→amount, whereas today's index branch drops it. Harmless to
   `analyze_index_trend` (uses close/volume only), but a small behavior delta.

6. **`now` not in the §5.2 propagation chain.** The public API defaults `now=None`;
   for deterministic freshness tests, document how tests inject `now` (write
   fixtures pass it explicitly; reads default to current Shanghai time).

7. **Warm reports drop optional baidu fund-flow/concept sections.**
   `_use_cache(…, include_optional=False)` means a `same_day` run returns
   `fund_flow=[]` and `concept_blocks={}`. Pre-existing v1 behavior, explicitly
   out of cache scope per SC-4 — but it should be a stated acceptance
   expectation so a warm report missing 资金流向 is not mistaken for a defect.

## Requirement-test gaps

1. **No deterministic full-path zero-network test.** The Batch C provider
   call-count test proves the index half in isolation; the stock skill-contract
   test (`test_same_day_a_share_cache_recomputes_without_network`) mocks
   `build_collection_payload`, so the real analyzer — and therefore
   `_fetch_index_kline` — never runs. The end-to-end "warm run makes zero
   stock+index provider calls" property is covered only by the manual local
   acceptance (§7 Batch D). Recommend one Batch C integration test that patches
   `ak.index_zh_a_hist` and mootdx `Quotes.factory` with call counters and runs
   `advanced_medium_term_resonance` with both a stock and an index cache
   present, asserting zero provider calls.

2. **Three-day natural boundary is not fixture-covered.** Existing freshness
   tests cover next-day (→ fallback_eligible) and >3d (→ stale), but not the
   exact boundary where `fetched_at` and `latest_date` are both exactly 3
   natural days old (e.g. Friday fetch, Monday run), which must be
   `fallback_eligible` (network-first), not `same_day`.

3. **Test-audit under-documents the second patch site.** Two
   `_fetch_index_kline` patchers exist: `test_market_resonance_integration.py:39`
   `_fake_fetch_index(symbol, days=120)` (strict, positional — must be updated
   for the new cache keyword) and `test_corporate_action_adjustment.py:42-44`
   (a variadic lambda — survives the signature change). Self-review Round 2's
   "one strict fake" is functionally correct but should name both sites.

4. **No attrs assertion on cache load.** v1 tests assert values (`amount`,
   `close`) but not that a loaded frame carries the correct
   `data_source`/`adjustment` attrs; worth one assert in Batch A since the
   analyzer reads `df.attrs` for `data_source`/`adjustment`.

## Hard-cutting v1: SAFE

- `data/processed/` is git-ignored (`.gitignore:49`); the two existing v1
  files (`0-300308.json`, `1-688385.json`) are disposable local artifacts from
  earlier acceptance runs.
- The v1 module is imported only by the dirty `technical_skills.py` and its own
  test file, both migrated in the same batch; no other script references the
  v1 path or module (grep clean).
- v2 diverges in directory (`…/technical_ohlcv/v2/`), filename prefix
  (`stock-`/`index-`), and schema string (`technical_market_ohlcv_cache.v2`),
  so no ambiguity, shadowing, or migration is possible.
- Stock/index `000001` collision is structurally prevented (`stock-0-000001.json`
  vs `index-cn-000001.json`).

## Provider order / behavior preservation

- Stock daily: akshare qfq → mootdx raw (`data_collector.fetch_kline`) — unchanged.
- Stock weekly: routed to the same source as daily (`source == "mootdx"` →
  mootdx-first) — unchanged.
- Index: akshare → mootdx (`technical_analyzer._fetch_index_kline`) — unchanged;
  normalize-failure now counts as provider failure and continues to mootdx
  (Round 2 fix) — correct and covered by the fall-through fixture.
- HK: stock cache skipped (`market != "hk"` guard), index cache disabled via
  the explicit flag; live index behavior preserved per non-goals — correct.
- Verified from installed tdxpy source: `get_security_bars` returns `vol`
  (not `volume`); mootdx `to_data` then adds `volume = vol`. So mootdx frames
  carry **both** columns and `normalize_ohlcv_frame`'s "canonical `volume`
  wins" rule is exactly the right resolution (consistent with the 15:43:09
  v1 fix). Both `client.bars` (stock) and `client.k` (index) go through
  `to_data`, so the rule applies uniformly.

## Freshness

`same_day` = fetched today (Asia/Shanghai) + latest bar ≤ 7 natural days;
`fallback_eligible` = both ≤ 3 natural days (network-first); `stale` = older;
future → `invalid`. This carries the Round 1 fix (both `fetched_at` AND
`latest_date` constrained) and matches v1 semantics. Fallback reads never
refresh `fetched_at`/mtime. Correct.

## Zero-network warm proof

Mechanism is credible: index same-day lookup precedes provider import/init
(§5.3), the skill same-day branch precedes `collect` (§5.1), and every
indicator/judgment/resonance is recomputed from cached raw frames by
`build_collection_payload` / `analyze_index_trend`. Deterministic call-count
tests are feasible (akshare is installed; mootdx is importable). The one gap is
the missing full-path integration test (above); otherwise SC-2 is proven per
component plus the manual local acceptance.

## Budget judgment

Measured current runtime delta vs `b784b96` (the `+260` reference):

- `data_collector.py` — `+126/-127` → **-1**
- `report_skills/technical_skills.py` — `+41` → **+41**
- `technical_ohlcv_cache.py` (untracked v1 module) → **+139**
- **Current runtime total: +179 lines.**

Estimated v2 incremental (v1 → v2):

- cache module `+43..+60` (asset_type identity/path, `market="cn"`, index
  weekly rules, plus the normalize merge that offsets `_frame`);
- `data_collector` `-22` (delete `_normalize_ohlcv_frame` ~37, add import +
  cache_dir threading on 4 methods ~+15);
- `technical_skills` `+10` (generic API names, cache_dir pass-through);
- `technical_analyzer` `+25..+55` (index same-day/write/fallback branches +
  quote plumbing + caller args).

**Judgment: the `+80` batch hard stop is likely tripped** (realistic v2
incremental lands `~+80..+110`; the `+60` net target is not credible because
SC-2 *requires* the index cache, so it cannot be trimmed). **The `+260` total
is right at the edge** (`+179 + ~+80..+110 ≈ +259..+289`); a maximally
disciplined implementation could squeak under, a realistic one exceeds it.
The design's tripwire ("return to design with a replacement/deletion ledger")
is the right mitigation, but as written the stops will probably fire.
Recommend either re-baselining (suggest `~+110` batch / `~+300` total) or
explicitly committing to the tripwire path as the expected outcome, so the
numbers are a meaningful discipline lever rather than a guaranteed halt.
Tests are excluded from the budget but are the largest real growth (+451
lines already vs HEAD); the absence of a test budget should be a conscious
decision.

## Success-contract traceability

- **SC-1** cold write after each successful stock/index source fetch — ✓
  (skill stock write + `_fetch_index_kline` index write; Batch A/B/C fixtures).
- **SC-2** same-day zero stock/index provider request — ✓ mechanism; test
  coverage partial (full-path gap above).
- **SC-3** every indicator/judgment/resonance recomputed from cached raw — ✓
  (raw-only projection; recompute in `build_collection_payload` /
  `analyze_index_trend`).
- **SC-4** fund-flow/concept/news outside cache and outside the
  zero-technical-network assertion — ✓ (`include_optional=False` on cache path).
- **SC-5** cache failure degrades resonance but cannot discard usable stock
  technical or abort — ✓ (write-failure tolerance, invalid→provider continue,
  stale→`None` with resonance `missing`).

## implementation_ready: no

The design is sound and close; no blockers. Before implementation, reflect the
must-fix items in the design: (1) re-baseline the budget or accept the
tripwire; (2) explicitly delete v1 `_frame` and
`data_collector._normalize_ohlcv_frame` (single normalization owner); (3) unify
`cache_enabled`/`index_cache_enabled` naming; (4) specify index
`weekly_data` `None`→`{}` and reject non-empty. Address the full-path
zero-network test gap during Batch C. After those are in the design, it is
ready.
