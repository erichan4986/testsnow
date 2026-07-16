# Knowledge Persistence Slimming 6A-3 Source Coverage Notes

verdict: implemented_gate_blocked

## Scope

- Added read-only `stale_source_covered` classification for v2 note projections.
- A retired card enters this state only when every `source_unit_id` exists in the
  current validated pack. The audit records the current card IDs that cover it.
- No loader, producer, report, knowledge-card write, archive, move, or delete
  behavior changed.

## Verification

- 6A focused suite: 200 passed.
- Downstream material/renderer/quality/source-boundary suite: 289 passed.
- `tools/ci_grep_gates.sh`: passed.
- `git diff --check`: passed.

## Eleven-Stock Read-Only Recalculation

| classification | count |
| --- | ---: |
| stale_duplicate | 244 |
| stale_reindexed | 91 |
| stale_source_covered | 106 |
| stale_orphan | 127 |
| stale_invalid | 0 |

The new category accounts for cards whose old family or bundle identity changed,
but whose complete source-unit provenance is present in the current pack. It does
not assert semantic equivalence beyond exact SourceUnit continuity.

## Gate

- 6A-3 audit enhancement accepted: yes.
- Archive or move allowed: no. The 127 `stale_orphan` cards still require
  content review or a separately approved recovery decision.
- 6B pack-first allowed: no.
