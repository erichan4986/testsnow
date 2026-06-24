# Broker Research Digest Synthesis Display Design

Date: 2026-06-24

Status: Fast draft

## 1. Goal

Let persisted broker research digest notes help §四深度分析, without changing canonical synthesis, core facts, scoring, risk scoring, or fact confirmation.

This is display-only:

- `ctx["synthesis"]` remains baseline.
- `ctx["synthesis_text"]` remains baseline.
- `ctx["core_facts"]` remain baseline.
- `ctx["synthesis_sources"]` remain baseline.
- `ctx["synthesis_display"]` may include broker research digest material.
- report renderers may continue preferring `synthesis_display`.

## 2. Source

Read existing notes from:

```text
knowledge/10-Stocks/<stock>/broker_research_digest/*.md
```

Only accept notes with:

- `source_type: broker_research`
- `claim_status: professional_analysis`
- `source_credit: 72`
- `confirmed_fact: false`
- `scoring_eligible: false`
- `risk_score_eligible: false`

Read the excerpt from body section:

```text
## Broker Research Excerpt

> ...
```

Do not read raw PDFs in synthesis. PDF parsing stays in the material preparation / preview layer.

## 3. Selection

Default budget:

- `max_display_items = 5`
- dedupe by `viewpoint_cluster`; keep at most one card per cluster first
- if budget remains, allow additional non-duplicate clusters
- skip `display_only: true` notes unless explicitly configured later

Reason: 中际旭创 showed many near-identical 1Q26 broker notes. The display layer should add diversity, not stack broker consensus.

## 4. Integration

Add a reader helper, parallel to `periodic_report_narrative_card_synthesis_items.py`:

```text
scripts/utils/broker_research_digest_synthesis_items.py
```

Add optional injection in `SynthesisSkill.run()`:

- existing order: baseline → fulltext → annual narrative cards
- new order: baseline → fulltext → annual narrative cards → broker research digest
- write `ctx["synthesis_display"]` once from all display extras
- when broker notes are included, set:
  - `ctx["synthesis_text_with_broker_research_digest"]`

Do not change `KnowledgeSynthesizer` prompt.

## 5. Config

Use source-intake config flag:

```json
"broker_research_digest_synthesis_display": {
  "enabled": true,
  "max_display_items": 5
}
```

`stock_reporter.py` should pass:

- `include_broker_research_digest_in_synthesis_display`
- `broker_research_digest_max_display_items`

Only when source intake is enabled, matching the periodic narrative card display pattern.

## 6. Allowed Files

Allowed:

- `scripts/utils/broker_research_digest_synthesis_items.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/stock_reporter.py`
- `tools/ci_grep_gates.sh`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`
- `tests/reporter/test_fulltext_material_isolation.py`
- `tests/utils/test_broker_research_digest_synthesis_items.py`
- `tests/utils/test_ci_grep_gates.py`

Forbidden:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- risk renderers / risk scoring code
- technical analysis code
- `periodic_report_filing_fact_note_writer.py`
- raw PDF extraction rules unless needed by tests
- real `knowledge/`, `reports/`, `data/raw/`

## 7. Tests

Required focused tests:

1. Reader parses broker digest note body blockquote into `SynthesisItem`.
2. Reader rejects non-broker notes and notes missing guardrail frontmatter.
3. Reader dedupes by `viewpoint_cluster`.
4. `SynthesisSkill` with broker display on keeps baseline invariants:
   - `synthesis`
   - `synthesis_text`
   - `core_facts`
   - `synthesis_sources`
5. Both-on test: fulltext + annual narrative cards + broker digest all share one `ctx["synthesis_display"]`.
6. Config test: `stock_reporter.py` passes broker display flags only when source intake is enabled.
7. CI gate test: `broker_research` cannot enter scoring/risk/Knowledge persistence hard paths.

Run:

```bash
python3 -m pytest \
  tests/utils/test_broker_research_digest_synthesis_items.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_fulltext_material_isolation.py \
  tests/utils/test_ci_grep_gates.py -q

bash tools/ci_grep_gates.sh
git diff --check
```

## 8. Stop Conditions

Stop and report if implementation requires:

- changing `KnowledgeSynthesizer` prompt or synthesis prompt wording
- changing scoring/risk behavior
- reading raw PDFs during report synthesis
- writing real Knowledge during tests
- changing broker digest extraction/card generation rules
- modifying more files than allowed above

## 9. Claude Implementation Prompt

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一个小范围 TDD 实现。

目标：
实现 broker research digest notes 的 synthesis display-only 接入。读取 knowledge/10-Stocks/<stock>/broker_research_digest/*.md，把合格 broker_research digest notes 转成 display-only SynthesisItem，并在 SynthesisSkill 的 display synthesis 中与 fulltext、annual narrative cards 共用 ctx["synthesis_display"]。

先读：
- docs/agent_workflow/2026-06-24-broker-research-synthesis-display-design.md
- scripts/utils/report_skills/synthesis_skills.py
- scripts/utils/periodic_report_narrative_card_synthesis_items.py
- scripts/utils/stock_reporter.py

允许修改：
- scripts/utils/broker_research_digest_synthesis_items.py
- scripts/utils/report_skills/synthesis_skills.py
- scripts/utils/stock_reporter.py
- tools/ci_grep_gates.sh
- tests/reporter/test_synthesis_skills.py
- tests/reporter/test_stock_reporter_source_intake_config.py
- tests/reporter/test_fulltext_material_isolation.py
- tests/utils/test_broker_research_digest_synthesis_items.py
- tests/utils/test_ci_grep_gates.py

禁止修改：
- scripts/utils/knowledge_synthesizer.py
- scripts/utils/reporter/scoring_engine.py
- risk renderer / risk scoring code
- technical analysis code
- raw PDF extraction/card generation rules
- real data/raw、reports、knowledge
- 与任务无关的重构或格式化

要求：
1. TDD：先写失败测试，再实现最小代码。
2. broker_research digest 只能 display-only，不得进入 confirmed_fact、评分、风险计分、canonical synthesis。
3. SynthesisSkill 必须只写一次 ctx["synthesis_display"]，顺序为 fulltext → annual narrative cards → broker research digest。
4. 新 reader 只读 Knowledge note，不读 PDF。
5. 跑：
   python3 -m pytest tests/utils/test_broker_research_digest_synthesis_items.py tests/reporter/test_synthesis_skills.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_fulltext_material_isolation.py tests/utils/test_ci_grep_gates.py -q
   bash tools/ci_grep_gates.sh
   git diff --check

完成后回复：
- 改了哪些文件
- 测试结果
- 是否触发 stop condition
- broker_research 是否仍保持 display-only
```
