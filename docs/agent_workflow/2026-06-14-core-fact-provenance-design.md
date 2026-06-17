# Core Fact Provenance Design

## Goal

Improve the "核心事实基座" so each fact can show where it came from, instead of only showing `fact/data/confidence`.

The current pipeline extracts `core_facts` from already synthesized narratives. Those narratives contain numbered citations, but the extracted fact rows do not preserve citation refs or evidence type. This makes the fact base look more authoritative than its provenance supports.

## Current Behavior

Path:

1. `KnowledgeSynthesizer._synthesize_theme()` generates five narrative sections with `[^n]` citations.
2. `KnowledgeSynthesizer.extract_core_facts()` asks the LLM to extract 8-12 facts from those narratives.
3. The JSON output is normalized to:

```json
{"fact_id": 1, "fact": "...", "data": "...", "confidence": "高"}
```

4. `SynthesisSkill._fill_citation_metadata()` fills `synthesis["citations"]` metadata from `SynthesisItem`.
5. `DeepAnalysisRenderer._core_facts_table()` renders only fact/data/confidence.

Issue:

- The fact text may be valid, but the table does not show which citation IDs support it.
- If the LLM extracts a fact without preserving citation markers, the table cannot expose that weakness.
- There is no distinction between announcement/research/community/news support.

## Design Principles

- Preserve existing compatibility: old `core_facts` without new fields must still render.
- Do not add new data sources.
- Do not let Agent-Reach become a numbered source through this work.
- Do not change scoring, risk, technical analysis, EV, recommendation, or pipeline order.
- Prefer deterministic enrichment from existing `citations` metadata over LLM-generated source names.
- Treat missing provenance as visible uncertainty, not as a crash.

## Options Considered

### Option A: Prompt-only provenance

Ask `extract_core_facts()` to output `source_refs` and `evidence_type`.

Pros:

- Smallest code change.
- Directly captures citation IDs from the narrative.

Cons:

- LLM may invent source labels or evidence type.
- Harder to guarantee source type correctness.

### Option B: LLM refs + deterministic enrichment

Ask `extract_core_facts()` to output only `source_refs`, then enrich facts in code using `synthesis["citations"]`.

Pros:

- LLM only copies citation numbers already visible in narratives.
- Code derives source labels/types from existing citation metadata.
- Missing/invalid refs can be flagged deterministically.

Cons:

- Slightly more code and tests.

### Option C: Deterministic extraction from narratives only

Parse sentences and citations without using LLM extraction.

Pros:

- Fully deterministic.

Cons:

- Chinese financial fact extraction becomes brittle.
- Likely worse fact quality without a larger extraction engine.

## Chosen Approach

Use Option B.

## Proposed Data Model

`core_facts` remain a list of dictionaries. Add optional fields:

```json
{
  "fact_id": 1,
  "fact": "黑芝麻智能C1236芯片进入比亚迪供应链",
  "data": "获得天神之眼C定点，处于产能爬坡期",
  "confidence": "高",
  "source_refs": [18, 5],
  "source_labels": ["雪球", "研报"],
  "evidence_type": "mixed",
  "provenance_status": "supported"
}
```

Field rules:

- `source_refs`: list of positive integers copied from citation markers in the narratives.
- `source_labels`: derived from `synthesis["citations"][ref]["source"]`, normalized to source families and capped to 2 unique labels.
- Agent-Reach sources are never accepted as supporting provenance. If they appear defensively in citation metadata, ignore them for `source_labels` and support status.
- `evidence_type`: derived from `source_labels`.
  - `announcement` when all labels are announcement/company disclosure style.
  - `research_report` when all labels are research report style.
  - `community` when all labels are social/community style.
  - `news` when all labels are news style.
  - `fundflow` when all labels are fund-flow style.
  - `mixed` when multiple evidence families are present.
  - `unknown` when no valid refs exist.
- `provenance_status`:
  - `supported`: at least one valid `source_ref` maps to citation metadata.
  - `partially_supported`: at least one valid non-Agent-Reach ref maps to citation metadata, but some refs are invalid or excluded.
  - `missing_ref`: `source_refs` empty.
  - `invalid_ref`: refs exist but none map to citations.

## Prompt Change

Update `KnowledgeSynthesizer.extract_core_facts()` prompt:

- Require each fact to include `source_refs`.
- `source_refs` must be copied from citation markers in the analysis text.
- If a fact has no citation marker, output an empty array.
- Do not invent source IDs.
- Keep `fact_id/fact/data/confidence`.

Example output:

```json
[
  {
    "fact_id": 1,
    "fact": "2025年营收",
    "data": "8.22亿元，同比+73.4%",
    "confidence": "高",
    "source_refs": [2]
  }
]
```

Normalization:

- Accept old rows without `source_refs`; normalize to `[]`.
- Convert numeric strings to ints.
- Drop non-positive/non-integer refs.
- Cap refs per fact to 3.
- Strip citation markers from `fact` and `data` during normalization so the table does not render inline `[1]` or `[^1]` markers inside cells.

## Deterministic Enrichment

Add a helper in `SynthesisSkill`, after `_fill_citation_metadata()`:

```python
result = self._fill_citation_metadata(result, items)
result = self._enrich_core_fact_provenance(result)
```

The helper:

- Reads `result["core_facts"]` and `result["citations"]`.
- Preserves old fact rows.
- Adds `source_labels`, `evidence_type`, and `provenance_status`.
- Handles both int-keyed and numeric-string-keyed `citations`.
- Normalizes fine-grained source platforms to source families:
  - `知乎全网(网易)`, `知乎全网(新浪)`, `知乎` -> `知乎`
  - `雪球`, `xueqiu` -> `雪球`
  - `研报`, `券商研报` -> `研报`
  - `公告`, `公司公告` -> `公告`
  - `资金流向`, `fundflow` -> `资金流向`
  - `新闻`, `news` -> `新闻`
- Maps `雪球` and `知乎` to `community` intentionally.
- Excludes `AgentReach(...)` / `Agent-Reach` sources from supporting provenance.
- Does not remove facts.
- Does not mutate citation metadata.

This keeps provenance enrichment outside the LLM and close to citation metadata.

## Rendering

Update `DeepAnalysisRenderer._core_facts_table()` columns from:

```markdown
| # | 事实 | 数据/来源 | 置信度 |
```

to:

```markdown
| # | 事实 | 数据/来源 | 证据 | 置信度 |
```

Evidence cell rendering:

- `supported`: `雪球、研报 (mixed)`
- `partially_supported`: `雪球 (community, 部分引用无效)`
- `missing_ref`: `未绑定引用 / unknown`
- `invalid_ref`: `引用无效 / unknown`

Backward compatibility:

- Old facts without provenance render as `未绑定引用 / unknown`.
- Existing tests that only assert fact text still pass after update.

## Failure Modes

- LLM omits `source_refs`: visible as `未绑定引用`, not hidden.
- LLM outputs invalid refs: visible as `引用无效`.
- LLM invents refs outside citations: ignored for support and flagged. If at least one other ref is valid, status becomes `partially_supported`.
- LLM copies or invents refs that would point to claim-verification-only context: those entries are not in `citations`, so they become invalid. Claim-verification context is not accepted as provenance.
- Fact is supported by community-only evidence: rendered as community, not disguised as official.
- A fact has both official and community support: rendered as mixed.
- Agent-Reach source labels are excluded even if they appear defensively in citation metadata.

## Tests

Focused tests should be added before implementation:

1. `KnowledgeSynthesizer.extract_core_facts()` normalizes `source_refs` from JSON output.
2. Missing `source_refs` keeps backward compatibility with `[]`.
3. Invalid/non-integer refs are dropped.
4. `SynthesisSkill._enrich_core_fact_provenance()` marks supported facts and derives labels/type.
5. Empty refs become `missing_ref`.
6. Unknown refs become `invalid_ref`.
7. `DeepAnalysisRenderer` renders the new evidence column.
8. Old-style facts still render without crashing.
9. String-keyed citations map correctly.
10. Mixed valid/invalid refs become `partially_supported`.
11. `知乎全网(...)` normalizes to `知乎`, and `雪球`/`知乎` map to `community`.
12. Agent-Reach citations are excluded from `source_labels`.
13. `fact` and `data` cells strip inline `[1]` / `[^1]` markers.

Suggested commands:

```bash
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py -q
```

## Acceptance Criteria

- Focused tests pass.
- Existing report generation remains compatible with old cached/fake `core_facts`.
- No Agent-Reach evidence becomes numbered citations.
- Report quality check still passes on 黑芝麻智能 fast-test.
- Because this changes the core-fact extraction prompt, user review of one sample core-facts table is mandatory before considering the prompt change accepted.

## Files Expected To Change

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `docs/agent_workflow/2026-06-14-core-fact-provenance-claude-notes.md`

## Files That Must Not Change

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_*.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `config/stocks.json`
- `knowledge/`
- `data/raw/`
- generated reports, except runtime validation outputs

## Design Delta After Round 1

Accepted Round 1 adjustments:

- Do not render `[^n]` citation markers in the core-facts evidence cell. Render source family and evidence type only.
- Add `partially_supported` for mixed valid/invalid refs.
- Normalize source platforms to stable families before deriving labels and evidence type.
- Cap `source_labels` to 2 and `source_refs` to 3.
- Strip inline `[1]` and `[^1]` markers from `fact` / `data` table cells during normalization or rendering.
- Exclude Agent-Reach sources from supporting provenance, even if future citation metadata accidentally includes them.
- Treat sample fast-test core-facts table review as mandatory because this touches an LLM extraction prompt.

No R2 required before implementation unless implementation reveals poor `source_refs` quality or broad prompt drift.

## Round 1 Feedback

### Status

**Ready to implement** — with minor design deltas and additional test coverage.

The proposed Option B (LLM `source_refs` + deterministic enrichment) is compatible with the current `KnowledgeSynthesizer`/`SynthesisSkill` flow and satisfies the stated constraints. It does not change scoring, risk, technical analysis, EV, recommendation, or pipeline order. No blocker was found.

### Findings

#### [medium] Renderer evidence cell could be misread as new citations
The proposed rendering `[^2][^5] / 雪球、研报 / mixed` places existing citation markers in the core-facts table. A reader may confuse this with new citations or think the table itself is being cited. The design already forbids Agent-Reach from becoming numbered citations, but the visual pattern remains similar to narrative citations.

#### [medium] Claim-verification context could still leak into `source_refs`
The `extract_core_facts()` prompt will scan narratives that may have been influenced by the claim-verification appendix. Although the appendix explicitly says it cannot be cited with `[^n]`, the LLM could still attribute a fact to a claim-verification item if the same fact also appears in a numbered source. The deterministic enrichment step only validates that refs map to `citations`, which does not include claim-verification entries, so invented refs will fall to `invalid_ref`. This is acceptable but should be documented as a defense-in-depth boundary, not a guarantee.

#### [medium] `source_platform` values are too granular for stable `source_labels`
`source_adapter.py` produces labels like `知乎全网(网易)`, `知乎全网(新浪)`, etc. If the renderer shows `知乎全网(网易)` as a source label, the table becomes noisy and the `evidence_type` derivation may not match the intended family. The design should normalize platform names to a small family set (`知乎`, `雪球`, `研报`, `公告`, `资金流向`, `新闻`) before deriving `evidence_type`.

#### [low] Old-style cached `core_facts` must be explicitly covered
The design states backward compatibility but the proposed renderer test list does not include a dedicated test for facts that lack all new fields. Because `SynthesisSkill.run()` stores `core_facts` in the context and `DeepAnalysisRenderer` reads it from the context (not only from `synthesis["core_facts"]`), cached report inputs may contain old rows. A regression test should cover this path.

#### [low] String-keyed `citations` dict needs explicit handling
`_fill_citation_metadata()` converts string keys to ints where possible, but `_enrich_core_fact_provenance()` should use the same lookup logic. If the enrichment helper assumes `citations` keys are ints, it may miss refs when the LLM returns string numbers or when citations come from a legacy cache.

#### [low] `evidence_type` derivation is reasonable but not exhaustive
The six-type model (`announcement`, `research_report`, `community`, `news`, `fundflow`, `mixed`, `unknown`) covers current source families. However, `xueqiu` posts are mapped to `雪球` which the design implies is `community`; `知乎` is also `community`. This is acceptable for this phase, but the design should state that `community` intentionally includes both forum sources.

#### [low] Fact count and quality risk from prompt change
Adding `source_refs` to the `extract_core_facts()` prompt is a small change, but any prompt change can affect the number of facts extracted, their phrasing, or the confidence distribution. The acceptance criterion already requires a human sample review; this should be treated as mandatory, not optional.

### Recommendations

1. **Renderer evidence cell format**: Use a less citation-like display. Suggested:
   ```markdown
   | 雪球、研报 (mixed) |
   | 未绑定引用 (unknown) |
   | 引用无效 (unknown) |
   ```
   If citation numbers must remain visible, separate them clearly: `雪球、研报 | refs: 2, 5 | mixed`.

2. **Normalize `source_platform` to family labels** in `_enrich_core_fact_provenance()` before deriving `source_labels` and `evidence_type`. Strip the `知乎全网(...)` parenthetical or map it to `知乎`.

3. **Cap `source_labels` to 2 unique labels** in the renderer to keep the table readable. The design currently says 3; 2 is safer for narrow columns.

4. **Document claim-verification boundary explicitly**: state that claim-verification claims are not in `citations`, so any `source_refs` pointing to them will be classified as `invalid_ref` and rendered as `引用无效`.

5. **Add focused tests**:
   - `DeepAnalysisRenderer` renders old-style facts without new fields and does not crash.
   - `SynthesisSkill._enrich_core_fact_provenance()` handles string-keyed citations.
   - `KnowledgeSynthesizer.extract_core_facts()` normalizes missing `source_refs` to `[]`, string numbers to ints, and drops non-integer refs.
   - All-empty and all-invalid `source_refs` produce `missing_ref` and `invalid_ref` respectively.
   - `AgentReach` is never present in `citations`, so it can never appear as a `source_label`.

6. **Mandatory sample review**: Before accepting the prompt change, run one full fast-test report for 黑芝麻智能 and visually inspect the rendered core-facts table for fact count, quality, and provenance accuracy.

### Open Questions

1. Should `provenance_status` also distinguish `partially_supported` when some refs are valid and some are invalid? The current binary `supported`/`invalid_ref` may hide partial support.
2. Should the renderer show citation numbers at all, or only source family and evidence type? Showing numbers may encourage readers to treat the core-facts table as a primary citation layer.
3. How should `fact`/`data` fields containing existing citations like `[1]` or `[^1]` be handled? The current design does not mention stripping or escaping them in the table.
4. Should `source_refs` be capped per fact to 3 instead of 5? More refs usually mean more noise; fewer refs force the LLM to pick the strongest sources.

### 是否需要 R2

**不需要完整 R2**。当前设计基本 ready，只需在实现前把上述 minor deltas 落进设计或测试计划即可。如果实现后发现 LLM 返回的 `source_refs` 质量差（例如大量 `invalid_ref` 或事实数量显著下降），再触发 R2 也不迟。
