# Periodic Report History Backfill Design

## Goal

Backfill official 2023-2024 annual-report caches for 中际旭创、复旦微电 and
黑芝麻智能 so the existing MetricSeries and FinancialScan paths can evaluate
cross-year filing facts. Preserve the accepted 2025 caches byte-for-byte.

## Current State

- The canonical cache contains 2025 annual text for all three stocks.
- No 2023 or 2024 annual/semiannual cache exists.
- MetricSeries already reads every matching annual cache and groups annual and
  semiannual reports into separate series.
- A-share discovery supports official CNINFO annual reports. HK discovery
  supports official HKEX annual/interim reports.

## Options Considered

1. **Run the existing single-report preparation entry into a staging directory
   (selected).** This adds no runtime code, reuses tested official discovery,
   and makes each missing period independently auditable.
2. Add a persistent batch backfill CLI. This is repeatable but unnecessary for
   a six-report pilot and would add another orchestration owner.
3. Add annual and semiannual multi-type intake now. This changes the pipeline
   contract and would not improve like-for-like three-year annual comparisons;
   defer it until the annual pilot proves useful.

## Scope And Source Policy

- Stocks: 中际旭创 (`300308`), 复旦微电 (`688385`), 黑芝麻智能 (`02533`).
- Requested periods: 2023 and 2024 annual reports. Existing 2025 caches are
  inputs to validation, not download targets.
- Sources: CNINFO for A shares and HKEX for the Hong Kong share.
- Do not use prospectuses, earnings releases, media articles, broker research,
  or social sources as substitutes for an unavailable annual report.
- Do not write Knowledge notes and do not invoke an LLM.
- Do not access Xueqiu, Chrome/CDP, Zhihu, WeChat, or external-material paths.

## Data Flow

1. Run `scripts/prepare_annual_report_materials.py` once per missing stock/year
   with `--report-type annual`, a temporary cache directory, and no
   `--write-knowledge`.
2. Validate the staged text/meta pair before any canonical write:
   - official domain and stock identity match;
   - report title/year/type match the requested period;
   - extracted text is non-empty and has a SHA-256 in metadata;
   - evidence-pack and structured-fact builders complete without exception;
   - revenue, net profit and operating cash flow are either exact supported
     filing facts or carry an explicit missing/unsupported diagnostic.
3. Copy only validated missing-period text/meta/source PDF files into the
   canonical cache. Never overwrite an existing canonical path.
4. Rebuild the existing annual MetricSeries and FinancialScan packs from the
   canonical cache; no new storage format is introduced.
5. Generate fresh no-PDF reports for the three stocks only after the series
   validation passes, then run quality/source/prose gates.

## Availability And Success Rules

- 中际旭创 and 复旦微电 must have 2023, 2024 and 2025 annual points for each
  supported metric that is present in all three filings.
- 黑芝麻智能 may lack a 2023 standalone HKEX annual report because an issuer
  may not have published one before listing. `official_report_not_available`
  is acceptable only when HKEX discovery returns no matching filing; the run
  must not silently substitute another document. Its available annual periods
  must still form a valid ordered series.
- A metric absent from a filing is not synthesized. It remains an explicit
  diagnostic and cannot be used in a derived cash-conversion calculation.
- The backfill is idempotent: a second run finds canonical paths present and
  performs no download or overwrite for those periods.

## Failure Modes And Gates

| Failure mode | Visible symptom | Stop gate |
|---|---|---|
| Wrong issuer/year PDF | Metadata or title mismatch | Reject staged period |
| Empty/broken PDF extraction | Empty text or no evidence blocks | Reject staged period |
| Unit/currency mismatch | Structured fact rejected | Do not publish that metric |
| Existing 2025 cache overwritten | Hash changes | Hard stop and restore backup |
| Missing HK 2023 report disguised as success | Substitute document appears | Hard stop |
| Partial canonical copy | Text without matching metadata/source | Roll back that period |
| Historical cache changes current display unexpectedly | Report/source gate regression | Keep caches, block report acceptance |

## Verification

- Record before/after hashes for all existing 2025 text files.
- Record each discovery URL, title, publication date, extracted character
  count, and text hash without exposing credentials.
- Verify annual cache ordering and MetricSeries point periods directly.
- Verify FinancialScan diagnostics and derived cash-conversion inputs.
- Run focused cache/intake/series/scan tests, CI grep gates and
  `git diff --check` if any tracked file changes.
- Report generated data files separately from tracked source changes.

## Self Review Round 1

The first draft proposed downloading 2023-2025. That could overwrite the
manually accepted 2025 source text with a different PDF extraction. The design
now stages only missing 2023/2024 periods and treats the 2025 hashes as a hard
immutability gate.

## Self Review Round 2

The initial success rule required three annual reports for every stock. That is
not valid for a recently listed HK issuer. The final rule accepts an explicitly
unavailable 2023 HKEX filing, forbids substitutions, and validates all available
periods without fabricating a third point.
