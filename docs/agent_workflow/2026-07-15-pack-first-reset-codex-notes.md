# Pack-First Reset

- Date: 2026-07-15
- Scope: local Knowledge projections only; no network or report generation.

## Policy

- Raw periodic-report caches remain the recoverable source material.
- Validated JSON packs are the machine-readable canonical annual-card source.
- Top-level v2 Markdown cards are disposable projections, not a recovery input.
- Legacy v1 Markdown remains available only for the existing compatibility adapter.

## Completed

- Rebuilt one validated 2025 annual pack from local cache for each of 11 stocks.
- Switched the default material loader to `pack_first` when a stock code and pack
  manifest are available; legacy Markdown remains the no-pack compatibility path.
- Archived 881 top-level v2 Markdown projections under each stock's
  `periodic_narrative_cards/_legacy_archive/20260715-pack-first-reset/` directory.
  Each archive includes a `manifest.json` with original path, card id, source hash,
  and file hash.
- Archived a further 100 v1 projections for 中简科技、中际旭创、乐鑫科技、圣邦股份
  and 黑芝麻智能 after verifying both `v1_adapter_use_count` and
  `v1_actionable_needs_recovery_count` were zero.
- Retained 48 v1 notes for 华大九天、德邦科技 and 赛微微电 because 11 actionable
  legacy facts still require the compatibility adapter.

## Verification

- All 11 manifests load successfully as `pack_first`.
- All 11 selected-card sets and diagnostics match pack shadow, excluding the
  expected storage-mode label.
- No top-level v2 Markdown projections remain.
- 390 focused and 242 downstream tests passed; CI grep gates and `git diff --check`
  passed.
