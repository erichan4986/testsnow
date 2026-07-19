# Technical Analysis v2 Phase 2.1 Codex Notes

## Result

- Code verdict: `PASS`.
- Implementation baseline: `087591d`.
- Formal-report acceptance: attempted once for Zhongji, but not accepted because the sandbox could not
  obtain technical market data.
- No network request succeeded and no LLM was used. The failed fast-test attempt wrote only a temporary
  report under `/tmp` and refreshed the ignored same-date raw input as a natural pipeline artifact.

## Implemented Contracts

- Support and resistance are admitted independently; one sparse or invalid side no longer deletes a valid
  opposite side.
- The 10-point volume component is direction-aware, excludes the current bar from its preceding-20 baseline,
  treats missing data as neutral, and neutralizes unadjusted in-window corporate-action comparisons.
- One adjacent-bar MACD histogram classifier feeds both advisor and momentum-extreme scans.
- Momentum extreme and confirmed pivot divergence use separate `family` contracts and separate analyzer
  fields.
- Confirmed pivot divergence uses shared left/right swing confirmation, material price movement, latest-pivot
  age, and RSI/MACD opposite movement without right-edge look-ahead.
- Judgment interpretation requires `technical_signal_contract.v2.1`; stale projections are rebuilt from
  current structural inputs or removed while retaining a valid core judgment.
- The zero-call `multi_indicator_resonance()` and unsupported `吸筹迹象` language were deleted.

## TDD Evidence

- Task 1 RED: 2 failed, 5 passed for one-sided support/resistance admission. GREEN: 7 passed.
- Task 2 RED: 7 failed, 8 passed for volume direction, neutral fallback, and corporate-action reliability.
  GREEN: 15 passed; downstream score/risk/recommendation contracts: 71 passed.
- Task 3 RED: 9 failed, 2 passed for adjacent MACD direction and missing pivot divergence. GREEN: 11 passed;
  expanded structure/momentum regression: 44 passed.
- Task 4 RED: 4 failed, 35 passed for signal-contract cache invalidation and family-aware evidence priority.
  GREEN with renderer/market contracts: 56 passed.
- Final self-review RED: 2 failed, 6 passed for NaN momentum payloads and zero pivot prices. GREEN: 8 passed.

## Verification

- Focused technical suite: 144 passed before the final self-review repair.
- Full offline suite after the final code change: 2520 passed, 16 skipped in 38.38s.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Five runtime modules compile with `python3 -m py_compile`.
- Symbol audit: no runtime `multi_indicator_resonance`, `吸筹迹象`, sign-only
  `macd_hist_shrinking`, or `柱线翻绿` path remains.

## Runtime Budget

Relative to `087591d`:

| Runtime file | Added | Removed | Net |
| --- | ---: | ---: | ---: |
| `technical_analyzer.py` | 47 | 26 | +21 |
| `technical_config.py` | 3 | 0 | +3 |
| `technical_patterns.py` | 135 | 192 | -57 |
| `technical_state_machine.py` | 77 | 63 | +14 |
| `technical_structure.py` | 26 | 17 | +9 |
| **Total** | **288** | **298** | **-10** |

The `+140` hard stop was not approached.

## Scope Audit

- Runtime changes are limited to the five locked technical modules.
- Tests are limited to support/resistance, trend health, corporate action, momentum extreme, pivot divergence,
  and technical judgment contracts.
- No target formula, EV, score weight, risk score, recommendation threshold, renderer classification,
  collector, Chapter 4, citation, or LLM prompt was changed.
- The unrelated dirty file
  `docs/agent_workflow/2026-07-15-knowledge-persistence-slimming-6a2-codex-notes.md` remains untouched.

## Blocker / Warning / Deviation

- Blocker: none for code acceptance.
- Formal-report gate: passed on 2026-07-19 with fresh Zhongji and Fudan Markdown/HTML outputs. Both report
  entrances exited 0; report quality and source-boundary checks passed, and prose checks passed with only
  pre-existing Chapter 4 warnings.
- Warning: corrected volume direction can legitimately change trend health and downstream recommendation near
  an existing threshold. Formal acceptance confirmed Zhongji volume `9 -> 1` and trend health `34 -> 26`,
  while Fudan volume changed `6 -> 4` and trend health `38 -> 36`; non-technical dimensions were unchanged.
- Deviation: the implementation plan expected net `+90`; deleting the legacy scorer made the result net
  `-10` without reducing behavior or test coverage.

## Formal Report Acceptance

- Fresh reports: `reports/中际旭创_20260719.md` and `reports/复旦微电_20260719.md`.
- Direction-aware volume wording rendered as `放量下跌确认` and `量能正常下跌` respectively.
- Fudan retained a valid resistance zone when support was unavailable.
- Both reports rendered `空头柱扩张`; momentum extremes and pivot divergence remained separate observations.
- Risk-control recommendations did not flip because of counter-trend evidence.
- Independent focused verification after the report run: 77 passed.

Phase 2.1 is ready for checkpointing. Chapter 4 prose warnings remain outside this technical-analysis batch.
