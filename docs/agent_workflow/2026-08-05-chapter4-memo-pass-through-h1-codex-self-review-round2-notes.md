# Chapter 4 Memo Pass-Through H1 Codex Self-Review Round 2

## Verdict

`needs_minor_revision`

## Round 1 Closure

- R1 closed: formal diagnostics now own citation candidate count.
- R2 closed: broker citations are allocated before grouped row emission.
- R3 closed: legacy `card_type` family mapping is deleted in H1.
- R4 closed: zero-hit forbidden/table admission guards are not relocated.
- R5 closed in principle; Round 2 narrows which broker items contribute refs.

## Findings

### S1. Preloaded broker items must not be overwritten

The current memo builder uses `ctx.get("broker_research_digest_items")` when the
key is present, including an empty list, and loads notes only when the value is
`None`. The proposed unconditional post-refresh load would change injected
fixture and caller behavior.

Fix: after refresh, load once only when the ctx value is `None`; otherwise copy
and retain the preloaded list. Loader call-count tests need both branches.

### S2. Usable and projected broker items are different sets

Current diagnostics/status use all deduplicated selected items, while row and
citation construction uses only `selected[:6]`. A single `items` field is
ambiguous and risks capping `broker_usable_card_count`, which can change profile
routing.

Fix: `_BrokerMaterialProjection` must carry `usable_items` and
`projected_items`. Status, families, institutions, and usable count derive from
the former; rows and citation candidates derive from the latter. When status is
`absent`, `projected_items` is empty even if one usable item exists.

### S3. Formal citation count needs exact status gating

The design says count bounded broker items, but current absent broker memos have
no citations. Likewise annual rows are not adapted when annual status is
`blocked` or `absent`.

Fix: count annual unique row keys only for `ready` or
`deterministic_fallback`; count broker projected items only for `ready` or
`single_institution`; never count synthetic disclosure-boundary rows.

### S4. Broker source identity needs an explicit regression

Moving `_source_id()` also moves the SHA256 seed contract. If the seed changes,
`source_ref_ids` change despite correct citation metadata.

Fix: lock the existing seed order
`viewpoint_cluster -> title -> content` and the 16-character SHA256 suffix in a
direct projection test.

## Scope And Budget

No additional runtime file is required. The fixes clarify state carried by the
private broker projection and should add only a few lines. The minimum net
reduction remains credible.

## Implementation Readiness

`yes_after_inline_design_delta`

After S1-S4 are incorporated, no blocker or unresolved must-fix remains. The
repository Level 3 review gate still applies before implementation.
