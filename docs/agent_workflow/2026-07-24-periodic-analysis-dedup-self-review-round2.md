# Periodic Analysis Dedup Self-Review Round 2

## Verdict

OK after repair.

## Findings And Repairs

1. **Read-count test ambiguity:** `Path.stat` calls are not source reads. The
   test will count only `Path.read_text` for matching cache files.
2. **Failure caching:** failed reads must remain diagnostic rows and must not be
   retried by another projection in the same run.
3. **Latest semantics:** latest remains max `(st_mtime_ns, path)` rather than
   highest report year; historical MetricSeries order remains period then path.
4. **Budget loophole:** test/docs lines do not satisfy runtime reduction. Both
   batch budgets are measured only across `scripts/` against `d1be180`.
5. **Boundary preservation:** strict FinancialScan source admission is not
   moved or compressed in this task; it is intentional defense, not duplication.

No blocker or unresolved must-fix remains. Implementation may proceed in Batch
A then Batch B, with a fresh RED/GREEN cycle for each.
