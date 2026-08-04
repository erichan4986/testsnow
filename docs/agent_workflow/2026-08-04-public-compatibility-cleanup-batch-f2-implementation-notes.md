# Public Compatibility Cleanup Batch F2 Implementation Notes

## Result

- Verdict: `PASS`
- Runtime delta: `0 added / 563 net removed`
- Public/manual hard cut was approved by the user's instruction to continue.

## Runtime Changes

- Deleted `scripts/utils/judgment_generator.py` (271 lines).
- Deleted `scripts/utils/wechat_sogou_fetcher.py` (222 lines).
- Reduced `scripts/utils/reporter/__init__.py` from 40 to 3 lines; retained `ReportManager` only (net -37).
- Reduced `scripts/utils/reporter/sections/__init__.py` from 34 to 1 line (net -33).

Current README capability rows were updated. Historical design/spec records were retained.

## TDD Evidence

1. RED: `test_batch_f2_public_compatibility_hard_cut` failed because `judgment_generator.py` still existed.
2. GREEN: the package-boundary test passed after the locked hard cut.
3. Initial focused reporter/external suite: `166 passed`.
4. First full-suite collection exposed six test-only imports from the removed `scripts.utils.reporter.sections` re-export surface.
5. Root cause: the self-review search omitted the fully-qualified `scripts.` prefix. All six tests were moved to direct renderer owner imports, and hygiene now scans the full test tree for both package-level forms.
6. Renderer/package correction suite: `136 passed`.
7. Final full repository suite: `2858 passed, 10 skipped`.

## Retained Contracts

- `from utils.reporter import ReportManager` works and resolves to `utils.reporter.report_manager`.
- `from utils.reporter import data_fetcher` works through normal submodule import semantics.
- Direct scoring, data-fetcher, and renderer module imports remain valid.
- `ReportAssemblySkill.RENDERERS` dynamic module registry is unchanged.
- Black Sesame offline report smoke generated Markdown, HTML, and its audit sidecar successfully.

## Verification

- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Active-reference search found only the negative hygiene assertion for the deleted utility names.
- No network, browser, LLM, scoring, technical, risk, source, citation, data, knowledge, report, or configuration behavior changed.

## Combined Batch F Ledger

- F1 runtime deletion: 1,225 lines.
- F2 runtime deletion: 563 lines.
- Combined Batch F runtime deletion: **1,788 lines**.
- F1 also removed 790 lines of isolated tests; F2 retained behavioral tests by moving imports to direct owners.

## Blockers, Warnings, Deviations

- Blocker: none.
- Warning: external callers relying on the deleted undocumented utility modules or package-level renderer/scoring/data re-exports must switch to direct owner modules.
- Deviation: six additional test files were updated after full-suite collection exposed package-level imports omitted by the initial search. Runtime scope and behavior remained unchanged.
