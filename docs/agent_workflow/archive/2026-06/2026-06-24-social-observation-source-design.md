# Social Observation Source Design

Date: 2026-06-24

Purpose: record the current Agent-Reach / low-risk social-media smoke status and keep the source boundary explicit before any future implementation.

## Current Smoke Result

Claude Code ran a read-only smoke and wrote `/tmp/social_observation_smoke.md`.

Repository side effects:

- no repository code changes
- no `knowledge/`, `data/raw/`, or `reports/` writes
- no Xueqiu detail-page fetches
- no Chrome/CDP automation
- no LLM calls

Current dirty files were pre-existing work from Source Intake news changes:

- `config/stocks.json`
- `scripts/utils/a_stock_source_intake.py`
- `tests/utils/test_a_stock_source_intake.py`

## Channel Status

| Channel | Status | Notes |
| --- | --- | --- |
| Agent-Reach CLI | Not usable | Binary exists, but `agent-reach doctor` fails with `ModuleNotFoundError: agent_reach.cli`. Do not depend on the wrapper CLI for now. |
| V2EX | Usable but sparse | Public API works. Hot-topic sample had 2 keyword hits out of 10, but quality was mixed and not necessarily investment-specific. |
| Reddit | Not tested | `rdt` is not installed. Per the smoke boundary, no tool installation was attempted. |
| Jina Reader | Usable | Tested URLs returned HTTP 200 and clean Markdown. It can read public pages and some report landing pages. |
| YouTube subtitles | Usable when captions exist | `yt-dlp` can list automatic captions for the tested YouTube video. |
| Bilibili subtitles | Partially usable | `yt-dlp` can parse the page, but the tested video did not expose a usable subtitle list. |

## Video Source Follow-up

2026-06-26 Bilibili / YouTube video smoke:

- `yt-dlp` subtitle extraction failed in the current environment:
  - Bilibili: 5 / 5 tested videos returned HTTP 412.
  - YouTube fallback: 3 / 3 tested videos returned HTTP 429.
- Bilibili candidate discovery was possible after installing the PyPI package
  `bilibili-cli==0.6.2` locally for smoke only.  The command is `bili`; the
  npm package name `bili-cli` was not available.
- The low-risk Bilibili discovery result produced 82 raw candidates for
  Shengbang / analog-chip queries.  A stricter second pass kept only:
  - 3 `transcript_candidate` items;
  - 1 `watchlist` item;
  - 12 `evergreen_background` items;
  - 66 `drop` items.
- Only 2 of the 3 transcript candidates were within the last 180 days.  The
  strongest candidate was a single Shengbang-specific video from 2026-05-17.

Decision:

- Do not make Bilibili an automatic source.
- Do not add broad video search to the report pipeline.
- Do not depend on `bilibili-cli` as a project dependency.
- Keep the generic explicit-URL `curated_external_video_subtitle_preview.py`
  helper as a preview-only utility for hand-picked videos.
- Treat Bilibili videos as opportunistic material only: a user or reviewer may
  provide a small URL list, then the preview tool may attempt subtitle extraction
  without writing Knowledge, synthesis, scoring, risk, or report inputs.
- If a high-value video lacks usable subtitles, decide in a separate task
  whether to do manual review or local ASR.  Do not silently fall back to logged
  in browser automation, cookies, video download, or comment scraping.

## WeChat Targeted Discovery Follow-up

2026-06-26 WeChat 180-day targeted discovery smokes covered six semiconductor
stocks:

| Stock | 180-day pattern | Useful WeChat categories |
| --- | --- | --- |
| 圣邦股份 | Low analysis density, high product noise | product / event signals; one weak capital-market context item |
| 黑芝麻智能 | Event-driven with some analysis | high-quality analysis; commercialization / certification / cooperation signals |
| 英集芯 | Low analysis density, product and price-cycle signal | product / event signals; industry cycle / price signal |
| 中际旭创 | High analysis density and supply-chain depth | high-quality analysis; customer/order; capacity/supply chain; earnings context; capital-market context |
| 寒武纪 | High attention, earnings and capital-market driven | earnings context; capital-market context; weak capacity/supply-chain mention |
| 普冉股份 | Cycle and product mixed | industry cycle / price signal; one product-depth article |

Design decision:

- Do not model WeChat as only `wechat_product_signal`.
- Preserve the source as preview-only material, but classify it into typed
  groups:
  - `high_quality_analysis`
  - `customer_order_or_design_win`
  - `capacity_supply_chain_signal`
  - `industry_cycle_price_signal`
  - `earnings_financial_context`
  - `certification_policy_standard`
  - `product_or_event_signal`
  - `capital_market_context`
- Do not set a fixed display cap for `high_quality_analysis` or
  `customer_order_or_design_win`.  These are rare and high-value enough that
  quality filtering and dedupe should be the limiting mechanisms.
- Keep display caps for lower-priority categories such as product releases,
  generic event signals, financial headlines, price-cycle notes, and
  capital-market context.
- Keep all WeChat items preview-only:
  - `quality_action`: `preview_only`
  - `knowledge_eligible`: `false`
  - `synthesis_eligible`: `false`
  - `scoring_eligible`: `false`
  - `risk_score_eligible`: `false`

Failure modes and tests:

- Targeted smoke JSONL may use `classification` rather than the older
  `action=keep/product_signal` format.  Candidate discovery must preserve the
  classification as `wechat_signal_category`.
- A renderer-level display cap must not hide high-quality analysis or
  commercialization events.  Focused renderer tests should verify that these
  groups remain fully visible while lower-priority product/event items are
  capped.
- The report must continue to avoid Knowledge, scoring, risk, and canonical
  synthesis paths for all WeChat-derived materials.

2026-06-26 implementation close-out:

- `scripts/wechat_targeted_discovery_preview.py` is the stable preview-only
  WeChat targeted discovery entrypoint.  It writes Markdown / JSONL to `/tmp`
  by default, can optionally download a small number of bodies, and keeps all
  retained items at preview-only eligibility.
- `scripts/curated_external_section_preview.py` renders a candidate JSONL into
  the same `精选外部观察（Preview）` section shape used by the report renderer.
  This replaces one-off `/tmp/write_curated_section.py` smoke helpers.
- Latest Shengbang smoke with the committed classifier fix changed the
  "涨价 + 招股 / 上市" headline from `industry_cycle_price_signal` to
  `capital_market_context`, which better reflects its content.
- Black Sesame and Shengbang section previews render successfully from candidate
  JSONL without writing Knowledge, reports, raw data, synthesis, scoring, or
  risk inputs.

Product decision:

- Keep WeChat targeted discovery as a **manual / optional external materials
  pack**.  Do not enable it as a default report section for every stock.
- Reasons:
  - Shengbang-style names can be dominated by product releases and product
    compilations, which dilute the core report if shown by default.
  - Event-driven names such as Black Sesame can produce useful commercial or
    certification signals, but those still require human review before they
    should influence any analysis.
  - The source remains high-duplication and preview-only by design.
- A reviewer may generate the pack before a report run, inspect the section
  preview, and then decide manually whether to include the materials as display
  context.  It must not silently promote to Knowledge, canonical synthesis,
  scoring, risk, or final recommendation logic.

## Longer-Term Synthesis Quality Plan

The current report synthesis path can continue to work, but adding more
external sources directly to a `source -> prompt -> article` flow will make the
system harder to audit.  The preferred long-term direction is:

`source -> evidence cards + excerpt packs -> topic buckets -> claim candidates -> cited narrative`

Rationale:

- Keep the research process separate from the writing process.
- Prevent low-credit sources such as WeChat, forums, market commentary, or
  syndicated media from being written as confirmed facts.
- Preserve traceability from each written claim back to `source_ref` / URL /
  file path.
- Deduplicate syndicated articles and repeated claims before the LLM sees them,
  so repeated reposts are not mistaken for independent confirmation.
- Preserve conflicts and uncertainty as explicit multi-source disagreement
  rather than smoothing them into vague prose.

Important constraint:

- Evidence cards must not replace the underlying material.  Each useful card
  should keep an attached excerpt pack with enough source detail for the LLM to
  write a non-generic paragraph.  A card is the index and control layer; the
  excerpt pack is the material layer.

Phase 1 / Phase 2 hard gates from the read-only review:

- **Schema boundary**: evidence cards should reuse the existing
  `periodic_report_narrative_evidence_card.v1` shape where practical:
  `card_id`, `evidence_refs`, `source_excerpt_hash`, `source_credit`,
  `verification_status`, `synthesis_display_only`, and source metadata.  For
  external sources, `source_ref` must be a stable canonical URL or local file
  path plus hash, not a vague source kind.
- **Excerpt fidelity**: card generation must not use an LLM to rewrite source
  excerpts.  `source_excerpt` should be deterministic source slices.  A
  fidelity check should verify that each normalized excerpt is a substring of
  the normalized source content.
- **Excerpt budget**: excerpt packs need explicit length and count limits so
  the preview can reveal when a topic would exceed a practical prompt budget.
- **Cross-platform dedupe before claims**: run canonical URL normalization and
  content fingerprinting before topic bucketing and claim extraction.  Reposts
  should merge into one claim candidate while preserving multiple
  `source_files` / `source_platforms`.
- **Display-only isolation**: any item with `synthesis_display_only=true` must
  also keep `knowledge_eligible=false`, `scoring_eligible=false`, and
  `risk_score_eligible=false`.  Add tests or CI gates so display-only sources
  cannot enter scoring, risk, or final recommendation paths.
- **Citation resolvability**: every generated narrative paragraph in Phase 2
  must bind to at least one resolvable evidence reference.  Renderers should
  surface unresolved references visibly instead of silently dropping them.
- **Observation wording guard**: prompts and post-processing should prevent
  low-credit `professional_observation` / `market_observation` material from
  being written as confirmed facts.  Add a lint pass for overclaiming terms such
  as "确认", "确定", "已经证实", or "必将" when they rely only on
  display-only evidence.

Suggested phased rollout:

1. **Phase 1: preview only**
   - Build `curated_external_to_evidence_cards_preview`.
   - Input: curated external synthesis display items.
   - Output: JSON / Markdown with short evidence cards plus attached excerpts.
   - Do not connect to report generation, Knowledge, scoring, risk, or final
     recommendation.
   - Goal: verify that the cards preserve enough detail and do not over-compress
     the source.

2. **Phase 2: display-only deep-analysis input**
   - Allow evidence cards / excerpts to contribute to `## 四、深度分析`.
   - Keep `knowledge_eligible=false`, `synthesis_display_only=true`,
     `scoring_eligible=false`, and `risk_score_eligible=false`.
   - Require paragraph-level citations to card IDs / source refs.
   - Do not allow these materials into the core fact base, scoring, risk, or
     final recommendation.

3. **Phase 3: migrate existing non-official sources gradually**
   - Move Zhihu, broker research, iwencai industry research, and curated external
     materials toward the same card / excerpt interface.
   - Keep official announcements and periodic reports as the only default
     confirmed-fact sources.
   - Use card grouping to improve dedupe and contradiction handling.

4. **Phase 4: claim-level fact upgrades**
   - Only promote a claim toward core facts when an official / high-credit source
     independently verifies it.
   - Display-only cards may seed claims, but cannot confirm claims by themselves.

Expected impact:

- High impact on source boundary quality, citation traceability, and prevention
  of overclaiming.

2026-06-29 design delta:

- Curated external longform sources now use the full-body viewpoint digest path
  as the preferred primary material layer.  Evidence cards remain useful as
  preview/audit/fallback material, but WeChat longform quality improved only
  after moving to source packets, LLM multipass claim extraction, quote/hash
  validation, semantic dedupe, and a cited narrative composer.  See
  `2026-06-29-curated-external-full-body-viewpoint-design-delta.md`.
- Medium impact on depth of analysis, depending on source quality and excerpt
  richness.
- No direct short-term impact on scoring or risk, by design.

2026-06-26 Phase 1 preview implementation note:

- `scripts/curated_external_evidence_cards_preview.py` and
  `scripts/utils/curated_external_evidence_cards.py` implement the preview-only
  card / excerpt step for curated external synthesis display items.
- The tool writes Markdown / JSON to `/tmp` by default and does not connect to
  report generation, Knowledge, canonical synthesis, scoring, risk, or final
  recommendation.
- The preview enforces deterministic source excerpts, normalized-substring
  fidelity checks, canonical URL / content-fingerprint dedupe, and display-only
  isolation fields.
- Smoke outputs for Black Sesame and Shengbang confirmed card generation and
  excerpt fidelity; Shengbang still has thin excerpts because the upstream
  WeChat candidate content is mostly product-signal summaries.

## Boundary

Social observation v1 is not a Knowledge source.

If implemented later, items must be material/display only:

- `source_type`: `social_observation`
- `source_credit`: 45-55 depending on channel
- `verification_status`: `market_discussion` or `secondary_source`
- `knowledge_eligible`: `false`
- `report_eligible`: `true`
- `scoring_eligible`: `false`
- `risk_score_eligible`: `false`

Do not feed social observations into:

- confirmed facts
- fact candidates
- scoring
- risk scoring
- final recommendation logic
- persistent Knowledge notes by default

## Recommended Next Step

Do not implement a broad Agent-Reach wrapper yet.

If this area is reopened, the preferred path is **curated external analysis**, not
open-ended social crawling.  The useful material is likely to come from a small
set of high-quality long-form URLs or exported files, not from broad platform
feeds.

Recommended v1 shape:

1. A preview-only helper tentatively named `curated_external_analysis_pack`.
2. Inputs:
   - user/Claude-curated public article URLs read through Jina Reader;
   - Bilibili / YouTube video URLs with subtitles extracted through `yt-dlp`;
   - local files exported from WeChat article tooling, such as Markdown / HTML /
     text exports;
   - local manually collected industry or company analysis files dropped into a
     per-stock folder.
3. Output:
   - `/tmp/...preview.md` first;
   - optional display-only synthesis items later, after manual review.
4. Metadata:
   - `source_type`: `curated_social_analysis` or `external_analysis`;
   - `source_credit`: 45-65 depending on channel and source quality;
   - `verification_status`: `professional_analysis`, `secondary_source`, or
     `market_discussion`;
   - `knowledge_eligible`: `false` by default;
   - `scoring_eligible`: `false`;
   - `risk_score_eligible`: `false`.

Use this source as synthesis/display material only.  Do not promote it to core
facts or scoring inputs unless an independent high-credit official source later
confirms the claim.

Concrete source guidance:

- Jina Reader: keep for public industry articles, company专题, 36Kr /
  Eastmoney / 同花顺 readable pages, and report landing pages.  This is the
  default low-friction reader.
- Bilibili / YouTube: keep only for explicitly supplied deep-video URLs.  Do not
  run broad video search in v1.
- WeChat articles: evaluate `wechat-article/wechat-article-exporter` as an
  external acquisition tool.  The report system should read exported local
  `md` / `html` / `txt` files rather than logging into WeChat or scraping
  directly.  The exporter appears suitable for stable official-account article
  collection, but credentials / read-count / comment capture must remain outside
  the report pipeline.
- Zhihu: already covered by the existing API path; do not duplicate it here.
- Xueqiu: already covered by the existing Playwright/list-cache path; any detail
  fetch remains subject to the existing logged-in CDP and rate-limit rules.
- Xiaohongshu: potentially valuable for consumer hardware / robotics / channel
  feedback, but not a v1 pipeline source.  Anti-bot controls, `xsec_token`
  coupling, image-heavy posts, OCR needs, and comment quality make it a separate
  smoke-only task.  If tested, use hand-picked note URLs and produce preview-only
  output.
- V2EX / Eastmoney guba / general forums: useful only as weak market discussion
  or claim-risk seed material.  Do not treat them as deep-analysis sources.

Keep Reddit, Bilibili active crawling, Twitter/X, Xiaohongshu, Weibo login
flows, and Xueqiu detail pages out of the main v1 path.

## Stop Conditions

Stop and ask for a new task boundary if any future social observation work requires:

- login cookies
- installed browser automation
- Xueqiu detail-page scraping
- Twitter/X authenticated search
- Xiaohongshu xsec-token handling
- Reddit tool installation
- writing Knowledge notes
- modifying synthesis, scoring, risk, or recommendation logic
