# Periodic Report LLM Analysis Helper Task

Date: 2026-06-16

## Objective

Implement Phase 1 of bounded LLM analysis for annual/semiannual report excerpts.

This phase is helper-only:

- no CLI
- no Source Intake integration
- no evidence notes
- no report generation
- no scoring/risk/core-fact/synthesis changes

The helper should take the deterministic `periodic_report_extractor` output, build a bounded prompt over selected extractor items, call a fake-testable LLM client, validate the JSON response, and return a conservative `periodic_report_analysis` object.

## Read First

- `docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-design.md`
- `scripts/utils/periodic_report_extractor.py`
- `tests/utils/test_periodic_report_extractor.py`

## Allowed Files

Create:

- `scripts/utils/periodic_report_llm_analysis.py`
- `tests/utils/test_periodic_report_llm_analysis.py`
- `docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-claude-notes.md`

Do not modify any other file.

## Forbidden Files / Behaviors

Do not modify:

- `scripts/periodic_report_extractor.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/a_stock_source_intake.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/utils/reporter/scoring_engine.py`
- technical-analysis modules
- `config/stocks.json`
- `knowledge/`
- `reports/`
- `data/raw/`

Do not:

- access external websites
- run a real LLM
- run a full stock report
- start Chrome/CDP
- scrape Xueqiu details
- add a CLI flag
- add pipeline wiring

Stop if any forbidden file seems necessary.

## Required Helper API

Implement in `scripts/utils/periodic_report_llm_analysis.py`:

```python
SCHEMA_VERSION = "periodic_report_llm_analysis.v1"

def build_periodic_report_llm_prompt(extractor_result: dict, *, max_items: int = 20) -> dict:
    ...

def validate_periodic_report_llm_output(raw_text: str, item_map: dict) -> dict:
    ...

def summarize_periodic_report_with_llm(extractor_result: dict, client: object, *, max_items: int = 20) -> dict:
    ...

def render_periodic_report_llm_markdown(analysis: dict) -> str:
    ...
```

The client should be duck-typed and fake-testable. Accept either:

- `client.chat(prompt: str) -> str`
- or `client.chat.completions.create(...)`

Prefer the simpler `.chat(prompt)` path first if present.

No OpenAI/DeepSeek import at module load.

## Prompt Builder Requirements

Input is only extractor result items, not the full report text.

Include:

- schema version instruction
- credit and usage guardrails
- JSON-only instruction
- item ids
- item usage/title/severity/evidence

Caps:

- at most 20 items
- at most 700 chars per evidence
- prioritize:
  1. `financial_forensics`
  2. `risk_disclosure`
  3. `management_view`
  4. `capital_action`

Generate stable item ids:

```text
{usage}-{index}
```

The prompt must explicitly forbid:

- `confirmed_fact`
- `fact_candidate`
- `核心事实`
- `已证实`
- `[^1]`
- `[^12]`
- `[^verified]`
- `[^supported]`
- `[^needs_review]`
- `[^unverified]`
- raw URLs

## Output Contract

Returned helper output should look like:

```python
{
    "schema_version": "periodic_report_llm_analysis.v1",
    "source_type": "periodic_report_analysis",
    "source_credit": 75,
    "verification_status": "professional_analysis",
    "claim_status": "professional_analysis",
    "knowledge_eligible": False,
    "report_eligible": True,
    "report_type": "...",
    "audit_status": "...",
    "sections": [...],
    "follow_up_questions": [...],
}
```

Allowed `sections[].usage` values:

- `management_narrative`
- `business_change`
- `risk_tension`
- `financial_red_flag`
- `capital_allocation`

`follow_up_question` is not allowed in `sections[].usage`; questions only belong in top-level `follow_up_questions`.

## Validator Requirements

Reject whole analysis if:

- JSON parse fails
- schema version mismatch
- any section has missing/invalid evidence refs
- any follow-up question has missing/invalid evidence refs
- any output contains `confirmed_fact` or `fact_candidate`
- section count > 8
- follow-up question count > 8

Drop individual sections if:

- unknown usage
- summary empty after sanitization
- confidence missing, not integer, `< 0`, or `> 100`
- summary length > 500 Chinese chars
- contains markdown citation markers

Sanitize:

- `[^1]`, `[1]`, `[^verified]`, `[^supported]`, `[^needs_review]`, `[^unverified]`
- raw URLs
- repeated whitespace

Phase 1 does not implement deterministic number/entity novelty detection. Add a clear module-level comment and test note that this must be implemented before any Source Intake / synthesis integration.

## Required Tests

Create focused tests in `tests/utils/test_periodic_report_llm_analysis.py`.

Tests must cover:

1. Prompt includes extractor items and not unrelated full report text.
2. Prompt caps item count and evidence length.
3. Prompt includes forbidden literal markers, not regex notation.
4. Valid JSON with valid refs is accepted.
5. Schema mismatch is rejected.
6. Invalid evidence refs reject the whole analysis.
7. Illegal citation markers are sanitized or rejected according to validator contract.
8. `confirmed_fact` / `fact_candidate` rejects the whole analysis.
9. `confidence: 120` and `confidence: -1` sections are dropped.
10. `sections[].usage == "follow_up_question"` is rejected/dropped.
11. Empty extractor result returns empty analysis and does not call the fake client.
12. Fake client summary returns `source_credit == 75`, `verification_status == professional_analysis`, `knowledge_eligible is False`, `report_eligible is True`.
13. Importing the helper does not require OpenAI/DeepSeek packages.
14. `render_periodic_report_llm_markdown()` renders a compact preview without numbered citations.

## Verification Commands

Run:

```bash
python3 -m pytest tests/utils/test_periodic_report_llm_analysis.py -q
python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
```

Do not run a full report.

## Notes Output

Write implementation notes to:

```text
docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-claude-notes.md
```

Include:

- changed files
- test results
- whether any LLM/network/Chrome/report run happened
- behavior summary
- deviations from task
- blockers
