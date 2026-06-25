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

## Annual Report Intake Current Map

Annual Report Intake is the shared mental model for annual/semiannual report code. Read files by layer instead of treating each helper as a separate product.

Canonical operator workflow:

1. Prepare report materials explicitly before a report run:

   ```bash
   python3 scripts/prepare_annual_report_materials.py --stock 黑芝麻智能 --year 2025
   ```

   This prepares the local annual-report cache and writes a `/tmp` narrative cards preview. It does not write Knowledge unless `--write-knowledge` is passed.

2. Inspect the `/tmp/*_narrative_cards_preview.md` output for card quality. If the cards are useful and should be persisted, rerun with `--write-knowledge`.
3. Run the relevant single-stock fast-test report entry, for example `cd scripts && python3 run_黑芝麻智能.py --fast-test`.

Do not silently auto-fetch annual reports inside ordinary report runs. Keep annual-report network/cache preparation as an explicit preflight step so generated reports remain predictable.

Scope boundary for narrative cards v1:

- Optimized target domain: pan-semiconductor / hard-tech annual reports, including semiconductor design, optical modules, electronic materials, AI chips, intelligent hardware, and high-end manufacturing companies with concrete product/R&D disclosures.
- Knowledge writes are allowed by default only after preview review for this target domain.
- Non-target industries, especially pharma/biotech, consumer, real estate, financial holding, or heavily templated filings, are preview-only in v1 unless a human explicitly approves writing. Use `长春高新` and `三花智控` as observation samples, not quality-regression baselines and not default Knowledge-write targets.
- If broader industry coverage is needed, create a separate v2 design/schema instead of adding broad industry special cases to the current pan-semiconductor path.

Intake and extraction helpers:

- one-command cache + preview + optional Knowledge preflight: `scripts/prepare_annual_report_materials.py`
<!-- path-check: scripts/prepare_annual_report_materials.py -->
- standard cache CLI for A-share CNINFO, HKEX, URL, and local files: `scripts/periodic_report_cache.py`
<!-- path-check: scripts/periodic_report_cache.py -->
- standard cache helpers: `scripts/utils/periodic_report_cache.py`
<!-- path-check: scripts/utils/periodic_report_cache.py -->
- raw evidence blocks: `scripts/utils/periodic_report_evidence_pack.py`
<!-- path-check: scripts/utils/periodic_report_evidence_pack.py -->
- required operating metrics: `scripts/utils/periodic_report_required_metrics.py`
<!-- path-check: scripts/utils/periodic_report_required_metrics.py -->
- required financial/risk metrics: `scripts/utils/periodic_report_required_financial_metrics.py`
<!-- path-check: scripts/utils/periodic_report_required_financial_metrics.py -->
- product/project/customer evidence: `scripts/utils/periodic_report_product_project_evidence.py`
<!-- path-check: scripts/utils/periodic_report_product_project_evidence.py -->
- narrative evidence cards: `scripts/utils/periodic_report_narrative_evidence_cards.py`
<!-- path-check: scripts/utils/periodic_report_narrative_evidence_cards.py -->
- structured filing facts: `scripts/utils/periodic_report_structured_facts.py`
<!-- path-check: scripts/utils/periodic_report_structured_facts.py -->
- HK report fetch helper: `scripts/utils/hk_periodic_report_fetcher.py`
<!-- path-check: scripts/utils/hk_periodic_report_fetcher.py -->
- standalone/legacy A-share extractor: `scripts/utils/periodic_report_extractor.py`
<!-- path-check: scripts/utils/periodic_report_extractor.py -->

Material and display helpers:

- fulltext LLM analysis and Ground Truth-constrained prompt: `scripts/utils/periodic_report_fulltext_llm_analysis.py`
<!-- path-check: scripts/utils/periodic_report_fulltext_llm_analysis.py -->
- Source Intake fulltext skill: `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
<!-- path-check: scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py -->
- Source Intake renderer: `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
<!-- path-check: scripts/utils/reporter/sections/source_intake_evidence_renderer.py -->

Knowledge writers:

- narrative card notes: `scripts/utils/periodic_report_narrative_card_note_writer.py`
<!-- path-check: scripts/utils/periodic_report_narrative_card_note_writer.py -->
- filing fact notes, writer-only: `scripts/utils/periodic_report_filing_fact_note_writer.py`
<!-- path-check: scripts/utils/periodic_report_filing_fact_note_writer.py -->

Preview and acceptance helpers:

- narrative cards single-stock preview: `scripts/periodic_report_narrative_cards_preview.py`
<!-- path-check: scripts/periodic_report_narrative_cards_preview.py -->
- narrative cards multi-stock acceptance: `scripts/periodic_report_narrative_cards_acceptance.py`
<!-- path-check: scripts/periodic_report_narrative_cards_acceptance.py -->

Cross-cutting and adjacent helpers:

- periodic report LLM validation/fidelity checks: `scripts/utils/periodic_report_validation.py`
<!-- path-check: scripts/utils/periodic_report_validation.py -->
- adjacent/legacy periodic report summary helper: `scripts/utils/periodic_reporter.py`
<!-- path-check: scripts/utils/periodic_reporter.py -->

Active unification design:

- `docs/agent_workflow/2026-06-22-periodic-report-intake-unification-design.md`
<!-- path-check: docs/agent_workflow/2026-06-22-periodic-report-intake-unification-design.md -->

Current limitation:

- The preferred annual-report preflight is `scripts/prepare_annual_report_materials.py`; it chooses `annual_report_url` first, then CNINFO for A shares, then HKEX for HK shares.
- A-share and HK narrative evidence cards are the current primary path for writing useful annual-report text into Knowledge. They can write `periodic_report_narrative_evidence` notes under `knowledge/10-Stocks/<stock>/periodic_narrative_cards/`.
- Narrative cards v1 is intentionally scoped to pan-semiconductor / hard-tech reports. Keep non-target industries preview-only by default; do not use pharma/manufacturing edge cases to tune the generic v1 extractor unless the task explicitly opens an industry-specific design.
- Fulltext LLM summaries remain material-layer display/synthesis references only. They must not enter Knowledge persistence, scoring, risk scoring, `confirmed_fact`, or `fact_candidate`.
- Ground Truth numeric blocks constrain fulltext LLM financial numbers; they are not a separate Knowledge source.
- Filing facts have a writer-only structured finance path, but they are not the current priority for annual-report knowledge enrichment.
- A-share structured filing facts have a helper-only Phase A path.
- HK narrative cards are supported, but HK structured facts are not yet supported because HK financial-statement blocks are not reliably extracted by the generic evidence pack. See the HK evidence-pack gap in `docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md`.
<!-- path-check: docs/agent_workflow/2026-06-20-vibe-trading-inspired-safety-and-periodic-report-roadmap.md -->

## Broker Research Digest Current Map

Broker research digest is a Source Intake professional-observation path for Eastmoney broker report PDFs. It is display-only by design.

Current contract:

- source type: `broker_research`
- credit: 72
- status: `professional_analysis`
- cache root: `data/raw/broker_research_reports/<stock>_<code>/`
- Knowledge notes: `knowledge/10-Stocks/<stock>/broker_research_digest/`
- may enter display synthesis through `ctx["synthesis_display"]`
- must not enter core facts, scoring, risk scoring, `confirmed_fact`, or `fact_candidate`

Operator workflow:

1. Let Source Intake download/cache recent Eastmoney broker report PDFs, or manually place high-quality PDFs under `data/raw/broker_research_reports/<stock>_<code>/_downloads/`.
2. Generate a local preview:

   ```bash
   python3 scripts/broker_research_digest_preview.py --stock 圣邦股份 --code 300661
   ```

3. Inspect the `/tmp/*_broker_research_digest_preview.md` output. Only persist useful cards:

   ```bash
   python3 scripts/broker_research_digest_preview.py --stock 圣邦股份 --code 300661 --write-knowledge
   ```

4. Enable display in the stock `source_intake` config with `broker_research_digest_synthesis_display.enabled=true`.

Digest helpers:

- PDF preview CLI: `scripts/broker_research_digest_preview.py`
<!-- path-check: scripts/broker_research_digest_preview.py -->
- deterministic digest extractor: `scripts/utils/broker_research_digest.py`
<!-- path-check: scripts/utils/broker_research_digest.py -->
- Knowledge note writer: `scripts/utils/broker_research_digest_note_writer.py`
<!-- path-check: scripts/utils/broker_research_digest_note_writer.py -->
- display-only synthesis reader: `scripts/utils/broker_research_digest_synthesis_items.py`
<!-- path-check: scripts/utils/broker_research_digest_synthesis_items.py -->
- synthesis integration: `scripts/utils/report_skills/synthesis_skills.py`
<!-- path-check: scripts/utils/report_skills/synthesis_skills.py -->
- stock config passthrough: `scripts/utils/stock_reporter.py`
<!-- path-check: scripts/utils/stock_reporter.py -->

Verified sample:

- `圣邦股份` has broker digest display enabled and validated through `scripts/run_圣邦股份.py --fast-test`.

## Social Observation Current Map

Social observation is not an active mainline source. The current low-risk smoke is recorded in:

- `docs/agent_workflow/2026-06-24-social-observation-source-design.md`
<!-- path-check: docs/agent_workflow/2026-06-24-social-observation-source-design.md -->

Current conclusion:

- do not depend on the `agent-reach` wrapper CLI; local `agent-reach doctor` fails with `ModuleNotFoundError: agent_reach.cli`
- prefer a curated external-analysis pack over broad social crawling: hand-picked public URLs, Bilibili / YouTube subtitle URLs, and local WeChat article exports
- Jina Reader is usable for public pages, industry/company articles, and some report landing pages
- YouTube subtitle access works when captions exist; Bilibili subtitle extraction is only partially validated and should be URL-driven
- WeChat should be handled through exported local files from external tooling such as `wechat-article/wechat-article-exporter`, not direct in-pipeline login/scraping
- Xiaohongshu may contain useful product/channel observations, but anti-bot, `xsec_token`, image/OCR, and comment-quality issues make it smoke-only, preview-only
- V2EX public API is usable but sparse
- Reddit was not tested because `rdt` is not installed

If reopened, keep this path preview/display-only by default. Do not write social observations to Knowledge, scoring, risk scoring, confirmed facts, fact candidates, or final recommendation logic.

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
- HK periodic report evidence-pack design: `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md`
<!-- path-check: docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md -->
- HK periodic report evidence-pack Round 1 review prompt: `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-claude-review-round1.md`
<!-- path-check: docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-claude-review-round1.md -->
- HK periodic report evidence-pack Round 2 review prompt: `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-claude-review-round2.md`
<!-- path-check: docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-claude-review-round2.md -->
- periodic report filing facts Knowledge design: `docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md`
<!-- path-check: docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md -->
- periodic report filing facts Knowledge Round 1 review prompt: `docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-claude-review-round1.md`
<!-- path-check: docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-claude-review-round1.md -->
- periodic report narrative evidence cards design: `docs/agent_workflow/2026-06-21-periodic-report-narrative-evidence-cards-design.md`
<!-- path-check: docs/agent_workflow/2026-06-21-periodic-report-narrative-evidence-cards-design.md -->
- Vibe-Trading walkthrough notes: `docs/agent_workflow/2026-06-21-vibe-trading-walkthrough-notes.md`
<!-- path-check: docs/agent_workflow/2026-06-21-vibe-trading-walkthrough-notes.md -->

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
