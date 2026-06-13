# Claude Code Task: <Task Name>

> **Design**: `docs/agent_workflow/YYYY-MM-DD-topic-design.md`
> **Notes Output**: `docs/agent_workflow/YYYY-MM-DD-topic-claude-notes.md`
> **Local Runner**: user runs this prompt from their local trusted terminal

You are implementing a locked task from the design above. Stay within scope.

---

## 0. Local Command

Recommended local command:

```bash
claude < docs/agent_workflow/YYYY-MM-DD-topic-claude-task.md
```

Record the actual command used in the notes output file.

---

## 1. Objective

State the exact implementation objective.

---

## 2. Allowed Changes

You may modify:

- `path/to/file.py` — reason
- `tests/path/to/test_file.py` — reason

---

## 3. Do Not Modify

Do not modify:

- Entry points: `scripts/xueqiu_monitor_v2.py`, `scripts/run_*.py`, `scripts/run_technical_analysis.py`, unless explicitly listed above.
- Core scoring or technical thresholds unless explicitly required by the design.
- Data source selection unless explicitly required by the design.
- Existing generated reports unless the task is specifically about report output fixtures.

Add task-specific no-touch areas here.

---

## 4. Implementation Steps

1. Read the design and relevant files.
2. Make the smallest scoped code or documentation changes needed.
3. Add or update focused tests.
4. Run the required verification commands.
5. Write concise notes to the notes output path.
6. Fill in the requirement-test matrix in the notes file for every non-trivial design requirement.

---

## 5. Required Verification

Run:

```bash
pytest
```

Add narrower commands here:

```bash
pytest tests/path/to/test_file.py -v
```

If a command cannot run, record the exact reason in the notes file.

---

## 6. Stop Conditions

Stop and write the blocker into the notes file if:

- The implementation requires changing files outside the allowed list.
- The design contradicts current code.
- Tests reveal a broader regression unrelated to this task.
- Xueqiu detail-page fetching or another risky external action would be required.
- LLM synthesis output changes require user confirmation.

---

## 7. Required Notes Format

Write `docs/agent_workflow/YYYY-MM-DD-topic-claude-notes.md` with:

```markdown
# Claude Notes: <Task Name>

## Summary

- 

## Files Changed

- 

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
|  |  |  |

## Requirement-Test Matrix

| Design Requirement | Implementation Location | Test/Verification |
|--------------------|-------------------------|-------------------|
|  |  |  |

## Local Command Used

```bash

```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
```
