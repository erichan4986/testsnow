# Knowledge Persistence Slimming 6A-1 Acceptance

verdict: pass_with_warning

## Evidence

- Relevant tests: 195 passed.
- CI grep gates, `py_compile`, and `git diff --check`: pass.
- Local-cache dual-write, A share: 中际旭创 65 pack cards / 65 legacy notes.
- Local-cache dual-write, HK share: 黑芝麻智能 56 pack cards / 56 legacy notes.
- Both manifest-backed pack sets validate; repeated writes preserve pack and manifest SHA256.
- Writes were confined to `/private/tmp/testsnow-6a1-acceptance-ELAkZ9`; no report was generated.
- Linked runtime set is 2671 lines versus the previously recorded 2905-line checkpoint (-234).

## Narrow Fixes During Acceptance

- Prevented the preparation CLI from importing the same-named wrapper module when
  `scripts/utils` was already present later in `PYTHONPATH`.
- Preserved original card indexes for preview maintenance and `existing_only` writes by
  making `existing_only` a writer option instead of filtering and reindexing cards.
- Updated stale v1 preview fixtures to validate the current v2 producer contract.

## Warning

The pre-6A per-file SHA snapshot required by the design was not persisted before 6A-1.
The line checkpoint and fresh functional evidence are sufficient for 6A-1 acceptance,
but 6A-2 records a new per-file SHA/line baseline before implementation.

## Gate

6A-2 allowed: yes. 6B allowed: no.
