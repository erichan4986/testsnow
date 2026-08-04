# Structured Financial History Source Implementation Notes

## Outcome

Implemented. Historical annual financial series now come from one local,
provider-backed structured cache. The latest annual-report text remains the
only source for current filing core facts, explanations and narrative cards.

No network refresh and no report generation were run in this implementation
turn.

## Runtime Changes

- Added `scripts/utils/structured_financial_history.py` as the single field
  admission, normalization, provenance, cache read/write and source-point owner.
- Added `fetch_structured_financial_history_rows()` to the existing provider
  boundary for A-share and HK raw rows.
- Added `scripts/refresh_structured_financial_history.py` as the only explicit
  network refresh entry.
- Extended MetricSeries with mutually exclusive `fact_packs` / `source_points`
  inputs; both normalize into the existing grouping and growth path.
- Moved the existing percentage-ratio implementation to one shared helper and
  reused it for official facts and API cash conversion.
- Replaced production traversal of all historical annual-text caches with one
  local structured-history cache read.
- Production annual-text intake now reads only the latest annual-report cache.
- Removed the old production historical-text MetricSeries adapter and its
  diagnostic helper.

## Requirement-Test Matrix

| Requirement | Implementation | Test / Evidence |
|---|---|---|
| A-share exact FY fields | `structured_financial_history._selected` | `test_a_share_admits_only_fy_rows_and_exact_fields` |
| HK FY/CNY/exact cash label | same adapter | `test_hk_requires_explicit_fy_cny_and_exact_cashflow_label` |
| Eastmoney HK operating-cash label | same adapter | `test_hk_admits_eastmoney_operating_business_net_cash_label` |
| Stable data hash/no-op write | cache writer | `test_cache_hash_is_stable_and_identical_refresh_is_byte_preserving` |
| Equal provider rows are order-independent | cache builder | `test_cache_is_deterministic_when_equal_provider_rows_change_order` |
| Structurally malformed cache fails closed | cache reader | `test_reader_rejects_hash_valid_record_with_missing_required_field` |
| Compact verified provenance | cache reader | `test_reader_validates_identity_and_emits_compact_source_points` |
| API facts never become core facts | official boundary unchanged | same reader test |
| Provider calls contain no field mapping | `reporter/data_fetcher.py` | three provider tests |
| Failed/empty refresh preserves cache | refresh entry | `test_refresh_entry_resolves_config_and_preserves_cache_on_empty_provider` |
| One source authority per series | MetricSeries admission | `test_metric_series_source_authorities_are_mutually_exclusive` |
| Existing growth and ratio owners reused | MetricSeries + contract helper | API growth/cash-conversion test and official fact regressions |
| API-derived ratio requires matching dimensions | MetricSeries | `test_api_cash_conversion_rejects_mismatched_value_basis_dimensions` |
| Normal report path is cache-only | existing intake skill | missing-history offline test |
| Latest annual material remains active | existing intake skill | filing-core-facts and missing-history tests |
| Old annual text is not scanned for history | `latest_only=True` | `test_skill_reads_only_latest_annual_material_once_per_run` |

## RED / GREEN

- Adapter/cache: module import RED, then 4 tests GREEN.
- Provider boundary: missing provider API RED, then 3 tests GREEN.
- MetricSeries: unsupported `source_points` RED, then API admission/growth/ratio
  tests GREEN.
- Pipeline cutover: old one-year text series RED against two-year cache and
  missing-cache expectations, then GREEN after production cutover.
- Latest-only annual read: older cache was still read RED, then GREEN after
  `latest_only=True` production selection.
- Acceptance repair: provider-order instability, a hash-valid malformed record,
  and mixed-basis API ratio input each reproduced RED, then GREEN after stable
  candidate selection, structural cache validation and dimension admission.
- Live acceptance exposed Eastmoney's exact HK label `经营业务现金净额`; the
  missing series reproduced RED and passed after the exact-label admission was
  added without widening fuzzy matching.

## Verification

- Focused structured-history/provider/MetricSeries/FinancialScan/intake chain:
  `139 passed`.
- Downstream pipeline, report-entry, source-boundary, report-quality and deep
  analysis renderer suites: `252 passed`.
- Full repository: `2796 passed, 16 skipped`.
- `tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Production Python implementation delta relative to the pre-implementation
  dirty-worktree baseline: net `+300`, at the `+300` hard stop.

## Boundaries And Warnings

- No scoring, target, risk, technical, recommendation, display or LLM prompt
  code changed.
- Batch A intentionally supports only revenue, parent-attributable net profit
  and operating cash flow in CNY.
- The repository does not yet contain refreshed canonical history caches; run
  the explicit refresh entry when network access is intentionally allowed.
- Existing pre-implementation HK report-year, adjusted-profit and latest-cache
  selection changes were preserved.

## Post-Implementation Live Acceptance

- Explicit Eastmoney refresh succeeded for 中际旭创, 复旦微电 and 黑芝麻智能.
- The caches contain respectively 18, 9 and 6 complete annual CNY records;
  each accepted record has revenue, parent-attributable net profit and operating
  cash flow with no cache-reader diagnostics.
- MetricSeries produced three base series and one cash-conversion derived series
  for each stock. The latest three annual points were verified directly.
- Fresh `20260731` Markdown/HTML reports were generated for all three stocks.
  Report quality and source-boundary gates passed for all three; prose checks
  passed with existing non-blocking theme/heading warnings.
- No pre-2025 annual-report text or citation leaked into the reports. Historical
  API series remained compute-only while 2025 filing facts remained the official
  report-facing source.
