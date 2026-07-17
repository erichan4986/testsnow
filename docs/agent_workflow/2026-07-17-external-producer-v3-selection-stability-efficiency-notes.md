# External Producer v3 Selection Stability and Efficiency Notes

## Status

Implementation is within the locked runtime budget. No live LLM call, network access, report generation,
config, cache, data, or knowledge mutation was performed.

## Modified Files

- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `tests/utils/test_curated_external_argument_cards.py`
- `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- `tests/utils/test_curated_external_display.py`
- `docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-notes.md`

## RED / GREEN

1. **Source order and coverage ownership**
   - RED: target-first pool persisted `[7, 5, 6]`; target-plus-peer enrichment included peer families.
   - GREEN: groups persist in source order; coverage is the fixed-priority union of precomputed unit families,
     and target-bound units exclusively own a target group’s coverage.
2. **Target bundles and continuations**
   - RED: no deterministic preparation helper existed.
   - GREEN: target units bypass selection; only closed `公司/本公司/该公司/该产品/上述产品/相关产品`
     continuations attach. `其`/`双方` and relation-switch text reject. The fixed helper return fields
     `bundle_key` and `coverage_families` are tested.
3. **Optional peer admission**
   - RED: generic industry-risk text reached the selector; repost and containment duplicates survived.
   - GREEN: optional units require peer/industry context and a number or concrete action. Exact global and
     same-source containment duplicates are removed without a final cap.
4. **Selector bypass/versioning**
   - RED: target-only material called the selector and v1 packs remained readable.
   - GREEN: selector batches contain eligible peer units only; retries count requests and v1 packs are stale.
5. **Compression regression**
   - RED: a forged prepared target source raised `NameError` through the removed `partition` local.
   - GREEN: the builder returns `selector_incomplete` with `unknown_source_id`. The redundant standalone
     partition API and three single-use wrappers were removed; prepare remains the sole admission owner.

## Requirement / Test Matrix

| Requirement | Verification |
| --- | --- |
| Source-ordered evidence and target-only family ownership | argument-card source-order and handcrafted mixed-group fixtures |
| Closed continuation, bundle split, and three-unit truncation | preparation fixtures for explicit targets, `其`, `双方`, and relation switches |
| Fixed helper return shape | target bundle key and ordered family-union assertion |
| Peer admission, dedupe, and no final cap | low-signal, named-action, exact/containment, and 25-unit fixtures |
| Target selector bypass and peer-only retries | full-body selector wrapper fixtures |
| Fail-closed prepared source validation | forged `source_id` pack fixture |
| Reader/display/profile and Chapter 4 isolation | 397-test related suite |

## Shared Preparation Result

```python
{
    "target_bundles": [{
        "bundle_key": "target-bundle:<source_id>:<ordinal>",
        "units": [...],
        "coverage_families": [...],
    }],
    "optional_peer_units": [...],
    "diagnostics": {...},
}
```

## Verification

- Mandated focused suite: `127 passed`
- Related external, source-intake, renderer, quality, and boundary suite: `397 passed`
- `bash tools/ci_grep_gates.sh`: PASS
- `git diff --check`: clean

## Runtime Budget

Starting-worktree baseline:

```text
curated_external_argument_cards.py: 570 lines
curated_external_full_body_viewpoint_claims.py: 203 lines
total: 773 lines
```

Before compression, the two files were 740 + 210 = 950 lines (`+177`). After removing the redundant
partition layer and single-use wrappers while retaining the locked bundle contract:

```text
curated_external_argument_cards.py: 701 lines
curated_external_full_body_viewpoint_claims.py: 210 lines
total: 911 lines
runtime delta: +138 lines
```

This is within the task’s `<= +140` stop condition.

## Blocker / Warning / Deviation

- **Blocker:** none.
- **Warning:** the source-unit splitter still treats a decimal point in `1.6T` as a sentence boundary. This
  is deliberately deferred because splitter behavior is outside this task.
- **Deviation:** none. The fixed shared-helper return fields were retained even though the current builder
  can derive card coverage from the units.

## Gate B2 Rerun Allowed

`yes`
