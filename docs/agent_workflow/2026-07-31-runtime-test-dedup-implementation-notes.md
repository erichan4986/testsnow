# Runtime And Test Deduplication Implementation Notes

## Result

`PASS`

The three batches were completed without changing report content, scoring,
technical analysis, risk rules, citations, data collection, or LLM prompts.
Pre-existing Chapter 2 gross-margin changes were preserved.

## Changes

### Batch A

- Deleted the shadowed `scripts/utils/reporter.py`; the active owner remains
  `scripts/utils/reporter/report_manager.py` through the `utils.reporter`
  package.
- Deleted nine zero-call private helpers and the two constants used only by a
  deleted helper.
- Added `tests/test_runtime_hygiene.py` to enforce the unique owner and dead
  definition contracts.

### Batch B

- Replaced four duplicated named entry implementations with compatibility
  wrappers around `run_stock_report.main()`:
  - `run_中际旭创.py`
  - `run_圣邦股份.py`
  - `run_黑芝麻智能.py`
  - `run_中简科技.py`
- Added a parameterized forwarding contract for all four wrappers.
- Moved surviving entry behavior coverage to the generic owner tests: nested
  interaction fields, fast-test network isolation, cached Zhihu reuse, and
  configured source features.
- Deleted three superseded stock-specific entry test files.

### Batch C

- Merged three identical annual-card admission test bodies while retaining all
  11 parameter cases.
- Merged two competition-risk and two capital-outflow negative test bodies
  while retaining all original cases.
- Deleted the permanently skipped, not-yet-implemented pipeline observability
  test file.

## RED / GREEN Evidence

- Batch A RED: `2 failed, 1 passed`; GREEN: `3 passed`.
- Batch A affected suites: `273 passed, 3 skipped`.
- Batch B RED: generic contracts passed and four wrapper cases failed as
  expected (`14 passed, 4 failed`); GREEN: `19 passed`.
- Entry/config regression suites: `71 passed`.
- Batch C focused suites: `293 passed`.

## Final Verification

- Full suite: `2810 passed, 10 skipped in 53.93s`.
- Collection: 2,834 -> 2,820 tests. The removed collection consists of
  superseded entry tests and permanent skips; merged parameter cases were
  retained.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- `python3 scripts/run_黑芝麻智能.py --offline-smoke`: exit 0; Markdown and HTML
  were generated under `/tmp/testsnow_offline_smoke`, with no PDF or live
  collection path.

## Line Accounting

| Area | Baseline | Final | Net |
|---|---:|---:|---:|
| Runtime Python | 68,592 | 67,156 | -1,436 |
| Test Python | 63,754 | 63,045 | -709 |
| Named entry scripts | 1,301 | 92 | -1,209 |

Runtime files decreased from 171 to 170. Test files decreased from 172 to 170.

## Deviations

- The generic Markdown parser already parsed indented
  `interactions.likes/comments` because it strips frontmatter keys before
  comparison. No runtime change was needed; a regression test now locks this
  behavior.
- `run_stock_report.py` contained one `PDF已生成` success log, not two. The
  hygiene test confirms the count is one, and no valid log was removed.
- The four wrappers total 92 lines rather than the design estimate of 40-60.
  The extra import-path setup keeps direct execution and file-based test imports
  robust; the overall runtime reduction still exceeds the hard target.

## Deferred

- `judgment_generator.py` and `wechat_sogou_fetcher.py` remain because they are
  documented manual capabilities, despite having no active runtime imports.
- Conditional environment-dependent skips and pytest marker infrastructure
  remain active and were not treated as dead tests.
- A post-cleanup AST scan found 11 exact runtime function-body pairs. Every
  named helper has active local callers; the pairs cross ownership boundaries
  such as quality/source-boundary checks, annual extraction, curated external
  material, renderer formatting, and WeChat discovery. They were not deleted
  or moved merely to reduce line count. A future shared-helper batch would need
  contract tests for those boundaries first.
- Seven remaining duplicate test bodies are small local fakes or fixture
  builders. Moving them into global fixtures would reduce only a few lines and
  increase coupling, so they remain local by design.
