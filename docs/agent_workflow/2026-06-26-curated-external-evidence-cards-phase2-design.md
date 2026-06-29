# Curated External Evidence Cards Phase 2 Design

Date: 2026-06-26

Status: Revised after Round 1 feedback; Round 2 required

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

2026-06-29 update: later validation moved the preferred curated-external
longform path from evidence-card excerpts to full-body source packets,
viewpoint claims, semantic dedupe, and narrative composition.  This document
remains the safety-boundary record for display-only curated external material;
the implementation delta is documented in
`2026-06-29-curated-external-full-body-viewpoint-design-delta.md`.

## 3. Non-Goals

- Do not connect raw WeChat discovery or candidate JSONL directly to report
  synthesis.
- Do not use non-enriched cards or cards with excerpt length below the quality
  gate.
- Do not write or update `knowledge/`.
- Do not alter `KnowledgeSynthesizer` prompts in this phase unless Round 2
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
  -> curated-external deep-analysis display synthesis path
  -> post-synthesis citation + overclaim lint
  -> ctx["deep_analysis_display"] only if lint passes
  -> DeepAnalysisRenderer reads deep_analysis_display before synthesis_display
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
ctx["deep_analysis_display"]
ctx["deep_analysis_display_sources"]
ctx["synthesis_text_with_curated_external_evidence_cards"]
ctx["curated_external_evidence_cards_status"]
ctx["curated_external_evidence_cards_stats"]
ctx["curated_external_evidence_cards_lint"]
```

Important: Phase 2 intentionally does **not** reuse `ctx["synthesis_display"]`.
That key is also consumed by `ExecutiveSummaryRenderer` and
`HtmlDashboardRenderer`; curated external evidence should affect only
`DeepAnalysisRenderer` in this phase.

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

`capital_market_context` requires an additional substance filter.  It is
eligible only when title or excerpt includes at least one substantive term:

- 财报 / 业绩 / 盈利 / 亏损 / 毛利率 / 现金流
- 募资用途 / 研发投入 / 产能建设 / 资本开支
- 上市进展 / 递表 / 聆讯 / 发行 / 招股书
- 行业影响 / 产业链 / 客户 / 订单 / 量产

Reject capital-market cards that are only price movement, market sentiment,
stock chatter, or generic listing-news aggregation.

Minimum card quality:

- `source_excerpt` length >= 300 chars after whitespace normalization;
- Chinese text density gate:
  - at least 80 Chinese characters; and
  - Chinese characters / normalized excerpt chars >= 5%;
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

The helper should preserve all card-level traceability fields in
`SynthesisItem.extra`; `SynthesisSkill._fill_citation_metadata()` must then
forward these fields into `synthesis["citations"]`:

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

`build_stock_report_pipeline()` must expose explicit default-off parameters
instead of relying on unstructured `**kwargs`:

```python
def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
    enable_claim_risk_signals: bool = False,
    enable_source_intake: bool = False,
    enable_periodic_report_fulltext_intake: bool = False,
    include_curated_external_evidence_cards_in_synthesis_display: bool = False,
    curated_external_evidence_cards_json: str = "",
    curated_external_evidence_cards_max_display_items: int = 8,
    curated_external_evidence_cards_min_cards: int = 3,
    curated_external_evidence_cards_min_total_excerpt_chars: int = 1200,
) -> SkillPipeline:
    ...
```

The pipeline should instantiate `SynthesisSkill` with these values or otherwise
make them available to the skill in a typed, testable way.  Runtime
`pipeline_input` may still override paths / gates, but the report entrypoint
must not depend on arbitrary, undocumented kwargs.

Suggested context keys:

```text
curated_external_evidence_cards_json
curated_external_evidence_cards_max_display_items
curated_external_evidence_cards_min_cards
curated_external_evidence_cards_min_total_excerpt_chars
```

Integration point:

- extend `SynthesisSkill.run()` with a separate curated-external
  deep-analysis display branch;
- do not mix curated external items into the existing
  `ctx["synthesis_display"]` branch used by periodic fulltext, periodic
  narrative cards, and broker digest;
- build deep-analysis display synthesis from baseline normal items plus
  curated external eligible items;
- run the existing `dedupe_synthesis_display_items()` on this branch's items;
- do not write to `ctx["synthesis"]`, `ctx["core_facts"]`,
  `ctx["synthesis_text"]`, or `ctx["synthesis_sources"]`.

If display synthesis fails lint, do not set `ctx["deep_analysis_display"]`.
Keep baseline synthesis and set:

```text
ctx["curated_external_evidence_cards_status"] = "lint_failed"
```

Normal report config wiring requires:

- `scripts/utils/stock_reporter.py` reads
  `source_intake_configs.<stock>.curated_external_evidence_cards_synthesis_display`;
- `scripts/utils/report_skills/__init__.py` accepts and passes any new
  pipeline-level wiring needed by `SynthesisSkill`;
- the config subsection supplies the cards JSON path and optional gates:

```yaml
curated_external_evidence_cards_synthesis_display:
  enabled: false
  cards_json: /tmp/zhongjixuchuang_curated_external_body_enriched_evidence_cards.json
  max_display_items: 8
  min_cards: 3
  min_total_excerpt_chars: 1200
```

Suggested mapping behavior in `stock_reporter.py`:

```python
curated_external_cards_cfg = (
    si_cfg.get("curated_external_evidence_cards_synthesis_display", {}) or {}
)
curated_external_cards_enabled = bool(
    source_intake_enabled and curated_external_cards_cfg.get("enabled", False)
)

if curated_external_cards_enabled:
    pipeline_kwargs["include_curated_external_evidence_cards_in_synthesis_display"] = True
    pipeline_kwargs["curated_external_evidence_cards_json"] = (
        curated_external_cards_cfg.get("cards_json", "")
    )
    pipeline_kwargs["curated_external_evidence_cards_max_display_items"] = (
        curated_external_cards_cfg.get("max_display_items", 8)
    )
    pipeline_kwargs["curated_external_evidence_cards_min_cards"] = (
        curated_external_cards_cfg.get("min_cards", 3)
    )
    pipeline_kwargs["curated_external_evidence_cards_min_total_excerpt_chars"] = (
        curated_external_cards_cfg.get("min_total_excerpt_chars", 1200)
    )
```

The same values should be copied into `pipeline_input` if `SynthesisSkill`
reads gates from context.  Tests should lock whichever implementation path is
chosen.

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

Add a deterministic lint pass over `deep_analysis_display` text when curated
external items are present.

The lint must be citation-aware:

- split display text into sentences;
- extract numeric citations from each sentence;
- classify each citation by citation metadata;
- classify a citation as curated external only when
  `source_type == "curated_external_analysis_evidence"` and
  `source_credit <= 65`;
- flag a sentence only when it contains strong-confirmation terms and all
  citations in that sentence are curated-external display-only sources;
- allow strong-confirmation terms when the sentence cites at least one
  high-credit announcement / official source.

Flag when the curated-external-only sentence contains:

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

Update `DeepAnalysisRenderer` to prefer a narrower deep-analysis-only key:

```python
ctx.get("deep_analysis_display") or ctx.get("synthesis_display") or ctx.get("synthesis")
```

This means the enriched material can influence:

- `## 四、深度分析`

It must not influence:

- `## 三、核心事实基座`
- executive summary;
- HTML dashboard snippets;
- risk renderer, which reads `ctx["synthesis_text"]`
- Knowledge writer, which reads `ctx["synthesis"]`
- scoring, EV, target price, or final recommendation.

## 12. Failure Modes and Required Tests

### 12.1 Thin material enters synthesis

Failure: one short card causes a generic paragraph.

Tests:

- cards below 300 chars are skipped;
- cards with too few Chinese characters / too low Chinese density are skipped;
- product-roadmap cards are skipped;
- `capital_market_context` without substance terms is skipped;
- stock-level min cards / min excerpt chars prevents display synthesis;
- 圣邦-style one-card sample stays baseline.

### 12.2 Display-only leaks into canonical synthesis

Failure: risk scoring or Knowledge sees curated external material.

Tests:

- `ctx["synthesis_text"]` stays byte-for-byte baseline;
- `ctx["synthesis"]` stays baseline;
- `ctx["core_facts"]` stays baseline;
- `ctx["synthesis_display"]` stays unchanged by curated external material;
- `ctx["deep_analysis_display"]` is the only curated-external display key;
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
- overclaim terms with high-credit announcement citations pass;
- cautious wording with `观察到/提到/可能/仍需验证` passes.

### 12.6 Existing display paths regress

Failure: fulltext / periodic narrative cards / broker digest are changed by the
curated external deep-analysis display branch.

Tests:

- existing display-only sources still share one `synthesis_display`;
- curated external sources use `deep_analysis_display` only;
- existing `synthesis_text_with_periodic_report_fulltext`,
  `synthesis_text_with_periodic_narrative_cards`, and
  `synthesis_text_with_broker_research_digest` continue to be set when those
  inputs are enabled;
- add `synthesis_text_with_curated_external_evidence_cards` without changing
  existing keys.

## 13. Allowed Implementation Scope

Allowed files:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- new helper:
  `scripts/utils/curated_external_evidence_card_synthesis_items.py`
- new helper if needed:
  `scripts/utils/curated_external_display_lint.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
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

CI gate expectations:

- Add `scripts/utils/curated_external_evidence_card_synthesis_items.py` and
  `scripts/utils/curated_external_display_lint.py` to helper leak checks.
- Add a curated-external leak pattern over core files:
  `curated_external_analysis_evidence`,
  `deep_analysis_display_sources`, and
  `synthesis_text_with_curated_external_evidence_cards` must not appear in:
  - `scripts/utils/reporter/scoring_engine.py`
  - `scripts/utils/reporter/sections/risk_renderer.py`
  - `scripts/utils/report_skills/knowledge_skills.py`
  - `scripts/utils/knowledge_synthesizer.py`

## 14. Pilot Plan

Implementation should run focused tests plus two sample smokes:

- 中际旭创 enriched cards: expected to render display deep-analysis material;
- 圣邦股份 enriched cards: expected to stay baseline due to insufficient cards.

Both smokes must confirm:

- no Knowledge writes;
- no scoring/risk changes;
- no `reports/` writes except explicit report trial output if separately
  requested;
- `git status` contains only expected implementation changes.

## 15. Resolved Round 1 Decisions and Remaining Questions

Resolved:

- Do not reuse `synthesis_display`; use `deep_analysis_display` consumed only
  by `DeepAnalysisRenderer`.
- Expand implementation scope to include config wiring files.
- Keep `product_roadmap` out of Phase 2.
- Keep `capital_market_context` only with a substance filter.

Remaining questions for Round 2:

1. Are the stock-level gates (`>=3 cards`, `>=1200 excerpt chars`) strict enough
   to prevent thin materials?
2. Should overclaim lint failure simply avoid setting `deep_analysis_display`,
   or should it re-run without curated external material if future display
   extras are added to the same branch?
3. Is source credit `55` appropriate for WeChat enriched evidence cards, or
   should high-quality media accounts be allowed `60-65` while still below the
   high-credit threshold?

## Design Delta After Round 1

Accepted:

- Replaced the broad `synthesis_display` integration with a narrower
  `deep_analysis_display` key consumed only by `DeepAnalysisRenderer`.
- Expanded allowed implementation scope to include `report_skills/__init__.py`
  and `stock_reporter.py` so the feature can be configured from normal report
  inputs.
- Added a `capital_market_context` substance filter and explicitly rejected
  price-only / sentiment-only capital-market chatter.
- Added Chinese-character count / density gates to avoid image/PDF placeholder
  bodies passing length checks.
- Required `_fill_citation_metadata()` or an equivalent post-fill step to
  preserve `card_id`, `source_ref`, `source_excerpt_hash`,
  `source_block_hash`, and `topic`.
- Changed overclaim lint to sentence-level and citation-aware.
- Added CI gate expectations for the new curated external helpers.

Rejected:

- No Round 1 finding was rejected.  The design now treats each blocker /
  must-fix as required.

Deferred:

- Updating `credit_usage_rules_text()` is kept as nice-to-have for Phase 2
  unless Round 2 decides prompt wording is required.  The primary guard remains
  metadata gates plus deterministic lint.
- Allowing `product_roadmap` cards remains deferred to a later phase.

R2 required: yes.

Reason:

- The design changed from broad `synthesis_display` reuse to a new
  `deep_analysis_display` integration path.  That is a safer but materially
  different report-rendering boundary and needs a second review before
  implementation.

## Round 1 Feedback

**Status:** Must-fix before task
**R2 Needed:** Yes

### Findings

#### Blocker

1. **Integration wiring is not in the allowed scope.**
   The design proposes a default-off switch and new context keys, but the
   allowed files do not include `scripts/utils/report_skills/__init__.py` or
   `scripts/utils/stock_reporter.py`.  In the current code:
   - `build_stock_report_pipeline()` registers all skills and passes only
     hard-coded flags to `SynthesisSkill`.
   - `stock_reporter.py` reads `source_intake_configs` and maps each display
     extra to a pipeline input key.
   Without modifying these two files, the new feature cannot be enabled from
   the normal report config, which makes Phase 2 unreachable in production.
   *Recommendation:* expand the allowed implementation scope to include these
   two files, or explicitly scope Phase 2 as a manual/CLI-only pilot.

#### Must-fix

2. **`capital_market_context` needs a substance filter or should be excluded.**
   The topic whitelist includes `capital_market_context`, but the only
   enriched 圣邦股份 card in Phase 1.5 was a capital-market article that
   mixed price/news/ listing chatter.  The current card gate only checks
   excerpt length and source credit, not content substance.  Allowing all
   `capital_market_context` cards risks letting price/sentiment/market-noise
   into `## 四、深度分析`.
   *Recommendation:* keep the topic but add a title/content substance gate
   (earnings / financing-use / listing-process / industry-impact terms) and
   reject price-only / sentiment-only / market-chatter cards.

3. **Citation metadata must include card-level traceability fields.**
   The design requires citations to be traceable to `card_id`,
   `source_ref`, `source_excerpt_hash`, and `topic`.  However,
   `SynthesisSkill._fill_citation_metadata()` only copies a fixed set of
   fields: `source`, `author`, `title`, `url`, `date`, `interaction_score`,
   `source_credit`, `source_type`, `verification_status`.  The new helper can
   put card metadata in `SynthesisItem.extra`, but `_fill_citation_metadata`
   will drop it unless the method is updated.
   *Recommendation:* extend `_fill_citation_metadata` to forward the extra
   fields needed for curated external traceability, or add a post-fill
     enrichment step in `SynthesisSkill`.

4. **Overclaim lint must be citation-aware and should not discard unrelated
   display extras.**
   The proposed lint scans the whole display synthesis text.  Because the
   display synthesis also contains baseline items, strong-confirmation terms
   such as `公告显示` can legitimately appear when the sentence cites an
   official announcement.  Rejecting the whole display synthesis when such a
   sentence also cites a curated external source is too coarse and could
   silence high-credit display material (e.g. periodic narrative cards or
   broker digests) that is unrelated to the curated external cards.
   *Recommendation:* implement per-sentence lint that checks whether *all*
   citations in the sentence are curated-external-only; if so, reject only
   the curated external contribution and re-synthesize the remaining display
   extras.  If no other extras exist, fall back to baseline.

5. **Reusing `synthesis_display` exposes curated external material to the
   executive summary and HTML dashboard.**
   `ExecutiveSummaryRenderer` and `HtmlDashboardRenderer` both consume
   `synthesis_display`.  The executive summary runs an LLM extraction that
   produces bullish/bearish thesis points and a one-sentence conclusion,
   which is closer to investment advice than `## 四、深度分析`.
   Although the extraction prompt has credit-tier rules, it does not know
   which citations are curated external, so a WeChat article could be
   misclassified as a confirmed bullish point.
   *Recommendation:* for Phase 2, introduce a narrower `deep_analysis_display`
   key and update only `DeepAnalysisRenderer` to prefer it.  This keeps the
   lower-credit material out of the executive summary and dashboard while
   still influencing the deep-analysis section.

6. **CI grep gates must cover the new helpers.**
   `tools/ci_grep_gates.sh` currently checks a fixed list of helper files.
   The new `curated_external_evidence_card_synthesis_items.py` and
   `curated_external_display_lint.py` are not in `HELPER_LEAK_FILES`, and the
   core-file grep pattern already includes `curated_external_analysis`.
   *Recommendation:* add the new helper files to `HELPER_LEAK_FILES` and add
   a dedicated check that asserts no curated external display-only metadata
   enters `scoring_engine.py`, `risk_renderer.py`, or
   `knowledge_skills.py`.

7. **Card gate should reject image/PDF placeholders that pass length checks.**
   Phase 1.5 showed that some downloaded WeChat articles are image/PDF-based
   and produce bodies with only ~200 Chinese characters despite a long raw
   string.  A length-only gate (>=300 chars) would let these through.
   *Recommendation:* add a Chinese-character density or minimum Chinese-char
   gate (e.g. >=80 Chinese chars and ratio >=5%) before a card is accepted.

#### Nice-to-have

8. Update `credit_usage_rules_text()` in `synthesis_credit.py` to explicitly
   name `curated_external_analysis_evidence` / `微信公众号精选观察` as
   observation-only material, so the LLM prompt is unambiguous.
9. Provide a small utility in `curated_external_display_lint.py` that is
   independently unit-testable, rather than inlining all lint logic in
   `SynthesisSkill`.
10. Add a dedicated smoke test that verifies the full path from enriched card
    JSON to rendered `## 四、深度分析` for 中际旭创 and the thin-material
    fallback for 圣邦股份.

### Required design deltas

- Expand the allowed implementation file list to include:
  - `scripts/utils/report_skills/__init__.py`
  - `scripts/utils/stock_reporter.py`
  - optionally `scripts/utils/synthesis_credit.py` (for prompt wording)
- Change the data-flow target from `ctx["synthesis_display"]` to a new
  `ctx["deep_analysis_display"]` (or write both but keep DeepAnalysisRenderer
  as the only consumer of the new key).
- Add a `capital_market_context` substance gate in the card reader.
- Extend `_fill_citation_metadata` to preserve curated external
  traceability fields (`card_id`, `source_ref`, `source_excerpt_hash`,
  `topic`).
- Rewrite the overclaim lint as a sentence-level, citation-aware filter with
  a fallback that removes only curated external items.
- Update `tools/ci_grep_gates.sh` to include the new helper files and add a
  curated-external leak check.
- Define the exact config subsection that enables Phase 2 (e.g.
  `source_intake_configs.<stock>.curated_external_evidence_cards_synthesis_display`).

### Missing tests

- Config wiring: `stock_reporter.py` passes the new flag and JSON path to
  `build_stock_report_pipeline`, and the pipeline registers the skill.
- Card gate:
  - excerpt <300 chars rejected;
  - `product_roadmap` rejected;
  - `capital_market_context` without substance rejected;
  - image/PDF placeholder with few Chinese chars rejected.
- Stock-level gate: 圣邦-style one-card / <1200-char sample stays baseline.
- Citation metadata contains `card_id`, `source_ref`,
  `source_excerpt_hash`, `topic`.
- Overclaim: mixed-citation sentence with `公告显示` and a baseline
  announcement citation passes; same sentence citing only curated external
  cards is rejected or rewritten.
- Isolation:
  - `ctx["synthesis_text"]` is byte-for-byte baseline;
  - `ctx["synthesis"]` is unchanged;
  - `ctx["core_facts"]` is unchanged;
  - Knowledge persistence writes baseline only;
  - scoring/risk receive `synthesis_text` only and are unaffected.
- Executive summary: does not produce bullish points solely from curated
  external citations when using `deep_analysis_display`.
- Thin material fallback: no `deep_analysis_display` when gates fail.

### Open questions

1. How is the enriched card JSON path supplied to the pipeline?  Should it
   live inside `source_intake_configs.<stock>` or as a standalone config key?
2. On lint failure, should the fallback drop only curated external display
   items and re-synthesize the remaining display extras, or is a full
   baseline fallback acceptable for the pilot?
3. Should the overclaim lint also run on the executive summary extraction
   output if `synthesis_display` is ever reused for curated external later?
4. Should `source_credit` for enriched WeChat cards be fixed at 55, or can
   high-quality industry-media accounts be allowed up to 60-65 while still
   staying below the high-credit threshold?

### Suggested implementation boundary

**Allowed for Phase 2:**
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py` (pipeline registration)
- `scripts/utils/stock_reporter.py` (config wiring)
- new `scripts/utils/curated_external_evidence_card_synthesis_items.py`
- new `scripts/utils/curated_external_display_lint.py` (optional)
- `scripts/utils/reporter/sections/deep_analysis_renderer.py` (if adopting
  the narrower `deep_analysis_display` key)
- tests under `tests/utils/` and `tests/reporter/`
- `tools/ci_grep_gates.sh`
- `tests/utils/test_ci_grep_gates.py`

**Still not allowed:**
- `scripts/utils/knowledge_synthesizer.py` (no prompt change needed for
  Phase 2)
- `scripts/utils/report_skills/knowledge_skills.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- technical analysis / EV / target price modules
- external scraping / WeChat exporter / Xueqiu / Playwright code

## Round 2 Feedback

**Status:** Ready to implement (with required deltas to be locked in PR)
**R3 Needed:** No

### Findings

#### Blocker

None. Round 1 blocker has been resolved at the design level.

#### Must-fix

1. **Config wiring needs concrete signature in `build_stock_report_pipeline`.**
   The design now correctly puts `report_skills/__init__.py` and
   `stock_reporter.py` in the allowed scope, but still describes the wiring
   narratively. Before implementation, add explicit parameters to
   `build_stock_report_pipeline`, for example:
   ```python
   include_curated_external_evidence_cards_in_synthesis_display: bool = False,
   curated_external_evidence_cards_json: str = "",
   curated_external_evidence_cards_max_display_items: int = 8,
   curated_external_evidence_cards_min_cards: int = 3,
   curated_external_evidence_cards_min_total_excerpt_chars: int = 1200,
   ```
   And map them from `source_intake_configs.<stock>.curated_external_evidence_cards_synthesis_display`
   in `stock_reporter.py` exactly like the existing periodic-narrative and
   broker-digest branches. Without this, the feature remains unreachable.

2. **`_fill_citation_metadata()` must forward card traceability fields.**
   The design requires `card_id`, `source_ref`, `source_excerpt_hash`,
   `source_block_hash`, and `topic` in citation metadata, but the current
   `_fill_citation_metadata()` only copies a fixed whitelist. Implementation
   must extend that method (or add a post-fill step) so the rendered reference
   list is traceable back to the card JSON. This is a hard requirement, not a
   nice-to-have.

3. **Overclaim lint must classify curated-external citations by `source_type`,
   not only by `source_platform`.**
   A citation should be considered curated-external display-only when
   `source_type == "curated_external_analysis_evidence"` **and**
   `source_credit <= 65` (or equivalent metadata flag). Relying solely on
   `source_platform == "微信公众号精选观察"` is brittle and could misclassify
   future WeChat-derived sources. This keeps the lint deterministic and
   independent of rendering labels.

4. **`SynthesisSkill.run()` must not write curated external items into
   `ctx["synthesis_display"]`.**
   The narrower `deep_analysis_display` key is the right boundary, but the
   implementation must guarantee that the existing `synthesis_display` branch
   (consumed by `ExecutiveSummaryRenderer` and `HTMLDashboardRenderer`) is
   built from the same baseline + periodic/broker extras as before. Any
   accidental append would reintroduce the Round 1 leak.

5. **`tools/ci_grep_gates.sh` needs a concrete curated-external leak gate.**
   The design says update CI gates but does not specify the check. Add:
   - the two new helper files to `HELPER_LEAK_FILES`;
   - a dedicated gate that greps `scoring_engine.py`, `risk_renderer.py`,
     `knowledge_skills.py`, and `knowledge_synthesizer.py` for
     `curated_external_analysis_evidence`, `deep_analysis_display_sources`,
     and `synthesis_text_with_curated_external_evidence_cards`.

#### Nice-to-have

6. **Update `credit_usage_rules_text()` to name `curated_external_analysis_evidence`.**
   The existing rules already cover “微信公众号” as medium-credit
   observation-only, so this is not required. Adding the explicit source type
   makes the prompt unambiguous and is low risk.

7. **Consider a more surgical lint fallback later.**
   For Phase 2, falling back to baseline `deep_analysis_display` when lint
   fails is acceptable because the key is display-only and separate from
   `synthesis_display`. A future improvement could drop only curated external
   items and re-synthesize the remaining display extras, but that is not a
   Phase 2 blocker.

8. **Add `deep_analysis_display_sources` to the report header only if desired.**
   Currently `_data_sources()` reads `synthesis_sources` (baseline). Leaving
   the new source out of the header keeps the report surface unchanged, which
   is safer for the pilot.

### Required design deltas

- Add the exact `build_stock_report_pipeline` signature and
  `stock_reporter.py` mapping snippet to section 8 (or to the implementation
  PR description).
- In section 7 / 9, explicitly state that `_fill_citation_metadata()` will
  be extended to forward `card_id`, `source_ref`, `source_excerpt_hash`,
  `source_block_hash`, and `topic` into each citation entry.
- In section 10, define curated-external citation classification as
  `source_type == "curated_external_analysis_evidence"` plus
  `source_credit <= 65`.
- In section 13, list `tools/ci_grep_gates.sh` helper-file additions and the
  new curated-external leak pattern.

### Missing tests

- **Config wiring:** `stock_reporter.py` correctly sets the new pipeline
  kwargs from `source_intake_configs` only when `source_intake_enabled` and
  the subsection `enabled` are true.
- **Helper unit tests:** `curated_external_evidence_card_synthesis_items.py`
  gates (topic, substance filter, Chinese density, source_credit cap,
  deterministic ordering).
- **Lint unit tests:** `curated_external_display_lint.py` sentence splitting,
  citation classification, strong-term detection, mixed-citation pass,
  curated-only fail.
- **Isolation tests:** canonical keys `synthesis`, `core_facts`,
  `synthesis_text`, `synthesis_sources`, and `synthesis_display` stay
  byte-for-byte / structurally unchanged when curated external is enabled.
- **Renderer test:** `DeepAnalysisRenderer` prefers `deep_analysis_display`
  over `synthesis_display` and over `synthesis`.
- **End-to-end smoke:** 中际旭创 enriched cards render curated material in
  `## 四、深度分析`; 圣邦股份 one-card sample stays baseline.
- **Executive/HTML leak test:** with `deep_analysis_display` set and
  `synthesis_display` unchanged, bullish/bearish extraction in
  `ExecutiveSummaryRenderer` and `HTMLDashboardRenderer` does not produce
  points solely attributable to curated external citations.

### Implementation task recommendations

- Use TDD for the two new helpers and the lint function; write failing tests
  first, then the minimal code to pass.
- Keep the feature default-off and gated by `source_intake_enabled`.
- Reuse `dedupe_synthesis_display_items()` for the new branch, but verify
  that deduplication does not drop traceability fields needed for citation
  metadata.
- In `_fill_citation_metadata()`, place card traceability fields at the
  citation entry top level (not nested under `extra`) so
  `DeepAnalysisRenderer` and the lint pass can access them directly.
- Run `node tests/run-all.js` and `npx markdownlint-cli '**/*.md' --ignore
  node_modules` before committing.

## Design Delta After Round 2

Accepted:

- Locked the `build_stock_report_pipeline()` signature with explicit
  default-off curated external parameters.
- Added a concrete `stock_reporter.py` mapping sketch for
  `source_intake_configs.<stock>.curated_external_evidence_cards_synthesis_display`.
- Defined curated-external citation classification for lint as
  `source_type == "curated_external_analysis_evidence"` plus
  `source_credit <= 65`.
- Added concrete CI leak patterns and helper files for
  `tools/ci_grep_gates.sh`.
- Kept `KnowledgeSynthesizer` prompt unchanged for Phase 2.

Rejected:

- No Round 2 finding was rejected.
- The generic suggestion to run `node tests/run-all.js` and markdownlint is not
  adopted for this Python report repository.  Phase 2 verification should use
  focused `pytest`, `compileall`, `tools/ci_grep_gates.sh`, and
  `git diff --check`.

Deferred:

- More surgical lint fallback that re-synthesizes after dropping only curated
  external items is deferred.  Phase 2 will use the simpler safe behavior:
  leave `deep_analysis_display` unset on lint failure.
- Adding `deep_analysis_display_sources` to the report header is deferred to
  avoid expanding the visible report surface during the pilot.

R3 required: no.

Reason:

- Round 2 found no design blocker.  Remaining requirements are implementation
  details now locked by this delta and should be enforced through tests.
