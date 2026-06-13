# <Task Name> Design

> **Date**: YYYY-MM-DD
> **Owner**: Codex
> **Status**: Draft | Under Claude Review | Ready For Implementation | Blocked | Superseded

---

## 1. Goal

Describe the user-visible outcome in one or two paragraphs.

---

## 2. Non-Goals

- List behavior that is explicitly out of scope.
- List files, modules, data sources, or workflows that should not change.

---

## 3. Current Context

Summarize the relevant existing code paths, entry points, data files, and tests.

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
|  |  |  |

---

## 4. Proposed Design

Describe the intended architecture and data flow.

### 4.1 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
|  |  |  |  |

### 4.2 Data Flow

```text
source
  -> transform
  -> validation
  -> report output
```

### 4.3 Error Handling And Fallbacks

- Describe expected failures.
- Describe fallback behavior.
- Describe what must be visible in logs or report output.

---

## 5. Failure Modes And Tests

| Failure Mode | User/Runtime Symptom | Test Or Check That Catches It |
|--------------|----------------------|-------------------------------|
|  |  |  |

---

## 6. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
|  |  |  |

---

## 7. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
|  |  |

---

## 8. Data And Reporting Constraints

- Data must come from actual API responses, local collected files, or explicitly provided fixtures.
- LLM synthesis must not fabricate data.
- Citation markers must map to source list entries.
- Xueqiu detail-page access requires logged-in Chrome CDP and 3-5 second request spacing.

Add task-specific constraints here.

---

## 9. Acceptance Gates

### Tests

```bash
pytest
```

Add narrower required tests here.

### Report Generation

```bash
cd scripts
python run_黑芝麻智能.py
```

State whether report generation is required for this task. If not required, explain why.

### Manual Review

- Technical analysis completeness:
- Fundamental analysis completeness:
- Risk disclosure completeness:
- Citation traceability:
- Prompt/sample-output user confirmation:

---

## 10. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
|  |  |  |

---

## 11. Claude Review Log

### Round 1 Feedback

- Pending.

### Design Delta After Round 1

Accepted:
- Pending.

Rejected:
- Pending.

Deferred:
- Pending.

R2 Required:
- Pending.

### Round 2 Feedback

- Not run unless required.

### Final Implementation Readiness

- Pending.
