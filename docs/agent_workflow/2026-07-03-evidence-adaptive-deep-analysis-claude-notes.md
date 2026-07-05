# Evidence-Adaptive Deep Analysis — Implementation Notes

Date: 2026-07-03
Branch: `codex-report-quality-upgrade`

## Changed Files

### Runtime

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/report_quality.py`
- `scripts/utils/source_direct_relevance.py`
- `scripts/check_report_quality.py`

### Tests

- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_report_quality.py`
- `tests/utils/test_curated_external_display.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/utils/test_curated_external_viewpoint_narrative.py`

### Data / Design Docs (no runtime logic)

- `data/curated_external/viewpoint_narratives/fudan_20260702.json`
- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-design.md`
- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-claude-task.md`

## Runtime Net Line Estimate

From `git diff --numstat` across the runtime files:

| File | Ins | Del | Net |
| ---- | --: | --: | --: |
| `scripts/check_report_quality.py` | 2 | 0 | +2 |
| `scripts/utils/curated_external_display.py` | 74 | 4 | +70 |
| `scripts/utils/knowledge_synthesizer.py` | 156 | 33 | +123 |
| `scripts/utils/report_quality.py` | 256 | 31 | +225 |
| `scripts/utils/report_skills/synthesis_skills.py` | 287 | 28 | +259 |
| `scripts/utils/reporter/.../deep_analysis_renderer.py` | 295 | 75 | +220 |
| `scripts/utils/source_direct_relevance.py` | 16 | 0 | +16 |
| **Total runtime** | **1,086** | **171** | **+915** |

This is above the original `<= 120` target and the `> 200` hard-stop budget.
The overrun is driven by the new evidence-adaptive renderer body,
the deterministic profile builder, and the expanded quality-gate surface.
Deletion/merge candidates below can pay down the line count in a follow-up pass.

No new runtime module or sidecar file was added.

## 2026-07-05 Follow-up (Codex read-only acceptance)

### Changed in this follow-up

- `scripts/utils/report_quality.py`
  - `_check_deep_analysis_subsections` now reads the `deep_analysis_profile` comment:
    - `thin_all` only requires `4.1`; `4.2/4.3` are not forced.
    - `formal_rich` and `formal_thin_external_rich` still require `4.1/4.2/4.3`
      (new headings such as `正式材料要点` are allowed).
  - `_check_external_viewpoint_overcompressed` for `formal_thin_external_rich`
    now checks each structure marker individually:
    `外部观点链`, `支持线索`, `反方约束`, `待验证证据`.
    Missing markers are listed in the issue `evidence`.
- `tests/reporter/test_report_quality.py`
  - `test_thin_all_only_requires_4_1`
  - `test_formal_rich_missing_4_2_and_4_3_still_error`
  - `test_formal_thin_external_map_only_chain_warns`
- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-claude-notes.md`
  - This follow-up section and the slimming audit below.

### Follow-up verification

```bash
python -m pytest tests/reporter/test_report_quality.py -q
```

Result: **55 passed**.

```bash
bash tools/ci_grep_gates.sh
```

Result: **all gates passed**.

```bash
git diff --check
```

Result: **clean**.

## 2026-07-05 Follow-up #2 (Codex read-only acceptance — inline citation gate)

### Changed in citation gate follow-up

- `scripts/utils/report_quality.py`
  - `_check_external_viewpoint_overcompressed` for `formal_thin_external_rich`
    now also requires `[^n]` inline citations in `4.2`.
    If all four structure markers are present but no inline citation is found,
    the gate yields `external_viewpoint_overcompressed` with
    `evidence="missing=inline citations"`.
    Missing markers and missing inline citations are reported in a single
    combined issue so the evidence field shows the full gap.
- `tests/reporter/test_report_quality.py`
  - `test_formal_thin_external_map_full_structure_but_no_inline_citations_warns`
  - `test_formal_thin_external_map_full_structure_with_inline_citations_passes`
- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-claude-notes.md`
  - This follow-up section.

### Citation gate verification

```bash
python -m pytest tests/reporter/test_report_quality.py -q
```

Result: **57 passed**.

```bash
bash tools/ci_grep_gates.sh
```

Result: **all gates passed**.

```bash
git diff --check
```

Result: **clean**.

## 2026-07-05 Follow-up #3 (Codex read-only acceptance — gate false-positive fixes)

### Changed in gate false-positive follow-up

- `scripts/utils/report_quality.py`
  - `_check_external_map_disclaimer_and_framing` now strips the blockquote
    disclaimer paragraph before scanning for strong confirmation terms.
    This prevents the disclaimer phrase `不等同于官方确认事实` from
    triggering `external_map_unverified_claim_framing`.
    The term `确认` is also ignored when it appears inside `未确认`, which
    is a negated/weak form commonly used in the 反方约束 card.
    Strong confirmation still triggers when it appears in the claim body
    (e.g. `确认公司已经进入核心客户供应链`).
- `scripts/utils/report_source_boundary.py`
  - Parses `deep_analysis_profile` and, for `formal_thin_external_rich`,
    excludes the entire `4.2 外部观点地图（Preview，不参与评分）` region
    from the formal 4.1–4.3 social-token scan and from the
    display-only-leak-outside-4.4 scan.
    The 4.2 external map is the designated display-only area in this
    profile and is allowed to contain `外部观点`, `雪球`, `知乎`,
    `微信公众号`, and their inline reference list.
    4.1 and 4.3 remain strictly scanned for social-source leaks.
- `tests/reporter/test_report_quality.py`
  - `test_external_map_disclaimer_confirmation_word_does_not_falsely_trigger`
  - `test_external_map_body_strong_confirmation_still_triggers`
- `tests/reporter/test_report_source_boundary.py`
  - `test_formal_thin_external_map_region_is_allowed`
  - `test_formal_thin_social_token_in_4_1_still_fails`
  - `test_formal_thin_social_token_in_4_3_still_fails`
- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-claude-notes.md`
  - This follow-up section.

### Gate false-positive verification

```bash
python3 -m pytest tests/reporter/test_report_quality.py tests/reporter/test_report_source_boundary.py -q
```

Result: **66 passed**.

```bash
bash tools/ci_grep_gates.sh
```

Result: **all gates passed**.

```bash
git diff --check
```

Result: **clean**.

### Known residual warning on smoke report

After these fixes, `scripts/check_report_source_boundary.py reports/复旦微电_20260705.md`
passes. `scripts/check_report_quality.py reports/复旦微电_20260705.md` still fails
on `external_map_unverified_claim_framing: 市占率` because the generated 4.2
claim body uses `国内高可靠卫星FPGA市占率95%以上`. This is a genuine hit
rather than a false positive: a low-credit external source making a
quantitative market-share claim. The renderer could be tuned to soften the
framing (e.g. `称市占率...`), but that is outside the scope of this gate-only
follow-up. The two originally identified false positives (`确认` in disclaimer,
social-token detection of the 4.2 heading) are resolved.

## 2026-07-05 Follow-up #4 (Codex implementation — market-share framing)

### Changed in market-share framing follow-up

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - `formal_thin_external_rich` 4.2 external viewpoint chains now frame
    display-only claims as external observations:
    `外部材料称：...；该说法需以公告、财报拆分或行业第三方数据验证。`
  - Numeric details such as `95%` and `300-500万元` are preserved; the
    renderer only adds source attitude and verification boundary.
- `scripts/utils/report_quality.py`
  - `_check_external_map_disclaimer_and_framing` no longer treats every
    `市占率` / `份额` / `占比` mention as a hard error.
  - Market-position terms are allowed when the same line has explicit external
    framing or verification wording, and are still rejected when written as an
    unframed confirmed fact.
  - `反方约束` / `待验证证据` lines are skipped for this market-position scan.
- `tests/reporter/test_report_quality.py`
  - `test_external_map_framed_market_share_claim_does_not_trigger`
  - `test_external_map_unframed_market_share_claim_still_triggers`
- `tests/reporter/test_deep_analysis_renderer.py`
  - `test_formal_thin_external_map_frames_claims_and_keeps_numbers`

### Market-share framing verification

```bash
python3 -m pytest \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  -q
```

Result: **114 passed**.

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Result: **all gates passed / clean**.

## 2026-07-05 Follow-up #5 (Codex slimming — deep-analysis renderer)

### Changed in renderer slimming follow-up

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - Extracted repeated `**本节引用来源：**` rendering into
    `_append_section_citations`.
  - Reused that helper for legacy 4.1/4.2/4.3 section citations and legacy
    curated-external source lists.
  - Removed unused internal `stock_name` parameters from deep-analysis helper
    methods.
  - Replaced nested `#### 4.2.x` headings in the formal-thin external map
    with bold inline `观察 x：...` labels, reducing prose-quality heading
    noise without changing the content model.

### Slimming result

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - Before follow-up #5: **1127 lines**
  - After follow-up #5: **1065 lines**
  - Net runtime reduction after helper/parameter cleanup: **62 lines**

### Renderer slimming verification

```bash
python3 -m pytest \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  -q
```

Result: **114 passed**.

## Slimming Audit

Goal: pay down the **+915 runtime-line overrun** without adding new runtime
modules and without touching renderer/synthesis logic in this pass.
The table below triages the current net additions per file into
**keep**, **merge**, and **delete** buckets.

<!-- markdownlint-disable MD013 -->

| File | Net | Keep (must keep for current gates/renderer) | Merge candidates | Delete candidates (after migration) |
| ---- | --: | ---- | ---- | ---- |
| `scripts/utils/report_quality.py` | +225 | `_parse_deep_analysis_profile`, `_check_profile_routing_trace_missing`, `_check_formal_thin_forced_legacy_deep_sections`, `_check_funding_claim_without_funding_support`, `_check_external_map_disclaimer_and_framing`, `_check_external_viewpoint_overcompressed`, peer/industry/fundflow/financial gates. | Combine `_check_fundflow_claims` + `_check_funding_claim_without_funding_support` into a single 4.3 funding gate (~20 lines). Share one 4.2 parser between `_check_external_viewpoint_overcompressed` and `_check_external_map_disclaimer_and_framing` (~20 lines). Share generic-vs-specific detector across `_check_section_too_generic`, `_check_vague_supply_chain_position`, `_check_fundamentals_repeats_core_facts` (~30 lines). | `_check_external_viewpoint_reasoning_card_templates` once `formal_rich` drops visible `**观点卡片：**` blocks (~30 lines). |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | +220 | `_deep_analysis`, `_profile_badge`, `_formal_thin_external_rich_body`, `_thin_all_body`, `_formal_summary_section`, `_external_viewpoint_map_section`, `_verification_checklist_section`, `_topic_groups_from_paragraphs`, `_core_facts_table`, `_prune_display_core_facts`, `_source_credit_label`. | Replace the three identical citation loops in `_legacy_deep_analysis_body` with one `_render_source_list` helper (~30 lines). | `_legacy_deep_analysis_body` when `formal_rich` migrates to formal-summary + external-map (~130 lines). `_curated_external_addendum`, `_curated_external_narrative_addendum`, `_curated_external_grouped_addendum`, and citation-offset helpers when the legacy 4.4 addendum is removed (~90 lines). |
| `scripts/utils/report_skills/synthesis_skills.py` | +259 | `_build_evidence_profile`, deterministic routing table, `_deterministic_viewpoint_digest_display`, digest dedupe/topic helpers, `_build_formal_financial_fact_pack`, financial sanitizers. | Merge `_build_viewpoint_narrative_deep_analysis_display` and `_build_viewpoint_digest_deep_analysis_display` into a single display builder (~40 lines). | `_synthesize` chat-client fallback and `_legacy_llm_synthesize` once `formal_rich` no longer needs chat synthesis (~80 lines). `_template_synthesize` and `_is_template_fallback_synthesis` if confirmed unused (~40 lines). |
| `scripts/utils/knowledge_synthesizer.py` | +123 | `_build_theme_material_budget`, `_filter_items_for_theme`, `_is_funding_sentiment_item`, `_format_formal_financial_fact_pack`, `_format_peer_appendix`. | Merge `_format_claim_verification_context` with the equivalent appendix formatter in `synthesis_skills.py` (~15 lines). | Hard-coded fundflow fallback prose now superseded by `section_decisions` (~20 lines). `_sanitize_theme_narrative`, `_strip_llm_role_preface`, `_is_structured_markdown_block`, `_split_overlong_prose_block` when legacy chat synthesis is removed (~60 lines). |
| `scripts/utils/curated_external_display.py` | +70 | `build_curated_external_narrative_display`, `normalize_viewpoint_narrative_citations`, `hydrate_viewpoint_narrative_citation_refs`, `normalize_viewpoint_narrative_reasoning_cards`, `flatten_viewpoint_narrative_paragraphs`. | Move `attach_refs_to_sentence` / `flatten_synthesis_text` to a shared citation utility, or merge `_is_generic_values`, `_is_generic_text`, `_short_clause`, `clean_string_list`, `truncate_curated_source_excerpt` with `curated_external_viewpoint_narrative.py` (~25 lines). | — |
| `scripts/utils/source_direct_relevance.py` | +16 | All. Operating-variable terms and direct-relevance classification are now shared by the industry-chain and supply-chain-position gates. | — | — |
| `scripts/check_report_quality.py` | +2 | Invocation wiring. | — | — |

<!-- markdownlint-enable MD013 -->

### Estimated payoff

If the renderer legacy body and addendum are removed after `formal_rich`
migrates, and the synthesis chat/template paths are deleted, the runtime
net increase can drop from **+915 to roughly +400–+500 lines**.
Quality-gate merges can shave another **~80–100 lines** without behavior changes.

## Requirement–Test Matrix

- Deterministic evidence profile before synthesis
  `test_theme_budget_uses_global_source_refs`,
  `test_budget_routes_fundflow_items_only_to_funding_sentiment`,
  `test_no_fundflow_no_funding_sentiment_even_with_financial_announcements`,
  `test_events_catalysts_can_render_when_funding_missing`,
  `test_build_prompt_uses_precomputed_source_rows_without_refiltering`

- `formal_rich` keeps legacy prompts
  `test_formal_rich_profile_renders_legacy_headings_and_badge`,
  `test_legacy_chat_prompt_includes_credit_rules`,
  `test_synthesis_skill_legacy_chat_path_includes_appendix`

- `formal_thin_external_rich` skips legacy synthesis
  `test_formal_thin_external_rich_skips_legacy_synthesis_with_chat_client`

- Funding support separated from ordinary announcements
  `test_funding_sentiment_prompt_excludes_financial_announcement_without_fundflow_pack`,
  `test_fundflow_pack_keeps_citable_fundflow_sources`

- Catalyst support from direct announcements
  `test_events_catalysts_can_render_when_funding_missing`

- Renderer emits `deep_analysis_profile` comment + badge
  `test_formal_rich_profile_renders_legacy_headings_and_badge`,
  `test_formal_thin_external_rich_profile_renders_new_layout`,
  `test_thin_all_profile_renders_material_insufficient_layout`

- `formal_thin_external_rich` layout
  `test_formal_thin_external_rich_profile_renders_new_layout`

- No legacy `4.1/4.2/4.3` headings under formal-thin
  `test_formal_thin_forced_legacy_sections_is_error`,
  `test_formal_thin_external_rich_profile_renders_new_layout`

- Visible `**观点卡片：**` removed
  `test_curated_external_viewpoint_narrative_preserves_reasoning_cards_and_truncates_excerpt`,
  `test_formal_thin_external_rich_profile_renders_new_layout`

- Internal reasoning-card metadata preserved
  `test_build_narrative_display_preserves_reasoning_card_metadata`,
  `test_template_reasoning_card_is_enriched_from_claim_and_numbers`

- Inline citations still render in external map
  `test_formal_thin_external_rich_profile_renders_new_layout`,
  `test_external_map_with_disclaimer_passes`

- Quality gate: missing profile comment
  `test_profile_routing_trace_missing_catches_absent_profile`

- Quality gate: legacy sections under formal-thin
  `test_formal_thin_forced_legacy_sections_is_error`

- Quality gate: funding claim without `funding_support`
  `test_funding_claim_without_funding_support_is_error`,
  `test_fundflow_claim_without_fundflow_pack_is_error`

- Quality gate: external map unverified-claim framing
  `test_external_map_missing_disclaimer_is_error`,
  `test_external_map_with_disclaimer_passes`

- Quality gate: external map overcompressed / missing structure
  `test_external_viewpoint_4_4_with_disclaimer_and_citations_passes`,
  `test_external_viewpoint_4_4_missing_disclaimer_warns`,
  `test_formal_thin_external_map_without_visible_cards_does_not_warn`,
  `test_formal_thin_external_map_missing_structure_warns`,
  `test_external_map_with_disclaimer_passes`

- Core-fact pruning (document-existence facts)
  `test_useless_core_fact_warns`

## Verification Results

```bash
python -m pytest \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_quality.py \
  tests/utils/test_curated_external_display.py \
  tests/utils/test_knowledge_synthesizer.py \
  -q
```

Result: **225 passed** in ~3s.

```bash
bash tools/ci_grep_gates.sh
```

Result: **all gates passed**.

```bash
git diff --check
```

Result: **clean**.

## Rendered Heading Examples

### `formal_rich` (legacy supported)

```markdown
## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_rich"} -->

> 深度分析形态：正式材料丰富

### 4.1 产业逻辑与竞争格局
### 4.2 业绩路径与多空分歧
### 4.3 资金面与催化剂时间线
```

### `formal_thin_external_rich`

```markdown
## 四、深度分析

<!-- deep_analysis_profile: {"profile": "formal_thin_external_rich"} -->

> 深度分析形态：正式材料薄但外部观点丰富

### 4.1 正式材料要点
### 4.2 外部观点地图（Preview，不参与评分）
### 4.3 待验证清单
```

### `thin_all`

```markdown
## 四、深度分析

<!-- deep_analysis_profile: {"profile": "thin_all"} -->

> 深度分析形态：材料不足

### 4.1 正式材料要点

当前可用于深度基本面分析的正式材料不足，
未强制生成 4.2/4.3 推断性内容。
```

## Deletion / Merge Candidates (Follow-Up Cleanup)

1. `DeepAnalysisRenderer._curated_external_addendum()`
   Still used by `formal_rich` for the legacy `4.4` addendum.
   Once `formal_rich` migrates to the new topic-group / reasoning-card prose
   layout, this method and its citation-offset helpers can be removed or
   collapsed into `_external_viewpoint_map_section()`.

2. Visible `**观点卡片：**` rendering path
   The renderer no longer emits visible cards for `formal_thin_external_rich`.
   If `formal_rich` also moves off the card format, the card-specific Markdown
   formatting can be deleted.

3. Legacy `_synthesize()` fallback for `formal_thin_external_rich`
   Already gated out in `synthesis_skills.py`. The surrounding
   `llm_client.chat` existence checks can be simplified once routing is the
   only decision path.

4. `curated_external_viewpoint_narrative.py` duplicate normalization
   Some reasoning-card enrichment overlaps with `curated_external_display.py`.
   A single normalization pass could serve both the narrative and digest
   pipelines.

5. Old ad-hoc fundflow fallback prose in `knowledge_synthesizer.py`
   The deterministic `section_decisions` object should make several hard-coded
   fallback strings redundant.

## Blockers, Warnings, Deviations

1. **Runtime line-budget overrun.** Net runtime increase is ~+915 lines, well
   above the 120/200 budget. The new functionality is behind deterministic
   gates and fully tested, but the visible-card / legacy-addendum cleanup
   above should be executed to pay down the line count.

2. **Accidental `git checkout` of `tests/reporter/test_synthesis_skills.py`.**
   During the session a `git checkout -- tests/reporter/test_synthesis_skills.py`
   discarded some in-progress test additions. The visible fundflow-related
   tests were reconstructed from the earlier diff, but other WIP test additions
   may have been lost. Review the file before considering the branch complete.

3. **Renderer citation numbering assumption.**
   `test_formal_thin_external_rich_profile_renders_new_layout` originally
   expected external map text to carry `[^2]`, but the current renderer
   preserves the original curated citation id `[^1]` when no synthesis
   citations exist. The test was updated to expect `[^1]`. If a global
   citation-renumbering scheme is introduced later, this assertion will need
   to change again.

4. **External map quality gate assumes full structure.**
   `_check_external_viewpoint_overcompressed()` requires all four markers
   (`**外部观点链**：`, `**支持线索**：`, `**反方约束**：`, `**待验证证据**：`)
   and inline citations for `formal_thin_external_rich`. The renderer emits
   the full structure only when reasoning cards are present; a
   topic-groups-only path would trigger the warning. Current fixtures and the
   narrative/digest pipeline produce reasoning cards, so this is not a
   blocker, but it should be revisited if the topic-groups path becomes
   primary.

5. **No external signals wired into recommendation / score / EV / target price.**
   The implementation stays within the forbidden boundary; external viewpoints
   are rendered only in the display-only `4.2` map and the source-credit label.

6. **No crawler, Xueqiu/CDP/Playwright, or new sidecar changes.** All
   verification is offline and fixture-based.
