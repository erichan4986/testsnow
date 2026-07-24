# Annual Document Coverage Manifest - Codex Implementation Notes

Date: 2026-07-24
Baseline: `c406f77`
Verdict: `PASS`

## Scope

Implemented an additive, deterministic audit ledger for periodic-report coverage. The evidence pack now
records recognized sections plus extracted/prioritized/selected block decisions; the narrative producer
finalizes those decisions with its existing source-unit/card diagnostics. No extractor, 48-block selection,
card admission, report display, scoring, target, risk, recommendation, technical, or LLM behavior changed.

## Design Reviews

- Round 1 fixed structural-vs-analytical status, synthetic/empty heading behavior, block identity,
  page-marker grammar, missing/malformed compatibility, and budget scope.
- Round 2 fixed evidence/producer stage semantics, exact duplicate accounting, full SHA-256 identities,
  page-marker section leakage, page locator status, and implementation readiness.

## TDD Evidence

1. Section inventory tests failed at import before the module existed, then passed after the pure builder and
   validator were implemented.
2. Block lifecycle/finalizer tests failed on the missing finalizer, then passed with exact ID joins and
   fail-closed producer behavior.
3. Evidence integration tests failed on the absent `coverage_manifest`, then passed while preserving the
   existing 48 selected blocks in the cap fixture.
4. Producer tests failed on the absent diagnostic, then passed for selected/rejected units and
   missing/malformed upstream manifests.
5. Self-review RED tests caught and fixed:
   - page marker leakage across an intervening heading;
   - short synthetic roots being mislabeled `structural_only`;
   - whitespace-only input being treated as available;
   - selected units without a real card link;
   - broken section/block references reaching finalization;
   - heading-only documents receiving a vacuous `complete` status.

## Test Results

- Coverage/evidence/producer/store focused suite: `311 passed`
- Material-pack/synthesis/report quality/source-boundary downstream suite: `153 passed`
- Full offline suite: `2630 passed, 16 skipped`
- `bash tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean

## Runtime Budget

Against `c406f77`:

| Runtime file | Net |
|---|---:|
| `periodic_report_coverage_manifest.py` | +240 |
| `periodic_report_evidence_pack.py` | +12 |
| `periodic_report_narrative_evidence_cards.py` | +6 |
| **Total** | **+258** |

The result is below the locked `+260` hard stop. The first implementation shape exceeded the budget before
integration; it was replaced rather than layered. Missing coverage now goes through the same finalizer as
valid coverage, avoiding a second unavailable-state owner.

## Local-Cache Acceptance

No network, Knowledge writes, or report generation was used.

| Stock | Style | Source chars | Evidence blocks | Cards | Sections | Unmapped | Page status | Coverage |
|---|---|---:|---:|---:|---:|---:|---|---|
| 黑芝麻智能 | HKEX | 157,369 | 19 | 60 | 168 | 152 | unavailable | partial |
| 中际旭创 | A-share | 230,085 | 45 | 70 | 603 | 124 | partial | partial |

Both finalized manifests were `ready/producer`; neither contained `text`, `source_excerpt`, or
`source_units`. The high unresolved counts are intentional and useful: this batch exposes extractor blind
spots rather than declaring unvisited annual-report sections complete.

## Warnings And Next Batch

- Jina Markdown creates many source-visible headings, especially table/leaf headings. `structural_only`
  prevents empty containers from inflating unresolved counts, but no semantic relevance is inferred.
- Explicit page markers are unavailable for the sampled HKEX cache and partial for the sampled A-share
  cache; page numbers remain null rather than inferred.
- Batch 2 should build `AnnualFact` / `MetricSeries` from source-owned cards and statement tables. It must
  consume this coverage ledger only for audit context, not use it as a new display selector.
