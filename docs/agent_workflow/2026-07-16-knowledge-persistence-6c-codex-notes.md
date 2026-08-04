# Knowledge Persistence Batch 6C - Codex Notes

## Scope

Batch 6C removes the obsolete v2 Markdown machine-data path. Validated JSON
packs are now the only v2 machine truth; Markdown under
`periodic_narrative_views/` is a human-readable projection. The minimal v1
reader remains solely for migration diagnostics and recovery.

No report, scoring, target-price, risk, technical-analysis, profile, LLM
prompt, or collection code was changed. No network access or report generation
was performed.

## Runtime Changes

- Deleted `periodic_report_narrative_card_note_writer.py`.
- Removed direct Markdown loading from narrative-card synthesis items.
- Removed v2 Markdown JSON parsing and v2-note classification from the annual
  material pack.
- Kept fail-closed typed pack-storage errors. A corrupt pack cannot fall back
  to stale v2 Markdown.
- Kept a minimal v1 frontmatter/body reader for migration only.
- Added a deterministic dry-run archive manifest with relative paths, SHA-256,
  note version, per-stock gates, and an explicit-confirmation requirement.
- Updated the workflow context index to identify the pack store as machine
  truth and the view writer as projection-only.

## TDD Evidence

Initial contract tests failed in seven expected places: default synthesis was
not pack-first, `use_pack=False` restored direct-note loading, typed errors were
swallowed, the old writer still existed, missing stock code did not fail,
corrupt packs fell back, and no archive manifest builder existed.

After the implementation:

- Batch 6C contract suite: `47 passed`.
- Related annual/material/renderer suite: `557 passed`.
- Context-index path checks: `3 passed`.
- `tools/ci_grep_gates.sh`: passed.
- `git diff --check`: passed.

The wider `tests/utils` run reached `1376 passed, 3 skipped` and exposed six
failures. The context-index failure caused by deleting the writer was fixed and
its focused suite is green. The five remaining failures are outside Batch 6C:
three existing Source Intake expectations and two standalone CLI circular
import failures. A separate full-suite run also exposed the existing top-level
`scoring_engine` relative-import failure in
`test_output_structured_risk_signals_passes_to_risk_section`. Batch 6C does not
modify those owners.

## Eleven-Stock Gate

Using local periodic-report caches only, all eleven configured acceptance
stocks passed:

- producer/pack parity
- deterministic projection
- pack bytes unchanged
- manifest bytes unchanged
- projection cards SHA-256 match
- `v1_actionable_needs_recovery_count == 0`
- `v1_adapter_use_count == 0`

Acceptance output: `/tmp/annual-producer-6c-acceptance.md`.

## Dry-Run Archive Manifest

Manifest: `/tmp/annual-producer-6c-archive-manifest.json`

- `dry_run_only: true`
- `requires_explicit_confirmation: true`
- all 11 stock gates passed
- invalid notes: 0
- eligible v1 notes: 48
- eligible v2 notes: 0

Eligible v1 distribution:

- 华大九天: 24
- 德邦科技: 20
- 赛微微电: 4

The dry-run itself did not move or delete files. The user subsequently gave
explicit confirmation, and the eligible files were moved as recorded below.

## Confirmed Archive Execution

All 48 eligible v1 notes were moved, not permanently deleted, into stock-local
archive directories:

- `华大九天/periodic_narrative_cards/_legacy_archive/20260716-pack-first-completion/`
- `德邦科技/periodic_narrative_cards/_legacy_archive/20260716-pack-first-completion/`
- `赛微微电/periodic_narrative_cards/_legacy_archive/20260716-pack-first-completion/`

Each directory contains a `manifest.json` receipt with original path, archived
path, SHA-256, and note version. Post-move verification proved all 48 archived
files match their dry-run SHA-256, no original top-level path remains, and the
top-level v1 narrative-note count is zero.

The eleven-stock acceptance was rerun after the move and again reported no
projection error, false parity gate, nonzero recovery count, or nonzero adapter
count. Post-archive output:
`/tmp/annual-producer-6c-post-archive-acceptance.md`.

## Post-Archive Formal Report Acceptance

Fresh reports were generated after the archive receipts were written:

- `reports/中际旭创_20260716.md` (`formal_medium`), with the complete 4.1-4.4
  source-layer structure.
- `reports/复旦微电_20260716.md` (`formal_thin_external_rich`), with the complete
  annual/broker/external three-section structure.

Both report commands exited zero. Both reports passed report-quality and
source-boundary checks, had no missing/unused/unknown/malformed citations, and
kept low-credit sources out of 4.1. Report generation did not alter pack or
manifest bytes and did not restore any top-level v1 note. Prose checks passed
with only the existing `theme_reexpanded_outside_owner` warnings.

## Runtime Ledger

Against pre-Batch-6 baseline `c20af7f`, the tracked Batch 6 persistence runtime
files add 371 and remove 1,385 lines. The new view writer contributes 193
lines, for a cumulative runtime net of **-821 lines**.

This satisfies the cumulative target of non-positive runtime growth and is far
below the `+80` hard stop.

## Result

Batch 6C implementation and the separately confirmed legacy-note archive are
accepted. Machine input remains pack-first and independent of archived notes.
