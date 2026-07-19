# Technical Analysis v2 Phase 2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and
> verification-before-completion. Execute inline from checkpoint `087591d`.

**Goal:** Correct support/resistance admission, volume-direction scoring, MACD histogram interpretation,
and pivot-divergence semantics without changing technical weights, target formulas, risk rules, or
recommendation thresholds.

**Architecture:** Preserve the existing analyzer/state-machine pipeline. Add shared structural and momentum
helpers at their current owners, pass explicit reliability data into the existing trend-health component,
and version only the additive judgment interpretation contract. Delete the zero-call legacy scorer instead
of adding another selection path.

**Tech Stack:** Python, pandas, pytest.

---

### Task 1: Admit Support And Resistance Independently

**Files:**
- Modify: `tests/reporter/test_support_resistance.py`
- Modify: `scripts/utils/reporter/technical_structure.py`

- [ ] Add fixtures where only support qualifies, only resistance qualifies, and one side fails its current-
  price position check while the opposite side remains valid.
- [ ] Run `python3 -m pytest tests/reporter/test_support_resistance.py -q -p no:cacheprovider` and confirm the
  one-sided fixtures fail because the current early return discards both sides.
- [ ] Replace the joint touch-count early return with per-side bucket admission. Preserve `min_touches`, ATR
  bucketing, position validation, overlap handling, and explicit side-specific diagnostics.
- [ ] Re-run the focused file and confirm all support/resistance tests pass.

### Task 2: Make Volume Confirmation Direction-Aware And Reliable

**Files:**
- Modify: `tests/reporter/test_trend_health.py`
- Modify: `tests/reporter/test_corporate_action_adjustment.py`
- Modify: `scripts/utils/reporter/technical_state_machine.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`

- [ ] Add tests for identical volume ratios under bullish/bearish/mixed contexts, current-bar exclusion,
  short or invalid history neutral fallback, and removal of the five-day monotonic adjustment.
- [ ] Add corporate-action fixtures proving an unadjusted gap inside the latest 21-bar window neutralizes
  volume while a gap before the window does not; malformed gap dates fail neutral.
- [ ] Run the named files and confirm RED against the optimistic direction-blind `8/10` implementation.
- [ ] Implement `_volume_window_reliable()` in the analyzer and pass its boolean into
  `compute_trend_health()`. Replace `_score_volume_confirmation()` with the locked matrix and return
  `(score, evidence, status)`.
- [ ] Append the volume comparability limitation once when status is `unreliable`; do not change component
  weights or trend-health grade thresholds.
- [ ] Re-run both focused files and the scoring/recommendation contract tests.

### Task 3: Separate Momentum Extreme From Confirmed Pivot Divergence

**Files:**
- Modify: `tests/reporter/test_boll_overextension.py`
- Create: `tests/reporter/test_pivot_divergence.py`
- Modify: `scripts/utils/reporter/technical_patterns.py`
- Modify: `scripts/utils/reporter/technical_structure.py`
- Modify: `scripts/utils/reporter/technical_analyzer.py`
- Modify: `scripts/utils/reporter/technical_config.py`

- [ ] Add adjacent-histogram tests for negative/positive expansion and contraction, including equal/missing
  fail-closed cases and advisor/scan identity.
- [ ] Add confirmed-pivot fixtures for bullish and bearish divergence, no material price relation, stale
  pivots, right-edge look-ahead rejection, and unresolved adjustment confidence caps.
- [ ] Run both focused files and confirm RED because the current scan is sign-only and no pivot detector
  exists.
- [ ] Add `classify_macd_histogram()`, canonical momentum-extreme scan, and thin
  `detect_boll_overextension()` compatibility alias in `technical_patterns.py`.
- [ ] Add shared `confirmed_swing_indices()` in `technical_structure.py`; reuse it from structure health and
  pivot divergence. Add the three generic divergence config keys.
- [ ] Store `overextension_scan` and `divergence_scan` separately in analyzer output, reusing canonical RSI
  and MACD formulas and applying adjustment caps independently.
- [ ] Delete `multi_indicator_resonance()` and its unused analyzer imports.
- [ ] Re-run momentum, pivot, structure, analyzer, and corporate-action tests.

### Task 4: Version Interpretation And Preserve Evidence Precedence

**Files:**
- Modify: `tests/reporter/test_technical_state_machine.py`
- Modify: `scripts/utils/reporter/technical_state_machine.py`

- [ ] Add tests for `technical_signal_contract.v2.1`, stale interpretation rebuild/removal, family-based
  legacy routing, divergence-before-overextension counter evidence, deduplication, and unchanged
  `risk_control` under bearish trend plus bullish divergence.
- [ ] Run the named tests and confirm RED because the current interpretation accepts unversioned caches and
  conflates `divergence_scan` with momentum extreme.
- [ ] Require the additive signal contract in `_valid_interpretation()`. Rebuild it from structural inputs or
  return a valid core-only cache without stale interpretation.
- [ ] Apply fixed evidence priority: false breakout/rebound, pivot divergence, momentum extreme, BIAS. Keep
  the two-item counter-evidence display budget and preserve the controlling action.
- [ ] Re-run state-machine and renderer tests.

### Task 5: Regression, Budget, And Acceptance Gates

**Files:**
- Create: `docs/agent_workflow/2026-07-18-technical-analysis-v2-phase2-1-codex-notes.md`

- [ ] Run all focused technical tests, scoring/risk/recommendation contracts, and the full offline suite.
- [ ] Run `bash tools/ci_grep_gates.sh` and `git diff --check`.
- [ ] Audit that no runtime `multi_indicator_resonance` reference or `吸筹迹象` text remains.
- [ ] Measure the five runtime files against `087591d`; stop if combined net growth exceeds `+140`.
- [ ] Record RED/GREEN evidence, runtime numstat, scope audit, blockers, warnings, and deviations. Do not
  generate formal reports until all code gates pass.
