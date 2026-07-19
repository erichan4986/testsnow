# Technical Analysis v2 Phase 2.1 Correctness Design

## 1. Status And Objective

Phase 2 established one technical judgment owner and a fail-closed renderer. Phase 2.1 fixes four
deterministic correctness defects discovered while comparing the production report with a detailed
three-month technical review:

1. support and resistance are currently discarded together when either side lacks enough touches;
2. volume confirmation is direction-blind and missing volume history receives an optimistic score;
3. a negative MACD histogram is mislabeled as histogram contraction without comparing adjacent bars;
4. momentum overextension and actual price/indicator divergence are conflated, while a zero-call legacy
   helper still contains unsupported `底背离/吸筹` language and a second composite score.

The objective is better technical correctness, not a longer report. Phase 3 structure-path narration,
shock-bar analysis, scenario ladders, anchored VWAP, volume profile, and additional indicators remain out of
scope.

## 2. Locked Boundaries

### Allowed behavior changes

- Technical trend-health values may change because the existing 10-point volume component becomes
  direction-aware and missing data becomes neutral.
- The technical pillar and final recommendation may move only as a downstream consequence of that corrected
  component. Existing weights, score conversion, risk rules, recommendation thresholds, and position rules
  remain unchanged.
- Reports may retain a valid support-only or resistance-only zone.
- A real pivot-aligned divergence may appear as counter-evidence or priority observation, but may never
  upgrade the controlling action by itself.

### Forbidden changes

- No new indicator families, LLM technical memo, event/fundamental input, or external material in the
  technical judgment.
- No changes to target-price formulas, EV, risk scoring, position caps, recommendation thresholds, market
  data collection, Chapter 4, citations, or LLM prompts.
- No `主力出货`, `吸筹确认`, or uncalibrated probability such as `派发70%`.
- No stock, market, or industry-specific hardcode.
- No renderer-side reclassification or second conclusion owner.

## 3. Preconditions

- Technical Analysis Phase 2 is checkpointed separately at `087591d`.
- Two Codex self-review rounds are closed; the revised design is implementation-ready from that baseline.
- The unrelated dirty file
  `docs/agent_workflow/2026-07-15-knowledge-persistence-slimming-6a2-codex-notes.md` remains untouched.
- The implementation baseline is `087591d`, not `cb35b7b` and not the current mixed worktree.

## 4. Design

### 4.1 Independent support and resistance admission

`find_support_resistance()` keeps the existing ATR buckets, touch validation, position validation, and
strength labels. Only the all-or-nothing admission is replaced:

- build a support candidate when valid support touches meet `min_touches`;
- build a resistance candidate when valid resistance touches meet `min_touches`;
- return both `None` only when neither side qualifies;
- preserve whichever side qualifies when the other side is sparse or fails its position check;
- diagnostics record each side's valid touch count and explain `support only`, `resistance only`, `both`, or
  `neither` explicitly.

No one-touch fallback, Fibonacci fallback, latest-low fallback, or relaxed touch threshold is introduced.

### 4.2 Direction-aware volume component

The 10-point `volume_confirmation` weight remains unchanged. `_score_volume_confirmation()` receives the
existing daily structure and evaluates the latest volume against the preceding 20 complete bars, excluding
the current bar from the denominator.

The contracts are explicit:

```text
_volume_window_reliable(df_daily, price_adjustment_validation) -> bool
_score_volume_confirmation(df_daily, daily_structure, volume_reliable) -> (score, evidence, status)
compute_trend_health(..., df_daily, volume_reliable=True) -> trend_health
```

`_volume_window_reliable()` compares the parsed latest corporate-action gap date with the first date/index
of `df_daily.tail(21)`. A gap before the window is reliable for current comparison; a gap inside the window,
or an unparseable gap while `has_gap` is true, is unreliable and fails neutral.

Context is deterministic and based on the latest completed bar:

- `bullish`: latest close return is positive and price is above MA20;
- `bearish`: latest close return is negative and price is below MA20;
- `mixed`: every other combination.

Score matrix:

| Context | ratio >= 1.5 | >= 1.2 | >= 0.8 | < 0.8 |
| --- | ---: | ---: | ---: | ---: |
| bullish | 9 | 7 | 6 | 4 |
| bearish | 1 | 3 | 4 | 5 |
| mixed | 5 | 5 | 5 | 5 |

Rules:

- fewer than 21 valid volume bars, missing/invalid close, or non-positive baseline volume returns neutral
  `5/10` with an explicit `量价数据不足，按中性处理` evidence string;
- if an unadjusted corporate-action gap falls inside the current bar plus the preceding 20-bar baseline,
  volume is not comparable and the component returns neutral `5/10` with status `unreliable`; analyzer
  confidence limitations record `成交量未完成除权等效调整，量价分项按中性处理`;
- the existing trend-health weights and grading thresholds are untouched;
- evidence says `放量上涨确认`, `放量下跌确认`, `缩量下跌`, or `方向混合` rather than directionless `放量`;
- no market-specific volume threshold is added;
- the old monotonic five-day volume `+1/-1` adjustment is deleted because it is direction-blind and would
  create a second scoring rule outside the matrix.

The score continues to represent bullish trend health. A high-volume breakdown therefore lowers rather than
raises that score.

### 4.3 MACD histogram direction

`_compute_base_indicators()` persists the current and previous MACD histogram snapshots. Momentum-extreme
logic classifies the histogram by adjacent-bar direction:

- latest negative and below the previous value: `空头柱扩张`;
- latest negative and above the previous value: `空头柱收缩`;
- latest positive and above the previous value: `多头柱扩张`;
- latest positive and below the previous value: `多头柱收缩`;
- equal or missing values: `方向未确认`.

For an oversold repair warning, only `空头柱收缩` contributes a MACD recovery condition. `空头柱扩张`
is retained as counter-evidence and never increases overextension confidence. The symmetric rule applies to
overbought risk: only `多头柱收缩` contributes exhaustion evidence.

A single `classify_macd_histogram(current, previous)` helper owns these four states. Both the canonical
overextension scan and `_build_advisors()` consume it, so the report table cannot retain the old sign-only
classification after the scan is corrected.

`_compute_base_indicators()` adds `macd_hist_prev` from the already computed canonical MACD series. Pivot
divergence receives RSI14 and MACD histogram series calculated with the existing `_rsi` and `_macd`
functions. Recomputing those short deterministic series once is acceptable; no alternative formula or
third-party indicator implementation is added.

### 4.4 Separate momentum extreme from real divergence

The current `detect_boll_overextension()` behavior is split into explicit runtime contracts:

- `overextension_scan`: `{family: momentum_extreme, type, confidence, matched, total, evidence, missing,
  action}` from BOLL position, RSI extreme, and direction-correct MACD exhaustion;
- `divergence_scan`: `{family: pivot_divergence, type, confidence, matched, total, pivots, evidence, missing,
  action}` from confirmed pivot-aligned price versus RSI/MACD divergence only.

The existing public `detect_boll_overextension()` remains a thin compatibility alias to the canonical
momentum-extreme function during this batch. It never emits pivot-divergence labels. Analyzer runtime stores
the result only in `overextension_scan`; `divergence_scan` is populated only by `detect_pivot_divergence()`.
Compatibility must not recreate a second selector or score.

#### Confirmed swing contract

A shared `confirmed_swing_indices()` helper in `technical_structure.py` owns left/right confirmed swing
selection. `detect_trend_structure_health()` reuses it, replacing its local duplicate loop.

`detect_pivot_divergence()` uses the existing config keys:

- `lookback=80`;
- `swing_left=3`;
- `swing_right=3`;
- `min_matched=2` of three conditions.

It adds three generic keys to the same `technical.divergence` block:

- `max_signal_age=10` bars;
- `price_tolerance_pct=0.01`;
- `price_atr_multiplier=0.5`.

The price relation is material only when its absolute change is at least
`max(price_tolerance_pct, price_atr_multiplier * ATR14_at_second_pivot / second_pivot_close)`. These values
reuse the established structure-health materiality defaults rather than introducing stock-specific tuning.
The second pivot age is `latest_index - second_pivot_index` and must be no more than `max_signal_age` after
right-side confirmation.

Bullish divergence requires:

1. the two most recent confirmed price lows form a material lower low;
2. RSI at the second low is strictly higher;
3. MACD histogram at the second low is strictly higher.

Condition 1 is mandatory and at least one of conditions 2/3 must pass. Bearish divergence is symmetric for
confirmed highs. The latest confirmed pivot must be the most recent qualifying pivot inside the configured
lookback and pass `max_signal_age`; no unconfirmed edge bar is used.

Output contains pivot dates, prices, RSI values, MACD histogram values, matched count, evidence, and missing
conditions. It uses `底背离观察` / `顶背离观察`, never `吸筹确认` or `派发确认`.

Adjustment-quality caps already applied to the old scan are applied independently to both canonical scans.
Raw data with an unresolved corporate-action gap cannot produce a medium/high-confidence divergence.

### 4.5 Single owner and projection

`technical_state_machine._interpretation()` remains the only evidence-priority owner:

- overextension contributes `momentum_extreme` counter-evidence;
- real divergence contributes `pivot_divergence` counter-evidence or priority observation;
- neither signal changes `trend.state`, `action.state`, target display mode, risk score, or position directly;
- bearish primary evidence remains controlling when an oversold or bullish-divergence signal exists.

Priority order is fixed:

1. false breakout / false rebound;
2. confirmed pivot divergence;
3. momentum overextension;
4. BIAS extreme.

The counter-evidence limit remains two. Pivot divergence is admitted before overextension so a stronger
structure-aligned signal is not displaced by a generic extreme reading. Identical evidence text is emitted
once.

For old cached resonance payloads that contain only `divergence_scan`, the family field controls routing.
Missing or unknown family is treated as a generic low-confidence observation and cannot receive a formal
pivot-divergence label. No payload is inferred to be a real divergence from its Chinese `type` text alone.

`technical_judgment.v1` remains the core schema, but interpretation adds
`signal_contract: technical_signal_contract.v2.1`. Core validation remains backward compatible for
recommendation/risk consumers. `_valid_interpretation()` requires the new signal contract; therefore
`ensure_technical_judgment()` rebuilds stale interpretation from current resonance when structural inputs
exist. Without structural inputs it returns a valid core-only copy rather than trusting stale evidence or
invalidating the controlling action.

The renderer only projects the resulting judgment. No renderer algorithm change is required.

### 4.6 Legacy deletion

Delete zero-call `multi_indicator_resonance()` and its unused imports/exports. This removes:

- the unsupported five-day-slope `底背离/吸筹迹象` wording;
- a hidden 0-10 composite score;
- duplicated MACD/RSI/BOLL/OBV classification logic.

## 5. Data Flow

```text
adjusted OHLCV
  -> base indicator series/snapshot
  -> independent support/resistance zones
  -> direction-aware volume component -> trend health
  -> overextension scan + confirmed pivot divergence
  -> technical resonance
  -> single technical judgment interpretation
  -> renderer projection
```

## 6. Files And Ownership

Expected runtime scope:

- `scripts/utils/reporter/technical_structure.py`
- `scripts/utils/reporter/technical_patterns.py`
- `scripts/utils/reporter/technical_analyzer.py`
- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/technical_config.py`

Expected tests:

- `tests/reporter/test_support_resistance.py`
- `tests/reporter/test_trend_health.py`
- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_boll_overextension.py`
- `tests/reporter/test_corporate_action_adjustment.py`
- a focused pivot-divergence test file if keeping the existing files would mix responsibilities.

Scoring engine, renderer, collectors, report assembly, and report-quality gates are not modified unless
Round 1 identifies a correctness blocker that cannot be handled within this scope.

## 7. Required Tests

### Support/resistance

- both sides qualify;
- only support qualifies and remains visible;
- only resistance qualifies and remains visible;
- neither qualifies and diagnostics show both counts;
- a candidate on the wrong side of current price is rejected without deleting a valid opposite side.

### Volume and trend health

- high volume in bullish context scores above neutral;
- high volume in bearish context scores below neutral and says `放量下跌确认`;
- the same ratio in bullish and bearish contexts produces different scores;
- a positive bar below MA20 and a negative bar above MA20 are mixed rather than forced into a direction;
- missing/short history returns `5`, never `8`;
- baseline excludes the current bar;
- an unadjusted corporate-action gap inside the 21-bar comparison window returns neutral and adds a
  confidence limitation; a gap outside that window does not suppress current volume evidence;
- an unparseable latest gap with `has_gap=true` fails neutral;
- monotonic five-day volume changes do not alter the matrix score;
- existing weights and grade thresholds remain identical;
- scoring-engine contract accepts the corrected trend-health value without threshold changes.

### MACD and overextension

- negative expanding histogram does not count as oversold recovery;
- negative contracting histogram does count as recovery;
- positive expanding histogram does not count as overbought exhaustion;
- equal/missing previous histogram fails closed;
- BOLL+RSI still produce a medium extreme warning without MACD confirmation;
- advisor MACD state and overextension evidence use the same histogram classification.

### Pivot divergence

- confirmed lower price low plus higher RSI produces bullish divergence;
- confirmed higher price high plus lower RSI produces bearish divergence;
- same-direction price and momentum returns no divergence;
- a price change below the materiality threshold returns no divergence;
- one momentum condition without the mandatory price relation returns no divergence;
- an unconfirmed right-edge low/high is ignored;
- a confirmed but stale pivot beyond `max_signal_age` is ignored;
- raw unresolved ex-right gap caps/suppresses the signal;
- bearish trend plus bullish divergence remains `risk_control` and treats divergence only as counter-evidence.
- pivot divergence outranks generic overextension when both are present, while false-breakout/rebound keeps
  existing top priority.

### Cache and compatibility

- new judgments contain `interpretation.signal_contract=technical_signal_contract.v2.1`;
- old v1 core action/trend remains valid for recommendation and risk consumers;
- old or missing interpretation contract is rebuilt when resonance inputs are available;
- old interpretation is removed rather than rendered when only a core judgment is available;
- a compatibility `detect_boll_overextension()` call returns only `family=momentum_extreme`.

### Deletion and regression

- no runtime reference to `multi_indicator_resonance` remains;
- no runtime text contains `吸筹迹象`;
- the old overextension fixture continues to assert that BOLL/RSI/MACD extremes alone never use
  `底背离` / `顶背离`; separate pivot fixtures prove when those labels are permitted;
- focused technical tests, scoring/risk/recommendation contracts, full offline suite, CI grep gates, and
  `git diff --check` pass.

## 8. Failure Modes And Guards

| Failure mode | Observable symptom | Guard |
| --- | --- | --- |
| single valid zone still discarded | report says no levels despite repeated touches | support-only/resistance-only fixtures |
| bearish breakdown receives positive volume score | health rises after a high-volume selloff | same-ratio direction test |
| missing volume remains optimistic | short history gets 8/10 | explicit neutral fallback test |
| split-adjusted price uses raw pre-split volume | false volume spike changes health | in-window corporate-action fixture |
| negative MACD called contraction | expanding negative bars strengthen repair warning | adjacent histogram fixtures |
| advisor and scan disagree on MACD | table says decay while scan says expansion | shared-classifier identity test |
| edge-bar look-ahead | latest unconfirmed low creates divergence | right-edge negative test |
| overextension called divergence | BOLL/RSI extreme emits `底背离` | schema/text assertions |
| divergence upgrades action | bearish judgment changes from risk control | state-machine precedence test |
| stale v1 interpretation survives | old false divergence prose remains after upgrade | signal-contract cache tests |
| corporate action creates false signal | raw gap emits trusted divergence | adjustment-cap integration test |
| hidden second score survives | dead helper still emits composite score | symbol audit |

## 9. Budget And Stop Conditions

- Target runtime delta: net `+90` lines after deleting the legacy helper and duplicate swing loop.
- Hard stop: net `+140` across the five runtime files relative to the Phase 2 checkpoint.
- Stop if implementation needs renderer classification, scoring-engine threshold changes, a new data source,
  market-specific rules, or report-specific hardcode.
- Stop if formal fixtures show a recommendation change that cannot be explained solely by the corrected
  volume component.
- Do not generate formal reports until code and downstream gates pass.

## 10. Acceptance

Code acceptance requires all focused/downstream/full gates and a symbol audit. Formal acceptance then
regenerates Zhongji and Fudan. Lexin is added only when a current locally cached input is available; the GPT
sample is not accepted as source data and is not used as a golden numeric fixture.

Formal acceptance records each stock's pre/post trend-health score and volume-component score. Any final
recommendation change must be traceable to that corrected component and still obey existing recommendation
thresholds; otherwise the batch stops.

## 11. Design Delta

- **Accepted:** direction-aware volume may change trend health; support/resistance sides are admitted
  independently; MACD uses adjacent-bar direction; overextension and pivot divergence are separate; dead
  legacy composite scoring is deleted.
- **Rejected:** indicator expansion, `70/30` washout/distribution probability, inferred main-force intent,
  renderer-side analysis, and copying the supplied Lexin numbers into fixtures.
- **Deferred:** structure-path timeline, shock-bar anatomy, scenario ladder, CMF/ADL, anchored VWAP, volume
  profile, event attribution, and historical calibration.
- **Review status:** Round 1 and Round 2 must-fix findings are closed. No separate Claude design review is
  pending.
