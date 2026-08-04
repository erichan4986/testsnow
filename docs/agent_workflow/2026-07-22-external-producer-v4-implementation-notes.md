# External Producer v4 Implementation Notes

## Status

Code batches A and B, the corrected canonical-data cutover, and the post-remap report integration check are
complete. External Producer v4 is accepted with unrelated report-environment warnings recorded below.

## Implemented

- Added immutable paragraph-preserving source documents, exact evidence units, deterministic target/peer/industry
  scope provenance, strict v4 packs and an ID-only narrative plan.
- Replaced the v3 display/projection/narrative runtime with a v4-only display adapter while preserving the report
  display envelope consumed by `MaterialSnapshot` and Chapter 4.
- Removed the old v3 card, display projection and free-form narrative modules and their obsolete tests.
- Kept the LLM boundary to peer/industry unit selection only. It cannot emit prose, scope, family, prices, scores,
  risk or recommendations.
- Added fail-closed checks for source boundary status, block kind, immutable unit fields, provenance, card entity,
  contiguous source order, exact family union, citation identity and unused citations.

## Verification

- Focused v4/snapshot/renderer/synthesis tests: `252 passed`.
- `bash tools/ci_grep_gates.sh`: passed.
- `git diff --check`: passed.
- Offline structural exercise using the local v3.1 source caches and an all-keep test selector:
  - Zhongji: 20 cards, reader/display `ok`; one collapsed comparative source rejected as
    `scope_input_degraded`.
  - Fudan: 10 cards, reader/display `ok`.
  - Heizhima: 21 cards, reader/display `ok`.

## Remaining Gate

`tests/reporter/test_stock_reporter_source_intake_config.py` has one expected failure: all three configured
canonical pack paths still contain v3 JSON, so `read_external_argument_pack_v4()` correctly rejects them. Do not
copy or hand-edit old cards into v4; their embedded source material and offsets are absent.

Batch C requires a local selector pilot against:

- `cache/curated_external/v3_1/zhongji-sources.jsonl`
- `cache/curated_external/v3_1/fudan-sources.jsonl`
- `cache/curated_external/v3_1/heizhima-sources.jsonl`

and the matching baseline files. Validate the three `/tmp` v4 pilots before atomically replacing the canonical
pack JSON files. The Zhongji collapsed comparative document must remain rejected rather than manually repaired.

## Acceptance Repair

- The pack builder now returns `source_input_degraded` when any input document is rejected; it no longer publishes
  a partial `ready` pack after silently dropping that source.
- The producer stops before the LLM selector when source-document diagnostics are degraded.
- The v4 reader rejects pre-fix `ready` packs that still record rejected source documents, preventing stale pilots
  from bypassing the corrected builder.
- Focused v4/snapshot/renderer/synthesis verification: `255 passed`; CI grep gates and `git diff --check` passed.
- The production-config gate remains intentionally red because all three canonical JSON files are still v3. Existing
  `/tmp` v4 pilot/migrated files also fail the corrected reader and must not be copied into canonical storage.
- Restored the collapsed Zhongji comparison source from the matching local recovery cache (same URL and metadata,
  nine preserved paragraphs). Source-document preflight is now 5/5, 4/4 and 5/5 for Zhongji, Fudan and Heizhima.
- Offline skip-peer structural packs pass reader/display for all three stocks. They live under
  `/tmp/external-producer-v4-preflight/` and are diagnostic only, never canonical candidates.

## Post-Batch-C Scope Repair

- Independent review rejected the original Batch C `PASS`: the final packs were structurally valid under the
  then-current resolver, but target-company product and operating facts had leaked into `peer_or_industry`.
  The external runner also exceeded the task's built-in retry contract, so its retry count was not an accepted
  part of the cutover evidence.
- Root cause was deterministic entity detection, not the LLM selector. Generic business phrases, product/model
  names and dated corporate-action phrases could be parsed as peer actors.
- Scope resolution now rejects those non-entity actor forms, preserves target-document ownership, keeps explicit
  partner relations as `target_with_peer_context`, and records `external_scope_resolver.v2`.
- Added regression fixtures for target business phrases, product/model continuations, dated actions, market
  context, partner relations and modal capability phrases.
- Rebuilt the three canonical packs without another LLM request. Existing peer `keep` IDs were preserved; target
  cards were deterministically regenerated from the corrected provenance. No evidence text, hashes, offsets or
  family labels were edited.
- Corrected card counts: Zhongji 31 (21 target, 1 target-with-peer, 9 peer/industry), Fudan 8 (all target), and
  Heizhima 17 (13 target, 1 target-with-peer, 3 peer/industry). No previously-target unit moved to peer scope.
- Verification: `287 passed`; strict reader/display/lint passed for all three packs; CI grep gates and
  `git diff --check` passed.
- Fresh reports were generated without rerunning the selector. Chapter 4.3 scope review passed for all three:
  Zhongji contains only Huagong/industry facts in the peer section, Fudan has no peer section, and Heizhima has
  only three industry-context facts there.
- Zhongji passed quality/source/prose gates. Fudan retained the known `financial_fact_unit_conflict` heuristic;
  Heizhima retained the known missing HK market-data sections. Both passed source-boundary and prose gates, and
  neither finding comes from External Producer v4.
- The acceptance report's claim that `resolver_version` was missing inspected only the pack root. The contract
  stores this field in each unit's `scope_provenance`; all 83 canonical evidence units record
  `external_scope_resolver.v2`, with zero missing values.
- The default offline suite exposed one stale caller outside the focused set:
  `social_viewpoint_source_packets.py` still imported the removed `SOURCE_PACKET_SCHEMA_VERSION`. It now emits
  `curated_external_source_input.v2` through the v4 `SOURCE_INPUT_SCHEMA_VERSION`; no legacy alias or compatibility
  branch was restored.
- Final verification: `2582 passed, 16 skipped`; CI grep gates passed; runtime search contains no v3/v3.1 pack,
  card, selection or source-input schema reference; `git diff --check` passed.
