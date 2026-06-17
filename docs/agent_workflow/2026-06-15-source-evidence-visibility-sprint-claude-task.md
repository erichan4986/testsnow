# Claude Task: Source Evidence Visibility Sprint

Date: 2026-06-15

## Goal

Implement the approved Source Evidence Visibility Sprint as one combined task.

Make Source Intake evidence visible in single-stock Markdown reports as a read-only, source-credit-aware section. This section must explain official / medium-credit source boundaries and must not affect scoring, risk, technical analysis, EV, LLM synthesis, citations, or final recommendations.

Read first:

- `docs/agent_workflow/2026-06-15-source-evidence-visibility-sprint-design.md`
- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

## Allowed Files

You may add or edit:

- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `tests/reporter/test_source_intake_evidence_renderer.py`
- `tests/reporter/test_assembly_skills.py`
- `docs/agent_workflow/2026-06-15-source-evidence-visibility-sprint-claude-notes.md`

Only if absolutely needed for existing test conventions:

- `tests/reporter/test_pipeline_integration.py`

## Forbidden Files / Areas

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/data_fetcher.py`
- technical analysis modules
- risk renderer logic except via assembly ordering if already required
- source intake collection/adapters
- claim verification helper logic
- `config/stocks.json`
- `knowledge/**` except runtime-generated evidence notes during validation
- `data/raw/**` except runtime-generated report input during validation
- `reports/**` except runtime-generated reports/images during validation

Do not:

- download broker research PDFs
- create numbered `[^n]` citations from Source Intake items
- run Xueqiu detail scraping, CDP, or logged-in Chrome automation
- refresh Zhihu collection or change LLM prompts

## Implementation Requirements

### 1. New Renderer

Add `SourceIntakeEvidenceRenderer`.

Render only when:

- `source_intake_enabled=True`
- `source_intake_status` is not disabled/error/empty
- there are usable `source_intake_items` or merged external evidence items from Source Intake

For empty Source Intake, return `""` to avoid report noise.

Section title:

```markdown
## Source Intake 分层证据观察
```

Required disclaimer:

```markdown
> 本节仅展示结构化外部证据来源分层，不参与综合评分、风险评分、技术面判断或最终建议。
> 官方公告可用于事实确认；新闻与券商研报仅作为专业观察或背景线索，不等同于官方事实。
```

### 2. Credit-Tier Summary

Generate this table dynamically from item metadata, not hard-coded counts:

| 来源类型 | 数量 | 信用等级 | 事实用途 | 状态 |
|----------|------|----------|----------|------|

Normalize labels:

- `exchange_announcement` -> `官方公告`
- `news` -> `东方财富新闻`
- `research_report` -> `券商研报摘要`
- unknown -> `其他来源`

Rules:

- `exchange_announcement` may show `confirmed_fact`.
- `news` and `research_report` must always render as `professional_observation` / background or professional observation, even if malformed metadata says otherwise.
- Use each bucket's actual source_credit values from item metadata; if multiple values appear, render a compact range such as `60-65`.

### 3. Representative Evidence Rows

Render at most 6 rows, priority:

1. official announcements
2. broker research
3. news
4. unknown

Columns:

| 时间 | 来源层级 | 证据摘要 | 信用 | 用途 |

Sanitize visible text:

- remove `[^n]` and `[n]`
- remove raw `AgentReach(...)`
- remove or truncate raw long URLs
- escape Markdown table pipes
- cap title/excerpt length so the table remains readable

Use `item.url` only as a plain URL if you decide to include it inside the Source Intake section. Do not create numbered citations.

### 4. Assembly Wiring

Register the new renderer in `ReportAssemblySkill.RENDERERS`:

- after `DeepAnalysisRenderer`
- before `AgentReachEvidenceRenderer`
- before `RiskRenderer`

Do not change HTML dashboard rendering unless the existing Markdown-to-HTML path automatically includes the new section. In notes, explicitly state whether the HTML dashboard includes the new Source Intake section.

### 5. Verified Claim Summary

Do not redesign this unless tests reveal an actual blocker. Existing `DeepAnalysisRenderer` hook should remain compatible.

## Tests

Write failing tests first, then implement.

Required renderer tests:

- disabled Source Intake renders `""`
- enabled but empty Source Intake renders `""`
- official announcements render as high-credit `confirmed_fact`
- news and research render as medium-credit `professional_observation`
- malformed `news` / `research_report` metadata claiming `confirmed_fact` is normalized down
- representative evidence rows are capped at 6
- citation markers and `AgentReach(...)` text are removed
- long raw URLs are not exposed in evidence summary text
- renderer does not mutate ctx or `SynthesisItem.extra`

Required assembly tests:

- new renderer is registered after deep analysis and before Agent-Reach/risk
- reports still render when Source Intake keys are absent
- Agent-Reach-only context does not render Source Intake section

Run focused tests:

```bash
python3 -m pytest tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

Also run relevant regression tests if touched:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_deep_analysis_renderer.py -q
```

## Runtime Validation

After tests pass, run fast-test validation for the three existing pilot stocks:

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
cd scripts && python3 run_中简科技.py --fast-test
cd scripts && python3 run_圣邦股份.py --fast-test
```

For each generated Markdown, run:

```bash
python3 scripts/check_report_quality.py reports/<generated>.md
```

Record:

- whether Markdown/HTML/PDF generated
- whether quality check PASS/WARNING/FAIL
- whether Source Intake section appears only where `source_intake_enabled=True`
- whether 黑芝麻智能 Agent-Reach evidence remains separate
- whether no Source Intake / Agent-Reach numbered citation pollution appears
- whether scoring/risk/EV/technical/final recommendation unexpectedly changed

If local network, akshare, PDF, or disk-space issues occur, record them and continue with whatever validation completed.

## Notes Output

Write:

- `docs/agent_workflow/2026-06-15-source-evidence-visibility-sprint-claude-notes.md`

Include:

- files changed
- tests run and results
- runtime validation table for three stocks
- whether HTML includes the section
- any generated report/evidence/cache files
- deviations
- blocker

## Stop Conditions

Stop and report before implementing if:

- you need to change scoring/risk/technical/EV/LLM prompt logic
- you need to modify Source Intake collection/adapters
- you need to download PDFs
- tests require broad unrelated rewrites
- runtime validation requires Xueqiu detail scraping, CDP, or Zhihu refresh
