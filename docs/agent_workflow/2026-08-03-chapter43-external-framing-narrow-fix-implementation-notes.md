# Chapter 4.3 External Framing Narrow Fix Notes

## Result

`PASS_WITH_ENVIRONMENT_WARNING`

The existing sentence-level owner-delta selector was retained. The renderer now
frames target material as external incremental verification points, frames peer
material as comparison context, and no longer inserts `此外` between every
continuation unit. Source quotes, rows, citations and offsets are unchanged.

The prose checker now ignores `已确认` only inside the narrow negated disclaimer
`不代表...已确认事实`; a real assertion such as `公司已确认获得新增订单` remains a
warning.

## TDD

- RED: 9 focused failures covering old topic leads, generated `此外`, separate
  paragraph framing and the negated-disclaimer false positive.
- GREEN: renderer + prose focused suite, `89 passed`.
- Downstream snapshot/renderer/quality/source/prose suite: `289 passed`.
- Full suite: `2820 passed, 10 skipped`.
- CI grep gates: all passed.
- `git diff --check`: clean.

## Report Projection

Offline Chapter 4 projections were generated at:

- `/tmp/chapter43-verify/中际旭创_20260803.md`
- `/tmp/chapter43-verify/复旦微电_20260803.md`

Both source-boundary checks pass. Neither report triggers an external-viewpoint
quality error or the previous false `strong_assertion_wording` warning. Advisory
theme-overlap warnings remain because current external facts add later periods,
orders, stages and metrics; deleting them would violate the locked no-material-
loss policy.

Formal full-report reruns also completed before the code change, but sandbox DNS
failure prevented market/technical data collection. Their missing daily/weekly/
volume failures are environment limitations and were not used to validate this
display-only change.

## Scope

No producer, canonical pack, prompt, citation, scoring, target, risk, technical
or recommendation changes. Runtime delta is net zero across the two modified
runtime files.
