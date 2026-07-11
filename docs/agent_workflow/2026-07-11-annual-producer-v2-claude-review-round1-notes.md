# Annual Producer v2 — Claude Round 1 Design Review Notes

**Date:** 2026-07-11
**Design doc:** `docs/agent_workflow/2026-07-11-annual-producer-v2-design.md`
**Reviewer:** Claude Code
**Scope:** Read-only design review against existing producer / pack / synthesis / snapshot / renderer / quality-gate code.

---

## Verdict

`needs_revision`

The design is directionally sound and the five-family schema is a meaningful simplification. However, it currently understates the existence of a **second display-layer taxonomy** (`product_business`, `operation_update`, `management_view`, `competitiveness_rd`, `financial_explanation`) sitting between the proposed canonical families and the renderer, and it does not yet specify how `argument_complete` will be enforced at the Chapter 4.4 price-path boundary. These two issues must be resolved before implementation planning. No code changes were made for this review.

---

## Blocker

None — the design does not propose any action that would immediately break scoring, target price, risk, recommendation, or source-boundary invariants. The identified risks are architectural/detail gaps that can be fixed inside the design.

---

## Must-fix (6 findings)

### F-01: Hidden second taxonomy between canonical families and renderer

- **Severity:** high
- **Issue:** The design states that the five canonical family names "flow unchanged through annual memo `display_group` and `MaterialRow.render_role`. Downstream code must not translate them into another taxonomy." In the existing code, however, `SynthesisSkill._build_annual_report_memo` already maps old card types to an intermediate `display_group` set (`product_business`, `operation_update`, `management_view`, `competitiveness_rd`, `financial_explanation`), and `deep_analysis_material_snapshot.classify_annual_render_role` infers `render_role` from titles when `display_group` is absent. The renderer then groups rows by these render roles. If Batch A simply renames old card types to the five families but keeps the existing memo/snapshot/renderer pipeline, the families will be translated into the old display-layer taxonomy — exactly what the design forbids.
- **Code evidence:**
  - `scripts/utils/report_skills/synthesis_skills.py:523-531` — `card_group` maps old 8 types to 5 display groups.
  - `scripts/utils/deep_analysis_material_snapshot.py:326-339` — `classify_annual_render_role` maps titles to `product_business`, `operation_update`, etc.
  - `scripts/utils/reporter/sections/deep_analysis_renderer.py:891-916` — groups like `**业务结构**`, `**经营变化**`, `**研发与产品进展**`, `**财务变化原因**` are driven by these render roles.
- **Suggested fix:** Decide one of:
  1. Canonical families **are** the render roles — replace `product_business`/`operation_update`/`management_view`/`competitiveness_rd`/`financial_explanation` with the five family names everywhere, and update renderer labels accordingly; or
  2. Clarify that `render_role` is a display-layer grouping that may coincide with but is not identical to families, and explicitly permit the mapping, while still removing the old 8-type card taxonomy.
  Either way, update the design doc so Batch B's deletion list explicitly includes the intermediate display-role constants and the title-inference helper if option 1 is chosen.

### F-02: `argument_complete` boundary for Chapter 4.4 is not wired

- **Severity:** high
- **Issue:** The design says `argument_complete=false` single-point facts "must not independently enter 4.4 股价推演." The current formal-medium price-path logic selects rows purely by `source_layer` and `render_role` (`_first_row_by_role` in `deep_analysis_material_snapshot.py:364-369` and `_formal_medium_price_path_section` in `deep_analysis_renderer.py:629-701`). There is no `argument_complete` field in `MaterialRow`, and no filter checks it before 4.4.
- **Code evidence:**
  - `scripts/utils/deep_analysis_material_snapshot.py:20-36` — `MaterialRow` dataclass has no `argument_complete` field.
  - `scripts/utils/deep_analysis_material_snapshot.py:364-369` — `_first_row_by_role` picks the first annual row from a role list without completeness check.
  - `scripts/utils/reporter/sections/deep_analysis_renderer.py:644-701` — picks the first annual/broker/external row by layer for 4.4.
- **Suggested fix:** Add `argument_complete: bool` to the v2 card schema and to `MaterialRow`. In `build_chapter4_view_model`, exclude `argument_complete=false` rows from `price_path_rows` unless they are paired with a complete row from the same family or used only as supporting evidence (not as the standalone inference premise). Document the exact rule in the design: e.g., "4.4 may cite an atomic fact, but the conditional premise must be a complete argument row."

### F-03: Source-unit tracking and monotonicity are absent from current producer

- **Severity:** high
- **Issue:** The design requires every card to carry `source_unit_ids`, `source_units`, monotonic positions, and a provenance trail. The existing producer only emits `source_block_id`, `source_excerpt`, and hashes. There is no concept of a "source unit" as a first-class object, and the deduplication logic works on normalized excerpt fingerprints rather than unit ownership.
- **Code evidence:**
  - `scripts/utils/periodic_report_narrative_evidence_cards.py:643-647` — `_split_snippets` returns strings, not unit objects with ids/positions.
  - `scripts/utils/periodic_report_narrative_evidence_cards.py:987-1026` — dedupe uses character n-grams and substring containment, not unit ids.
- **Suggested fix:** Specify the unit data structure in the design (e.g., a dict with `unit_id`, `start_pos`, `end_pos`, `text`, `block_id`). The v2 producer must materialize units before card assembly, and the card schema must reference them. This is a nontrivial data-model change and should be reflected in the Batch A file scope and test matrix.

### F-04: "No cap" requirement conflicts with existing hard caps in three places

- **Severity:** medium-high
- **Issue:** The design says "Material retention has no fixed total or per-family business cap." The current pipeline imposes caps in at least three independent locations:
  1. Producer: `max_cards_per_type=12`, `max_total_cards=24` (`periodic_report_narrative_evidence_cards.py:492-493`).
  2. Material pack: `max_cards=8`, `per_type_limit=2` (`annual_report_material_pack.py:139-140`), with a second fill round that can exceed `per_type_limit` (`annual_report_material_pack.py:564-570`).
  3. Synthesis loader: `max_cards=12`, `per_type_limit=3` (`periodic_report_narrative_card_synthesis_items.py:41-43`; called from `synthesis_skills.py:274-285` with these values).
- **Code evidence:** See line references above.
- **Suggested fix:** For Batch A, explicitly state which caps are removed and which remain as deterministic tie-breakers. The design currently says "no fixed total or per-family business cap" but does not address the synthesis loader or material pack. Recommended:
  - Remove `max_total_cards` and `per_type_limit` from producer, material pack, and synthesis loader.
  - Keep quality-score ordering and source-order tie-breaking.
  - Move any remaining "fairness" round-robin into the quality-ordering step, not a hard cut.
  Add a test proving >12 distinct high-quality cards survive end-to-end.

### F-05: Family-assignment precedence is not yet deterministic enough for ambiguous snippets

- **Severity:** medium
- **Issue:** The design's precedence rules (financial mechanism > technology/product progress > operating progress > management outlook > business structure) are reasonable, but the existing producer frequently emits **two card types for one snippet** (e.g., `management_market_view` + `market_outlook`, `technology_platform` + `rd_product_progress`, `business_model` + `rd_product_progress`). The design says "Each card receives exactly one `argument_family`," and secondary signals go into `secondary_signals`. The current code has no mechanism to pick a single family when multiple usage hints match; it emits one candidate per matched card type and then dedupes within scopes.
- **Code evidence:**
  - `scripts/utils/periodic_report_narrative_evidence_cards.py:33-65` — `_USAGE_TO_CARD_TYPES` maps one usage to multiple card types.
  - `scripts/utils/periodic_report_narrative_evidence_cards.py:620-629` — loops over all `card_types` for a snippet and appends one candidate each.
- **Suggested fix:** Add an explicit precedence resolver to the design: given a snippet and the set of matched families, apply the rule order and emit exactly one family, recording the others in `secondary_signals`. Provide fixtures for the ambiguous cases listed in the requirement-test matrix (e.g., management-view vs market-outlook).

### F-06: Sparse-report atomic-fact retention is not guaranteed by current filters

- **Severity:** medium
- **Issue:** The design requires that "sparse reports may retain self-contained official single-point disclosures" and that "单点但自洽、具体、可追溯的官方事实必须可保留." The existing producer has many aggressive filters (`_looks_like_table_fragment`, `_looks_like_definition_fragment`, boilerplate detectors, risk-paragraph rejection, checkbox rejection) that can return empty cards for a sparse report even when a concrete official sentence exists. For example, a one-sentence business description with a checkbox marker could be rejected by `_strip_applicability_markers` and then fall below quality thresholds.
- **Code evidence:**
  - `scripts/utils/periodic_report_narrative_evidence_cards.py:1029-1071` — `_is_valid_excerpt` rejects many categories.
  - `scripts/utils/periodic_report_narrative_evidence_cards.py:974-984` — applicability markers are stripped, but the remaining text may be short or lack markers.
- **Suggested fix:** Add a "sparse-report fallback" rule to the design: after normal filtering, if no cards are admitted and the evidence pack contains at least one non-boilerplate sentence with a concrete anchor (product, segment, metric, customer), admit it as `argument_complete=false` with the appropriate family. This ensures empty output is not caused by over-filtering.

---

## Nice-to-have (3 findings)

### N-01: Add schema-validation helper spec

- **Severity:** low
- **Issue:** The design says `annual_argument_schema.py` owns "schema validation helpers" but does not describe what they validate. Without a spec, Batch A may omit validation or add ad-hoc checks.
- **Suggested fix:** Specify helpers such as `validate_card_v2(card)`, `validate_family(family)`, `is_v1_card_type(card_type)`, `adapt_v1_to_v2_note(frontmatter)`. Include the allowed key set and required fields.

### N-02: Selection version and migration acceptance criteria are vague

- **Severity:** low
- **Issue:** The design says "Advance the selection version so current notes refresh" but does not name the new version string or how migration acceptance is gated.
- **Suggested fix:** Propose a concrete selection version (e.g., `periodic_report_narrative_evidence_v2`) and state that Batch B can remove the v1 adapter only after all configured stocks' notes have been refreshed and the real-report samples pass.

### N-03: Diagnostics contract should list observable keys

- **Severity:** low
- **Issue:** Section 13 lists diagnostic categories but does not define JSON keys. Producers and tests will diverge without a schema.
- **Suggested fix:** Add a sample diagnostics envelope to the design with keys such as `source_blocks_seen`, `usable_units`, `candidates_by_family`, `admitted_by_family`, `argument_complete_counts`, `rejection_counts`, `candidate_explosion`, `v1_adapter_use_count`.

---

## Requirement–test gaps

| Design requirement | Existing test coverage | Gap |
|---|---|---|
| Five canonical families | `test_periodic_report_narrative_evidence_cards.py` tests old 8-type outputs | No v2 family fixtures; no precedence tests |
| Single-family ownership | Tests verify dedupe of identical management/outlook text into one card | No test for multi-signal snippet emitting once with `secondary_signals` |
| Original source preservation | Tests check `source_excerpt` is a substring of block | No `source_unit_ids` / monotonic-position tests |
| Official single-point disclosure retained | No sparse-report fixture | Need sparse A-share fixture with one concrete fact |
| Complete argument preferred | No quality-score tie test | Need test where complete card ranks above atomic fact |
| Same block → multiple cards | `test_business_model_and_rd_product_progress_do_not_dedupe_each_other` | Need test requiring non-overlapping unit ids |
| No source-unit reuse | None | New test required |
| No hidden count cap | `test_default_per_type_limit_allows_more_than_three_clean_cards` tests producer only | Need end-to-end >12 card survival test through pack and renderer |
| Semantic novelty | None explicit | Need test with same wording but different products/periods |
| Duplicate removal | Exact and near-dup tests exist | Need anchor-signature duplicate test |
| Sparse-report behavior | None | New real or fixture-based test required |
| Candidate explosion | None | New fail-closed test required |
| v1 migration | None | Need adapter and selection-version refresh test |
| Direct family propagation | Tests use old display groups (`product_business`, etc.) | Need test that family name reaches renderer group label |
| Citation hygiene | Covered by `check_report_quality.py` / `check_report_source_boundary.py` | Need v2 report sample run |
| Source boundary | Covered for broker/external; narrative cards already marked `synthesis_display_only` | Need to confirm v2 cards keep `knowledge_eligible=false`, `scoring_eligible=false` |
| No business-path regression | Byte-for-byte business-path tests not present | Add snapshot test for score/target/risk/technical/recommendation outputs before/after v2 |

---

## Batch A / Batch B runtime budget assessment

### Current line counts (relevant files)

| File | Lines | Notes |
|---|---|---|
| `scripts/utils/periodic_report_narrative_evidence_cards.py` | 1,684 | Old producer, mostly markers/skip logic |
| `scripts/utils/annual_report_material_pack.py` | 641 | Pack selection with caps |
| `scripts/utils/periodic_report_narrative_card_note_writer.py` | 346 | Writer only; frontmatter shape must change for v2 |
| `scripts/utils/periodic_report_narrative_card_synthesis_items.py` | 200 | Loader with caps |
| `scripts/utils/report_skills/synthesis_skills.py` | 2,054 | Memo builder with old card→display_group mapping |
| `scripts/utils/deep_analysis_material_snapshot.py` | 430 | Render-role inference |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 1,881 | Groups by render role |
| **Total** | **~7,236** | |

### Batch A (+80 lines target)

Realistic only if the v2 producer is a **surgical refactor** of the existing producer rather than a rewrite. Required additions:
- `scripts/utils/annual_argument_schema.py` (~120–150 lines new).
- Unit-tracking and family-precedence logic inside producer (~+100–200 lines net after removing some old dedup code).
- `argument_complete` plumbing through note writer and snapshot (~+50 lines).

This already risks exceeding +80 unless some old producer code is deleted in Batch A. **Recommendation:** treat +80 as the *net* target by deleting the old 8-type marker tables that become unused, rather than adding 80 on top of the full legacy file.

### Batch B (–110 to –180 lines target)

Achievable if the following are actually deleted:
- Old `_CARD_TYPES`, `_USAGE_TO_CARD_TYPES`, and `_CARD_TYPE_MARKERS` from producer (~300–350 lines).
- Old dedupe-scope and per-type/global cap logic from producer and pack (~100 lines).
- `HIGH_VALUE_CARD_TYPES`, `OTHER_KNOWN_CARD_TYPES`, `_CARD_TYPE_TITLES`, per-type limits, and second-fill round from material pack (~120 lines).
- Old `card_group` mapping and `classify_annual_render_role` title inference from synthesis/snapshot/renderer (~80–100 lines).
- Legacy v1 notes and adapter (~80 lines after migration).

**Risk:** the v2 family-precedence logic, anchor extraction, and quality scoring may themselves require ~250–350 lines, partially offsetting deletions. The design should identify specific deletions by function name to make the budget credible.

---

## Expected deletions / replacements

| Old helper/file | Replace with | Remove in |
|---|---|---|
| `_CARD_TYPES` (8 old types) | `CANONICAL_FAMILIES` in `annual_argument_schema.py` | Batch A |
| `_USAGE_TO_CARD_TYPES` multi-type mapping | Single-family precedence resolver | Batch A |
| `_CARD_TYPE_MARKERS` (old marker tables) | Anchor/signal scoring without per-type markers | Batch B |
| `_dedupe_scope` and old fingerprint dedup | Source-unit ownership + anchor-signature dedup | Batch B |
| `max_cards_per_type` / `max_total_cards` in producer | Remove; bound by source-unit count with fail-closed gate | Batch A/B |
| `max_cards` / `per_type_limit` in material pack and synthesis loader | Remove; quality ordering only | Batch A/B |
| `HIGH_VALUE_CARD_TYPES` / `OTHER_KNOWN_CARD_TYPES` | Use canonical family order directly | Batch B |
| `card_group` in `synthesis_skills.py` | Direct family assignment; no display-group translation | Batch B |
| `classify_annual_render_role` + title inference | Either delete (if families become render roles) or document as permitted display mapping | Batch B |
| `_select_diverse_cards` block-diversity limit | Remove or repurpose as quality tie-breaker | Batch B |
| v1 adapter in `annual_argument_schema.py` | Delete after migration acceptance | Batch B |

---

## Real-report acceptance samples

The design lists four sample classes but does not name concrete tickers for the sparse A-share and HK cases. From the repo config and existing tests, likely candidates are:

- **复旦微电** — existing fixture stock; rich FPGA/MCU narrative.
- **中际旭创** — existing fixture stock; high-volume management/outlook narrative.
- **Sparse A-share** — suggest a small-cap A-share with minimal MD&A narrative, e.g., one of the test fixture stocks that currently produces few cards.
- **港股** — need a stock with `market: "HK"` in `config/stocks.json`; verify `hk_periodic_report_fetcher.py` usage mapping and Traditional Chinese source units.

**Action:** the design should explicitly name the sparse A-share and HK tickers and state that HK samples must pass without A-share-specific heading assumptions.

---

## Recommended next step

1. Revise the design doc to resolve F-01 (display-layer taxonomy) and F-02 (4.4 `argument_complete` boundary) explicitly.
2. Add the source-unit data model and family-precedence resolver spec.
3. Name the concrete selection version, sparse A-share sample, and HK sample.
4. Then proceed to **Round 2** review of the revised design before any implementation.

---

## Git status note

Only this review notes file is intended to be added. No code, config, prompts, reports, knowledge notes, or raw data files were modified during the review.
