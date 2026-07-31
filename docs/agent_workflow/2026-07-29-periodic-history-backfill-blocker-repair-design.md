# Periodic History Backfill Blocker Repair

## Scope

Fix only the two deterministic defects exposed by the staged 2023-2024 annual
backfill. Do not change report structure, financial formulas, source priority,
semiannual behavior, scoring, risk, recommendation, or LLM prompts.

## Defect 1: HKEX Cross-Year Selection

The live HKEX title-search endpoint returned all available annual reports even
when `from`/`to` parameters requested an earlier window. The current reader
selects the first annual-report title, so a 2023 request for 黑芝麻智能 returned
`2025年報`.

Add an optional `report_year` argument to `find_hk_periodic_report`. When set,
an entry is eligible only if its title contains that four-digit year. Preserve
the old behavior when the argument is omitted. `discover_hkex_periodic_report`
must always pass its requested year to the reader. If no matching title remains,
raise the existing `No HKEX ... found` error.

## Defect 2: Adjusted Profit Overrides Core Profit

`_line_metric` correctly found the 2024 core table value for 复旦微电
(`57,259.51万元`) but later preferred an explicit-unit sentence describing
`剔除调整项目后` profit (`626,808,711.76元`). That adjusted amount is not the
core `归属于上市公司股东的净利润` metric and cannot replace it.

Before ranking candidates, reject a candidate only when the bounded text before
the exact metric label contains an explicit adjusted-basis qualifier:
`剔除`, `经调整`, `經調整`, `调整后`, or `調整後`. Inspect both text before a
line-level label and the source context before a regex-level candidate, because
the latter starts at the label. Keep the existing explicit-unit/context-unit
ranking for all non-adjusted candidates.

## Defect 3: Backfilled History Overrides the Current Report

The latest-report adapters rank cache files by filesystem modification time.
Publishing a historical cache therefore makes a newly copied 2024 file newer
than the pre-existing 2025 file and incorrectly replaces the current filing in
core facts, narrative cards and the annual memo.

Use one shared cache-selection key everywhere: report year first, then mtime,
then path for deterministic same-year variants. Historical MetricSeries loading
continues to read every period in year order; only latest-report consumers use
this selection key.

## Tests

1. A mixed HKEX payload ordered `2025年報`, `2024年報` returns the 2024 item
   when `report_year=2024`.
2. The same payload returns `None` for `report_year=2023`.
3. Calling `find_hk_periodic_report` without a year retains first-match behavior.
4. Discovery passes the requested year into the reader and fails when only a
   different-year annual report exists.
5. A financial fixture containing a unitless core table row under
   `单位：万元` plus a later adjusted explicit-unit sentence returns the core
   table value.
6. A normal explicit-unit core sentence remains preferred, proving that the
   filter is qualifier-specific rather than a general priority reversal.
7. A 2025 cache with an older mtime outranks a newly copied 2024 cache in both
   the direct latest-only wrapper and the pipeline skill.
8. Same-year variants retain the existing mtime/path tie-break behavior.

## Failure Modes

- Titles without a numeric year are rejected only in year-bound discovery, not
  in backward-compatible direct reader calls.
- The adjusted-basis filter examines only the bounded prefix before the exact
  label; words such as “同比调整” after the amount cannot suppress a core fact.
- No fuzzy company matching, alternate document substitution, or manual metric
  override is introduced.
- Cache publication time can never override an explicitly newer report year.

## Self Review Round 1

An initial proposal changed candidate ranking so contextual table units always
beat explicit units. That would regress valid narrative statements. The final
design keeps ranking unchanged and removes only candidates with an explicit
adjusted-basis prefix.

## Self Review Round 2

Filtering only full lines would miss regex-generated candidates that begin at
the metric label and discard their prefix. The final design requires bounded
source-context inspection for those candidates and locks it with the mixed
table/narrative fixture.

The history backfill also exposed an independent selection defect: mtime is a
valid tie-breaker only within one report year. Reusing a single year-first key
avoids fixing the file finder while leaving the row-based pipeline owner stale.
