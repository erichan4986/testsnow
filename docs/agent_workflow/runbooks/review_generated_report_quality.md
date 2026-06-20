# Runbook: Review Generated Report Quality

Purpose: inspect a generated report for obvious correctness, completeness, and source-isolation issues.

## Inputs

- generated Markdown report under `reports/`;
- optional HTML/PDF output;
- git status after generation.

## Required Checks

Run the quality checker:

```bash
python3 scripts/check_report_quality.py reports/<generated>.md
```

Then inspect the Markdown for:

- executive summary exists and is not empty;
- technical section includes trend background, daily structure, weekly structure, volume confirmation, volatility condition, support/resistance, and invalidation notes;
- risk section includes risk factors and does not contradict the score;
- source/citation markers are readable and correspond to source rows;
- Source Intake section is present when enabled.

## Periodic Report Fulltext Checks

If the report includes `定期报告全文摘要（实验路径）`, confirm:

- status is `professional_analysis`;
- credit is 75;
- guardrail copy says it does not enter core facts, scoring, risk scoring, or final advice directly;
- it appears in the Source Intake material section, not representative confirmed facts;
- no `confirmed_fact` / `fact_candidate` promotion is shown for that item.

For synthesis-display experiments, also confirm:

- `ctx["synthesis"]` remains baseline in tests;
- `ctx["synthesis_display"]` is the only enhanced display path;
- risk keyword scoring reads baseline `synthesis_text`.

## Common Failure Patterns

- report says "质量 PASS" but a section is empty;
- fulltext material appears as confirmed fact;
- generated report has conflicting technical score and trend wording;
- report entry produced tracked image/report diffs unintentionally;
- fast-test skipped data and the output is too thin for semantic review.

## Completion Report

Summarize:

- Markdown/HTML/PDF paths and sizes;
- quality checker result;
- obvious missing sections;
- any source-isolation or citation issue;
- git status noise.
