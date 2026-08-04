# 6A-4 Annual Narrative Orphan Resolution Design

## Goal

Clear the `stale_orphan` migration gate without losing an actionable annual-report
fact and without making legacy Markdown a second producer input. This prepares,
but does not implement, the 6B pack-first loader switch.

## Evidence

The 6A-3 read-only ledger contains 127 v2 cards whose complete SourceUnit identity
is not in the current pack. Seven have `argument_complete=true`; examples include
中际旭创的产品速率、乐鑫科技的竞争风险、以及黑芝麻智能的收入、产品与订单事实。
They cannot be bulk-archived merely to make the migration counter green.

## Decision

Use a raw-source-first resolution path:

1. A concrete orphan must be recovered by the existing annual evidence pack and
   the single v2 producer selector. Its old Markdown note is never copied into the
   current JSON pack.
2. A stale card may be archive-eligible only after all of its persisted
   SourceUnits map exactly to current raw-evidence unit decisions and every
   non-selected unit has a narrow producer-owned archive-safe reason. The stale
   Markdown excerpt itself never decides archive eligibility.
3. Broad `audit_or_policy`, table/OCR, industry-barrier, ESG, operating-mode,
   governance, incomplete, and unclassified signals are not archive-safe. They
   can contain investment-relevant facts and remain blockers unless the current
   producer selects them.
4. Every archive-eligible result records a deterministic reason. Every other
   orphan remains blocking until the producer emits a card from the raw source.

This keeps the current source-of-truth boundary intact: raw annual material feeds
the producer; the validated pack persists its result; Markdown is only a human
projection during migration.

## Scope

Allowed runtime candidates:

- `scripts/utils/annual_argument_schema.py`
- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `scripts/utils/annual_report_material_pack.py`
- `scripts/previews/periodic_report_narrative_cards_acceptance.py`

Allowed tests:

- `tests/utils/test_annual_argument_schema.py`
- `tests/utils/test_periodic_report_narrative_evidence_cards.py`
- `tests/utils/test_annual_report_material_pack.py`
- `tests/utils/test_periodic_report_narrative_pack_store.py`
- `tests/utils/test_periodic_report_narrative_card_note_writer.py`
- `tests/reporter/test_periodic_report_narrative_cards_acceptance_script.py`

No report renderer, memo/snapshot, citation, profile, scoring, target, risk,
technical, recommendation, intake, LLM prompt, or normal report entry changes.
No note move/delete occurs in this batch.

## Resolution Contract

### Producer-Owned SourceUnit Decisions

The producer remains the only owner of source materialization, noise rejection,
family admission, bundling, and card selection. Its diagnostics add a versioned
`source_unit_decisions` list derived during the existing producer pass. Each
entry contains only deterministic audit data:

```python
{
    "source_block_id": "business_overview-0",
    "source_unit_id": "business_overview-0:u4",
    "source_text_hash": "<normalized exact-text sha256>",
    "source_order": 4,
    "disposition": "selected" | "rejected",
    "reason": "selected" | "<detailed producer reason>",
    "selected_by_card_ids": ["..."],
}
```

The detailed diagnostic has its own schema version. Instrumentation alone does
not change card admission or `selection_version`, but it changes persisted
producer diagnostics and pack hashes; temporary packs must therefore be
refreshed and round-tripped before acceptance. If the recovery stage changes any
admission, family, continuation, or bundling predicate, `SELECTION_VERSION` is
bumped once and pack/note freshness tests must prove that the old version is
rejected or refreshed. The acceptance layer consumes these decisions and must
not call or reproduce private producer predicates.

Detailed archive-safe reasons are intentionally narrower than the producer's
existing aggregate `rejection_counts` buckets:

- `section_label`
- `regulatory_disclosure`
- `audit_procedure`
- `accounting_policy_definition`
- `checkbox_or_page_marker`
- `definition_or_hash`

An archive-safe reason is valid only when its narrow unit-level predicate
directly matches the current unit. A block-context fallback cannot make one unit
archive-safe. All other rejection reasons are non-archive-safe. In particular,
`audit_or_policy` is an aggregate compatibility bucket, not an archive reason.

### Exact Current-Source Mapping

Persisted note SourceUnits are audit fingerprints only. They map to current
producer decisions in this order:

1. exact `(source_block_id, source_unit_id, normalized_text_hash)`;
2. one unique ordered sequence of normalized hashes in the same source block;
3. one unique ordered sequence of normalized hashes contained within one source
   block anywhere in the complete current evidence set, used only when a source
   block was deterministically reindexed.

Every hash in a multi-unit card must map to a distinct current unit in original
order. Zero matches become `stale_source_missing`; multiple matches become
`stale_source_ambiguous`. Neither state is archive-eligible. There is no fuzzy
matching, token overlap, embedding, or excerpt rewriting.

### Producer Recovery

The existing producer remains the only selector. A recovery is valid only if:

- its generated v2 card has exact `source_units` from the current evidence pack;
- the output is a valid current card, not an adapter around a legacy note;
- it passes the existing noise and source-order guards; and
- it does not reuse a SourceUnit already selected by another current card; and
- it is selected from the exact current units matched above, never from legacy
  Markdown prose.

Family reassignment is permitted only through the existing canonical family
resolver. No stock-specific exception, second selector, text similarity score, or
legacy-note-derived candidate is allowed.

### Migration Classification

Each original `stale_orphan` enters exactly one source-resolution state:

- `stale_resolved_selected`: every old unit maps to a currently selected unit;
- `stale_resolved_structural`: every old unit maps to an archive-safe structural
  rejection;
- `stale_resolved_mixed`: every old unit maps and the card contains both selected
  and archive-safe structural units;
- `stale_recovery_required`: at least one mapped current unit is rejected for a
  non-archive-safe reason;
- `stale_source_missing`: no exact current raw-source sequence exists;
- `stale_source_ambiguous`: more than one exact current sequence exists.

Within every resolved state, the audit records current unit IDs, covering card
IDs, and archive-safe reasons per old unit. A mixed card resolves only when every
unit is selected or archive-safe. Concrete product, customer, application,
financial metric, operating cause/effect, named competitor, or named-exposure
risk content rejected by the current producer remains `stale_recovery_required`.
`table_or_ocr`, `too_short`, broad boilerplate, and unknown reasons also remain
recovery blockers.

Output drift is an independent whole-pack gate, not an orphan state. Acceptance
reports `legacy_only_selected_records` and `pack_only_selected_records` with
record identity and originating stale classification across all stale v2
categories. Either list being non-empty blocks 6B.

### Resolution Sequence

1. A read-only acceptance pass maps each stale SourceUnit fingerprint to the
   producer-owned current unit decisions and assigns one migration state.
2. For every recovery-required item, compare its source block and units against
   the current raw evidence pack. Fix the existing producer's admission, family,
   or bundling predicate only where the raw source contains an actionable fact.
3. When recovery changes selection behavior, bump `SELECTION_VERSION`, refresh
   packs in a temporary local-cache copy, and rerun classification. No
   generated pack may contain legacy-note content that cannot be traced to the
   current raw evidence pack.
4. Compare the unmodified legacy loader to pack shadow. A filtered stale-note
   simulation may explain drift, but it cannot satisfy the 6B parity gate.

## Acceptance Gate Before 6B

On all eleven current note directories, including the eight with stale effects:

1. The six mutually exclusive source-resolution counts sum to the original
   orphan inventory; `stale_recovery_required`, `stale_source_missing`, and
   `stale_source_ambiguous` are all zero.
2. Every former orphan has an exact current-source mapping and every mapped unit
   is selected or has one narrow archive-safe reason.
3. Actual, unfiltered `selected_material_parity` and `synthesis_items_parity`
   pass between the legacy loader and pack shadow. A no-move exclusion
   simulation is diagnostic only.
4. `legacy_only_selected_records` and `pack_only_selected_records` are empty
   across all stale categories, not only the original orphans.
5. `v1_diagnostics_parity` remains unchanged.
6. The acceptance output records the explicit local cache root used for all
   eleven stocks. Missing local input stops the gate; it cannot silently use the
   network or an undeclared fallback directory.
7. No v2 Markdown is physically moved or deleted until the user separately
   approves the dry-run archive manifest.
8. Only then may the 6B implementation task be written. 6B itself still requires
   fresh formal-medium and formal-thin report parity after a pack-first switch.

## Required Tests

1. Producer decision diagnostics cover every materialized unit exactly once;
   selected units record owning card IDs and rejected units retain detailed
   reasons while aggregate rejection counts remain compatible.
2. Direct section-label, regulatory, audit-procedure, accounting-policy,
   checkbox/page, and definition/hash units are archive-safe; industry-barrier,
   ESG, operating-mode, governance, table/OCR, product, metric, causal, and
   named-risk fixtures are not.
3. Exact identity, same-block reindex, unique cross-block reindex, ambiguous
   sequence, missing sequence, and multi-unit mixed-resolution fixtures exercise
   the mapping order without fuzzy matching.
4. Legacy-only prose cannot produce a card or an archive-safe result when no
   exact current unit decision exists.
5. A selected stale note creates a concrete legacy-only material diff and blocks
   6B even when a filtered simulation passes.
6. A selection predicate change bumps `SELECTION_VERSION`; old pack validation
   fails closed and old note freshness triggers refresh.
7. A/H fixtures cover simplified/traditional regulatory text, accounting tables,
   named products, concrete metrics, competitors, and causal explanations.
8. The eleven-stock local-cache gate reports all six source-resolution counts,
   complete output-drift identities, explicit cache provenance, and zero
   unresolved/output-drift blockers before 6B.

## Failure Modes

| Failure | Guard | Test / acceptance proof |
| --- | --- | --- |
| Genuine fact is dropped as noise | Only producer-owned narrow archive reasons resolve a unit | Product, metric, industry-barrier and named-risk fixtures stay blocking |
| Legacy text is copied into pack | Recovery only accepts exact current producer decisions | Legacy-only fixture cannot produce a recovered card |
| Unit IDs shift | Unique ordered exact-hash sequence remaps current units | Reindexed and ambiguous-sequence fixtures |
| Recovery creates a second selector | Reuse the existing selector and SourceUnit uniqueness validation | Duplicate-SourceUnit test |
| Family drift hides a fact | Existing canonical resolver owns family | Cross-family producer fixtures |
| A partial archive changes report material | Actual legacy/pack selected material and synthesis parity are hard gates | Output-affecting stale-note fixture |
| 6B starts before migration proof | All source-resolution blockers and actual output drift are zero | CLI/acceptance assertion |

## Budget and Stop Conditions

- Target: replace existing predicates and diagnostics, not a new recovery engine.
- Before implementation, record SHA256 and line counts for all four allowed
  runtime files. Runtime target: local net `+80` lines across them by
  extending the existing producer loop and classifier rather than adding a
  recovery engine.
- Local hard stop: net `+120` lines or any need for a second selector/parser.
- The parent Batch 6 ledger remains authoritative. Its original four runtime
  files had a locked 1,799-line baseline and currently total 2,008 lines
  (approximately `+209`). Changes to `annual_report_material_pack.py` and the
  acceptance script must keep that four-file cumulative delta at or below the
  existing 6A `+300` hard stop. The schema and producer changes are still
  counted in the 6A4 local budget.
- Stop and return to design if a concrete orphan cannot be recovered from the
  current raw evidence pack without weakening source/noise guards.
