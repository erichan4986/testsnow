# Annual Producer Self-Contained Admission Repair Notes

Date: 2026-07-16

## Scope

- Shared annual source-tail handling now accepts one embedded annual-report page header and rejects a second header.
- Producer admission keeps complete source-only business, technology, financial, market, and risk arguments without relaxing structural-noise guards.
- Legacy coverage proof remains exact: normalized contiguous `SourceUnit` text only, with no fuzzy or semantic recovery.

## Modified Runtime

- `scripts/utils/annual_argument_schema.py`
- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `scripts/utils/annual_report_material_pack.py`

## Verification

- Focused annual producer/material suites: `293 passed`.
- Downstream annual memo/snapshot/renderer suites: `547 passed`.
- `tools/ci_grep_gates.sh`: passed.
- `git diff --check`: clean.
- Runtime delta for the three repair files versus the branch baseline: `+116` net lines.

## Real 11-Stock Gate

All configured stocks were refreshed from local caches only. For every stock:

- `producer_pack_parity = true`
- `projection_deterministic = true`
- `pack_bytes_unchanged = true`
- `manifest_bytes_unchanged = true`
- `projection_cards_sha256_matches = true`
- `v1_actionable_needs_recovery_count = 0`
- `v1_adapter_use_count = 0`

Acceptance artifact: `/tmp/annual-producer-admission-real-acceptance.md`.

## Boundaries

- No network access and no report generation.
- No scoring, target, risk, technical, profile, renderer, collection, or LLM prompt changes.
- No legacy note was archived or deleted.
