# Claude Notes: Core Fact Provenance

## Summary

Added deterministic provenance metadata to the core-facts base: `source_refs` are produced by the LLM from narrative citation markers, and `source_labels`, `evidence_type`, and `provenance_status` are derived in code from existing citation metadata. The "核心事实基座" table now includes an "证据" column showing the provenance family and status.

## Files Changed

- `scripts/utils/knowledge_synthesizer.py`
  - Updated `extract_core_facts()` prompt to request `source_refs` from narrative `[^n]` markers.
  - Added normalization of `source_refs`: convert numeric strings to ints, drop non-positive/non-integer refs, deduplicate, cap at 3.
  - Strip inline `[1]`/`[^1]` citation markers from `fact` and `data` fields.
  - Old rows without `source_refs` normalize to `[]`.

- `scripts/utils/report_skills/synthesis_skills.py`
  - Added `_enrich_core_fact_provenance()` called after `_fill_citation_metadata()`.
  - Handles int-keyed and numeric-string-keyed citations.
  - Normalizes fine-grained source platforms to families (`知乎`, `雪球`, `研报`, `公告`, `资金流向`, `新闻`).
  - Excludes Agent-Reach sources from supporting provenance.
  - Caps `source_labels` to 2 unique labels.
  - Derives `evidence_type` and `provenance_status` (`supported`, `partially_supported`, `missing_ref`, `invalid_ref`).
  - Preserves old fact rows and their order; does not mutate citation metadata.

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - Added "证据" column to the core-facts table.
  - Rendered evidence cells:
    - `supported`: `雪球、研报 (mixed)`
    - `partially_supported`: `雪球 (community, 部分引用无效)`
    - `missing_ref`: `未绑定引用 (unknown)`
    - `invalid_ref`: `引用无效 (unknown)`
  - Does not render `[^n]` markers in the evidence cell.
  - Old-style facts without provenance render as `未绑定引用 (unknown)`.

- `tests/utils/test_knowledge_synthesizer.py`
  - Added 4 tests for `source_refs` normalization and citation-marker stripping.

- `tests/reporter/test_synthesis_skills.py`
  - Added 14 tests for deterministic enrichment covering supported, missing, invalid, partially supported, source family normalization, Agent-Reach exclusion, label cap, order preservation, citation immutability, and evidence-type derivation.

- `tests/reporter/test_deep_analysis_renderer.py`
  - Added 5 tests for the new evidence column, old-style facts, partial/invalid states, and absence of `[^` markers.

- `docs/agent_workflow/2026-06-14-core-fact-provenance-claude-notes.md` (new)

## Tests Run

Required focused tests:

```bash
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py -q
```

```text
46 passed in 2.05s
```

Optional broader tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

```text
46 passed in 31.62s
```

## Prompt Change Summary

The `extract_core_facts()` prompt now asks for:

```json
{
  "fact_id": 1,
  "fact": "2025年营收",
  "data": "8.22亿元，同比+73.4%",
  "confidence": "高",
  "source_refs": [2]
}
```

Constraints added:

- `source_refs` must be copied from `[^n]` markers already in the narrative.
- Output `[]` if no citation supports the fact.
- Do not invent source IDs.
- Do not include `[1]` or `[^1]` markers in `fact`/`data` fields.

## Sample Enriched Core Fact Output

```python
{
  'fact_id': 1,
  'fact': '营收增长',
  'data': '10%',
  'confidence': '高',
  'source_refs': [1, 2],
  'source_labels': ['雪球', '研报'],
  'evidence_type': 'mixed',
  'provenance_status': 'supported'
}
```

## Sample Rendered Core Facts Table

```markdown
## 三、核心事实基座

| # | 事实 | 数据/来源 | 证据 | 置信度 |
|---|---|-----------|------|--------|
| 1 | 营收增长 | 10% | 雪球、研报 (mixed) | 高 |
| 2 | 客户定点 | 未披露 | 未绑定引用 (unknown) | 低 |
```

## Deviations From Task

- None. The implementation follows the task and design documents.

## Blockers

- None.

## Notes

- Agent-Reach sources are excluded from provenance support. A fact referencing only Agent-Reach refs receives `invalid_ref`.
- The enrichment step is fully deterministic and does not call any LLM, browser, or external service.
- Old-style `core_facts` without new fields continue to render without crashing.
- No scoring, risk, technical analysis, EV, position sizing, or final recommendation logic was modified.
- No Agent-Reach renderer/fetch/quality code was modified.
- No `knowledge/`, `data/raw/`, or `reports/` files were written.
