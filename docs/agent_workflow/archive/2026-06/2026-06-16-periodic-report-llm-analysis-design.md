# Periodic Report LLM Analysis Design

Date: 2026-06-16

## Goal

Add an optional LLM-assisted analysis layer for annual and semiannual reports, so long periodic reports can produce useful management-narrative and financial-forensics summaries without promoting them into confirmed facts, scoring inputs, or final recommendations.

This is a second layer after the deterministic `periodic_report_extractor`:

```text
periodic report text
  -> deterministic extractor
  -> selected excerpt items
  -> bounded LLM analysis
  -> periodic_report_analysis observation
  -> optional display / evidence-note use
```

The LLM is not a replacement for extraction. It only compresses and organizes already-selected excerpts.

## Current State

The current periodic report work already provides:

- `scripts/utils/periodic_report_extractor.py`
  - standalone, no network, no LLM
  - emits `risk_disclosure`, `management_view`, `capital_action`, `financial_forensics`
  - renders compact Markdown for human review
- Source Intake integration
  - creates `periodic_report_excerpt` items
  - `source_credit: 75`
  - `verification_status` remains typed as the extractor usage
  - excluded from core synthesis and representative evidence rows
  - rendered in a dedicated `### 定期报告关键摘录` subsection
- Safety guards
  - evidence notes never write periodic excerpts as `fact_candidate`
  - Source Intake renderer guards malformed `confirmed_fact`
  - periodic excerpts do not enter `KnowledgeSynthesizer` context

Recent preview feedback showed that deterministic extraction can find useful management and capex paragraphs, but pure rule excerpts are still too flat. The missing piece is not more raw text; it is a bounded summarizer that can cluster and compare extracted observations.

## Non-Goals

This phase does **not**:

- send the full annual/semiannual report to an LLM
- modify `KnowledgeSynthesizer` prompt or multi-source synthesis behavior
- modify `scoring_engine.py`, EV, risk scoring, technical analysis, position advice, or final recommendation
- add periodic report analysis to core facts
- add claim-verification schema states
- create numbered Markdown references
- write to `knowledge/` by default
- change Xueqiu, Zhihu, Agent-Reach, or social-media intake

The LLM output is an interpretation layer over official filings, not a source of new facts.

## Credit Semantics

The underlying annual/semiannual filing is official, but this layer is generated from rule-selected snippets plus LLM compression. Therefore the output must stay below official-fact status.

Recommended metadata:

```python
{
    "source_type": "periodic_report_analysis",
    "source_credit": 75,
    "verification_status": "professional_analysis",
    "claim_status": "professional_analysis",
    "knowledge_eligible": False,
    "report_eligible": True,
}
```

Required constraints:

- Never emit `confirmed_fact`.
- Never emit `fact_candidate`.
- Never enter `core_facts`.
- Never become a risk-scoring structured signal.
- If later written as an evidence note, it must remain `professional_analysis`.

## Input Contract

The LLM input is built only from extractor items, not the whole report text.

Allowed input fields:

- extractor `schema_version`
- `report_type`
- `audit_status`
- `industry`
- selected item ids
- item `usage`
- item `severity`
- item `title`
- item `evidence`

Excluded input:

- full report text outside selected items
- raw PDF/Jina metadata
- raw URLs
- numbered citation markers
- Source Intake news/research/community items

Recommended caps:

- max extractor items into LLM: 20
- max evidence chars per item: 700
- max total prompt excerpt chars: 12000
- prioritize items in this order:
  1. `financial_forensics`
  2. `risk_disclosure`
  3. `management_view`
  4. `capital_action`

This keeps the LLM focused on the strongest report evidence and avoids reintroducing full-report noise.

## Output Schema

The LLM must return JSON only:

```json
{
  "schema_version": "periodic_report_llm_analysis.v1",
  "report_type": "annual_report",
  "audit_status": "audited",
  "sections": [
    {
      "usage": "management_narrative",
      "title": "管理层叙事主线",
      "summary": "公司将高性能碳纤维与预浸料、功能材料并列为业务扩展方向，但该表述仍属于管理层叙事。",
      "evidence_refs": ["management_view-0", "management_view-2"],
      "confidence": 70
    }
  ],
  "follow_up_questions": [
    {
      "question": "四期项目投产节奏是否能被后续在建工程转固和收入放量验证？",
      "evidence_refs": ["capital_action-0"]
    }
  ]
}
```

Allowed `sections[].usage`:

- `management_narrative`
- `business_change`
- `risk_tension`
- `financial_red_flag`
- `capital_allocation`

Follow-up questions must only appear in the top-level `follow_up_questions` array. They are not a valid `sections[].usage` value.

Required output rules:

- Every section must have at least one valid `evidence_refs` entry.
- `evidence_refs` must reference extractor item ids generated before the LLM call.
- `summary` must not introduce numbers, dates, product names, customers, or capex claims absent from referenced extractor items.
- `confidence` must be an integer between 0 and 100.
- No Markdown footnotes such as `[^1]`, `[^verified]`, `[1]`.
- No `corroborated`, `confirmed`, or `officially verified` wording unless it describes the underlying filing source in a guarded way.

## Prompt Guardrails

The prompt must state, in Chinese:

- 你只能基于给定摘录总结，不能补充外部事实。
- 管理层讨论与年报摘录可以反映公司叙事和披露口径，但不等同于外部验证事实。
- 对 `risk_disclosure` 应写成公司披露的风险，不得写成风险已经发生。
- 对 `management_view` 应写成管理层表述/公司称/年报称，不得写成独立事实。
- 对 `financial_forensics` 应写成规则观察或待复核线索，不得写成会计造假结论。
- 如果证据不足，输出 follow-up question，不要编造结论。
- JSON only。

The prompt should include an explicit illegal-output list:

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

## Deterministic Validation

The LLM output must be validated before it can be used.

Reject the whole analysis if:

- JSON parse fails
- `schema_version != periodic_report_llm_analysis.v1`
- any section has no valid `evidence_refs`
- any `evidence_refs` points to a missing extractor item
- any summary contains Markdown citation markers
- any output field contains `confirmed_fact` or `fact_candidate`
- output has more than 8 sections or 8 follow-up questions

Drop individual sections if:

- `usage` is unknown
- `confidence` is malformed
- `confidence` is not an integer in `[0, 100]`
- `summary` is empty after sanitization
- summary is longer than 500 Chinese characters

Sanitize:

- remove `[^n]`, `[n]`, `[^verified]`, `[^supported]`, `[^needs_review]`, `[^unverified]`
- strip raw URLs
- normalize whitespace

Open question for implementation review: whether to add a stricter number/entity guard that rejects numbers not present in referenced evidence. It is desirable but may need careful Chinese-token handling.

Phase 1 decision after Round 1 review: deterministic number/entity novelty detection is deferred to Phase 1.1. Phase 1 output must therefore remain helper-only and must not be used as a source for new numbers, new factual claims, Source Intake observations, core facts, synthesis context, risk scoring, or recommendations. Before `periodic_report_analysis` can enter Source Intake or multi-source synthesis, a Phase 1.1 guard must reject summaries that introduce numbers, dates, products, customers, capex figures, growth rates, or named entities absent from the referenced extractor evidence.

## Standalone Interface

Recommended helper module:

```text
scripts/utils/periodic_report_llm_analysis.py
```

Primary API:

```python
def build_periodic_report_llm_prompt(extractor_result: dict, *, max_items: int = 20) -> dict:
    ...

def validate_periodic_report_llm_output(raw_text: str, item_map: dict) -> dict:
    ...

def summarize_periodic_report_with_llm(extractor_result: dict, client: Any) -> dict:
    ...
```

The helper should be testable with a fake client. It should not import OpenAI/DeepSeek clients at module import time.

CLI is explicitly out of scope for Phase 1.

Future CLI option:

```text
python3 scripts/periodic_report_extractor.py report.txt --llm-summary
```

If added later, it must go through a narrow CLI safety review, remain opt-in, fail closed when no client is configured, and never run from existing extractor commands by default.

## Source Intake Integration

Phase 1 should not automatically connect LLM analysis to Source Intake. It should first produce a standalone preview artifact for human review.

Phase 1.5 may add optional Source Intake integration:

- one `SynthesisItem` per validated LLM section
- `source_type: periodic_report_analysis`
- `source_credit: 75`
- `verification_status: professional_analysis`
- dedicated renderer subsection, separate from `定期报告关键摘录`
- excluded from representative evidence rows
- excluded from synthesis context and core facts

Do not merge the LLM analysis into `periodic_report_excerpt` items; keeping the type separate makes later auditing easier.

## Multi-Source Synthesis Later

The later multi-source stage should consume:

- high-credit company announcements / exchange filings
- medium-credit research/news/policy observations
- verified/supported claim-verification results
- optional `periodic_report_analysis`

Recommended usage:

- `periodic_report_analysis` can inform `专业背景与产业判断`.
- It can be compared against outside evidence to create `多来源验证观察`.
- It still cannot by itself become a core fact or final recommendation driver.

Example wording:

- “年报管理层将业务扩展描述为 X；该叙事需要结合后续订单、在建工程转固和现金流验证。”
- “该线索获得公告/中信用来源部分支持，但仍非官方确认。”

## Testing Plan

Focused tests should cover:

- prompt builder includes extractor items, not full report text
- prompt caps item count and evidence length
- prompt includes credit/usage guardrails
- validator accepts valid JSON with valid refs
- validator rejects schema mismatch
- validator rejects missing/invalid refs
- validator removes illegal citation markers
- validator rejects `confirmed_fact` / `fact_candidate`
- malformed confidence is dropped or normalized safely
- `confidence < 0` and `confidence > 100` sections are dropped
- `sections[].usage == "follow_up_question"` is rejected
- empty extractor results return an empty analysis without calling the LLM client
- fake-client summary returns `source_credit <= 75` and `professional_analysis`
- fake-client summary returns metadata with `knowledge_eligible: False` and `report_eligible: True`
- no import-time OpenAI/DeepSeek dependency
- disabled/default extractor path does not call LLM
- `periodic_report_analysis` cannot become fact_candidate if evidence-note support is added later

Runtime verification should be narrow:

1. Run focused tests.
2. Run standalone preview on `/tmp/zhongjian_2025_annual_jina.txt`.
3. If real LLM is used, show only the generated analysis preview and confirm:
   - no new unsupported numbers
   - no illegal citations
   - no confirmed-fact wording
   - management/capex/risk labels are clear
4. Do not run a full report unless the user explicitly asks.

## Allowed Files For First Implementation

Allowed:

- `scripts/utils/periodic_report_llm_analysis.py`
- `tests/utils/test_periodic_report_llm_analysis.py`
- `docs/agent_workflow/*-periodic-report-llm-analysis-claude-notes.md`

Do not modify in Phase 1:

- `KnowledgeSynthesizer`
- `synthesis_skills.py`
- `scripts/periodic_report_extractor.py`
- `source_intake_merge_skill.py`
- `source_intake_evidence_renderer.py`
- `evidence_note_writer.py`
- `scoring_engine.py`
- technical-analysis modules
- `config/stocks.json`
- `knowledge/`
- `reports/`
- `data/raw/`

If implementation needs any forbidden file, stop and return to design review.

## Open Questions For Review

1. Should the first implementation include a CLI `--llm-summary`, or keep only a helper + tests?
2. Should number/entity novelty detection be mandatory in Phase 1, or deferred after basic validation?
3. Should the output be rendered as Markdown preview by the standalone extractor, or only JSON at first?
4. Should `periodic_report_analysis` eventually be written to evidence notes, or stay runtime-only until multi-source synthesis is designed?

Round 1 resolution:

- Phase 1 is helper-only. No CLI.
- Number/entity novelty detection is deferred to Phase 1.1 and is mandatory before any Source Intake or synthesis integration.
- Markdown preview can be helper-level only if implemented without touching the CLI.
- Evidence notes are out of scope until Phase 1.5.

## Round 1 Feedback

**Reviewer**: Claude Code
**Date**: 2026-06-16
**Scope**: Read-only design review of `periodic_report_llm_analysis` Phase 1; no file changes.

### Status

**Ready to implement** as a helper-only Phase 1.

- **R2 Needed**: **No** for the helper + tests. If the team decides to add the `--llm-summary` CLI in Phase 1, a narrow CLI safety review is recommended, but it does not require a full R2.

### Findings by Severity

#### High: Number/entity novelty detection is the largest unclosed risk
- **Location**: `Deterministic Validation` section, line 215
- **Issue**: The validator rejects `confirmed_fact` / `fact_candidate` wording and citation markers, but it has no mechanism to detect when the LLM introduces numbers, dates, customer names, product names, capex figures, or growth rates that were **not** present in the referenced extractor items. This is exactly the failure mode the design is trying to prevent: LLM compression turning management narrative into seemingly precise claims.
- **Impact**: A malformed or over-eager LLM could output `"公司2025年营收同比增长42.86%"` even though the referenced excerpt only said `"营业收入保持增长"`. The validator would accept it because there are no illegal strings.
- **Verdict**: **Not a Phase 1 blocker** if the feature stays helper-only and never enters Source Intake / scoring / synthesis. **Must be a Phase 1.1 or Phase 2 blocker** before any Source Intake integration.
- **Suggested fix for Phase 1.1**: Add a deterministic post-validator that extracts Arabic numerals and percentage patterns from referenced extractor `evidence` fields and rejects any summary containing a number/percentage not found in the union of referenced evidence. For product/customer names, maintain an allowlist derived from referenced evidence.

#### High: `follow_up_question` appears both as a section usage and as a top-level array
- **Location**: `Output Schema` section
- **Issue**: The schema has `sections[].usage` include `follow_up_question`, but also has a separate top-level `follow_up_questions` array. This is ambiguous. If a section has `usage: follow_up_question`, does it render as a section or move to the top-level array? Duplicate representation increases parser/validator complexity.
- **Suggested fix**: Remove `follow_up_question` from `sections[].usage`. Keep questions only in the top-level `follow_up_questions` array. Each question still references extractor items via `evidence_refs`.

#### Medium-High: CLI `--llm-summary` adds integration and accidental-pipeline risk
- **Location**: `Standalone Interface` and `Allowed Files For First Implementation`
- **Issue**: Adding an opt-in CLI flag to `scripts/periodic_report_extractor.py` is reasonable, but it creates a path where a user or script could accidentally invoke LLM analysis from the existing extractor command. It also requires the CLI to load an LLM client configuration, handle API keys, and manage timeouts.
- **Verdict**: Defer CLI to Phase 1.1. Helper + tests is enough to prove the contract.
- **Suggested fix**: Keep the allowed file list, but make CLI explicitly out of scope for Phase 1. If a CLI is added later, require `--llm-summary` to be the only opt-in flag and fail closed if no client is configured.

#### Medium: Prompt illegal-output list uses regex notation `[^\w+]` which is unclear
- **Location**: `Prompt Guardrails` section
- **Issue**: The list says `[^\w+]`. This is a regex class, not a literal string the LLM should avoid. Listing it alongside literal strings like `[^verified]` is confusing.
- **Suggested fix**: Replace with explicit literals: `[^1]`, `[^12]`, `[^supported]`, `[^verified]`, `[^needs_review]`, `[^unverified]`.

#### Medium: No explicit test that the helper does not import OpenAI/DeepSeek at module load
- **Location**: `Testing Plan`
- **Issue**: The design says the helper "should not import OpenAI/DeepSeek clients at module import time", and there is a test bullet "no import-time OpenAI/DeepSeek dependency", but there is no concrete test description.
- **Suggested fix**: Add a test that runs `subprocess` to import `scripts.utils.periodic_report_llm_analysis` in an environment where `openai` / `deepseek` are unavailable (or mocked as missing) and asserts the import succeeds.

#### Medium: `periodic_report_analysis` is not covered by existing `evidence_note_writer` source-type guard
- **Location**: `scripts/utils/evidence_note_writer.py::_claim_status_for_item()` (existing code)
- **Issue**: The writer currently hard-guards only `periodic_report_excerpt`. The design correctly says Phase 1 does **not** connect to evidence notes. However, the `Multi-Source Synthesis Later` section contemplates future Source Intake integration. When that happens, the guard must be extended to `periodic_report_analysis`.
- **Verdict**: Not a Phase 1 blocker because Phase 1 does not integrate with notes. Must be fixed before Phase 1.5.
- **Suggested fix**: Add `periodic_report_analysis` to the guard in `_claim_status_for_item` when Phase 1.5 is implemented.

#### Low: `knowledge_eligible: False` is correct but should be tested
- **Location**: `Credit Semantics` section
- **Issue**: The metadata sets `knowledge_eligible: False`, which is the right conservative choice for Phase 1. The testing plan does not explicitly assert this.
- **Suggested fix**: Add a test that verifies the returned `SynthesisItem`-like dict has `knowledge_eligible: False` and `report_eligible: True`.

#### Low: Output `sections[].confidence` has no upper-bound enforcement rule in validator
- **Location**: `Output Schema` and `Deterministic Validation`
- **Issue**: The schema says confidence must be 0–100. The validator checks that confidence is malformed, but does not explicitly say it rejects `confidence > 100` or `< 0`.
- **Suggested fix**: Add a validator rule: drop sections where `confidence` is not an integer or not in `[0, 100]`.

### Required Deltas

1. **Remove `follow_up_question` from `sections[].usage`**; keep it only in the top-level array.
2. **Clarify the prompt illegal-output list** by replacing regex notation with explicit literal examples.
3. **Document that number/entity novelty detection is deferred to Phase 1.1** and that Phase 1 output must never be used as a source of new numbers/claims.
4. **Make CLI `--llm-summary` explicitly out of scope for Phase 1**; leave it as a future option.
5. **Add confidence range validation** to the deterministic validator.

### Missing Tests

The testing plan is strong. Add these focused tests before implementation is considered complete:

1. **Import-time client independence**: import the helper module in a subprocess with no LLM packages and assert success.
2. **Novel number rejection** (or at least placeholder test): if a validator number/entity guard is implemented, assert it rejects summaries with unsupported numbers.
3. **Confidence range enforcement**: `confidence: 120` is rejected/dropped.
4. **`follow_up_question` not in sections**: assert `sections[].usage` cannot be `follow_up_question`.
5. **Empty extractor result**: helper returns empty analysis without calling the LLM client when extractor items are empty.
6. **Knowledge/report eligibility**: returned metadata has `knowledge_eligible: False` and `report_eligible: True`.
7. **No `periodic_report_analysis` accidental pipeline injection**: at helper level, assert the returned object is not a `SynthesisItem` and has no `source_type` that existing pipeline code would misinterpret (or if it is a SynthesisItem, it is clearly typed as `periodic_report_analysis`).

### Open Questions

1. **Number/entity novelty detection**: Will Phase 1.1 implement deterministic extraction of allowed numbers/names from referenced evidence, or will it use a second LLM call to check fidelity? A deterministic approach is strongly preferred for auditability.
2. **Markdown preview rendering**: If Phase 1 stays helper-only, how will humans review the output? Should the helper provide a `render_markdown()` function, or is JSON inspection sufficient?
3. **Client abstraction**: Will the helper accept any client with a `chat.completions.create`-like interface, or will it hard-code DeepSeek/OpenAI? The design says "testable with a fake client", which implies an interface, but this should be explicit.

### Final Recommendation

**Approve Phase 1 as helper-only.**

The design is safe because:

- The LLM input is strictly bounded to extractor items, not the full report.
- The output is typed as `professional_analysis` with `source_credit: 75`, consistent with existing claim-status thresholds.
- Phase 1 does not integrate with Source Intake, evidence notes, scoring, risk, synthesis, or final recommendation.
- The allowed file list is narrow and does not include any pipeline-critical modules.
- The validator rejects schema mismatch, missing refs, illegal citations, and `confirmed_fact` / `fact_candidate` strings.

**Do not add the CLI in Phase 1.** Keep it to:

- `scripts/utils/periodic_report_llm_analysis.py`
- `tests/utils/test_periodic_report_llm_analysis.py`

This minimizes blast radius and allows the team to validate the contract before exposing it through any command-line or pipeline path.
