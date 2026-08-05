# G2 User-Approved Review Waiver

- Date: 2026-08-05
- Baseline: `77dd423`
- User instruction: `自审并修复，然后直接实现`
- Interpretation: the user explicitly approved skipping the external Claude
  Round 1 review presented immediately before this instruction.

This waiver replaces only the external read-only reviewer. It does not waive
the locked design, two Codex self-review passes, TDD, scope restrictions,
runtime stop conditions, or final verification.

Codex self-review corrections made before implementation:

1. Generic snapshot attribution values (`研报`, `券商`, `机构`) must not be
   duplicated into output such as `研报研报预计`.
2. An accepted memo with zero valid material rows fails closed to the existing
   unavailable fallback; no sentinel row or snapshot-level compatibility state
   will be added.

Review verdict: `ok`

- blockers: none
- must_fix: none after the two corrections above
- implementation_ready: yes
