# Public Compatibility Cleanup Batch F1 Implementation Notes

## Result

- Verdict: `PASS`
- Runtime delta: `0 added / 1,225 removed`
- Isolated test delta: `0 added / 790 removed`
- Canonical External Producer v4 runtime was not modified.

## Modified Files

Deleted runtime modules:

- `scripts/utils/social_viewpoint_source_packets.py`
- `scripts/utils/curated_external_video_subtitles.py`
- `scripts/utils/curated_external_candidate_discovery.py`

Deleted isolated tests:

- `tests/utils/test_social_viewpoint_source_packets.py`
- `tests/utils/test_curated_external_video_subtitles.py`
- `tests/utils/test_curated_external_candidate_discovery.py`

Updated:

- `tests/test_runtime_hygiene.py`
- Batch F audit and this implementation record

## TDD Evidence

1. RED: `test_batch_f1_detached_external_preview_utilities_are_absent` failed because `social_viewpoint_source_packets.py` still existed.
2. GREEN: the target test passed after deleting the locked six-file group.
3. Focused External Producer v4 suite: `152 passed`.
4. Full repository suite: `2857 passed, 10 skipped`.

## Verification

- Active-reference search found only the new negative hygiene assertions and the historical preview-layout absence contract.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Black Sesame offline report smoke: exit 0; Markdown, HTML, and audit sidecar generated under `/tmp/testsnow_offline_smoke/`.
- No network, browser, LLM, data, knowledge, report, scoring, risk, citation, or technical-algorithm behavior was changed.

## Deletion Proof

- Candidate discovery and video subtitle preview entry scripts were intentionally removed in commit `48a893d`.
- The social viewpoint preview entry was intentionally removed in commit `cb35b7b` during External Producer v3 cutover.
- The surviving utility modules had no active runtime, preview, tool, README command, package export, or dynamic registry caller.
- External Producer v4 focused tests prove the canonical pack/scope/source/evidence/display/snapshot path remains intact.

## Blockers, Warnings, Deviations

- Blocker: none.
- Warning: direct out-of-repository imports of the three undocumented utility modules will fail; this is the user-approved internal hard cut.
- Deviation: none.
- Public/manual tools (`WechatSogouFetcher`, `JudgmentGenerator`) and reporter package re-exports remain deferred to F2.
