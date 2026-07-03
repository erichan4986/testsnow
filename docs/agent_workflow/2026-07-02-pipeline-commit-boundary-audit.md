# Pipeline Commit Boundary Audit

Date: 2026-07-02

## Verdict

`split_before_commit`

当前工作区不适合一次性提交。生产代码、测试、workflow 文档和自然生成报告混在一起；如果一把提交，会很难 code review，也很难回滚。

## Current State

Tracked diff:

```text
23 files changed, 2436 insertions(+), 238 deletions(-)
```

Untracked notable files:

- `scripts/utils/curated_external_display.py`
- `scripts/utils/fundflow_material.py`
- `scripts/utils/periodic_report_explanation_pack.py`
- `scripts/utils/source_direct_relevance.py`
- corresponding tests
- many `docs/agent_workflow/*.md`
- `reports/`

Important: `reports/` must not be staged wholesale. The current `reports/复旦微电_20260702.md` was overwritten by a sandbox run with network/API failures and is not a valid review artifact.

## Commit Packages

### Package 1 - Trial Config And Peer/Fudan Wiring

Purpose:

- Add/complete stock config needed for formal trial and peer config.

Files:

- `config/stocks.json`
- `tests/reporter/test_stock_reporter_source_intake_config.py`

Status:

- Keep.
- Commit separately if the config itself has already been reviewed.

Risk:

- Low to medium. Config affects future report runs for several stocks.

### Package 2 - Direct Relevance And Industry-News Safety

Purpose:

- Prevent MLCC-style unrelated or multi-hop industry logic from entering canonical 4.1-4.3.
- Keep indirect or sector-only news out of 4.3 unless deterministic chain validation allows it.

Files:

- `scripts/utils/source_direct_relevance.py`
- `scripts/utils/industry_news_relevance.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/synthesis_skills.py` related filtering pieces
- `scripts/utils/report_quality.py` related quality checks
- `tests/utils/test_source_direct_relevance.py`
- `tests/utils/test_industry_news_relevance.py`
- `tests/utils/test_source_adapter.py`

Status:

- Keep, but review carefully before commit.

Risk:

- Medium. Conservative filtering can under-fill some sections if stock config lacks product exposure terms.

Pre-commit check:

- Confirm fallback behavior when `product_exposure_terms` is missing.
- Confirm no social/display-only material enters canonical 4.1-4.3.

### Package 3 - Fundflow Material Pack

Purpose:

- Make 4.3 funding section use deterministic fund-flow summary rather than raw/noisy items.

Files:

- `scripts/utils/fundflow_material.py`
- `scripts/utils/source_adapter.py` fundflow normalization pieces
- `scripts/utils/report_skills/assembly_skills.py` sidecar pieces if applicable
- `scripts/utils/report_quality.py` fundflow gate pieces
- `tests/utils/test_fundflow_material.py`
- `tests/reporter/test_assembly_skills.py` fundflow-related tests
- `tests/reporter/test_report_quality.py` fundflow-related tests

Status:

- Keep.

Risk:

- Low. Small deterministic helper with focused tests.

### Package 4 - Annual Report Fact And Explanation Packs

Purpose:

- Use formal annual report facts and management explanations in 4.2.
- Avoid repeating core finance table values without explanation.

Files:

- `scripts/utils/periodic_report_structured_facts.py`
- `scripts/utils/periodic_report_explanation_pack.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/knowledge_synthesizer.py` financial pack prompt appendix
- `scripts/utils/report_skills/synthesis_skills.py` formal financial pack handoff
- `tests/utils/test_periodic_report_structured_facts.py`
- `tests/utils/test_periodic_report_explanation_pack.py`
- `tests/reporter/test_periodic_report_fulltext_intake_skill.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`

Status:

- Keep.

Risk:

- Medium. This touches prompt inputs and extraction logic; needs local real-report rerun before final release.

Pre-commit check:

- Show sample 4.2 prompt appendix or output excerpt to user before final commit because `KnowledgeSynthesizer` prompt input changed.

### Package 5 - Curated External 4.4 Reasoning Cards

Purpose:

- Preserve external article/social long-form reasoning in 4.4 without leaking into canonical analysis.

Files:

- `scripts/utils/curated_external_viewpoint_narrative.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/report_skills/synthesis_skills.py` narrative display caller
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/utils/test_curated_external_viewpoint_narrative.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`

Status:

- Keep, with caveat.

Caveat:

- Existing `data/curated_external/viewpoint_narratives/fudan_20260702.json` may not contain `reasoning_cards`; the pipeline supports cards, but actual report output needs regenerated narrative JSON.

Risk:

- Medium. Display and citation logic are sensitive, but focused tests currently cover the path.

### Package 6 - Evidence-Depth Warning Gates

Purpose:

- Warning-only checks for empty/template-like 4.1-4.4.

Files:

- `scripts/utils/report_quality.py`
- `tests/reporter/test_report_quality.py`

Status:

- Keep as warning-only.

Risk:

- Medium. Useful tripwires, but can produce noise.

Pre-commit check:

- Do not promote these warnings to errors yet.
- Document that `section_too_generic` is intentionally low-sensitivity.

### Package 7 - Technical Risk/Data Fallbacks

Purpose:

- Prior fixes around missing technical data / risk handling.

Files:

- `scripts/utils/report_skills/technical_skills.py`
- `tests/reporter/test_technical_skills_contract.py`

Status:

- Keep if still tied to validated 黑芝麻/复旦 issue.

Risk:

- Medium because technical/risk behavior affects recommendations.

Pre-commit check:

- Ensure this package is not bundled with 4.1-4.4 prose fixes unless tests justify it.

### Package 8 - Workflow Docs

Purpose:

- Trace design, Claude review, Codex notes, and audit decisions.

Files:

- `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-*.md`
- `docs/agent_workflow/2026-07-02-fudan-evidence-depth-pipeline-*.md`
- `docs/agent_workflow/2026-07-02-pipeline-code-bloat-audit.md`
- `docs/agent_workflow/2026-07-02-pipeline-commit-boundary-audit.md`

Status:

- Keep final design and final notes.
- Consider pruning intermediate review prompts if commit size becomes noisy.

Risk:

- Low runtime risk, high review-noise risk.

### Package 9 - Reports And Generated Artifacts

Purpose:

- Natural report outputs / sidecars.

Files:

- `reports/`

Status:

- Do not commit.

Reason:

- Current `reports/复旦微电_20260702.md` is degraded due sandbox network/API failure.
- `reports/` contains many historical artifacts and should not be staged wholesale.

## Recommended Commit Order

1. Direct relevance + industry safety
2. Fundflow material pack
3. Annual report fact/explanation pack
4. Curated external reasoning cards
5. Evidence-depth warnings
6. Config / peer wiring, if not already committed separately
7. Workflow docs, curated to final design + notes only

Alternative:

- If commit history cleanliness matters less than speed, group 1-5 into two commits:
  - canonical safety and material packs
  - display/prose quality warnings

## Required Verification Before Any Commit

Focused regression:

```text
python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
```

Gates:

```text
bash tools/ci_grep_gates.sh
git diff --check
```

Report smoke:

- Must be run locally, not in the current restricted sandbox.
- Regenerate `reports/复旦微电_20260702.md` with working network/API/LLM/Chrome.
- Then run:
  - `python3 scripts/check_report_quality.py reports/复旦微电_20260702.md`
  - `python3 scripts/check_report_prose_quality.py reports/复旦微电_20260702.md`
  - `python3 scripts/check_report_source_boundary.py reports/复旦微电_20260702.md`

## Stop Conditions

- Do not start Batch B peer business comparison before this diff is committed or split.
- Do not split `report_quality.py` in this same change unless required by test failures.
- Do not rely on the current sandbox-generated report for content review.
- Do not stage `reports/`.
