# Claude Implementation Task: Structured Risk Signals

Read first:

- `docs/agent_workflow/2026-06-14-structured-risk-signals-design.md`

## Goal

Stabilize qualitative risk scoring so LLM free-text wording no longer moves risk score by default.

This phase only changes qualitative risk handling inside the risk section. Do not connect Agent-Reach, claim verification, or core-fact provenance yet.

## Allowed Files

Modify:

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `tests/reporter/test_risk_renderer.py`

Create:

- `tests/reporter/test_scoring_engine_risk.py`
- `docs/agent_workflow/2026-06-14-structured-risk-signals-claude-notes.md`

Stop before modifying any other file.

## Forbidden

- Do not modify Agent-Reach code.
- Do not modify claim verification or evidence note writer code.
- Do not modify KnowledgeSynthesizer or synthesis skills.
- Do not modify technical analysis, valuation, EV, position sizing, or recommendation logic.
- Do not modify config, knowledge, data/raw, or generated reports.
- Do not run full report generation in the implementation round.
- Do not access external websites, browser, CDP, Xueqiu, Zhihu, or LLM.

## Required Implementation

### 1. Extend `risk_score_section()`

Add optional parameters:

```python
structured_risk_signals=None
score_llm_keyword_risks=False
```

Default behavior:

- Quantitative risk factors still score as before.
- LLM keyword matches from `synthesis_text` do **not** score by default.
- LLM keyword matches must render under:

```markdown
### LLM文本风险观察（不计分）
```

Compatibility escape hatch:

- If `score_llm_keyword_risks=True`, preserve old behavior: keyword matches add score.
- In this mode, the status should be explicit, e.g. `LLM关键词命中: 降价`.

### 2. Add structured risk signal scoring

Recognized signal names and max scores:

- `业绩预期下调`: 1.5
- `竞争格局恶化`: 1.5
- `盈利压力`: 1.0
- `资金流出`: 1.0
- `技术路线风险`: 1.0

Signal shape:

```python
{
    "name": "竞争格局恶化",
    "score": 1.5,
    "confidence": 80,
    "source": "claim_verification",
    "evidence_text": "地平线营收规模与毛利率显著领先。",
    "matched_terms": ["毛利率差距"],
    "status": "verified",
}
```

Scoring:

- `status == "verified"` and `confidence >= 60`: add full score, capped by signal max.
- `status == "supported"` and `confidence >= 60`: add at most half score, rounded to 0.5 increments.
- `status == "unverified"` or missing status: no score.
- `confidence < 60`: no score.
- Unknown signal names: no score.
- Duplicate signal names: score at most once, using highest valid score.

Observation rendering:

- Low-confidence, unverified, unknown, malformed, or duplicate signals may still render as observations.
- Render at most one observation row per signal name, preferring highest confidence, then highest score.
- Unknown/empty `source` renders as `外部来源`.
- Strip `[n]` and `[^n]` from `evidence_text` and `matched_terms` before rendering.

### 3. Update `RiskRenderer`

Read safe defaults from ctx:

```python
structured_risk_signals = ctx.get("structured_risk_signals", []) or []
score_llm_keyword_risks = bool(ctx.get("score_llm_keyword_risks", False))
```

Pass both into `risk_score_section()`.

Do not add config plumbing in this phase.

## Required Tests

Write failing tests first.

### `tests/reporter/test_scoring_engine_risk.py`

Add focused tests:

1. Quantitative risks still score.
2. `structured_risk_signals=[]` and `synthesis_text` keyword match: risk score excludes keyword points and renders `LLM文本风险观察（不计分）`.
3. `score_llm_keyword_risks=True` restores old keyword scoring.
4. Verified structured signal adds full score.
5. Supported structured signal adds half score.
6. Unverified structured signal does not score but renders observation.
7. Low-confidence structured signal does not score but renders observation.
8. Unknown signal name does not score but renders observation.
9. Duplicate structured signals score once using highest valid score and render one observation row.
10. Evidence text / matched terms containing `[1]` / `[^1]` are sanitized.

### `tests/reporter/test_risk_renderer.py`

Add tests:

1. Renderer passes `structured_risk_signals` to `risk_score_section()`.
2. Renderer passes `score_llm_keyword_risks` to `risk_score_section()`.
3. Renderer default context without these keys uses safe defaults and does not crash.

## Verification Commands

Run:

```bash
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
```

Optional if quick:

```bash
python3 -m pytest tests/reporter/test_assembly_skills.py -q
```

Do not run full report generation in this implementation round.

## Notes Output

Write:

`docs/agent_workflow/2026-06-14-structured-risk-signals-claude-notes.md`

Include:

- Files changed.
- Tests run and results.
- Summary of default behavior change.
- Example output for keyword observation not scoring.
- Any deviations.
- Any blocker.

## Runtime Validation Later

After implementation review, Codex will ask for local 黑芝麻智能 fast-test runtime validation. That validation must record before/after risk behavior:

- Previous keyword-scored behavior could produce `竞争格局恶化 +1.5`.
- New default behavior should show keyword observation but not add the +1.5 unless `score_llm_keyword_risks=True`.

## Stop Conditions

Stop and report if:

- You need to modify files outside the allowed list.
- You need to touch Agent-Reach, claim verification, synthesis, technical analysis, valuation, or generated data.
- Tests require real network, LLM, browser, CDP, Xueqiu, or Zhihu.
