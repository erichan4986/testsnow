# Periodic Analysis Dedup Self-Review Round 1

## Verdict

Needs revision.

## Findings

1. The first draft treated one evidence pack as reusable everywhere. Existing
   fulltext display uses `annual_report`/`semiannual_report`, while structured
   facts use `annual`/`semiannual`; sharing one pack would change contracts.
2. Sharing decimal formatting would conflate MetricSeries two-place rounding,
   FinancialScan canonical-string rejection, and ExternalMap source precision.
3. A cache bundle keyed only by report year would collapse distinct documents
   for the same year and hide duplicate/alternate cache diagnostics.
4. Replacing public wrappers would break tests and external preview callers.

## Repairs Applied

- Keep separate latest-cache display evidence and per-file structured evidence.
- Share only finite Decimal conversion; retain local syntax and formatting.
- Material rows are path-identified and preserve every discovered cache.
- Keep all public wrappers and route them through shared private machinery.
