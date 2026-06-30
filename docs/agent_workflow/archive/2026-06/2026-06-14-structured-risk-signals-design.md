# Structured Risk Signals Design

## Goal

Stabilize the "综合风险评分" so small LLM wording changes do not directly change risk score.

Current issue observed in 黑芝麻智能 runtime:

- Previous risk score: `4.0/10`
- Current risk score: `5.5/10`
- Delta came from `竞争格局恶化 +1.5`
- Root cause: `risk_score_section()` scans `synthesis_text` for free-form keywords such as `降价`, `价格战`, `不确定性`, `减持`.

This phase makes qualitative risk scoring more structured and explainable while keeping existing quantitative rules intact.

## Current Behavior

`RiskRenderer` calls:

```python
risk_score_section(..., synthesis_text=synthesis_text)
```

`risk_score_section()` adds deterministic quantitative risks:

- valuation overheat
- monthly price rise
- Xueqiu sentiment overheat
- technical breakdown
- poor liquidity

Then it scans LLM narrative text:

```python
if any(keyword in synthesis_text):
    risk_factors.append((signal_name, "LLM 合成文本识别", score))
    total_risk += score
```

Problem:

- The same underlying data can produce different risk scores when the LLM uses different wording.
- The report does not show matched terms or evidence snippets.
- A generic phrase like `降价周期` can trigger `竞争格局恶化` even if the narrative is not saying competition has worsened.

## Design Principles

- Do not change valuation, technical, liquidity, or sentiment quantitative risk rules in this phase.
- Do not connect Agent-Reach or claim verification yet.
- Do not remove qualitative risk information from the report; downgrade it from automatic scoring to explicit observation unless structured signals are provided.
- Keep backward compatibility for callers of `risk_score_section()`.
- Make every scored qualitative factor explainable by structured fields.

## Chosen Approach

Split qualitative risk into two layers:

1. **Structured qualitative risk signals** can affect score.
2. **Free-text LLM keyword observations** are displayed for review but do not affect score by default.

This keeps current risk section informative without letting LLM wording move the score.

## Proposed API

Extend `risk_score_section()`:

```python
def risk_score_section(
    stock_name,
    posts,
    stock_raw,
    quote,
    consensus,
    industry_fwd_pe,
    watch_points_md="",
    synthesis_text="",
    structured_risk_signals=None,
    score_llm_keyword_risks=False,
):
    ...
```

Defaults:

- `structured_risk_signals=None`
- `score_llm_keyword_risks=False`

Backward compatibility:

- Existing calls still work.
- Existing `synthesis_text` keyword matches are rendered as observations, but do not add points unless `score_llm_keyword_risks=True`.

## Structured Signal Shape

Each structured signal is a dict:

```python
{
    "name": "竞争格局恶化",
    "score": 1.5,
    "confidence": 80,
    "source": "claim_verification",
    "evidence_text": "地平线营收规模与毛利率显著领先，黑芝麻仍以价换量。",
    "matched_terms": ["毛利率差距", "以价换量"],
    "status": "verified"
}
```

Scoring rules:

- `status == "verified"` can add full score.
- `status == "supported"` can add at most 50% score, rounded to 0.5 increments.
- `status == "unverified"` / missing status does not add score.
- `confidence < 60` does not add score.
- `score` is capped to the configured maximum for that signal name.
- Unknown signal names are ignored for scoring and rendered as observations.
- Unknown or empty `source` values render as `外部来源`.
- `evidence_text` and `matched_terms` must be sanitized before rendering: strip `[n]` and `[^n]` markers.
- Duplicate signal names render at most one observation row, preferring the highest-confidence evidence. If confidence ties, prefer the higher score.
- Signals with `confidence < 60` or `status=unverified` do not score, but still render as observations when they have a known or unknown signal name.

Allowed signal names and max scores:

- `业绩预期下调`: 1.5
- `竞争格局恶化`: 1.5
- `盈利压力`: 1.0
- `资金流出`: 1.0
- `技术路线风险`: 1.0

## LLM Keyword Observations

Keep the existing keyword list, but change its default effect:

- If `score_llm_keyword_risks=False`, keyword matches render in a separate subsection:

```markdown
### LLM文本风险观察（不计分）

| 风险信号 | 命中词 | 说明 |
|----------|--------|------|
| 竞争格局恶化 | 降价 | 自由文本命中，仅提示人工复核 |
```

- If `score_llm_keyword_risks=True`, preserve old scoring behavior but make status explicit:

```markdown
| 竞争格局恶化 | LLM关键词命中: 降价 | +1.5 |
```

Production default should be `False`.

This default intentionally changes report output for stocks whose risk score previously relied on free-text LLM keyword scoring. It is a safety correction, not a compatibility bug.

## Renderer Flow

`RiskRenderer` should pass optional structured signals from context:

```python
structured_risk_signals = ctx.get("structured_risk_signals", [])
score_llm_keyword_risks = bool(ctx.get("score_llm_keyword_risks", False))
```

Then call:

```python
risk_score_section(
    ...,
    synthesis_text=synthesis_text,
    structured_risk_signals=structured_risk_signals,
    score_llm_keyword_risks=score_llm_keyword_risks,
)
```

No existing pipeline skill needs to produce `structured_risk_signals` yet. This phase only creates the stable scoring surface.

## Report Output

The main risk-factor table remains:

```markdown
| 风险因子 | 状态 | 加分 |
```

For structured scored signals:

```markdown
| 竞争格局恶化 | verified / claim_verification / 地平线营收规模... | +1.5 |
```

For free-text observations:

```markdown
### LLM文本风险观察（不计分）

| 风险信号 | 命中词 | 说明 |
|----------|--------|------|
| 竞争格局恶化 | 降价 | 自由文本命中，仅提示人工复核 |
```

## Failure Modes

- LLM wording changes: observations may change, but score remains stable by default.
- Empty `structured_risk_signals`: only quantitative risks score.
- Malformed signal dict: ignored for scoring, optionally shown as unscored observation if it has a name.
- Unknown signal name: ignored for scoring.
- Supported but low confidence signal: no score.
- Duplicate signal name: keep the highest valid scored signal and avoid double counting.
- Duplicate observations: render one row per signal name, using the highest-confidence evidence.
- Keyword matches with `score_llm_keyword_risks=False`: always render the observation subsection; never silently discard them.
- Evidence text contains citation markers: strip them before rendering.

## Tests

Add focused tests around `risk_score_section()` and `RiskRenderer`:

1. Existing quantitative risks still score.
2. `synthesis_text` keyword match does not add score by default.
3. `synthesis_text` keyword match appears in `LLM文本风险观察（不计分）`.
4. `score_llm_keyword_risks=True` preserves old keyword scoring behavior.
5. Verified structured signal adds full score.
6. Supported structured signal adds half score.
7. Unverified / low-confidence structured signal does not score.
8. Unknown structured signal does not score.
9. Duplicate structured signal does not double count.
10. `RiskRenderer` passes `structured_risk_signals` and `score_llm_keyword_risks` from context.
11. `structured_risk_signals=[]` with keyword matches keeps score unchanged and renders observation table.
12. Duplicate structured signals render one observation row and score only once.
13. Evidence text or matched terms containing `[1]` / `[^1]` are sanitized.
14. `RiskRenderer` default context without `structured_risk_signals` uses safe defaults.

Suggested command:

```bash
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
```

If no dedicated scoring-engine risk test file exists, create:

```text
tests/reporter/test_scoring_engine_risk.py
```

## Acceptance Criteria

- Focused tests pass.
- 黑芝麻智能 fast-test report quality passes.
- With default settings, LLM keyword-only `竞争格局恶化` does not move the risk score.
- Risk report still displays keyword observations for human review.
- Implementation notes include before/after 黑芝麻智能 risk score behavior.
- No Agent-Reach / claim-verification integration is added in this phase.
- No scoring changes outside qualitative risk handling.

## Files Expected To Change

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `tests/reporter/test_risk_renderer.py`
- `tests/reporter/test_scoring_engine_risk.py`
- `docs/agent_workflow/2026-06-14-structured-risk-signals-claude-notes.md`

## Files That Must Not Change

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/claim_verification.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/report_skills/agent_reach_*`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/utils/reporter/technical_*.py`
- `config/stocks.json`
- `knowledge/`
- `data/raw/`
- generated reports, except runtime validation outputs

## Design Delta After Round 1

Accepted Round 1 adjustments:

- `score_llm_keyword_risks=False` is an intentional default behavior change. Runtime validation must record before/after risk score behavior for 黑芝麻智能.
- If LLM keyword matches exist and keyword scoring is disabled, `### LLM文本风险观察（不计分）` must always render.
- Duplicate structured or observation signals render one row per signal name, preferring highest confidence and then highest score.
- Unknown `source` values render as `外部来源`.
- Rendered `evidence_text` and `matched_terms` must strip `[n]` and `[^n]`.
- Low-confidence or unverified structured signals do not score, but remain visible as observations.
- No R2 is required before implementation.

## Round 1 Feedback

### Status

**Ready to implement** — with minor clarifications and test additions.

The design correctly isolates qualitative risk scoring from LLM wording drift by defaulting `score_llm_keyword_risks=False` and introducing a structured signal surface. It does not touch forbidden files or connect Agent-Reach / claim verification / core-fact provenance to risk scoring.

### Findings

#### [medium] `score_llm_keyword_risks=False` changes existing report output by default
The design states backward compatibility for callers, but the default behavior change means existing reports will stop scoring LLM keyword risks. This is the intended safety improvement, but it should be called out explicitly in the task notes and verified with a before/after fast-test risk score comparison for 黑芝麻智能.

#### [medium] Risk observations may still be hidden if renderer does not always emit the new subsection
The design requires a separate `### LLM文本风险观察（不计分）` subsection when keyword matches exist but `score_llm_keyword_risks=False`. If `risk_score_section()` is called without an explicit signal that matches occurred, this subsection may be omitted. The current design relies on scanning `synthesis_text` inside `risk_score_section()`, so it should work, but the renderer output contract should be explicit: keyword matches must always be shown, never silently dropped.

#### [medium] Duplicate signal handling needs a clear rule for observations too
The design says "keep the highest valid scored signal and avoid double counting" for duplicate signal names. It should also state how duplicates are rendered in the observation table: one row per unique signal name with the highest-confidence evidence, or all rows with a note. Otherwise the report may look inconsistent.

#### [low] structured signal `source` field is permissive
The schema allows any string in `source`. While scoring ignores it, rendering might display unsupported source names. Since this phase does not integrate claim verification, consider restricting rendered `source` values or treating unknown ones generically as "外部来源" to avoid implying unsupported provenance.

#### [low] `matched_terms` may leak inline `[1]`/`[^1]` if not sanitized
If a signal producer copies text from narratives, `matched_terms` or `evidence_text` could contain citation markers. The design does not mention sanitizing these. Rendering them could create false citations. Add a note to strip `[^n]`/`[n]` from evidence text before rendering.

#### [low] No test for empty `structured_risk_signals` + keyword matches
The test list covers many cases but does not explicitly assert that when `structured_risk_signals=[]` and `synthesis_text` contains keyword matches, the score excludes keyword points while still showing the observation table. This is the primary runtime scenario for the next report run.

### Recommendations

1. **Explicit default-behavior note**: In the implementation notes, document that `score_llm_keyword_risks=False` intentionally lowers risk scores that previously relied on free-text keywords, and list the expected before/after behavior for 黑芝麻智能.

2. **Always render keyword observations**: Ensure `risk_score_section()` emits the `LLM文本风险观察（不计分）` subsection whenever keyword matches exist and scoring is disabled, even if the main risk-factor table is otherwise empty.

3. **Deduplicate observation rows**: Render at most one observation row per unique signal name. If multiple signals share a name, show the highest-confidence one and optionally append "等" to the matched terms.

4. **Sanitize evidence text**: Strip `[^n]` and `[n]` markers from `evidence_text` and `matched_terms` before rendering to avoid accidental citations.

5. **Add tests**:
   - `structured_risk_signals=[]` with keyword matches → score unchanged, observation table rendered.
   - `score_llm_keyword_risks=True` with keyword matches → old scoring restored.
   - Duplicate structured signals → only highest scored counted and only one observation row.
   - Evidence text containing `[^1]` is sanitized in output.
   - `RiskRenderer` default context (`structured_risk_signals` absent) uses safe defaults.

6. **Schema guardrails**: If `source` is rendered, normalize unknown values to "外部来源" or similar neutral label so the table does not imply unverified provenance.

### Open Questions

1. Should `score_llm_keyword_risks=True` still be exposed as a config option, or kept as an internal escape hatch only? Exposing it in `config/stocks.json` could be misused.
2. Is there a plan for a future skill to produce `structured_risk_signals`, or will it remain a manual/placeholder surface for this phase? The design says no skill needs to produce it yet, but knowing the next consumer helps define schema stability.
3. Should `confidence < 60` signals be rendered in the observation table even though they do not score? Hiding them might lose weak-but-relevant clues.
4. How should signals with `status=unverified` but high `confidence` be treated? The current rule says no score, but the observation may still be valuable.

### R2 Needed

**No.** The design is ready to implement after incorporating the minor clarifications above. No fundamental rework is required.
