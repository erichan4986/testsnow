# Periodic Report Required Metrics Implementation Notes

## Scope

Codex took over after the previous local agent stalled on inventory parsing.

Modified files:

- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`

No main report pipeline, scoring, KnowledgeSynthesizer, data/raw, reports, knowledge, Chrome/CDP, network, or LLM calls were touched.

## Implemented

- Added deterministic required metrics extraction for:
  - segment/product revenue, revenue YoY, gross margin, gross margin delta
  - region rows
  - sales mode rows
  - production/sales/inventory rows and inventory YoY
  - customer concentration
  - supplier concentration
- The helper consumes evidence-pack blocks first and can use bounded `raw_text` fallback when evidence pack extraction has trimmed away needed table context.
- Inventory parser now uses direct table row parsing and supports broken product names such as `数 模 混 合 / SoC 类`.
- Segment parser supports both standard 6-column annual-report tables and simplified 5-column tables.
- Jina-style spaced decimals such as `99. 42%` and `87.4 9` are normalized.
- Monetary values keep original `text` but canonicalize `normalized` to `万元` with two decimals for yuan-denominated table values.
- Table presence now records source block ids from actual extracted rows/concentration entries, not all source blocks.
- Fulltext experimental prompt now accepts `required_metrics` as deterministic context, while explicitly forbidding evidence-pack ids such as `segment_margin_table-0` in LLM `evidence_refs`.
- Fulltext renderer now has an optional deterministic `## 必备经营指标摘录` section before LLM judgments.
- Fixed `_empty_fulltext_analysis()` to use `FULLTEXT_ANALYSIS_SCHEMA_VERSION`.

## Tests

Focused:

```bash
python3 -m pytest tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
# 36 passed
```

Adjacent regression:

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
# 108 passed
```

## Notes

- `required_business_metrics` remains deterministic input/renderer data, not an LLM output field.
- LLM validation still only accepts `fulltext-*` refs. Evidence-pack ids are rejected as invalid refs by the existing item map path.
- Raw-text fallback is only needed when the evidence pack has already removed key context, for example a top-five customer percentage sentence trimmed away from a customer table block.

## Blockers

None.
