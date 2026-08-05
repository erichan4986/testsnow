# Chapter 4 Read-Model Consolidation Batch G1 Review Record

> **Date**: 2026-08-05
> **Review type**: user-approved waiver
> **Verdict**: ok
> **Implementation ready**: yes

## Waiver

The user explicitly instructed Codex to `推进实现` after receiving the locked
design and its two-pass self-review result. Under `AGENTS.md` section 9, this
record replaces an external Claude Round 1 review. It does not waive design,
TDD, scope controls, stop conditions, or final Codex verification.

## Codex Self-Review Findings

- **Closed**: formal-thin broker rendering cannot yet move to `MaterialRow`
  because the memo preserves separate forecast metric/period structure.
- **Closed**: annual portrait selection belongs only to
  `select_annual_display_rows()`; the renderer must not score a second
  portrait.
- **Closed**: suspicious `0.00亿元` filtering is admission logic, but remains
  narrowly limited to `formal_fact` rows with financial metric titles.
- **Closed**: citation offset and full-snapshot merge formulas remain
  unchanged.
- **Closed**: unused formatter parameters and zero-call helpers can be removed
  without changing visible output.

## Scope And Stop Conditions

No blocker or unresolved must-fix remains. Implementation is limited to the
two runtime files and three test files named in the design, plus workflow
notes. Stop if broker output/citation identity changes, if another owner path
is introduced, if broader modules must change, or if the green implementation
reduces fewer than 65 runtime lines.
