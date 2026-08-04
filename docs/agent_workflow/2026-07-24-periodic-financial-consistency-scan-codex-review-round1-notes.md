# Periodic Financial Consistency Scan - Codex Self-Review Round 1

> Date: 2026-07-24
> Verdict after repair: `ok_for_round2`

## Findings And Repairs

1. **Must-fix: hidden second formula owner.** The draft allowed the scanner to
   recompute growth and cash conversion. That contradicted its own ownership
   rules. The design now trusts the in-process canonical builders, validates
   typed structure/refs/finite values only, and never reimplements either
   formula.
2. **Must-fix: derived-series comparability was underspecified.** The repaired
   derived-series id now explicitly includes `value_basis`; inputs must share
   basis, currency, and unit, and derived rows group by basis.
3. **Must-fix: cashflow threshold API was implicit.** The design now locks the
   exported constant and predicate signature, and requires both the existing
   risk builder and scanner to call the same predicate.
4. **Must-fix: duplicate source series had winner ambiguity.** Duplicate ids now
   reject every occurrence rather than using input order.
5. **Must-fix: counts and status could be interpreted as raw input counts.** All
   counters now explicitly count admitted rows/points/unique intervals.
6. **Must-fix: diagnostic propagation could leak arbitrary upstream fields.**
   The copied field allowlist is now exact.
7. **Nice-to-have accepted: finding collisions.** Duplicate series are rejected
   first; any residual conflicting finding identity is removed and diagnosed.

## Scope Audit

- No raw-text extractor changes.
- No report/scoring/risk/target/technical/prompt consumer.
- No new materiality threshold.
- The only existing-rule change is exporting the exact cashflow predicate and
  making its current caller use it.

No blocker remains for the second self-review.
