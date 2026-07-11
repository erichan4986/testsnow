# Annual Producer v2 — Claude Round 2 Design Review Notes

**Date:** 2026-07-11
**Design doc:** `docs/agent_workflow/2026-07-11-annual-producer-v2-design.md`
**Target commit:** `4db014e docs: revise annual producer v2 design`
**Reviewer:** Claude Code
**Scope:** Read-only verification of the revised design against existing producer, pack, synthesis, snapshot, renderer, and tests.

---

## Verdict

`ok`

The revised design closes all Round 1 findings. Canonical families now directly drive the display layer, `argument_complete` is wired through `MaterialRow` to the 4.4 boundary, SourceUnit has a concrete positional record, caps are explicitly removed from the canonical path, family resolution is a single deterministic call, and atomic facts are handled by the unified admission contract rather than a second selector. The runtime-deletion budget is now credible because Batch A names the same-batch deletions. No blockers remain.

No code changes were made for this review.

---

## Round 1 Findings Status

| Finding | Status | Evidence |
|---|---|---|
| **F-01** Hidden second taxonomy | **closed** | Design §5 now states the five canonical families are the annual memo `display_group` and `MaterialRow.render_role` values, and explicitly lists `product_business`, `operation_update`, `management_view`, `competitiveness_rd`, `financial_explanation` for deletion. Batch A deletes `card_group` in `synthesis_skills.py:523-531` and `classify_annual_render_role` in `deep_analysis_material_snapshot.py:326-339`. Renderer labels remain Chinese-only (`业务结构`, `经营变化`, `管理层判断与行业展望`, `技术与产品进展`, `财务质量与变化原因`) and are not a machine-readable taxonomy. |
| **F-02** `argument_complete` 4.4 boundary | **closed** | Design §6 copies `argument_complete` card → note → pack → memo → `MaterialRow`, defaults to `false`, and states `build_chapter4_view_model` admits only annual rows with `argument_complete=true` to 4.4. Atomic and adapted-v1 cards are forced to `false` (§4) and therefore remain 4.1-only. Batch A item 7 schedules the `MaterialRow` field and the 4.4 filter. |
| **F-03** Source-unit tracking | **closed** | Design §6 defines `source_units` as a first-class record (`unit_id`, `block_id`, `ordinal`, `start_pos`, `end_pos`, `text`) with monotonic non-overlapping positions. `unit_id` is deterministic (`<block_id>:u<ordinal>`). `validate_card_v2` checks position monotonicity and unit-id consistency. The v1 adapter creates a single legacy proxy unit (`start_pos=0`, `end_pos=len(excerpt)`) marked legacy-adapted, so proxy units are unmistakably non-current. |
| **F-04** No cap requirement | **closed** | Design §11 explicitly removes producer `max_cards_per_type`/`max_total_cards` (`periodic_report_narrative_evidence_cards.py:492-493`), material-pack `max_cards`/`per_type_limit` and second fill-round (`annual_report_material_pack.py:139-140`, `:564-570`), annual memo `valid_cards[:8]` (`synthesis_skills.py:533`), and annual renderer `row_limit`/`rows[:row_limit]` (`deep_analysis_renderer.py:924-925`). The optional `periodic_narrative_cards_max_display_items` budget is retained only for the LLM display-synthesis path and must slice after the uncapped pack is built. |
| **F-05** Family-assignment precedence | **closed** | Design §9 replaces the old per-type candidate loop (`_USAGE_TO_CARD_TYPES` mapping one usage to multiple card types at `periodic_report_narrative_evidence_cards.py:33-65`, `:620-629`) with a single `resolve_argument_family(bundle, usage_hint)` call that returns exactly one primary family plus `secondary_signals`. Precedence rules are deterministic and the test matrix covers the ambiguous cases. |
| **F-06** Sparse-report atomic-fact retention | **closed** | Design §8 makes atomic-fact admission part of the one normal selector and explicitly rejects a separate sparse fallback selector (§20). After hard noise filtering, any self-contained unit with a concrete anchor must be admitted; otherwise `admission_invariant_violation` is recorded. This satisfies the sparse-report requirement without creating a second selection path. |

---

## Blocker

0

## Must-fix

0

## Nice-to-have

1. **LLM display-budget slicing implementation detail.** Design §11 correctly states that `periodic_narrative_cards_max_display_items` must slice after the uncapped pack is built. The current code path in `synthesis_skills.py:280-285` passes `max_cards` and `per_type_limit=3` directly into `load_periodic_narrative_card_synthesis_items`, which forwards them to `build_annual_report_material_pack`. During implementation, ensure the canonical pack is built uncapped first and the display budget slices that result, rather than re-capping the pack. Add a test that asserts `annual_report_material_pack.selected_narrative_cards` length is independent of `periodic_narrative_cards_max_display_items`.

2. **Note-writer frontmatter serialization for `source_units`.** The design defines `source_units` as a list of records, but the existing note writer (`periodic_report_narrative_card_note_writer.py:_render_frontmatter`) only supports scalars and flat lists. This is an expected implementation change, but the design could mention that `source_units` may be serialized as a YAML block or stored in the note body rather than frontmatter to avoid a frontmatter schema change for `annual_argument_schema.py` consumers.

3. **Renderer formal-thin shared path.** The `row_limit` removal in `_annual_report_business_profile_section` (`deep_analysis_renderer.py:924-925`) affects both formal-medium and formal-thin (`_annual_report_memo_section` → `_annual_report_business_profile_section`). The budget table mentions both; no change required, but tests should cover formal-thin as well as formal-medium.

---

## Requirement–test gaps

The requirement-test matrix in §16 is comprehensive. The following are not design gaps but implementation-level checks to add so the design contracts do not regress:

| Requirement | Recommended test |
|---|---|
| Direct family propagation | Assert `display_group` and `MaterialRow.render_role` equal canonical family string, not `product_business`/etc. |
| 4.4 completeness boundary | Create a MaterialRow with `source_layer=annual`, `render_role=business_structure`, `argument_complete=false`; assert it is absent from `Chapter4ViewModel.section("4.4").rows` and present in `section("4.1").rows`. |
| LLM context budget isolation | Build pack with >12 cards; set `periodic_narrative_cards_max_display_items=3`; assert pack still contains >12 cards and display synthesis receives 3. |
| Source-unit substring proof | Construct a block, split into SourceUnits, and assert every unit text equals `cleaned_block[start_pos:end_pos]`. |
| v1 adapter proxy unit | Feed a v1 note; assert `source_units[0].unit_id` contains `:legacy:`, `argument_complete=false`, and schema/selection versions trigger refresh. |
| Admission invariant | Pass a block with one concrete anchored unit and a producer that returns zero cards; assert diagnostic key `admission_invariant_violation` is present and no fallback cards are produced. |
| No hidden renderer cap | Build memo with 5 `business_structure` explanation rows; assert renderer emits all 5 in formal-medium 4.1. |

---

## Batch A budget

**Credible.**

The design now treats the +80 target as net by naming concrete same-batch deletions:

- `_CARD_TYPES`, `_USAGE_TO_CARD_TYPES`, `_CARD_TYPE_MARKERS`, per-type candidate loop (`periodic_report_narrative_evidence_cards.py` ~300–350 lines of old taxonomy/marker code).
- `_truncate_cards`, `_select_diverse_cards`, producer count parameters.
- material-pack `_select_records` round-robin and count parameters (`annual_report_material_pack.py` ~120 lines).
- annual memo `card_group` and `valid_cards[:8]` (`synthesis_skills.py`).
- `classify_annual_render_role` and intermediate annual roles (`deep_analysis_material_snapshot.py`).
- annual renderer `row_limit` / `rows[:row_limit]` (`deep_analysis_renderer.py`).

Against these deletions, Batch A adds:

- `annual_argument_schema.py` (~120–150 lines).
- Source-unit materialization and family resolver in producer (~150–200 lines net).
- `argument_complete` plumbing in note writer, snapshot, and memo (~50–80 lines).
- Renderer label mapping update (~20–30 lines).

Net addition should land near or below +80. Hard stop at +100 is defensible if the old marker tables are removed rather than commented out.

## Batch B budget

**Credible.**

Named Batch B deletions:

- v1 adapter/map and old-type note fixtures.
- Residual old card-type titles, loader compatibility branches, and marker helpers that no longer serve generic noise/anchor detection.
- Duplicate pack/loader ordering and validation helpers merged into `annual_argument_schema.py`.

Estimated reduction: 110–180 lines. If reduction is under 80, the audit requirement in §19 applies.

---

## Implementation plan ready

`yes`

The design is sufficiently concrete: schema/selection versions are named, SourceUnit fields are specified, family-to-renderer-label mapping is explicit, the 4.4 filter rule is exact, caps are listed for removal by file, and the migration batches have acceptance criteria. The remaining items are implementation and test details, not design ambiguities.

---

## Recommended next step

Proceed to implementation planning. Priority order:

1. Add `annual_argument_schema.py` with constants, validation helpers, and v1 adapter.
2. Update producer to materialize SourceUnits and emit v2 cards.
3. Update note writer for v2 frontmatter and `argument_family` filenames.
4. Remove canonical-path caps from producer, pack, memo builder, snapshot, and renderer.
5. Add `argument_complete` to `MaterialRow` and filter 4.4 rows.
6. Add tests for the matrix in §16, especially the 4.4 boundary, source-unit ownership, and cap-isolation tests.
7. Run real-report acceptance on 复旦微电, 中际旭创, the sparse A-share sample, and the HK sample.

---

## Git status note

Only the Round 2 review notes file (`docs/agent_workflow/2026-07-11-annual-producer-v2-claude-review-round2-notes.md`) is intended to be added. No code, config, prompts, reports, knowledge notes, or raw data files were modified during this review. Pre-existing dirty worktree files (reports, broker digest notes, etc.) are unchanged.
