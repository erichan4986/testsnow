# Periodic Report Metric Series - Codex Self-Review Round 1

> Date: 2026-07-24
> Verdict: needs_revision

## Findings

### B1 - Duplicate cash-conversion formula owner

The draft recomputes `operating_cash_flow_to_net_profit` inside the new series
module even though `periodic_report_structured_facts.py` already owns that
formula. Two owners can drift. The structured-fact derived row must gain period
metadata and a formula version; MetricSeries should validate and assemble it,
not recompute it.

### M1 - Flattened provenance can collide across documents

`source_block_id` values such as `financial_summary_table-0` repeat in every
report. Independent `source_docs`, `evidence_refs`, and hash lists lose the
document/block pairing. Each point needs sorted `source_evidence` records that
bind source document, block id, excerpt hash, and block hash together.

### M2 - Non-consecutive observations can be mislabeled as period growth

Adjacent available points may be several years apart. The first draft would
emit one growth rate without identifying the gap. Only consecutive report years
should produce `periodic_growth.v1`; gaps must emit a diagnostic and no change.

### M3 - Existing glob patterns can return the same file more than once

The cache finder extends one list from overlapping patterns. An all-history
adapter must deduplicate resolved paths before sorting, while preserving the
latest-file mtime behavior used by existing callers.

### M4 - Input-pack extraction diagnostics disappear

Missing or unanchored metrics explain why a series has holes. The series pack
must preserve compact source-pack diagnostics with source document and period;
otherwise Batch 3 cannot distinguish a missing disclosure from a parser miss.

### M5 - Source document is optional in the draft admission contract

Cross-period provenance must identify the originating cache. Series admission
therefore requires `source_doc` on the pack and fact. Existing direct fact
builders stay backward compatible because only the series layer enforces it.

## Design Delta

- accepted: B1 and M1-M5; revise the design before Round 2.
- rejected: none.
- deferred: broader filing metrics and comparative/restated-column extraction
  remain outside Batch 2.
- Round 2 required: yes, because derived-series ownership and provenance shape
  materially change.

