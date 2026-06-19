# Periodic Report Experimental Path Scoped Diff Review

Date: 2026-06-17

## Scope

Reviewed the current annual/semiannual standalone experimental path diff before deciding what to keep for the next checkpoint.

This review covers:

- required business metrics
- required financial-risk metrics
- fulltext LLM helper prompt / validator / renderer
- deterministic product/project/customer backfill
- HK annual-report fetch helper and HK required-metric extensions
- helper-only Source Intake item builder
- local cache ignore policy
- focused tests and preview docs

No Source Intake, main report pipeline, `KnowledgeSynthesizer`, scoring, technical analysis, `reports/`, or `knowledge/` integration is included in this stage.

## Submit Bucket

These files belong together and should be kept as the current experimental path:

- `.gitignore`
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_product_project_evidence.py`
- `scripts/utils/hk_periodic_report_fetcher.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/evidence_note_writer.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_required_financial_metrics.py`
- `tests/utils/test_periodic_report_product_project_evidence.py`
- `tests/utils/test_hk_periodic_report_fetcher.py`
- `tests/utils/test_periodic_report_fulltext_intake.py`
- `tests/utils/test_evidence_note_writer.py`

Supporting docs:

- `docs/agent_workflow/2026-06-17-periodic-report-experimental-path-status.md`
- `docs/agent_workflow/2026-06-17-periodic-report-experimental-path-scoped-review.md`
- `docs/agent_workflow/2026-06-17-yingjixin-periodic-report-llm-preview.md`
- `docs/agent_workflow/2026-06-17-huadajiutian-periodic-report-llm-preview.md`
- `docs/agent_workflow/2026-06-17-periodic-report-scoped-diff-review.md`
- `docs/agent_workflow/2026-06-17-periodic-report-source-intake-integration-design.md`

## Do Not Submit Bucket

- `data/raw/periodic_reports/`

Decision: keep this as local validation cache only. `.gitignore` now excludes it. If durable regression data is needed later, create small purpose-built fixtures under `tests/fixtures/` instead of committing full annual-report text.

`/tmp/*annual*` previews are also local scratch outputs and should not be moved into the repo unless a specific preview needs to be archived as a review note.

## Findings

No blocker found in the scoped diff.

### Accepted Behavior

- `required_business_metrics` remains outside the LLM output schema and is rendered as deterministic material.
- `required_financial_risk_metrics` also remains outside the LLM output schema and is used for prompt context, rendering, and supplier-risk backfill.
- LLM `evidence_refs` are still restricted to `fulltext-*` ids; evidence-pack ids remain forbidden.
- Product/project backfill produces supplemental `professional_analysis` material only. It does not upgrade anything into confirmed facts.
- Supplier concentration backfill is deterministic and thresholded: it fires for high supplier concentration and does not fire for moderate supplier concentration in offline samples.
- Positive profit-quality observations without an adverse mechanism are dropped instead of forced into risk output.
- `governance_risk` and related model aliases are normalized into the fixed risk taxonomy.

### Residual Risk

- Product/project backfill is intentionally mechanical. It is acceptable as synthesis material, but should not be treated as final human-facing prose without the later report-generation LLM pass.
- Required-metric backfill relies on extracted table values. It is useful for recall, but any future Source Intake integration should keep these rows as evidence notes, not core facts or scoring inputs.
- Full annual-report caches are ignored locally; repeatable CI-style tests should use small fixtures later if this path moves toward integration.
- The largest helper files are now long enough to be expensive for LLM review. Future tasks should target functions/tests by name instead of asking an agent to re-read the whole path.

### Large File Notes

Files that are likely to consume unnecessary LLM context if read wholesale:

- `scripts/utils/periodic_report_fulltext_llm_analysis.py` (~1,900 lines)
- `scripts/utils/periodic_report_required_metrics.py` (~1,300 lines)
- `scripts/utils/periodic_report_product_project_evidence.py` (~1,300 lines)
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py` (~1,260 lines)

These are not delete candidates. They are routing candidates: prompts should name the specific function or behavior under review, and use focused `rg`/`sed` windows.

## Next Gate

Before Source Intake integration:

1. Run one real LLM preview after the latest readability pass on at least 英集芯 and 华大九天.
2. Confirm the real preview keeps required metrics, product/project backfill, and financial risks without obvious hallucination.
3. Design the Source Intake integration boundary so this path remains `professional_analysis`, `source_credit=75`, and never enters scoring or core facts directly.

## Post-review Backlog

This section records the merged four-pass code review after false positives were removed. These items are not current blockers for the experimental path, but they should be handled before broad rollout or before asking an agent to maintain this path for long sessions.

### High Priority: Product/project Evidence Performance

- `scripts/utils/periodic_report_product_project_evidence.py`: snippet de-duplication currently uses list membership checks and can become O(n^2) on large annual reports. Replace with a `set` while preserving output order.
- `scripts/utils/periodic_report_product_project_evidence.py`: `_extract_snippets` scans the same long text once per marker. Consider precompiled combined regexes per marker group.
- `scripts/utils/periodic_report_product_project_evidence.py`: `_snippet_quality_score` repeatedly scans a large diversity-token tuple for every snippet. Convert marker/token groups to `frozenset` or pre-normalized lookup helpers where practical.

### Medium Priority: Robustness And Correctness

- `scripts/utils/hk_periodic_report_fetcher.py`: several `except Exception` branches intentionally return `None`/empty results. Add `logging.warning` with enough context to distinguish invalid JSON, missing HKEX result shape, download failure, and cache-read failure.
- `scripts/utils/hk_periodic_report_fetcher.py`: optional network fetch currently has no retry or request spacing. Add simple bounded retry and a small delay for manual/batch use. This is a general HKEX politeness/robustness concern, not the Xueqiu CDP anti-bot rule.
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`: fulltext title/time/credit fields are interpolated into Markdown. Add injection/escaping tests for `|`, backticks, emphasis markers, and newlines, then centralize field sanitization.
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`: table-cell escaping should avoid double escaping already escaped pipes.
- `scripts/utils/periodic_report_required_metrics.py`: `_valid_percentage_cell` has a year-filter branch that is unreachable after the current `>100` return. Either remove it or rewrite the branch so the intention is testable.
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`: `build_periodic_report_fulltext_intake_item` builds both `fulltext_pack` and `evidence_pack` from the same raw text. If large annual reports become a runtime issue, consider a shared preprocessed text/section object rather than parsing raw text twice.

### Low Priority: Cleanup

- `scripts/utils/periodic_report_product_project_evidence.py`: remove duplicate local assignments / duplicate filtering where they exist after the latest readability patches.
- `scripts/utils/periodic_report_product_project_evidence.py`: replace any company-sample-shaped hard-coded phrase guard with a generic pattern if it still exists after focused review.
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`: remove repeated local `import json` where module-level import is clearer.

### Structural Debt

- `scripts/utils/periodic_report_fulltext_llm_analysis.py` is now large enough that future changes should be routed to narrower modules: prompt builder, validator, renderer, financial-risk backfill, and product/project backfill integration.
- `scripts/utils/periodic_report_product_project_evidence.py` should eventually be split into constants, extraction, scoring, summarization, and utility helpers.

### Confirmed Non-issues

- `required_metrics` yuan normalization does not create a practical `元元` malformed unit because values do not include Chinese unit text in that code path.
- `required_financial_metrics._amount_in_wan` strips `亿元` correctly with `[:-2]` and has exception fallback.
- Financial metrics already reuse core helpers where needed; there is no urgent duplicate-four-copy logic issue.
- `100%` gross margin is not rejected by the current percentage validator; the remaining issue is only the unreachable year branch.

### Follow-up Completed

- HK fetcher now logs invalid JSON / fetch failures and uses a bounded retry with delay for optional downloads.
- Source Intake renderer now sanitizes fulltext metadata and table date cells, escaping only unescaped Markdown control characters.
- `required_metrics._valid_percentage_cell` no longer contains the unreachable year-filter branch.
