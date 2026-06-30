# Claude Code Review: Periodic Report Structured Facts

> **Design**: `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md`
> **Expected Output**: append feedback to the design under `## 11. Claude Review Log` or write concise notes in `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-claude-notes.md`
> **Local Runner**: user runs this prompt from local trusted terminal

You are reviewing the design only. Do not implement code in this round.

---

## 1. Review Objective

Review whether the proposed `periodic_report_structured_facts` design safely separates:

- existing fulltext material-layer summaries;
- exact filing facts;
- derived facts;
- typed filing risk signals.

The key question: can this design eventually let annual-report facts enter Knowledge/scoring without reopening the leakage risks we just closed for `periodic_report_fulltext_analysis`?

---

## 2. Files To Inspect

- `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md`
- `docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md`
- `docs/agent_workflow/context_index.md`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `tests/reporter/test_fulltext_material_isolation.py`
- `tools/ci_grep_gates.sh`

---

## 3. Constraints

- Do not implement code.
- Do not fetch external pages.
- Do not start Chrome/CDP.
- Do not modify scoring, risk, Knowledge, synthesis, or data collection code.
- Keep feedback concise and actionable.

---

## 4. Specific Review Questions

1. Is the source-type split strong enough to keep `periodic_report_fulltext_analysis` material-only while allowing future `periodic_report_filing_fact` into Knowledge/scoring?
2. Is the proposed fact schema sufficient for evidence binding, unit normalization, restated/as-reported distinction, and future invalidation?
3. Are `derived_facts` safe to persist in Phase B, or should only original `filing_facts` persist first?
4. Does the Phase A helper-only scope avoid changing runtime behavior?
5. Are the failure modes and tests enough to catch fabrication, unit-scale errors, stale derived facts, prose-based risk scoring, and scoring leakage?
6. Are there any existing helper functions or schemas this design should reuse more directly?

---

## 5. Required Response Format

```markdown
### Round 1 Feedback

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
