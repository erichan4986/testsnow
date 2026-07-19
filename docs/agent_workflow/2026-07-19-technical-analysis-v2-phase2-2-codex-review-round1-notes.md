# Technical Analysis v2 Phase 2.2 Codex Review Round 1

## Verdict

`needs_revision`

The ownership split is sound, but the first draft exposed four ambiguities that would create hidden second
rules if implemented literally.

## Findings And Repairs

### R1. A latest close could be mistaken for a confirmed pivot

- Risk: appending the latest close to the path and later labeling the segment by direction could imply a
  confirmed reversal at the right edge.
- Repair: `end_kind=latest_close` is mandatory and the judgment may call it only a terminal observation.
  Confirmed high/low wording is reserved for `confirmed_swing_indices()` output.
- Status: closed in design section 5.1.

### R2. Scenario levels could become an undeclared target formula

- Risk: selecting a nearest MA or zone and calling it rebound/reversal may be read as a forecast.
- Repair: every value must be an exact member of accepted MA/support/resistance/invalidation inputs, retain a
  `level_source`, and render as a conditional observation level. No interpolation or Fibonacci fallback is
  allowed.
- Status: closed in sections 5.4 and 5.6.

### R3. Shock volume could diverge from Phase 2.1 reliability

- Risk: a second volume baseline or independent corporate-action decision would contradict trend health.
- Repair: terminal shock reuses the preceding-20 baseline and the same `volume_reliable` result. Unreliable
  volume is omitted from shock prose rather than rescored.
- Status: closed in sections 5.2 and 5.3.

### R4. Structure narration could override the accepted trend

- Risk: a recent up segment under a bearish regime could be rendered as reversal.
- Repair: analyzer emits facts only; state-machine wording is regime-aware, labels counter-trend segments as
  repair, and cannot mutate `trend.state` or `action.state`. Downstream identity is a required test.
- Status: closed in sections 5.4 and 7.

## Scope And Budget Review

- Five runtime owners are justified: two fact producers, one analyzer bridge, the existing decision owner,
  config, and the pure renderer projection.
- No second selector or indicator family is introduced.
- The `+120` target is credible only if repeated weekly/daily renderer prose is replaced rather than retained.
  The `+180` hard stop is appropriate.

## Final Result

The inline specification review also tightened bullish/range level selection, removed `reversal` as an output
state, and added hard renderer row budgets. All Round 1 findings are closed in the written design. No blocker
or unresolved must-fix remains. The design is ready for user review before an implementation plan is written.
