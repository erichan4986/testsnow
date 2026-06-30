# Verified Claim Summary Section Implementation Notes

Date: 2026-06-14

## Summary

Implemented a read-only `### 官方事实核验摘要` subsection in the deep analysis section.

The section renders verified/supported claim verification rows from `claim_verification_summary`, without adding numbered citations, mutating synthesis/core facts, or affecting scoring/risk/EV/technical logic.

## Files Changed

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - Added optional claim verification summary rendering.
  - Supports both design shorthand buckets (`verified`, `supported`) and real summary buckets (`verified_claims`, `supported_claims`).
  - Sanitizes citation markers, URLs, `AgentReach(web)` labels, table pipes, and `Title:` prefixes.
  - Caps rendered rows at 6.
- `scripts/utils/report_skills/claim_risk_signal_skill.py`
  - Reuses the already-built `ClaimVerificationPlan` to set `claim_verification_summary` on ctx.
  - Does not rebuild the plan in the renderer.
- `tests/reporter/test_deep_analysis_renderer.py`
  - Added focused renderer tests for rendering, sanitization, malformed input, row cap, fallback source label, no mutation, and real summary bucket names.
- `tests/reporter/test_claim_risk_signal_skill.py`
  - Added test proving claim risk bridge exposes `claim_verification_summary` for rendering.

## Verification

- `python3 -m pytest tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_claim_risk_signal_skill.py tests/reporter/test_assembly_skills.py -q`
  - 34 passed
- `python3 -m pytest tests/reporter/test_scoring_engine_risk.py tests/utils/test_claim_risk_signals.py tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py -q`
  - 191 passed
- `cd scripts && python3 run_中简科技.py --fast-test`
  - generated Markdown, HTML, PDF
- `python3 scripts/check_report_quality.py reports/中简科技_20260614.md`
  - PASS

## Runtime Observation

`reports/中简科技_20260614.md` now includes:

```markdown
### 官方事实核验摘要

| 结论 | 核验状态 | 支撑来源 | 置信度 |
|------|----------|----------|--------|
| 2 、 研发费用1.18亿元 ， 同比增长37.02% | verified | 1225106812.PDF | 84 |
| 报告期内 ， 影响公司业绩变动的主要原因： 1 、 客户对公司部分产品的需求量阶段性减少导致发货暂时减少 ， 其中收入下降约50%-60% | verified | 1225106812.PDF | 84 |
| 2 、 报告期内 ， 围绕新领域的应用需求 ， 公司持续加大研发投入 ， 研发费用同比增长约 175%-185% | verified | 1225106812.PDF | 84 |
```

Agent-Reach remains in its separate observation section. The new subsection does not include `[^n]` citations.

## Known Runtime Warnings

- Eastmoney/akshare proxy failures appeared for some market/index calls, but the report generated successfully and passed the quality gate.
- `H100027` competitor financial fetch still emits a non-blocking `NoneType` warning.

## Blockers

None.

## Follow-up: Official Disclosure Display Cleanup

Implemented after the initial verified-claim summary section because the first runtime report still exposed raw Jina/cninfo PDF metadata in report-facing tables.

Additional changes:

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
  - Maps known cninfo announcement PDF ids to human-readable titles:
    - `1225145344.PDF` -> `2026年第一季度报告`
    - `1225106812.PDF` -> `2026年第一季度业绩预告`
    - `1225102392.PDF` -> `补缴税款及滞纳金事项公告`
    - `1225362219.PDF` -> `2025年年度权益分派实施公告`
  - Removes display-only Jina/PDF boilerplate such as `Published Time`, `Number of Pages`, `证券代码`, `证券简称`, repeated disclosure headings, and common cninfo disclosure disclaimer text.
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - Applies the same known cninfo PDF id mapping to official fact summary source labels.
- Tests:
  - Added cninfo PDF display-cleanup cases to `tests/reporter/test_agent_reach_evidence_renderer.py`.
  - Added known cninfo title mapping case to `tests/reporter/test_deep_analysis_renderer.py`.

Follow-up verification:

- `python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_assembly_skills.py -q`
  - 67 passed
- `python3 -m pytest tests/reporter/test_claim_risk_signal_skill.py tests/reporter/test_scoring_engine_risk.py tests/utils/test_claim_risk_signals.py tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py -q`
  - 199 passed
- `cd scripts && python3 run_中简科技.py --fast-test`
  - generated Markdown, HTML, PDF
- `python3 scripts/check_report_quality.py reports/中简科技_20260614.md`
  - PASS

Runtime cleanup result:

- `reports/中简科技_20260614.md` no longer contains raw `Published Time`, `Number of Pages`, `1225106812.PDF`, `1225145344.PDF`, `1225102392.PDF`, `1225362219.PDF`, `证券代码`, or `证券简称` in the rendered report.
- Agent-Reach remains isolated in its own observation section.
