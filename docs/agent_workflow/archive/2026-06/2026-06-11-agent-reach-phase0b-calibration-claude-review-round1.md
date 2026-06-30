# Claude Code Review Round 1: Agent-Reach Phase 0B RSS/Web Calibration

> **Design**: `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-design.md`
> **Runtime Validation Notes**: `docs/agent_workflow/2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md`
> **Expected Output**: write review notes to `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-claude-notes.md`
> **Local Runner**: user runs this prompt from the local trusted terminal

You are reviewing the design only. Do not implement code in this round.

---

## 1. Review Objective

Review whether Phase 0B is the right next step after runtime validation of Agent-Reach Phase 0.

Specifically verify:

1. Whether replacing or disabling broken default RSS feeds is the right approach.
2. Whether tightening RSS filter terms avoids broad false positives without making the connector useless.
3. Whether source-aware RSS/Web quality scoring is safer than globally lowering keep thresholds.
4. Whether portal-page detection belongs in the quality gate instead of WebConnector.
5. Whether the proposed test plan catches the actual runtime-validation failures.

The outcome should be either:

- `Ready to implement`
- `Ready with changes`
- `Blocked`

---

## 2. Files To Inspect

Read:

- `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-design.md`
- `docs/agent_workflow/2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md`
- `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-codex-implementation-review.md`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_quality_skill.py`

Optional if useful:

- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`

---

## 3. Constraints

- Do not implement code.
- Do not modify source files.
- Do not fetch external pages or start browsers.
- Do not add or recommend account/cookie/login platforms.
- Do not recommend changing `KnowledgeSynthesizer`, scoring engine, technical analysis, Xueqiu/CDP, or entry scripts.
- Keep the review concise and actionable.

---

## 4. Review Questions

Please explicitly answer:

1. Should Phase 0B use a small known-good default RSS list, or no default RSS feeds unless `agent_reach_rss_feeds` is supplied?
2. Is removing generic filter terms such as standalone `科技` sufficient, or should query generation require stock name/code only for RSS?
3. Is neutral engagement scoring (+5) for RSS/Web a reasonable first calibration, or should the 10 engagement points be reallocated to evidence/substance?
4. Should portal detection force discard, or apply a soft penalty?
5. Are any tests missing to prevent the validation failures from recurring?

---

## 5. Required Response Format

Write `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-claude-notes.md`:

```markdown
# Claude Review Round 1: Agent-Reach Phase 0B Calibration

Status: Ready to implement / Ready with changes / Blocked

## Findings

- [Severity: High/Medium/Low] Finding with file reference and reason.

## Recommendations

- Concrete recommendation.

## Answers To Review Questions

1. ...
2. ...
3. ...
4. ...
5. ...

## Suggested Implementation Scope

List exact files that should change if implementation proceeds.

## Suggested Tests

List exact tests or test scenarios.
```

Do not write code in this round.
