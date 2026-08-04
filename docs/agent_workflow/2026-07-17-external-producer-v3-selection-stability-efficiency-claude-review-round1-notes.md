# Claude Review Round 1 — V3 Selection Stability & Efficiency Design

verdict: needs_revision

---

## blockers

none

The core design decisions are sound:
- Deterministic target bundling removes LLM from coverage ownership (4.1)
- Structurally pre-filtered peer pool reduces request volume without a cap (4.2)
- Shared preparation helper prevents divergent pools (5)
- Per-unit coverage union (vs group-text recompute) fixes the Gate B2 instability (4.1, 6)

No fundamental architecture flaw was found. Blocker-level issues are absent because the
design correctly identifies the root causes and the direction of the fixes.

---

## must_fix

- id: MF-01
  issue: **Corporate entity detection is too narrow for the continuation guardrail.**
  The design (4.1) requires that a continuation unit "must not introduce a different
  named corporate subject" — a critical guardrail against entity misbinding. The
  only entity extraction utility available in the codebase is `_mentioned_entities()`
  (cards.py:546) with pattern
  `[一-鿿A-Za-z0-9]{2,16}(?:股份|科技|电子|微电|智能|集团)`.
  This misses nearly all common company names that lack a corporate suffix:
  - 英伟达, 华为, 特斯拉, 三星 (no matching suffix)
  - 中际旭创 (4 chars, no suffix — would not match the fixed-suffix list)
  - AMD, Intel, Broadcom (English short-form names)
  - 台积电, 联发科 (industry shorthand, no matching suffix)

  A continuation unit starting with "其" followed by any of the above would wrongly
  pass the "no different corporate subject" check and be attached to the target
  bundle, altering coverage.

  evidence: `_mentioned_entities` regex at cards.py:546 only matches entities with
  specific corporate suffixes (股份/科技/电子/微电/智能/集团). The design requires
  this as a hard guardrail but the available detection logic is inadequate.

  suggested_fix: Broaden the entity pattern to include the most common bare-name
  company forms in Chinese financial text — e.g., add common 2-4 char company name
  suffixes like those ending in (达/讯/科/光/电/力/汽/药/银/保/矿/能源/医药/制造
  /汽车/电子/通信), or switch to a simple dictionary-based approach for stock names
  known in the target corpus. The detection does not need to be perfect — it should
  err on the side of false positives (seeing an entity where there may be none) to
  avoid false negatives. If in doubt, reject the continuation.

- id: MF-02
  issue: **`_build_v3_card` currently recomputes coverage from group text — the new
  design must wire per-unit family union for target bundles instead.**
  Currently `_build_v3_card` (cards.py:345) calls
  `enrich_external_evidence_group(members)` which recomputes `coverage_families` via
  `_coverage_families(" ".join(texts))`. The design (4.1, 6) says target coverage
  must be the ordered union of *precomputed* per-unit families, not recomputed from
  combined group text. These are equivalent for same-source units (both check
  substring presence in the concatenated text), BUT after the design's continuation
  attachment, if a continuation unit happens to introduce a word that matches a
  coverage family term absent from the leading unit, the recompute path counts it
  correctly anyway — so this may not cause a practical regression. The deeper issue
  is that the code DESIGN currently says "precomputed per-unit family union" and the
  implementation site MUST match that contract. A future change to coverage signal
  words (adding/removing terms) would create a subtle divergence between what's
  computed at materialization time and what the card stores.

  evidence: `_build_v3_card` at cards.py:346 calls `enrich_external_evidence_group`
  which at cards.py:88-91 recomputes families from `" ".join(texts)` rather than
  taking the union of `unit.get("coverage_families")`.

  suggested_fix: Either (a) make `_build_v3_card` take the union of per-unit
  `coverage_families` for target bundles, or (b) ensure the continuation bundling
  helper explicitly computes `target_bundle["coverage_families"]` as the union and
  passes it down, so `_build_v3_card` never recomputes. Option (b) is cleaner and
  matches the shared-preparation-helper design.

- id: MF-03
  issue: **Test matrix (Section 9) is comprehensive in intent but missing explicit
  negative-case tests.**

  evidence: The required test table lists 14 scenarios. The following negative cases
  are absent from the spec:

  1. **Continuation rejection — different corporate subject introduced.** The happy
     path (continuation attaches) IS tested ("strict continuation is deterministic"),
     but the unhappy path (continuation attaches a unit mentioning a different
     company, e.g., "其竞争对手英伟达已发布新品") is not listed. This is the most
     critical guardrail to test.

  2. **Pre-filtered peer statistics recorded in diagnostics.** The test "low-signal
     peer is prefiltered" verifies the peer doesn't reach the selector, but doesn't
     verify that `optional_peer_low_signal_count` increments in diagnostics. Ditto
     for dedupe counts.

  3. **Selector-retry request count is recorded.** The test "retry accounting is
     visible" is listed, but the specification doesn't say which diagnostic field
     (`selector_request_count`) should contain the value. This should be explicit.

  4. **Card persistence follows source order for target bundles.** The test "group
     persistence follows source order" targets LLM groups (from the old mixed-pool
     code). After the redesign, target bundles are built deterministically — need
     a test that a multi-unit deterministic bundle persists as `[5, 6, 7]` not
     `[7, 5, 6]`.

  suggested_fix: Add the four missing negative cases to the Required Tests table.

---

## nice_to_have

- id: NH-01
  issue: **"At most 2 immediately adjacent units" is an arbitrary limit.**
  The continuation rule (4.1) limits to 2 continuation units. Why 2 and not 1 or 3?
  In Chinese financial writing, a target-company paragraph can have 3-4 pronoun
  continuations in a row. With the current limit, the 3rd+ continuation would become
  a separate card (LLM would receive it as optional peer). This may lose context
  that should be part of a single coherent argument block.

  suggested_fix: Start with 2, but make the limit configurable or data-driven. Add
  a diagnostic counter for "continuation_truncated" so the empirical distribution
  of continuation lengths can be observed in Gate B2. If most source paragraphs
  produce 3+ continuations, consider raising the limit to 3.

- id: NH-02
  issue: **"双方" (both parties) in continuation subjects implies two entities.**
  The continuation subject list (4.1) includes "双方". If a unit begins with
  "双方达成合作协议", it references two entities — the target and a partner. The
  entity scope of the resulting bundle should be `target_with_peer_context`, not
  `target`, because the combined evidence discusses the target in a peer/partner
  context. The design (5.1) says "A continuation such as 公司/双方/其 is target-bound
  only when grouped with an adjacent preceding unit that explicitly contains the
  target name" — this means the bundle IS target-bound, but the presence of "双方"
  in the continuation should trigger peer_context for the entity scope.

  suggested_fix: Ensure the enrichment logic treats "双方" continuations as
  `target_with_peer_context` (the existing `_PEER_TERMS` includes "对比" but not
  "双方"). Either add "双方" to `_PEER_TERMS` or add a specific check in the
  continuation attachment logic. Add a test for this case.

- id: NH-03
  issue: **Diagnostics (Section 7) could include peer anchor-type breakdown.**
  The concrete anchor requirement (4.2) accepts "a number, percentage, year,
  product/model token, comparison metric, or a concrete event/action". If the
  filter is too broad in practice ("number" alone is very broad), a flood of
  low-value peer units could still pass. Tracking which anchor types admitted each
  eligible peer would help narrow the rules empirically.

  suggested_fix: Add an optional `optional_peer_by_anchor_type` diagnostic dict
  (e.g., `{"number": 5, "year": 2, "event": 3}`). This is diagnostic-only and does
  not affect the data path.

- id: NH-04
  issue: **Profile routing at synthesis_skills.py:997-1001 uses entity_scope
  prefix-match `startswith("target")` — fine for current two variants but fragile.**
  The profile code computes target families by filtering `entity_scope.startswith("target")`.
  Currently only `"target"` and `"target_with_peer_context"` both start with "target".
  If a future scope name like `"target_negative"` or `"target_only"` is added, the
  prefix match would silently include it. This is not a problem for the current
  design, but a minor fragility.

  suggested_fix: Consider `entity_scope in {"target", "target_with_peer_context"}`
  instead of `startswith("target")` to be explicit about which scopes count.

---

## requirement_test_gaps

- requirement: **Continuation rule rejects unit with different named corporate subject.**
  missing_test: A fixture where a unit starts with "其" but the text introduces
  "竞争对手英伟达" or another named company. The continuation must be rejected and
  the mandatory unit must remain a standalone single-unit card.

- requirement: **Pre-filtered peer statistics are recorded in diagnostics.**
  missing_test: After running `build_curated_external_argument_pack` with source
  material containing both eligible and non-eligible peer units, verify
  `pack["diagnostics"]["optional_peer_low_signal_count"]` and
  `pack["diagnostics"]["optional_peer_duplicate_count"]` have the expected values.

- requirement: **Selector retry request count is recorded.**
  missing_test: Inject an `FullBodyExtractorError` on first selector call, verify
  the pack eventually succeeds AND
  `pack["diagnostics"]["selector_request_count"]` >= 2.

- requirement: **Target bundles persist in source order (not pool index order).**
  missing_test: A deterministic bundle with two units having ordinals 7 and 8.
  Verify the stored card's `evidence_units` list has
  `[{"source_ordinal": 7, ...}, {"source_ordinal": 8, ...}]` in that order, never
  reversed.

---

## scope_and_budget

  status: ok

  evidence:
  - Allowed scope (Section 8) correctly limits runtime changes to claims.py and
    cards.py, with tests limited to their focused suites plus existing reader/
    display/profile tests where version assertions must update.
  - Forbidden list (Section 8) explicitly excludes stock-specific rules, a second
    selector, semantic repair/embedding/embedding, total card/source cap,
    report-time source reads, production config/cache/report changes, and
    scoring/target price/risk/recommendation/KnowledgeSynthesizer changes. This
    matches the Gate B2 scope boundary.
  - Design delta (Section 12) correctly rejects: two-line hotfix (leaves 27-call
    flood), larger batches (increase incomplete responses), fixed card cap
    (discards distinct evidence), stock-specific rules (don't generalize).

  Budget analysis:
  - New code estimate: target bundling ~30 lines, continuation check ~25 lines,
    peer pre-filter ~40 lines, shared helper ~30 lines, diagnostics ~15 lines,
    selector version bump ~2 lines, refactored build_curated_external_argument_pack
    ~10 lines, refactored build_external_argument_pack ~15 lines = ~167 lines
  - Delete: mixed-pool code in claims.py lines 181-192 (~12 lines) and cards.py
    lines 215-239 (~25 lines) plus _selected_unit_groups sorting bug (~2 lines) and
    the old group-text recompute path (~5 lines) = ~44 lines
  - Net delta: +123 — within the +140 budget

  The budget is credible because the new design replaces (rather than layers on top
  of) the existing mixed-pool path. The shared helper (Section 5) eliminates the
  duplicate materialization in build_external_argument_pack, offsetting the new
  code.

---

## implementation_ready: no

Conditions that must be resolved before implementation can start:

1. **MF-01**: The entity detection approach must be decided (broadened regex or
   dictionary-based). Without this, the continuation guardrail is a design
   assertion without a reliable implementation mechanism.

2. **MF-02**: The coverage-family contract for target bundles must be explicitly
   wired in the implementation plan: per-unit union at what point in the pipeline,
   and how `_build_v3_card` receives it.

3. **MF-03**: The test matrix must be updated with the four missing negative-case
   tests before writing them (TDD order: write RED test, then implement).

4. The shared preparation helper's API between claims.py and cards.py must be
   explicitly designed — what struct does it return? TargetBundleP is a
   `dict[str, Any]` with `bundle_key`, `units`, `coverage_families`? A namedtuple?
   A lightweight dataclass? The design says "one shared preparation helper" but
   does not specify the interface contract. This should be decided before coding
   to avoid divergent implementations on each side.

Resolve must_fix items (especially MF-01 and MF-02), fill the test gaps, and
specify the helper interface, then proceed to implementation. R2 review is only
needed if the resolution changes target/peer ownership, evidence identity, the
no-cap contract, or the sole-selector boundary.
