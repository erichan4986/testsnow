# Claude Implementation Notes: Agent-Reach Claim/Risk Bridge

Date: 2026-06-14

## Files Changed

### Created

- `scripts/utils/claim_risk_signals.py` — pure helper that derives `structured_risk_signals` from a full `ClaimVerificationPlan` using conservative regex/polarity phrase matching.
- `scripts/utils/report_skills/claim_risk_signal_skill.py` — pipeline skill inserted between `SynthesisSkill` and `scoring_skill`.
- `tests/utils/test_claim_risk_signals.py` — false-positive/true-positive regression tests and plan behavior tests.
- `tests/reporter/test_claim_risk_signal_skill.py` — skill behavior tests.
- `tests/reporter/test_claim_risk_signal_isolation.py` — Agent-Reach isolation test.

### Modified

- `scripts/utils/report_skills/__init__.py` — added `claim_risk_signal_skill` import/export and `enable_claim_risk_signals` parameter to `build_stock_report_pipeline`.
- `scripts/utils/stock_reporter.py` — reads `claim_verification.risk_signals` config, passes `enable_claim_risk_signals` to pipeline builder and input, and passes `claim_verification_base_dir` when either claim verification or risk signals are enabled.
- `tests/reporter/test_pipeline_integration.py` — added skill count and order tests.
- `tests/reporter/test_stock_reporter_agent_reach_config.py` — added default/risk_signals/independent/base_dir pass-through tests, updated existing mocks for new pipeline signature.
- `tests/reporter/test_scoring_engine_risk.py` — added `claim_verification` source label and double-count regression tests.

## Tests Run and Results

Focused tests:

```bash
python3 -m pytest tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py -q
# 66 passed
```

Integration/config/scoring regression:

```bash
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_scoring_engine_risk.py -q
# 55 passed
```

Existing Agent-Reach/evidence/claim tests:

```bash
python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py tests/reporter/test_agent_reach_quality_skill.py -q
# 126 passed
```

Isolation test:

```bash
python3 -m pytest tests/reporter/test_claim_risk_signal_isolation.py -q
# 1 passed
```

## Risk Phrase False-Positive Protections

Implemented in `claim_risk_signals.py`:

- **Risk and exclusion regexes per signal**: a signal is emitted only if a risk regex matches AND no exclusion regex for the same signal matches.
- **技术路线风险**: risk phrases include `未通过认证`, `未获认证`, `认证受阻`, `技术路线不确定`, `功能安全风险`, `架构迭代风险`, `技术替代风险`. Exclusions use negative lookbehind `(?<!未)` for `通过/获得/获.*认证`, plus `ASIL-D.*认证`, `功能安全认证`, `技术突破`, `技术.*领先`.
- **竞争格局恶化**: risk phrases include `竞争格局恶化`, `竞争加剧`, `价格战`, `降价压力`, `份额下滑`, `被.*替代` (excluding negated substitution), `竞品挤压`, `替代风险`. Exclusions include `难以被替代`, `不被替代`, `未被替代`, `竞争力提升`, `份额提升`, `份额.*增长`.
- **盈利压力**: risk phrases include `毛利率承压`, `毛利率下滑`, `毛利压缩`, `费用扩张`, `利润侵蚀`, `盈利压力`, `亏损扩大`, `亏损加剧`. Exclusions include `毛利率提升`, `毛利率改善`, `盈利改善`, `扭亏`, `亏损收窄`, `亏损减少`, `亏损改善`, `费用率下降`, `费用控制`, `利润增长`.
- **资金流出**: risk phrases include `资金净流出`, `主力净流出`, `减持压力`, `做空压力`, `退通风险`, `流动性恶化`. Exclusions include `港股通纳入`, `纳入港股通`, `流动性改善`, `资金净流入`, `主力净流入`, `增持`, `回购`.
- **Evidence text is sanitized** after matching: URLs, file paths, citation markers `[n]`/`[^n]`, and `rawid...` tokens are stripped; whitespace collapsed; then truncated once to 180 chars.
- **Deduplication** uses the full plan before applying `max_signals` cap.

## Pipeline / Config Wiring

- `build_stock_report_pipeline(..., enable_claim_risk_signals=False)` inserts `claim_risk_signal_skill` after `SynthesisSkill` and before `scoring_skill` only when enabled.
- `PerStockReporter` reads `agent_reach.claim_verification.risk_signals` (independent of `claim_verification.enabled`) and passes it through.
- `claim_verification.base_dir`, `max_verified`, `max_supported`, `max_unverified` are passed to pipeline input when either synthesis claim verification or risk signals are enabled.
- Default behavior unchanged: `enable_claim_risk_signals=False`, default pipeline remains 11 skills.
- Skill counts:
  - default: 11
  - `enable_claim_risk_signals=True`: 12
  - `enable_agent_reach=True`: 14
  - `enable_agent_reach=True, enable_evidence_notes=True`: 15
  - all three enabled: 16

## Protected Resources

- `config/stocks.json` — not modified.
- `knowledge/**` — not modified by implementation tests (tests use temporary dirs only).
- `reports/**` — not modified by implementation tests.
- `data/raw/**` — not modified.
- `scripts/utils/reporter/scoring_engine.py`, `scripts/utils/knowledge_synthesizer.py`, `scripts/utils/report_skills/synthesis_skills.py`, `scripts/utils/report_quality.py` — not modified.
- No network, LLM, browser, Chrome/CDP, Xueqiu, or Zhihu access used.
- No full report generation run.

## Deviations

- `stock_reporter.py` no longer sets `enable_claim_verification_context=True`. The original code set this only when `claim_verification.enabled=True`. Since `SynthesisSkill` already reads `claim_verification_base_dir`/`max_*` keys to build the summary, and the new risk-signal skill does not depend on `claim_verification_summary`, the boolean context flag was not needed for this task. Existing synthesis tests still pass.
- The isolation test confirms the bridge only writes `structured_risk_signals`, `claim_risk_signal_status`, `claim_risk_signal_summary`, and `claim_risk_signal_error` to context; it does not mutate `synthesis_text`, `core_facts`, or citations.

## Blockers

None.
