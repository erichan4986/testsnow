# Codex Review: Agent-Reach Claim/Risk Bridge

Date: 2026-06-14

## Status

Accepted after Codex fix round.

The implementation matches the design direction:

- derives `structured_risk_signals` from a full `ClaimVerificationPlan`
- keeps the bridge disabled by default
- inserts the skill after synthesis and before scoring only when enabled
- uses conservative risk phrase + exclusion matching
- does not modify `config/stocks.json`
- does not write `knowledge/`, `reports/`, or `data/raw/`
- keeps Agent-Reach out of synthesis text, citations, core facts, and final recommendations

## Codex Findings And Fixes

### 1. Fixed: claim verification synthesis context regression

Claude's implementation removed `enable_claim_verification_context=True` from `stock_reporter.py` when `claim_verification.enabled=True`.

This was a regression from Phase 5. `SynthesisSkill` only builds the claim verification prompt appendix when `enable_claim_verification_context` is true; passing `claim_verification_base_dir` alone is not enough.

Codex restored the flag:

- `claim_verification.enabled=True` now sets `enable_claim_verification_context=True`
- `claim_verification.risk_signals=True` remains independent and does not enable synthesis context by itself
- both enabled together set both independent flags

Tests added/updated in `tests/reporter/test_stock_reporter_agent_reach_config.py`.

### 2. Fixed: citation sanitizer regex

`_CITATION_RE` in `claim_risk_signals.py` included an empty regex branch. Codex replaced it with the intended citation-only pattern.

### 3. Fixed: certification phrase-table edge case

The first implementation could still suppress some negative certification phrases with broad positive certification exclusions.

Codex tightened the technology-risk phrase table:

- risk now matches `未通过 ISO 26262 认证`, `未获 ASIL-D 认证`, and `未获得功能安全认证`
- positive certification exclusions now require explicit positive verbs such as `通过/获/获得...认证`
- standalone `ASIL-D.*认证` no longer suppresses risk phrases

Regression tests were added to `tests/utils/test_claim_risk_signals.py`.

## Verification

Commands run:

```bash
python3 -m pytest tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py -q
# 69 passed

python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_scoring_engine_risk.py -q
# 56 passed

python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py tests/reporter/test_agent_reach_quality_skill.py -q
# 126 passed

python3 -m pytest tests/reporter/test_claim_risk_signal_isolation.py tests/reporter/test_assembly_skills.py -q
# 10 passed
```

## Scope Check

Expected code/test files changed by this phase:

- `scripts/utils/claim_risk_signals.py`
- `scripts/utils/report_skills/claim_risk_signal_skill.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`
- `tests/utils/test_claim_risk_signals.py`
- `tests/reporter/test_claim_risk_signal_skill.py`
- `tests/reporter/test_claim_risk_signal_isolation.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `tests/reporter/test_scoring_engine_risk.py`

No runtime report was generated in this review.

The current worktree still contains unrelated pre-existing changes under `knowledge/`, `reports/`, docs, and earlier report-system files. They were not reverted or attributed to this phase.

## Runtime Next Step

Do not enable `claim_verification.risk_signals` in `config/stocks.json` without explicit user approval.

Recommended next validation is a controlled runtime using a temporary config path or a narrowly scoped local toggle, then compare:

- risk factor table
- `LLM文本风险观察（不计分）`
- structured claim-risk rows
- Agent-Reach isolation
- report quality check

## Controlled Runtime Validation

Codex ran a controlled Black Sesame fast-test with an in-process temporary toggle:

- `claim_verification.risk_signals=True`
- no `config/stocks.json` write
- no Xueqiu detail-page fetch
- fast-test Zhihu cache reuse

The first sandbox run was not treated as valid runtime evidence because network and browser permissions blocked DeepSeek/API/Kaleido calls. Codex reran the same temporary-toggle validation in the local non-sandbox environment.

Results from the valid local run:

- report generated: `reports/黑芝麻智能_20260614.md`
- dashboard generated: `reports/黑芝麻智能_20260614.html`
- PDF generated: `reports/黑芝麻智能_20260614.pdf`
- Agent-Reach audit generated: `reports/黑芝麻智能_20260614_agent_reach.json`
- report quality: `PASS: reports/黑芝麻智能_20260614.md`
- quality gate: `keep=18, demote=24, discard=100`
- Agent-Reach: `keep=6, demote=0, discard=0`, no audit `content` field
- `claim_risk_signal`: `status=empty count=0`
- risk score: `2.0/10`
- position advice guardrail: `趋势破坏期，以观望或防守仓位为主，建议 0-5%`
- `LLM文本风险观察（不计分）` remained visible
- no claim-verification structured risk rows were added
- one non-blocking akshare proxy failure occurred; mootdx fallback succeeded

Why the bridge produced no signals:

- `knowledge/10-Stocks/黑芝麻智能/evidence/` does not exist yet
- existing `knowledge/10-Stocks/黑芝麻智能/posts/*.md` files are old post notes without `claims` / `source_credit` frontmatter
- `build_claim_verification_plan("黑芝麻智能", "knowledge", dry_run=True)` returned `high=0, low=0, verifications=0`

Conclusion:

The runtime wiring works, but the current local knowledge base has no structured claim pool for the bridge to score. The next useful step is to explicitly enable/writerun Agent-Reach evidence notes for 黑芝麻智能, or separately migrate existing post notes into low-credit claim notes. Without that input layer, the claim-risk bridge will correctly remain empty.

## Evidence Note Write Validation

After user approval, Codex ran a local non-sandbox Black Sesame fast-test with temporary in-process toggles:

- `evidence_notes.enabled=True`
- `evidence_notes.dry_run=False`
- `claim_verification.risk_signals=True`
- no `config/stocks.json` write

Runtime result:

- `evidence_note_writer`: `status=written`
- generated 6 official evidence notes under `knowledge/10-Stocks/黑芝麻智能/evidence/`
- each note has `source_credit=85`
- each note has `claim_status=fact_candidate`
- each note has `agent_reach_quality_action=keep`
- quality scores were 80-85
- `check_report_quality.py reports/黑芝麻智能_20260614.md`: PASS
- PDF generation succeeded

Codex also fixed a metadata propagation bug discovered during validation:

- `agent_reach_quality_skill` now annotates keep/demote `SynthesisItem.extra` with `agent_reach_quality_score`, `agent_reach_quality_action`, and `agent_reach_quality_reasons`
- previously, evidence notes could be written with `agent_reach_quality_score: 0` even when the quality gate had scored the item 80+
- existing six Black Sesame evidence notes were corrected to match the audit scores

Focused verification after the fix:

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_evidence_note_skill.py tests/utils/test_evidence_note_writer.py -q
# 79 passed

python3 -m pytest tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py tests/reporter/test_claim_risk_signal_isolation.py -q
# 70 passed

python3 -m pytest tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py tests/reporter/test_pipeline_integration.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_claim_risk_signal_isolation.py -q
# 126 passed
```

Post-write claim verification state:

- `high_credit_claims=6`
- `low_credit_claims=0`
- `verifications=0`
- `structured_risk_signals=[]`

Material sufficiency assessment:

- sufficient for official high-credit fact candidates
- sufficient to validate Agent-Reach -> evidence notes -> high-credit claim pool
- not yet sufficient for risk-signal scoring, because there are no structured low-credit claims to verify against the official evidence

Next useful implementation step:

- create a low-credit claim extraction/migration path for existing Xueqiu/community post notes, or
- write a small non-LLM extractor that converts selected report/community observations into `unverified_claim` notes with conservative frontmatter.

Only after there is a low-credit claim pool can the bridge exercise the intended "high-credit verifies low-credit" risk-signal path.

## Lightweight Bridge Smoke Tool

Codex added a narrow runtime tool to avoid running the full report for every Agent-Reach/claim-risk iteration:

- `scripts/smoke_agent_reach_claim_bridge.py`
- tests: `tests/reporter/test_agent_reach_claim_bridge_smoke_script.py`

The script runs only:

- `agent_reach_query_skill`
- `agent_reach_fetch_skill`
- `agent_reach_quality_skill`
- optional `evidence_note_writer_skill`
- `build_claim_verification_plan`
- `derive_structured_risk_signals_from_plan`

It intentionally does not import or run:

- `PerStockReporter`
- `ZhihuCollector`
- `KnowledgeSynthesizer`
- full report pipeline
- scoring renderer
- chart/PDF/report assembly
- Xueqiu detail/CDP paths

Main usage:

```bash
python3 scripts/smoke_agent_reach_claim_bridge.py --stock 黑芝麻智能
python3 scripts/smoke_agent_reach_claim_bridge.py --stock 黑芝麻智能 --json
python3 scripts/smoke_agent_reach_claim_bridge.py --stock 黑芝麻智能 --write-evidence-notes
python3 scripts/smoke_agent_reach_claim_bridge.py --stock 黑芝麻智能 --write-evidence-notes --evidence-dry-run
python3 scripts/smoke_agent_reach_claim_bridge.py --stock 黑芝麻智能 --write-audit
```

Validation:

- sandbox run correctly showed network-blocked fetch status while still reading existing claim plan: `high=6, low=0`
- local non-sandbox dry-run completed in about 11 seconds
- local non-sandbox result: `keep=6, demote=0, discard=0`, `high=6, low=0`, `signals=[]`
- no evidence notes were written in the dry-run validation

Focused tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_claim_bridge_smoke_script.py -q
# 5 passed

python3 -m pytest tests/reporter/test_agent_reach_smoke_script.py tests/reporter/test_agent_reach_claim_bridge_smoke_script.py -q
# 18 passed

python3 -m pytest tests/reporter/test_agent_reach_claim_bridge_smoke_script.py tests/reporter/test_agent_reach_smoke_script.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_evidence_note_skill.py tests/utils/test_evidence_note_writer.py tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py tests/reporter/test_claim_risk_signal_isolation.py -q
# 167 passed
```

This tool should be the default runtime check for future work on:

- Agent-Reach source expansion
- evidence note write behavior
- claim verification plan inputs
- source-credit calibration
- claim-risk signal phrase rules

## Low-Credit Community Claim Pool

Codex added a local-only extractor for cached Xueqiu/community material:

- `scripts/utils/community_claim_note_writer.py`
- `scripts/smoke_cached_community_claims.py`
- tests:
  - `tests/utils/test_community_claim_note_writer.py`
  - `tests/reporter/test_cached_community_claim_smoke_script.py`

The extractor intentionally uses existing local cache only:

- source cache: `data/raw/xueqiu_data_20260602_黑芝麻智能.json`
- no external network
- no Xueqiu detail page fetch
- no Chrome/CDP
- no LLM

Output written after dry-run validation:

- `knowledge/10-Stocks/黑芝麻智能/20260614-雪球缓存社区claims.md`
- `claim_status=unverified_claim`
- `verification_status=market_opinion`
- `source_type=social_discussion`
- `source_credit=35`
- `data_source=cached_xueqiu`
- `claims=34`

Dry-run smoke result:

```bash
python3 scripts/smoke_cached_community_claims.py --stock 黑芝麻智能 --code 02533 --json --max-posts 20 --max-claims 40
# claim_count=34
# status=dry_run
# post_count=299
```

Post-write claim verification state:

- `high_credit_claims=6`
- `low_credit_claims=34`
- `verifications=34`
- `skipped_files=0`

The bridge now produces structured risk observations from the low-credit pool:

- `盈利压力`
  - evidence: community claim about needing much higher revenue to reach profitability
  - `status=unverified`
  - `confidence=0`
  - does not score
- `资金流出`
  - evidence: community claim mentioning short-selling pressure
  - `status=unverified`
  - `confidence=0`
  - does not score

Codex also tightened the phrase table with focused false-positive tests:

- added clear risk phrases for `做空`, `港股通.*退通`, `不可能盈利`, `难以盈利`, `盈利困难`
- preserved exclusions for positive/low-risk contexts such as `空单.*低`, `做空力量.*未.*大规模`, `港股通纳入`, `流动性改善`
- verified that positive certification, competitor mentions, margin improvement, liquidity improvement, buyback/increase-holding phrases still do not generate risk signals

Focused verification:

```bash
python3 -m pytest tests/utils/test_claim_risk_signals.py -q
# 70 passed

python3 -m pytest tests/utils/test_community_claim_note_writer.py tests/reporter/test_cached_community_claim_smoke_script.py -q
# 9 passed

python3 -m pytest tests/utils/test_claim_risk_signals.py tests/utils/test_community_claim_note_writer.py tests/reporter/test_cached_community_claim_smoke_script.py tests/utils/test_claim_verification.py tests/reporter/test_claim_risk_signal_skill.py tests/reporter/test_pipeline_integration.py tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_scoring_engine_risk.py -q
# 190 passed
```

Current interpretation:

- the material is now sufficient to exercise the full high-credit/low-credit claim verification path
- the generated risk signals are correctly conservative: visible as observations, but not scored because official high-credit evidence did not verify them
- Agent-Reach Xueqiu fetching is not needed for this baseline and remains a separate optional experiment because Xueqiu anti-crawl/CDP account risk is higher than the value of this step

## Full Black Sesame Runtime Validation With Temporary Risk Signals

Codex ran a non-sandbox Black Sesame fast-test with an in-process temporary config patch:

- `claim_verification.enabled=True`
- `claim_verification.risk_signals=True`
- `claim_verification.base_dir=<repo>/knowledge`
- no `config/stocks.json` write

The first sandbox attempt was not used for acceptance because network and browser permissions failed there. The accepted run used local network/browser permissions and completed successfully.

Generated files:

- `reports/黑芝麻智能_20260614.md` — 33K
- `reports/黑芝麻智能_20260614.html` — 11K
- `reports/黑芝麻智能_20260614.pdf` — 1.8M
- `reports/黑芝麻智能_20260614_agent_reach.json` — 5.8K

Quality check:

```bash
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260614.md
# PASS: reports/黑芝麻智能_20260614.md
# No quality issues found.
```

Runtime observations:

- DeepSeek calls returned HTTP 200 in the accepted run.
- Xueqiu detail pages were not fetched; the run reused `xueqiu_data_20260602_黑芝麻智能.json`.
- Zhihu collection and curator were skipped by `--fast-test`; cached `report_input_20260614_黑芝麻智能.json` was reused.
- Agent-Reach fetch status was `ok`; quality status was `ok`; `keep=6`, `demote=0`, `discard=0`.
- `agent_reach.json` remained compact and did not contain full content.
- `akshare index_zh_a_hist` had one proxy failure, but `mootdx` fallback fetched index data successfully.
- PDF export succeeded.

Risk section result:

- `风险等级: 2.0/10（低风险）`
- position advice guardrail remained active:
  - `趋势破坏期，以观望或防守仓位为主，建议 0-5%`
  - `仓位约束` line was rendered
- scoring factors remained quantitative only:
  - `技术破位 +1.0`
  - `流动性差 +1.0`
- no structured risk signal was scored

Structured risk observations rendered as intended:

```text
### 结构化风险观察（不计分）

| 盈利压力 | claim_verification | unverified | 0 | ... / 不可能盈利 |
| 资金流出 | claim_verification | unverified | 0 | ... / 做空 |
```

LLM free-text keyword observations also remained non-scoring:

- `业绩预期下调`
- `盈利压力`
- `资金流出`
- `技术路线风险`

Isolation checks:

- Agent-Reach section still includes the explicit non-scoring disclaimer.
- Agent-Reach entries appear only in the independent evidence observation section.
- No `AgentReach(...)[^n]` or `Agent-Reach[^n]` numbered citations were found.
- Core facts still show source provenance such as `雪球 (community)` and do not attribute facts to Agent-Reach.
- `config/stocks.json` was not modified by this validation.

Git status for expected runtime outputs:

- tracked image refreshes:
  - `reports/黑芝麻智能_radar.png`
  - `reports/黑芝麻智能_valuation.png`
- generated Markdown/HTML/PDF/audit files are ignored and do not appear in `git status`.

Conclusion:

- The end-to-end path is now validated in a real Black Sesame report.
- It is safe to persist `claim_verification.risk_signals=True` for Black Sesame if the user wants this behavior by default.
- The conservative status gate is working: low-credit community claims create visible risk observations, but do not affect risk score unless verified/supported by high-credit evidence.

## Config Persistence

After user approval, Codex persisted the Black Sesame setting in `config/stocks.json`:

```json
"claim_verification": {
  "enabled": true,
  "risk_signals": true
}
```

Scope:

- only `黑芝麻智能`
- only under its existing `agent_reach` config
- no URL/source changes
- no other stock config changes

Verification:

```bash
python3 -m pytest tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_pipeline_integration.py tests/reporter/test_claim_risk_signal_skill.py tests/utils/test_claim_risk_signals.py -q
# 106 passed

python3 -m pytest tests/reporter/test_agent_reach_source_config.py -q
# 3 passed

python3 -m json.tool config/stocks.json
# valid JSON
```

## Default Config Runtime And Claim-Pool Cleanup

Codex tightened cached community claim extraction so title/question-like fragments are skipped unless they contain a verifiable fact predicate.

Filtered examples:

- `A2000还有多少隐藏彩蛋`
- `华山A2000深度解析和投资价值讨论`

Still retained:

- product/customer claims such as `C1236已经获得比亚迪定点`
- certification/volume claims such as `A2000U获得ASIL-D认证`
- financial/risk claims such as `毛利率为41%` and `不可能盈利`

The local Black Sesame low-credit note was regenerated with overwrite:

- file: `knowledge/10-Stocks/黑芝麻智能/20260614-雪球缓存社区claims.md`
- previous claims: 34
- current claims: 30
- source remained local cache only: `data/raw/xueqiu_data_20260602_黑芝麻智能.json`
- no Xueqiu detail fetch, Chrome/CDP, or external network was used for this extraction

Focused verification:

```bash
python3 -m pytest tests/utils/test_community_claim_note_writer.py tests/reporter/test_cached_community_claim_smoke_script.py -q
# 11 passed

python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_claim_risk_signals.py tests/reporter/test_claim_risk_signal_skill.py -q
# 125 passed
```

Codex then ran the default Black Sesame fast-test using the persisted config, without any in-process patch:

```bash
python3 scripts/run_黑芝麻智能.py --fast-test
```

Runtime result:

- report quality: PASS, no quality issues
- `reports/黑芝麻智能_20260614.md` — 31K
- `reports/黑芝麻智能_20260614.html` — 10K
- `reports/黑芝麻智能_20260614.pdf` — 1.7M
- `reports/黑芝麻智能_20260614_agent_reach.json` — 5.8K
- Agent-Reach audit: `keep=6`, `demote=0`, `discard=0`, `fetch_status=ok`, `quality_status=ok`
- compact audit still contains no full content
- DeepSeek calls returned HTTP 200
- Xueqiu detail pages were not fetched
- Zhihu collection/curator were skipped by `--fast-test`
- one `akshare index_zh_a_hist` proxy failure occurred; `mootdx` fallback succeeded
- PDF export succeeded

Default risk result:

- `claim_risk_signal` ran automatically from config: `status=ok count=2`
- structured observations rendered:
  - `盈利压力 | claim_verification | unverified | 0`
  - `资金流出 | claim_verification | unverified | 0`
- both remained non-scoring
- risk score remained driven only by quantitative factors:
  - `技术破位 +1.0`
  - `流动性差 +1.0`
- position guardrail remained active: `趋势破坏期，以观望或防守仓位为主，建议 0-5%`

Isolation checks:

- no `AgentReach(...)[^n]` numbered citations
- no `Agent-Reach[^n]` numbered citations
- no strong recommendation phrases such as `积极配置` or `建议加仓`
- Agent-Reach remained in the independent evidence observation section
