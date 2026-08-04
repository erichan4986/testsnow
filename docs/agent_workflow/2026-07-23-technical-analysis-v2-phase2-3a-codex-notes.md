# Technical Analysis v2 Phase 2.3A Codex Notes

## Result

- Verdict: PASS
- Formal report generation: not run by design
- Runtime budget: `+137` lines against `f17b859`; hard stop was `+140`
- Scope deviation: none

## Modified Files

Runtime:

- `scripts/utils/reporter/technical_structure.py`
- `scripts/utils/reporter/technical_state_machine.py`
- `scripts/utils/reporter/sections/technical_renderer.py`

Tests:

- `tests/reporter/test_technical_structure_path.py`
- `tests/reporter/test_technical_state_machine.py`
- `tests/reporter/test_technical_renderer.py`

## RED / GREEN

1. Pivot relation facts: RED `4 failed, 5 passed`; final GREEN `9 passed`.
2. v2.3 diagnosis and cache contract: RED `14 failed, 40 passed`; GREEN `54 passed`.
3. Renderer projection: RED `5 failed, 13 passed`; GREEN `18 passed`.
4. Compression regression: `1 failed, 80 passed`; restored empty-path fail-closed behavior.
5. Final self-review fixtures: RED `3 failed`; GREEN `3 passed`. These cover a ready path without an
   active segment, an unknown source-path status, and an unavailable path carrying a source date.

The first pivot-relation GREEN attempt exposed two unrealistic low-price fixtures whose changes were below
the existing ATR materiality threshold. The fixtures were moved to realistic price scale; the algorithm and
threshold were not weakened.

## Requirement-Test Matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Higher/lower/flat facts from confirmed pivots | `build_structure_path()` emits exact same-kind relations | structure-path relation and right-edge tests |
| Numeric, source-ordered path | segments retain start/end prices and pivot kind | source substring/order and segment tests |
| One deterministic diagnosis owner | `_path_interpretation()` in state machine | state/phase matrix tests |
| Core trend/action remain controlling | local conflict changes wording only | conflict identity test |
| Observed break separated from future formula | primary evidence uses `message`; conditions retain formula | invalidation evidence and renderer tests |
| Auxiliary overlap requires exact relation and points | source dates/prices compared before suppression | overlap and non-overlap tests |
| Stale cached projection is rebuilt | v2.3 projection compared with current source inputs | stale-cache test |
| Renderer remains presentation-only | source prices formatted in structure table | compact/full renderer tests |
| Scenario, score, target, risk, action unchanged | no owner files changed; identity suite retained | downstream and full suites |

## Verification

- Focused technical suite: `84 passed in 2.22s`
- Downstream identity suite: `194 passed in 3.18s`
- Full offline suite: `2597 passed, 16 skipped in 50.85s`
- `bash tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean

## Runtime Numstat

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `technical_renderer.py` | 12 | 13 | -1 |
| `technical_state_machine.py` | 143 | 29 | +114 |
| `technical_structure.py` | 27 | 3 | +24 |
| **Total** | **182** | **45** | **+137** |

The first complete implementation measured `+168`. Shared phase wording, projection validation, and cache
comparison were consolidated without changing decision order, reducing the final delta to `+137`.

## Blockers / Warnings / Deviations

- Blockers: none
- Warnings: runtime is within the hard stop but above the `+80` design target; further compression would
  trade away explicit validation or source-provenance behavior.
- Deviations: none
- Deferred acceptance: fresh Zhongji/Fudan report generation and visual review remain a separate local gate.
