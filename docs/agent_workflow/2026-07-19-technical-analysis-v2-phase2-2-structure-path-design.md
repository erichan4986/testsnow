# Technical Analysis v2 Phase 2.2 Structure Path Design

## 1. Status And Goal

- Status: proposed after Phase 2.1 formal-report acceptance.
- Phase 2.1 is checkpointed at `fdd0941` and remains the correctness baseline.
- The goal is to turn the technical chapter from a current-state snapshot into a concise path narrative:
  how price reached the current regime, whether the latest bar is an abnormal shock, and which existing
  structural levels distinguish a reflex rebound from an actual trend repair.
- This phase does not make the report longer by adding indicator inventories. It replaces disconnected
  diagnostics with three bounded projections: structure path, terminal-bar anatomy, and scenario ladder.

## 2. Why This Is The Next Batch

The accepted reports now classify volume direction, MACD histogram direction, support/resistance, momentum
extremes, and pivot divergence correctly. They still answer mostly "what is true now". A professional
technical note also needs to answer:

1. Which confirmed swings formed the current path?
2. Did the latest bar materially change the path or merely extend it?
3. Which existing levels would mark rebound, repair, trend-turn observation, or further failure?

The gap is sequencing and conditional interpretation, not a shortage of indicators. CMF/ADL, anchored VWAP,
volume profile, extra oscillators, and uncalibrated washout/distribution probabilities remain deferred.

## 3. Considered Approaches

### A. Renderer-only chronology

Let the renderer read raw OHLCV and write a timeline. Rejected because it recreates a trend owner in the
renderer and makes cache and compact/full output inconsistent.

### B. State-machine-only reconstruction

Infer a path from current `trend_state`, support/resistance, and prose summaries. Rejected because those
snapshots do not retain ordered pivot facts and would encourage invented chronology.

### C. Analyzer facts plus state-machine interpretation

The analyzer emits ordered, source-derived structural facts. The existing state machine selects their
meaning under the controlling regime. The renderer formats the accepted projection. Selected because it
preserves one decision owner and keeps every displayed date/price auditable against OHLCV.

## 4. Locked Boundaries

### 4.1 Allowed changes

- Derive a bounded path from confirmed swing highs/lows and the latest daily-row close.
- Describe the latest daily row when it qualifies as an abnormal terminal shock.
- Build a scenario ladder from existing MA, support/resistance, and invalidation values.
- Add an additive `technical_signal_contract.v2.2` interpretation projection and invalidate stale v2.1
  interpretation while retaining a valid core judgment.
- Replace redundant renderer diagnostics when the new projection carries the same information.

### 4.2 Forbidden changes

- No score, risk, EV, target-price, position, recommendation, or trigger-threshold change.
- No new market-data source, external/fundamental input, LLM memo, or prompt change.
- No `主力出货`, `吸筹`, `洗盘结束`, or numeric probability attribution.
- No stock, market, or industry-specific hardcode.
- No renderer-side swing detection, shock classification, level selection, or action inference.
- No exact scenario price manufactured from Fibonacci or a new target formula.

## 5. Runtime Contracts

### 5.0 Shared volume context

Phase 2.1 currently calculates the preceding-20 volume baseline inside `_score_volume_confirmation()`. The
terminal-shock helper must not reproduce that calculation. Move the factual calculation to one pure helper
in `technical_structure.py`:

```python
build_volume_context(df_daily, daily_structure, volume_reliable) -> {
    "status": "ready|unreliable|insufficient",
    "ratio": float | None,
    "price_change": float | None,
    "context": "bullish|bearish|mixed|unknown",
}
```

It excludes the current row from the preceding-20 baseline and preserves the accepted Phase 2.1 context
rules. `compute_trend_health(..., volume_context=None)` calls this helper only when no context is supplied;
the analyzer computes it once and passes the same object to trend health and terminal-shock analysis.
`_score_volume_confirmation()` consumes the context object and retains the accepted score matrix and wording.
There is no second volume ratio, direction classifier, or corporate-action decision.

### 5.1 Structure path facts

Add a deterministic helper in `technical_structure.py`:

```python
build_structure_path(df_daily, config) -> {
    "status": "ready|sparse|unavailable",
    "as_of": str,
    "lookback": int,
    "segments": [
        {
            "start_date": str,
            "end_date": str,
            "start_price": float,
            "end_price": float,
            "change_pct": float,
            "bars": int,
            "direction": "up|down|flat",
            "end_kind": "confirmed_high|confirmed_low|latest_close",
        }
    ],
    "pivot_sequence": [{"date": str, "price": float, "kind": "high|low"}],
    "limitations": [str],
}
```

Rules:

1. Use the existing `technical.divergence.lookback`, `swing_left`, and `swing_right` configuration so this
   phase does not create a second pivot taxonomy.
2. Select confirmed highs and lows only through `confirmed_swing_indices()`.
3. Merge both kinds in source order. Consecutive pivots of the same kind collapse to the more extreme price;
   equal prices keep the earlier pivot. This creates one alternating sequence without fuzzy matching.
   A single outside bar can satisfy both strict high and strict low tests; omit both pivots at that index and
   record `dual_extreme_bar_omitted` rather than choosing an arbitrary order.
4. Append the latest row close as `latest_close` only when it is later than the last confirmed pivot. The
   existing daily-collector contract treats report input rows as completed daily bars; this phase does not
   add a market-clock or intraday-finalization guess. The row is never relabeled as a confirmed high or low.
5. A segment is `up` or `down` only when its absolute move clears the existing Phase 2.1 materiality floor:
   `max(price_tolerance_pct, price_atr_multiplier * ATR14_at_segment_end / end_price)`. Otherwise it is
   `flat`.
6. Preserve all qualifying segments in the runtime fact object. The judgment display projection selects at
   most five latest non-flat segments; this is a display budget, not source deletion.
7. Fewer than two confirmed alternating pivots returns `sparse`. Missing/invalid dates, prices, or ATR fail
   closed to `unavailable` or omit only the invalid segment.
   Dates come from a parseable `date` column or `DatetimeIndex` and are normalized to ISO date strings. A
   positional integer index is not presented as a date.
8. The helper emits facts only. It does not say bull market, bear market, double top, distribution, rebound,
   or reversal.

### 5.2 Terminal shock facts

Add a second helper in `technical_structure.py`:

```python
analyze_terminal_shock(df_daily, atr_series, volume_context, config) -> {
    "status": "ready|ordinary|unavailable",
    "direction": "up|down|mixed",
    "date": str,
    "return_pct": float,
    "range_atr_ratio": float,
    "body_range_ratio": float,
    "close_location": float,
    "volume_ratio": float | None,
    "volume_status": "reliable|unreliable|unavailable",
    "facts": [str],
}
```

The latest daily row qualifies as a shock only when all are true:

- valid OHLC and previous close exist;
- true range is at least `1.5 * ATR14`, where ATR14 is calculated through the preceding row and excludes the
  shock row from its own baseline;
- body occupies at least `65%` of the full range;
- close lies in the bottom `20%` for a downside shock or top `20%` for an upside shock.

These generic thresholds live under `technical.structure_path.shock` in `technical_config.py`. They describe
bar abnormality, not a buy/sell trigger. Direction follows close versus open and previous close; conflicting
signs produce `mixed` and are not promoted by the judgment.

Direction is `down` only when close is below both open and previous close, `up` only when it is above both,
and `mixed` otherwise. Zero range, missing previous close, or non-finite OHLC fails closed.

Volume ratio is copied from the shared Phase 2.1 volume context. Unreliable or insufficient volume retains
price anatomy but prints no volume claim and sets `volume_status=unreliable|unavailable`. Missing price/ATR
history returns `unavailable`; an ordinary bar returns `ordinary` without visible report output.

### 5.3 Analyzer ownership

`technical_analyzer.py` computes and stores:

```python
resonance["structure_path"] = build_structure_path(...)
resonance["terminal_shock"] = analyze_terminal_shock(...)
```

Both use the already adjusted daily frame and the same volume-reliability result used by trend health. The
analyzer does not derive action text or scenario meaning.

### 5.4 Scenario ladder and interpretation

`technical_state_machine.py` remains the only interpretation owner. `_interpretation()` changes explicitly
to `_interpretation(resonance, trend, target, action, indicators)`, and `build_technical_judgment()` passes its
existing normalized indicators object. Upgrade the additive contract to
`technical_signal_contract.v2.2` and add:

```python
"structure_path": {
    "status": "ready|sparse|unavailable",
    "summary": str,
    "segments": [{"period": str, "move": str, "meaning": str}],
},
"terminal_event": {
    "status": "shock|ordinary|unavailable",
    "headline": str,
    "facts": [str],
} | None,
"scenario_ladder": {
    "as_of": str,
    "reference_close": float,
    "steps": [
        {
            "role": "near_upside|far_upside|near_downside|far_downside",
            "label": str,
            "condition": str,
            "level": float | None,
            "level_source": "support_zone|resistance_zone|ma20|ma60|hard_invalidation|none",
            "source_field": "value|zone_low|zone_high|none",
            "meaning": str,
        }
    ]
}
```

#### Path interpretation

- Under `down/invalid`, aligned down segments are `下行延续`; an up segment after a confirmed low is
  `反抽/局部修复`; a lower confirmed high followed by a lower confirmed low may be summarized as
  `高点下移、低点下移`.
- Under `strong_up/weak_up`, apply the symmetric wording.
- Under `range/transition/unknown`, use neutral `区间上行段/区间下行段`; do not infer reversal.
- The path summary may explain the accepted regime but never changes `trend.state` or `action.state`.
- At most five segments appear in the interpretation and renderer. Dates, prices, and percentage moves are
  copied from analyzer facts without recalculation.
- `高点下移/抬高` and `低点下移/抬高` compare the latest two confirmed pivots of the same kind and require
  the same materiality floor used for segment direction. Sub-material equality is described as `持平`.

#### Terminal-event interpretation

- A ready downside shock under `down/invalid` is controlling confirmation.
- A ready downside shock under an accepted bullish regime is deterioration evidence, not an automatic state
  flip.
- A ready upside shock is symmetric.
- Mixed, ordinary, unavailable, or corporate-action-contaminated volume is not promoted beyond limitations.
- Wording is factual: `放量长阴且收盘接近日内低位`; never `资金出逃` or `恐慌盘确认`.
- An aligned terminal shock enters primary evidence after hard invalidation and directional channel break,
  before timeframe structure. An opposing shock enters counter-evidence before pivot divergence. Stable
  evidence codes are `terminal_down_shock` and `terminal_up_shock`; the existing list budgets remain three
  primary and two counter items. The event never mutates trend/action state.

#### Scenario ladder

Scenario levels are selected only from values already present in `indicators`, `key_levels`, and
`invalidation`. They are observation levels, not price targets.

For `down/invalid`:

1. `near_upside` / `反抽观察`: nearest valid overhead value from MA20 or resistance-zone low;
2. `far_upside` / `趋势修复`: next distinct overhead value from resistance-zone high or MA60;
3. `near_downside` / `下行延续`: nearest valid downside value from support-zone low or hard-invalidation
   price.

For `strong_up/weak_up`:

1. `near_upside` / `上行延续`: nearest valid overhead resistance-zone low/high;
2. `near_downside` / `第一防线`: nearest valid downside value from MA20 or support-zone high;
3. `far_downside` / `结构失效观察`: next distinct downside value from MA60, support-zone low, or
   hard-invalidation price.

For `range/transition`, emit at most `near_upside` / `区间上沿` at resistance-zone low and
`near_downside` / `区间下沿` at support-zone high. No MA fallback is added to a range when the corresponding
zone is absent.

All values must be on the expected side of current close, sorted monotonically within each direction,
deduplicated within `0.5%`, and retain their source. Missing levels are omitted; the state machine never
fabricates a replacement. `reversal` is not an output enum in this phase. When the `far_upside` bearish
recovery step combines a valid MA60 with a distinct resistance boundary, its meaning may say
`趋势扭转观察条件`, but its role remains geometric and the report cannot declare that a reversal has occurred.

When two sources are within the deduplication tolerance, preserve the earlier source in the explicit priority
order above. `reference_close` is copied from `indicators.close`; `as_of` is copied from the structure path.
Missing/non-finite close yields an empty ladder rather than a positional guess.

### 5.5 Cache and validation

- `_valid_interpretation()` requires `technical_signal_contract.v2.2` and validates all new enums, shapes,
  budgets, finite numeric levels, monotonic order, and localized text.
- Shape validation alone cannot prove a cached price came from the current inputs. Add a context-aware
  `_scenario_levels_match_inputs(interpretation, resonance, indicators)` check in
  `ensure_technical_judgment()`. Every non-null level must equal the value identified by its `level_source`
  and `source_field` after numeric normalization. `scenario_ladder.reference_close` must equal `indicators.close`, and its
  `as_of` must equal the current `structure_path.as_of`. A missing source, mismatched value, wrong side,
  changed close, or changed as-of date invalidates the additive projection and triggers rebuild when
  structural inputs exist.
- A v2.1 interpretation is stale. `ensure_technical_judgment()` rebuilds it when current structural inputs
  exist. A v2.2 interpretation without current provenance inputs is reduced to the valid core judgment rather
  than trusted for path/scenario rendering. This deliberately makes old standalone caches fail closed.
- Core `technical_judgment.v1`, recommendation, risk, and dashboard compatibility remain unchanged.

### 5.6 Renderer projection

`technical_renderer.py` adds three bounded blocks after the controlling evidence and before detailed trend
components:

1. `结构演变`: one summary plus a compact 3-5 row period/move/meaning table;
2. `末端异常K线`: only when `terminal_event.status == shock`;
3. `情景阶梯`: at most three short bullets labeled rebound/repair/failure or their bullish equivalents.

The renderer copies interpretation fields only. It does not read raw daily bars or select levels. Existing
weekly/daily bullet blocks are shortened where they repeat the path summary. Across the three new blocks, the
full renderer may emit at most five path rows, four shock facts, and three scenario bullets. Compact and full
modes must use the same action, path summary, and scenario meaning; compact mode may omit tables but not
substitute a different conclusion.

## 6. Expected Files

Runtime:

- `scripts/utils/reporter/technical_structure.py`
- `scripts/utils/reporter/technical_analyzer.py`
- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/technical_config.py`
- `scripts/utils/reporter/sections/technical_renderer.py`

Tests:

- `tests/reporter/test_technical_structure_path.py` (new)
- `tests/reporter/test_trend_health.py` or a focused terminal-shock test module
- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_technical_renderer.py`
- relevant recommendation/score regression tests

No collector, scoring, target-price, risk, Chapter 4, citation, external producer, or LLM file is allowed.

## 7. Required Tests

### Structure path

1. Confirmed alternating pivots produce source-ordered segments with exact dates and prices.
2. The last `swing_right` bars never become confirmed pivots.
3. Consecutive same-kind pivots collapse to the more extreme point.
4. A same-index dual high/low outside bar is omitted with a limitation.
5. Sub-material moves become flat and are not promoted to the display path.
6. Latest close is terminal observation, never a confirmed pivot.
7. ATR materiality uses only data available through each segment end; malformed dates fail closed.
8. Sparse and malformed frames fail closed.

### Terminal shock

9. A large downside body closing near the low passes; a long-lower-shadow recovery bar does not.
10. The upside case is symmetric; mixed open/previous-close direction is not promoted.
11. Current true range is excluded from its ATR baseline and current volume from its volume baseline.
12. Corporate-action-contaminated volume is not described as confirmation.
13. Insufficient volume suppresses only the volume claim, not valid price anatomy.
14. Ordinary and short-price-history bars remain silent.
15. Trend health and terminal shock consume the same object identity/value for volume ratio and context.

### Judgment and scenarios

16. A bearish path plus downside shock strengthens prose but does not alter the precomputed action.
17. An opposing shock uses counter evidence and cannot flip the action.
18. A counter-trend up segment is labeled repair, not reversal.
19. Scenario prices are a subset of supplied MA/support/resistance/invalidation values.
20. Wrong-side, duplicate, NaN, infinite, and missing levels are omitted with deterministic source priority.
21. Downside, upside, and range ladders use geometric roles, exact localized labels, and monotonic source
    priorities.
22. v2.1 cache rebuilds to v2.2; context-free v2.2 cache returns core-only judgment.
23. A cached level/source, reference-close, or as-of mismatch rebuilds or strips the interpretation.
24. Malformed path/scenario projection invalidates the additive interpretation.

### Renderer and downstream

25. Full renderer shows bounded structure, shock, and scenario blocks with no raw diagnostic dump.
26. Ordinary shock status prints no placeholder block.
27. Compact/full outputs preserve the same controlling action and scenario semantics.
28. Score, risk, target values, recommendation state, and position cap remain identity-equal before/after the
    additive projection for the same accepted core judgment.
29. Zhongji/Fudan fixtures remain internally consistent and report quality gates pass.

## 8. Failure Modes

| Failure | Visible symptom | Guard |
| --- | --- | --- |
| Unconfirmed edge pivot leaks | latest bar is called a new swing high/low | right-edge pivot test |
| Outside bar gets two pivot roles | same date appears as both high and low | dual-extreme omission test |
| Timeline becomes second trend owner | path says reversal while action remains risk control | state/action identity test |
| Shock rule mistakes long lower shadow for breakdown | recovery candle described as long bearish shock | body/close-location negative fixture |
| Shock normalizes itself away | current range inflates its own ATR denominator | shifted-ATR fixture |
| Corporate action inflates volume | split date described as volume confirmation | shared reliability test |
| Volume formula forks again | trend health and shock print different volume ratios | shared-context identity fixture |
| Scenario ladder invents a price | level absent from all accepted inputs | subset identity test |
| Stale cache retains old level | cached MA20 differs from current MA20 | context-aware provenance test |
| Stale cache retains prior day path | cached as-of/close differs from current input | as-of/reference-close fixture |
| Wrong-side levels create nonsense order | bearish recovery level below current close | side and monotonic validation |
| Exact levels are mistaken for targets | scenario block reads as target-price forecast | renderer wording/gate test |
| Stale cache skips new facts | v2.1 interpretation renders without path validation | contract-upgrade fixture |
| Report grows into indicator inventory | duplicate weekly/daily/path prose | renderer budget fixture and report review |

## 9. Verification And Stop Conditions

- TDD order: path facts -> shock facts -> scenario interpretation/cache -> renderer -> downstream identity.
- Run focused tests after each task, then full offline `pytest`, CI grep gates, and `git diff --check`.
- Regenerate fresh Zhongji and Fudan fast-test reports; Hong Kong data remains user-supplied and is not a
  blocker.
- Runtime target: net `+120` lines after replacing redundant renderer diagnostics; hard stop at net `+180`
  across the five allowed runtime files relative to `fdd0941`.
- Stop and return to design if implementation needs a new data source, new indicator family, score/risk/target
  change, stock-specific rule, renderer-side classification, or fabricated scenario level.

## 10. Design Delta

- Accepted: deterministic swing chronology, terminal shock anatomy, and scenario ladder from existing levels.
- Rejected: renderer-only chronology, second view model, indicator expansion, LLM technical memo, and
  washout/distribution probabilities.
- Deferred: composite-top naming, gap-event attribution, CMF/ADL, anchored VWAP, volume profile, historical
  backtest/calibration, and target formula changes.
