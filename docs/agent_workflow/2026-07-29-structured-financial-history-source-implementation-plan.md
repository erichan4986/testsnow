# Structured Financial History Source Implementation Plan

**Goal:** Replace production use of historical annual-text fact packs with an
auditable local API-backed series while keeping the latest annual report as the
full narrative/current-fact source.

**Design:**
`2026-07-29-structured-financial-history-source-design.md`

## Batch 1: Adapter And Cache

1. Add failing tests for exact A-share/HK field admission, FY filtering, CNY
   enforcement, stable hashing and atomic no-op writes.
2. Add one adapter/cache module that normalizes provider rows into three annual
   metric source points.
3. Run only the new adapter tests.

## Batch 2: Provider Boundary And Refresh Entry

1. Add failing tests for A-share symbol routing and HK cash-flow query shape.
2. Add narrow provider wrappers and one explicit refresh CLI.
3. Ensure the CLI owns no metric mapping and failed refreshes preserve cache.

## Batch 3: MetricSeries Admission

1. Add failing tests for the mutually exclusive `fact_packs` / `source_points`
   contract, source hashes, ordered growth and cash conversion.
2. Normalize both authorities into the existing private series row shape.
3. Reuse the existing cash-conversion formula owner.

## Batch 4: Pipeline Cutover

1. Add failing tests proving production intake reads only the local structured
   history cache for history while latest annual narrative remains unchanged.
2. Replace the production historical-text series call with cache loading.
3. Keep the historical-text helper available only for existing focused tests;
   do not retain it as a second production path.

## Batch 5: Verification

1. Run focused adapter, MetricSeries, scan, intake and provider tests.
2. Run downstream reporter tests and CI grep gates.
3. Run `git diff --check` and audit production Python numstat against the
   pre-implementation tree.
4. Do not refresh network data or generate reports in this implementation turn.

## Stop Conditions

- Production Python delta exceeds net `+300` lines.
- A required change reaches display, scoring, target, risk, technical,
  recommendation or LLM prompt code.
- Normal report generation would need network access.
- Provider fields require fuzzy matching or FX conversion.
