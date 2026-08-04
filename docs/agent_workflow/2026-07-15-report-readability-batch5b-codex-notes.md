# Report Readability Batch 5B - Codex Notes

## Delivered

`DeepAnalysisRenderer` now renders one admitted external observation as readable Markdown blocks: at most two source-preserving sentence/semicolon units per block, exact duplicate-unit removal within the same claim, and the original inline citation cluster on every visible block.

No character cap, semantic similarity rule, source rewrite, cross-layer topic suppression, or material admission change was added.

## TDD Evidence

RED: the five-unit and exact-duplicate fixtures failed because the old renderer emitted one paragraph. GREEN results:

- Batch 5B focused regressions: `4 passed`.
- Deep-analysis renderer, report-quality, and source-boundary suites: `217 passed`.
- `bash tools/ci_grep_gates.sh`: passed.
- `git diff --check`: clean.

## Scope Audit

Runtime modified: `scripts/utils/reporter/sections/deep_analysis_renderer.py`.

Tests modified: `tests/reporter/test_deep_analysis_renderer.py`.

No producer, MaterialSnapshot, citation offset, quality gate, score, target, risk, technical, profile, prompt, data, knowledge, or report file changed. No report was generated.

## Runtime Delta

The helper and call-site adjustment are approximately +25 runtime lines, below the +60 stop condition. Repository-wide `git diff --numstat` is not a valid batch measurement because this worktree was already dirty in the same files.

## Deferred

Cross-source repetition such as a product-rate topic across official, broker, and external layers remains intentional evidence separation. It needs a separate editorial-ownership decision, not mechanical deletion here.
