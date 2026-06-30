# Periodic Report Narrative Evidence Cards Design

> **Date**: 2026-06-21
> **Owner**: Codex
> **Status**: Draft for Claude Round 1 Review

---

## 1. Goal

Add a helper-only annual/semiannual report layer that extracts short, evidence-bound narrative cards from report text.

This fills the gap between two existing paths:

- `periodic_report_fulltext_analysis`: useful LLM-assisted six-section summary, but mixed with interpretation and therefore material-layer only.
- `periodic_report_filing_fact`: exact structured numeric filing facts such as revenue, net profit, and operating cash flow.

Narrative cards should capture the high-value annual-report text that other data sources usually cannot provide:

- management market judgment;
- company operating updates;
- business model and product/customer descriptions;
- R&D/product/project progress;
- financial notes such as impairment reasons, cash-flow explanations, audit key matters, governance dissent, and subsidy/investment explanations.

The first version should not change pipeline behavior. It should prove that cards can be extracted, bounded, typed, and evidence-linked without confusing them with confirmed facts or fulltext LLM judgments.

---

## 2. Non-Goals

- Do not remove or replace the fulltext LLM path.
- Do not persist `periodic_report_fulltext_analysis` to Knowledge.
- Do not write narrative cards to real `knowledge/` in v1.
- Do not feed narrative cards into scoring, risk scoring, or `KnowledgeSynthesizer` in v1.
- Do not call an LLM in v1.
- Do not fetch annual reports or access the network.
- Do not rewrite `periodic_report_extractor.py`; it is a v0 reference, not the new public interface.
- Do not treat narrative cards as `confirmed_fact` or `fact_candidate`.
- Do not generate investment advice, valuation opinions, or buy/sell conclusions.

---

## 3. Current Context

| Existing Piece | What It Does | Useful For This Design | Limitation |
|---|---|---|---|
| `periodic_report_extractor.py` | Standalone v0 extractor for management views, risk disclosures, business segments, R&D, capex, and financial forensics | Provides category vocabulary and old tests | Mixes excerpts, interpretations, and financial flags in one item shape |
| `periodic_report_evidence_pack.py` | Builds deterministic bounded report blocks and usage labels | Primary input for cards | Some usages are broad and may include table noise |
| `periodic_report_fulltext_llm_analysis.py` | Builds fulltext chunks/prompt and validates LLM six-section output | Downstream consumer later | Its judgments are not safe as durable facts |
| `periodic_report_structured_facts.py` | Builds exact numeric filing facts with evidence anchors | Separate numeric channel | Not meant for text narrative |
| `periodic_report_product_project_evidence.py` | Extracts product/customer/project snippets and deterministic backfill judgments | Useful snippet-ranking references | Current outputs are short judgments, not durable source cards |

The old v0 extractor proves this idea existed before the fulltext LLM path. This design keeps that useful idea but narrows the schema: cards are bounded evidence snippets with light metadata, not report-ready analysis.

---

## 4. Source-Type Contract

Use a new source type:

```text
periodic_report_narrative_evidence
```

This source type is distinct from:

| Source Type | Role | Knowledge v1 | Scoring v1 |
|---|---|---:|---:|
| `periodic_report_fulltext_analysis` | LLM/rule mixed material summary | No | No |
| `periodic_report_filing_fact` | Exact numeric filing fact | Existing Phase B writer only | No |
| `periodic_report_derived_fact` | Computed value | No | No |
| `periodic_report_risk_signal` | Typed numeric risk signal | No | Later Phase C |
| `periodic_report_narrative_evidence` | Original text evidence card | No | No |

Narrative cards may become synthesis material later, but v1 only produces a helper output. Future Knowledge persistence must be a separate Phase B design with stricter card-type allowlists and stale-data policy.

---

## 5. Card Types

V1 should produce only these card types:

| Card Type | Meaning | Preferred Evidence-Pack Usages |
|---|---|---|
| `business_model` | What the company does, products/services, sales model, customers, applications | `business_overview`, `business_model`, `product_capacity_profile`, `sales_certification_model` |
| `operation_update` | Management explanation of annual operating changes, volume, customer introduction, order rhythm, capacity/inventory/project progress | `management_strategy`, `management_market_view`, `business_overview`, `segment_table`, `production_sales_inventory_table` |
| `management_market_view` | Industry demand, competition, localization, policy, standards, market cycle, technology trend | `industry_outlook`, `management_market_view`, `risk_disclosure` |
| `rd_product_progress` | R&D direction, product launch, certification, validation, mass production, customer introduction, IP progress | `rd_table`, `rd_investment_table`, `product_capacity_profile`, `management_strategy` |
| `financial_note` | Management/accounting explanation for cash flow, impairment, inventory, receivables, audit key matters, governance dissent, subsidy, investment, goodwill, financial assets | `cash_flow_capex_table`, `asset_impairment_note`, `ar_aging_note`, `inventory_note`, `audit_key_matters`, `governance_dissent`, `government_grant_note`, `financial_assets_note`, `goodwill_note` |

V1 should prefer fewer high-quality cards over many noisy cards. A reasonable default is at most 3 cards per type and at most 12 cards total.

Disambiguation examples:

- `operation_update`: "报告期内销量、产能、订单、库存、客户导入、项目投产发生了什么变化。"
- `management_market_view`: "管理层如何判断行业景气、竞争格局、价格趋势、政策标准、国产替代或技术周期。"

`financial_note` stays broad in v1 because cards do not enter Knowledge or scoring. If a later phase persists narrative cards, split `audit_governance_note` from `financial_note` first; audit key matters and governance dissent are governance/disclosure signals, not ordinary financial explanations.

---

## 6. Proposed Schema

Helper output:

```python
{
    "schema_version": "periodic_report_narrative_evidence_cards.v1",
    "stock_code": "300777",
    "stock_name": "中简科技",
    "report_year": 2025,
    "report_type": "annual",
    "cards": [...],
    "diagnostics": [...]
}
```

Card:

```python
{
    "schema_version": "periodic_report_narrative_evidence_card.v1",
    "source_type": "periodic_report_narrative_evidence",
    "card_id": "periodic:300777:2025:annual:narrative:management_market_view:0",
    "stock_code": "300777",
    "stock_name": "中简科技",
    "report_year": 2025,
    "report_type": "annual",
    "card_type": "management_market_view",
    "title": "管理层对行业需求与竞争格局的判断",
    "source_block_id": "management_market_view-0",
    "evidence_refs": ["management_market_view-0"],
    "source_excerpt": "年报原文短摘录...",
    "keywords": ["国产替代", "价格承压"],
    "confidence": "medium_high",
    "source_credit": 75,
    "knowledge_eligible": False,
    "synthesis_eligible": False,
    "experimental": True,
}
```

Important constraints:

- `source_excerpt` must be original report text, not an LLM rewrite.
- `title` may be a short deterministic label, but should not add unsupported conclusions.
- `keywords` must be extracted from the excerpt or card-type marker set.
- `confidence` describes extraction confidence only; it is not a claim-verification tier.
- `synthesis_eligible` stays `False` in v1. A later phase may flip it behind an explicit switch and tests.
- Cards must not contain LLM/judgment-path fields: `judgment`, `interpretation`, `claim_status`, `verification_status`, `report_eligible`, `knowledge_persisted`, `output_path`, or `planned_path`.
- Tests must enforce the card dictionary key allowlist so future edits cannot silently add fact-candidate or write-path fields.

---

## 7. Extraction Approach

Create:

```text
scripts/utils/periodic_report_narrative_evidence_cards.py
tests/utils/test_periodic_report_narrative_evidence_cards.py
```

Public helper:

```python
def build_periodic_report_narrative_evidence_cards(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    evidence_pack: dict,
    max_cards_per_type: int = 3,
    max_total_cards: int = 12,
) -> dict:
    ...
```

Implementation outline:

1. Read only `evidence_pack["blocks"]`.
2. Select candidate blocks by usage map from Section 5.
3. Split each block into bounded snippets/sentences.
4. Score snippets using card-type marker sets.
5. Reject snippets that look like pure table fragments, table-of-contents fragments, or boilerplate disclaimers.
6. Deduplicate by normalized excerpt text.
7. Rank within each card type first; keep up to `max_cards_per_type` per type; then apply `max_total_cards` by fixed card-type order from Section 5 and within-type score/order. This keeps output deterministic and prevents one verbose section from crowding out all other card types.
8. Emit diagnostics for empty evidence pack, no candidates, or all candidates filtered.

V1 can reuse ideas from:

- `_rank_sentences` and category keywords in `periodic_report_extractor.py`;
- table-fragment and product/project snippet filtering patterns from `periodic_report_product_project_evidence.py`;
- source block ids and usage labels from `periodic_report_evidence_pack.py`.

Do not import or call the fulltext LLM analysis helper.

---

## 8. Quality Rules

Each card must satisfy:

- `source_type == "periodic_report_narrative_evidence"`;
- non-empty `card_type`;
- non-empty `source_block_id`;
- `evidence_refs == [source_block_id]`;
- `source_excerpt` length between 40 and 500 chars after whitespace normalization;
- no Markdown table row-only excerpt;
- no table-of-contents dot leader excerpt;
- no raw URL;
- no LLM phrases such as "这意味着", "说明", "需要跟踪" unless those exact words are in the original excerpt;
- `knowledge_eligible is False`;
- `synthesis_eligible is False`;
- no `claim_status`, `verification_status`, `knowledge_persisted`, `output_path`, or `planned_path`;
- stable deterministic ordering.

If a card cannot satisfy these rules, skip it and record a diagnostic rather than emitting a low-quality card.

---

## 9. Test Plan

Focused tests should cover:

1. `business_model` card from a company description block.
2. `management_market_view` card from a management/industry judgment block.
3. `rd_product_progress` card from product certification or mass-production text.
4. `financial_note` card from impairment/cash-flow/audit/governance note.
5. Cards preserve source block id and evidence refs.
6. Cards are original excerpts, not generated judgments.
7. Emitted card keys match the v1 allowlist and do not include `judgment`, `interpretation`, `claim_status`, `verification_status`, `report_eligible`, `knowledge_persisted`, `output_path`, or `planned_path`.
8. Table-only / dense-numeric snippets are rejected with an explicit diagnostic.
9. LLM-style judgment phrases ("这意味着", "说明", "需要跟踪") are rejected unless they are verbatim in the original excerpt.
10. Cards never carry `fact_candidate`, `confirmed_fact`, `claim_status`, or `verification_status` markers.
11. Helper returns no file paths and no `knowledge_persisted` flag.
12. Empty input returns empty cards plus diagnostic.
13. Stable id/order across repeated calls, including per-type and total cap truncation.
14. Real-cache smoke check over at least 中简科技 and one HK sample can be done manually to `/tmp`, not in unit tests.

CI/gate tests:

- Add `scripts/utils/periodic_report_narrative_evidence_cards.py` to `LEAK_FILES` in `tools/ci_grep_gates.sh`.
- Add a negative fixture to `tests/utils/test_ci_grep_gates.py` proving the gate rejects `periodic_report_fulltext` / `synthesis_display` references in the new helper file.

Suggested commands:

```bash
python3 -m pytest tests/utils/test_periodic_report_narrative_evidence_cards.py -q
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_product_project_evidence.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

---

## 10. Stop Conditions

Stop and report before coding if implementation appears to require:

- modifying `KnowledgeSynthesizer`;
- changing `scoring_engine.py`, `risk_renderer.py`, or risk scoring;
- registering a new pipeline skill;
- writing to real `knowledge/`, `reports/`, or `data/raw`;
- calling a real LLM;
- fetching annual reports from the network;
- broad refactoring of `periodic_report_fulltext_llm_analysis.py` or `periodic_report_extractor.py`;
- persisting cards as facts or fact candidates.

---

## 11. Open Questions For Claude Review

1. Are the five v1 card types enough, or should `financial_note` be split before implementation?
2. Should `synthesis_eligible` exist in v1 if it is always `False`, or should it be omitted until integration?
3. Is `source_credit=75` appropriate, or should cards use a separate `source_credit`/`confidence` convention from filing facts?
4. Is the proposed excerpt length range too wide for future Knowledge notes?
5. Which existing helper should be reused versus copied lightly to avoid coupling to private functions?

---

## 12. Claude Review Log

### Round 1 Feedback (Claude, 2026-06-21)

Status: Ready
R2 Needed: No
Implementation allowed: Yes — helper-only v1

The design is sound for a helper-only first version. The source-type contract, the
explicit `knowledge_eligible=False` / `synthesis_eligible=False` / `experimental=True`
guardrails, and the narrow scope (no pipeline, no Knowledge writes, no LLM, no network)
are all correct. The five card types cover the high-value narrative gaps that sit
between exact filing facts and fulltext LLM judgment. It does not replace the
fulltext path, and the schema deliberately avoids interpretation fields, which is the
right boundary.

Blockers:

- None. No change to `KnowledgeSynthesizer`, `scoring_engine.py`, `risk_renderer.py`,
  pipeline registration, real `knowledge/` / `reports/` / `data/raw/` writes, LLM
  invocation, or network fetches is required for v1.

Must-fix:

1. **Make the "no interpretation / no claim status" invariant explicit and test it.**
   The card schema currently contains only `source_excerpt`, `title`, `keywords`,
   `confidence` (extraction confidence), and source metadata. That is correct.
   However, the doc should state explicitly that cards must **never** contain fields
   such as `judgment`, `interpretation`, `claim_status`, `verification_status`, or
   `report_eligible`, because those fields are reserved for the LLM fulltext path and
   would blur the material-layer boundary. Add a test that asserts the emitted card
   dict keys are exactly the v1 allowlist.

2. **Extend the test plan to cover the four leakage risks listed in the review brief.**
   The current test plan mentions table fragments and TOC fragments, but it should
   contain explicit, individually assertable tests for:
   - table-only / dense-numeric snippets are rejected (not just "filtered");
   - LLM-style judgment phrases ("这意味着", "说明", "需要跟踪") are rejected unless
     verbatim in the original excerpt;
   - emitted cards never carry `claim_status`, `verification_status`, or any
     `fact_candidate` / `confirmed_fact` marker;
   - the helper returns no file paths, no `knowledge_persisted` flag, and no
     `output_path` field that could be mistaken for a write command.

3. **Pre-register the new helper in `tools/ci_grep_gates.sh` gate (a).**
   `periodic_report_narrative_evidence_cards.py` will be a new file that reads
   evidence packs and emits narrative cards. Although v1 does not write Knowledge,
   future edits could pull `periodic_report_fulltext_*` or `synthesis_display` into it.
   Add the new file to `LEAK_FILES` in `tools/ci_grep_gates.sh` and add a matching
   rejection test in `tests/utils/test_ci_grep_gates.py` before the first code commit,
   mirroring what was done for `periodic_report_filing_fact_note_writer.py`.

Nice-to-have:

- **Keep `financial_note` unsplit in v1, but flag it as a future split candidate.**
  The type is broad (cash flow, impairment, audit key matters, governance dissent,
  subsidy, investment, goodwill, financial assets). That is acceptable for a v1
  helper that stays out of Knowledge, but a future Phase B integration should
  consider splitting `audit_governance_note` from `financial_note` because audit
  key matters and governance dissent are disclosure/governance signals rather than
  management financial explanations. Document this explicitly in §5 or §11.

- **Add a concrete disambiguation example for `operation_update` vs
  `management_market_view`.** Both can read like management discussion. A short
  example in §5 (e.g., “operation_update = 报告期内销量/产能/订单/客户导入变化；
  management_market_view = 行业景气、竞争格局、价格趋势、政策判断”) would help
  the implementer pick the right type and write tighter marker sets.

- **Clarify the ranking / truncation policy for `max_cards_per_type` and
  `max_total_cards`.** Is the cap applied after per-type scoring, or after global
  scoring across all types? Add one sentence in §7 so tests can assert stable
  deterministic ordering under the chosen policy.

- **Consider exposing a `dry_run` / diagnostics-only mode on the public helper.**
  This makes manual smoke tests on real cache cheaper and does not require file
  writes. It is not required for v1 but would reduce friction during the manual
  `/tmp` smoke check mentioned in §9.

Open questions answered:

1. **Five v1 card types?** Yes, they are sufficient for a helper-only seam. Future
   phases may split `financial_note` and possibly add `audit_governance_note`.
2. **`synthesis_eligible` in v1?** Yes, keep the field as an explicit `False`
   guardrail. Its presence signals to downstream consumers that the card is not
   synthesis-ready, which is safer than omitting the field and relying on absence.
3. **`source_credit=75`?** Yes, it is consistent with
   `periodic_report_fulltext_analysis` and `periodic_report_filing_fact`. Narrative
   cards are original text, but they are bounded excerpts, not externally confirmed
   facts, so 75 is the right conservative tier.
4. **Excerpt length 40–500 chars for future Knowledge notes?** Acceptable for v1.
   For future Knowledge persistence the upper bound should be revisited; 500 chars
   is long for a note excerpt and may encourage prose-over-claim drift. A Phase B
   design should cap Knowledge-bound narrative excerpts more tightly.
5. **Reuse vs. copy from existing helpers?** Reuse ideas, not private functions:
   - Use `periodic_report_evidence_pack.py` block `usage` / `id` contracts as the
     input surface; do not import private extraction helpers.
   - Reuse the table-fragment / numeric-debris detection *logic pattern* from
     `periodic_report_product_project_evidence.py` (e.g. digit-ratio and numeric-cell
     counting), but implement it locally so the new helper stays self-contained.
   - Reuse the keyword/category vocabulary from `periodic_report_extractor.py` as a
     reference for marker sets, but do not import `_rank_sentences` or other
     underscore-prefixed functions directly. If a shared primitive is needed, extract
     it to `scripts/lib/` in a separate refactor.

Recommended next step: fold the three must-fix items into the design doc and test
plan, then implement the helper via TDD: red tests for source-type contract,
excerpt-length validation, table/TOC/LLM-phrase filtering, stable idempotency, and
ci-grep gate membership first; then the helper to green. No pipeline registration,
no Knowledge writes, no LLM call, no network fetch.

### Implementation Log (Claude, 2026-06-21)

Helper-only v1 implemented via strict TDD: failing tests written first, then
minimal helper code to green.

Files added:

- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `tests/utils/test_periodic_report_narrative_evidence_cards.py`

Files modified:

- `tools/ci_grep_gates.sh` — added
  `periodic_report_narrative_evidence_cards.py` to gate (a) `LEAK_FILES`.
- `tests/utils/test_ci_grep_gates.py` — added
  `test_ci_grep_gates_rejects_fulltext_leakage_in_narrative_evidence_cards`.
- `docs/agent_workflow/2026-06-21-periodic-report-narrative-evidence-cards-design.md`
  — this implementation log.

Public API:

```python
def build_periodic_report_narrative_evidence_cards(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    evidence_pack: dict,
    max_cards_per_type: int = 3,
    max_total_cards: int = 12,
) -> dict:
    ...
```

Output schema:

- Pack: `schema_version == "periodic_report_narrative_evidence_cards.v1"` plus
  `stock_code`, `stock_name`, `report_year`, `report_type`, `cards[]`,
  `diagnostics[]`.
- Card: `schema_version == "periodic_report_narrative_evidence_card.v1"`,
  `source_type == "periodic_report_narrative_evidence"`, stable deterministic
  `card_id`, `evidence_refs == [source_block_id]`, `source_credit == 75`,
  `knowledge_eligible == False`, `synthesis_eligible == False`,
  `experimental == True`.
- Cards intentionally do **not** contain `judgment`, `interpretation`,
  `claim_status`, `verification_status`, `report_eligible`,
  `knowledge_persisted`, `output_path`, or `planned_path`.

Implementation notes:

- Reads only `evidence_pack["blocks"]`; each block contributes snippets based on
  its `usage` label mapped to one or more v1 card types.
- Snippets are sentence-clause splits whitespace-normalized to 40–500 chars.
- Filtering rejects TOC dot leaders, raw URLs, dense numeric/table-only
  snippets, and LLM causal phrases (`这意味着`, `说明`). `需要跟踪` is rejected
  only when it lacks a concrete customer/product/project context, preserving
  original forward-looking statements that name specific customers or products.
- Ranking: snippets score +1 per matching card-type marker; `confidence` is
  `medium_high` when score ≥ 2, otherwise `medium`. Within each type,
  candidates are kept in original block/snippet order and capped at
  `max_cards_per_type`. Types are then emitted in fixed order
  (`business_model`, `operation_update`, `management_market_view`,
  `rd_product_progress`, `financial_note`) and capped at `max_total_cards`.
- Diagnostics cover `empty_evidence_pack`, `no_candidate_snippets`, and
  `filtered_invalid_excerpt`.

Scope held: no pipeline registration, no `KnowledgeSynthesizer` / synthesis /
scoring / risk / fetcher changes, no writes to `knowledge/`, `reports/`, or
`data/raw`.

Test results:

- `python3 -m pytest tests/utils/test_periodic_report_narrative_evidence_cards.py
  tests/utils/test_ci_grep_gates.py -q` → 20 passed.
- `python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py
  tests/utils/test_periodic_report_product_project_evidence.py -q` → 67 passed.
- `bash tools/ci_grep_gates.sh` → all gates passed.
- `git diff --check` → clean.

Optional smoke check (read-only, `/tmp` preview):

- 中简科技 2025 annual: 30 evidence blocks → 11 cards (`business_model` 3,
  `operation_update` 1, `management_market_view` 3, `rd_product_progress` 1,
  `financial_note` 3).
- 黑芝麻智能 2025 annual (HK): 4 evidence blocks → 0 cards; diagnostic
  `no_candidate_snippets`. HK annual reports do not currently match the A-share
  usage patterns in `periodic_report_evidence_pack.py`, so v1 cards are A-share
  focused. This is acceptable for a helper-only v1 and does not block the seam.
