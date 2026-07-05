# Evidence-Adaptive Deep Analysis First Batch Task

> For Claude Code in `/Users/erichan/testsnow`.

## Goal

Implement the first, smallest safe batch of `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-design.md`.

The report should stop forcing legacy `4.1 产业 / 4.2 业绩 / 4.3 资金` when formal materials are thin. For formal-thin but external-rich stocks such as 复旦微电, render:

- `4.1 正式材料要点`
- `4.2 外部观点地图（Preview，不参与评分）`
- `4.3 待验证清单`

For formal-rich stocks such as 中际旭创, preserve the existing supported legacy `4.1 / 4.2 / 4.3` layout.

## Required Reading

Read before editing:

- `docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-design.md`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/report_quality.py`

## Allowed Runtime Files

Prefer modifying only:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/report_quality.py`

Allowed tests:

- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/utils/test_curated_external_display.py`
- `tests/reporter/test_report_quality.py`

If another file is necessary, stop and explain why before editing it.

## Forbidden

- Do not change scoring, EV, target price, technical indicators, or recommendation algorithms.
- Do not wire external viewpoint signals into final recommendation, score, target price, EV, or risk score in this batch.
- Do not add a new runtime module.
- Do not add a new sidecar file.
- Do not change any crawler, Xueqiu/CDP/Playwright behavior, data source, or external API logic.
- Do not run Xueqiu detail-page collection or Chrome/CDP.
- Do not hand-edit generated reports as a fix.
- Do not delete internal reasoning/card metadata yet; only stop rendering visible cards in the report.

## Runtime Budget

- Target runtime net increase: <= 120 lines.
- Hard stop: > 200 runtime net lines unless paired with obvious deletion/merge of old visible-card or ad-hoc fallback paths.
- Notes must report runtime net line estimate and deletion/merge candidates.

## Implementation Requirements

### 1. Deterministic Evidence Profile

Add a deterministic profile payload, using existing synthesis inputs and the existing `_build_theme_material_budget()` path as much as possible.

Required profile shape:

```json
{
  "profile": "formal_rich | formal_thin_external_rich | thin_all",
  "formal_insight_facts": 0,
  "formal_section_support": {
    "industry": 0,
    "fundamentals": 0,
    "funding_support": 0,
    "catalyst_support": 0
  },
  "external_viewpoint_topics": 0,
  "external_usable_claims": 0,
  "external_source_count": 0,
  "external_distinct_author_count": 0,
  "single_source_external_rich": false,
  "external_signal_count": 0,
  "section_decisions": {
    "industry": "legacy | formal_summary | skipped",
    "fundamentals": "legacy | formal_summary | skipped",
    "funding": "legacy | fallback | skipped",
    "catalysts": "timeline | fallback | skipped"
  },
  "reasons": []
}
```

Counting rules:

- No LLM calls.
- Do not infer from rendered Markdown.
- Do not count document-existence facts such as annual report published, preview disclosed, dividend implemented.
- Do not count low-credit external material as formal support.
- `funding_support` must come from fund-flow, holding, financing balance, northbound, volume/turnover, or trading-sentiment data.
- Ordinary announcements, financing plans, dividends, and financial statements do not count as `funding_support`; route them to `catalyst_support` or `fundamentals`.

### 2. Pre-Synthesis Routing

Routing must happen before deep-analysis LLM prompt calls.

Behavior:

- `formal_rich`: keep supported legacy prompts. Funding can fallback locally if `funding_support == 0`; do not demote the whole layout.
- `formal_thin_external_rich`: skip legacy deep-analysis prompts for `industry_logic`, `fundamentals`, `valuation_debate`, `funding_sentiment`, and `events_catalysts`. The renderer should use formal facts/packs and external display payload instead.
- `thin_all`: skip forced deep-analysis prompts and render material-insufficient layout.

The renderer must not merely hide legacy LLM output after it has already been generated.

### 3. Renderer Layouts

Update `DeepAnalysisRenderer` to use the profile.

Always emit near the fourth chapter:

```markdown
<!-- deep_analysis_profile: {...full minimal audit payload...} -->
```

Also emit a visible badge:

```markdown
> 深度分析形态：正式材料丰富
```

or:

```markdown
> 深度分析形态：正式材料薄但外部观点丰富
```

or:

```markdown
> 深度分析形态：材料不足
```

For `formal_rich`, preserve existing legacy layout and citations.

For `formal_thin_external_rich`, render:

- `4.1 正式材料要点`
  - short formal-only summary.
  - include available annual-report explanation pack if present.
  - explicitly list important missing disclosures, such as customers, orders, capacity, supply chain, guidance, segment split, if not supported.
  - no peer financial comparison table here if already shown elsewhere.
- `4.2 外部观点地图（Preview，不参与评分）`
  - readable synthesis, not visible cards.
  - keep inline citations.
  - each topic should use four lightweight parts when available:
    - 外部观点链
    - 支持线索
    - 反方约束
    - 待验证证据
  - include a source-credit label such as `来源层级：低信用论坛 / 单源长文 / 多源一致 / 需正式验证`.
  - do not show raw source excerpts by default.
- `4.3 待验证清单`
  - table with columns: `变量 | 为什么重要 | 需要什么证据 | 来源层级`.

For `thin_all`, render formal material status and insufficiency notice. Do not force fake 4.1/4.2/4.3 analysis.

### 4. Remove Visible Reasoning Cards

Stop rendering the visible `**观点卡片：**` block.

Keep internal `_curated_external_reasoning_cards` or equivalent metadata available for citations and future audit. Do not delete schema-normalization code unless tests prove it is unused and the replacement metadata exists.

### 5. Display Core Facts Pruning

Implement only display-layer pruning.

- Raw source items remain available for citations, section support, and verification checklist.
- Remove or hide document-existence / duplicate / useless facts from the visible core facts table.
- Keep facts that carry investment-useful meaning: revenue/profit direction and reason, product-line change, margin/expense explanation, order/customer/capacity/supply/inventory/price/delivery/funding variables, guidance, or explicit absence of guidance.

### 6. Focused Quality Gates

Add focused checks in `report_quality.py`:

- `profile_routing_trace_missing`
  - error if fourth chapter lacks parseable `deep_analysis_profile`.
- `formal_thin_forced_legacy_deep_sections`
  - error if profile is `formal_thin_external_rich` but legacy `4.1 产业逻辑与竞争格局`, `4.2 业绩路径与多空分歧`, or `4.3 资金面与催化剂时间线` headings appear.
- `funding_claim_without_funding_support`
  - error if funding prose claims inflow/outflow, active buying/selling, northbound/financing/holding behavior, or trading sentiment while `funding_support == 0`.
- `useless_core_fact`
  - warning or error if visible core facts include document-existence facts.
- `external_map_missing_display_only_disclaimer`
  - error if external viewpoint map lacks display-only / not-scoring disclaimer.
- `external_map_unverified_claim_framing`
  - error if low-credit-only sentences use confirmation terms such as `确认`, `已经`, `确定`, `进入供应链`, `市占率`, `订单落地`, `客户为` without a formal citation.

Do not add broad prose-policing gates beyond these.

## Tests To Add Or Update

Use focused fixtures; do not run network, Chrome, CDP, or external data fetches.

Required tests:

1. `KnowledgeSynthesizer` / `SynthesisSkill`
   - formal-rich profile preserves legacy prompt eligibility.
   - formal-rich with weak funding keeps industry/fundamentals but marks funding fallback.
   - formal-thin external-rich profile skips legacy deep-analysis prompts.
   - funding support is not triggered by ordinary announcements or financial statements.
   - catalyst support can be triggered by direct company announcements.

2. `DeepAnalysisRenderer`
   - formal-rich renders legacy 4.1/4.2/4.3 and profile comment/badge.
   - formal-thin external-rich renders `4.1 正式材料要点`, `4.2 外部观点地图`, `4.3 待验证清单`.
   - formal-thin external-rich does not render legacy headings.
   - visible `**观点卡片：**` is absent.
   - internal citations for external paragraphs still render.

3. `curated_external_display`
   - external narrative display keeps internal reasoning-card/claim metadata.
   - external viewpoint map can be built without raw excerpts.

4. `report_quality`
   - catches missing profile comment.
   - catches legacy headings under formal-thin profile.
   - catches funding claims with `funding_support == 0`.
   - catches external map confirmed-claim wording when only low-credit external citation exists.
   - does not catch formal-rich legacy layout.

## Verification Commands

Run at minimum:

```bash
pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_curated_external_display.py tests/reporter/test_report_quality.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

If focused tests pass and no external data is needed, optionally run a no-network-ish smoke only if existing cached inputs are used. Do not run Xueqiu detail collection or Chrome/CDP.

## Completion Notes

Write notes to:

`docs/agent_workflow/2026-07-03-evidence-adaptive-deep-analysis-claude-notes.md`

Include:

- changed files.
- runtime net line estimate.
- requirement-test matrix.
- whether any new runtime file or sidecar was added.
- focused test results.
- CI gate and `git diff --check` result.
- examples of rendered headings for formal-rich and formal-thin fixtures.
- deletion/merge candidates for later cleanup.
- blockers, warnings, deviations.

## Stop Conditions

Stop and report instead of continuing if:

- profile cannot be generated before deep-analysis LLM synthesis.
- implementation needs a new runtime module or sidecar.
- external signals would need to affect recommendation, score, EV, target price, or risk score.
- `funding_support` cannot be separated from ordinary announcements/financial statements.
- visible external map cannot keep citations without visible cards.
- raw source items would need to be deleted to prune display core facts.
- runtime net increase is likely above 200 lines.
- tests require network, Chrome/CDP, or Xueqiu detail-page access.
