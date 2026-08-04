# Technical Analysis v2 Phase 2.3A Structure Diagnosis Design

Date: 2026-07-23
Baseline: `f17b859`
Status: two Codex self-review rounds complete; ready for implementation planning after user approval

## 1. Goal

Improve the technical chapter from a sequence of alternating swing legs into an auditable structural
diagnosis. The report should explain whether the latest leg is trend continuation, a counter-trend rebound,
a pullback inside an uptrend, range movement, or mixed transition.

This batch does not add indicators or subjective chart-pattern names. It keeps every date and price traceable
to the adjusted OHLCV input and leaves score, risk, target price, position, and recommendation unchanged.

## 2. Current Defects

The accepted v2.2 path has three remaining quality problems:

1. `_path_interpretation()` labels each leg only from its direction and the controlling trend. It does not
   compare the latest two confirmed highs and lows, so it cannot distinguish a descending structure from a
   single pullback.
2. A triggered invalidation can enter `primary_evidence` through the generic future condition
   `周线收盘跌破MA10，或日线有效跌破MA60` instead of the actual observed message and price.
3. The renderer repeats the same structural fact in both `结构演变` and `局部趋势结构（辅助）`, while the
   structure table omits the source prices. Its radar summary also calls the relatively highest component
   `最强` even when every component is weak.

## 3. Considered Approaches

### A. Renderer-only narrative synthesis

Rejected. It would make the renderer infer pivot relationships and create a second technical decision owner.

### B. Named-pattern detector

Rejected. Labels such as `复合顶`, `主力出货`, or `洗盘结束` require subjective thresholds and would increase
false positives. Existing double-top/bottom output is not expanded by this batch.

### C. Analyzer facts plus state-machine interpretation

Selected. `technical_structure.py` owns source-derived pivot relations, `technical_state_machine.py` remains
the only interpretation owner, and `technical_renderer.py` only formats the accepted projection.

## 4. Locked Boundaries

### 4.1 Allowed runtime changes

- `scripts/utils/reporter/technical_structure.py`
- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/sections/technical_renderer.py`

### 4.2 Allowed test changes

- `tests/reporter/test_technical_structure_path.py`
- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_technical_renderer.py`
- Existing downstream recommendation, scoring, risk, and report-quality tests may be run but not modified
  unless a test-only compatibility assertion is required and separately justified in implementation notes.

### 4.3 Forbidden changes

- No indicator formula, trend score, risk score, EV, target-price formula, position cap, recommendation
  threshold, collector, market-data source, Chapter 4, citation, LLM prompt, or report profile change.
- No stock, code, exchange, or industry-specific rule.
- No `复合顶`, `主力出货`, `吸筹`, `洗盘`, numeric reversal probability, or inferred institutional behavior.
- No renderer-side pivot comparison, break classification, or action inference.
- No second structure selector or parallel technical judgment schema.
- No scenario-ladder source expansion in Phase 2.3A. Confirmed pivots may be used as scenario levels only in a
  separately reviewed Phase 2.3B.

## 5. Source-Fact Contract

### 5.1 Extend the existing structure path

`build_structure_path()` remains the only pivot-path producer. It keeps the existing `pivot_sequence` and
`segments` and adds `pivot_relations`:

```python
{
    "high": {
        "status": "higher|lower|flat|unavailable",
        "previous": {"date": str, "price": float} | None,
        "latest": {"date": str, "price": float} | None,
        "materiality_pct": float | None,
    },
    "low": {
        "status": "higher|lower|flat|unavailable",
        "previous": {"date": str, "price": float} | None,
        "latest": {"date": str, "price": float} | None,
        "materiality_pct": float | None,
    },
}
```

Each serialized segment also exposes the already available factual values:

```python
{
    "start_date": str,
    "end_date": str,
    "start_price": float,
    "end_price": float,
    "start_kind": "high|low",
    "end_kind": "high|low|latest_close",
    "change_pct": float,
    "move": "up|down|flat",
}
```

No value is reconstructed in the renderer.

### 5.2 Relation materiality

The latest two pivots of the same kind are compared with the existing Phase 2.1 materiality rule:

```python
threshold = max(
    price_tolerance_pct,
    price_atr_multiplier * atr_at_latest_pivot / abs(latest_pivot_price),
)
change_pct = latest_pivot_price / previous_pivot_price - 1
```

- `change_pct > threshold` -> `higher`
- `change_pct < -threshold` -> `lower`
- otherwise -> `flat`

`atr_at_latest_pivot` is calculated only from rows available through that pivot. Missing/non-finite prices or
ATR produce `unavailable`; they never fall back to a zero threshold.

The existing confirmed-pivot right-window rule remains unchanged. A pivot cannot become available before its
right-side confirmation bars exist.

### 5.3 Factual structure state

The state machine derives one bounded `structure_state` from `pivot_relations`:

| High relation | Low relation | structure_state |
| --- | --- | --- |
| lower | lower | descending |
| higher | higher | ascending |
| flat | flat | range |
| all other complete pairs | mixed |

If either relation is `unavailable`, the state is `sparse`, regardless of the other relation. This rule takes
precedence over the complete-pair table.

## 6. Interpretation Contract

### 6.1 Contract version

Upgrade only the additive interpretation contract:

```python
"signal_contract": "technical_signal_contract.v2.3"
```

The core `technical_judgment.v1` contract remains unchanged. A cached v2.2 interpretation is stale and must
be rebuilt from current structural inputs or removed while retaining a valid core judgment.

Shape validation is not enough for a v2.3 cache. `ensure_technical_judgment()` must compare the cached
`structure_path` projection with a deterministic projection rebuilt from the current
`resonance.structure_path`, current core trend, channel, invalidation, and auxiliary structure-health inputs.
A mismatched as-of date, relation, source price, active phase, break state, overlap decision, or segment
invalidates the additive interpretation. Reuse the existing interpretation builder for this comparison; do
not add a second classifier or trust a cached prose signature.

### 6.2 Structure diagnosis

Replace, rather than wrap, the current `_path_interpretation()` implementation. It emits:

```python
_path_interpretation(path, trend, channel, invalidation, structure_health)
```

The helper remains pure. `_interpretation()` passes the five already normalized inputs; the renderer never
calls it.

```python
{
    "status": "ready|sparse|unavailable",
    "as_of": str | None,
    "structure_state": "descending|ascending|range|mixed|sparse|unavailable",
    "active_phase": (
        "continuation|countertrend_rebound|countertrend_pullback|range_leg|transition|flat|unknown"
    ),
    "break_state": "confirmed_down|confirmed_up|none",
    "covers_auxiliary_low_relation": bool,
    "summary": str,
    "segments": [
        {
            "period": str,
            "start_price": float,
            "end_price": float,
            "move": str,
            "meaning": str,
        }
    ],
}
```

Deterministic mapping:

- Any structure state with a flat active move -> `flat`, neutral consolidation wording
- `descending + down` -> `continuation`, `下降结构延续`
- `descending + up` -> `countertrend_rebound`, `下降结构中的反抽`
- `ascending + up` -> `continuation`, `上升结构延续`
- `ascending + down` -> `countertrend_pullback`, `上升结构中的回撤`
- `range + up/down` -> `range_leg`, `区间上行段/区间下行段`
- `mixed + up/down` -> `transition`, neutral mixed-transition wording
- sparse/unavailable relations -> no structural claim beyond `确认拐点不足`

The active move is the final accepted segment from the latest confirmed pivot to the current close. The flat
rule has first precedence, before structure-state mapping.

Projection `status` is derived explicitly:

- source path `unavailable` -> `unavailable`;
- source path `sparse`, or derived `structure_state == sparse` -> `sparse`;
- otherwise -> `ready`.

`as_of` is copied from the source path without renderer reconstruction. Sparse paths retain a valid source
date; unavailable paths may use `None`.

Ready summaries name both complete pivot relations before describing the active phase. Mixed summaries must
therefore state both sides, such as `高点下移、低点抬高，结构处于混合过渡`; they cannot collapse to a generic
label that would hide the low relation used by auxiliary-overlap logic. Sparse summaries make no individual
high/low claim.

`structure_state` describes the bounded pivot path, not the controlling trend regime. When it disagrees with
the core trend, the summary must label it as a local counter-state: an ascending path under a bearish core is
`局部修复线索`, while a descending path under a bullish core is `局部转弱线索`. The core trend remains the
controlling conclusion, and the path cannot use `反转` or silently replace the core state.

`covers_auxiliary_low_relation` is true only when all of the following hold:

1. canonical projection status is `ready`;
2. canonical `pivot_relations.low.status` exactly equals `structure_health.last_low_relation` and is in
   `higher|lower|flat`;
3. the canonical previous/latest low points match the auxiliary final two `swing_lows` by normalized calendar
   date and finite numeric price.

Date normalization may remove a midnight time suffix. Price identity uses the existing finite-number helper
and a maximum relative normalization tolerance of `1e-6`; this is serialization tolerance, not semantic fuzzy
matching. Equal relation labels from different pivot points do not count as overlap. A missing or conflicting
point sets the flag false.

### 6.3 Break state

`break_state` is additive context, not a chronology claim:

- `confirmed_down` only when current channel breakout explicitly contains `向下` or invalidation status is
  `broken`.
- `confirmed_up` only when current channel breakout explicitly contains `向上`.
- Otherwise `none`.

The summary may say `当前同时处于已确认破位状态`, but it must not say the break occurred before or after a
particular pivot unless a source date exists. It never mutates `trend.state`, `action.state`, or scores.

### 6.4 Actual facts versus future conditions

When invalidation is currently broken, `primary_evidence` must use the observed `invalidation.message`, for
example `当前收盘价已跌破MA60（1115.34），中期结构破坏确认。`

The generic `hard_invalid` formula remains available only under `invalidation_conditions`. If the observed
message is missing, use the bounded fallback `中期结构失效已确认`; never promote the formula to observed
evidence.

`invalidation_conditions` remain condition definitions, not observed-event records. The renderer must label
them `趋势失效条件` (or `确认与趋势失效条件` when confirmation items exist), even when the core trend is already
invalid. It must not relabel every condition as `已触发` merely because one observed break exists. The actual
trigger is already carried by `primary_evidence`.

## 7. Renderer Contract

### 7.1 Structure projection

The full table becomes:

```markdown
| 阶段 | 价格区间 | 变动 | 结构含义 |
```

The renderer formats `start_price` and `end_price` as the displayed price range. Formatting is permitted;
selecting, recalculating, or replacing either value is not. The renderer does not read raw pivots or OHLCV.

Omit the separate `局部趋势结构（辅助）` block only when
`structure_path.covers_auxiliary_low_relation is True`. Otherwise retain it and rename the heading to
`60日局部低点结构（辅助）` so the different window is explicit. Keep the channel/box block because it is a
distinct fact.

Compact and full modes use the same summary. Compact mode may omit the table but cannot emit a different
diagnosis.

If the observed invalidation message already appears in `primary_evidence`, the key-observation block keeps
the invalidation source, price, and distance but does not repeat the same message. The full technical section
must contain the observed break sentence only once.

### 7.2 Radar wording narrow correction

The score values do not change. `_build_radar_summary()` changes wording only:

- If the maximum normalized component score is `<= 0.5`, emit `各维度均未形成明显支撑` and do not call any
  component `最强`.
- Otherwise retain the strongest-component wording.
- Tied maxima at or below `0.5` follow the same no-strongest rule and do not depend on dictionary order.
- Existing weakest-component warning remains when its normalized score is below `0.4`.

## 8. Required Tests

### 8.1 Structure facts

1. Two lower confirmed highs and two lower confirmed lows produce `lower/lower` with exact dates and prices.
2. Two higher highs and two higher lows produce `higher/higher`.
3. Sub-material differences produce `flat`, using the configured tolerance/ATR floor.
4. A missing second high or low produces `unavailable` for that relation.
5. A candidate pivot inside the unconfirmed right window does not enter either relation.
6. Serialized segment start/end prices are exact source values and remain source ordered.

### 8.2 Interpretation

7. `lower/lower` plus an active up leg is `下降结构中的反抽`, never reversal.
8. `lower/lower` plus an active down leg is `下降结构延续`.
9. `higher/higher` plus an active down leg is `上升结构中的回撤`, not automatic invalidation.
10. `higher/higher` plus an active up leg is `上升结构延续`.
11. `flat/flat`, mixed, sparse, and unavailable fixtures each use their bounded neutral wording.
12. A flat active leg takes precedence over ascending/descending/range/mixed mapping.
13. Source-path unavailable, relation-sparse, and ready fixtures produce the explicitly defined projection
    statuses.
14. A confirmed break appends break context without changing core trend/action state.
15. An ascending local path under a bearish core and a descending local path under a bullish core are framed
    as counter-state evidence and do not overwrite the controlling regime.
16. Broken invalidation primary evidence uses `message`, while `hard_invalid` remains only a condition.
17. A missing broken-invalidation message uses the bounded fallback and never the generic formula.
18. Condition definitions are never relabeled as triggered solely because core trend state is invalid.

### 8.3 Cache and rendering

19. A v2.2 interpretation is rebuilt to v2.3 when current structural inputs exist.
20. `_valid_interpretation()` requires valid structure status/state/phase/break enums, `as_of` as a string or
    `None`, a boolean overlap flag, at most five segments, non-empty period/move/meaning strings, and finite
    numeric start/end prices.
21. A malformed v2.3 relation/segment/enum fails closed, and a shape-valid projection that does not match the
    current source path is rebuilt or removed.
22. The full structure table includes exact source prices; compact/full summaries match.
23. Exact low relation plus exact two-point identity suppresses the auxiliary block. The same relation from
    different pivot points, and different/missing/conflicting relations, preserve it under the explicit
    60-day heading.
24. An observed break sentence appears once even though the invalidation price remains in key observations.
25. Weak/tied radar components do not produce `最强`; a genuinely strong component still does.

### 8.4 Downstream invariants

26. Fixed fixtures preserve trend state, trend-health score, action state, risk score, target state, position,
    and recommendation before and after v2.3 projection.
27. Existing scenario ladder values and source provenance are byte-for-byte unchanged.
28. Focused technical, recommendation, report-quality, full offline, CI grep, and whitespace gates pass.

## 9. Failure Modes

| Failure | Visible symptom | Guard |
| --- | --- | --- |
| Future pivot leaks into current diagnosis | Historical report uses a later-confirmed turning point | Right-window fixture and walk-forward slice test |
| Small price noise becomes trend structure | Near-equal highs/lows labeled higher/lower | Existing tolerance plus ATR materiality test |
| One missing pivot side forces a trend | `lower/unavailable` becomes descending | Sparse-state test |
| Counter-trend leg becomes reversal | One rebound flips bearish diagnosis | Active-phase mapping test |
| Formula is rendered as observed fact | Primary evidence contains `或` condition | Broken-invalidation evidence test |
| Core recommendation changes | Structure projection changes action/score | Downstream identity fixture |
| Stale cache is trusted | Old v2.2 prose survives current inputs | Contract-version rebuild test |
| Renderer re-derives facts | Raw pivot access appears in renderer | Static ownership assertion |
| Distinct 60-day evidence is silently lost | Canonical and auxiliary windows disagree but auxiliary is hidden | Exact relation-overlap test |
| Report repeats identical low relation | Canonical and auxiliary expose the same fact | Exact relation-overlap suppression test |
| Observed break is repeated | Same MA60-break sentence appears in evidence and key levels | Primary-text dedupe test |
| Weak component called strongest | `5/10` is described as strongest | Radar wording test |

## 10. Runtime Budget And Stop Conditions

- Target runtime delta: net `+80` lines across the three allowed runtime files.
- Hard stop: net `+140` lines. Replace existing path interpretation and duplicate renderer branches rather
  than adding a parallel path.
- Stop if implementation requires changing technical scoring, target formulas, risk/recommendation logic,
  scenario source priorities, collector behavior, or files outside the locked scope.
- Stop if exact source dates/prices cannot be retained, a historical slice test detects look-ahead, or
  downstream identity fixtures change.
- Do not generate formal reports until focused and full offline suites pass. Formal acceptance must rerun at
  least Zhongji Innolight and Fudan Microelectronics from modified source and compare technical conclusions,
  evidence wording, structure tables, scores, targets, risks, positions, and recommendations.

## 11. Expected Outcome

The technical chapter should move from:

> Recent confirmed structure is mainly a rebound/local repair.

to an evidence-bounded statement such as:

> Recent confirmed highs and lows both moved lower. The final 13.0% rise is a rebound inside the descending
> structure and has not changed the controlling trend; the current price also remains in a confirmed-break
> state.

The output remains deterministic, auditable, and no more aggressive than the existing core judgment.

## 12. Self-Review Round 1 Delta

- Locked the pure `_path_interpretation(path, trend, channel, invalidation, structure_health)` ownership
  boundary so break and overlap decisions cannot migrate into the renderer.
- Retained numeric segment prices through interpretation for cache provenance and exact-source tests.
- Separated observed invalidation evidence from condition definitions in renderer wording.
- Replaced unconditional auxiliary suppression with exact low-relation overlap, preserving distinct 60-day
  evidence.

## 13. Self-Review Round 2 Delta

- Gave flat active legs first-precedence and defined ready/sparse/unavailable projection status explicitly.
- Strengthened auxiliary deduplication from relation-label equality to exact two-pivot source identity.
- Added complete v2.3 shape validation requirements for enums, booleans, segment text, and finite prices.
- Prevented the observed invalidation sentence from being repeated in both primary evidence and key levels.
- Corrected the additive version field to the existing `signal_contract` owner and made structure `as_of`
  explicit for cache-provenance validation.
