# Curated External Evidence Cards Phase 2 Design

Date: 2026-06-26

Status: Draft for Round 1 review

## 1. Goal

Allow enriched curated-external evidence cards to improve `## 四、深度分析`
while preserving the existing source boundary:

- no core fact upgrade;
- no Knowledge write;
- no scoring, risk scoring, EV, target price, or final recommendation impact;
- no default report enablement;
- no use of short-summary cards.

The intended role is display-only synthesis context, similar to the existing
periodic-report narrative-card and broker-research digest display paths, but
with stricter source-quality gates because WeChat / curated external materials
are lower-credit and more heterogeneous.

## 2. Current Evidence

Phase 1 and Phase 1.5 preview smokes showed:

| Stock | Baseline card quality | Enriched body quality | Phase 2 suitability |
| --- | --- | --- | --- |
| 圣邦股份 | Product noise, short excerpts | 1 usable enriched card | Not a pilot |
| 黑芝麻智能 | Some useful industry logic | 2 usable enriched cards | Secondary pilot only |
| 中际旭创 | Best topic distribution | 5 usable enriched cards | Primary pilot |
| 寒武纪 | Earnings / commercialization useful | 3 usable enriched cards | Primary pilot |
| 普冉股份 | Few but useful cycle signals | 2 usable enriched cards | Secondary pilot only |

Key lessons:

- The schema, isolation flags, source refs, and excerpt fidelity are stable.
- Short-summary cards are not useful enough for report synthesis.
- Body enrichment raised average excerpt length from about 81 chars to about
  708 chars and eliminated product-roadmap noise in the enriched sample.
- Phase 2 should be tested first on 中际旭创 and 寒武纪; 圣邦股份 should not
  be used as the main quality sample.

## 3. Non-Goals

- Do not connect raw WeChat discovery or candidate JSONL directly to report
  synthesis.
- Do not use non-enriched cards or cards with excerpt length below the quality
  gate.
- Do not write or update `knowledge/`.
- Do not alter `KnowledgeSynthesizer` prompts in this phase unless Round 1
  review finds it unavoidable.
- Do not modify `scoring_engine.py`, `risk_renderer.py`, technical analysis,
  EV, target price, or position advice.
- Do not add new web crawling, Xueqiu detail scraping, Chrome/CDP, or
  Playwright behavior.
- Do not make the curated external section default-visible in every report.

## 4. Proposed Data Flow

```text
enriched evidence cards JSON
  -> strict card reader / eligibility gate
  -> curated external display-only SynthesisItems
  -> existing display synthesis path
  -> post-synthesis citation + overclaim lint
  -> ctx["synthesis_display"] only if lint passes
  -> DeepAnalysisRenderer reads synthesis_display as it already does
```

The canonical baseline remains:

```text
ctx["synthesis"]
ctx["core_facts"]
ctx["synthesis_text"]
ctx["synthesis_sources"]
```

The curated external enhanced path may write only:

```text
ctx["synthesis_display"]
ctx["synthesis_display_sources"]
ctx["synthesis_text_with_curated_external_evidence_cards"]
ctx["curated_external_evidence_cards_status"]
ctx["curated_external_evidence_cards_stats"]
ctx["curated_external_evidence_cards_lint"]
```

## 5. Input Contract

Phase 2 accepts only structured JSON produced by:

```text
scripts/curated_external_evidence_cards_preview.py
```

Required summary-level fields:

- `schema_version == "curated_external_evidence_cards.v1"`
- `cards`: list
- `excerpt_packs`: list
- `wrote_knowledge == false`
- `connected_synthesis == false`

Required card-level fields:

- `schema_version == "periodic_report_narrative_evidence_card.v1"`
- `source_type == "curated_external_analysis_evidence"`
- stable `card_id`
- stable `source_ref`
- non-empty `source_excerpt`
- `source_excerpt_hash`
- `source_block_hash`
- `verification_status == "professional_observation"`
- `quality_action == "preview_only"`
- `knowledge_eligible == false`
- `synthesis_eligible == true`
- `synthesis_display_only == true`
- `scoring_eligible == false`
- `risk_score_eligible == false`

Required excerpt-level field:

- `normalized_substring_verified == true`

If any required field fails, the card is skipped.  If no valid cards remain,
the report stays baseline and records a status, but does not error.

## 6. Quality Gates

### 6.1 Card Gate

Eligible topics:

- `industry_logic`
- `commercialization`
- `earnings_context`
- `cycle_price`
- `certification_policy`
- `capital_market_context`

Default-excluded topic:

- `product_roadmap`

`product_roadmap` may be allowed only in a later phase if the card also
contains customer adoption, design win, certification, volume shipment,
pricing, supply-demand, or earnings context.  Phase 2 should not include it.

Minimum card quality:

- `source_excerpt` length >= 300 chars after whitespace normalization;
- `source_ref` must be URL or local path, not just a source kind;
- `source_credit` must be <= 65 so it cannot be interpreted as high-credit;
- `verification_status` remains `professional_observation`.

### 6.2 Stock-Level Gate

Enable display synthesis only when the stock has enough enriched material:

- at least 3 eligible cards; and
- total eligible excerpt chars >= 1200.

This allows 中际旭创 and 寒武纪 style samples through while preventing 圣邦股份
from rendering a thin display narrative based on one capital-market article.

## 7. Conversion to Synthesis Items

Create a small helper, for example:

```text
scripts/utils/curated_external_evidence_card_synthesis_items.py
```

It should convert eligible cards into `SynthesisItem` objects.

Suggested item fields:

- `source_platform`: `微信公众号精选观察`
- `title`: card title
- `content`: card title + source excerpt + topic/source_kind note
- `url`: card `source_ref` when it is a URL
- `author`: source account when available, otherwise empty
- `publish_time`: source publish date when available
- `extra`:
  - `source_type`: `curated_external_analysis_evidence`
  - `source_credit`: card `source_credit` or `55`
  - `verification_status`: `professional_observation`
  - `claim_status`: `professional_observation`
  - `quality_action`: `preview_only`
  - `knowledge_eligible`: `False`
  - `synthesis_display_only`: `True`
  - `scoring_eligible`: `False`
  - `risk_score_eligible`: `False`
  - `card_id`
  - `source_ref`
  - `source_excerpt_hash`
  - `source_block_hash`
  - `topic`

Ordering should be deterministic:

```text
topic priority, then longer excerpt first, then publish_time descending, then card_id
```

## 8. Synthesis Skill Integration

Add a default-off switch:

```text
include_curated_external_evidence_cards_in_synthesis_display
```

Suggested context keys:

```text
curated_external_evidence_cards_json
curated_external_evidence_cards_max_display_items
curated_external_evidence_cards_min_cards
curated_external_evidence_cards_min_total_excerpt_chars
```

Integration point:

- extend `SynthesisSkill.run()` alongside the existing fulltext,
  periodic narrative-card, and broker-research digest display-only paths;
- append curated external items after existing display items so ordinary source
  numbering remains stable;
- run the existing `dedupe_synthesis_display_items()` on combined items;
- do not write to `ctx["synthesis"]`, `ctx["core_facts"]`,
  `ctx["synthesis_text"]`, or `ctx["synthesis_sources"]`.

If display synthesis fails lint, do not set `ctx["synthesis_display"]` from
curated external material.  Keep baseline synthesis and set:

```text
ctx["curated_external_evidence_cards_status"] = "lint_failed"
```

## 9. Citation Requirements

Each display paragraph that uses curated external evidence must contain numeric
citations that resolve to synthesis citations.

Post-synthesis validation should check:

- every `[^n]` marker in display text has a corresponding citation entry;
- curated external citation metadata includes `source_ref` or URL;
- citation metadata includes `source_type`,
  `verification_status`, and `source_credit`;
- no non-numeric citation markers survive after sanitization.

If unresolved citation markers remain, reject the display synthesis and keep
baseline.

Implementation may reuse the existing citation fill path, but should enrich
curated external citation metadata with `card_id`, `source_ref`,
`source_excerpt_hash`, and `topic` so report references are traceable back to
the card JSON.

## 10. Overclaim Guard

Curated external evidence is not confirmed fact.  The display synthesis must not
write these sources as if they were official confirmation.

Add a deterministic lint pass over `synthesis_display` text when curated
external items are present.

Flag and reject display synthesis when strong-confirmation terms appear in a
sentence whose only citations are curated external display-only sources:

- `确认`
- `证实`
- `已验证`
- `必然`
- `确定`
- `公司披露`
- `公告显示`
- `已落地`
- `锁定`

Allowed wording examples:

- `微信公众号文章观察到...`
- `产业媒体文章提到...`
- `作为外部观察线索...`
- `仍需公告、财报或客户验证...`
- `可能指向...`

If overclaim lint fails, keep baseline and record the failure in
`ctx["curated_external_evidence_cards_lint"]`.

## 11. Rendering

No renderer change should be required for the first implementation because
`DeepAnalysisRenderer` already reads:

```python
ctx.get("synthesis_display") or ctx.get("synthesis")
```

This means the enriched material can influence:

- `## 四、深度分析`
- executive summary display paths that also use `synthesis_display`
- HTML dashboard snippets that use `synthesis_display`

It must not influence:

- `## 三、核心事实基座`
- risk renderer, which reads `ctx["synthesis_text"]`
- Knowledge writer, which reads `ctx["synthesis"]`
- scoring, EV, target price, or final recommendation.

If Round 1 review considers executive summary exposure too broad, Phase 2
should instead introduce a narrower `deep_analysis_display` key and update only
`DeepAnalysisRenderer`.  That is safer but requires renderer changes.

## 12. Failure Modes and Required Tests

### 12.1 Thin material enters synthesis

Failure: one short card causes a generic paragraph.

Tests:

- cards below 300 chars are skipped;
- stock-level min cards / min excerpt chars prevents display synthesis;
- 圣邦-style one-card sample stays baseline.

### 12.2 Display-only leaks into canonical synthesis

Failure: risk scoring or Knowledge sees curated external material.

Tests:

- `ctx["synthesis_text"]` stays byte-for-byte baseline;
- `ctx["synthesis"]` stays baseline;
- `ctx["core_facts"]` stays baseline;
- `ctx["synthesis_text_with_curated_external_evidence_cards"]` contains
  curated material only when enabled.

### 12.3 Low-credit material becomes core fact

Failure: display synthesis extracts curated external claims into `core_facts`.

Tests:

- even if display synthesis result contains `core_facts`, canonical
  `ctx["core_facts"]` remains baseline;
- curated external citation metadata is rejected by
  `is_core_fact_supporting_source()`.

### 12.4 Citation cannot resolve

Failure: report shows `[^n]` but source list lacks metadata.

Tests:

- valid numeric citations resolve to metadata with URL/source_ref;
- unresolved numeric citations reject display synthesis;
- non-numeric markers are sanitized and never rendered.

### 12.5 Overclaiming

Failure: WeChat article is written as `公司公告确认`.

Tests:

- overclaim terms with only curated external citations reject display synthesis;
- cautious wording with `观察到/提到/可能/仍需验证` passes.

### 12.6 Existing display paths regress

Failure: fulltext / periodic narrative cards / broker digest overwrite or hide
curated external display material.

Tests:

- all display-only sources share one `synthesis_display`;
- existing `synthesis_text_with_periodic_report_fulltext`,
  `synthesis_text_with_periodic_narrative_cards`, and
  `synthesis_text_with_broker_research_digest` continue to be set when those
  inputs are enabled;
- add `synthesis_text_with_curated_external_evidence_cards` without changing
  existing keys.

## 13. Allowed Implementation Scope

Allowed files:

- `scripts/utils/report_skills/synthesis_skills.py`
- new helper:
  `scripts/utils/curated_external_evidence_card_synthesis_items.py`
- new helper if needed:
  `scripts/utils/curated_external_display_lint.py`
- tests under `tests/utils/` and `tests/reporter/`
- `tools/ci_grep_gates.sh`
- `tests/utils/test_ci_grep_gates.py`

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/knowledge_skills.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- technical analysis modules
- report entry scripts
- external scraping / WeChat exporter / Xueqiu / Playwright code

## 14. Pilot Plan

Round 1 review should decide whether to use:

1. existing `synthesis_display` for Phase 2; or
2. a narrower `deep_analysis_display` key that affects only
   `DeepAnalysisRenderer`.

If approved, implementation should run focused tests plus two sample smokes:

- 中际旭创 enriched cards: expected to render display deep-analysis material;
- 圣邦股份 enriched cards: expected to stay baseline due to insufficient cards.

Both smokes must confirm:

- no Knowledge writes;
- no scoring/risk changes;
- no `reports/` writes except explicit report trial output if separately
  requested;
- `git status` contains only expected implementation changes.

## 15. Open Questions for Round 1

1. Is reusing `synthesis_display` acceptable, given that executive summary and
   HTML dashboard also read it, or should Phase 2 be limited to
   `DeepAnalysisRenderer` only?
2. Are the stock-level gates (`>=3 cards`, `>=1200 excerpt chars`) strict enough
   to prevent thin materials?
3. Should `capital_market_context` be allowed in Phase 2, or kept preview-only
   unless it includes earnings / financing-use / listing-process substance?
4. Should overclaim lint reject the whole display synthesis, or only fall back
   by removing curated external display items and reusing other display extras?
5. Is source credit `55` appropriate for WeChat enriched evidence cards, or
   should high-quality media accounts be allowed `60-65` while still below the
   high-credit threshold?
