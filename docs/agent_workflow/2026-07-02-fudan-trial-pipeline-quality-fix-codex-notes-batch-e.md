# Batch E Final Smoke Notes — Fudan Trial Pipeline Quality Fix

Date: 2026-07-02

## Scope

Batch E reran the formal Fudan Microelectronics pipeline after Batch 1.5/D/A/B/C fixes and closed two final pipeline-level tails found during smoke:

- Financial missing contradiction sanitizer was accepting `0.00亿元` filing facts.
- 4.3 still allowed indirect industry-news chains such as memory-price / AI-infrastructure narratives to appear as company catalysts.

## Additional Fixes

### Financial fact sanitizer

- `SynthesisSkill._build_formal_financial_fact_pack()` now drops zero-valued financial facts.
- `SynthesisSkill._sanitize_financial_missing_contradictions()` falls back to high-confidence supported core facts when the formal fact pack is absent or unreliable.
- Added regression coverage for the exact bad pattern: zero-value filing facts plus supported revenue/profit core facts.

### 4.3 indirect industry-chain cleanup

- `classify_industry_news_relevance()` now keeps high-confidence industry chains in `4.1` only; `4.3` remains company-direct only.
- `SynthesisSkill._sanitize_indirect_industry_citations_from_43()` removes 4.3 rows/lines that cite indirect industry/news sources not directly naming the company.
- Added tests for prompt filtering and post-synthesis cleanup.

## Formal Fudan Report Smoke

Command:

```bash
set -a; source ./.env; set +a; python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
```

Result:

- Exit code: 0
- Markdown: `reports/复旦微电_20260702.md` (30K)
- HTML: `reports/复旦微电_20260702.html` (10K)
- Peer sidecar: `reports/复旦微电_20260702_peer_comparison_material.json` (3.6K)

Runtime notes:

- Zhihu/API/LLM completed successfully.
- akshare optional quote/index calls hit proxy failures but fell back to mootdx; report still generated.

## Quality Gates

- `python3 scripts/check_report_quality.py reports/复旦微电_20260702.md`: PASS, no quality issues.
- `python3 scripts/check_report_prose_quality.py reports/复旦微电_20260702.md`: PASS with 2 warnings.
  - `repeated_theme_across_sections`: 毛利率/估值
  - `theme_reexpanded_outside_owner`: 4.3 still references revenue/profit/margin as validation indicators.
- `python3 scripts/check_report_source_boundary.py reports/复旦微电_20260702.md`: PASS.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.

## Targeted Content Checks

Within 4.3 only:

- `北京君正`: 0
- `AI基础设施`: 0
- `内存价格`: 0
- `超级周期`: 0
- `传导`: 0
- `MLCC`: 0
- `0.00亿元`: 0
- `未提供营收`: 0
- `未提供利润`: 0

The indirect industry source still appears in the global citation list and 4.1 background only. It no longer enters 4.3 company catalyst/body text.

## Focused Regression

Command:

```bash
env PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils \
  python3 -m pytest \
  tests/reporter/test_assembly_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_synthesis_skills.py \
  tests/utils/test_industry_news_relevance.py \
  tests/utils/test_knowledge_synthesizer.py \
  tests/utils/test_periodic_report_structured_facts.py \
  tests/utils/test_source_direct_relevance.py -q
```

Result: `249 passed`.

## Status

Verdict: ok.

Blocker: 0

Warnings:

- Prose checker still reports mild topic re-expansion around 毛利率/估值 and 4.3 validation indicators. This is non-blocking for Batch E but worth revisiting in a later prose tightening pass.
- Global citation list may retain an industry source that is only used in 4.1, not 4.3.

Deviation: none.
