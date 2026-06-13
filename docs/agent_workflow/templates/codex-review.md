# Codex Review: <Task Name>

> **Design**: `docs/agent_workflow/YYYY-MM-DD-topic-design.md`
> **Claude Task**: `docs/agent_workflow/YYYY-MM-DD-topic-claude-task.md`
> **Claude Notes**: `docs/agent_workflow/YYYY-MM-DD-topic-claude-notes.md`
> **Status**: Accepted | Changes Requested | Blocked

---

## 1. Scope Review

| Check | Result | Notes |
|-------|--------|-------|
| Changes match the locked task | Pass/Fail |  |
| No out-of-scope files modified | Pass/Fail |  |
| Existing entry points preserved | Pass/Fail |  |
| Data-source constraints preserved | Pass/Fail |  |
| Claude was user-triggered locally, not invoked by Codex against external provider | Pass/Fail |  |
| Forbidden/no-touch files unchanged | Pass/Fail |  |
| Requirement-test matrix complete for non-trivial task | Pass/Fail/Not Applicable |  |

---

## 2. Findings

List issues first, ordered by severity. Use file and line references when possible.

- None.

---

## 3. Verification

| Command | Result | Notes |
|---------|--------|-------|
|  | Pass/Fail/Not Run |  |

### Forbidden Change Check

| Check | Result | Notes |
|-------|--------|-------|
| Manual `git diff --name-only` checked against no-touch list | Pass/Fail |  |
| `scripts/check_forbidden_changes.py` run, if available | Pass/Fail/Not Available |  |

---

## 4. Report Quality Checks

| Check | Result | Notes |
|-------|--------|-------|
| Technical report completeness | Pass/Fail/Not Applicable |  |
| Fundamental report completeness | Pass/Fail/Not Applicable |  |
| Risk disclosure completeness | Pass/Fail/Not Applicable |  |
| Citation traceability | Pass/Fail/Not Applicable |  |
| LLM sample output reviewed by user | Pass/Fail/Not Applicable |  |

---

## 5. Final Decision

State whether the work is accepted, needs changes, or is blocked.
