# Repo Cleanup / Pre-Commit Audit

Date: 2026-06-17

## Current State

Current branch: `codex-report-quality-upgrade`.

The working tree contains several overlapping sprint lines plus runtime artifacts:

- tracked diff: 51 files, about 4.7k insertions / 0.8k deletions
- untracked: workflow docs, new helper modules/tests, knowledge notes, report images, raw data caches, local skill files
- recent committed history already contains earlier AgentReach / claim verification work, so this tree is not a clean one-feature branch

Do not run broad cleanup commands until the code/doc changes are separated.

## First Move: Stop New Noise

Review and fix `.gitignore` before staging feature work.

Current `.gitignore` diff removed or weakened useful ignores:

- `data/raw/2026*/` was removed, causing `data/raw/20260612/` to appear
- `.agents/skills/` was removed, causing `.agents/skills/grill-me/` to appear
- some report image ignores were changed

Recommended `.gitignore` intent:

- keep ignoring dated raw runtime caches: `data/raw/2026*/`
- keep ignoring local agent skills: `.agents/skills/`
- ignore runtime report images unless intentionally used as test fixtures
- keep tracked fixture files only when they are deliberate golden outputs

## Natural Runtime Artifacts: Do Not Commit by Default

These should be excluded, ignored, or deliberately committed in a separate data/fixture commit only after review:

- `data/raw/20260612/**`
- `reports/agent_reach_page_*.png`
- untracked `reports/*_bullbear.png`
- modified tracked report images:
  - `reports/圣邦股份_radar.png`
  - `reports/黑芝麻智能_radar.png`
  - `reports/黑芝麻智能_valuation.png`
- generated knowledge/evidence notes unless explicitly part of a runtime validation artifact:
  - `knowledge/10-Stocks/**/evidence/**`
  - newly generated `knowledge/10-Stocks/**/20260612-*.md`
  - fresh/cached social claim notes if they are only runtime outputs
- `.agents/skills/grill-me/**` unless the project intentionally wants to version this skill

## Knowledge Directory Findings

`knowledge/10-Stocks/**/evidence/` is now ignored because those files are generated source-intake evidence notes and should not be staged by default.

Remaining visible `knowledge/10-Stocks` changes need human review instead of blanket ignore:

- many `20260612-*.md` files look like report-runtime generated stock notes
- `20260614/20260615-雪球缓存社区claims.md` and `20260615-新鲜外部社媒claims.md` are claim-intake runtime outputs; commit only if they are intended as checked-in fixtures or accepted knowledge artifacts
- `knowledge/10-Stocks/圣邦股份/MOC.md` is a tracked modified file and appears to contain malformed nested wiki links; do not stage it until manually reviewed or explicitly restored

Recommended action:

1. keep generated knowledge notes unstaged for now
2. decide whether claim notes should be versioned as runtime fixtures
3. explicitly approve any destructive cleanup/restoration before running `git restore` or `git clean`

## High-Risk Modified Files: Review Before Any Commit

These affect core report behavior or scoring and should not be bundled blindly:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_analyzer.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `config/stocks.json`
- `scripts/run_圣邦股份.py`

Recommended action:

1. inspect each diff independently
2. connect it to a design/task note
3. run the matching focused tests
4. avoid mixing these with pure helper or docs commits

## Suggested Commit Buckets

### 1. Workflow / Collaboration Docs

Purpose: document Fast Quality Mode and collaboration workflow updates.

Likely files:

- `AGENTS.md`
- `docs/agent_workflow/README.md`
- `docs/codex_handoff/runbook.md`
- selected `docs/agent_workflow/*design.md`, `*task.md`, `*notes.md`, `*review*.md`

Review question:

- Should `docs/agent_workflow/2026-06-13-codex-catchup-handoff.md` really be deleted?

Suggested tests:

- none required beyond markdown review

### 2. Periodic Report / Annual Report Experimental Path

Purpose: annual/semiannual extraction, LLM helper, evidence pack, required metrics.

Likely files:

- `scripts/periodic_report_extractor.py`
- `scripts/utils/periodic_report_extractor.py`
- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_validation.py`
- `tests/utils/test_periodic_report_extractor.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- related `docs/agent_workflow/2026-06-16-periodic-report-*`

Focused tests:

```bash
python3 -m pytest \
  tests/utils/test_periodic_report_extractor.py \
  tests/utils/test_periodic_report_evidence_pack.py \
  tests/utils/test_periodic_report_fulltext_llm_analysis.py \
  tests/utils/test_periodic_report_required_metrics.py -q
```

Current known passing subset from latest run:

```bash
python3 -m pytest \
  tests/utils/test_periodic_report_evidence_pack.py \
  tests/utils/test_periodic_report_required_metrics.py \
  tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
```

Cleanup note:

- `periodic_report_llm_analysis.py` and `periodic_report_llm_analysis_v2.py` were experimental predecessors.
- The current recommended path is `fulltext_llm_analysis + required_metrics + evidence_pack`.
- Shared grounding helpers live in `periodic_report_validation.py`.

### 3. Source Intake / Evidence Notes / Source Visibility

Purpose: A-stock source intake, evidence notes, source-intake renderer, source-intake merge.

Likely files:

- `scripts/utils/a_stock_source_intake.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/report_skills/a_stock_source_intake_skill.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/smoke_source_intake.py`
- `tests/utils/test_a_stock_source_intake.py`
- `tests/utils/test_evidence_note_writer.py`
- `tests/reporter/test_a_stock_source_intake_skill.py`
- `tests/reporter/test_source_intake_evidence_renderer.py`
- `tests/reporter/test_source_intake_merge_skill.py`
- `tests/reporter/test_source_intake_smoke_script.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`
- source-intake workflow docs

Focused tests:

```bash
python3 -m pytest \
  tests/utils/test_a_stock_source_intake.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_a_stock_source_intake_skill.py \
  tests/reporter/test_source_intake_evidence_renderer.py \
  tests/reporter/test_source_intake_merge_skill.py \
  tests/reporter/test_source_intake_smoke_script.py \
  tests/reporter/test_stock_reporter_source_intake_config.py -q
```

### 4. Claim Verification / Claim Risk Signals

Purpose: claim verification, community claim handling, claim-to-risk bridge.

Likely files:

- `scripts/utils/claim_verification.py`
- `scripts/utils/claim_risk_signals.py`
- `scripts/utils/community_claim_note_writer.py`
- `scripts/utils/report_skills/claim_risk_signal_skill.py`
- `scripts/smoke_claim_verification_audit.py`
- `scripts/smoke_claim_intake_audit_flow.py`
- `scripts/smoke_cached_community_claims.py`
- `scripts/smoke_agent_reach_claim_bridge.py`
- `tests/utils/test_claim_verification.py`
- `tests/utils/test_claim_risk_signals.py`
- `tests/utils/test_community_claim_note_writer.py`
- `tests/reporter/test_claim_risk_signal_skill.py`
- `tests/reporter/test_claim_risk_signal_isolation.py`
- `tests/reporter/test_claim_verification_audit_script.py`
- `tests/reporter/test_claim_intake_audit_flow_script.py`
- `tests/reporter/test_cached_community_claim_smoke_script.py`
- `tests/reporter/test_agent_reach_claim_bridge_smoke_script.py`

Focused tests:

```bash
python3 -m pytest \
  tests/utils/test_claim_verification.py \
  tests/utils/test_claim_risk_signals.py \
  tests/utils/test_community_claim_note_writer.py \
  tests/reporter/test_claim_risk_signal_skill.py \
  tests/reporter/test_claim_risk_signal_isolation.py \
  tests/reporter/test_claim_verification_audit_script.py \
  tests/reporter/test_claim_intake_audit_flow_script.py \
  tests/reporter/test_cached_community_claim_smoke_script.py \
  tests/reporter/test_agent_reach_claim_bridge_smoke_script.py -q
```

### 5. Fresh Social Low-Credit Intake

Purpose: bounded fresh social claims intake, mostly Eastmoney Guba now.

Likely files:

- `scripts/utils/fresh_social_claim_intake.py`
- `scripts/smoke_fresh_social_claims.py`
- `tests/utils/test_fresh_social_claim_intake.py`
- `tests/reporter/test_fresh_social_claim_smoke_script.py`
- related `docs/agent_workflow/2026-06-15-fresh-social-*`

Focused tests:

```bash
python3 -m pytest \
  tests/utils/test_fresh_social_claim_intake.py \
  tests/reporter/test_fresh_social_claim_smoke_script.py -q
```

### 6. Credit-Aware Synthesis / Report Quality Guardrails

Purpose: source credit prompt constraints, citation cleaning, core-fact invalid state, supported labels, report quality checks.

Likely files:

- `scripts/utils/synthesis_credit.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_quality.py`
- `scripts/check_report_quality.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `tests/utils/test_synthesis_credit.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_risk_renderer.py`
- `tests/reporter/test_report_quality.py`

Focused tests:

```bash
python3 -m pytest \
  tests/utils/test_synthesis_credit.py \
  tests/utils/test_knowledge_synthesizer.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_executive_summary_renderer.py \
  tests/reporter/test_risk_renderer.py \
  tests/reporter/test_report_quality.py -q
```

Important:

- Because this touches `KnowledgeSynthesizer` and LLM/report text behavior, inspect sample output before accepting.

### 7. AgentReach / Agent Evidence

Purpose: AgentReach quality, source config, evidence renderer, smoke scripts.

Likely files:

- `scripts/smoke_agent_reach.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_quality_skill.py`
- `tests/reporter/test_agent_reach_smoke_script.py`
- `tests/reporter/test_agent_reach_source_config.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- related `docs/agent_workflow/2026-06-14-agent-reach-*`

Focused tests:

```bash
python3 -m pytest \
  tests/reporter/test_agent_reach_evidence_renderer.py \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_agent_reach_smoke_script.py \
  tests/reporter/test_agent_reach_source_config.py \
  tests/reporter/test_stock_reporter_agent_reach_config.py -q
```

### 8. WeChat Exporter Recovery

Purpose: recover/verify `wechat-article-exporter` deployment helper.

Likely files:

- `scripts/deploy_wechat_exporter.sh`
- `tests/reporter/test_deploy_wechat_exporter_script.py`
- `docs/agent_workflow/2026-06-16-wechat-exporter-channel-recovery-notes.md`

Focused tests:

```bash
python3 -m pytest tests/reporter/test_deploy_wechat_exporter_script.py -q
```

## Files to Hold Until Explicit Decision

- `config/stocks.json`
  - enables source intake and evidence notes for 中简科技 / 圣邦股份
  - could make normal runs write notes and perform source intake
- `scripts/run_圣邦股份.py`
  - single-stock entry behavior change; commit only with entry-point tests
- `scripts/utils/reporter/scoring_engine.py`
  - high risk; separate review and tests
- `scripts/utils/reporter/technical_analyzer.py`
  - high risk; separate review and tests
- report image fixture changes under `reports/`
  - commit only if they are deliberate golden fixture updates
- `tests/reporter/tmp_out/*`
  - likely generated fixture output; review before commit

## Suggested Cleanup Sequence

1. Save a patch snapshot outside git if desired.
2. Fix `.gitignore` to stop raw/report/local-skill noise.
3. Re-run `git status --short` and verify untracked runtime artifacts disappear from ordinary status.
4. Review high-risk tracked diffs individually.
5. Stage and commit one functional bucket at a time.
6. For each bucket, run only its focused tests first.
7. After all code buckets are committed, run broader suites:

```bash
python3 -m pytest tests/utils tests/reporter -q
```

8. Only then decide whether runtime knowledge/report/data artifacts should be archived, ignored, or committed as explicit fixtures.

## Recommended Immediate Next Action

Do not stage everything.

Start with either:

1. `.gitignore` cleanup commit, then re-check status; or
2. periodic-report experimental path commit, because it is the most self-contained recent work and has a known passing test subset.
