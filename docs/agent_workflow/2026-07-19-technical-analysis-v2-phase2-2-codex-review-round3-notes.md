# Technical Analysis v2 Phase 2.2 Codex Review Round 3

## Verdict

`ok` after inline repairs.

## Edge-Case Findings

### E1. Shock ATR included the shock bar itself

- Risk: an extreme range inflates ATR14 and suppresses its own abnormality classification.
- Repair: compare terminal true range with ATR14 calculated through the preceding row.
- Status: closed.

### E2. Missing volume history incorrectly suppressed valid price anatomy

- Risk: a visibly abnormal candle disappears because the volume series has fewer than 21 usable rows.
- Repair: price and volume readiness are independent. Price anatomy survives with
  `volume_status=unavailable`; only its volume clause is omitted.
- Status: closed.

### E3. One outside bar can be both a strict high and strict low

- Risk: ordering the two same-index pivots arbitrarily creates a zero-duration segment and false reversal.
- Repair: omit both roles at that index and record a deterministic limitation.
- Status: closed.

### E4. Scenario cache lacked time/reference provenance

- Risk: levels could remain source-equal but describe a prior close or prior report date.
- Repair: scenario ladder is an object with `as_of`, `reference_close`, and steps; ensure validates both
  against current structural inputs.
- Status: closed.

### E5. Shock evidence priority was unspecified

- Risk: implementers could append shock prose without reconciling it with the bounded primary/counter lists.
- Repair: aligned shock follows hard invalidation/channel break in primary priority; opposing shock precedes
  pivot divergence in counter priority. It cannot mutate action.
- Status: closed.

### E6. Scenario state labels were asymmetric

- Risk: `repair` meant bearish trend repair but was also used for a bullish first-defense level; a range upper
  bound was called continuation.
- Repair: cache and validation use geometric `role` values, while the state machine supplies fixed
  regime-aware labels such as `反抽观察`, `第一防线`, and `区间上沿`.
- Status: closed.

## Final Assessment

- Ownership: one fact layer, one state-machine interpretation owner, pure renderer.
- Look-ahead: confirmed pivots and shifted ATR are explicitly bounded.
- Provenance: path dates/prices and scenario levels remain traceable to current inputs.
- Scope: no new indicator family, target formula, score, risk, recommendation, source, or LLM path.
- Budget: the `+120` target and `+180` hard stop remain credible if duplicate renderer diagnostics are
  replaced.

No blocker or must-fix remains. The design is implementation-plan ready after user confirmation.
