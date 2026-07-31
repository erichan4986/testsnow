# Structured Financial History Source Design

## 1. Decision

Historical annual-report PDFs are no longer the primary source for cross-year
financial series.

- The latest official annual report remains the source for business narrative,
  product progress, management explanations, current filing core facts and
  Chapter 4.1 citations.
- Prior-year history uses structured financial APIs and a small local cache.
- Historical PDFs are fetched only for an explicit missing/conflicting-data
  investigation. They are not a normal pipeline dependency and are not split
  into evidence blocks, narrative cards or memos.

This design supersedes only the historical-source choice in
`2026-07-27-periodic-history-backfill-design.md`. The accepted MetricSeries and
FinancialScan compute contracts remain the downstream owners.

## 2. Goal

Provide three comparable annual points for the existing deterministic metrics
without multiplying annual-report producer work.

Batch A supports only the current MetricSeries metric universe:

1. revenue;
2. parent-attributable net profit;
3. operating cash flow.

Gross margin, adjusted profit and R&D intensity are deferred until the three
core metrics pass the three-stock pilot. They must not be added opportunistically
inside Batch A.

## 3. Source Matrix

### A shares

Use the existing AkShare wrappers around Eastmoney report-period statements:

- `stock_profit_sheet_by_report_em` for revenue and parent-attributable net
  profit;
- `stock_cash_flow_sheet_by_report_em` for operating cash flow.

Only fiscal-year rows ending on 31 December are admitted. Quarterly, trailing,
forecast and single-quarter rows are rejected.

Field admission is an exact ordered allowlist, not fuzzy label matching:

- revenue: `TOTAL_OPERATE_INCOME`, then `OPERATE_INCOME`;
- parent-attributable net profit: `PARENT_NETPROFIT`;
- operating cash flow: `NETCASH_OPERATE`.

### Hong Kong shares

Use Eastmoney Datacenter:

- `RPT_HKF10_FN_GMAININDICATOR` for revenue and holder-attributable profit;
- `RPT_HKSK_FN_CASHFLOW` for operating cash flow.

Only rows explicitly identified as annual/FY are admitted. The provider must
preserve the issuer reporting currency. Batch A admits CNY series only because
the current MetricSeries/FinancialScan v1 contract is CNY/万元; any other
currency produces `unsupported_reporting_currency` rather than an FX
conversion.

HK field admission is likewise exact:

- revenue: `OPERATE_INCOME`;
- holder-attributable profit: `HOLDER_PROFIT`;
- operating cash flow: select the one `RPT_HKSK_FN_CASHFLOW` line-item row whose
  `ITEM_NAME` exactly equals one of `经营活动产生的现金流量净额`,
  `經營活動產生的現金流量淨額`, `经营活动所用现金净额` or
  `經營活動所用現金淨額`, then read `AMOUNT`.

The cash-flow endpoint is row-oriented (`ITEM_NAME`/`AMOUNT`), unlike the wide
GMAININDICATOR row. No substring/fuzzy match is permitted; no exact match means
an explicit missing-metric diagnostic.

### Source authority

The API history is a structured secondary representation of filed statements,
not an official filing citation. It is compute-only and cannot become a current
core fact, Chapter 4.1 row, score, target-price input, risk input or
recommendation input.

## 4. Cache Contract

Normal report generation must not depend on a successful live history request.
An explicit refresh step writes one compact cache per stock:

```json
{
  "schema_version": "structured_financial_history_cache.v1",
  "stock_code": "300308",
  "stock_name": "中际旭创",
  "market": "A",
  "provider": "eastmoney",
  "fetched_at": "2026-07-29T00:00:00+08:00",
  "data_hash": "sha256-of-identity-and-records",
  "records": [
    {
      "report_year": 2025,
      "report_date": "2025-12-31",
      "report_type": "annual",
      "currency": "CNY",
      "metrics": {
        "revenue": {"value": "...", "source_field": "..."},
        "net_profit": {"value": "...", "source_field": "..."},
        "operating_cash_flow": {"value": "...", "source_field": "..."}
      },
      "source_rows": [
        {
          "dataset": "profit",
          "report_name": "stock_profit_sheet_by_report_em",
          "report_date": "2025-12-31",
          "selected_fields": {"TOTAL_OPERATE_INCOME": "...", "PARENT_NETPROFIT": "..."},
          "row_hash": "..."
        },
        {
          "dataset": "cashflow",
          "report_name": "stock_cash_flow_sheet_by_report_em",
          "report_date": "2025-12-31",
          "selected_fields": {"NETCASH_OPERATE": "..."},
          "row_hash": "..."
        }
      ]
    }
  ],
  "diagnostics": []
}
```

The persisted cache contains only fields needed to reproduce each selected
annual metric, request identity and canonical row hashes. It does not contain
the provider's unrelated columns or annual-report prose. `row_hash` is computed
from the canonical JSON of `dataset`, `report_name`, `report_date` and
`selected_fields`; records, fields and metrics are sorted deterministically.

`data_hash` is computed from stock identity, market, provider and canonical
`records`, excluding both `fetched_at` and `data_hash` itself. If a refresh
produces the same `data_hash`, the existing cache file is left byte-for-byte
unchanged; wall-clock metadata must not create provenance churn.

Canonical cache path is
`data/raw/structured_financial_history/<stock_code>.json`. Network refresh uses
`scripts/refresh_structured_financial_history.py --stock <name-or-code>`. The
entry contains argument parsing and atomic-write orchestration only; provider
mapping and validation remain in the adapter module.

The refresh command writes through a temporary file and atomically replaces a
valid cache only after schema, stock identity, period, currency and metric
validation pass. A failed refresh leaves the prior cache unchanged.

## 5. Ownership And Data Flow

1. `reporter/data_fetcher.py` remains the network boundary. It owns provider
   calls but not financial formulas or report selection.
2. A new small structured-history adapter validates provider rows, normalizes
   currency units and writes/reads the cache contract.
3. `periodic_report_metric_series.py` remains the sole owner of grouping,
   consecutive-period changes and series ordering. The API adapter supplies
   validated source rows to the same internal row builder; it must not create a
   second growth implementation.
4. `periodic_report_financial_scan.py` remains the sole anomaly-rule owner.
5. `periodic_report_fulltext_intake_skill.py` continues to publish the existing
   context keys. It builds current filing facts, explanation material and
   narrative cards from the latest annual cache, but reads historical series
   from the structured financial-history cache instead of every annual-text
   cache. It performs no history network calls.
6. Do not add another pipeline skill or feature flag in Batch A. The existing
   intake skill is already the context publisher for MetricSeries and
   FinancialScan; changing its source adapter is smaller and avoids a second
   orchestration owner.

The normal report path therefore has one latest-report prose source, one
structured-history source and the existing single context publisher.

The MetricSeries public contract is extended narrowly:

```python
build_periodic_report_metric_series_pack(
    *,
    stock_code: str,
    stock_name: str,
    fact_packs: list[dict] | None = None,
    source_points: list[dict] | None = None,
) -> dict
```

Exactly one source argument may be supplied. Existing official-filing callers
continue to use `fact_packs`; the structured-history adapter supplies
`source_points`. Both validation paths normalize into the same private row shape
before the existing grouping and change logic. Supplying both returns an empty
pack with a source-authority diagnostic rather than merging authorities.

More precisely, exactly one argument must be non-`None`. An explicitly supplied
empty list produces the existing valid empty MetricSeries pack; both arguments
`None`, or both non-`None`, produce a top-level source-authority diagnostic and
no accepted points.

An API source point has the fixed source type
`structured_financial_api_fact`, a canonical `periodic:<stock>:<year>:annual:<metric>`
fact reference, and the compact source evidence described in Section 6. It is
never inserted into an official structured-fact pack.

Cash conversion retains one numeric formula owner. The existing
operating-cash-flow/net-profit calculation is extracted as a pure helper in
`periodic_report_contract_utils.py`; the official structured-fact path and the
API source-point path both call it. MetricSeries remains the only owner that
groups API-derived ratio points into a derived series. Formula version,
non-positive-profit behavior and diagnostics must remain byte-for-byte
compatible with the accepted v1 output.

## 6. Provenance And Admission

Each API metric point must retain:

- provider and dataset;
- stock code and exact report date;
- source field name;
- canonical selected-row hash;
- cache filename and verified stable `data_hash`;
- value basis (`as_reported`);
- currency and normalized unit.

Its `source_block_id` is deterministic:
`<provider>:<dataset>:<report-year>:<metric-key>`. `source_excerpt_hash` hashes
the selected metric field/value pair; `source_block_hash` is the matching
canonical `source_rows[].row_hash`. These are data-provenance hashes, not claims
that an exact annual-report sentence was quoted.

The MetricSeries adapter may admit an API-derived source type, but
`filing_facts_to_core_facts()` must continue to admit only exact official filing
facts. This is the hard boundary preventing API history from silently replacing
the latest annual-report facts.

FinancialScan and the external compatibility map may consume the API-backed
MetricSeries as compute-only context. Their existing `report_eligible=false`
contract must remain unchanged, and Batch A must not add any renderer path from
those packs.

Conflicting values for the same stock/year/metric are rejected with a diagnostic;
the pipeline does not choose the larger, newer or more convenient value. Missing
metrics remain missing and are never estimated.

## 7. Runtime Behavior

- Explicit refresh: network allowed, writes only the structured history cache.
- Ordinary report generation: cache-only, no additional history API latency.
- Missing cache: publish an empty valid MetricSeries with
  `history_cache_missing`, then let the existing FinancialScan contract report
  `empty`; the report continues using the latest annual report. Do not add a new
  status field to MetricSeries v1.
- The cache does not expire by wall-clock time. Freshness is controlled only by
  the explicit refresh command and the available fiscal-year set.
- Provider failure: retain the last valid cache.
- Historical PDF fallback: manual/explicit only, outside ordinary report runs.

## 8. Migration

1. Keep the existing 2025 annual caches and latest-year report path unchanged.
2. Keep the generic correctness repairs already found during the pilot:
   requested HKEX year matching, adjusted-profit rejection and year-first latest
   cache selection.
3. Stop using `_metric_series_from_cache_rows()` in the production pipeline.
4. Do not delete the downloaded 2023/2024 pilot files in this batch; they remain
   ignored audit artifacts and are no longer required inputs.
5. After the API pilot is accepted, mark the PDF-history backfill design as
   superseded. Historical cache helpers may be removed only after call-site and
   test audits prove they have no supported public consumer.

## 9. Required Tests

### Provider and cache

- A-share annual rows map the three exact metrics and reject quarterly rows.
- HK annual rows map the three exact metrics and reject interim/TTM rows.
- non-CNY HK rows fail closed without FX conversion.
- missing source fields remain explicit diagnostics.
- duplicate/conflicting period values are rejected.
- deterministic row hashes and sort order are stable.
- an identical refresh preserves cache bytes and `data_hash`.
- failed refresh does not overwrite the previous valid cache.
- malformed/wrong-stock cache is unavailable.

### MetricSeries and scan

- API points use the existing growth/change owner; no duplicate formula helper
  exists.
- API and official-filing inputs produce identical cash-conversion values and
  diagnostics for identical numeric inputs.
- passing both `fact_packs` and `source_points` fails closed.
- passing neither source collection fails closed, while an explicit empty
  collection preserves the accepted empty-pack behavior.
- API source-point evidence hashes are checked against the selected cache row.
- ordered 2023/2024/2025 points produce the accepted changes and scan findings.
- a missing middle year does not produce pseudo-YoY growth.
- negative profit/cash-flow bases retain current diagnostics.
- API source points cannot pass `filing_facts_to_core_facts()`.

### Pipeline

- latest annual narrative/core facts still come from the newest report year.
- ordinary report generation reads local history cache without network calls.
- missing history cache does not remove Chapter 4.1 current annual material.
- no historical evidence cards, annual memos or Knowledge notes are written.
- scoring, target, risk, technical and recommendation payloads are unchanged.

### Pilot acceptance

- 中际旭创 and 复旦微电: three ordered annual points for all available core
  metrics.
- 黑芝麻智能: all available annual points; absence before listing is explicit.
- compare API points with the already validated pilot annual-report values.
  Any mismatch blocks cutover and records metric/year/provider details.

## 10. Failure Modes

| Failure | Symptom | Gate |
|---|---|---|
| Quarterly row admitted as FY | inflated or partial annual value | exact date/type fixture |
| Parent profit confused with adjusted profit | incompatible profit trend | source-field allowlist |
| HK currency assumed CNY | unit-corrupted series | currency hard rejection |
| API outage empties history | prior valid series disappears | atomic cache retention test |
| API history leaks into current facts | Chapter 3/4.1 source label changes | core-fact boundary regression |
| Two growth owners diverge | inconsistent scan outputs | helper/call-site audit |
| Old PDF history remains active | duplicate/conflicting series | production context identity test |

## 11. Scope And Stop Conditions

Allowed implementation scope is limited to:

- one structured financial-history adapter/cache module;
- existing provider functions in `reporter/data_fetcher.py`;
- MetricSeries normalization needed to consume the cache without a second
  formula owner;
- the existing structured-fact and contract-utils modules only as needed to
  extract and reuse the single cash-conversion formula;
- focused tests and `scripts/refresh_structured_financial_history.py` as the one
  explicit refresh entry.

Stop and return to design if implementation requires:

- changing report display, scoring, target, risk, technical or recommendation;
- introducing an LLM or annual narrative extraction for historical years;
- automatic historical PDF downloads;
- fuzzy metric matching;
- FX conversion;
- any provider mapping, cache validation or financial formula duplicated in the
  refresh entry or intake skill instead of the one adapter/MetricSeries owners;
- retaining both PDF-history and API-history production paths.

Runtime target is net `+220` lines across production Python files, with a hard
stop at net `+300`. The implementation must replace the production
`_metric_series_from_cache_rows()` call rather than layering another pipeline
branch beside it. Test and design lines are excluded from this budget.

## 12. Design Delta

### Accepted

- Use structured APIs rather than historical annual PDFs for financial history.
- Keep only the latest annual report on the full narrative path.
- Make ordinary report generation cache-only and deterministic.
- Preserve existing MetricSeries/FinancialScan owners.

### Rejected

- API-only replacement of the latest annual report: loses management and
  product explanations required by Chapter 4.1.
- Parsing all three historical annual reports into cards/memos: high cost and no
  current display need.
- Fetching live history on every report run: adds latency and makes report
  reproducibility depend on provider uptime.

### Deferred

- gross margin, adjusted profit, R&D intensity, inventory, receivables and
  capital expenditure;
- non-CNY history and FX normalization;
- visible three-year report table;
- automatic PDF fallback.

### Round 1 Review Required

Yes. This changes a data-source boundary, pipeline ownership and the input path
to MetricSeries, so it requires a Level 3 read-only design review before an
implementation task is written.

## 13. Self Review Round 1

The first draft proposed six metrics immediately. That would require new ratio
and statement-field contracts before proving the source switch. Batch A is now
limited to the three metrics already accepted by MetricSeries and FinancialScan.

The first draft also proposed network refresh during report generation. That
would make a stable report depend on provider uptime and increase runtime. The
final flow separates explicit refresh from cache-only report intake.

A later interface check found that HK cash-flow data is emitted as line-item
rows rather than a wide `NETCASH_OPERATE` field. The design now uses a narrow
exact `ITEM_NAME` allowlist and `AMOUNT`, failing closed for unknown labels.

## 14. Self Review Round 2

The initial source-neutral plan could have allowed API history into the current
core-fact adapter. The final design keeps `filing_facts_to_core_facts()`
official-filing-only and requires an explicit API source type.

The migration originally added a dedicated pipeline skill. That duplicated the
existing context publisher and expanded configuration for no user-visible
benefit. The final design keeps the current intake skill, swaps only its history
source, and forbids history network calls there.

The migration also originally removed historical cache helpers immediately.
That is unsafe while tests and external callers may still use them. The final
design removes the production call first and permits helper deletion only after
a call-site audit.

The second review also found that API-derived cash conversion could have become
a second formula implementation. The final design extracts the accepted numeric
formula into one shared pure helper and requires equivalence tests across the
official and API inputs.

It also aligned missing-cache behavior with the existing schemas: MetricSeries
remains a valid empty v1 pack with a diagnostic and FinancialScan remains
`empty`; no new status convention is invented. Provenance uses a stable
`data_hash` over identity and records, excluding refresh timestamps, so an
identical refresh leaves cache bytes unchanged.
