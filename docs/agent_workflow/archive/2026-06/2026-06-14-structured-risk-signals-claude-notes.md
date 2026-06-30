# Claude Notes: Structured Risk Signals

## Summary

Stabilized qualitative risk scoring by defaulting LLM free-text keyword matches to non-scoring observations. Only structured risk signals can affect the risk score, and only when they meet status/confidence/name rules. The change keeps risk information visible while preventing LLM wording drift from moving the score.

## Files Changed

- `scripts/utils/reporter/scoring_engine.py`
  - Extended `risk_score_section()` signature with:
    - `structured_risk_signals: Optional[List[Dict]] = None`
    - `score_llm_keyword_risks: bool = False`
  - Quantitative risk rules remain unchanged.
  - LLM keyword matches are always collected but only add score when `score_llm_keyword_risks=True`.
  - Added structured signal processing:
    - Recognized names: `业绩预期下调`, `竞争格局恶化`, `盈利压力`, `资金流出`, `技术路线风险`
    - `verified` + confidence >= 60 adds full score, capped at signal max.
    - `supported` + confidence >= 60 adds at most half score, rounded to 0.5.
    - `unverified`, low confidence, unknown names do not score.
    - Duplicate signal names score once (highest valid score) and render one observation row.
  - Renders two observation subsections:
    - `### 结构化风险观察（不计分）`
    - `### LLM文本风险观察（不计分）`
  - Added `_sanitize_citation_markers()` to strip `[n]`/`[^n]` from evidence text and matched terms.

- `scripts/utils/reporter/sections/risk_renderer.py`
  - Reads `structured_risk_signals` and `score_llm_keyword_risks` from context with safe defaults.
  - Passes both to `risk_score_section()`.

- `tests/reporter/test_risk_renderer.py`
  - Added 3 tests proving renderer passes the new parameters and defaults safely.

- `tests/reporter/test_scoring_engine_risk.py` (new)
  - Added 14 focused tests covering quantitative risks, keyword observations, structured signal scoring, duplicate handling, sanitization, and unknown signals.

- `docs/agent_workflow/2026-06-14-structured-risk-signals-claude-notes.md` (new)

## Tests Run

Required focused tests:

```bash
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
```

```text
21 passed in 0.08s
```

Optional assembly tests:

```bash
python3 -m pytest tests/reporter/test_assembly_skills.py -q
```

```text
9 passed in 28.94s
```

## Default Behavior Change

- **Before**: `synthesis_text` containing keywords like `价格战` or `降价` automatically added `竞争格局恶化 +1.5` to the risk score.
- **After**: those keyword matches render under `### LLM文本风险观察（不计分）` and do **not** change the risk score unless `score_llm_keyword_risks=True`.
- Structured risk signals are the only new path that can add qualitative risk points, and they require an explicit `verified`/`supported` status, confidence >= 60, and a known signal name.

## Keyword Observation Output Sample

Input: `synthesis_text="价格战加剧，降价压力大，毛利率承压。"`

```markdown
## 综合风险评分

### 风险等级: 0.0/10（低风险）

> **仓位建议**: 积极配置，最大仓位 20%

当前未触发主要风险因子，整体风险可控。

### LLM文本风险观察（不计分）

| 风险信号 | 命中词 | 说明 |
|----------|--------|------|
| 竞争格局恶化 | 价格战, 降价 | 自由文本命中，仅提示人工复核 |
| 盈利压力 | 毛利率承压 | 自由文本命中，仅提示人工复核 |
```

## Deviations From Task

- None. The implementation follows the task and design documents.

## Blockers

- None.

## Notes

- No Agent-Reach, claim verification, synthesis, technical analysis, valuation, EV, position sizing, or final recommendation code was modified.
- No config, knowledge, data/raw, or generated reports were changed.
- No external network, LLM, browser, CDP, Xueqiu, or Zhihu access was used during focused tests.
- The escape hatch `score_llm_keyword_risks=True` preserves the old keyword scoring behavior for backward compatibility.
