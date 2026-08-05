# Chapter 4 Memo Pass-Through H1 Codex Acceptance

## Verdict

`PASS`

No blocker or must-fix was found in the independent post-implementation review.

## Contract Review

- `annual_report_memo.v1` and `broker_research_memo.v1` have no runtime owner or
  runtime reads.
- Annual current-card precedence, canonical family admission, cleanup,
  full-body exact dedupe, zero-metric guards, status, and citation identities
  remain represented by the snapshot projection.
- Broker guardrails, exact-key dedupe, status, attribution, source-id hashing,
  source-order citation allocation, and H1's frozen first-six behavior remain
  represented by the snapshot projection.
- Profile and coverage consume one formal diagnostics object rather than
  rebuilding annual/broker eligibility.
- Broker notes are loaded once and reused by freshness and optional display
  synthesis.
- Annual, broker, and external citations preserve their global order and
  full-snapshot offset contract.

## Evidence

- Runtime delta against `e504cb9`: snapshot `+247`, synthesis `-358`, combined
  `-111` lines.
- Focused H1 suite: `267 passed`.
- Full suite: `2857 passed, 10 skipped`.
- CI grep gates: pass.
- `git diff --check`: clean.
- Runtime hygiene grep: no old memo schema/builder/context reads.
- Offline baseline comparison for 中际旭创, 复旦微电, 黑芝麻智能 preserved
  annual/broker status, row bodies/source identities, and citation counts.

## Residual Risk

H1 intentionally preserves three content policies for H2: the annual
300-character cut, broker's secondary six-row cap, and rejection of a single
guarded broker card. They are not H1 regressions.
