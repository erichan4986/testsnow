# Claude Code Review: <Task Name>

> **Design**: `docs/agent_workflow/YYYY-MM-DD-topic-design.md`
> **Expected Output**: update the design review log or write `docs/agent_workflow/YYYY-MM-DD-topic-claude-notes.md`
> **Local Runner**: user runs this prompt from their local trusted terminal

You are reviewing the design only. Do not implement code in this round.

---

## 1. Local Command

Recommended local command:

```bash
claude -p --permission-mode plan --max-budget-usd 0.08 < docs/agent_workflow/YYYY-MM-DD-topic-claude-review-roundN.md
```

If provider setup needs interaction:

```bash
claude docs/agent_workflow/YYYY-MM-DD-topic-claude-review-roundN.md
```

---

## 2. Review Objective

State what Claude should verify.

---

## 3. Files To Inspect

- `path/to/file`

---

## 4. Constraints

- Do not implement code.
- Do not fetch external pages or start browsers unless explicitly authorized.
- Do not modify files outside the review output target.
- Keep feedback concise and actionable.

---

## 5. Required Response Format

```markdown
### Round N Feedback

Status: Ready as-is | Ready with nice-to-have | Must-fix before task | Blocked

Decision:
- R2 recommended: Yes/No
- Reason:

Findings:
- [Blocker/Must-fix/Nice-to-have] Finding with file reference and reason.

Recommendations:
- Concrete recommendation.

Open Questions:
- Question, if any.
```
