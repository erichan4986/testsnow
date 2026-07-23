# Formal-Medium Chapter 4.4 Retirement: Codex Self-Review Round 2

日期：2026-07-23
Verdict：`needs_revision` -> fixed in design

## Findings

### F1. Mixed tests could be deleted too aggressively

Several snapshot tests contain one obsolete 4.4 assertion but primarily protect narrative filtering, owner-delta source preservation or diagnostics. Deleting the whole tests would remove valid 4.3 coverage.

**Fix:** Added an exact migration ledger. Four price-path-only tests are deleted; mixed tests retain their primary assertions and replace/remove only the 4.4 clauses.

### F2. No end-to-end formal-medium renderer absence test existed

The renderer test file covered formal-rich and formal-thin profiles but did not construct a formal-medium view model and assert its complete heading set.

**Fix:** Required a new formal-medium three-section fixture that rejects the heading, labels and generic condition sentences.

### F3. Historical report-quality compatibility was underspecified

Removing current rendering does not mean the quality checker should stop understanding already-generated formal-medium reports containing 4.4.

**Fix:** Locked `report_quality.py`, source-boundary logic and their historical 4.4 fixtures as unchanged.

### F4. Citation invariant needed an exact formula

“Citations remain stable” was too vague.

**Fix:** Defined `view_model.citations` as the exact union of refs visible in 4.1--4.3 rows and external narrative parts. Existing 4.4 rows are a subset of those rows, so removal must not change the set.

### F5. Runtime deletion estimate was low

The removable paths cover roughly 95 runtime lines across snapshot construction, three selectors, the renderer call site and the fixed template method.

**Fix:** Updated expected runtime net change to `-85` through `-105` lines; net-positive runtime remains a stop condition.

## Result

All Round 2 findings are closed in the design. No runtime or test files were modified.
