# Technical Analysis v2 Phase 2.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic structure-path, terminal-shock, and scenario-ladder projections to the technical chapter without changing scores, risk, target prices, recommendation policy, or data collection.

**Architecture:** `technical_structure.py` produces auditable OHLCV facts, including a shared volume context. The analyzer stores those facts in resonance; `technical_state_machine.py` is the only component allowed to turn them into regime-aware interpretation. The renderer copies that interpretation into bounded Markdown blocks.

**Tech Stack:** Python, pandas, existing technical-report modules, pytest.

---

## File Map

| File | Responsibility |
| --- | --- |
| `scripts/utils/reporter/technical_structure.py` | Shared volume context, confirmed-pivot path facts, terminal-shock facts |
| `scripts/utils/reporter/technical_analyzer.py` | Compute once from adjusted OHLCV and attach facts to resonance |
| `scripts/utils/reporter/technical_state_machine.py` | Preserve the Phase 2.1 volume score matrix; derive scenario/path/shock interpretation and cache validation |
| `scripts/utils/reporter/technical_config.py` | Generic terminal-shock thresholds |
| `scripts/utils/reporter/sections/technical_renderer.py` | Pure projection of the v2.2 interpretation |
| `tests/reporter/test_technical_structure_path.py` | New isolated path/shock/volume-context contracts |
| `tests/reporter/test_trend_health.py` | Shared volume context preserves accepted Phase 2.1 score matrix |
| `tests/reporter/test_technical_state_machine.py` | Scenario, evidence precedence, cache provenance, downstream identity |
| `tests/reporter/test_technical_renderer.py` | Bounded full/compact report projection |

## Task 1: Shared Volume, Structure Path, And Terminal Shock Facts

**Files:**

- Modify: `scripts/utils/reporter/technical_structure.py`
- Modify: `scripts/utils/reporter/technical_config.py`
- Modify: `scripts/utils/reporter/technical_state_machine.py`
- Create: `tests/reporter/test_technical_structure_path.py`
- Modify: `tests/reporter/test_trend_health.py`

- [ ] **Step 1: Write failing source-fact tests**

```python
from technical_structure import (
    analyze_terminal_shock,
    build_structure_path,
    build_volume_context,
)

def test_path_uses_confirmed_alternating_pivots_and_latest_close_only():
    frame = _daily_frame([100, 104, 98, 106, 101, 108, 103, 107])
    result = build_structure_path(frame, _config())
    assert result["status"] == "ready"
    assert result["segments"][-1]["end_kind"] == "latest_close"
    assert all(item["date"] != str(len(frame) - 1) for item in result["pivot_sequence"])

def test_dual_extreme_bar_is_omitted_not_ordered_twice():
    result = build_structure_path(_outside_bar_frame(), _config())
    assert "dual_extreme_bar_omitted" in result["limitations"]
    assert len({item["date"] for item in result["pivot_sequence"]}) == len(result["pivot_sequence"])

def test_terminal_downside_shock_uses_prior_atr_and_shared_volume_context():
    frame = _shock_frame()
    volume = build_volume_context(frame, {"price_vs_ma20": "跌破"}, True)
    shock = analyze_terminal_shock(frame, _atr(frame), volume, _config())
    assert shock["status"] == "ready"
    assert shock["direction"] == "down"
    assert shock["volume_ratio"] == volume["ratio"]
    assert shock["range_atr_ratio"] >= 1.5

def test_unreliable_or_short_volume_does_not_hide_price_shock():
    frame = _shock_frame()
    volume = {"status": "unreliable", "ratio": None, "context": "unknown"}
    shock = analyze_terminal_shock(frame, _atr(frame), volume, _config())
    assert shock["status"] == "ready"
    assert shock["volume_status"] == "unreliable"
    assert all("量能比" not in fact for fact in shock["facts"])
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_structure_path.py -q -p no:cacheprovider
```

Expected: import failure for the three missing fact helpers.

- [ ] **Step 3: Implement the fact helpers**

Add `build_volume_context()` to `technical_structure.py`. Its complete decision structure is:

```python
def build_volume_context(df_daily, daily_structure, volume_reliable=True):
    empty = {"status": "insufficient", "ratio": None, "price_change": None, "context": "unknown"}
    if not volume_reliable:
        return {**empty, "status": "unreliable"}
    if df_daily is None or len(df_daily) < 21 or not {"close", "volume"}.issubset(df_daily):
        return empty
    window = df_daily.tail(21)
    close = pd.to_numeric(window["close"], errors="coerce")
    volume = pd.to_numeric(window["volume"], errors="coerce")
    if close.iloc[-2:].isna().any() or volume.isna().any() or (volume <= 0).any():
        return empty
    baseline = float(volume.iloc[:-1].mean())
    if baseline <= 0:
        return empty
    change = float(close.iloc[-1] - close.iloc[-2])
    position = (daily_structure or {}).get("price_vs_ma20")
    context = "bullish" if change > 0 and position == "站上" else "bearish" if change < 0 and position == "跌破" else "mixed"
    return {"status": "ready", "ratio": float(volume.iloc[-1] / baseline), "price_change": change, "context": context}
```

Implement `build_structure_path()` using only `confirmed_swing_indices()` and the existing divergence
config. Normalize dates from `date` or `DatetimeIndex`; return `unavailable` for an unparseable positional
index. Remove dual-role indices before sorting, collapse consecutive same-kind pivots to the more extreme
price, calculate each segment with ATR through its end position, and append the latest close only as
`end_kind="latest_close"`.

Implement `analyze_terminal_shock()` using a prior-row ATR reference:

```python
prior_atr = pd.to_numeric(atr_series, errors="coerce").shift(1).iloc[-1]
true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
close_location = (close - low) / (high - low)
body_ratio = abs(close - open_) / (high - low)
```

Return `ordinary` unless range/ATR, body/range, and directional close-location all pass the config values.
Only append a volume fact when `volume_context["status"] == "ready"`.

Add default config:

```python
"structure_path": {
    "shock": {"min_range_atr": 1.5, "min_body_range": 0.65, "close_extreme_pct": 0.20},
}
```

- [ ] **Step 4: Route trend health through the shared context**

Change the internal scorer to consume `volume_context`, preserving its score matrix exactly:

```python
def _score_volume_confirmation(volume_context):
    if volume_context.get("status") == "unreliable":
        return 5, "成交量不可比，量价分项按中性处理", "unreliable"
    if volume_context.get("status") != "ready":
        return 5, "量价数据不足，按中性处理", "insufficient"
    ratio, context = volume_context["ratio"], volume_context["context"]
    # retain existing bucket thresholds, score matrix, and Chinese labels
```

Add optional `volume_context=None` to `compute_trend_health()`. When absent, call
`build_volume_context(df_daily, daily_structure, volume_reliable)`; when present, use it unchanged.
The existing public callers and all Phase 2.1 behavior therefore remain compatible.

- [ ] **Step 5: Run Task 1 tests and verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_structure_path.py tests/reporter/test_trend_health.py -q -p no:cacheprovider
```

Expected: all pass, including existing 9/1/4 direction-aware volume scores.

## Task 2: Attach Facts Once In The Analyzer

**Files:**

- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Modify: `tests/reporter/test_technical_structure_path.py`

- [ ] **Step 1: Add an analyzer integration test**

```python
def test_analyzer_attaches_one_volume_context_path_and_shock(monkeypatch):
    result = advanced_medium_term_resonance(_long_daily_frame(), quote={"adjustment": "qfq"})
    resonance = result["resonance"]
    assert resonance["volume_context"]["status"] in {"ready", "unreliable", "insufficient"}
    assert resonance["structure_path"]["status"] in {"ready", "sparse", "unavailable"}
    assert resonance["terminal_shock"]["status"] in {"ready", "ordinary", "unavailable"}
    assert resonance["trend_health"]["components"]["volume_confirmation"]["score"] in range(0, 11)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_structure_path.py::test_analyzer_attaches_one_volume_context_path_and_shock -q -p no:cacheprovider
```

Expected: missing resonance keys.

- [ ] **Step 3: Implement analyzer wiring**

After `daily_structure` and `atr_series` exist, compute exactly once:

```python
volume_reliable = _volume_window_reliable(df_daily, price_adjustment_validation)
volume_context = build_volume_context(df_daily, daily_structure, volume_reliable)
structure_path = build_structure_path(df_daily, config)
terminal_shock = analyze_terminal_shock(df_daily, atr_series, volume_context, config)
```

Pass `volume_context=volume_context` to `compute_trend_health()` and store all three facts under resonance.
Do not move score logic, target calculation, state classification, or action calculation.

- [ ] **Step 4: Run Task 2 tests and verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_structure_path.py tests/reporter/test_trend_health.py tests/reporter/test_corporate_action_adjustment.py -q -p no:cacheprovider
```

Expected: all pass; corporate-action windows still neutralize only the volume claim.

## Task 3: Derive v2.2 Interpretation And Cache Provenance

**Files:**

- Modify: `scripts/utils/reporter/technical_state_machine.py`
- Modify: `tests/reporter/test_technical_state_machine.py`

- [ ] **Step 1: Write failing judgment tests**

```python
def test_bearish_path_and_downside_shock_are_evidence_not_action_owner():
    judgment = build_technical_judgment(
        _broken_resonance_with_path_and_shock(), _bearish_observe_target(),
        indicators={"close": 100.0, "ma_20": 105.0, "ma_60": 110.0},
    )
    interpretation = judgment["interpretation"]
    assert judgment["action"]["state"] == "risk_control"
    assert interpretation["signal_contract"] == "technical_signal_contract.v2.2"
    assert interpretation["primary_evidence"][0]["code"] in {"hard_invalidation", "directional_channel_break", "terminal_down_shock"}
    assert interpretation["scenario_ladder"]["reference_close"] == 100.0
    assert {step["level_source"] for step in interpretation["scenario_ladder"]["steps"]} <= {"ma20", "ma60", "support_zone", "resistance_zone", "hard_invalidation"}

def test_cached_v22_scenario_with_wrong_as_of_or_level_rebuilds():
    cached = _valid_v22_judgment()
    cached["interpretation"]["scenario_ladder"]["reference_close"] = 99.0
    rebuilt = ensure_technical_judgment(cached, _current_resonance(), _target_payload(), {"close": 100.0, "ma_20": 105.0})
    assert rebuilt["interpretation"]["scenario_ladder"]["reference_close"] == 100.0

def test_context_free_v22_cache_returns_core_only():
    cached = _valid_v22_judgment()
    result = ensure_technical_judgment(cached)
    assert "interpretation" not in result
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_state_machine.py -q -p no:cacheprovider
```

Expected: v2.1 contract/cache behavior fails the new v2.2 assertions.

- [ ] **Step 3: Implement scenario and interpretation helpers**

Add helpers with these responsibilities:

```python
def _path_interpretation(path, trend): ...
def _terminal_event(shock, trend): ...
def _scenario_ladder(resonance, indicators, trend): ...
def _scenario_levels_match_inputs(interpretation, resonance, indicators): ...
```

`_scenario_ladder()` builds exact source candidates only:

```python
candidates = {
    "ma20": indicators.get("ma_20"),
    "ma60": indicators.get("ma_60"),
    "support_zone": (resonance.get("key_levels") or {}).get("support_zone"),
    "resistance_zone": (resonance.get("key_levels") or {}).get("resistance_zone"),
    "hard_invalidation": (resonance.get("invalidation") or {}).get("hard_invalid_price"),
}
```

Resolve zone candidates to `zone_high` or `zone_low` only under the exact regime priority in the design, and
persist that choice as `source_field` (`zone_high`, `zone_low`, or `value`). Filter non-finite and wrong-side
values, preserve priority before the `0.5%` dedupe, and put the current path `as_of` plus
`indicators["close"]` in the ladder object. Do not interpolate a level.

Change `_interpretation()` to take `indicators`; add `terminal_down_shock` or `terminal_up_shock` at the
specified primary/counter precedence without changing `_action_state()`. Validate v2.2 shapes and then make
`ensure_technical_judgment()` retain interpretation only when current resonance/indicators prove its scenario
provenance. A context-free v2.2 cache returns its validated core without interpretation.

- [ ] **Step 4: Run Task 3 tests and downstream identity tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_state_machine.py tests/reporter/test_scoring_engine_contract.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_risk_renderer.py -q -p no:cacheprovider
```

Expected: all pass; no score, risk, target, or recommendation identity regression.

## Task 4: Render The Bounded Projection

**Files:**

- Modify: `scripts/utils/reporter/sections/technical_renderer.py`
- Modify: `tests/reporter/test_technical_renderer.py`

- [ ] **Step 1: Write failing renderer tests**

```python
def test_full_renderer_projects_path_shock_and_scenarios_without_raw_selection():
    ctx = _make_ctx(with_new_fields=True, mode="full")
    _add_v22_interpretation(ctx)
    output = TechnicalRenderer().render(ctx)
    assert "**结构演变**" in output
    assert "**末端异常K线**" in output
    assert "**情景阶梯**" in output
    assert output.count("| 阶段 | 变动 | 含义 |") == 1
    assert "趋势扭转观察条件" in output

def test_ordinary_terminal_bar_has_no_placeholder_and_compact_keeps_action():
    full, compact = _render_v22_pair(terminal_status="ordinary")
    assert "末端异常K线" not in full
    assert "当前行动" in full and "当前行动" in compact
    assert _action_line(full) == _action_line(compact)
```

- [ ] **Step 2: Run the renderer tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_renderer.py -q -p no:cacheprovider
```

Expected: new v2.2 blocks are absent.

- [ ] **Step 3: Implement pure renderer projection**

Add renderer-only formatting helpers:

```python
def _render_structure_path(self, projection): ...
def _render_terminal_event(self, event): ...
def _render_scenario_ladder(self, ladder): ...
```

They accept interpretation dictionaries only, never resonance raw bars or indicators. Emit no more than five
path rows, four event facts, and three scenario bullets. Place them after main evidence/conditions and before
the detailed component table. Remove repeated weekly/daily prose that restates the path summary. For compact
mode, render the summary and up to three scenario bullets but omit the path table; it must use the same
judgment action and labels.

- [ ] **Step 4: Run Task 4 tests and report-contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_renderer.py tests/reporter/test_report_quality.py -q -p no:cacheprovider
```

Expected: all pass with no legacy raw-warning ranking or precision-target leak.

## Task 5: Full Verification, Budget, And Formal Reports

**Files:**

- Modify: `docs/agent_workflow/2026-07-19-technical-analysis-v2-phase2-2-codex-notes.md`

- [ ] **Step 1: Verify implementation boundaries**

Run:

```bash
git diff --numstat fdd0941 -- \
  scripts/utils/reporter/technical_structure.py \
  scripts/utils/reporter/technical_analyzer.py \
  scripts/utils/reporter/technical_state_machine.py \
  scripts/utils/reporter/technical_config.py \
  scripts/utils/reporter/sections/technical_renderer.py
git diff --check
```

Expected: runtime net growth at or below `+180`; no whitespace errors; no changes to collectors, scoring,
target prices, risks, Chapter 4, citations, or prompts.

- [ ] **Step 2: Run the complete offline suite and CI gate**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
```

Expected: no test failures and all CI grep gates pass.

- [ ] **Step 3: Regenerate formal report evidence locally**

Run only in a local environment with ordinary market-data access:

```bash
python3 scripts/run_stock_report.py --stock 中际旭创 --date 20260719 --fast-test --no-pdf
python3 scripts/run_stock_report.py --stock 复旦微电 --date 20260719 --fast-test --no-pdf
python3 scripts/check_report_quality.py reports/中际旭创_20260719.md
python3 scripts/check_report_source_boundary.py reports/中际旭创_20260719.md
python3 scripts/check_report_prose_quality.py reports/中际旭创_20260719.md
python3 scripts/check_report_quality.py reports/复旦微电_20260719.md
python3 scripts/check_report_source_boundary.py reports/复旦微电_20260719.md
python3 scripts/check_report_prose_quality.py reports/复旦微电_20260719.md
```

Expected: fresh Markdown/HTML outputs; quality/source checks pass; structure path, shock (only when present),
and scenario ladder use only existing levels; action and target status remain coherent.

- [ ] **Step 4: Record acceptance and make one explicit checkpoint commit**

Document test outputs, report freshness, runtime numstat, scope audit, blockers/warnings/deviations, and any
environment-only report limitation in the notes file. Stage only Phase 2.2 runtime, tests, and workflow files:

```bash
git add scripts/utils/reporter/technical_structure.py \
  scripts/utils/reporter/technical_analyzer.py \
  scripts/utils/reporter/technical_state_machine.py \
  scripts/utils/reporter/technical_config.py \
  scripts/utils/reporter/sections/technical_renderer.py \
  tests/reporter/test_technical_structure_path.py \
  tests/reporter/test_trend_health.py \
  tests/reporter/test_technical_state_machine.py \
  tests/reporter/test_technical_renderer.py \
  docs/agent_workflow/2026-07-19-technical-analysis-v2-phase2-2-codex-notes.md
git commit -m "feat: narrate technical structure paths"
```

Do not stage the unrelated `2026-07-15-knowledge-persistence-slimming-6a2-codex-notes.md` modification.

## Plan Self-Review

- Spec coverage: Tasks 1-2 implement shared facts and one analyzer bridge; Task 3 owns all interpretation,
  level provenance, cache behavior, and action invariants; Task 4 is pure projection; Task 5 covers budget,
  complete suite, and formal reports.
- Provenance scan: zone-derived scenario levels record `source_field`, so cache validation can distinguish the
  high and low edge of the same source zone without adding a second owner or changing user-facing prose.
- Type consistency: `volume_context`, `structure_path`, `terminal_shock`, and the object-shaped
  `scenario_ladder` use the same names in producer, state machine, cache, renderer, and tests.
- Scope check: this remains one technical projection batch. The plan does not add indicators, data sources,
  scores, risk logic, targets, recommendation policy, or Chapter 4 behavior.
