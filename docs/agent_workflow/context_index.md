# Agent Workflow Context Index

Date: 2026-06-20

Purpose: give Codex, Claude Code, and future agents a short map of the current testsnow workflow. This file is an index, not a design document. Keep it current and compact.

## Current Mainline

The mainline is the single-stock deep report pipeline:

- entry scripts: `scripts/run_*.py`
<!-- path-check: scripts -->
- reporter facade: `scripts/utils/stock_reporter.py`
<!-- path-check: scripts/utils/stock_reporter.py -->
- skill pipeline assembly: `scripts/utils/report_skills/__init__.py`
<!-- path-check: scripts/utils/report_skills/__init__.py -->
- synthesis skill: `scripts/utils/report_skills/synthesis_skills.py`
<!-- path-check: scripts/utils/report_skills/synthesis_skills.py -->
- report renderers: `scripts/utils/reporter/sections/`
<!-- path-check: scripts/utils/reporter/sections -->

Do not use `scripts/xueqiu_monitor_v2.py` as the default validation entry unless the task is specifically about batch scheduling or the legacy monitor.
<!-- path-check: scripts/xueqiu_monitor_v2.py -->

## Periodic Report Fulltext Status

The annual/semiannual fulltext path is an experimental material-layer source.

Current contract:

- source type: `periodic_report_fulltext_analysis`
- credit: 75
- status: `professional_analysis`
- default pipeline switch: off
- may enter display synthesis through `ctx["synthesis_display"]`
- must not directly enter core facts, Knowledge persistence, scoring, risk scoring, `confirmed_fact`, or `fact_candidate`

Key implementation files:

- fulltext analysis helper: `scripts/utils/periodic_report_fulltext_llm_analysis.py`
<!-- path-check: scripts/utils/periodic_report_fulltext_llm_analysis.py -->
- required metrics: `scripts/utils/periodic_report_required_metrics.py`
<!-- path-check: scripts/utils/periodic_report_required_metrics.py -->
- required financial metrics: `scripts/utils/periodic_report_required_financial_metrics.py`
<!-- path-check: scripts/utils/periodic_report_required_financial_metrics.py -->
- product/project evidence backfill: `scripts/utils/periodic_report_product_project_evidence.py`
<!-- path-check: scripts/utils/periodic_report_product_project_evidence.py -->
- HK report fetch helper: `scripts/utils/hk_periodic_report_fetcher.py`
<!-- path-check: scripts/utils/hk_periodic_report_fetcher.py -->
- structured filing fact helper: `scripts/utils/periodic_report_structured_facts.py`
<!-- path-check: scripts/utils/periodic_report_structured_facts.py -->
- Source Intake fulltext skill: `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
<!-- path-check: scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py -->
- Source Intake renderer: `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
<!-- path-check: scripts/utils/reporter/sections/source_intake_evidence_renderer.py -->

Current limitation:

- A-share structured filing facts have a helper-only Phase A path.
- HK structured facts are not yet supported because HK financial-statement blocks are not reliably extracted by the generic evidence pack. See the HK evidence-pack gap in `docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md`.
<!-- path-check: docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md -->

Guardrail files:

- material-layer gate: `tools/ci_grep_gates.sh`
<!-- path-check: tools/ci_grep_gates.sh -->
- gate tests: `tests/utils/test_ci_grep_gates.py`
<!-- path-check: tests/utils/test_ci_grep_gates.py -->
- material isolation tests: `tests/reporter/test_fulltext_material_isolation.py`
<!-- path-check: tests/reporter/test_fulltext_material_isolation.py -->

## Files To Treat As High Risk

Do not casually change these without an explicit task boundary:

- `scripts/utils/knowledge_synthesizer.py`
<!-- path-check: scripts/utils/knowledge_synthesizer.py -->
- `scripts/utils/reporter/scoring_engine.py`
<!-- path-check: scripts/utils/reporter/scoring_engine.py -->
- `scripts/utils/report_skills/knowledge_skills.py`
<!-- path-check: scripts/utils/report_skills/knowledge_skills.py -->
- `scripts/utils/reporter/sections/risk_renderer.py`
<!-- path-check: scripts/utils/reporter/sections/risk_renderer.py -->
- `scripts/utils/reporter/technical_analyzer.py`
<!-- path-check: scripts/utils/reporter/technical_analyzer.py -->
- `scripts/utils/fetcher.py`
<!-- path-check: scripts/utils/fetcher.py -->

Changes involving LLM prompts, synthesis/citation logic, scoring, technical analysis, risk scoring, Xueqiu/CDP/Playwright, or external data collection should use Level 2 or Level 3 workflow.

## Active Design And Status Docs

- workflow README: `docs/agent_workflow/README.md`
<!-- path-check: docs/agent_workflow/README.md -->
- periodic report source-intake design: `docs/agent_workflow/2026-06-17-periodic-report-source-intake-integration-design.md`
<!-- path-check: docs/agent_workflow/2026-06-17-periodic-report-source-intake-integration-design.md -->
- fulltext synthesis material design: `docs/agent_workflow/2026-06-19-periodic-report-fulltext-synthesis-material-design.md`
<!-- path-check: docs/agent_workflow/2026-06-19-periodic-report-fulltext-synthesis-material-design.md -->
- safety and periodic-report roadmap: `docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md`
<!-- path-check: docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md -->
- periodic report structured facts design: `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md`
<!-- path-check: docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md -->
- periodic report structured facts Round 1 review prompt: `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-claude-review-round1.md`
<!-- path-check: docs/agent_workflow/2026-06-20-periodic-report-structured-facts-claude-review-round1.md -->
- periodic report structured facts Round 2 review prompt: `docs/agent_workflow/2026-06-20-periodic-report-structured-facts-claude-review-round2.md`
<!-- path-check: docs/agent_workflow/2026-06-20-periodic-report-structured-facts-claude-review-round2.md -->

## Runbooks

- local report validation: `docs/agent_workflow/runbooks/run_local_report_validation.md`
<!-- path-check: docs/agent_workflow/runbooks/run_local_report_validation.md -->
- add periodic report metric: `docs/agent_workflow/runbooks/add_periodic_report_metric.md`
<!-- path-check: docs/agent_workflow/runbooks/add_periodic_report_metric.md -->
- review generated report quality: `docs/agent_workflow/runbooks/review_generated_report_quality.md`
<!-- path-check: docs/agent_workflow/runbooks/review_generated_report_quality.md -->

## Common Validation Commands

Use focused commands unless the task requires a broader run.

```bash
python3 -m pytest tests/utils/test_ci_grep_gates.py tests/reporter/test_fulltext_material_isolation.py -q
python3 -m pytest tests/utils/test_agent_workflow_docs.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

For report trials, prefer the relevant single-stock fast-test entry, for example:

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
```

Do not refresh Zhihu/LLM materials unless the task explicitly requires it.
