# Credit-Aware Synthesis Layer Phase 1 — Implementation Notes

Date: 2026-06-15

## Files Changed

Implementation:

- `scripts/utils/synthesis_credit.py` (new)
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`

Tests:

- `tests/utils/test_synthesis_credit.py` (new)
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`

Notes:

- `docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-claude-notes.md` (this file)

## Helpers Added

`scripts/utils/synthesis_credit.py` provides shared helpers used by both `KnowledgeSynthesizer` and `SynthesisSkill`:

- `credit_usage_rules_text()` — returns the prompt-level credit-usage rules block.
- `derive_synthesis_usage(item_or_meta)` — returns `{credit_tier, usage, display_label}` for a `SynthesisItem` or citation metadata dict. Prefers structured metadata (`source_credit`, `source_type`, `verification_status`) then falls back to `source_platform`.
- `format_synthesis_source_line(index, item)` — formats a numbered source line with credit/usage labels.
- `is_core_fact_supporting_source(source, meta)` — deterministic hard filter for core-fact provenance.
- `format_claim_verification_appendix(context)` — shared guarded, non-citable claim-verification appendix used by both prompt paths.

## Hard-Filter Rules

Allowed to support core facts:

- Source family `公告` / `官方` / `交易所` / `巨潮`
- Any source whose metadata indicates `source_credit >= 80` AND a confirmed-fact `source_type` or `verification_status` (`exchange_announcement`, `company_ir`, `company_official`, `announcement`, `official`, `confirmed_fact`, `primary_source`)

Rejected as core-fact support:

- `研报`
- `新闻`
- `雪球`
- `知乎`
- `微信公众号` (unless explicitly high-credit confirmed by metadata)
- `AgentReach(...)`
- `资金流向`
- `unknown`

Implementation: `_fill_citation_metadata()` now preserves `source_credit`, `source_type`, and `verification_status` from `item.extra`. `_enrich_core_fact_provenance()` calls `is_core_fact_supporting_source(source, meta)` for every citation; rejected sources set `invalid_or_excluded = True` and are not added to `accepted_labels`.

## Invalid Ref Handling

- Phase 1 does **not** drop invalid core facts.
- Facts whose refs are all rejected/missing get `provenance_status: invalid_ref` and `source_labels: []`.
- `DeepAnalysisRenderer` already renders `invalid_ref` facts as `引用无效 (unknown)`; this behavior is preserved and covered by existing tests.
- Invalid-ref facts do not feed scoring, position advice, final recommendation, or numbered citations; they are only displayed in the core-facts audit table.

## WeChat Fallback

`微信公众号` is mapped explicitly in `derive_synthesis_usage()`:

- If metadata indicates a publisher/article source (`extra.account` present, `account_type` in `official/publisher/media`, or `source_type` in `official/publisher/article/media`), it is treated as `medium / professional_observation`.
- Otherwise it defaults to `low / discussion_only`.

This follows the task instruction to make the mapping explicit and prefer the safer low tier when metadata is unclear.

## Prompt Changes

### `KnowledgeSynthesizer._build_prompt()`

- Credit-usage rules are now emitted **before** the numbered source lines.
- Numbered source lines use `format_synthesis_source_line()` and include `信用层` / `可用方式` labels.
- Claim-verification appendix uses the shared helper and includes:
  - `已验证讨论线索`
  - `部分支持讨论线索`
  - `未验证市场讨论`
  - explicit statement that Phase 1 does not output a `corroborated` bucket
  - reminder that repeated low-credit-only claims are only community attention

### `KnowledgeSynthesizer.extract_core_facts()`

Prompt now explicitly excludes:

- 券商/媒体观点本身
- 社区讨论观点本身
- supported/unverified discussion
- 多源低信用社区共振线索
- analyst inference / prediction / “可能、预计、推测、若...则...”

And requires that only high-credit official/announcement/exchange/confirmed references become core facts.

### `SynthesisSkill` legacy `.chat(prompt)` path

- `_build_prompt()` now injects `credit_usage_rules_text()`.
- `_format_claim_verification_appendix()` uses the shared helper, so the legacy appendix has the same wording constraints as the modern path.

## Test Results

Focused tests:

```text
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_synthesis_credit.py -q
# 91 passed
```

Related regression:

```text
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_source_intake_evidence_renderer.py -q
# 33 passed
```

## Deviations

- `format_synthesis_source_line()` was added to the helper API even though the task listed only three required public helpers; it is needed so both `KnowledgeSynthesizer` and `SynthesisSkill` produce identical source-line labels without duplicating code.
- The task listed `derive_synthesis_usage(item_or_meta)` accepting a single argument; the implementation keeps that signature and internally normalizes both `SynthesisItem` and dict metadata.
- No new renderer was added for invalid refs; existing `DeepAnalysisRenderer` behavior is preserved.

## Blockers

None. Phase 1 implementation is complete and all required tests pass.
