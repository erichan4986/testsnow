# Claude Implementation Task: Agent-Reach Claim/Risk Bridge

Read first:

- `AGENTS.md`
- `docs/agent_workflow/2026-06-14-agent-reach-claim-risk-bridge-design.md`

## Goal

Implement one combined, gated bridge:

```text
ClaimVerificationPlan
  -> conservative claim_risk_signals
  -> structured_risk_signals
  -> existing risk_score_section()
```

This should connect the existing claim-verification framework to the already implemented structured risk signal API. It must not let Agent-Reach directly enter synthesis, numbered citations, EV, technical analysis, or final recommendation.

## Allowed Files

Create:

- `scripts/utils/claim_risk_signals.py`
- `scripts/utils/report_skills/claim_risk_signal_skill.py`
- `tests/utils/test_claim_risk_signals.py`
- `tests/reporter/test_claim_risk_signal_skill.py`
- `docs/agent_workflow/2026-06-14-agent-reach-claim-risk-bridge-claude-notes.md`

Modify:

- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `tests/reporter/test_scoring_engine_risk.py` only if needed for a focused label/double-count regression

Stop before modifying any other file.

## Forbidden

- Do not modify `config/stocks.json`.
- Do not modify `knowledge/**`, `reports/**`, or `data/raw/**` during implementation tests.
- Do not modify `scripts/utils/reporter/scoring_engine.py`.
- Do not modify `scripts/utils/knowledge_synthesizer.py`.
- Do not modify `scripts/utils/report_skills/synthesis_skills.py` unless a test proves an unavoidable bug; stop and report first if this seems needed.
- Do not modify `scripts/utils/report_quality.py`.
- Do not modify technical analysis, EV, scoring pillars, final recommendation, Xueqiu scraping, Playwright, Chrome/CDP, or Agent-Reach fetching logic.
- Do not run full report generation in this implementation round.
- Do not access network, LLM, browser, Chrome/CDP, Xueqiu, or Zhihu.

## Required Implementation

### 1. `claim_risk_signals.py`

Implement a pure helper:

```python
def derive_structured_risk_signals_from_plan(plan, max_signals: int = 5) -> list[dict]:
    ...
```

Input:

- full `ClaimVerificationPlan` from `scripts/utils/claim_verification.py`

Output:

- list of dicts accepted by `risk_score_section(structured_risk_signals=...)`

Output shape:

```python
{
    "name": "盈利压力",
    "score": 1.0,
    "confidence": 76,
    "source": "claim_verification",
    "evidence_text": "黑芝麻智能风险线索：毛利率承压...",
    "matched_terms": ["毛利率承压"],
    "status": "verified",
}
```

Derivation rules:

- Build a lookup from `plan.low_credit_claims` by `claim_id`.
- Iterate all `plan.verifications`.
- Match against full low-credit `claim_text` plus verification reasons.
- Do not use `summarize_claim_verification_plan()` output.
- Do not truncate before matching.
- Sanitize/truncate evidence text only after matching and deduplication.

Status mapping:

| Verification action | Signal status | Default confidence |
|---------------------|---------------|--------------------|
| `verified` | `verified` | verification confidence or 70 |
| `supported` | `supported` | verification confidence or 60 |
| `needs_review` | `unverified` | 0 |
| `unverified` | `unverified` | 0 |

Known signal names and scores:

- `业绩预期下调`: 1.5
- `竞争格局恶化`: 1.5
- `盈利压力`: 1.0
- `资金流出`: 1.0
- `技术路线风险`: 1.0

Dedup:

- At most one signal per name.
- Prefer `verified` > `supported` > `unverified`.
- Then higher confidence.
- Then longer sanitized evidence text.
- Apply `max_signals` only after deduping the full plan.

Sanitize `evidence_text`:

- strip URLs
- strip local file paths
- strip raw ids if present
- strip `[n]` and `[^n]`
- collapse whitespace
- truncate once to 180 chars

### 2. Conservative Phrase Matching

Implement phrase matching with explicit risk regexes and exclusion regexes. Do not use broad substring checks.

For each signal:

1. A risk regex must match.
2. No exclusion regex for the same signal may match.
3. Bare domain terms are not enough.

Required false-positive behavior:

- `A2000U 获 ISO 26262 ASIL-D 最高功能安全认证` -> no `技术路线风险`
- bare `地平线` / `Mobileye` / `竞品` -> no `竞争格局恶化`
- `毛利率提升` / `毛利率改善` / `亏损收窄` / `亏损减少` / `亏损改善` / `费用率下降` / `费用控制有效` / `利润增长` -> no `盈利压力`
- `港股通纳入` / `流动性改善` -> no `资金流出`
- `难以被替代` / `不被替代` / `未被替代` -> no `竞争格局恶化`

Required true-positive behavior:

- `未通过认证` -> `技术路线风险`
- `未获认证` -> `技术路线风险`
- `技术路线不确定` -> `技术路线风险`
- `毛利率承压` -> `盈利压力`
- `价格战` -> `竞争格局恶化`
- `退通风险` -> `资金流出`

Use deterministic regex/polarity guards. The implementation must ensure `未通过认证` is not suppressed by positive `通过.*认证` exclusions.

### 3. New Pipeline Skill

Create `scripts/utils/report_skills/claim_risk_signal_skill.py`.

Skill name: `claim_risk_signal`

Behavior:

Disabled:

```python
structured_risk_signals = []
claim_risk_signal_status = "disabled"
claim_risk_signal_error = ""
```

Enabled:

- Read `stock_name`.
- Resolve base dir from `claim_verification_base_dir`, defaulting to repo-root `knowledge/`.
- Call `build_claim_verification_plan(stock_name, base_dir, dry_run=True)`.
- Call `derive_structured_risk_signals_from_plan(plan)`.
- Set:

```python
structured_risk_signals = signals
claim_risk_signal_status = "ok" if signals else "empty"
claim_risk_signal_summary = {
    "signal_count": len(signals),
    "signals": [{"name": ..., "status": ..., "confidence": ...}, ...],
}
claim_risk_signal_error = ""
```

Error:

- Catch all exceptions.
- Set empty signals, status `error`, and short error string.
- Do not abort pipeline.

The skill must not rely on `claim_verification_summary`, because that summary is truncated and prompt-facing.

### 4. Pipeline Builder

Update `build_stock_report_pipeline(...)`:

```python
def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
    enable_claim_risk_signals: bool = False,
) -> SkillPipeline:
```

Insert `claim_risk_signal_skill` after `SynthesisSkill(llm_client=...)` and before `scoring_skill` only when enabled.

Expected counts:

- default: 11
- `enable_claim_risk_signals=True`: 12
- `enable_agent_reach=True`: 14
- `enable_agent_reach=True, enable_evidence_notes=True`: 15
- all three enabled: 16

### 5. PerStockReporter Config

Update `stock_reporter.py`:

```python
cv_cfg = ar_cfg.get("claim_verification", {}) or {}
claim_verification_enabled = bool(cv_cfg.get("enabled", False))
claim_risk_signals_enabled = bool(cv_cfg.get("risk_signals", False))

pipeline = build_stock_report_pipeline(
    enable_agent_reach=agent_reach_enabled,
    enable_evidence_notes=agent_reach_enabled and evidence_notes_enabled,
    enable_claim_risk_signals=claim_risk_signals_enabled,
)
```

`claim_verification.risk_signals=True` must work independently of `claim_verification.enabled`.

If `cv_cfg.base_dir` exists, pass it as `claim_verification_base_dir` so the new skill can use it.

Do not modify `config/stocks.json`.

## Required Tests

Write failing tests first.

### `tests/utils/test_claim_risk_signals.py`

Add tests for:

False positives:

- official ASIL-D certification news does not produce `技术路线风险`
- bare `地平线`, `Mobileye`, `竞品` do not produce `竞争格局恶化`
- `毛利率提升`, `毛利率改善`, `亏损收窄`, `亏损减少`, `亏损改善`, `费用率下降`, `费用控制有效`, `利润增长` do not produce `盈利压力`
- `港股通纳入`, `流动性改善` do not produce `资金流出`
- `难以被替代`, `不被替代`, `未被替代` do not produce `竞争格局恶化`

True positives:

- `未通过认证` and `未获认证` produce `技术路线风险`
- `技术路线不确定` produces `技术路线风险`
- `毛利率承压` produces `盈利压力`
- `价格战` produces `竞争格局恶化`
- `退通风险` produces `资金流出`

Plan behavior:

- Derives from full `ClaimVerificationPlan`, not summary.
- Dedup uses all verifications before `max_signals`.
- Highest-confidence verified signal wins.
- Evidence is matched before final display truncation.
- Sanitization removes URLs, file paths, and citation markers.
- Malformed confidence/status does not crash.

### `tests/reporter/test_claim_risk_signal_skill.py`

Add tests for:

- disabled skill returns empty signals and `disabled`
- enabled skill builds full plan from temp knowledge dir
- empty/missing knowledge dir returns `empty` without crash
- builder error returns `error` and empty signals
- skill does not use `claim_verification_summary`
- output `structured_risk_signals` can be passed to `risk_score_section()`

### `tests/reporter/test_pipeline_integration.py`

Add/update tests for:

- default count 11 unchanged
- risk_signals only count 12
- agent_reach only count 14
- agent_reach + evidence_notes count 15
- agent_reach + evidence_notes + claim_risk_signals count 16
- order includes `SynthesisSkill` -> `claim_risk_signal_skill` -> `scoring_skill`

### `tests/reporter/test_stock_reporter_agent_reach_config.py`

Add tests for:

- default reporter does not enable claim risk signals
- `claim_verification.risk_signals=True` passes `enable_claim_risk_signals=True`
- `risk_signals=True` works even when `claim_verification.enabled=False`
- `base_dir` is passed through for risk-signal skill
- other stocks/configs unaffected

### Isolation Test

Add a focused isolation test in the most appropriate existing/new test file:

- With `enable_claim_risk_signals=True`, the bridge only sets `structured_risk_signals`.
- Agent-Reach URLs/titles must not be added to `synthesis_text`, `core_facts`, or citation metadata by this bridge.
- Do not call LLM.

### Optional Scoring Test

If needed, add a small regression to `tests/reporter/test_scoring_engine_risk.py`:

- A signal with source `claim_verification` renders the source label.
- Existing LLM keyword observations plus structured signals do not double-count the same risk beyond structured scoring.

## Verification Commands

Run focused tests:

```bash
python3 -m pytest tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py -q
```

Run integration/config/scoring regression:

```bash
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_scoring_engine_risk.py -q
```

Run relevant existing Agent-Reach/evidence/claim tests:

```bash
python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py tests/reporter/test_agent_reach_quality_skill.py -q
```

Do not run full report generation in this implementation round.

## Notes Output

Write:

`docs/agent_workflow/2026-06-14-agent-reach-claim-risk-bridge-claude-notes.md`

Include:

- Files changed.
- Tests run and results.
- Summary of risk phrase false-positive protections.
- Summary of pipeline/config wiring.
- Confirmation that `config/stocks.json`, `knowledge/**`, `reports/**`, and `data/raw/**` were not modified by implementation tests.
- Deviations.
- Blockers.

## Stop Conditions

Stop and report before proceeding if:

- You need to modify files outside the allowed list.
- You need to change `scoring_engine.py`, `KnowledgeSynthesizer`, `synthesis_skills.py`, `report_quality.py`, technical analysis, EV, final recommendation, or Agent-Reach fetching.
- Tests require modifying `config/stocks.json`.
- You need to run network, LLM, browser, Chrome/CDP, Xueqiu, or Zhihu.
- The risk phrase rules cannot pass the required false-positive tests without becoming too broad.
