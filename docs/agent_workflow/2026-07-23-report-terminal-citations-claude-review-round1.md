# Claude Review Prompt: Report Terminal Citations Round 1

You are the read-only design reviewer in:

`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

Review:

`docs/agent_workflow/2026-07-23-report-terminal-citations-design.md`

Inspect the real implementation and tests, especially:

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/report_quality.py`
- `scripts/utils/report_prose_quality.py`
- `scripts/utils/report_source_boundary.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_assembly_skills.py`

Do not modify code, tests, data, knowledge, reports, prompts, or the design. Write findings to:

`docs/agent_workflow/2026-07-23-report-terminal-citations-claude-review-round1-notes.md`

Review for:

1. Whether exact-heading detachment can truncate any Chapter 4 or report-tail content.
2. Whether global citation IDs, aliases, formal-thin offsets, and reserved executive-summary refs remain exact.
3. Whether deleting every local source list can hide a source not admitted by the global visible-ref filter.
4. Whether quality/source-boundary/prose checks assume local lists or the old appendix position.
5. Whether all profile and no-citation paths are covered.
6. Whether a simpler owner boundary exists without adding a second citation aggregator.
7. Whether unique-ref and global no-URL fallback parsing preserve the duplicate-source warning semantics.
8. Whether runtime can remain net non-positive and under the `+60` hard stop.

Classify findings as `blocker`, `must-fix`, or `nice-to-have`, include a requirement-test matrix, and end with:

- `verdict: ok|needs_revision`
- `implementation_ready: yes|no`

Stop after writing the notes. Do not implement anything.
