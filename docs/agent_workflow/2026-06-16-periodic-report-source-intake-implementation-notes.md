# Periodic Report Source Intake Implementation Notes

Date: 2026-06-16

## Summary

Implemented the R2-approved periodic report excerpt bridge for Source Intake.

Periodic annual/semiannual report extraction now remains a display/evidence-note layer:

- original cninfo announcement items stay `exchange_announcement`, `source_credit: 95`, `confirmed_fact`
- derived periodic report excerpts are separate `periodic_report_excerpt` items, `source_credit: 75`
- excerpts use `verification_status` values from extractor usage only:
  - `risk_disclosure`
  - `management_view`
  - `capital_action`
  - `financial_forensics`
- malformed periodic excerpts claiming `confirmed_fact` are downgraded in renderer display
- periodic excerpts never become `fact_candidate` evidence notes, even if given high source credit
- periodic excerpts do not enter `KnowledgeSynthesizer` item context

## Files Changed

- `scripts/utils/a_stock_source_intake.py`
  - Added explicit `periodic_report_extraction` handling for annual/semiannual reports.
  - Added `periodic_report_excerpt_id` using `{url_digest}-{usage}-{index}`.
  - Added schema guard for `periodic_report_extractor.v1`.
  - Added max report / max chars / total chars caps.
  - Annual report summaries and quarterly reports do not trigger periodic extraction.

- `scripts/utils/report_skills/source_intake_merge_skill.py`
  - Added periodic-specific dedup key so original announcements and derived excerpts survive with the same URL.

- `scripts/utils/evidence_note_writer.py`
  - Added source-type guard: `periodic_report_excerpt` cannot become `fact_candidate`.

- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
  - Added Source Intake summary label for `定期报告摘录`.
  - Added dedicated `### 定期报告关键摘录` subsection.
  - Excluded periodic excerpts from representative evidence rows.
  - Added malformed-status guard for periodic excerpts.

- Tests:
  - `tests/utils/test_a_stock_source_intake.py`
  - `tests/reporter/test_source_intake_merge_skill.py`
  - `tests/utils/test_evidence_note_writer.py`
  - `tests/reporter/test_source_intake_evidence_renderer.py`
  - `tests/reporter/test_synthesis_skills.py`

## Verification

Focused:

```bash
python3 -m pytest tests/utils/test_a_stock_source_intake.py tests/reporter/test_source_intake_merge_skill.py tests/utils/test_evidence_note_writer.py tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_synthesis_skills.py -q
# 140 passed
```

Related regression:

```bash
python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/reporter/test_a_stock_source_intake_skill.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
# 72 passed
```

Broad reporter/utils without chart generator:

```bash
python3 -m pytest tests/utils tests/reporter --ignore=tests/reporter/test_chart_generator.py -q
# 1091 passed, 6 skipped
```

Broad reporter/utils including chart generator:

```bash
python3 -m pytest tests/utils tests/reporter -q
# 1091 passed, 6 skipped, 6 failed
```

The 6 failures are all in `tests/reporter/test_chart_generator.py`, caused by Kaleido/Chrome startup:

`BrowserFailedError: The browser seemed to close immediately after starting`

This is an environment/browser issue and not related to periodic report Source Intake.

## Runtime

No full report runtime was run in this implementation round. No network, LLM, Chrome/CDP, Xueqiu detail fetch, or report generation was performed by the implementation itself.

## Follow-up Preview Fixes

After reviewing `/tmp/zhongjian_2025_annual_excerpt_preview.md`, four display-quality issues were fixed in the standalone extractor:

- Management discussion excerpts now allow longer evidence text, avoiding premature `...` truncation for complete management sentences.
- Standalone Markdown no longer repeats the same interpretation on every row; each section now has one blockquote note and a compact `等级 / 主题 / 证据` table.
- Capital-action extraction filters governance checkbox / repeated `不适用` table rows.
- Generic capacity strategy language no longer triggers the capital-action bucket; only harder signals such as `固定资产`, `项目投入/建设`, `四期项目`, `产能闲置`, `回购`, `员工持股`, `重大合同` are used.
- Pointer-only risk sentences such as `具体风险及应对措施请见` are filtered out.

Regenerated preview:

- `/tmp/zhongjian_2025_annual_excerpt_preview.md`
- `/tmp/zhongjian_2025_annual_excerpt_preview.json`

Preview summary after the fixes:

- items: 10
- management_view: 8
- capital_action: 2
- risk pointer sentence: removed
- checkbox / repeated `不适用` noise: removed
- repeated interpretation text: one note per section

Verification:

```bash
python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_a_stock_source_intake.py tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_source_intake_merge_skill.py tests/utils/test_evidence_note_writer.py -q
# 126 passed
```
