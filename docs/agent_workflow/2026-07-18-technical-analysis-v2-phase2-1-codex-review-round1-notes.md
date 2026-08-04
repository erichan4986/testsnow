# Technical Analysis v2 Phase 2.1 - Codex Self-Review Round 1

## Verdict

`needs_revision` before the inline design repair; all findings below were accepted and applied.

## Findings

### R1-01 - Unadjusted volume across a corporate action

- Severity: must-fix
- Evidence: `technical_analyzer.py` repairs OHLC but records `volume_adjusted: False`. The original design
  would compare post-action volume with a pre-action baseline and could create a false spike.
- Repair: in-window unadjusted corporate-action gaps now force the volume component to neutral and add an
  analysis-confidence limitation. Out-of-window gaps do not suppress current evidence.

### R1-02 - Five-session direction can hide the latest breakdown

- Severity: must-fix
- Evidence: a positive five-day return can coexist with a large final down bar, the exact shock pattern that
  exposed the current defect.
- Repair: context now uses the latest completed bar plus current MA20 position. Mixed combinations remain
  neutral. The old monotonic five-day volume adjustment is explicitly deleted.

### R1-03 - MACD has two active classification paths

- Severity: must-fix
- Evidence: `_build_advisors()` also classifies MACD from signs alone, independently of the overextension
  scan.
- Repair: one adjacent-histogram classifier now feeds both advisor and scan contracts.

### R1-04 - Scan schemas and cache routing were ambiguous

- Severity: must-fix
- Evidence: the design named two fields but did not define their family tags or old-payload behavior.
- Repair: both schemas now carry explicit families. Unknown legacy family is fail-closed and is never inferred
  to be pivot divergence from prose.

### R1-05 - Pivot materiality used the wrong ATR time

- Severity: must-fix
- Evidence: current ATR can be inflated by a later shock bar and incorrectly suppress an earlier valid pivot
  relation.
- Repair: materiality uses ATR14 at the second pivot; signal age is defined by exact index distance.

## Result

The revised design closes all Round 1 findings without adding a second score owner or expanding into Phase 3.
