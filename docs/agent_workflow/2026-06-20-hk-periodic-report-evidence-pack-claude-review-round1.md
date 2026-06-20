# Claude Code Review: HK Periodic Report Evidence Pack

> **Design**: `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md`
> **Expected Output**: append feedback to the design under `## 10. Claude Review Log` or write concise notes in `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-claude-notes.md`

You are reviewing the design only. Do not implement code.

---

## Review Objective

Review whether the proposed HK evidence-pack support is the right next step before Knowledge/scoring integration. The design should let HK annual-report financial facts anchor to real evidence blocks while preserving current A-share behavior and fulltext material-layer guardrails.

---

## Files To Inspect

- `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md`
- `scripts/utils/periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_structured_facts.py`
- `tests/utils/test_periodic_report_structured_facts.py`
- `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md`

---

## Constraints

- Do not implement code.
- Do not access external websites.
- Do not start Chrome/CDP.
- Do not run report entries.
- Do not write `data/raw`, `reports`, or `knowledge`.
- Only write review notes/design feedback.

---

## Specific Review Questions

1. Should HK financial statement blocks use new usage names (`hk_income_statement_table`, etc.) or reuse A-share usages?
2. Is the proposed anti-five-year-summary rule strong enough?
3. Are the label variants sufficient for 黑芝麻-style Chinese HK annual reports?
4. Should loss-making HK companies map anything to `net_profit` in this task, or should operating loss / adjusted loss remain separate later facts?
5. Are the proposed tests sufficient to prevent A-share regressions?
6. Does the scope avoid pipeline/Knowledge/scoring changes?

---

## Required Response Format

```markdown
### Round 1 Feedback

Status: Ready as-is | Ready with nice-to-have | Must-fix before task | Blocked

Decision:
- R2 recommended: Yes/No
- Reason:

Findings:
- [Blocker/Must-fix/Nice-to-have] Finding with file/design reference and reason.

Recommendations:
- Concrete recommendation.

Open Questions:
- Question, if any.
```
