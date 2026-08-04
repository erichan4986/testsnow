# Annual Document Coverage Manifest Design

Date: 2026-07-24
Baseline: `c406f77`
Approval: pre-authorized by the user goal directive for autonomous execution

## 1. Goal

Add a deterministic, machine-readable coverage ledger for annual and interim report ingestion. The ledger
must show which recognized document sections and extracted evidence candidates reached the narrative
producer, which were omitted before producer review, which produced cards, and which were reviewed without
producing cards.

This batch changes auditability only. It must not change evidence selection, narrative cards, material rows,
Chapter 4, scoring, target price, risk, recommendation, technical analysis, or LLM behavior.

## 2. Problem

The current pipeline has strong unit-level diagnostics after a block enters
`build_periodic_report_narrative_evidence_cards()`, but it has two blind spots:

1. `_dedupe_and_prioritize_blocks()` and `_select_bounded_blocks()` discard candidates before unit-level
   producer diagnostics begin.
2. Report sections that never match an evidence extractor have no audit record.

Therefore `source_unit_decisions` proves ownership only for selected evidence blocks. It does not prove
document-level coverage and cannot distinguish an irrelevant rejected sentence from a completely unvisited
annual-report section.

## 3. Scope And Non-Goals

### In scope

- A-share and HKEX/Jina Markdown heading inventory.
- A fallback whole-document section when no heading can be recognized.
- Optional page locators only when an explicit page marker can be proven from source text.
- All extracted block candidates before usage limits and the 48-block cap.
- Evidence-stage and producer-stage dispositions.
- A compact summary that exposes partial coverage honestly.
- Persistence inside existing producer diagnostics and narrative-pack integrity.

### Out of scope

- Claiming every PDF page has been semantically understood.
- OCR, PDF page reconstruction, table parsing, financial metric extraction, or multi-year comparisons.
- Changing the 48-block evidence-pack cap or family reservations.
- Treating an unmapped section as irrelevant automatically.
- Adding coverage prose to generated stock reports.
- Writing duplicate excerpts, section bodies, or source units into the manifest.

## 4. Alternatives

### A. Add more counters to producer diagnostics

Rejected. The producer cannot count blocks removed before it is called and cannot see document sections that
never matched an extractor.

### B. Store every paragraph as a coverage row

Rejected. This would reproduce large portions of annual reports, create tens of thousands of low-value rows,
and repeat the storage-bloat problem. Paragraph-level semantic review belongs to a later ingestion adapter,
not this compatibility-safe batch.

### C. Section inventory plus candidate/block/unit decisions

Selected. It provides an honest hierarchy without duplicating source text:

```text
document -> recognized sections -> extracted candidates -> selected evidence blocks -> source units/cards
```

Unknown or unmatched content remains visible as partial coverage rather than being silently declared safe.

## 5. Architecture

Create `scripts/utils/periodic_report_coverage_manifest.py` as the sole schema and composition owner.

`periodic_report_evidence_pack.py` remains the extraction owner. It will retain three in-memory lists:

1. all extracted candidates before usage limits;
2. candidates surviving usage limits and priority sorting;
3. candidates selected after family reservation and the 48-block cap.

It passes those lists and cleaned source text to the coverage builder, then returns the resulting manifest as
an additive `coverage_manifest` field in the evidence pack.

`periodic_report_narrative_evidence_cards.py` remains the card-selection owner. After cards and
`source_unit_decisions` are final, it calls `finalize_periodic_report_coverage_manifest()` and stores the
result under `diagnostics["coverage_manifest"]`. Existing pack storage already persists and hashes producer
diagnostics, so no storage schema or second sidecar is required.

## 6. Coordinate And Identity Contract

All source spans use `coordinate_space = "periodic_report_cleaned_text.v1"`, the exact string produced by
`periodic_report_evidence_pack._clean_text()` before block extraction.

The manifest records:

- `document_sha256`: SHA-256 of that cleaned text;
- `cleaned_char_count`;
- `coverage_block_id`: SHA-256 identity over usage, section, title, start, end and source-text hash;
- `source_text_sha256`: SHA-256 of the extracted candidate text;
- source spans and heading spans as integers.

No identity depends on list position, Python object identity, output cap, or card selection. Re-running the
same source must produce byte-equivalent manifest content.

## 7. Document Section Inventory

The section scanner accepts only source-visible headings:

1. Markdown headings matching `^#{1,6}\s+...`;
2. A-share major headings matching a complete `第...节 ...` line when Markdown markers are absent;
3. a synthetic `document-root` section only when neither form exists.

Each section row contains:

```json
{
  "section_id": "section:<full-sha256>",
  "heading": "管理层讨论及分析",
  "heading_level": 1,
  "source_span": {"start": 1200, "end": 5300},
  "page_start": null,
  "page_end": null,
  "matched_coverage_block_ids": [],
  "coverage_state": "unmapped"
}
```

Duplicate headings at different source positions remain separate sections. A block belongs to the section
with the largest positive span overlap; ties go to the earlier section. A section may contain several blocks.
The content span is the text between the end of one heading and the start of the next recognized heading. If
that span contains fewer than 12 non-whitespace characters, the row is a `structural_only` heading and does
not count as an unresolved analytical section. This handles source-visible container headings without
silently excluding substantive governance or financial sections.

Page numbers are optional. Accepted proof is limited to a source line beginning or ending with an integer
adjacent to `年度报告`, `年報`, or `ANNUAL REPORT`, including the Jina form `7 2025 年年度报告 公司名`.
Standalone table-of-contents rows such as `7 管理层讨论及分析` are never page markers. The nearest proven
marker at or before a section start becomes `page_start` only when its end is within 240 source characters of
the heading; the last proven marker inside the section becomes `page_end`. Missing proof yields `null`.
Top-level `page_locator_status` is `available` when every substantive section has a page, `partial` when only
some do, and `unavailable` when none do.

Section states at evidence stage:

- `selected_for_review`: at least one selected evidence block overlaps the section;
- `candidate_not_reviewed`: candidates existed but all were removed by usage limits or capacity;
- `unmapped`: no extracted candidate overlaps the section;
- `structural_only`: source-visible heading with no substantive body before the next heading.

Section states after producer finalization:

- `card_selected`: at least one mapped block owns a selected source unit;
- `reviewed_no_card`: mapped selected evidence blocks were unit-reviewed but produced no card;
- `candidate_not_reviewed`, `unmapped`, and `structural_only` retain their evidence-stage meanings.

These are audit states, not investment relevance judgments.

## 8. Block Decisions

Every extracted candidate receives one evidence disposition:

- `selected_for_producer`;
- `omitted_usage_limit`;
- `omitted_capacity`.

Each block row has both a deterministic `coverage_block_id` and `evidence_block_id`. The latter is populated
only when the candidate survives usage limiting and receives the existing producer-facing ID such as
`business_overview-0`. Producer finalization joins unit decisions by exact `evidence_block_id`; it never joins
on title, excerpt, hash similarity, or list position.

Candidates with the same full identity are represented by one block decision with
`candidate_occurrences >= 1`. Their evidence and producer dispositions must agree; disagreement is a
validation error. This collapse affects only the audit ledger and never changes extractor or cap inputs.

After producer finalization, selected evidence blocks also receive one producer disposition:

- `card_selected`, with `selected_by_card_ids`;
- `reviewed_no_card`, with stable unit rejection counts;
- `not_reviewed`, only for pre-producer omissions.

The manifest does not store candidate text, card excerpts, or source-unit text. It stores hashes and IDs.

## 9. Manifest Schema

Schema version: `annual_document_coverage_manifest.v1`.

Top-level fields:

```text
schema_version
coordinate_space
stage                        evidence | producer
status                       ready | unavailable
analysis_coverage_status     complete | partial | unavailable
document_sha256
cleaned_char_count
report_type
document_style
page_locator_status
sections
block_decisions
summary
```

`status` meanings:

- `ready`: manifest is structurally valid, regardless of analytical completeness;
- `unavailable`: empty input or an invalid upstream manifest.

`analysis_coverage_status` meanings:

- `complete`: at evidence stage, every substantive section is `selected_for_review`; at producer stage,
  every substantive recognized section is `card_selected` or `reviewed_no_card`;
- `partial`: at least one substantive section is `candidate_not_reviewed` or `unmapped`;
- `unavailable`: no valid document manifest exists.

`summary` contains exact counts by section state, evidence disposition, producer disposition, plus:

```text
recognized_section_count
mapped_section_count
unresolved_section_count
candidate_block_count
selected_evidence_block_count
source_unit_count
selected_source_unit_count
```

No percentage is emitted when the denominator is zero.

## 10. Validation And Fail-Closed Behavior

`validate_periodic_report_coverage_manifest()` returns stable error codes. It checks:

- schema and coordinate-space versions;
- 64-character document/text hashes;
- non-negative monotonic spans within `cleaned_char_count`;
- unique section and block IDs;
- recognized enum values;
- stage-appropriate section states;
- selected evidence block IDs exactly match evidence-pack blocks before producer finalization;
- selected card IDs in block decisions exist in the producer output;
- summary counts equal recomputed counts.

The evidence builder must fail closed with `ValueError("invalid_coverage_manifest:<code>")` if its freshly
built manifest is invalid. Empty input returns the existing empty evidence pack plus an unavailable manifest.
The narrative producer must not trust a malformed or missing upstream manifest; it emits a canonical
unavailable manifest with `unavailable_reason = upstream_invalid|upstream_missing` while preserving existing
card behavior byte-for-byte apart from the additive diagnostics field.

## 11. Persistence

The finalized manifest is nested only under `producer_diagnostics`. The existing narrative pack store hashes
and validates the diagnostics payload, so it will persist coverage automatically without a schema migration.
Human narrative views and Markdown reports do not render it in this batch.

## 12. Required Tests

### Coverage module

1. A-share Markdown headings produce source-ordered distinct sections.
2. HKEX Markdown headings are inventoried without A-share assumptions.
3. duplicate heading names at different positions keep distinct IDs.
4. no headings produce one synthetic root section.
5. empty parent headings become `structural_only` and do not inflate unresolved counts.
6. explicit page markers populate page locators; TOC numbers and absent proof stay null.
7. maximal-overlap section mapping is deterministic.
8. selected, usage-limited, and capacity-omitted candidates receive exact dispositions.
9. selected decisions carry exact evidence and coverage IDs.
10. exact duplicate candidates collapse with an occurrence count and do not affect extractor selection.
11. no source text or excerpt field appears anywhere in the manifest.
12. identical inputs produce identical manifests.
13. malformed spans, hashes, IDs, stage states, enums, and summaries fail validation.

### Evidence-pack integration

14. selected block IDs in coverage exactly match `pack["blocks"]`.
15. family-reserved selection behavior and the 48-block cap remain byte-for-byte unchanged.
16. a candidate omitted by cap appears as `omitted_capacity`.

### Producer integration

17. selected and rejected unit decisions finalize their parent blocks correctly.
18. section states derive from finalized block states.
19. hand-built legacy evidence packs without coverage continue to produce identical cards and an unavailable
    coverage diagnostic rather than failing.
20. a malformed upstream coverage manifest cannot affect card selection.

### Storage and downstream regression

21. pack write/load round-trip retains the finalized coverage manifest and integrity hash.
22. annual material pack card ordering and display rows remain unchanged.
23. full existing evidence-pack, producer, storage, material-pack, report-quality, and source-boundary suites
    pass.

## 13. Runtime Budget

Target runtime net growth: `+180` lines. Hard stop: `+260` lines across the new module and two modified
runtime files. Tests and design documents are excluded. Stop and redesign if paragraph text, excerpts, a
second card selector, or report-rendering logic becomes necessary.

## 14. Failure Modes

| Failure | User-visible symptom | Guard |
|---|---|---|
| Manifest claims full coverage from selected blocks only | Missing annual sections appear reviewed | unmapped section inventory test |
| 48-block cap hides useful candidates | No explanation for omitted material | capacity disposition test |
| Usage limit and cap are conflated | Wrong remediation decision | exact evidence disposition tests |
| HK headings are parsed as A-share sections | fragmented or empty HK ledger | HKEX fixture |
| Page numbers are inferred | false source traceability | no-proof page test |
| Raw report text is duplicated | pack/Knowledge bloat | recursive forbidden-field test |
| Manifest changes card selection | report content regression | card identity tests |
| Malformed manifest poisons storage | stale or unauditable pack | validator and integrity tests |
| Duplicate headings collapse | coverage rows disappear | source-position identity test |

## 15. Acceptance

- Two design self-reviews are completed and all accepted findings are incorporated.
- TDD RED/GREEN evidence exists for each task.
- Runtime remains within budget.
- Focused and full offline tests, CI grep gates, and `git diff --check` pass.
- Local-cache acceptance includes at least one A-share fixture and the HKEX Black Sesame report.
- No report regeneration is required because this batch has no display or decision behavior.
