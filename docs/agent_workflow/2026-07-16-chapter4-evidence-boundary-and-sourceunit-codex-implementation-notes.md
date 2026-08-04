# Chapter 4 Evidence Boundary and SourceUnit Repair - Implementation Notes

## Scope

- Kept the annual producer and memo material intact; no report, data, knowledge,
  prompt, scoring, target, risk, technical, or recommendation logic changed.
- Added a cited generic broker-assumption fallback for formal-medium 4.4. Risk
  rows remain ineligible.
- Made cached and fresh external viewpoint paths require matching stock identity,
  reject target-company claims backed only by explicitly foreign company titles,
  preserve peer/industry context under a Preview heading, and compact citations
  after card preservation.
- Reused the same claim-scope owner for the direct digest display path, closing
  its previous stock-identity and foreign-only bypass.
- Added `其他收益` as a financial anchor and split SourceUnit bundles before any
  cross-family continuation shortcut.

## Verification

- Focused material, external-display, narrative, and synthesis tests: `359 passed`.
- Renderer, quality, source-boundary, and preview CLI tests: `224 passed`.
- `bash tools/ci_grep_gates.sh`: passed.
- `git diff --check`: clean.

The full suite was sampled for 10 minutes and then interrupted after pre-existing
worktree/import/network failures. Two preview-fixture failures caused by the new
identity contract were repaired and their dedicated suite passes. No report was
generated.

## Runtime Budget

Measured from the recorded pre-Batch-A worktree state, the five runtime files
now increase by approximately `+179` net lines, down from the initial `+224`.
The reduction comes from one shared fresh/direct claim-scope filter, one shared
claim-ID resolver, a single-pass cached claim index, and removal of duplicate
digest row formatting. This still exceeds the design's original `+120` hard
stop; retaining all locked paragraph/card ownership and citation behavior makes
`+120` unrealistic without obscuring or dropping policy. The implementation is
functionally verified, but the original line-budget constraint requires an
explicit revision before merge.
