# Periodic External Evidence Map - Implementation Review Round 2

Verdict: fixed

## Findings

- A forged validated display could repeat one external `unit_id`; identical
  observations then collapsed silently instead of failing closed.
- The output authority and no-prose boundary needed an explicit regression
  test rather than relying only on code inspection.
- The first implementation exceeded the +650 runtime hard stop when the mapper
  was counted together with the shared scanner reader and pipeline hook.

## Repairs

- Reject duplicate external unit identities before extraction.
- Added a recursive contract test proving that no text, content, title, URL, or
  source excerpt enters the map and that all consumer eligibility stays false.
- Removed layout-only and repeated runtime lines without adding another parser
  or selector. Runtime delta is now +644 against `cd80dec`.

## Verification

The duplicate identity test went RED then GREEN. The no-prose test was GREEN.
The focused scanner, mapper, and synthesis suite passed after compression.
