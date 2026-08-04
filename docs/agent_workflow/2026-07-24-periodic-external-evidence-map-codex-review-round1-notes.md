# Periodic External Evidence Map - Codex Review Round 1

## Verdict

`needs_revision`, repaired in the design before Round 2.

## Findings And Repairs

1. **Target-with-peer numeric ownership was unsafe.** A comparative card can
   concern the target while its number belongs to a peer. The design now admits
   only `entity_scope=target`; both peer and target-with-peer cards are out of
   scope for v1 mapping.
2. **The supplied scan was not bound strongly enough to MetricSeries.** Matching
   stock/schema/counters cannot prove identical values. The mapper now rebuilds
   the deterministic scan and requires byte-equivalence before using finding
   ids.
3. **Bare-year parsing could misread publication dates.** Month/day/quarter
   tokens are now rejected before the bare-year annual rule.
4. **External currency was underspecified.** RMB or no currency marker is
   accepted for Chinese amount units; explicit HKD/USD language is rejected.
5. **Identity and counters were ambiguous.** The design now distinguishes all
   target units from financial target units and fixes observation/mapping hash
   inputs, duplicate collapse, and collision failure behavior.

## Remaining Risk For Round 2

Review period/modality inheritance, numeric range grammar, precision math,
value-basis ambiguity, exact finding links, unavailable/partial semantics, and
pipeline ownership.
