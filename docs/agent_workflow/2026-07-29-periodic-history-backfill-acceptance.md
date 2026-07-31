# Periodic History Backfill Acceptance

## Verdict

`PASS_WITH_ENVIRONMENT_WARNINGS`

The annual-report backfill, deterministic extraction, history-series intake and
latest-report selection all passed. Full report quality checks were blocked only
by unavailable technical market data in the sandbox; annual source-boundary and
prose checks passed for all three reports.

## Published Official Reports

| Stock | Year | Official source | Status | Revenue | Net profit | Operating cash flow |
|---|---:|---|---|---:|---:|---:|
| 中际旭创 | 2023 | CNINFO | ready | 1,071,800.00万元 | 217,400.00万元 | 189,700.00万元 |
| 中际旭创 | 2024 | CNINFO | ready | 2,386,200.00万元 | 517,100.00万元 | 316,500.00万元 |
| 复旦微电 | 2023 | CNINFO | ready | 353,600.00万元 | 71,900.00万元 | -70,816.66万元 |
| 复旦微电 | 2024 | CNINFO | ready | 359,000.00万元 | 57,300.00万元 | 73,246.56万元 |
| 黑芝麻智能 | 2023 | HKEX | official_report_not_available | - | - | - |
| 黑芝麻智能 | 2024 | HKEX | ready | 47,425.20万元 | 31,331.50万元 | -118,975.40万元 |

Every ready row has a matching official URL, issuer/year/type metadata, source
PDF, extracted text hash, evidence block and zero structured-fact diagnostics.
The 复旦微电 2024 net-profit value uses the supported rounded core summary
(`5.73亿元`); the adjusted-basis value was rejected.

## Cache Integrity

New text hashes:

- 中际旭创 2023: `98b1902eb39f61329fd3cd266a68b142067cc0a21ff43d77ac4cbeb26eef9337`
- 中际旭创 2024: `b6cddccd8b2240144cf29acedf4b7fee28522ceccc292fecf3baa04a59b22eb0`
- 复旦微电 2023: `374fd024ef32339015b12925436fef98abe8eec28df97f9f3b1bdf5838257d7d`
- 复旦微电 2024: `b4774cf70807527dac13eba844ae611e287816261ff560a12e4abdfc5aa74438`
- 黑芝麻智能 2024: `e580402f7f9a4721087e402fed8e868360c5d1c44356708d1b12149f4a7a4a4c`

Protected 2025 hashes remained byte-for-byte unchanged:

- 中际旭创: `e1bacdb99700b8a44f17f5109e8e69f14961a339757e1c6e7d409282b329662e`
- 复旦微电: `f8d5a7011b390148208f2e12bb8e406e355cd992868d112e45bd6f6f57c684f3`
- 黑芝麻智能: `2cf85989af8c5739019bdd5b4e704512f6a61189f27c1303931e1eaedd709b18`

## History Consumption

- 中际旭创: revenue, net profit and operating cash flow each contain ordered
  periods `2023, 2024, 2025`; FinancialScan status is `ready`.
- 复旦微电: the same three ordered periods are present; FinancialScan status is
  `ready`. The 2023 negative operating-cash-flow base is retained as an explicit
  deterministic diagnostic.
- 黑芝麻智能: all officially available periods are ordered `2024, 2025`;
  FinancialScan status is `ready`. Loss and negative-base diagnostics are
  retained rather than normalized away.
- MetricSeries and FinancialScan remain compute-only in this batch
  (`report_eligible=false`, `scoring_eligible=false`). No new report section,
  score, target price, risk or recommendation behavior was introduced.

## Blocker Repairs

Three deterministic defects were repaired with tests:

1. HKEX discovery now filters annual-report titles by the requested year.
2. Adjusted-basis profit sentences cannot override the core net-profit metric.
3. Current-report consumers select by report year first, using mtime/path only
   for same-year variants. This prevents newly copied 2024 history from
   replacing the existing 2025 filing.

The refreshed reports confirm 2025 current facts:

| Stock | Revenue | Net profit | Operating cash flow |
|---|---:|---:|---:|
| 中际旭创 | 382.40亿元 | 107.97亿元 | 108.96亿元 |
| 复旦微电 | 39.82亿元 | 2.32亿元 | 7.84亿元 |
| 黑芝麻智能 | 8.22亿元 | -14.25亿元 | -9.85亿元 |

## Verification

- Combined focused tests: `180 passed in 6.39s`.
- Full repository tests: `2783 passed, 16 skipped in 56.79s`.
- `tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Source-boundary checks: PASS for all three reports.
- Prose checks: PASS with existing cross-section/theme warnings.
- Report generation: all three no-PDF entries exited 0 and refreshed Markdown
  and HTML outputs.
- Report quality checks: FAIL only for missing daily/weekly/volume/volatility
  technical data after network and market-data fallbacks failed. No annual
  source, identity, citation or financial-fact error was reported.

Fresh reports:

- `reports/中际旭创_20260729.md` (16,376 bytes)
- `reports/复旦微电_20260729.md` (10,581 bytes)
- `reports/黑芝麻智能_20260729.md` (15,739 bytes)

## Scope And Deviations

- No LLM prompt, scoring, target-price, risk, recommendation, technical-analysis
  or report-layout behavior changed.
- No Xueqiu detail page or logged-in Chrome/CDP session was used.
- Raw caches and generated reports follow repository ignore policy.
- Deviation from the original data-only plan: staged validation exposed three
  runtime correctness defects. Their narrow TDD repairs are documented in the
  blocker-repair design and are included in this acceptance scope.
