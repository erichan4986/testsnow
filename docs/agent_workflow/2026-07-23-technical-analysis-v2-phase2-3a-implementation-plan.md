# Technical Analysis v2 Phase 2.3A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` and execute tasks in order.

**Goal:** Add deterministic higher/lower pivot diagnosis, factual invalidation evidence, and a concise
source-priced structure projection without changing score, target, risk, position, or recommendation logic.

**Architecture:** Extend the existing `build_structure_path()` fact producer, replace the existing
`_path_interpretation()` state-machine projection, and keep the renderer presentation-only. Upgrade only the
additive interpretation contract to `technical_signal_contract.v2.3` and validate it against current source
facts before trusting cache.

**Tech Stack:** Python, pandas, pytest, existing technical report pipeline.

---

## File Map

Runtime:

- `scripts/utils/reporter/technical_structure.py`: exact pivot relations and segment source fields.
- `scripts/utils/reporter/technical_state_machine.py`: v2.3 diagnosis, cache provenance, factual invalidation.
- `scripts/utils/reporter/sections/technical_renderer.py`: price table, condition labels, overlap display, radar wording.

Tests:

- `tests/reporter/test_technical_structure_path.py`
- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_technical_renderer.py`

Notes:

- `docs/agent_workflow/2026-07-23-technical-analysis-v2-phase2-3a-codex-notes.md`

## Task 1: Pivot Relation Facts

- [x] Add failing tests proving:
  - lower/lower, higher/higher, and flat relations;
  - unavailable relation when one same-kind pair is missing;
  - exact previous/latest source dates and prices;
  - unconfirmed right-edge extrema do not leak;
  - segments expose `start_kind`, `start_price`, and `end_price` in source order.
- [x] Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_technical_structure_path.py -q -p no:cacheprovider
  ```

  Expected: new assertions fail because `pivot_relations` and `start_kind` do not exist.

- [x] Implement one private relation helper in `technical_structure.py` using:

  ```python
  threshold = max(tolerance, multiplier * atr_at_latest / abs(latest_price))
  change = latest_price / previous_price - 1.0
  status = "higher" if change > threshold else "lower" if change < -threshold else "flat"
  ```

  Missing/non-finite values return the fixed unavailable shape. Use only the final two confirmed pivots of
  each kind and retain exact source values.

- [x] Re-run the focused test until GREEN.

## Task 2: v2.3 Structure Diagnosis And Cache Contract

- [x] Add failing tests in `test_technical_state_machine.py` for:
  - descending continuation and descending counter-trend rebound;
  - ascending continuation and ascending pullback;
  - flat precedence, range, mixed, sparse, and unavailable paths;
  - local counter-state wording when path and core trend disagree;
  - break state without core trend/action mutation;
  - exact two-low overlap and same-label/different-pivot non-overlap;
  - observed invalidation `message` in primary evidence, formula only in conditions;
  - missing observed message bounded fallback;
  - v2.2 rebuild, malformed v2.3 rejection, and shape-valid/current-source mismatch rebuild;
  - unchanged scenario ladder.
- [x] Run the state-machine module and confirm RED for the missing v2.3 contract and fields.
- [x] Replace `_path_interpretation()` with:

  ```python
  def _path_interpretation(path, trend, channel, invalidation, structure_health):
      ...
  ```

  It must return `status`, `as_of`, `structure_state`, `active_phase`, `break_state`,
  `covers_auxiliary_low_relation`, `summary`, and at most five numeric-price segments.
- [x] Update `_interpretation()` to use observed invalidation text and emit
  `signal_contract = technical_signal_contract.v2.3`. Do not change primary/counter budgets.
- [x] Strengthen `_valid_interpretation()` for all v2.3 enums, booleans, text fields, finite prices, and list
  budgets.
- [x] Add a deterministic current-source projection comparison in `ensure_technical_judgment()` alongside
  the existing scenario provenance check. Reuse `_path_interpretation()`; do not add another classifier.
- [x] Re-run state-machine and recommendation identity tests until GREEN.

## Task 3: Renderer Projection And Wording

- [x] Add failing renderer tests proving:
  - full table header is `阶段 | 价格区间 | 变动 | 结构含义` and contains source prices;
  - compact/full summaries are identical;
  - exact auxiliary overlap suppresses the duplicate block;
  - non-overlap retains `60日局部低点结构（辅助）`;
  - invalidation condition definitions are never labeled `已触发` merely because trend is invalid;
  - observed break message appears once;
  - maximum normalized component `<= 0.5` produces `各维度均未形成明显支撑`, while a value above `0.5`
    retains strongest-component wording.
- [x] Run renderer tests and confirm RED.
- [x] Implement presentation-only formatting and dedupe in `technical_renderer.py`. Do not read raw pivots,
  compare structure states, or select levels in the renderer.
- [x] Re-run renderer tests until GREEN.

## Task 4: Refactor And Verification

- [x] Run focused technical tests:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
    tests/reporter/test_technical_structure_path.py \
    tests/reporter/test_technical_state_machine.py \
    tests/reporter/test_technical_renderer.py -q -p no:cacheprovider
  ```

- [x] Run downstream identity tests covering recommendation, scoring, risk, and report quality.
- [x] Measure the three runtime files against `f17b859`; stop above net `+140`.
- [x] Run the full offline suite, `bash tools/ci_grep_gates.sh`, and `git diff --check`.
- [x] Write notes recording RED/GREEN evidence, tests, runtime delta, scope audit, and any deviation.
- [x] Do not generate formal reports in this code batch. Fresh Zhongji/Fudan report acceptance is a separate
  local execution gate after code verification.

## Plan Self-Review

- Every behavior has a test-first step.
- The only interpretation owner remains `technical_state_machine.py`.
- Scenario sources and values are explicitly frozen.
- Source prices remain numeric through validation and are formatted only at render time.
- No scoring, target, risk, action, recommendation, collector, Chapter 4, or prompt file is in scope.
