# Run Stock Report Entry Cleanup Batch D Codex Self-Review

## Round 1

Verdict: `needs_revision`

Accepted fixes:

- The unknown-stock message now uses the actual `--config` path instead of
  hard-coding the repository default. This preserves useful diagnostics for
  temporary or alternate configurations.
- Runtime hygiene now rejects all six bootstrap-only options, not only the
  three primary switches. This prevents a partial compatibility surface from
  surviving after the hard cut.

No blocker remained after those design edits.

## Round 2

Verdict: `ok`

Checks performed:

- Exact-date cache priority is explicit and independent of mtime.
- An invalid exact-date projected type falls through to older valid files.
- Zhihu dict and Xueqiu list schemas remain separate at their call sites.
- The fast-test network prohibition and formal Eastmoney fallback are intact.
- Offline smoke retains separate optional-import failure boundaries.
- The second credential clear is now covered against an import that restores
  an API key, matching the real `.env` reload hazard.
- Removing `--code`, `--xueqiu-code`, and `--gid` does not affect configured
  stock lookup, which reads those fields from `stocks.json`.
- The deletion estimate remains credible: bootstrap removes about 140 runtime
  lines before the smaller cache/smoke consolidations.

Implementation ready: `yes`.

The user explicitly waived the independent Claude review after these two
self-review rounds and authorized direct TDD implementation.
