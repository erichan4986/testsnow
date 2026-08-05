# Chapter 4 Memo Pass-Through H1 Codex Self-Review Round 1

## Verdict

`needs_revision`

## Findings

### R1. `memo_refs_resolved` has no replacement source

The design retains the profile key but the proposed formal diagnostics do not
carry a citation candidate count. Inferring it again in `SynthesisSkill` would
create a second status/row owner.

Fix: formal diagnostics must expose `formal_citation_candidate_count`; profile
sets `memo_refs_resolved` from that value only.

### R2. Broker citation and row order are underspecified

The current memo allocates local citation IDs in selected-item order, then
stores rows in three buckets. Snapshot iteration emits general sections first,
forecasts second, and risks last. Therefore citation numbers may be non-monotonic
in visible row order. A direct adapter that allocates while emitting grouped
rows would silently change citation identities.

Fix: allocate broker citation metadata for the bounded selected list first, in
source selection order; only then emit rows grouped as sections, forecasts,
risks. Add a mixed-order regression fixture.

### R3. Legacy family fallback contradicts the audit evidence

All configured packs are canonical, all have zero v1 adapter/recovery use, and
the pack adapter assigns `argument_family` before projection. Retaining the
memo-local `card_type` taxonomy merely moves obsolete compatibility into the
new owner.

Fix: require canonical `argument_family` at the read-model boundary. Invalid
noncanonical test fixtures must be migrated or rejected. Do not defer this map
to H2.

### R4. Zero-hit memo guards should not be relocated

The memo-local table-fragment and forbidden-source guards reject zero of the
651 canonical cards. Canonical producer validation and source boundaries own
that safety. Relocating the guards would fail the code-reduction goal and keep
a hidden post-producer admission path.

Fix: do not move these guards. Add contract tests that malformed/noncanonical
cards are rejected because they lack the canonical card contract, while
producer/source-boundary suites retain their existing safety tests.

### R5. Annual citation count must match accepted row inputs

The diagnostics proposal needs to state whether filtered suspicious-zero facts
and exact duplicate cards count as citation candidates. Otherwise
`memo_refs_resolved` can become true when the snapshot allocates no ref.

Fix: count unique citation keys from prepared facts, explanations, and cards
after all H1 preparation filters.

## Scope Review

The two runtime files remain sufficient. Test scope must include
`tests/utils/test_external_v4_snapshot.py` because it constructs memo-shaped
snapshot input. No producer or renderer runtime change is needed.

## Budget Review

Deleting the legacy family map and zero-hit guards improves the chance of
meeting the 110-line minimum reduction. The behavior change is limited to
unsupported synthetic/noncanonical inputs; all configured production packs are
covered by canonical contract tests.

## R2 Required

`yes`

Round 2 must verify the revised citation contract, canonical-card boundary, and
single diagnostics owner before implementation planning.
