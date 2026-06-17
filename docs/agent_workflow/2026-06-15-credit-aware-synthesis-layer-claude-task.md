# Claude Implementation Task — Credit-Aware Synthesis Layer Phase 1

## Status

Ready to implement.

Design:

- `docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-design.md`

Round 2 conclusion:

- Status: Ready to implement
- R3 Needed: No

## Goal

Implement Phase 1 of the Credit-Aware Synthesis Layer.

This is a synthesis-safety upgrade. It must make `KnowledgeSynthesizer` and legacy synthesis prompts aware of source credit and claim verification status, and must add deterministic protection so news/research/community sources cannot support core facts.

## Allowed Files

Implementation:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- Optional new helper: `scripts/utils/synthesis_credit.py`

Tests:

- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py` only if needed to lock existing `invalid_ref` display behavior

Notes:

- `docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-claude-notes.md`

## Forbidden Files / Behavior

Do not modify:

- `scripts/utils/reporter/scoring_engine.py`
- technical analysis modules
- EV / position advice logic
- Source Intake fetchers
- Agent-Reach fetchers
- Xueqiu / CDP / Playwright collection logic
- `config/stocks.json`
- `knowledge/**`
- `reports/**`
- `data/raw/**`

Do not:

- Run LLM calls.
- Access external network.
- Generate reports.
- Refresh Zhihu.
- Fetch Xueqiu detail pages.
- Start Chrome/CDP.

Stop if implementation requires modifying scoring, technical algorithms, data collectors, or report runtime behavior outside the allowed files.

## Required Implementation

### 1. Shared credit helper

Create a helper importable by both `knowledge_synthesizer.py` and `synthesis_skills.py`.

Preferred location:

- `scripts/utils/synthesis_credit.py`

Required public helpers:

```python
credit_usage_rules_text() -> str
derive_synthesis_usage(item_or_meta) -> dict
format_synthesis_source_line(index: int, item) -> str
is_core_fact_supporting_source(source: str, meta: dict | None = None) -> bool
```

Use a minimal API if implementation finds a cleaner shape, but the same logic must be shared by:

- `KnowledgeSynthesizer._build_prompt()`
- `SynthesisSkill._build_prompt()` legacy `.chat(prompt)` path
- `SynthesisSkill._enrich_core_fact_provenance()`

### 2. Source usage fallback mapping

`derive_synthesis_usage()` must prefer structured metadata when present:

- `source_credit`
- `source_type`
- `verification_status`

If metadata is missing, fallback by `source_platform`.

Required mapping:

| source_platform | credit_tier | usage |
|---|---|---|
| 公告 | high | core_fact_allowed |
| 巨潮 / 交易所 / 官方 | high | core_fact_allowed |
| 研报 | medium | professional_observation |
| 新闻 | medium | professional_observation |
| 东方财富新闻 / 同花顺新闻 | medium | professional_observation |
| 微信公众号 | medium or low, but must be explicit; prefer medium/professional_observation only if source is publisher/article, otherwise low/discussion_only |
| 资金流向 | medium | quantitative_observation |
| 雪球 | low | discussion_only |
| 知乎 | low | discussion_only |
| AgentReach(...) | use `extra.source_credit` if present, otherwise low/limited |
| unknown | unknown | background_limited |

Unknown must never be `core_fact_allowed`.

### 3. Prompt rules

Add shared credit usage rules before numbered source lines in `KnowledgeSynthesizer._build_prompt()`.

Rules must include:

- 高信用/官方/公告/交易所来源可作为事实。
- 中信用/研报/新闻/政策来源只能写为“券商研报关注/媒体报道显示/政策文件指向”，不得写成公司确认。
- verified discussion 必须写为“社区讨论线索已与……相互印证”或“已验证讨论线索”，并且正文引用必须来自上方编号高信用来源。
- supported discussion 可写为“该线索获得新闻/研报支持，但仍非官方确认”。
- 多个低信用来源重复出现只表示“社区共振/市场关注”，不得写成事实确认。Phase 1 不使用 `corroborated` schema。
- unverified discussion 只能作为待验证观点，不得进入核心事实、结论或风险加分。
- 推论必须显式使用“可能/若/需要验证”，不得把推论写成事实。
- 中信用新闻/研报可进入风险观察文字，但不得生成结构化风险信号，不得影响风险评分。

Numbered source lines must include credit usage labels.

Example shape:

```text
[3] 标题: ... | 来源: 公告 | 信用层: high | 可用方式: core_fact_allowed | ...
```

### 4. Claim verification appendix

Update both appendices:

- `KnowledgeSynthesizer._format_claim_verification_context()`
- `SynthesisSkill._format_claim_verification_appendix()` legacy path

Required:

- Still explicitly says appendix is not a citation source.
- verified rows are described as `已验证讨论线索`.
- supported rows are described as `部分支持讨论线索`.
- unverified rows are described as `未验证市场讨论`.
- No corroborated row in Phase 1.
- States repeated low-credit-only claims are only community attention, not fact verification.

### 5. Core fact extraction prompt

Update `KnowledgeSynthesizer.extract_core_facts()` prompt:

Must exclude:

- 券商/媒体观点本身
- 社区讨论观点本身
- supported/unverified discussion
- 多源低信用社区共振线索
- analyst inference / prediction / “可能、预计、推测、若...则...”

Must require:

- Only high-credit official/announcement/exchange/confirmed references can become core facts.

### 6. Core fact provenance hard filter

Update `SynthesisSkill._enrich_core_fact_provenance()` so only valid high-credit fact-supporting sources can support core facts.

Allowed support:

- source family `公告`
- source family `官方`
- source family `交易所`
- source family `巨潮`
- any source with metadata equivalent to `source_credit >= 80` and `verification_status` or `source_type` indicating `confirmed_fact`

Rejected as core fact support:

- `研报`
- `新闻`
- `雪球`
- `知乎`
- `微信公众号` unless explicitly high-credit confirmed by metadata
- `AgentReach`
- `资金流向`
- unknown

Important R2 adjustment:

- The hard-filter helper must be able to inspect citation metadata containing `item.extra`, `source_credit`, or `source_type`.
- If current citation metadata does not include `item.extra`, extend `_fill_citation_metadata()` to preserve enough safe metadata for deterministic filtering.
- Do not add URLs/content to prompt-visible claim verification summary.

Invalid ref behavior:

- Do not drop invalid core facts in Phase 1.
- Mark them `provenance_status: invalid_ref`.
- Existing `DeepAnalysisRenderer` owns display of invalid refs; preserve or test that it renders them as invalid/unknown.
- Ensure invalid refs do not feed scoring, position advice, final recommendation, or numbered citations. This should already be true; add focused tests if needed.

## Required Tests

Add/update tests before implementation where possible.

### KnowledgeSynthesizer tests

- Prompt contains credit usage rules before numbered sources.
- Numbered source line includes source credit / usage label for:
  - announcement
  - report
  - news
  - Xueqiu/social
  - WeChat
- Claim verification appendix labels verified/supported/unverified with required wording.
- Appendix still says it is not a citation source.
- Prompt says repeated low-credit-only discussion is community attention, not fact verification.
- Core fact extraction prompt excludes professional observations, community claims, low-credit corroboration, and inference.

### SynthesisSkill tests

- `derive_synthesis_usage()` fallback for legacy adapters:
  - Announcement -> high/core_fact_allowed
  - Report -> medium/professional_observation
  - News -> medium/professional_observation
  - WeChat -> explicit configured tier/usage
  - Xueqiu/Zhihu -> low/discussion_only
  - unknown -> background_limited
- AgentReach uses `extra.source_credit` when available.
- Core fact provenance rejects refs that only point to news/report/community/AgentReach/fundflow.
- Core fact provenance accepts announcement/official/exchange/high-credit confirmed source.
- `test_core_fact_hard_filter_uses_source_credit`: non-announcement label with `source_credit >= 80` and `confirmed_fact` can support core fact.
- `test_invalid_ref_core_fact_does_not_affect_output`: invalid_ref facts are rendered/audited only and do not enter scoring/recommendations.
- Legacy `_build_prompt()` includes credit usage rules and labels.
- Existing prompt previous-narratives ordering remains stable.

### Existing focused tests to run

```text
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py -q
```

Also run related regression:

```text
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_source_intake_evidence_renderer.py -q
```

## Completion Notes

Write notes to:

- `docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-claude-notes.md`

Notes must include:

- Files changed
- Which helpers were added and where
- Exact hard-filter allowed/rejected source rules
- How invalid_ref core facts are handled
- Whether WeChat fallback is medium or low and why
- Test results
- Any deviations from this task
- Blockers, if any

## Stop Conditions

Stop and report if:

- You need to modify scoring/risk/technical/EV/report generation outside allowed files.
- You need to change claim verification schema to implement Phase 1.
- You need to run an LLM or generate a report to verify.
- Tests reveal unrelated broad failures.
