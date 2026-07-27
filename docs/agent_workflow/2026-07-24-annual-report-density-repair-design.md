# Annual Report Density Repair

## Scope

Only repair the annual-report path. Do not change technical data collection,
scoring, target price, risk, recommendation, broker material, external material,
or LLM prompts.

## Root Causes

1. A source block before the first Markdown heading has no coverage section.
2. Unitless annual-report table rows are treated as yuan even when the nearest
   table header says `单位：万元`.
3. Chapter 4.1 gives `argument_complete` a hard ranking priority and uses a
   narrow role budget, hiding concrete product, customer, operating, and
   financial facts while sometimes retaining generic prose.
4. Incomplete annual fragments can pass role admission and consume display
   slots.

## Design

1. Add a deterministic `document-preamble` section when substantive text
   precedes the first Markdown heading. Keep strict section-reference validation.
2. In financial row extraction, prefer an amount with an explicit unit. For a
   unitless table row, use only the nearest preceding `单位：...` marker within
   the bounded local table context; otherwise retain the current yuan default.
3. Keep MetricSeries and FinancialScan compute-only. Correct filing facts flow
   through the existing annual memo and citation allocator.
4. Rank annual display rows by a weighted evidence-value score rather than a
   hard `argument_complete` sort key. Numeric changes, named products,
   customers, shipments, validation, and causal explanations outrank generic
   plans.
5. Use role budgets `business=3`, `operating=4`, `market=3`, `technology=3`,
   `financial=6`. This is a maximum of 19 rows, not a minimum. The added slots
   are reserved for concrete operating changes, target-company market facts,
   and distinct financial performance/quality/driver facts.
6. Reject visibly incomplete date/period tails before ranking.

## Failure Modes And Tests

- Preamble source loses its section: exact block-to-preamble regression test.
- A-share `万元` table is scaled as yuan: compact table-unit fixture.
- An explicit `亿元` sentence loses to a unitless table row: precedence fixture.
- A distant unit marker contaminates another row: bounded-context negative test.
- Generic complete prose beats a concrete progress fact: ranking regression.
- Broken `截至 ... 止` fragment reaches 4.1: admission regression.
- Expanded budgets dump all candidates: exact per-role budget/hidden-count test.

## Self Review Round 1

- Rejected direct rendering of MetricSeries/FinancialScan because their contract
  is compute-only and current caches provide only one annual period.
- Narrowed unit inference to local preceding context; explicit units always win.
- Kept strict citation/source-boundary behavior unchanged.

## Self Review Round 2

- Avoided an unlimited display path. Nineteen rows is the hard editorial maximum,
  while projection and deduplication still run before budgeting.
- Kept source text verbatim except existing deterministic heading/noise cleanup.
- Validation must use the three local annual reports; missing technical market
  data is explicitly outside the verdict.

## Implementation Acceptance

- Full annual material remains available to the memo/snapshot; only the Chapter
  4 display projection removes headings, governance text, catalog fragments,
  unsupported self-comparison, duplicate facts, and incomplete tails.
- The display selector keeps one owner and one budget path. A final compression
  audit found no second selector or duplicate renderer owner to remove; turning
  the explicit delete-only projections into a generic rule table would reduce
  auditability without materially reducing runtime.
- Focused annual tests: `637 passed`. Full offline suite: `2778 passed, 16
  skipped`. CI grep gates and `git diff --check` passed.
- Fresh manually reviewed projections are available at
  `reports/中际旭创_20260727.md`, `reports/复旦微电_20260727.md`, and
  `reports/黑芝麻智能_20260727.md` in the main workspace. Their remaining
  technical-data omissions are local collection limitations and were excluded
  from this annual-only verdict.
