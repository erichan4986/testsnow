# Claude Code Review: Chapter 4 Architecture Slimming

> **Design**: `docs/agent_workflow/2026-07-10-chapter4-architecture-slimming-design.md`
> **Expected Output**: `docs/agent_workflow/2026-07-10-chapter4-architecture-slimming-claude-review-round1-notes.md`
> **Local Runner**: user runs this prompt from their local trusted terminal

You are reviewing the architecture design only. Do not implement code, change
runtime files, run a formal report, or refresh broker notes in this round.

## 1. Review Objective

Determine whether the proposed contract-first migration actually reduces
Chapter 4 coupling without changing report semantics or allowing annual,
broker, or external material to cross source boundaries.

Pay special attention to whether the design creates a real ownership boundary
or merely adds `Chapter4ViewModel` on top of the current large files.

## 2. Files To Inspect

- `docs/agent_workflow/2026-07-10-chapter4-architecture-slimming-design.md`
- `docs/agent_workflow/2026-07-06-deep-analysis-material-snapshot-design.md`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_quality.py`
- `scripts/utils/report_source_boundary.py`
- `scripts/utils/broker_research_digest.py`
- `scripts/utils/broker_research_digest_note_writer.py`
- `scripts/utils/broker_research_digest_synthesis_items.py`
- `scripts/utils/annual_report_material_pack.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_report_quality.py`
- `tests/reporter/test_report_source_boundary.py`
- `reports/中际旭创_20260710.md`
- `reports/复旦微电_20260708.md`

If an ignored report is absent from your checkout, note that limitation and
continue the code/design review. Do not regenerate it.

## 3. Questions To Answer

1. Is `Chapter4MaterialSkill` in the correct pipeline position, or would it
   accidentally run after information needed by scoring/recommendation has
   already been mixed?
2. Is extending the existing `EvidenceRow` preferable to adding another row
   schema? Identify any field that is redundant, underspecified, or likely to
   become renderer policy in disguise.
3. Can `Chapter4ViewModel` derive visible citations entirely from admitted
   rows, including local-ref collisions across annual, broker, and external
   producers?
4. Does Batch A remain behavior-preserving, or does any proposed field require
   a producer rewrite before the adapter is trustworthy?
5. Does Batch B genuinely let `formal_medium` stop reading raw memo/display
   payloads?
6. Are `formal_thin_external_rich` and `formal_rich` protected by adequate
   compatibility boundaries and tests?
7. Which proposed deletion candidates still have active callers or protect
   source-boundary/citation behavior?
8. Is the plan to keep `check_report_file()` Markdown-only still coherent once
   in-memory contract gates expand?
9. Are broker note refresh, note persistence, and report-time consumption
   separated enough, or should their lifecycle be a separate subproject?
10. Does the design include all failure modes needed to prevent external
    low-credit material from affecting scoring, risk, target price,
    recommendation, or official sections?
11. Is the first implementation scope small enough for one task? If not,
    recommend the exact split and the first independently shippable batch.

## 4. Constraints

- Do not implement code.
- Do not modify the design file.
- Write only the expected review notes file.
- Do not access external websites, start browsers, crawl Xueqiu, or use CDP.
- Do not change scoring, target price, risk scoring, technical analysis,
  recommendation, collection, or `KnowledgeSynthesizer` prompt behavior.
- Treat current report profile behavior as a compatibility contract.
- Findings must cite concrete files/functions, not only general architecture
  preferences.

## 5. Required Response File

Create:

`docs/agent_workflow/2026-07-10-chapter4-architecture-slimming-claude-review-round1-notes.md`

Use exactly this structure:

```markdown
# Chapter 4 Architecture Slimming Round 1 Review

Status: Ready as-is | Ready with nice-to-have | Must-fix before task | Blocked

## Decision

- R2 recommended: Yes/No
- Reason:

## Findings

- [Blocker/Must-fix/Nice-to-have] Finding with file/function reference and reason.

## Requirement-Test Matrix Gaps

| Requirement | Existing coverage | Missing test or design change |
| --- | --- | --- |

## Deletion Audit

### Safe only after migration

- Helper and evidence.

### Keep for compatibility

- Helper and active caller.

### Not enough evidence

- Helper and missing audit.

## Recommended First Implementation Batch

- Exact files allowed to change.
- Exact behavior to add.
- Exact behavior that must remain unchanged.
- Focused tests and stop conditions.

## Open Questions

- Question, if any.
```

## 6. Stop Conditions

Stop and report `Blocked` if:

- the design cannot preserve current profile routing without changing scoring,
  target, risk, technical, recommendation, or canonical synthesis paths;
- the proposed first batch requires an LLM prompt change or new persistence;
- the report samples needed to evaluate a claimed behavior are absent and code
  alone cannot establish compatibility;
- the scope cannot be reduced to an independently testable first batch.
