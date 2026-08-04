# Batch F2 Codex Self-Review Notes

## Round 1

Verdict: `needs_revision`.

Findings:

1. The initial package plan must explicitly retain `from utils.reporter import data_fetcher`; repository tests use this Python submodule-import form.
2. `ReportManager` is active in `xueqiu_monitor_v2.py` and must remain the sole eager reporter-package export.
3. Historical specs mentioning `JudgmentGenerator` are records, not current capability documentation; deleting or rewriting them would create unrelated churn.
4. The sections-package cut needs a direct-import replacement for `test_fulltext_material_isolation.py`.

Corrections applied to the design:

- Added explicit submodule-import and `ReportManager` retained contracts.
- Limited documentation edits to current README rows.
- Added the exact direct test import change.

## Round 2

Verdict: `ok`.

Checks:

- Repository search shows no active caller for either detached utility.
- Active modern owners exist and are already wired.
- Reporter submodules remain importable without eager re-exporting their symbols.
- Assembly dynamically imports renderer modules, not package-level renderer names.
- The only package-level renderer import is test-only and can move to the direct module.
- No compatibility shim is required; adding one would defeat the cleanup.
- Estimated runtime deletion exceeds the 540-line gate.

Implementation ready: yes.

## Implementation Correction

The first full-suite collection exposed six test imports using the fully
qualified `scripts.utils.reporter.sections` package surface. The Round 2 search
covered `utils.reporter.sections` and `reporter.sections` but omitted that
prefix. These were test-only imports, so the locked runtime boundary did not
change. All six imports were moved to their direct renderer owner modules, and
the hygiene test now scans the complete test tree for either package-level
renderer import form.
