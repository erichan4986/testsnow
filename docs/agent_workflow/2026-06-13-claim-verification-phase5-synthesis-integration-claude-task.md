# Claim Verification Phase 5 Synthesis Integration Claude Task

> **Date**: 2026-06-13  
> **Owner**: Codex  
> **Implementer**: Claude Code  
> **Design**: `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-design.md`  
> **Notes Output**: `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-implementation-claude-notes.md`  
> **Status**: Ready to implement

You are implementing a locked task from the design above. Stay within scope.

---

## 1. Mission

Implement optional, default-off claim verification context for Phase 5 synthesis integration.

The result should let `SynthesisSkill` pass a sanitized, non-citable verification summary into both modern `KnowledgeSynthesizer` prompts and legacy `.chat(prompt)` prompts. It must not add new numbered citation sources, must not write to `knowledge/`, and must not change report behavior unless `enable_claim_verification_context=True`.

---

## 2. Hard Boundaries

You may modify or create only these files:

- Modify: `scripts/utils/claim_verification.py`
- Modify: `scripts/utils/report_skills/synthesis_skills.py`
- Modify: `scripts/utils/knowledge_synthesizer.py`
- Modify: `scripts/utils/stock_reporter.py`
- Modify: `tests/utils/test_claim_verification.py`
- Modify: `tests/utils/test_knowledge_synthesizer.py`
- Modify: `tests/reporter/test_synthesis_skills.py`
- Modify: `tests/reporter/test_stock_reporter_agent_reach_config.py`
- Create: `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-implementation-claude-notes.md`

Do not modify:

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_*.py`
- `scripts/utils/reporter/price_target.py`
- `scripts/utils/fetcher.py`
- `scripts/utils/detail_page_fetcher.py`
- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`
- `config/stocks.json`
- `data/raw/**`
- `reports/**`
- real `knowledge/10-Stocks/**`

Do not:

- call LLMs
- call network
- launch browsers, Playwright, Chrome, or CDP
- run `xueqiu_monitor_v2.py`
- run `run_黑芝麻智能.py`
- run any `run_*.py` report entry
- run ZhihuCurator or DeepSeek curator
- write to real `knowledge/10-Stocks/**`
- change scoring, risk, technical analysis, price targets, report renderers, or data-source selection

---

## 3. Required Behavior

### 3.1 Summary Helper

In `scripts/utils/claim_verification.py`, add a pure helper:

```python
def summarize_claim_verification_plan(
    plan: ClaimVerificationPlan,
    max_verified: int = 6,
    max_supported: int = 4,
    max_unverified: int = 4,
    max_chars: int = 2500,
) -> Dict[str, Any]:
    """Return a prompt-safe, non-citable claim verification summary."""
```

Requirements:

- Return a plain dict.
- Include counts:
  - `high_credit_claims`
  - `low_credit_claims`
  - `verified`
  - `supported`
  - `unverified`
  - `needs_review`
  - `skipped_files`
- Include capped lists:
  - `verified_claims`
  - `supported_claims`
  - `unverified_claims`
  - optionally `needs_review_claims` if easy and compact
- Prompt-facing claim rows may include only:
  - `claim_text`
  - `action`
  - `verified_by_titles` when resolvable without URLs/file paths
  - `confidence`
  - short `reason`
- Do not include:
  - `url`
  - `source_file`
  - raw `claim_id`
  - raw `verified_by` ids
  - local file paths
  - raw frontmatter
- If a `verified_by` id cannot be resolved to a safe title, omit the title instead of exposing the id.
- Truncate long `claim_text` and reasons deterministically.
- Enforce both per-bucket caps and total `max_chars` budget.

### 3.2 KnowledgeSynthesizer Prompt Appendix

In `scripts/utils/knowledge_synthesizer.py`:

- Allow `synthesize(stock_name, all_data)` to read optional `all_data["claim_verification_context"]`.
- Pass the context to `_synthesize_theme()` and `_build_prompt()`.
- Add a helper such as `_format_claim_verification_context(context)` to render a guarded appendix.
- The appendix must state:
  - it is not a new citation source
  - it must not be cited with `[^n]`
  - it must not alone create facts
  - `verified` can guide emphasis only when the same fact appears in numbered sources
  - `supported` is not confirmed fact
  - `unverified` must remain market/community discussion and must not enter core facts
- Append order must be:
  1. numbered source lines
  2. claim verification context appendix
  3. previous narratives section
- Do not change citation parsing semantics.

### 3.3 SynthesisSkill Wiring

In `scripts/utils/report_skills/synthesis_skills.py`:

- Read `enable_claim_verification_context` from ctx, default `False`.
- When disabled, do not import or call the claim verification builder/helper.
- When enabled, build context before choosing modern vs legacy synthesis path.
- Wrap the full context build in one try/except:
  - import
  - base dir resolution
  - `build_claim_verification_plan()`
  - `summarize_claim_verification_plan()`
  - appendix/context preparation
- On success:
  - set `claim_verification_status` to `ok` if there is usable context
  - set `claim_verification_summary` to the sanitized summary
  - set `claim_verification_error` to `""`
- On empty/no usable context:
  - set status to `empty` or `no_usable_claims`
  - pass no context to the synthesizer
- On error:
  - set `claim_verification_status="error"`
  - set `claim_verification_error` to a short string
  - continue normal synthesis without context
- Modern path:
  - call `KnowledgeSynthesizer.synthesize(stock_name, {"items": items, "claim_verification_context": summary})` when context exists.
- Legacy `.chat(prompt)` path:
  - extend `_legacy_llm_synthesize()` and `_build_prompt()` so the same guarded appendix is included when context exists.
  - Do not silently drop context when enabled.

### 3.4 Reporter Config Pass-Through

In `scripts/utils/stock_reporter.py`:

- Accept optional per-stock config:

```json
"claim_verification": {
  "enabled": true,
  "base_dir": "knowledge",
  "max_verified": 6,
  "max_supported": 4,
  "max_unverified": 4
}
```

- Do not modify `config/stocks.json`.
- Pass these into `pipeline_input` only when `enabled=True`.
- Claim verification context should not require Agent-Reach to be enabled, because it reads existing local knowledge notes.
- If `base_dir` is provided, pass it as `claim_verification_base_dir`.

---

## 4. Test-First Requirements

Write or update tests before implementation and run the targeted test or test group to confirm failures.

### 4.1 `tests/utils/test_claim_verification.py`

Add tests for:

- `summarize_claim_verification_plan()` returns plain dict counts.
- It strips `url`, `source_file`, raw ids, and local paths.
- It resolves `verified_by_titles` from safe claim titles when possible.
- It omits unresolved ids.
- It caps verified/supported/unverified rows.
- It truncates long claim text and respects `max_chars`.

### 4.2 `tests/utils/test_knowledge_synthesizer.py`

Add tests for:

- `_build_prompt()` includes guarded claim verification appendix when context is provided.
- The appendix says it is non-citable and must not be used as standalone fact.
- Prompt order is numbered sources -> verification context -> previous narratives.
- `_parse_with_citations()` behavior is unchanged by the existence of verification context; it only parses actual LLM output text.

### 4.3 `tests/reporter/test_synthesis_skills.py`

Add tests for:

- Disabled default does not call claim verification builder/helper.
- Enabled modern path passes sanitized context to fake synthesizer.
- Builder/helper exception sets status `error` and falls back to normal synthesis.
- Empty/no usable context does not pass prompt context.
- Legacy `.chat(prompt)` path includes the guarded appendix when enabled.
- Existing tests still pass without requiring config changes.

### 4.4 `tests/reporter/test_stock_reporter_agent_reach_config.py`

Add tests for:

- Default reporter does not set `enable_claim_verification_context`.
- Per-stock `claim_verification.enabled=True` passes enable flag and caps/base_dir into `pipeline_input`.
- This pass-through does not require `agent_reach.enabled=True`.
- No test should edit `config/stocks.json`.

---

## 5. Required Verification

Run focused tests:

```bash
python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_stock_reporter_agent_reach_config.py -q
```

If failures point to unrelated pre-existing import/collection issues, record the exact failure and run narrower focused commands for changed files.

Do not run full report generation in this implementation round. Phase 5 prompt/sample-output review is a separate acceptance step after Codex reviews the diff.

---

## 6. Required Notes

Write `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-implementation-claude-notes.md` with:

```markdown
# Claude Notes: Claim Verification Phase 5 Synthesis Integration

## Summary

- 

## Files Changed

- 

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
|  |  |  |

## Requirement-Test Matrix

| Design Requirement | Implementation Location | Test/Verification |
|--------------------|-------------------------|-------------------|
| Default-off behavior |  |  |
| Sanitized summary strips uncitable metadata |  |  |
| Modern KnowledgeSynthesizer receives guarded context |  |  |
| Legacy `.chat(prompt)` receives guarded context |  |  |
| Error fallback continues normal synthesis |  |  |
| Reporter config pass-through |  |  |

## Sample Prompt Appendix

Include one short sanitized prompt appendix example generated by unit-test fixtures. Do not call an LLM.

## Local Command Used

```bash

```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
```

---

## 7. Stop Conditions

Stop and write the blocker into the notes file if:

- You need to modify files outside the allowed list.
- You need to modify scoring, technical analysis, data collection, report renderers, or real config.
- You need to call an LLM, network, browser, Chrome, Playwright, CDP, or report entry script.
- The design contradicts current code in a way that requires broader architecture changes.
- Tests expose broad unrelated failures.
