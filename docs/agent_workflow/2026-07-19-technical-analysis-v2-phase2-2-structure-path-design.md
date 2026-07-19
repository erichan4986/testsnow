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

### 5.1 Structure path facts

Add a deterministic helper in `technical_structure.py`:

```python
build_structure_path(df_daily, config) -> {
    "status": "ready|sparse|unavailable",
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
8. The helper emits facts only. It does not say bull market, bear market, double top, distribution, rebound,
   or reversal.

### 5.2 Terminal shock facts

Add a second helper in `technical_structure.py`:

```python
analyze_terminal_shock(df_daily, atr_series, volume_reliable, config) -> {
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
- true range is at least `1.5 * ATR14`;
- body occupies at least `65%` of the full range;
- close lies in the bottom `20%` for a downside shock or top `20%` for an upside shock.

These generic thresholds live under `technical.structure_path.shock` in `technical_config.py`. They describe
bar abnormality, not a buy/sell trigger. Direction follows close versus open and previous close; conflicting
signs produce `mixed` and are not promoted by the judgment.

Volume ratio uses the same preceding-20 baseline and corporate-action reliability decision as the accepted
Phase 2.1 volume component. An unreliable volume window retains price anatomy but prints no volume claim and
sets `volume_status=unreliable`. Missing ATR or fewer than 21 daily bars returns `unavailable`; an ordinary
bar returns `ordinary` without visible report output.

### 5.3 Analyzer ownership

`technical_analyzer.py` computes and stores:

```python
resonance["structure_path"] = build_structure_path(...)
resonance["terminal_shock"] = analyze_terminal_shock(...)
```

Both use the already adjusted daily frame and the same volume-reliability result used by trend health. The
analyzer does not derive action text or scenario meaning.

### 5.4 Scenario ladder and interpretation

`technical_state_machine.py` remains the only interpretation owner. Upgrade the additive contract to
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
"scenario_ladder": [
    {
        "state": "rebound|repair|failure|continuation",
        "condition": str,
        "level": float | None,
        "level_source": "support_zone|resistance_zone|ma20|ma60|hard_invalidation|none",
        "meaning": str,
    }
]
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

#### Terminal-event interpretation

- A ready downside shock under `down/invalid` is controlling confirmation.
- A ready downside shock under an accepted bullish regime is deterioration evidence, not an automatic state
  flip.
- A ready upside shock is symmetric.
- Mixed, ordinary, unavailable, or corporate-action-contaminated volume is not promoted beyond limitations.
- Wording is factual: `放量长阴且收盘接近日内低位`; never `资金出逃` or `恐慌盘确认`.

#### Scenario ladder

Scenario levels are selected only from values already present in `indicators`, `key_levels`, and
`invalidation`. They are observation levels, not price targets.

For `down/invalid`:

1. `rebound`: nearest valid overhead value from MA20 or resistance-zone low;
2. `repair`: next distinct overhead value from resistance-zone high or MA60;
3. `failure`: nearest valid downside value from support-zone low or hard-invalidation price.

For `strong_up/weak_up`:

1. `continuation`: nearest valid overhead resistance-zone low/high;
2. `repair`: nearest valid downside value from MA20 or support-zone high, framed as the first defense;
3. `failure`: next distinct downside value from MA60, support-zone low, or hard-invalidation price.

For `range/transition`, emit at most `continuation` at resistance-zone low and `failure` at support-zone high.
No MA fallback is added to a range when the corresponding zone is absent.

All values must be on the expected side of current close, sorted monotonically within each direction,
deduplicated within `0.5%`, and retain their source. Missing levels are omitted; the state machine never
fabricates a replacement. `reversal` is not an output enum in this phase. When the farthest bearish recovery
step combines a valid MA60 with a distinct resistance boundary, its meaning may say `趋势扭转观察条件`, but
the state remains `repair` and the report cannot declare that a reversal has occurred.

### 5.5 Cache and validation

- `_valid_interpretation()` requires `technical_signal_contract.v2.2` and validates all new enums, shapes,
  budgets, finite numeric levels, monotonic order, and localized text.
- A v2.1 interpretation is stale. `ensure_technical_judgment()` rebuilds it when current structural inputs
  exist; otherwise it returns the valid core judgment without rendering invented path/scenario content.
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
4. Sub-material moves become flat and are not promoted to the display path.
5. Latest close is terminal observation, never a confirmed pivot.
6. Sparse and malformed frames fail closed.

### Terminal shock

7. A large downside body closing near the low passes; a long-lower-shadow recovery bar does not.
8. The upside case is symmetric.
9. Current volume is excluded from its baseline.
10. Corporate-action-contaminated volume is not described as confirmation.
11. Ordinary and short-history bars remain silent.

### Judgment and scenarios

12. A bearish path plus downside shock strengthens prose but does not alter the precomputed action.
13. A counter-trend up segment is labeled repair, not reversal.
14. Scenario prices are a subset of supplied MA/support/resistance/invalidation values.
15. Wrong-side, duplicate, NaN, infinite, and missing levels are omitted.
16. Downside, upside, and range ladders follow their exact source-priority rules and remain monotonic.
17. v2.1 cache rebuilds to v2.2; core-only cache remains fail closed.
18. Malformed path/scenario projection invalidates the additive interpretation.

### Renderer and downstream

19. Full renderer shows bounded structure, shock, and scenario blocks with no raw diagnostic dump.
20. Ordinary shock status prints no placeholder block.
21. Compact/full outputs preserve the same controlling action and scenario semantics.
22. Score, risk, target values, recommendation state, and position cap remain identity-equal before/after the
    additive projection for the same accepted core judgment.
23. Zhongji/Fudan fixtures remain internally consistent and report quality gates pass.

## 8. Failure Modes

| Failure | Visible symptom | Guard |
| --- | --- | --- |
| Unconfirmed edge pivot leaks | latest bar is called a new swing high/low | right-edge pivot test |
| Timeline becomes second trend owner | path says reversal while action remains risk control | state/action identity test |
| Shock rule mistakes long lower shadow for breakdown | recovery candle described as long bearish shock | body/close-location negative fixture |
| Corporate action inflates volume | split date described as volume confirmation | shared reliability test |
| Scenario ladder invents a price | level absent from all accepted inputs | subset identity test |
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
