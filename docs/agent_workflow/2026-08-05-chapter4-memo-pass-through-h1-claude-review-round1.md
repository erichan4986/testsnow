# Chapter 4 Memo Pass-Through H1 Claude Review Round 1

You are the read-only repository reviewer for a Level 3 refactor in:

`/Users/erichan/testsnow`

Read these files completely:

- `docs/agent_workflow/2026-08-05-chapter4-memo-pass-through-batch-h-audit.md`
- `docs/agent_workflow/2026-08-05-chapter4-memo-pass-through-h1-design.md`
- `docs/agent_workflow/2026-08-05-chapter4-memo-pass-through-h1-codex-self-review-round1-notes.md`
- `docs/agent_workflow/2026-08-05-chapter4-memo-pass-through-h1-codex-self-review-round2-notes.md`

Inspect the real runtime and tests, especially:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/annual_report_material_pack.py`
- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `scripts/utils/broker_research_digest_synthesis_items.py`
- every test file listed in the design's allowed scope.

## Review Goal

Decide whether H1 can remove `annual_report_memo.v1` and
`broker_research_memo.v1` while preserving current behavior and achieving a
meaningful runtime reduction.

Audit these points with file/line evidence:

1. all runtime consumers of both memo ctx keys/schemas are covered;
2. current-card-over-pack precedence is preserved;
3. annual visible cleanup remains display-only and does not alter source-unit
   substring contracts;
4. canonical-family admission is sufficient for every configured pack and
   in-memory producer path;
5. annual status, broker status, usable counts, six projected rows, and profile
   routing remain exactly equivalent;
6. preloaded broker items bypass disk loading and a missing key loads once;
7. mixed broker citation allocation preserves selected-item IDs before grouped
   row emission;
8. `formal_citation_candidate_count` exactly replaces current
   `memo_refs_resolved` behavior;
9. direct formal refs preserve the external full-snapshot offset;
10. the allowed runtime/test scope is complete;
11. net runtime reduction of at least 110 lines is credible without compressed
    or duplicated logic;
12. the test matrix catches A-share, HK, multi-institution, single-institution,
    absent, stale-pack, suspicious-zero, and citation regressions.

Also check that H1 does not accidentally implement H2 changes: no annual bound,
broker cap, sparse admission, profile, prompt, scoring, target, risk, technical,
recommendation, producer, data, Knowledge, or report-template change.

## Output

Write only:

`docs/agent_workflow/2026-08-05-chapter4-memo-pass-through-h1-claude-review-round1-notes.md`

Use this structure:

- `verdict: ok|needs_revision`
- `implementation_ready: yes|no`
- `blockers`
- `must_fix`
- `nice_to_have`
- `requirement_test_gaps`
- `scope_and_budget_assessment`
- `recommended_next_step`

For each finding, cite exact file and line. Do not modify design, runtime,
tests, configuration, prompts, data, Knowledge notes, reports, or git state.
Do not run network, LLM, Chrome/CDP, report generation, or destructive git
commands. Stop after writing the review notes.
