# Periodic External Evidence Map - Codex Review Round 2

## Verdict

`ok`; implementation-plan ready.

## Round 1 Closure

All five Round 1 findings are closed: target-with-peer exclusion, exact scan
binding, date-safe period parsing, foreign-currency rejection, and stable
counter/id contracts are explicit in the design.

## Round 2 Findings And Repairs

1. **Report-period precedence needed a real-source case.** A unit may contain a
   publication date and an explicit half-year period. The design now selects
   the last explicit annual/semiannual period before applying calendar-date
   rejection to a bare-year fallback.
2. **Forecast context needed an exit.** Explicit actual/reported language now
   resets inherited forecast modality within the card.
3. **Multi-metric and range grammar was ambiguous.** Longest aliases, metric
   clause boundaries, endpoint-unit equality, and negative-sign parsing are
   fixed.
4. **Relation semantics could be overread.** Every mapping now states
   `adjudication=none` and `official_fact_mutated=false`; confirm/contradict are
   compatibility results, not source-priority decisions.

## Final Audit

- no LLM/fuzzy matching;
- no peer-to-target mapping;
- no publication-time period inference;
- no duplicate MetricSeries validator or financial formula;
- no report/scoring/risk consumer;
- no raw source prose in output;
- exact scan/MetricSeries binding;
- deterministic identities, no cap, fail-closed ambiguity;
- runtime hard stop remains +650 lines against `cd80dec`.

No blocker or must-fix remains.

Implementation-plan consistency check added the explicitly specified
`observations` list to the top-level pack; the earlier count-only envelope
could not carry the observation contract defined by the design. This is a
schema completion, not a changed ownership boundary.
