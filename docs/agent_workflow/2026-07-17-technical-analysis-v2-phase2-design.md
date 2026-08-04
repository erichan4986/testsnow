# Technical Analysis v2 Phase 2 Judgment Projection and Readability Design

## 1. Status

- Status: locked after three Codex self-review rounds; the user explicitly waived Claude review.
- Phase 1 remains the accepted calculation and decision baseline.
- Phase 2 changes only the technical judgment state machine and technical report projection.
- It does not change indicator formulas, score/risk calculations, target-price formulas, recommendation
  thresholds, market-data collection, Chapter 4, or any LLM prompt.
- Hong Kong market data remains a manual-input concern and is not part of this batch.

## 2. Why Phase 2 Is Needed

Phase 1 established `technical_judgment.v1` as the single contract for trend, target confidence, execution,
and action. The final technical chapter still has a second conclusion owner, however:

- `TechnicalRenderer._build_conclusion()` reclassifies trend weakness from raw `trend_state` and health;
- `TechnicalRenderer._pick_priority_signal()` independently ranks raw warning modules;
- raw `structure_health`, `channel_status`, BIAS, divergence, market resonance, and sell assessment are
  rendered side by side without stating which evidence controls the conclusion;
- the full renderer inserts a sell assessment and the compact body prints it again;
- target status is rendered from `display_mode` plus the raw English `reason_code`, which can produce
  statements such as `当前目标被阻断：structure_observation`;
- missing market/sector data produces a visible placeholder analysis instead of a concise limitation.

The 20260717 reports expose the consequences:

1. Zhongji and Fudan both say `下降趋势 / 破坏期`, while local structure modules say `低点走平` or
   `低点抬升 / 上升趋势结构健康`. These may coexist as a main bearish regime and a counter-trend repair
   clue, but the report currently presents them as equal conclusions.
2. A confirmed box breakdown, an oversold BIAS reading, a generic divergence warning, and the final action
   are displayed as separate blocks without evidence precedence.
3. `structure_observation` is described as blocked even though observation and blocking have different
   meanings.
4. Support/resistance diagnostics repeat raw extrema counts and may reuse a support-specific reason under
   the resistance heading.
5. The chapter is long but the actionable answer -- regime, controlling evidence, counter-evidence,
   confirmation, invalidation, and current action -- is difficult to scan.

This is an interpretation and projection problem. Dropping source data or adding more indicators would not
solve it.

## 3. Considered Approaches

### A. Renderer-only wording cleanup

Remove duplicate blocks and shorten prose in `technical_renderer.py`. This is small, but the renderer would
remain a second judgment owner and contradictions would return as soon as raw modules disagree. Rejected.

### B. Add a second `TechnicalViewModel` module

Create a separate read-model that reconciles raw signals after the state machine. This creates another
decision boundary and requires a broader cache/consumer contract. Rejected.

### C. Add an interpretation projection to the existing judgment

The existing state machine classifies raw modules into controlling evidence, counter-evidence, conditions,
market context, and target explanation. The renderer only formats this projection and retains detailed
numeric diagnostics where useful. This keeps one owner and is the selected approach.

## 4. Locked Ownership and Compatibility

### 4.1 One decision owner

`build_technical_judgment()` remains the only owner of:

- reconciled trend regime;
- execution and action state;
- evidence precedence;
- whether a local signal confirms or merely counters the main regime;
- the target explanation state;
- the single short-term observation shown prominently.

The renderer may format numbers and tables, but it must not infer a new action, rank warnings, or decide
whether evidence is bullish or bearish.

### 4.2 Additive v1 contract

Keep `schema: technical_judgment.v1` and the existing `trend`, `target`, `action`, and `limitations` fields so
recommendation and dashboard consumers require no changes. Add one field:

```python
{
    "interpretation": {
        "timeframe_alignment": "aligned_up|aligned_down|daily_break_weekly_range|daily_repair_weekly_weak|mixed|unknown",
        "headline": str,
        "primary_evidence": [{"code": str, "text": str}],
        "counter_evidence": [{"code": str, "text": str}],
        "confirmation_conditions": [str],
        "invalidation_conditions": [str],
        "priority_observation": {"code": str, "label": str, "detail": str} | None,
        "market_context": {
            "status": "ready|partial|unavailable",
            "summary": str,
        },
        "target_message": {
            "state": "ready|pending|observe|blocked|invalid|unavailable",
            "text": str,
        },
        "change": {
            "state": "improving|deteriorating|unchanged|unknown",
            "previous_stage": str,
            "current_stage": str,
        },
    }
}
```

New judgments always contain a complete `interpretation`. Existing valid v1 caches remain acceptable to
non-renderer consumers. `ensure_technical_judgment()` follows this exact order:

1. valid v1 with `interpretation` -> return unchanged;
2. valid core v1 without `interpretation` plus structural `resonance`/`price_target` -> rebuild;
3. valid core v1 without `interpretation` and without structural inputs -> return the core judgment, which
   may only be rendered as a minimal core summary from its existing `trend`, `target`, and `action` fields;
4. invalid judgment -> rebuild from structural inputs or produce the existing unavailable fail-closed
   judgment.

It must not invent interpretation evidence from cached Chinese prose. `is_valid_technical_judgment()` keeps
the core compatibility contract but also rejects known producer-status/reason contradictions. When an
`interpretation` key is present, it must validate the enum values, list/object shapes, display budgets
(`primary_evidence <= 3`, `counter_evidence <= 2`, `confirmation_conditions <= 2`) and required localized
text. A malformed additive projection invalidates the cache instead of being partially trusted.

Structural rebuild eligibility is explicit: at least one of `trend_state`, `trend_health`, `invalidation`,
`weekly_background`, `daily_structure`, `market_resonance`, or a non-empty `price_target` must be present.
The mere presence of the cached `judgment` object inside `resonance` is not a rebuild signal.

For a valid core-only cache, the renderer may show the existing action summary and safe target message, but
must omit primary/counter evidence, market context, and short-term observation. It must never fall back to
`_build_conclusion()`, raw warning ranking, or raw target reason prose.

## 5. Deterministic Interpretation Rules

### 5.1 Timeframe alignment

The state machine consumes existing `trend.state`, `trend_state`, `weekly_background`, and `daily_structure`.
It does not recalculate MA values or indicators.

Priority:

1. hard invalidation or `trend.state == invalid` -> controlling breakdown evidence;
2. `trend.state == down` -> controlling bearish evidence;
3. `trend.state == transition` -> controlling deterioration/repair evidence according to existing stage;
4. `strong_up` / `weak_up` -> controlling constructive evidence;
5. `range` -> controlling range evidence;
6. missing structural inputs -> unknown and fail closed.

Weekly normalization is closed: `单边上涨 -> up`, `单边下跌 -> down`, `震荡 -> range`, and every other
value -> `unknown`. Daily posture is likewise a closed read of existing categorical fields:

- invalidation `broken` or `price_vs_ma60 == 跌破` -> `break`;
- `price_vs_ma20 == 站上` and `ma20_direction == 向上` -> `constructive`;
- `price_vs_ma20 == 跌破` or `ma20_direction == 向下` -> `weak`;
- otherwise -> `unknown`.

No MA value, distance, or new threshold is recalculated. `timeframe_alignment` describes, but never
overrides, the accepted `trend.state`:

- weekly up plus `constructive` daily posture and constructive judgment -> `aligned_up`;
- weekly down plus `weak` or `break` daily posture and `down/invalid` judgment -> `aligned_down`;
- weekly range plus `weak` or `break` daily posture and `down/invalid` judgment -> `daily_break_weekly_range`;
- weekly down plus `constructive` daily posture and a non-down judgment -> `daily_repair_weekly_weak`;
- other opposing combinations -> `mixed`;
- insufficient inputs -> `unknown`.

### 5.2 Evidence precedence

At most three primary and two counter-evidence items are selected in fixed order. This is a display budget,
not a data deletion rule; all raw technical modules remain in `resonance`.

Primary evidence order:

1. hard invalidation / MA60 structural break;
2. confirmed channel or box break in the same direction as the main regime;
3. weekly background and daily MA structure;
4. trend-health grade and score;
5. ready market/sector resonance that confirms the regime.

Stable primary codes are `hard_invalidation`, `directional_channel_break`, `timeframe_structure`,
`trend_health`, and `market_confirmation`.

Counter-evidence order:

1. `structure_health` that opposes the main regime;
2. bottom-region evidence;
3. oversold/overbought BIAS or divergence that opposes the main regime;
4. market resonance that opposes the stock regime.

Stable counter codes are `local_structure_repair`, `bottom_watch`, `momentum_extreme`, and
`market_divergence`.

Direction admission is closed and uses only existing structured fields:

- under `down/invalid`, `structure_health.is_healthy is True`, a non-`none` bottom signal, BIAS
  `direction == low`, or a specific `超卖预警` may be counter-evidence;
- under `strong_up/weak_up`, `structure_health.is_healthy is False`, BIAS `direction == high`, or a specific
  `超买预警` may be counter-evidence;
- under `transition/range/unknown`, these modules are not promoted to counter-evidence because their
  direction is not decisive enough; they remain available in raw diagnostics.

The channel module is primary only when `breakout_status` contains `向下` for `down/invalid` or `向上` for
`strong_up/weak_up`. It is never used to change the accepted regime.

A counter item must be framed as a local repair/risk clue and cannot change `trend.state`, `action.state`,
position constraints, score, risk score, or target mode. For example, `低点抬升` during `down/invalid` is
rendered as `局部低点抬升，但尚不足以改变破坏期判断`, never as `上升趋势结构健康`.

### 5.3 Conditions

- `confirmation_conditions` reuse existing trigger checks and structural fields. They may state that price,
  trend, volume, or momentum remains pending, but cannot create a new threshold.
- `invalidation_conditions` reuse the existing soft warning, hard invalidation, and stop/structure fields.
- Conditions are deduplicated by exact normalized text and preserve fixed priority.
- No price, ADX, volume-ratio, ATR, support, resistance, or target formula is recalculated here.

### 5.4 Priority observation

The generic renderer ranking is deleted. The state machine emits zero or one short-term observation:

1. confirmed false breakout/rebound with a concrete reason;
2. medium-or-higher divergence with a specific type;
3. severe BIAS extreme;
4. otherwise `None`.

Generic labels such as `单一预警`, empty details, or low-confidence placeholder observations are not
promoted. Short-term observations never override the medium-term regime or action.

The exact current-value gates are: false breakout/rebound needs non-empty `reason`; divergence needs
`type` other than `单一预警` and `confidence` in `{中度, 强烈}`; BIAS needs `level == 严重`. No numeric
indicator is recomputed.

Stable priority codes are `false_breakout`, `false_rebound`, `divergence`, and `bias_extreme`.

### 5.5 Market context

- `ready`: `state != 未知`, at least one evidence item, and empty `missing`;
- `partial`: `state != 未知`, at least one evidence item, and non-empty `missing`;
- `unavailable`: no usable comparison evidence.

Only `ready` and `partial` are rendered as analysis. `unavailable` is retained in judgment limitations but
the report does not print an empty table or `本次共振分析仅作占位` block. The state machine appends exactly
one deduplicated limitation `市场/行业共振数据不足` when it derives `unavailable`.

### 5.6 Target status consistency and wording

The state machine validates the existing producer status/reason pair before deriving execution/action:

| Reason family | Allowed producer status |
| --- | --- |
| `target_ready` | `ready` |
| `weekly_range`, `structure_observation`, `risk_plan_unavailable` | `observe` |
| `opposing_macd_expansion`, `risk_reward_below_minimum` | `blocked` |
| `timeframe_direction_conflict`, `pattern_direction_conflict` | `invalid` |
| `insufficient_daily_data`, `insufficient_weekly_data`, `structure_unavailable`, `invalid_atr`, `untrusted_or_malformed_judgment`, `target_status_conflict`, `unknown_target_status` | `unavailable` |

An internally inconsistent known pair fails closed to
`producer_status=unavailable / reason_code=target_status_conflict`. An unknown reason code fails closed to
`producer_status=unavailable / reason_code=unknown_target_status`. The validator applies the same matrix to
cached judgments, so a cached `blocked/structure_observation` pair cannot bypass rebuilding. Reason codes
are never printed verbatim.

`target_message` is derived from the validated status, execution state, confidence, and display mode:

- observation -> `当前仅形成观察结构，暂不展示精确目标价`;
- pending -> `目标结构存在，但价格、趋势、量能或动量确认尚未齐备`;
- blocked with `opposing_macd_expansion` -> `MACD动能与目标方向相反且仍在扩张，暂不跟随该目标`;
- blocked with `risk_reward_below_minimum` -> `目标结构存在，但当前盈亏比未达到既有门槛`;
- invalid -> `周期或形态方向冲突，当前目标无效`;
- unavailable -> `证据不足，暂不展示目标价`;
- ready -> renderer may display only the target rows already allowed by `display_mode`.

The display-state reducer is closed: `invalid`, `blocked`, `unavailable`, and `observe` producer states win
first; a ready producer with pending execution becomes `pending`; a ready producer with a
`full_targets/core_targets/conditional_range` mode becomes `ready`; a ready bearish `levels_only` result
becomes `observe`; every other combination becomes `unavailable`. This projection never alters the
underlying target calculation or action.

English `reason_code` is retained for diagnostics and downstream contracts but is not shown in report prose.

### 5.7 Headline and confirmation wording

`headline` is produced only by the state machine from the already accepted action/trend state:

| Action state | Headline |
| --- | --- |
| `risk_control` | `中期趋势偏空，风险控制优先` |
| `wait_for_entry` | `趋势结构存在，但当前入场条件未满足` |
| `wait_for_confirmation` | `技术信号尚待确认，暂不提高仓位` |
| `follow` | `趋势与确认条件一致，可继续跟踪` |
| `unavailable` | `技术证据不足，维持观察` |

The renderer may append existing trend label, health score, and analysis-confidence label, but must not
reword the conclusion or derive an alternative action.

`confirmation_conditions` has a closed admission rule:

- only a bullish `ready` or `observe` target may contribute existing trigger-check details;
- include at most two non-`pass` checks in fixed `price, trend, volume, momentum` order;
- a target without an applicable bullish structure contributes only `target_message`, never fabricated
  confirmation conditions;
- structural repair language may be shown only when it already exists in a source field and must carry its
  counter-evidence qualification.

This avoids presenting a bearish/observation target as though it has an actionable upside trigger checklist.

### 5.8 Stage change

`change` consumes only `trend_state.state_changed`, `previous_state`, and current `stage`:

- no previous state or `state_changed is None` -> `unknown`;
- `state_changed is False` -> `unchanged`;
- entering `转弱期` or `破坏期` from any other stage -> `deteriorating`;
- leaving `转弱期` or `破坏期` for any other stage -> `improving`;
- every other stage-to-stage change -> `unknown`.

Phase 2 does not invent an ordinal ranking among `启动期`, `主升期`, `加速期`, `高位钝化期`, and `盘整期`.

## 6. Renderer Contract

### 6.1 Report order

Both compact and full modes start from the same judgment projection:

1. **技术判断**: headline, action, trend health, analysis confidence;
2. **主导证据**: at most three items;
3. **反向线索**: at most two items, only when present;
4. **确认与失效条件**;
5. **趋势与位置**: weekly, daily, volume, volatility, support/resistance, MA20/MA60 and invalidation;
6. optional market context and one short-term observation;
7. indicator/advisor diagnostics;
8. localized target analysis;
9. chart.

The full mode may keep the five-component health table and advisor table. Compact mode may omit those
details. Both modes must use the same headline, evidence precedence, conditions, action, and target message.

The renderer enters this projection path whenever either advanced structural fields are present or a valid
core judgment exists. A valid core-only judgment renders only the safe minimal summary defined in section
4.2. The legacy snapshot path is reserved for payloads with neither advanced structure nor a valid judgment.

### 6.2 Required deletions or replacements

- delete `_build_conclusion()`;
- delete `_pick_priority_signal()`;
- remove duplicate sell-assessment rendering;
- replace `list.insert()`-based full-mode assembly with ordered section composition;
- do not print raw support/resistance extrema diagnostics in the main report;
- do not render unavailable market resonance;
- do not print raw English target reason codes;
- fix unmatched bold markers in the priority block by replacing that block entirely.

Legacy indicator-snapshot rendering remains for truly missing advanced technical data, including manually
unprovided Hong Kong market data. Phase 2 does not attempt to synthesize missing prices.

## 7. Allowed Scope

Runtime:

- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/sections/technical_renderer.py`

Tests:

- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_technical_renderer.py`
- `tests/reporter/test_market_resonance_integration.py` only to replace the obsolete expectation that an
  unavailable market-resonance placeholder must be visible

Workflow design/review/task/notes may be added under `docs/agent_workflow/`.

Forbidden:

- changes to indicator, support/resistance, structure, pattern, target-price, score, risk, EV, or
  recommendation calculations;
- changes to `technical_analyzer.py`, `price_target.py`, `scoring_engine.py`, recommendation/dashboard
  consumers, collectors, config, or source APIs;
- LLM technical memo or prompt changes;
- Chapter 4, citations, data, knowledge, reports, or production cache changes;
- stock-specific thresholds or wording rules.

## 8. Required Tests

| Requirement | Required RED test |
| --- | --- |
| One owner for final conclusion | runtime symbol audit finds no `_build_conclusion` or `_pick_priority_signal` |
| Broken regime controls healthy local structure | down/invalid + `低点抬升` keeps risk-control headline and places the latter in counter-evidence |
| Weekly range plus daily break is explicit | alignment is `daily_break_weekly_range`, not aligned bearish or generic mixed |
| Daily posture is formula-free | existing categorical `price_vs_ma20`, `price_vs_ma60`, and `ma20_direction` fixture determines alignment without MA values |
| Oversold cannot upgrade action | severe negative BIAS under down regime remains `risk_control` |
| Constructive regime preserves bearish local warning as counter-evidence | strong/weak up does not silently discard a concrete opposing warning |
| Conditions reuse existing checks | pending checks appear once; no new numeric threshold is introduced |
| Generic warning is not promoted | `单一预警/轻度` produces no priority observation |
| Concrete warning is promoted once | specific medium divergence or confirmed false breakout appears once |
| Directional warning admission is closed | `超卖预警` is counter-evidence only under down/invalid, while `单一预警` remains raw-only |
| Missing market context is hidden | unavailable resonance produces no market table or placeholder prose |
| Ready/partial market context remains visible | real state, impact and relative strength render without recomputation |
| Observation is not blocking | `observe/structure_observation` renders observation wording, not `被阻断` |
| Known status/reason mismatch fails closed | blocked + `structure_observation` becomes `target_status_conflict/unavailable` |
| Reason codes are not user-facing | rendered target prose contains no snake_case reason code |
| No duplicate sell assessment | full output contains the assessment at most once |
| Support diagnostics are concise | raw valley/peak counts and support-specific reason are absent under pressure |
| Full and compact share judgment | both modes have identical headline/action/target-message semantics |
| Existing v1 cache is safely upgraded | valid core judgment without interpretation rebuilds when resonance is supplied |
| Core-only v1 cache stays safe | renderer shows minimal core summary and does not revive raw warning ranking |
| Missing technical data remains fail closed | HK/manual-data fixture stays on legacy snapshot and does not invent a regime |

Run focused state-machine, renderer, market-resonance integration, recommendation, dashboard, report-quality,
and technical-skill contract suites. Then run the non-network technical suite, `tools/ci_grep_gates.sh`, and
`git diff --check`.

## 9. Failure Modes and Stop Conditions

| Failure mode | Manifestation | Required response/test |
| --- | --- | --- |
| Renderer remains a second owner | output action differs from judgment action | symbol audit and paired mode tests |
| Local repair clue upgrades broken regime | `低点抬升` produces follow/wait-to-buy under invalid trend | counter-evidence fixture |
| Status/reason mismatch is trusted | observation is printed as blocker | mismatch fail-closed fixture |
| Missing market data becomes analysis | empty table and placeholder text return | unavailable-market renderer fixture |
| Interpretation duplicates indicator logic | new MA/ADX/volume thresholds appear in state machine | diff audit and exact-value fixtures |
| Additive cache path trusts stale prose | old cache renders an unsupported headline | cache upgrade/fail-closed fixture |
| Compact/full diverge | same judgment yields different action or target state | paired renderer fixture |
| Readability cleanup removes required coverage | weekly/daily/volume/volatility/confidence disappear | report completeness fixture |
| Refactor expands beyond two runtime owners | analyzer/scoring/target/recommendation files change | scope audit; stop |
| Runtime grows instead of replacing duplicate logic | two runtime files net growth exceeds +120 lines | stop and delete old renderer paths |

Runtime target is net-negative because duplicate renderer conclusions and insertion-based assembly are
replaced. Absolute hard stop: combined runtime net growth greater than `+120` lines relative to task start.

## 10. Acceptance Gate

Code-only acceptance requires:

- focused and downstream tests pass;
- no second conclusion/priority owner remains in the renderer;
- no indicator/score/risk/target formula diff exists;
- Zhongji/Fudan-like fixtures produce one controlling regime plus clearly labeled counter-evidence;
- unavailable market context and generic warnings do not occupy report space;
- target observation, blocked, invalid, pending, and unavailable states have distinct localized prose;
- runtime budget, CI grep gates, and whitespace checks pass.

After code acceptance, regenerate Zhongji and Fudan reports locally. Black Sesame is regenerated only when
the user has supplied usable Hong Kong market data; missing HK data is not a Phase 2 blocker.

## 11. Design Delta

- **Accepted:** keep Phase 1 calculations and action enums; add an interpretation projection to the same
  judgment owner; make the renderer a pure projection; local structure and oversold evidence become
  counter-evidence when they oppose the main regime; hide unavailable market placeholders; localize target
  states; remove duplicate/noisy blocks.
- **Rejected:** renderer-only prose patch; a new view-model/state-machine module; LLM technical memo; new
  indicators or thresholds; using external/fundamental material in technical judgment.
- **Deferred:** target formula recalibration, score/risk changes, recommendation policy, historical backtest,
  HK market-data acquisition, and Chapter 4 warnings.
- **Claude review:** explicitly waived by the user after the third Codex self-review. Implementation may
  proceed directly under the locked scope, TDD, runtime budget, and downstream gates above.
