# Evidence Freshness Adaptation Design

日期：2026-07-14
分支：`codex/annual-producer-v2`
路线图批次：Batch 4

## 1. Goal

当正式材料已经较久、近期正式补充和券商材料不足时，报告需要明确这是一个时效性问题，并把已有的近期外部观察作为**待验证变量**补充到 Chapter 4 Preview；在极窄条件下，执行摘要最多展示一条同样被明确降级的近期变量。

本批解决“材料时间点过旧导致动态基本面偏薄”，不解决“没有任何可用材料”。它是现有 material / display 的 freshness overlay，不是新的采集、LLM memo 或 producer selector。

## 2. Fixed Boundaries

### Must preserve

- annual / broker / external producer、annual memo、MaterialSnapshot 均保留完整材料。
- `formal_medium` 的 Chapter4ViewModel 继续是 4.1--4.4 的唯一 display-row owner；`formal_thin_external_rich` 继续使用 full-snapshot citation offset。
- 4.1 只使用正式材料；外部来源绝不进入 4.1 官方确认区。
- 外部材料不进入 core facts、评分、风险评分、目标价、推荐结论、技术判断或 LLM synthesis input。
- profile 判定、采集、KnowledgeSynthesizer prompt 与外部 source discovery 均不修改。
- 不使用股票名、股票代码、行业专用词或缓存 mtime 作为规则输入。

### Out of scope

- 不新增网络请求、公告抓取、IR 采集或 LLM memo。
- 不从标题、文件名、报告年份或内容正文推测发布日期。
- 不改变 formal-rich legacy Chapter 4。
- 不重排 Batch 3 annual/broker editor selection；新鲜度只影响 external Preview 的排序提示与摘要的唯一受控补充。

## 3. Date Contract

### 3.1 Explicit metadata only

所有新鲜度判断只接受字段值，按下列顺序读取：

1. `published_at`
2. `publish_time`
3. `announcement_date`
4. `report_date`
5. citation metadata 的 `date`

只解析完整日期前缀：`YYYY-MM-DD`、`YYYY/MM/DD`、`YYYY年M月D日`。不完整年份、标题中的日期、文件路径、note mtime、抓取时间都返回 `None`。

`as_of_date` 由报告上下文的 `report_as_of_date` 提供；未注入时运行时使用 `date.today()`。测试必须显式注入 `report_as_of_date`，不依赖系统时钟。

### 3.2 Freshness states

阈值固定为 120 个自然日，且只在可解析日期时生效：

| 状态 | 条件 | 行为 |
|---|---|---|
| `fresh` | `0 <= age_days <= 120` | 该来源层可覆盖动态变量；不会触发外部摘要补充。 |
| `stale` | `age_days > 120` | 该来源层不再单独满足动态变量的近期性；可进入补充判定。 |
| `future` | 日期晚于 as-of | 视为未知，不参与补充。 |
| `unknown` | 没有明确可解析日期 | 保持原有材料展示，但**不触发**任何外部提升。 |

正式层、券商层、外部层分别计算最近日期和状态。缺少一个层的日期不允许由另一个层替代。

层状态聚合必须使用同一套 fail-closed 规则，不能只取“看起来最新”的一条：

- `fresh`：至少一条可用来源日期为 fresh；
- `official.stale`：正式层至少有一条可用来源，且**每一条**都有可解析日期并全部 stale；只要混有 undated / invalid / future 正式来源，正式层就是 `unknown`，不允许外部提升；
- `broker.stale`：至少一条可用券商来源有可解析 stale 日期，且没有 fresh；混有 undated / invalid / future 时记为 `unknown`，但仍按第 5 节的 broker-missing 路径处理；
- `unknown`：没有可用来源，或按上述规则无法证明该层完整日期状态；
- `latest_date` 只记录 `<= as_of_date` 的最近可解析日期；future 日期只进入 `reason_codes`，不能成为 latest。

### 3.3 Dynamic topics and conservative layer coverage

本批只对动态变量执行 freshness policy：订单/客户、产能/交付、毛利率/成本、需求/景气、产品验证/量产。长期业务模式、产品线、竞争定位继续使用正式材料，不因日期旧被降级。

本批的正式层与券商层采用**层级级别**的新鲜度门，而不是臆造“某一篇材料覆盖了某一主题”的映射：只要可用正式层或可用券商层存在 `fresh` 的明确日期，摘要外部补充一律不激活。这是宁可漏掉补充、也不把无关新材料误判为专题覆盖的保守策略。

外部候选自身必须有可归一化的 dynamic topic。现有 cached claim 的 `topic` 实际是自由文本，因此不能假定它已经是 canonical key；新增纯函数 `canonical_dynamic_topic(raw_topic)`，**只读取** claim 的 `topic` / `primary_topic` 元数据字段，并按封闭、通用、非股票专用 token 表归一化：

| canonical topic | 仅允许在 topic 字段内匹配的 token |
|---|---|
| `product_validation` | 验证、认证、导入、量产 |
| `order_customer` | 订单、客户、中标、签约 |
| `capacity_delivery` | 产能、交付、供应链、供应、物料 |
| `margin_cost` | 毛利、成本、费用、售价、产品价格、原料价格、价格压力 |
| `demand_cycle` | 需求、景气、周期、资本开支 |

优先级固定为表格顺序，避免“客户需求”在不同运行中落入不同 family。不得读取 claim、source_quote、why_incremental、paragraph body、heading、source title 或文件名做 topic 推断；不得调用当前会扫描正文的 `_external_viewpoint_topic_key()`。没有映射的 topic 归为 `other`，可留在现有 4.3 Preview，但不能成为 freshness preface 或摘要补充候选。paragraph 在验证时只保留 resolved claims 的 canonical topic ordered union 为 `topic_keys`。

## 4. Data Model and Ownership

新增纯函数模块：`scripts/utils/evidence_freshness.py`。

该模块不读取文件、不修改 context、不分配 citation id。输入是已经构造好的正式/券商/外部 metadata 与 `as_of_date`，输出可序列化的：

```python
{
  "schema": "evidence_freshness.v1",
  "as_of_date": "2026-07-14",
  "official": {"latest_date": "2026-03-31", "status": "stale"},
  "broker": {"latest_date": None, "status": "unknown"},
  "external": {"latest_date": "2026-07-01", "status": "fresh"},
  "dynamic_topics": {
    "order_customer": "needs_recent_support",
    "demand_cycle": "needs_recent_support"
  },
  "summary_candidate": {
    "paragraph_index": 0,
    "citation_refs": [12, 13],
    "citation_identities": [["url", "..."], ["url", "..."]],
    "topic": "demand_cycle",
    "reason_code": "official_stale_broker_missing_external_fresh"
  } | None,
  "reason_codes": ["official_stale", "broker_unknown"],
}
```

`SynthesisSkill` owns construction of the overlay because it already sees canonical `SynthesisItem.publish_time`, annual/broker memo inputs and curated external display before the renderer runs. It stores the overlay under `ctx["evidence_freshness"]` and does not mutate memo rows, core facts or profile.

The freshness inputs are deliberately narrow:

- official: dated `periodic_report_fulltext_items`，以及 `source_intake_items` 中 source type 明确属于 `exchange_announcement`、`company_ir`、`company_official`、`announcement`、`official`、`confirmed_fact` 或 `periodic_report_excerpt` 的条目；不能直接用 `is_formal_display_source()`，因为其集合还包含 broker / industry research / mainstream media；
- broker: dated `broker_research_digest_items` already eligible for the broker memo, excluding `extra.card_type == broker_risk_note`;
- external: the preferred `_curated_external_narrative_paragraphs` projection and its citation metadata only.

The overlay is built after the baseline synthesis object exists but before it is stored in `ctx["synthesis"]`. Adding display-only citation metadata must not append external text to baseline synthesis fields, `_sources`, `synthesis_text`, core facts, or any score input.

`deep_analysis_material_snapshot.py` and `Chapter4ViewModel` are intentionally out of scope for this batch. Batch 3 already projects the complete preferred external bucket without a freshness row cap; Batch 4 must not create a second selector merely to reorder it. `DeepAnalysisRenderer` consumes only the completed overlay to render a non-factual 4.3 preface and to reserve summary citation refs in the global citation table.

## 5. Source Priority and Candidate Admission

The policy is deterministic:

1. The profile must be `formal_medium` or `formal_thin_external_rich`; `formal_rich` and every other profile always return no candidate and no freshness preface.
2. Any usable `fresh` official source suppresses summary external supplementation.
3. Otherwise any usable `fresh` non-risk broker source suppresses summary external supplementation.
4. Only if official is `stale`, broker is `stale` or `unknown`, and a `fresh` external observation exists may that external observation be labelled as a recent pending variable.
5. If official is `unknown`, no external promotion occurs. The output may diagnose `official_date_unknown`, but 4.3 and the summary keep their current behavior.
6. An external candidate must already satisfy all existing preview-only fields (`synthesis_display_only is True`, `scoring_eligible is False`, `risk_score_eligible is False`, `quality_action == preview_only`, professional-observation status) on every supporting citation, be a row from the existing visible narrative-paragraph projection, have a mapped dynamic topic, and have a non-duplicate citation identity. Missing boundary fields fail closed. Supporting citations must all have numeric `source_credit >= 55`; lower or malformed credit remains ordinary 4.3 Preview only.
7. Every citation supporting that narrative paragraph must have an explicit parseable `fresh` date. A mixed dated/undated or mixed fresh/stale paragraph remains 4.3-only and cannot enter the summary.

No global external count is introduced. Existing Chapter 4 dedupe remains the hard constraint. The summary gets **at most one** candidate. Complete bounded candidate text is built before ranking; rows that cannot produce it are omitted. Remaining rows are sorted by `(oldest_supporting_date DESC, minimum_source_credit DESC, bounded_candidate_text_length DESC, original_index ASC)`；dynamic topic 只是 admission 条件，不是额外排序维度。相同 URL / metadata identity 先去重，再计算候选引用；支持来源中任一条日期或信用不合格，整段不准入。

## 6. Citation Plan

The baseline `synthesis["citations"]` map is the single allocator for an executive-summary external candidate:

1. `SynthesisSkill` derives candidate metadata from `deep_analysis_display` without changing that display.
2. It adds each candidate citation to baseline citations only when the strict admission policy passes, using the next numeric baseline ids and the existing URL-first `citation_identity()` semantics to dedupe against baseline metadata.
3. `evidence_freshness.summary_candidate.citation_refs` stores the final deduplicated baseline ids.
4. `ExecutiveSummaryRenderer` renders exactly those `[^n]` markers. It does not allocate or offset ids.
5. `DeepAnalysisRenderer` continues to offset Chapter 4 snapshot citations from the maximum baseline id. Therefore formal-thin keeps its existing formula:

```
annual_offset   = max(baseline citations)
broker_offset   = annual_offset + max(full snapshot annual ref)
external_offset = annual_offset + max(full snapshot annual/broker ref)
```

The summary candidate citation is source-boundary display-only metadata, never a core-fact citation. Citation identity dedupe uses existing URL-first identity semantics.

Because the same external paragraph remains visible in 4.3, its snapshot citation would otherwise be emitted a second time after offset. After Chapter 4 has been rendered and all offsets are known, `DeepAnalysisRenderer` builds an alias map from offset Chapter 4 refs to the reserved baseline candidate refs when `citation_identity()` matches. It remaps only exact `[^n]` markers inside `deep_md`, then runs visible-citation pruning. This is a post-offset identity alias: annual/broker/external offset arithmetic remains based on the full snapshot, while the final report contains one citation row per candidate identity. No unrelated Chapter 4 citation may be remapped, and no aliasing runs when there is no renderable summary candidate.

`DeepAnalysisRenderer._visible_citations_only()` currently sees only its own section text, while the executive summary is assembled earlier. Therefore its signature becomes `_visible_citations_only(citations, body_text, reserved_refs=())` and it retains the union of inline refs from its own text plus `reserved_refs` from a renderable `evidence_freshness.summary_candidate`. It must not retain any candidate ref when the overlay has no renderable summary candidate. The reserved refs and the post-offset alias map are derived from the same summary-candidate tuple; this keeps a valid summary footnote from being removed while avoiding duplicate/unused citation rows.

## 7. Rendered Output

### 7.1 Chapter 4

- 4.1 keeps the existing official-only title, rows and boundary.
- 4.2 keeps broker attribution and the existing institution assumption contract.
- 4.3 keeps its Preview disclaimer. Only when the visible narrative projection has at least one fully fresh, explicitly dated dynamic row and the official/broker gate permits supplementation, append one short deterministic preface before its rows:

  `正式材料的时间点较早，以下近期外部观察仅补充订单、交付、成本、需求或产品验证等变量；不替代官方确认，不参与评分、风险评分或目标价。`

  It is a boundary label, not an external factual assertion and carries no citation itself.
- 4.4 receives no new source and remains a conditional-only projection of visible rows.

### 7.2 Executive summary

Only when `summary_candidate` is present, append one labelled sentence immediately after `基本面判断`:

```markdown
**近期待验证变量**：外部材料称，[candidate claim][^n][^m]（外部待验证，不替代官方确认，不参与评分、风险评分或目标价）。
```

The sentence must not say “公司已…”, “确认…”, “订单已…”, “客户已…”, “预计贡献…”, or otherwise convert the external claim into a confirmed fact or forecast. The pure policy module owns one `has_unnegated_strong_confirmation()` helper; `report_quality.py` reuses it instead of maintaining a second token/negation list. Admission scans the bounded candidate text after stripping only negative-confirmation phrases; any unnegated strong-confirmation token fails closed rather than being rewritten. It uses the first source-preserving complete sentence(s) of the already visible paragraph, at most 160 Chinese characters; if no complete bounded text exists, omit the candidate. Text is compacted before all citations are attached; citations must remain complete.

If the overlay is absent, unknown, stale externally, invalid, duplicated, or incomplete, the sentence is omitted completely. Formal-thin’s existing unsupported-bullish filter continues to apply to separately extracted LLM points; this deterministic labelled sentence is not a bullish point.

## 8. Metadata Plumbing

Current curated narrative citation objects do not consistently retain publication dates or all preview-only boundary fields. `_citation_from_claim()` may read the first explicit claim date in Date Contract order (`published_at` → `publish_time` → `announcement_date` → `report_date` → `date`) and copy that raw value into the citation's canonical `date` field, plus copy `synthesis_display_only`、`scoring_eligible`、`risk_score_eligible`、`quality_action` from the already-safe claim without parsing, defaulting, or inventing them; the pure freshness module owns date parsing and admission. Missing fields in legacy cached narratives therefore remain a safe no-op. During narrative validation, a paragraph may retain `topic_keys` only as the ordered de-duplicated union of `canonical_dynamic_topic()` applied to its resolved claims' `topic` / `primary_topic` fields. Existing paragraphs do not have a stable id, so the overlay stores their zero-based `paragraph_index` and stable input order rather than synthesizing an identity from heading/text. It may not derive a date or topic from source text, title, path or mtime when that metadata is absent.

Existing official `SynthesisItem.publish_time` and broker digest `publish_time` are usable inputs. Annual narrative cards that only carry `report_year` are not a valid publication-date substitute. Source Intake already exposes a reusable explicit configuration boundary; this batch must consume its output only, not enable it, change defaults, or add a rendering flag.

## 8.1 Quality Gate Contract

`report_quality.py` receives Markdown rather than the in-memory overlay, so it enforces report-level grammar only:

- `**近期待验证变量**` appears zero or one time in `执行摘要`;
- if present, it has at least one complete inline footnote and includes both `外部待验证` and `不替代官方确认`;
- the same line contains `不参与评分`、`风险评分`、`目标价` and does not contain an unnegated strong-confirmation pattern;
- its refs resolve in the final global citation table.

Unit tests for `evidence_freshness` and `SynthesisSkill` enforce the stricter in-memory admission predicate. An assembly integration test proves that a renderable candidate survives global citation pruning. Neither gate reconstructs freshness from report prose.

## 9. Failure Modes and Tests

| Failure mode | Expected safe outcome | Required regression test |
|---|---|---|
| Old annual date + no broker + fully fresh dated external paragraph | One labelled summary pending variable; 4.3 freshness preface; external remains display-only. | Fixed as-of fixture, all paragraph refs resolve globally, no core-fact/scoring mutation. |
| Same evidence under formal-rich | No candidate and no freshness preface; legacy Chapter 4 is byte-for-byte unchanged for the fixture. | Explicit profile-gate regression fixture. |
| Official date missing | No summary external candidate and no freshness preface. | `unknown` official date fails closed. |
| Fresh official source exists | External content remains only in normal 4.3; no summary candidate. | Conservative official-layer suppression fixture. |
| Fresh non-risk broker exists | No external summary candidate. | Conservative broker-layer precedence fixture. |
| External paragraph lacks date, topic, citation, or has mixed fresh/stale refs | No candidate and no 4.3 freshness preface. | Missing/mixed metadata fixtures. |
| Legacy narrative citation lacks preview-only boundary fields | No candidate; existing 4.3 output remains unchanged. | Legacy-cache safe-no-op fixture. |
| Formal layer mixes stale dated material with an undated/future item | Official status is unknown; no external promotion. | Layer aggregation fail-closed fixture. |
| Free-form topic mentions a dynamic variable only in body/title, not topic metadata | It remains `other`; no promotion. | Topic-field-only normalization fixture. |
| Candidate has any supporting citation below credit 55 | It remains normal 4.3 Preview only. | Mixed-credit paragraph fixture. |
| Duplicate URL appears in several candidate refs | At most one candidate and a single baseline citation identity. | URL identity dedupe fixture. |
| Candidate URL is also visible in offset Chapter 4 citations | Deep body refs alias to the reserved baseline ref; final citation table has one identity and no missing/unused refs. | Formal-medium and formal-thin post-offset alias fixtures. |
| Candidate leaks into 4.1 / core facts / scoring | Quality error / test failure. | Formal-medium and formal-thin source-boundary fixtures. |
| Baseline candidate is pruned as not visible to DeepAnalysisRenderer | Reserved summary refs remain in the global source table only when the executive sentence is renderable. | Assembly integration fixture with formal-thin full-snapshot offsets and no missing/unused refs. |
| Invalid/future date | Treat as unknown, no promotion. | Future-date fixture. |
| External candidate sounds confirmed | Quality error. | Summary must contain both `外部待验证` and `不替代官方确认`; unframed external hard claim fails. |
| Candidate needs a mid-sentence cut | Omit it rather than rendering a fragment or truncating its footnotes. | Bounded-summary-text fixture. |

## 10. Planned Scope

Runtime files, subject to review refinement:

- Create `scripts/utils/evidence_freshness.py`
- Modify `scripts/utils/report_skills/synthesis_skills.py`
- Modify `scripts/utils/curated_external_viewpoint_narrative.py`
- Modify `scripts/utils/reporter/sections/executive_summary_renderer.py`
- Modify `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Modify `scripts/utils/report_quality.py`

Corresponding focused tests may be added under `tests/utils/` and `tests/reporter/`. No config, data, knowledge, report, prompt, scoring, target-price, risk or technical files are allowed.

Runtime target is net `+190` lines; hard stop is `+240` runtime lines against the locked pre-Batch-4 baseline. Tests and workflow notes are excluded from this count. The implementation must reuse existing `citation_identity()`, replace local duplicate date/candidate helpers, and must not add an alternative selector. The budget includes an explicit date parser, topic-field-only normalizer, strict paragraph admission, citation reservation/post-offset aliasing, and boundary gates; hiding these in existing renderers would make the policy untestable.

## 11. Stop Conditions

Stop and return to design if any condition is met:

1. A required source date exists only in titles, paths, cache mtimes or inferred text.
2. Citation allocation cannot preserve formal-thin’s full-snapshot offset contract.
3. The change would alter profile, core facts, scoring, risk, target price, recommendation, technical analysis, collection or LLM prompt.
4. The overlay needs a second external selector, a body-keyword topic classifier, or inferred topic/date metadata.
5. Any missing, unused, malformed or `unknown` citation is introduced.
6. Runtime net delta exceeds `+240` lines.
7. A test demonstrates an external statement can enter 4.1, official confirmation language, or a score-driving path.

## 12. Acceptance

The batch is accepted only after focused unit/renderer/quality tests pass, global citations remain aligned for formal-medium and formal-thin fixtures, and fresh generated reports for a dated source scenario demonstrate:

- stale official timing is visibly disclosed only when a fully fresh visible external paragraph exists, without reducing official-source boundaries;
- one or zero explicitly framed external summary variables, never more;
- external content stays Preview/display-only and does not affect scores or targets;
- undated legacy external narratives remain safe no-op candidates.
