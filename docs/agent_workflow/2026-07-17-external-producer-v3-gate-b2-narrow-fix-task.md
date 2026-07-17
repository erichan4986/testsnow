# External Producer v3 Gate B2 Narrow Fix Implementation Plan

**Goal:** Fix semantic source-unit completeness and safely project exact external evidence.

**Architecture:** Materialization owns sentence completeness; display owns visible attribution; lint recognizes
only the canonical quoted Preview contract. Selection and pack schemas remain unchanged.

## Task 1: Source units

- Add failing tests for decimal-preserving units, terminal numeric-dot rejection, and two structural-noise
  prefixes.
- Replace the sentence-boundary regex with a decimal-aware expression and add one structural-prefix guard.
- Run the argument-card suite.

## Task 2: Display and lint

- Add a failing display test using exact evidence containing `公告显示`, `确定`, and `锁定`.
- Add lint tests proving canonical heading + quote passes and either component alone still fails.
- Render each evidence unit as a quoted line with unit-level refs and add the canonical heading once.
- Teach lint to recognize only that exact framed quote contract.
- Run display and lint suites.

## Task 3: Verification

- Run external focused and Chapter 4 suites.
- Run `tools/ci_grep_gates.sh` and `git diff --check`.
- Re-read the six existing `/tmp` Gate B2 packs through the updated display path. Do not regenerate packs.
