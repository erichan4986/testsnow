# Codex + Local Claude Code Collaboration Workflow

> **Purpose**: Use Codex as planner/reviewer and locally triggered Claude Code as reviewer/executor for major work, while keeping context transfer cheap, auditable, and bounded.

This workflow is intended for tasks that change architecture, reporting behavior, LLM prompts, scoring logic, data collection, or any other high-risk part of the stock report pipeline. For small, well-bounded tasks, prefer the lighter Direct Prompt Handoff described below instead of creating full workflow files.

Important constraint: in the Codex environment, Codex should not directly invoke Claude/Kimi against private project files. Codex prepares file-based prompts and reviews written outputs; the user runs Claude Code locally from their trusted terminal.

---

## 1. Roles

| Agent | Primary Role | Should Do | Should Avoid |
|------|--------------|-----------|--------------|
| Codex | Planner, prompt author, and reviewer | Define scope, write design, create Claude prompt files, review diff, run verification | Directly invoking external Claude/Kimi with private repo context, delegating vague tasks, accepting summaries without checking code/tests |
| User | Local trigger and risk owner | Run Claude Code locally, approve design, authorize risky data collection, confirm LLM synthesis quality when required | Pasting long transcripts when a notes file/diff is enough |
| Claude Code | Local reviewer and executor | Review design for implementation risks, implement locked tasks, run local checks, write concise notes | Broad refactors, changing data sources, weakening tests, modifying core business logic without explicit approval |

---

## 2. Workflow Levels

Do not use the full two-round workflow for every change. Pick the lightest level that protects quality.

| Level | Use When | Flow | Notes |
|-------|----------|------|-------|
| Level 0: Direct Prompt Handoff | Small implementation tasks with clear boundaries; usually 1-2 files; user wants Claude Code to write code but does not need file-based audit ceremony | Codex sends a short pasteable prompt -> user gives it to Claude -> Claude reports files/tests -> Codex reviews diff/tests | Most token-efficient handoff. No `docs/agent_workflow` files required. |
| Level 1: Codex Direct | Small typo fixes, narrow renderer copy edits, local test-only changes, simple docs updates, or user wants Codex to implement directly | Codex implements and verifies directly | No Claude handoff needed. |
| Level 2: File Task Handoff | Medium implementation tasks with clear scope; likely 1-3 files; behavior is testable; risk is moderate; audit trail is useful | Codex writes `claude-task.md` -> user runs Claude locally -> Codex reviews diff/tests | Skip two-round design review unless ambiguity appears. |
| Level 3: Full Design Review | High-risk or ambiguous work: prompts/LLM synthesis, scoring, technical algorithms, report structure, data collection, Xueqiu/Playwright/CDP, external APIs, or changes touching more than 3 files | Design -> Claude Round 1 -> Design Delta -> optional Round 2 only if needed -> Claude implement -> Codex review | Use the complete workflow below. |

Default to Level 0 when the user asks to "hand this to an agent" and the task is small. Default to Level 1 when the user wants speed and Codex can safely implement directly. Use Level 2 when the implementation needs a written boundary. Escalate to Level 3 when the task can affect data integrity, account safety, report correctness, or user-facing financial conclusions.

If Codex cannot reliably run a local browser or GUI-dependent verification inside the sandbox, such as Playwright/Chromium PDF export, screenshots, or visual preview checks that require macOS browser permissions, use Level 0 handoff. Codex should record the sandbox failure reason, give the user a pasteable prompt for local Claude Code, and review the resulting diff/output afterward instead of repeatedly requesting sandbox escalation.

Report trial runs should use the single-stock deep-report entry point by default, especially `scripts/run_黑芝麻智能.py --fast-test`. Fast-test mode skips Zhihu collection and ZhihuCurator/LLM token use while reusing cached input where available. Do not use `scripts/xueqiu_monitor_v2.py` for routine validation unless the task specifically concerns batch scheduling, batch collection, or the legacy monitor itself. The architectural direction is to keep deep-report capabilities in the single-stock pipeline (`run_*.py` / `PerStockReporter` / `report_skills`) and let `xueqiu_monitor_v2.py` become a lightweight batch report/collection coordinator.

---

## 3. Lessons From The CDP Extraction Pilot

The first pilot task validated the workflow:

- Claude Round 1 caught a real design bug: `extract_detail.py` passed `cdp_url` to `DetailPageFetcher`, but the fetcher did not accept that parameter.
- Codex final review caught an implementation risk: CDP cleanup could close the user's logged-in Chrome context/browser.
- The loop improved quality by putting design and implementation under different review pressure.

The pilot and Wind Excel loader task also showed where to keep the process lean:

- Full two-round design review is valuable for high-risk tasks, but too heavy for small changes.
- Round 2 should be conditional, not automatic. If Round 1 has no blockers and no unresolved high-risk design changes, Codex should write a compact design delta and proceed to task.
- For light implementation work, a short pasteable agent prompt plus Codex diff review is often cheaper than writing a full task file.
- The main quality gain comes from Codex reviewing the actual diff and running focused verification, not from making every handoff ceremony-heavy.
- Codex should not spend tokens reading full chat transcripts; Claude should write concise notes and Codex should inspect actual diffs.
- Focused tests are usually enough per iteration. Run full `pytest` once to identify global blockers, then avoid repeating known unrelated failures on every small fix.
- Review prompts should be short once the workflow is established; the task file carries the details.

---

## 4. Token And Efficiency Rules

The workflow saves Codex tokens only when context transfer stays disciplined. For small tasks, avoid creating long design/task files unless the audit record is worth the cost.

- Prefer Level 0 short prompts for narrow, low-risk implementation tasks.
- Use Markdown files as the handoff boundary.
- Prefer `git diff`, notes, and focused tests over pasted transcripts.
- Keep Claude notes to: files changed, tests run, deviations, blockers.
- Keep Codex tasks narrow enough that the full diff is reviewable.
- Avoid full design ceremony for Level 1 and most Level 2 tasks.
- For Level 3 tasks, keep Claude review rounds bounded: review design only, no implementation in review rounds.
- Replace long Codex response documents with a compact "Design Delta" section: accepted items, rejected items with reason, changed sections. Do not restate the whole design.
- Run Round 2 only when Round 1 has blockers, unresolved `must-fix` items, or changes that affect data integrity, account safety, scoring/technical algorithms, LLM prompts, report structure, or external data access.
- If full `pytest` has a known unrelated collection failure, record it once in the review file and rely on focused tests for subsequent fix rounds.

---

## 5. When To Use This Workflow

Use Level 0 direct prompt handoff for:

- Small parser/loader/adapter changes with focused tests.
- A local bug fix where allowed files are obvious.
- A single renderer or skill behavior tweak that does not change core scoring, algorithms, prompts, or data-source contracts.
- Report trial runs where the task is to run an existing single-stock entry point, record generated files, and check quality without modifying code. Prefer `scripts/run_黑芝麻智能.py --fast-test`; avoid `scripts/xueqiu_monitor_v2.py` unless validating batch behavior. Run the full single-stock entry without `--fast-test` only when the task explicitly requires refreshing Zhihu/LLM materials.
- Browser/PDF/visual verifications that Codex cannot run in the sandbox but Claude Code can run locally.
- Cases where the user explicitly asks for an agent prompt and does not ask for workflow files.

Use Level 3 full design review for:

- Major plan/design work.
- Changes touching `KnowledgeSynthesizer`, report structure, prompts, or LLM synthesis logic.
- Changes touching `scoring_engine.py`, technical analysis algorithms, risk scoring, or report completeness checks.
- Data collection changes, especially anything involving Xueqiu, Playwright, CDP, or external APIs.
- Any work expected to touch more than 3 files or require multiple verification commands.

Use Level 2 task handoff for:

- Well-scoped implementation tasks with clear tests.
- Small bug fixes that benefit from Claude doing the coding and Codex doing review.
- Refactors where the boundaries are already agreed.
- Tasks where an audit trail in `docs/agent_workflow` is useful even if no design review is needed.

Use Level 1 Codex direct work for:

- Small documentation edits.
- Typo/copy fixes.
- Very narrow tests or local-only cleanup.

For small typo fixes, narrow renderer copy edits, or local test-only changes, normal Codex-only work is enough.

---

## 6. File Layout

Create one dated folder or dated file set per task:

```text
docs/agent_workflow/
  YYYY-MM-DD-topic-design.md
  YYYY-MM-DD-topic-claude-task.md
  YYYY-MM-DD-topic-claude-notes.md
  YYYY-MM-DD-topic-codex-review.md
```

Keep all agent-to-agent communication in these files. Do not paste full chat transcripts back into Codex unless there is a specific issue to inspect.

---

## 7. Level 0 Direct Prompt Handoff

Use this when the task is small and the user wants Claude Code to implement. Codex does not create workflow files. Codex sends a short, pasteable prompt and later verifies the actual diff.

The prompt should contain:

- Goal in one sentence.
- Allowed files or directories.
- Files/areas that must not change.
- Required focused tests.
- Completion report format.
- Stop conditions.

Template:

```text
You are Claude Code working in /Users/erichan/testsnow.

Goal:
[one-sentence goal]

Allowed changes:
- [file or directory]
- [test file]

Do not modify:
- Entry scripts unless listed above
- scoring_engine.py, technical_analyzer.py, KnowledgeSynthesizer
- data/raw, reports, knowledge
- unrelated formatting or refactors

Requirements:
1. Write the failing test first, then implement the minimal fix.
2. Do not access external websites, start Chrome, or fetch Xueqiu detail pages.
3. Run: [focused pytest command]
4. Reply with files changed, tests run/results, deviations, and blockers.

Stop if:
- You need to change files outside the allowed list.
- You need to modify scoring/technical algorithms/LLM prompts.
- Tests reveal a broad unrelated failure.
```

Codex review after Level 0:

1. Inspect `git diff` for the allowed files.
2. Read any Claude summary/notes, but do not rely on it alone.
3. Run the focused tests.
4. Run a sample report or quality check only if the task affects report output.
5. Report accepted/rework with concrete findings.

Report trial run template:

```text
You are Claude Code working in /Users/erichan/testsnow. Run a report trial only; do not modify code.

Goal:
Run the existing single-stock report entry point for [stock name], confirm Markdown/HTML/PDF outputs, and record the quality-check result.

Do not:
- Modify code.
- Fetch Xueqiu detail pages.
- Start or control a logged-in Chrome/CDP session.
- Change scoring, technical analysis, LLM prompts, or report templates.
- Modify existing data/raw or reports files except outputs naturally produced by the report entry point.
- Run scripts/xueqiu_monitor_v2.py unless this validation is explicitly about batch scheduling or the legacy monitor.
- Refresh Zhihu content or run ZhihuCurator/LLM filtering unless the task explicitly requires it.

Steps:
1. Run the single-stock entry point: [script path, default scripts/run_黑芝麻智能.py --fast-test].
2. If Markdown is generated, run: python3 scripts/check_report_quality.py [generated markdown path].
3. Record Markdown, HTML, and PDF paths and file sizes.
4. Briefly check whether the report includes trend background, daily structure, weekly structure, volume confirmation, volatility condition, score, confidence, and risk warning.
5. Do not fix problems; only report them.

Reply with:
- Entry point run.
- Files generated.
- Quality check PASS/FAIL/WARNING.
- Main warnings/errors.
- Network, LLM, Chrome/PDF issues.
- Any obvious report contradictions.
- Whether git status shows unexpected changes beyond generated report/input files.
```

Local browser/PDF verification template:

```text
You are Claude Code working in /Users/erichan/testsnow. Run a local browser/PDF verification.

Goal:
Verify [specific goal, for example regenerate reports/黑芝麻智能_20260611.pdf and confirm all images are fully visible and not cropped].

Allowed changes:
- If a code fix is needed, only modify: [files]
- Focused tests: [test files]

Do not:
- Fetch Xueqiu detail pages.
- Connect to or control a logged-in Chrome/CDP session.
- Modify scoring logic, technical analysis algorithms, LLM prompts, or core report structure.
- Perform unrelated refactors or formatting.
- Delete existing reports/data. Natural overwrite of the target PDF/report output is acceptable.

Requirements:
1. If code changes are needed, keep/write the failing test first and implement the minimal fix.
2. Run the required local Playwright/Chromium/PDF export verification.
3. Inspect the generated PDF or screenshots for image scaling, full visibility, and cropping/overflow.
4. Run the focused tests: [commands].

Reply with:
- Files changed, if any.
- Which PDF/screenshot/browser output was verified.
- Focused test results.
- Whether any report image is still cropped or overflowing.
- git status entries for generated reports/cache files.
- Blockers or diff areas Codex should review.
```

---

## 8. Required Flow For Level 3 Major Tasks

This is a user-triggered handoff flow. Codex writes the prompts; the user runs Claude Code locally; Claude writes feedback or implementation notes into repository files; Codex reviews those files and the actual diff.

### Step 1: Codex Drafts Design

Codex writes `YYYY-MM-DD-topic-design.md` with:

- Goal and non-goals.
- Current system context.
- Proposed architecture.
- Files expected to change.
- Data source and anti-fabrication constraints.
- Failure modes: what can break, how it would show up, and which test catches it.
- Testing and report-generation acceptance gates.
- Open questions requiring user confirmation.

### Step 2: Codex Writes Claude Round 1 Review Prompt

Codex writes `YYYY-MM-DD-topic-claude-review-round1.md`.

The prompt must:

- Tell Claude Code not to implement code.
- List the exact files to inspect.
- Define the expected feedback format.
- Require feedback to be written back into the design review log or a notes file.
- Forbid real Xueqiu fetching, browser startup, or risky external actions unless explicitly authorized.

Codex then gives the user a pasteable prompt for Claude Code. A local command may be included only as optional convenience, not as the primary handoff artifact.

### Step 3: User Runs Claude Round 1 Locally

The user runs Claude Code from the local terminal, for example:

```bash
claude -p --permission-mode plan --max-budget-usd 0.08 < docs/agent_workflow/YYYY-MM-DD-topic-claude-review-round1.md
```

If local provider prompts or plugin setup require interaction, the user may run Claude interactively instead:

```bash
claude docs/agent_workflow/YYYY-MM-DD-topic-claude-review-round1.md
```

Claude Code reads only the design and relevant files. It writes comments into the design or a notes file.

Round 1 should focus on:

- Missing implementation details.
- Risky assumptions.
- Existing code paths the design forgot.
- Test gaps.
- Places where the task is too broad.

Round 1 findings must be labeled as:

- `blocker`: cannot proceed without user/Codex decision.
- `must-fix`: design should change before task writing.
- `nice-to-have`: optional improvement that should not block task writing.

Claude Code should not implement code in this step.

### Step 4: Codex Revises Design And Writes Design Delta

Codex updates the design and records material decisions in a compact `Design Delta` section.

The delta should contain only:

- `Accepted` items: what changed and which section changed.
- `Rejected` items: short technical reason.
- `Deferred` items: why they are out of scope.
- `R2 Required`: yes/no, with reason.

Codex should not write a separate long `codex-response.md` unless the user explicitly asks for one. Codex may reject Claude Code suggestions, but must write the reason when rejecting anything that affects scope, data quality, or test coverage.

### Step 5: Decide Whether Round 2 Is Required

Skip Round 2 and proceed to implementation task when Round 1 has only `nice-to-have` items or straightforward accepted `must-fix` changes that Codex fully resolved in the design delta.

Run Round 2 only when:

- Claude reports `Blocked`.
- Any `blocker` remains unresolved.
- A `must-fix` changes architecture, file boundaries, data contracts, prompts, scoring, technical algorithms, report structure, external APIs, Xueqiu/Playwright/CDP behavior, or account-safety controls.
- Codex rejects a `must-fix` item and the technical disagreement matters to correctness.
- The design changed enough that a second reviewer pass is cheaper than catching mistakes during implementation.

### Step 6: Codex Writes Claude Round 2 Review Prompt When Required

Codex writes `YYYY-MM-DD-topic-claude-review-round2.md`.

Round 2 should ask only whether the revised design is:

- `Ready to implement`
- `Blocked: needs user decision`
- `Blocked: design still ambiguous`

### Step 7: User Runs Claude Round 2 Locally When Required

Claude Code performs a second review and writes one of:

- `Ready to implement`
- `Blocked: needs user decision`
- `Blocked: design still ambiguous`

If blocked, Codex resolves the issue before implementation.

### Step 8: Codex Writes Claude Implementation Task

Codex writes `YYYY-MM-DD-topic-claude-task.md`.

The task must include:

- Exact scope.
- Files allowed to modify.
- Files that must not be modified.
- Required tests.
- Required notes format.
- Stop conditions.

Codex then gives the user a pasteable prompt for Claude Code. A local command may be included only as optional convenience, not as the primary handoff artifact.

### Step 9: User Runs Claude Implementation Locally

Claude Code implements the task and writes `YYYY-MM-DD-topic-claude-notes.md`.

Notes must be concise and include:

- Files changed.
- Behavior changed.
- Tests run and exact pass/fail result.
- Any unresolved issues.
- Any deviations from the task.
- Requirement-to-implementation-to-test matrix for non-trivial tasks.

### Step 10: Codex Reviews and Verifies

Codex reviews the actual diff, not only Claude Code's notes.

Codex must verify:

- Scope stayed within the task.
- Tests pass or failures are explained.
- Report-generation acceptance gates pass when required.
- No Xueqiu, LLM, or external data constraints were violated.
- Any prompt/synthesis changes have user-visible sample output for confirmation.
- Each important design requirement maps to implementation and tests.

Codex writes `YYYY-MM-DD-topic-codex-review.md` with findings and final status.

---

## 9. Level 2 File Task Handoff Flow

Use this for medium tasks where the design is already clear.

1. Codex writes `YYYY-MM-DD-topic-claude-task.md`.
2. User runs Claude Code locally.
3. Claude implements and writes `YYYY-MM-DD-topic-claude-notes.md`.
4. Codex reviews actual diff and runs focused verification.
5. Codex writes `YYYY-MM-DD-topic-codex-review.md`.

Level 2 still requires strict scope, allowed files, stop conditions, and tests. It simply skips the two design review rounds.

---

## 10. Why Codex Does Not Directly Run Claude Here

Codex may be able to execute local shell commands, but this environment has sandbox, network, and data-export controls. Directly invoking Claude/Kimi from Codex can fail because:

- The Codex sandbox may not have access to the user's local provider, cc-switch, proxy, or `~/.claude` state.
- Network attempts may fail before any model tokens are consumed.
- Escalated execution may be denied because it would send private repository context to an external model provider.

Therefore the stable contract is:

```text
Level 0:
  Codex writes a short pasteable prompt
  -> user gives it to Claude Code locally
  -> Claude writes files and reports files/tests
  -> Codex reviews files/diff

Level 2/3:
  Codex writes prompt files
  -> user runs Claude Code locally
  -> Claude writes notes/files/diff
  -> Codex reviews files/diff
```

Codex should not attempt indirect workarounds for this restriction.

---

## 11. Token-Saving Rules

- Transfer state through Markdown files, not chat transcripts.
- For Level 0, transfer only the short prompt and Claude's concise files/tests summary; do not paste full transcripts.
- Claude Code should summarize command output instead of pasting full logs.
- Codex should inspect diffs and targeted files instead of reading entire generated reports unless report quality is the subject.
- Claude Code should stop and ask when scope changes, rather than solving a larger problem opportunistically.
- Keep each task small enough that Codex can review the full diff comfortably.
- Prefer local Claude commands with small `--max-budget-usd` values during review rounds.

---

## 12. Project-Specific Guardrails

- Do not rewrite the repository.
- Do not replace established data sources without explicit design approval and field compatibility tests.
- Do not batch-fetch Xueqiu detail pages unless the user confirms a logged-in Chrome CDP session and the script respects the 3-5 second delay rule.
- Do not modify `KnowledgeSynthesizer` prompt or synthesis logic without showing sample output to the user before final acceptance.
- Do not modify scoring or technical-analysis thresholds without tests that prove the new behavior.
- Do not accept a report as complete unless it satisfies the technical, fundamental, risk, and citation completeness requirements in `AGENTS.md`.

---

## 13. Recommended Handoff Patterns

When the user asks for an agent handoff, Codex should provide a pasteable prompt as the primary artifact. Do not respond with only a shell command.

Use Level 0 short prompts for light tasks. Use file-based prompts when asking Claude Code to review larger designs:

```bash
claude -p --permission-mode plan --max-budget-usd 0.08 < docs/agent_workflow/YYYY-MM-DD-topic-claude-review-round1.md
claude -p --permission-mode plan --max-budget-usd 0.08 < docs/agent_workflow/YYYY-MM-DD-topic-claude-review-round2.md
```

Use file-based prompts when asking Claude Code to implement:

```bash
claude < docs/agent_workflow/YYYY-MM-DD-topic-claude-task.md
```

If the Claude Code setup supports a different command, keep the same file contract and write the actual command used into `YYYY-MM-DD-topic-claude-notes.md`.

After Claude finishes, tell Codex which files changed. Codex will read the files and `git diff` instead of relying on pasted transcripts.
