# Runbook: Add Periodic Report Metric

Purpose: add or adjust a required annual/semiannual report metric without weakening no-fabrication guardrails.

## When To Use

Use this when a generated periodic-report summary misses a deterministic metric such as segment revenue, gross margin, inventory, customer concentration, supplier concentration, cash-flow quality, or a financial-risk ratio.

## Main Files

- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_required_financial_metrics.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`

## Rules

- Prefer deterministic extraction from evidence-pack blocks or parsed tables.
- Do not let an LLM invent missing metric values.
- Validator acceptance must use exact normalized value matching, not "metric appears somewhere".
- If a value is missing, preserve visible missingness instead of fabricating.
- Do not put required metrics into the LLM output top-level schema.
- Do not let LLM judgments cite evidence-pack ids such as `segment_margin_table-0`; LLM evidence refs should remain fulltext refs.

## TDD Steps

1. Add a failing fixture/test for the missing metric.
2. Implement the smallest parser or renderer change.
3. Verify canonical normalized values and units.
4. Add a renderer assertion if the metric should appear in Markdown.

## Focused Tests

```bash
python3 -m pytest tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
```

For product/project context changes, also run:

```bash
python3 -m pytest tests/utils/test_periodic_report_product_project_evidence.py -q
```

## Stop Conditions

Stop and ask for review if the change requires:

- scoring or risk-rule changes;
- Knowledge persistence changes;
- LLM prompt/schema changes beyond the fulltext helper;
- new network fetching behavior;
- broad parser rewrites across unrelated report sections.
