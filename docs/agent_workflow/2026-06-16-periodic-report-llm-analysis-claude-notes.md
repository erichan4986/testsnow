# Periodic Report LLM Analysis — Implementation Notes

**Date**: 2026-06-16
**Task**: Implement Phase 1 helper-only bounded LLM analysis for annual/semiannual report excerpts.

## Changed Files

- `scripts/utils/periodic_report_llm_analysis.py` (new)
- `tests/utils/test_periodic_report_llm_analysis.py` (new)
- `docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-claude-notes.md` (this file)

No other files were modified.

## Test Results

```bash
python3 -m pytest tests/utils/test_periodic_report_llm_analysis.py -q
# 16 passed in 0.09s

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 36 passed in 0.28s
```

All focused tests pass.

## What Was Implemented

### `scripts/utils/periodic_report_llm_analysis.py`

Public API:

- `build_periodic_report_llm_prompt(extractor_result, *, max_items=20)` — builds a bounded prompt containing only extractor items.
- `validate_periodic_report_llm_output(raw_text, item_map)` — deterministic JSON validator/sanitizer.
- `summarize_periodic_report_with_llm(extractor_result, client, *, max_items=20)` — end-to-end helper returning a credit-typed analysis.
- `render_periodic_report_llm_markdown(analysis)` — compact Markdown preview.

Key behaviors:

- LLM input is built from extractor items only; full report text is never included.
- Items are prioritized: `financial_forensics` > `risk_disclosure` > `management_view` > `capital_action`.
- Evidence text is capped at 700 chars per item.
- Total prompt user content is capped at 12000 chars.
- Stable item ids are generated as `{usage}-{index}`.
- Validator rejects:
  - JSON parse failures
  - schema version mismatch
  - missing/invalid evidence refs
  - `confirmed_fact` / `fact_candidate` / `核心事实` / `已证实`
  - Markdown citation markers
  - raw URLs
  - sections with `confidence` outside `[0, 100]`
  - sections with unknown `usage`
  - sections with `usage == "follow_up_question"`
- Output metadata:
  - `source_type`: `periodic_report_analysis`
  - `source_credit`: 75
  - `verification_status`: `professional_analysis`
  - `claim_status`: `professional_analysis`
  - `knowledge_eligible`: False
  - `report_eligible`: True
- Empty extractor result returns an empty analysis without calling the client.
- No OpenAI/DeepSeek import at module load.
- Client is duck-typed: supports `client.chat(prompt)` or `client.chat.completions.create(...)`.

### `tests/utils/test_periodic_report_llm_analysis.py`

Tests cover all required cases from the task:

1. Prompt includes extractor items, not full report text.
2. Prompt caps item count and evidence length.
3. Prompt prioritizes financial forensics/risk.
4. Prompt includes forbidden literal markers, not regex notation.
5. Valid JSON with valid refs accepted.
6. Schema mismatch rejected.
7. Invalid evidence refs rejected (no valid sections remain).
8. Illegal citation markers rejected.
9. `confirmed_fact` / `fact_candidate` rejected.
10. `confidence` out of `[0, 100]` drops section.
11. `sections[].usage == "follow_up_question"` rejected.
12. Empty extractor result returns empty analysis without calling client.
13. Fake client returns correct credit/status metadata.
14. Completion-style client works.
15. Markdown render contains no numbered citations.
16. Import does not require OpenAI/DeepSeek packages.

## Did We Access Network / Run Real LLM / Chrome / Full Report?

- **Network**: No.
- **Real LLM**: No. All tests use `FakeChatClient` or `FakeCompletionClient`.
- **Chrome/CDP**: No.
- **Xueqiu detail scraping**: No.
- **Full stock report**: No.
- **CLI added**: No.
- **Source Intake / evidence notes / pipeline wiring**: No.

## Behavior Summary

The helper reads deterministic extractor output, builds a tightly bounded prompt, validates the LLM response deterministically, and returns a low-credit (`source_credit=75`) analysis typed as `professional_analysis`. It is intentionally isolated from the rest of the pipeline.

## Deviations from Task

None significant. Minor implementation choices:

- `_chinese_char_count()` uses a simple CJK range check; this is consistent with the task's "500 Chinese characters" rule but is an approximation.
- `_truncate_evidence()` shortens to `max_chars - 1` plus an ellipsis so the final length never exceeds `max_chars`.
- The module-level comment explicitly documents that number/entity novelty detection is deferred to Phase 1.1.

## Blockers

None. The implementation is helper-only and does not require any forbidden file or behavior.

## Next Steps (Not in This Task)

- Phase 1.1: add deterministic number/entity novelty guard before any Source Intake or synthesis integration.
- Phase 1.5 (future design): optionally wire `periodic_report_analysis` into Source Intake as a separate `source_type`, with renderer/writer guards extended to prevent `confirmed_fact` / `fact_candidate`.

## Codex Validation Addendum

Codex reviewed the helper-only diff after the initial implementation and found one task-contract gap:

- The task required whole-analysis rejection when any section or follow-up question referenced missing/invalid `evidence_refs`.
- The first implementation dropped invalid rows and kept valid rows, which could allow an LLM to smuggle an unsupported section alongside supported ones.

Codex added two focused regression tests and changed the validator to fail closed for missing/invalid refs.

Updated tests:

```bash
python3 -m pytest tests/utils/test_periodic_report_llm_analysis.py -q
# 18 passed

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 38 passed
```

No LLM, network, Chrome/CDP, Xueqiu detail scraping, full report run, CLI, Source Intake, evidence notes, or pipeline wiring was added during validation.
