# External Topic Narrative Memo Implementation Notes

## Result

- Status: code-complete; live LLM/report acceptance pending.
- Baseline: `cb010646616ba340004d37c0fb92d084c803d7a5`.
- Scope: optional producer-time extractive memo and Chapter 4.3 display only.
- Unchanged: core v3 card admission, profile/freshness, synthesis text, Chapter 4.4, scoring, target, risk, technical analysis, recommendation, and LLM prompts outside the new memo composer.

## RED / GREEN

| Batch | RED evidence | GREEN evidence |
| --- | --- | --- |
| Pure contract | missing `curated_external_topic_narrative` module/API | 8 contract tests passed |
| Producer/reader/preview | missing `llm_topic_narrative_composer_factory` | 46 Batch A tests passed |
| Display/snapshot | missing immutable narrative read-model types | 46 display/snapshot tests passed |
| Renderer/quality | renderer rejected `narratives=` and formal-thin used row fallback | focused narrative and framing tests passed |

## Requirement-Test Matrix

| Requirement | Implementation | Verification |
| --- | --- | --- |
| Exact extractive prefixes and complete unit coverage | `curated_external_topic_narrative.py` | `test_curated_external_topic_narrative.py` |
| One 60-second memo attempt; no retry | `llm_topic_narrative_composer_factory` | producer factory timeout/call-count test |
| Memo failure cannot poison core pack | optional envelope attachment after ready core | producer failure and reader invalid-envelope tests |
| Private display projection only | `_curated_external_topic_narratives` | baseline display/synthesis equality test |
| Unit-derived citations | snapshot rebuilds refs from canonical units; display only passes validated parts | display and snapshot global-ref tests |
| Hidden rows cannot be restored | `select_external_topic_narratives` exact visible-unit coverage | hidden-argument projection test |
| Per-topic fallback | renderer narrative lookup by scope/family | valid-topic plus fallback-topic test |
| Formal-thin full-snapshot offset | snapshot-global part refs plus baseline offset | formal-thin `[^5]` regression test |
| Chapter 4.4 isolation | price path remains row-only | view-model equality test |
| External framing remains enforced | two deterministic lead phrases added to gates | framed/unframed quality tests |

## Verification

- Focused contract/producer/display/snapshot/renderer/quality: `263 passed`.
- Full suite: `2578 passed, 16 skipped`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Runtime import audit: no `openai`, composer, source packet reader, or JSONL reader reference in display/snapshot/renderer/quality files.

## Runtime Budget

| State | Net lines | Limit |
| --- | ---: | ---: |
| Initial implementation | +344 | +380 |
| After shared-contract refactor and live finding fix | +339 | +380 |

The narrative module is 167 lines. No report generation or live LLM call was run in this implementation session.

## Code Reduction

- Moved family titles, display order, scope normalization, unit keys, and unit indexing into the existing canonical card owner; no parallel contract module remains.
- Derived display order from the one family-title mapping instead of maintaining duplicate Chinese labels.
- Removed display-layer citation attachment; snapshot remains the single citation allocator and derives refs from canonical evidence units.
- Reused one external whitespace normalizer across card and narrative validation.
- Removed an unnecessary renderer scope-normalization dependency; narratives already carry normalized scope buckets.
- Live packs showed that the composer correctly emits `separate`, but the renderer previously flattened it into the same paragraph. `separate` now creates a Markdown paragraph boundary, while `continuation` remains inline and does not duplicate an existing `同时/此外` connector.
- Every separate paragraph now restates `据外部材料，`; this preserves low-credit framing after the paragraph boundary and fixes `external_map_unverified_claim_framing` without weakening the quality gate.

## Live Trial Findings

- Zhongji and Fudan memo envelopes were both `ready`; all 45 unit occurrences passed exact-prefix and ownership validation.
- Fresh reports passed report-quality, source-boundary, prose, CI, and citation-alignment checks.
- The final no-LLM rerun rendered all 26 visible `separate` paragraphs with explicit `据外部材料，` framing; both report-quality checks passed and Fudan retained only the pre-existing structural `external_viewpoint_overcompressed` warning.
- The first live render exposed two upstream canonical-unit issues that are intentionally not hidden in this renderer batch: editorial lead-ins such as `这里做一张清晰的对比表` / `资料来源`, and a few target-related units classified as peer/industry. These belong to External Producer source-unit hygiene and scope admission, not narrative formatting.

## Warnings / Deviations

- No blocker or design deviation found.
- The existing modified `2026-07-15-knowledge-persistence-slimming-6a2-codex-notes.md` and untracked `.superpowers/` directory were preserved and not edited by this task.
- Because this changes LLM composition behavior, representative live paragraphs still require user confirmation before merge.
