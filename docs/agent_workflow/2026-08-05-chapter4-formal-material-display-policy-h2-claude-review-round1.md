# Chapter 4 Formal Material Display Policy H2 Review Prompt

You are a read-only reviewer in `/Users/erichan/testsnow`.

Read:

- `docs/agent_workflow/2026-08-05-chapter4-formal-material-display-policy-h2-design.md`
- `docs/agent_workflow/2026-08-05-chapter4-formal-material-display-policy-h2-codex-self-review-round1-notes.md`
- `docs/agent_workflow/2026-08-05-chapter4-formal-material-display-policy-h2-codex-self-review-round2-notes.md`
- the real current diff and relevant runtime/tests.

Review only. Do not modify runtime, tests, config, prompts, data, Knowledge
notes, or reports.

Verify in particular:

1. removing the annual 300-character snapshot cut cannot bypass the existing
   annual display budgets or restore PDF/OCR noise;
2. removing `selected[:6]` and coverage `min(6, usable)` leaves one explicit
   loader budget and the existing formal-medium `5+2` display budget;
3. one guarded broker card can safely reuse `single_institution` without
   changing the evidence-profile branch or implying consensus;
4. sparse broker ownership suppresses only duplicate external facts and keeps
   external rows with a new anchor/event;
5. formal-thin citation offsets still use the full snapshot;
6. the tests cover long annual bodies, eight broker items, one-card admission,
   negative guards, profile equivalence, renderer attribution, external
   duplicate-versus-delta ownership, and mixed-source citation identity;
7. scope, pre-commit report validation, and runtime stop conditions are
   credible.

Write findings as `blocker / must-fix / nice-to-have`, include a compact
requirement-test gap table, and state `verdict: ok|needs_revision` plus
`implementation_ready: yes|no`.

Write the only output to:

`docs/agent_workflow/2026-08-05-chapter4-formal-material-display-policy-h2-claude-review-round1-notes.md`

Stop after writing the notes. Do not implement.
