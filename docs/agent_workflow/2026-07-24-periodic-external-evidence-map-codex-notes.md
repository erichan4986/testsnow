# Periodic External Evidence Map - Codex Notes

## Verdict

Accepted. Batch 4 adds a deterministic, compute-only external-to-filing map.
It does not alter official facts and has no report, scoring, risk, target,
technical-analysis, recommendation, Knowledge, or prompt consumer.

## Implemented

- Exposed the financial scanner's admitted MetricSeries reader and made both
  the scanner and mapper use that single validation owner.
- Added `periodic_external_evidence_map.py` with:
  - canonical v4 target-company and `financial_quality` admission;
  - exact card/block-local report-period and modality context;
  - typed revenue, net-profit, and operating-cash-flow amount/growth parsing;
  - representation-precision comparisons;
  - deterministic `confirm`, `contradict`, and chronological `update` links;
  - exact financial-scan finding links for matching growth intervals;
  - compact hash/citation evidence and no copied source prose;
  - fail-closed ambiguity, currency, duplicate identity, and stale-scan rules.
- Published `periodic_external_evidence_map` from Synthesis only after a valid
  curated display and only when both periodic source packs exist.

## TDD Evidence

1. Shared reader: missing import RED; scanner output-preservation and admission
   tests GREEN (`36 passed`).
2. Observation extraction: missing mapper module RED; initial admission,
   ownership, context, numeric, and currency tests GREEN (`8 passed`).
3. Relations: 13 expected failures with an empty relation layer; amount/rate,
   precision, forecast, update, value-basis, finding-link, and order tests
   GREEN.
4. Pipeline publication: 3 missing-import/call failures RED; publication and
   no-call boundaries GREEN.
5. Final mapper suite after self-review repairs: `27 passed`.

## Implementation Self-Review 1

Three correctness defects were reproduced with RED tests and repaired:

- `expected to realize` no longer becomes a reported result;
- period/modality context no longer crosses source/document/block boundaries;
- decline rates and loss amounts retain their negative direction.

See
`2026-07-24-periodic-external-evidence-map-codex-implementation-review-round1-notes.md`.

## Implementation Self-Review 2

One fail-closed defect and two contract/budget gaps were repaired:

- duplicate external unit identities now reject the display;
- recursive tests prove no prose-bearing payload or consumer authority leaks;
- equivalent runtime code was compressed from 658 to 600 mapper lines, keeping
  the complete batch runtime delta below the +650 hard stop.

See
`2026-07-24-periodic-external-evidence-map-codex-implementation-review-round2-notes.md`.

## Verification

- Focused scanner/mapper/synthesis: `164 passed`.
- External v4, periodic, renderer, quality, and source-boundary downstream:
  `290 passed`.
- Full offline suite: `2722 passed, 16 skipped`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- Module compilation: passed.
- `git diff --check`: clean.
- Scope audit: only Synthesis writes the context key; no runtime consumer reads
  it outside the pure mapper and publication call.

## Read-Only Cache Smoke

Inputs were local annual caches under
`/Users/erichan/testsnow/data/raw/periodic_reports` plus the three canonical v4
argument packs. No network, LLM, browser, report, Knowledge, data, or config
write occurred.

| Stock | Display | Filing series | Scan | Financial units | Observations | Mappings | Map |
|---|---|---:|---|---:|---:|---:|---|
| Zhongji Innolight | ok | 2 | partial | 1 | 0 | 0 | partial |
| Fudan Microelectronics | ok | 0 | empty | 16 | 13 | 0 | partial |
| Black Sesame | ok | 2 | partial | 3 | 0 | 0 | partial |

The checked cache set remains one-period and Fudan has no admitted filing
series. Zero live mappings are therefore the correct fail-closed outcome;
multi-year confirm/contradict/update behavior is covered by exact fixtures.

## Runtime Delta

Against `cd80dec`:

- shared scanner reader refactor: +70 / -39, net +31;
- Synthesis publication: +13;
- new mapper: +600;
- total runtime net: +644 (hard stop: +650).

Tests and workflow notes are excluded from the runtime budget.

## Blockers / Warnings / Deviations

- Blockers: none.
- Warning: current local annual caches are too sparse to demonstrate a live
  relation; no relation was inferred to compensate for missing history.
- Deviations: none.
