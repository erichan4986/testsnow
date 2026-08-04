# Technical Analysis v2 Phase 2.2 Compression Notes

## Result

- Behavior-preserving compression accepted: yes
- Runtime delta against `fdd0941`: `+355` across the six Phase 2.2 runtime files
- Runtime delta including the two report-skill import cleanups: `+332` across eight files
- Previous Phase 2.2 five-file delta: about `+401`
- No scoring, risk, target, recommendation, collection, or report contract change

## Changes

- Reused `technical_indicators.atr` and removed the duplicate ATR implementation.
- Removed definition-only `_is_support_resistance`.
- Consolidated scenario source lookup into `_scenario_candidate`, shared by ladder construction and cache provenance validation.
- Preserved strict source/source-field combinations, side checks, ordering, and 0.5% dedupe.
- Reduced status/config boilerplate without introducing a new abstraction layer.

## Verification

- Structure/pattern/trend: 32 passed
- State machine and scoring/risk downstream: 95 passed
- Renderer/report quality: 117 passed
- Full suite: 2532 passed, 16 skipped
- CI grep gates: passed
- `git diff --check`: clean

## Follow-Up Closure

The full-suite chart failure had two separate causes. The immediate defect was an early return from the
core-only technical judgment projection, which skipped an already generated chart. A shared chart helper
now serves full, core-only, and legacy projections. The first canonical-import slice also removed
`sys.path` mutation from chart and data skills, so the chart integration test passes in isolation without
an externally supplied `PYTHONPATH`.

## Deviation

The original Phase 2.2 `+180` budget was retired. The accepted implementation cannot meet it without
removing approved facts or provenance validation. This compression uses the reviewed `+360` hard stop for
the six Phase 2.2 runtime files.
