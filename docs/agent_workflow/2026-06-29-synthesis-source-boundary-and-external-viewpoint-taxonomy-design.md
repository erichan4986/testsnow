# Synthesis Source Boundary And External Viewpoint Taxonomy Design

Date: 2026-06-29

Status: Implemented preview / launch acceptance passed for curated external narrative 4.4

## 1. Goal

Separate the report's deep-analysis section into two clearer layers:

1. `4.1-4.3` as the canonical research layer, grounded mainly in high /
   medium-high credit materials such as announcements, annual reports,
   quarterly reports, broker research, industry research, official pages, and
   structured data.
2. `4.4` as the external-observation layer, containing WeChat / Zhihu /
   Xueqiu / social or industry-media viewpoints as display-only, cited
   observations and watch variables.

The goal is not to shrink the report.  It is to make the source boundary
legible: formal materials support the main analysis; social and external
longform materials explain what the market and industry are debating.

## 2. Current State

Already implemented:

- Generic entry `scripts/run_stock_report.py --stock <name>`.
- A-share `source_intake` can feed canonical synthesis.
- 中际旭创 and 圣邦股份 formal runs now generate meaningful `4.1-4.3`
  from source-intake materials.
- Curated external full-body WeChat / industry-media longform materials can
  produce cached viewpoint digest / narrative JSON.
- Cached curated external narrative renders in `4.4` through
  `ctx["deep_analysis_display"]`.
- Curated external material is display-only and isolated from Knowledge,
  scoring, risk scoring, target price, and final recommendation.
- 中际旭创 and 黑芝麻智能 now render cached viewpoint narratives as flat,
  cited `4.4` narrative sections.
- `4.4` narrative output has deterministic safety gates for claim refs,
  model/product tokens, quantitative expressions, overclaim wording, and
  display-only isolation.

Still legacy / mixed:

- `SynthesisSkill._build_synthesis_items()` still consumes `keep_posts`
  from Xueqiu / Eastmoney community-style fallback.
- It also consumes `zhihu.report_items`.
- Therefore `4.1-4.3` can still mix formal research with lower-credit
  social or Q&A material.
- Xueqiu / Zhihu social source-packet preview exists for `/tmp` digest
  generation, but ordinary report runtime still only reads cached narrative
  JSON; it does not run social extraction or narrative composition live.

## 3. Non-Goals

- Do not modify scoring, risk scoring, EV, target price, technical analysis,
  or final recommendation rules in this work.
- Do not write social or curated external materials to `knowledge/`.
- Do not run WeChat / Zhihu / Xueqiu scraping inside ordinary report runtime.
- Do not feed raw full-body articles directly into the report renderer.
- Do not remove existing single-stock entry scripts.
- Do not make `4.4` a dumping ground for every social item.
- Do not allow `4.4` to support core facts or structured risk signals.

## 4. Source Policy

### 4.1-4.3 Canonical Research Layer

Allowed source families by default:

- exchange / official announcements;
- annual reports, quarterly reports, investor relations activity records;
- official company pages;
- broker research reports;
- industry research reports;
- mainstream media / policy / industry news with source-credit metadata;
- structured market / financial / fund-flow data already used by the report.

Allowed source types currently expected in code:

- `exchange_announcement`
- `broker_research`
- `industry_research`
- `mainstream_media`
- future high-credit annual-report fact packs, if their schema explicitly
  marks them as canonical and not display-only.

Default excluded source families:

- Xueqiu / Guba / Eastmoney community posts;
- Zhihu answers / articles / search results;
- WeChat / curated external longform viewpoints;
- Agent-Reach external web observations unless promoted by explicit
  high-credit metadata and source policy review;
- periodic report excerpt / fulltext display-only analysis paths;
- any item with `synthesis_display_only == true`;
- any item with `quality_action == "preview_only"`;
- any item with `knowledge_eligible == false` and `report_eligible == false`.

### Cross-Verified Social Viewpoint Exception

Social or Q&A material may influence `4.1-4.3` only as a topic-discovery
signal, not as the primary citation.

Allowed pattern:

```text
Social source raises question Q.
Announcement / broker research / industry research also contains evidence E.
4.1-4.3 writes the formal claim using E as the citation.
4.4 may separately explain that external discussion is watching Q.
```

Disallowed pattern:

```text
Xueqiu / Zhihu / WeChat says Q.
4.1-4.3 cites that social source directly as if Q is a confirmed fact.
```

## 5. 4.4 External Viewpoint Taxonomy

The taxonomy remains useful for digest extraction, fallback grouping, and
quality diagnostics.  It is not the final renderer shape for validated
narratives.

For cached narrative JSON (`_curated_external_narrative == true`), the report
renders the LLM-planned paragraphs in order as a flat `4.4` narrative.

For older digest/card addendum data without a validated narrative, the
renderer may still use grouped topic headings as a fallback.  Empty headings
must not render.

Canonical topic keys:

| Topic key | Chinese heading | Purpose |
| --- | --- | --- |
| `tech_route` | 产业链与技术路线分歧 | CPO/LPO/NPO/XPO, silicon photonics, 800G/1.6T, product-generation disputes |
| `order_capacity_delivery` | 订单、产能与交付节奏 | customer demand, order rumors, delivery plans, capacity bottlenecks, prepayments |
| `financial_quality` | 业绩质量与财务可持续性争议 | revenue quality, margin, expense ratio, cash flow, inventory, losses/profit inflection |
| `competition_commercialization` | 竞争格局与商业化窗口 | competitor comparison, design wins, benchmark models, adoption window, commercialization |
| `market_expectation` | 资本市场预期与情绪温度 | valuation crowding, institutional consensus, expectation gap, trading narrative |
| `risk_rumor_rebuttal` | 风险传言与反证线索 | sanctions, entity lists, order cuts, customer-loss rumors, company rebuttals |

Mapping rules:

- A claim may have one primary topic and optional secondary tags.
- Digest fallback rendering may group by primary topic to avoid duplication.
- Validated narrative rendering preserves the narrative composer order instead
  of regrouping paragraphs.
- If the extractor emits old topic names, a deterministic mapper should
  normalize them to these six keys.
- Unmapped topics should fall into `market_expectation` only if they are
  market-expectation observations; otherwise the claim should be dropped or
  marked `unmapped_topic`.

## 6. 4.4 Narrative Shape

Validated narrative `4.4` should render as:

```markdown
### 4.4 精选外部观察（Preview）

> 精选外部材料仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或最终建议。

**外部主线标题 A**
观点 -> 证据引用 -> 推导 -> 对公司基本面/上下游的观察。

**外部主线标题 B**
观点 -> 证据引用 -> 推导 -> 需要继续验证的变量。

**本节引用来源：**
- [^n] 来源 | 作者 | 标题 | URL
```

Rendering limits:

- 2-4 narrative paragraphs per stock by default.
- Each paragraph must cite at least one claim/source.
- Same-source citations can repeat when separate claims need traceability; a
  future polish can merge local source rows for readability.
- The section must not include scoring, target price, buy/sell advice, or
  final recommendation language.

`4.4` should not become a bullet dump unless the narrative composer fails and
the fallback path is explicitly marked as preview / degraded.

Additional safety gates:

- `claim_refs` must resolve to known claims.  A unique tail-hash may be
  repaired to the full `claim_id`; ambiguous tail-hashes fail closed.
- Product/model-like tokens in generated text must appear in the referenced
  claims or stock name.
- Quantitative expressions, including ratios, percentages, ranges, units, and
  large standalone numbers, must appear in the referenced claims.
- Overclaim lint runs per paragraph; unsafe paragraphs are dropped while safe
  paragraphs remain.  If all paragraphs are dropped, `4.4` does not render.

## 7. Runtime Data Flow

Preferred longform path:

```text
full-body source packet
  -> LLM multipass viewpoint extraction
  -> quote/hash validation
  -> novelty + duplicate gates
  -> topic normalization
  -> cached viewpoint digest JSON
  -> narrative composer
  -> cached viewpoint narrative JSON
  -> report runtime reads cached narrative only
  -> DeepAnalysisRenderer renders flat 4.4 narrative only
```

Ordinary report runtime should not perform the extraction or narrative
composition LLM calls.  It should only read precomputed JSON files referenced
by per-stock config.

## 8. Rollout Plan

### Phase A: Narrative Renderer Preview

- Render validated narrative JSON as flat 4.4 narrative paragraphs.
- Keep taxonomy grouped rendering only for digest/card fallback paths.
- Validate on 中际旭创 and 黑芝麻智能 cached narratives.
- 圣邦股份 remains a negative control: no narrative file means no `4.4`.

Status: complete.  黑芝麻智能 and 中际旭创 passed formal report validation on
2026-06-30; 圣邦股份 was previously validated as the no-4.4 negative control.

### Phase B: Canonical Source Policy Preview

- Add a source-policy switch, initially preview / opt-in:
  - `legacy_mixed`: current behavior.
  - `formal_first`: exclude Xueqiu / Zhihu / WeChat from canonical synthesis.
- Run 中际旭创 and 圣邦股份 with `formal_first`.
- Compare `4.1-4.3` length, citations, and quality against current reports.

### Phase C: Cross-Verified Social Bridge

- Add a separate pre-synthesis bridge that can convert social observations
  into formal-source-backed themes only when a formal source supports the same
  claim.
- The resulting `4.1-4.3` citation must point to the formal source, not to
  the social source.
- The original social observation remains visible only in `4.4`.

### Phase D: Default Policy Decision

Make `formal_first` the default only after:

- 中际旭创 and 圣邦股份 both preserve substantive `4.1-4.3`;
- 黑芝麻智能 still has useful main analysis via official / annual / external
  non-social sources or an explicit HK source-intake path;
- reports without enough formal sources fail gracefully with a clear
  "formal materials insufficient" note rather than silently reverting to
  social-only synthesis.

## 9. Testing And Acceptance

Unit tests:

- `SynthesisSkill` excludes Xueqiu / Zhihu / WeChat from canonical synthesis
  when `formal_first` is enabled.
- `SynthesisSkill` still includes `exchange_announcement`,
  `broker_research`, `industry_research`, and `mainstream_media`.
- Display-only items never enter canonical synthesis even if present in
  `external_evidence_keep_items`.
- Topic normalization maps old curated-external topics to the six canonical
  topic keys.
- Renderer suppresses empty 4.4 topic groups.
- Renderer keeps validated narrative paragraphs flat and in planned order.
- Renderer preserves citations and local source list.
- Narrative validator rejects unsupported model/product tokens and unsupported
  quantitative expressions.

Report smokes:

- 中际旭创:
  - `4.1-4.3` have formal-source citations and no degradation template.
  - `4.4` renders a flat validated narrative with no `4.4.1/4.4.2/4.4.3`
    taxonomy subheadings.
- 黑芝麻智能:
  - `4.4` renders the four validated social/external narrative paragraphs.
  - 4.4 remains display-only.
- 圣邦股份:
  - `4.1-4.3` have formal-source citations.
  - `4.4` does not render unless a validated narrative JSON is configured.

Quality gates:

- `tools/ci_grep_gates.sh` must continue to pass.
- `check_report_quality.py` should not report missing 4.1-4.3 content for
  the pilot stocks.
- Curated external tokens must not appear in executive summary, scoring,
  risk scoring, target price, or final recommendation.

## 10. Failure Modes

| Failure mode | Symptom | Test / detection |
| --- | --- | --- |
| 4.1-4.3 become too thin after social exclusion | degradation template or very short deep analysis | formal-first report smoke on 中际旭创 / 圣邦股份 |
| social source leaks into canonical synthesis | `雪球` / `知乎` / `微信公众号` citations appear in 4.1-4.3 | source-policy unit test and report grep |
| 4.4 becomes a dumping ground | many unrelated bullets or weak narrative flow | renderer snapshot / smoke review |
| 4.4 empty headings render | headings with no paragraphs | renderer unit test |
| narrative renderer re-groups planned paragraphs | `4.4.1/4.4.2/4.4.3` appears for `_curated_external_narrative` | renderer unit test and report smoke |
| LLM invents product/model token | unsupported model such as `C1236` appears | narrative validator unit test |
| LLM invents ratio or numeric comparison | unsupported `1/4` / percentage / unit number appears | narrative validator unit test |
| curated external affects scoring/risk | curated tokens appear outside 4.4 | CI gate c and report grep |
| cross-verified bridge cites social directly | 4.1-4.3 citation points to social item | bridge unit test |
| extractor topic drift | unknown topics dominate | topic-normalization stats / unmapped-topic test |
| formal source not enough for HK stocks | 黑芝麻 4.1-4.3 degrade | HK-specific smoke and source-intake gap report |

## 11. Open Questions For Review

1. Should `formal_first` be opt-in per stock first, or should we immediately
   make it default for A-shares?
2. Should broker research be considered canonical for 4.1-4.3, or should it
   be separated from announcements / annual reports as "professional
   observation" inside the same section?
3. Should Xueqiu / Zhihu get their own 4.4 source-packet pipeline, or should
   they reuse the curated external viewpoint schema only after full-body
   extraction quality is proven?
4. For stocks with weak formal coverage, is it better to show a short
   formal-source section plus a richer 4.4, or temporarily keep legacy mixed
   synthesis until enough formal material is available?

## 12. Round 1 Review Delta

Claude Round 1 status: `ready_to_implement_preview`.

Accepted:

- Phase A proceeded as a narrative renderer preview.  Earlier grouped taxonomy
  rendering remains as a fallback, but the final validated-narrative path is
  flat and preserves the composer-planned paragraph order.
- Phase B can proceed now: add `formal_first` only as an opt-in preview source
  policy. The default remains legacy mixed synthesis.
- Broker research can remain in 4.1-4.3 when explicitly attributed as broker
  research / professional analysis.
- The initial `market_expectation` classifier must not be a catch-all. Unknown
  or weakly classified items should stay in an "other / needs review" bucket
  rather than being labeled as market expectation.

Implemented in this preview pass:

- 4.4 taxonomy version `external_viewpoint.v1`.
- Flat narrative 4.4 rendering for `_curated_external_narrative` payloads.
- Grouped 4.4 rendering with empty groups suppressed for fallback
  `_curated_external_topic_groups` payloads.
- Digest and narrative paths carry or infer topic groups.
- `canonical_synthesis_source_policy=formal_first` excludes Xueqiu / Zhihu
  from canonical synthesis while retaining reports, announcements, news, and
  eligible source-intake formal items.
- `formal_first` is wired through `source_intake_configs.<stock>` but is not
  enabled by default for any stock in this design.
- Cached Xueqiu / Zhihu / Eastmoney community materials can now be converted
  into preview-only social source packets and run through the existing
  viewpoint digest extractor. This path writes only `/tmp` outputs and is not
  connected to report runtime.
- 黑芝麻智能 and 中际旭创 cached narratives passed formal report validation
  with flat `4.4` rendering and display-only isolation.

Deferred:

- Phase C cross-verified bridge. The LLM generating 4.1-4.3 must not see raw
  social text; this needs a separate implementation.
- Phase D default rollout. Low-formal-coverage names, especially HK stocks
  such as 黑芝麻智能, need graceful degradation thresholds and source-intake
  coverage checks before any default switch.
