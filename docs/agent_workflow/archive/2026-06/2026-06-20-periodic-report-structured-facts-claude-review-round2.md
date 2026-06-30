# Claude Code Review Round 2: Periodic Report Structured Facts

> **Design**: `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md`
> **Expected Output**: append feedback to the design under `## 11. Claude Review Log` or write concise notes in `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-claude-notes.md`
> **Local Runner**: user runs this prompt from local trusted terminal

You are doing a narrow Round 2 design review. Do not implement code.

---

## 1. Review Scope

Only review whether the Round 1 must-fix items have been resolved well enough for Phase A helper-only implementation.

Focus on:

1. Evidence anchoring for `revenue`, `net_profit`, and `operating_cash_flow`.
2. Signed operating cash flow ratio and `cashflow_quality_weak` behavior.
3. Conservative Phase A gating for `periodic_report_filing_fact` (`confidence` separate from `source_credit`, no Knowledge/scoring registration yet).
4. Phase B decision to persist only filing facts, not derived facts.

Do not re-review unrelated architecture unless you see a new blocker caused by the changes.

---

## 2. Files To Inspect

- `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/synthesis_credit.py`
- `tests/reporter/test_fulltext_material_isolation.py`

---

## 3. Constraints

- Do not implement code.
- Do not modify source, tests, config, prompts, data, reports, or knowledge.
- Only write review feedback to the design or notes file.
- Do not access external websites.
- Do not start Chrome/CDP.
- Do not run report entries.

---

## 4. Required Response Format

```markdown
### Round 2 Feedback

Status: Ready to implement | Needs minor fixes | Blocked

Decision:
- Phase A implementation allowed: Yes/No
- Reason:

Findings:
- [Blocker/Must-fix/Nice-to-have] Finding with file/design reference and reason.

Implementation Notes:
- Concrete constraints Phase A implementer must follow.
```
