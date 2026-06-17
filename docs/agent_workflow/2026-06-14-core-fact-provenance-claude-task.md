# Claude Implementation Task: Core Fact Provenance

Read first:

- `docs/agent_workflow/2026-06-14-core-fact-provenance-design.md`

## Goal

Add provenance metadata to `core_facts` and render it in the "核心事实基座" table without changing scoring, risk, technical analysis, LLM narrative citations, Agent-Reach behavior, or pipeline order.

## Allowed Files

Modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`

Add:

- `docs/agent_workflow/2026-06-14-core-fact-provenance-claude-notes.md`

Stop before modifying any other file.

## Forbidden

- Do not modify scoring, risk, technical analysis, EV, position sizing, or final recommendation logic.
- Do not modify Agent-Reach renderer or fetch/quality logic.
- Do not add Agent-Reach to synthesis citations.
- Do not write `knowledge/`, `data/raw/`, or generated reports.
- Do not access external websites.
- Do not start Chrome/CDP or touch Xueqiu details.
- Do not run full report generation in the implementation round.

## Required Implementation

### 1. Normalize `source_refs` in `KnowledgeSynthesizer.extract_core_facts()`

Update the core-fact extraction prompt so the JSON schema asks for:

```json
{
  "fact_id": 1,
  "fact": "...",
  "data": "...",
  "confidence": "高",
  "source_refs": [2, 5]
}
```

Prompt constraints:

- `source_refs` must be copied from citation markers already present in the analysis text.
- If no citation marker supports the fact, output `[]`.
- Do not invent source IDs.
- Keep `fact_id`, `fact`, `data`, `confidence`.

Normalization rules:

- Old rows without `source_refs` normalize to `[]`.
- Numeric strings normalize to ints.
- Non-integer, zero, negative, and duplicate refs are dropped.
- Cap refs per fact at 3.
- Strip inline citation markers from `fact` and `data`: both `[1]` and `[^1]`.

### 2. Add deterministic enrichment in `SynthesisSkill`

After `_fill_citation_metadata(result, items)`, call a new helper:

```python
result = self._enrich_core_fact_provenance(result)
```

Helper behavior:

- Read `result["core_facts"]` and `result["citations"]`.
- Preserve old fact rows and existing fact order.
- Handle both int-keyed and numeric-string-keyed citations.
- Add:
  - `source_labels`
  - `evidence_type`
  - `provenance_status`

Source family normalization:

- `知乎全网(网易)`, `知乎全网(新浪)`, `知乎` -> `知乎`
- `雪球`, `xueqiu` -> `雪球`
- `研报`, `券商研报` -> `研报`
- `公告`, `公司公告` -> `公告`
- `资金流向`, `fundflow` -> `资金流向`
- `新闻`, `news` -> `新闻`

Evidence type:

- `announcement` for only `公告`
- `research_report` for only `研报`
- `community` for only `雪球`/`知乎`
- `news` for only `新闻`
- `fundflow` for only `资金流向`
- `mixed` for more than one family
- `unknown` when no accepted refs exist

Status:

- `supported`: all provided refs are accepted and mapped.
- `partially_supported`: at least one ref is accepted, but at least one ref is invalid or excluded.
- `missing_ref`: `source_refs` is empty.
- `invalid_ref`: refs exist but none are accepted.

Agent-Reach boundary:

- If a citation source is `AgentReach(...)`, `Agent-Reach`, or similar, exclude it from `source_labels` and support status.
- If a fact only references Agent-Reach refs, it should be `invalid_ref`, not `supported`.

Label cap:

- `source_labels` should contain at most 2 unique labels.

### 3. Render provenance in `DeepAnalysisRenderer`

Change core facts table columns to:

```markdown
| # | 事实 | 数据/来源 | 证据 | 置信度 |
```

Evidence cell:

- `supported`: `雪球、研报 (mixed)`
- `partially_supported`: `雪球 (community, 部分引用无效)`
- `missing_ref`: `未绑定引用 (unknown)`
- `invalid_ref`: `引用无效 (unknown)`

Do not render `[^n]` markers in the core-facts evidence cell.

Old-style facts without provenance must render as `未绑定引用 (unknown)` and must not crash.

## Required Tests

Write failing tests first, then implement.

### `tests/utils/test_knowledge_synthesizer.py`

Add tests for:

- `extract_core_facts()` normalizes `source_refs` from ints and numeric strings.
- Missing `source_refs` becomes `[]`.
- Invalid/non-positive/duplicate refs are dropped and refs are capped at 3.
- `fact` and `data` have `[1]` and `[^1]` markers stripped.

Use a fake client or monkeypatch `_call_llm`; do not call a real LLM.

### `tests/reporter/test_synthesis_skills.py`

Add tests for `_enrich_core_fact_provenance()`:

- Supported fact with int-keyed citations derives labels and type.
- Supported fact with string-keyed citations works.
- Empty refs becomes `missing_ref`.
- Unknown refs becomes `invalid_ref`.
- Mixed valid/invalid refs becomes `partially_supported`.
- `知乎全网(网易)` normalizes to `知乎`, and `雪球`/`知乎` derive `community`.
- Agent-Reach citation source is excluded and does not produce `source_labels`.

### `tests/reporter/test_deep_analysis_renderer.py`

Add tests for:

- New evidence column renders.
- Supported fact renders `雪球、研报 (mixed)` or equivalent source-family cell.
- Old-style fact without new fields renders `未绑定引用 (unknown)` and does not crash.
- Evidence cell does not contain `[^`.

## Verification Commands

Run:

```bash
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py -q
```

Optional if quick:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

Do not run the full report entry in this implementation round.

## Notes Output

Write:

`docs/agent_workflow/2026-06-14-core-fact-provenance-claude-notes.md`

Include:

- Files changed.
- Tests run and results.
- Sample rendered core facts row.
- Any prompt changes made.
- Any deviations.
- Any blocker.

## Stop Conditions

Stop and report if:

- You need to modify files outside the allowed list.
- You need to touch scoring, risk, technical analysis, Agent-Reach, report pipeline order, or generated data.
- Focused tests reveal broad unrelated failures.
- The prompt change requires real LLM validation before unit tests can pass.
