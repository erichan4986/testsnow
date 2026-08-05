# H2 Codex Self-Review Round 3

## Verdict

`ok_after_revision`

## Findings And Fixes

### M1: Sparse broker rows change 4.3 ownership

`build_chapter4_view_model()` passes selected broker rows to the incremental
external selector as owner rows. Admitting one broker card can therefore hide
an overlapping target external observation. The initial design did not state
or test this cross-section consequence.

Fix:

- define exact-duplicate suppression as expected;
- require external rows with a new concrete anchor/event to remain visible;
- add a duplicate-plus-delta ownership fixture without changing the existing
  dedupe algorithm.

### M2: Report validation was deferred too late

The initial design deferred report reruns until H1/H2 were committed together.
Visible content and citation changes must instead be inspected before commit.

Fix:

- require three local-cache `--fast-test --no-pdf` report reruns after offline
  implementation gates and before commit;
- require fresh-report, Chapter 4 citation, and quality-gate checks;
- keep PDF visual comparison deferred because H2 does not change layout code.

## Final Assessment

No blocker or unresolved must-fix remains. Runtime ownership and scope are
unchanged by these design corrections. Independent repository review is still
required before implementation.
