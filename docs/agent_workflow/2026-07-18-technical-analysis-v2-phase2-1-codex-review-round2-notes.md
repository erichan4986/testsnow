# Technical Analysis v2 Phase 2.1 - Codex Self-Review Round 2

## Verdict

`needs_revision` before the inline design repair. The revised design is `ok`, conditional on checkpointing
Phase 2 separately before implementation.

## Findings

### R2-01 - Stale interpretation cache remains valid

- Severity: must-fix
- Evidence: `ensure_technical_judgment()` currently returns any valid v1 judgment with an interpretation,
  while `_valid_interpretation()` has no algorithm/signal version.
- Repair: interpretation gains `technical_signal_contract.v2.1`. Core v1 remains compatible; stale
  interpretation is rebuilt from resonance or removed when only core data exists.

### R2-02 - Volume reliability contract lacked an executable date rule

- Severity: must-fix
- Evidence: the first revision said `inside 21 bars` without defining date parsing, an unknown date, or the
  function boundary.
- Repair: exact helper signatures and fail-neutral date behavior are now specified.

### R2-03 - Evidence priority could drop real divergence

- Severity: must-fix
- Evidence: interpretation admits at most two counter-evidence items. Without ordering, generic
  overextension could occupy the slot before confirmed divergence.
- Repair: false breakout/rebound remains first, pivot divergence precedes overextension, BIAS remains last,
  and evidence text is deduplicated.

### R2-04 - Indicator-series ownership was implicit

- Severity: must-fix
- Evidence: pivot comparison needs RSI/MACD series, while `_compute_base_indicators()` returns only snapshots.
- Repair: implementation reuses canonical `_rsi`/`_macd`; `macd_hist_prev` comes from the existing MACD
  computation. No duplicate formula is introduced.

### R2-05 - Score propagation lacked formal evidence

- Severity: must-fix
- Evidence: corrected volume can alter the technical pillar and final recommendation near a threshold.
- Repair: formal acceptance must record per-stock pre/post trend-health and volume component deltas; any
  recommendation movement must be fully explained by the corrected component.

## Scope Audit

- No renderer analysis, new data source, target formula, risk rule, recommendation threshold, LLM behavior,
  or Phase 3 feature was introduced.
- Deleting the zero-call legacy helper still makes the `+90` target / `+140` hard stop credible.
- Runtime implementation must not begin until Phase 2 has a separate checkpoint, otherwise the budget and
  regression baseline are not auditable.

## Result

`implementation_ready: yes`. The Phase 2 checkpoint precondition is satisfied by `087591d`.
