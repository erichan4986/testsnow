# Periodic External Evidence Map - Implementation Review Round 1

Verdict: fixed

## Findings

- Forecast phrases containing `realize` were classified as reported because the
  generic reported marker won before the forecast marker.
- Period and modality context flowed across source-block boundaries inside one
  card, contrary to the design contract.
- Decline and loss wording lost its negative direction during numeric parsing.

## Repairs

- Added marker-order parsing that keeps `expected to realize` in forecast mode
  while allowing later explicit actual-result wording to reset the mode.
- Reset period and modality context on source/document/block identity changes.
- Normalize decline rates and loss amounts to negative Decimal ranges.

## Verification

All three findings were reproduced with RED tests and repaired to GREEN. The
complete mapper suite passed after the fixes.
