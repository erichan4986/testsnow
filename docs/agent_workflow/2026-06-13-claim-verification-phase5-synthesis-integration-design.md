# Claim Verification Phase 5 Synthesis Integration Design

> **Date**: 2026-06-13  
> **Owner**: Codex  
> **Status**: Under Claude Review  
> **Workflow Level**: Level 3, with conditional Round 2  
> **Context**: Phase 4D made claim verification useful enough for synthesis integration.

---

## 1. Goal

Integrate the Phase 4 claim verification plan into `KnowledgeSynthesizer` as optional guarded context.

Phase 5 should help the LLM distinguish verified/supportable low-credit social claims from unverified market opinions. It must not turn social content into facts, must not create uncited facts, and must remain disabled unless explicitly enabled by config or direct pipeline input.

The intended user-visible result is safer fundamental synthesis: verified social claims can guide emphasis when the same fact is already present in numbered synthesis sources, while unverified claims are either ignored or described as low-confidence market discussion.

---

## 2. Non-Goals

- Do not change scoring, risk scoring, technical analysis, or price target logic.
- Do not change Agent-Reach fetching, Xueqiu scraping, Playwright, Chrome, CDP, or external API behavior.
- Do not run `xueqiu_monitor_v2.py` as a validation entry.
- Do not enable claim verification context by default.
- Do not write back verification results to `knowledge/`.
- Do not add LLM-based claim extraction.
- Do not add verified claims as new numbered citation sources in Phase 5.
- Do not let verification context produce uncited factual statements in the report.
- Do not treat `supported` or `verified` as investment conclusions.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Evidence notes | Agent-Reach keep/demote items can be written or dry-run as evidence notes when explicitly enabled. | `scripts/utils/report_skills/evidence_note_skill.py`, `scripts/utils/evidence_note_writer.py` |
| Claim verification | Pure dry-run builder reads high-credit evidence notes and low-credit social notes, then returns `ClaimVerificationPlan`. | `scripts/utils/claim_verification.py`, `tests/utils/test_claim_verification.py` |
| Phase 4D result | Real legacy body claims are extracted as low-credit `unverified_claim`; runtime validation reduced the all-unverified blocker. | `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md` |
| Synthesis skill | Builds `SynthesisItem` list from raw data and posts, then calls `KnowledgeSynthesizer.synthesize(stock_name, {"items": items})`. | `scripts/utils/report_skills/synthesis_skills.py` |
| KnowledgeSynthesizer | Builds per-theme LLM prompts from numbered source lines; citation parsing assumes only numbered source items can be cited. | `scripts/utils/knowledge_synthesizer.py`, `tests/utils/test_knowledge_synthesizer.py` |
| Per-stock config | `PerStockReporter` already passes Agent-Reach and evidence-note config into pipeline input. | `scripts/utils/stock_reporter.py`, `config/stocks.json` |

---

## 4. Proposed Design

### 4.1 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| Claim verification summary helper | Convert `ClaimVerificationPlan` into a compact prompt-safe summary. | `ClaimVerificationPlan` | Plain dict/string with counts and capped verified/supported/unverified claim lines |
| `SynthesisSkill` wiring | Optionally build verification context before calling `KnowledgeSynthesizer`; never abort synthesis on verification failure. | `ctx`, stock name, knowledge base dir, enable flag | `claim_verification_status`, `claim_verification_summary`, `claim_verification_error`, `synthesis` |
| `KnowledgeSynthesizer` prompt extension | Append guardrailed verification context to theme prompts. | numbered source items, previous narratives, optional verification context | LLM prompt that separates numbered citable sources from non-citable verification context |
| `PerStockReporter` config pass-through | Allow per-stock config to enable the feature without changing pipeline defaults. | `agent_reach_configs[stock]["claim_verification"]` or top-level stock config block | pipeline input keys |

### 4.2 Data Flow

```text
knowledge/10-Stocks/<stock>/**
  -> build_claim_verification_plan(stock, base_dir, dry_run=True)
  -> summarize verification plan for prompt
  -> SynthesisSkill passes {"items": items, "claim_verification_context": summary}
  -> KnowledgeSynthesizer appends guarded context to each theme prompt
  -> LLM synthesis continues to cite only numbered source items
```

### 4.3 Gating And Config

Default behavior must remain unchanged.

`SynthesisSkill` should read these optional ctx inputs:

| Key | Default | Meaning |
|-----|---------|---------|
| `enable_claim_verification_context` | `False` | Enable Phase 5 prompt context. |
| `claim_verification_base_dir` | repo root `knowledge` | Knowledge base root passed to `build_claim_verification_plan`. |
| `claim_verification_max_verified` | `6` | Max verified claim lines included in prompt. |
| `claim_verification_max_supported` | `4` | Max supported claim lines included in prompt. |
| `claim_verification_max_unverified` | `4` | Max unverified claim lines included in prompt. |

`PerStockReporter` may pass these from optional per-stock config:

```json
"claim_verification": {
  "enabled": true,
  "base_dir": "knowledge",
  "max_verified": 6,
  "max_supported": 4,
  "max_unverified": 4
}
```

Do not add this block to `config/stocks.json` in Phase 5 implementation unless explicitly asked. Tests should exercise direct pipeline input and reporter pass-through with synthetic config.

### 4.3.1 Legacy LLM Path

`SynthesisSkill` currently has two synthesis paths:

- modern path: `KnowledgeSynthesizer.synthesize(stock_name, {"items": items})`
- legacy path: `_legacy_llm_synthesize()` when `llm_client` has a `.chat(prompt)` method

Phase 5 must not silently drop verification context on the legacy path. If `enable_claim_verification_context=True`, `SynthesisSkill` should build the same sanitized verification context before branching, then:

- pass it to `KnowledgeSynthesizer` on the modern path
- append the same guarded non-citable appendix to `_legacy_llm_synthesize()` prompt on the legacy path

This keeps behavior explicit for tests and older local clients. If context build fails, both paths must fall back to normal synthesis with `claim_verification_status="error"`.

### 4.4 Prompt Contract

The verification context is not a citation source. The prompt must say this explicitly.

Required wording intent, not necessarily exact text:

```text
以下“Claim Verification Context”不是新的引用来源，不能用 [^n] 引用，也不能单独作为事实写入正文。
它只用于判断社区观点的可信度：
- verified: 只有当同一事实也出现在上方编号信息来源中时，才可作为重点线索使用，并必须引用上方编号来源。
- supported: 可描述为“有中等信用来源支持的线索”，但不得写成已确认事实。
- unverified: 只能作为“待验证市场观点/社区讨论”，不得进入核心事实基座。
```

`KnowledgeSynthesizer._build_prompt()` should append this section after numbered sources and before previous narratives, so the model sees trust guidance before reading already generated sections.

### 4.5 Summary Shape

The prompt summary should be compact and deterministic. It should include counts plus capped examples.

The summary helper must be prompt-safe and must strip uncitable provenance metadata. Do not include:

- `url`
- `source_file`
- raw `claim_id` / `verified_by` ids
- local file paths
- raw frontmatter dictionaries

Allowed fields in prompt-facing claim rows:

- `claim_text`
- `action` / status bucket (`verified`, `supported`, `unverified`, `needs_review`)
- `verified_by_titles` when a title can be resolved without exposing URLs or file paths
- `confidence`
- short `reason`

If a `verified_by` id cannot be resolved to a safe title, omit the title instead of exposing the id.

Example plain dict:

```python
{
    "enabled": True,
    "stock": "三花智控",
    "counts": {
        "high_credit_claims": 2,
        "low_credit_claims": 11,
        "verified": 4,
        "supported": 0,
        "unverified": 7,
        "skipped_files": 1,
    },
    "verified_claims": [
        {
            "claim_text": "三花智控研报线索：拓展机器人、服务器液冷等新领域",
            "verified_by_titles": ["公司官网热管理业务介绍"],
            "confidence": 85,
        }
    ],
    "supported_claims": [],
    "unverified_claims": [
        {
            "claim_text": "三花智控风险线索：短期资金面分歧",
            "reason": "no high or medium credit source with matching topic and terms",
        }
    ],
}
```

Prompt text should truncate long claim text and cap total section length. A target budget of about 1,500-2,500 Chinese characters is enough for Phase 5.

The helper should cap both counts and total character budget. Count caps prevent one status bucket from dominating; a total character cap prevents unexpectedly long claim text from crowding out numbered source lines.

### 4.6 Error Handling And Fallbacks

- If the feature is disabled, do not import or call claim verification; set no new synthesis prompt context.
- If any part of verification-context construction raises, catch the exception inside `SynthesisSkill`, set `claim_verification_status="error"`, store a short error string, and continue normal synthesis. This includes:
  - importing the claim verification module
  - resolving the knowledge base directory
  - `build_claim_verification_plan()`
  - summary helper conversion
  - prompt appendix rendering
- If knowledge files are missing or no usable claims exist, set status to `empty` or `no_usable_claims`, pass no prompt context, and continue normal synthesis.
- If LLM client is absent and template synthesis is used, claim verification context should not fabricate conclusions. Template output should remain explicit that LLM synthesis is unavailable.

---

## 5. Failure Modes And Tests

| Failure Mode | User/Runtime Symptom | Test Or Check That Catches It |
|--------------|----------------------|-------------------------------|
| Verification context is treated as citable source | LLM emits `[^n]` facts that do not map to source list entries. | `test_build_prompt_marks_claim_verification_context_non_citable()` asserts context says no citation and numbered source list remains unchanged. |
| Unverified social claim becomes core fact | Report core facts include community rumor or `unverified_claim` content as confirmed fact. | Prompt unit test asserts unverified guidance says not to enter core facts; sample-output manual review required after implementation. |
| Disabled feature changes existing synthesis behavior | Existing reports/prompts change without enabling flag. | `test_synthesis_skill_claim_verification_disabled_does_not_call_builder()`. |
| Claim verification failure aborts report generation | Synthesis returns empty or pipeline fails because knowledge note parse failed. | `test_synthesis_skill_claim_verification_error_falls_back_to_normal_synthesis()`. |
| Legacy `.chat(prompt)` synthesis silently drops verification context | Tests pass with legacy fake client but runtime prompt lacks guardrails. | `test_legacy_llm_synthesis_includes_claim_verification_context_when_enabled()`. |
| Prompt becomes too long | LLM latency/cost increases or important source lines are crowded out. | Test summary helper caps verified/supported/unverified counts and truncates long claim text. |
| Reporter config accidentally writes knowledge or enables live collection | Running fast-test modifies `knowledge/` or fetches external data. | Reporter pass-through test uses synthetic config; implementation must not modify `config/stocks.json`; runtime validation uses `--fast-test`. |
| Supported evidence is overstated as verified | Medium-credit source turns a social claim into fact. | Summary helper test keeps `supported` separate and prompt contract says supported is not confirmed. |
| Verification appendix affects citation parsing | Citation extraction sees verification context as numbered sources or refs. | `test_parse_with_citations_ignores_absent_refs_when_verification_context_exists()` or equivalent; `_parse_with_citations()` behavior must depend only on LLM output text. |
| Verification context is appended in the wrong prompt location | Model reads previous narratives before trust guardrails. | Prompt order test asserts numbered sources appear before context and context appears before previous narratives. |

---

## 6. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/claim_verification.py` | Modify | Add pure summary helper, or expose enough data for a local helper. |
| `scripts/utils/report_skills/synthesis_skills.py` | Modify | Optional gating, builder call, ctx status, pass context to synthesizer. |
| `scripts/utils/knowledge_synthesizer.py` | Modify | Accept optional verification context and append guarded prompt section. |
| `scripts/utils/stock_reporter.py` | Modify | Optional per-stock config pass-through. |
| `tests/utils/test_claim_verification.py` | Modify | Summary helper cap/truncation/status tests. |
| `tests/utils/test_knowledge_synthesizer.py` | Modify | Prompt contract tests. |
| `tests/reporter/test_synthesis_skills.py` | Modify | Disabled/error/enabled pass-through tests, plus legacy `.chat(prompt)` context test. |
| `tests/reporter/test_stock_reporter_agent_reach_config.py` or equivalent | Modify/Create | Reporter pass-through tests if no suitable file exists. |
| `docs/agent_workflow/2026-06-13-claim-verification-phase5-synthesis-integration-implementation-claude-notes.md` | Create | Claude implementation notes and requirement-test matrix. |

---

## 7. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/reporter/scoring_engine.py` | Phase 5 does not affect scoring. |
| `scripts/utils/reporter/technical_*.py` | No technical algorithm change. |
| `scripts/utils/reporter/price_target.py` | No valuation algorithm change. |
| `scripts/utils/fetcher.py`, `scripts/utils/detail_page_fetcher.py` | No data collection or browser behavior change. |
| `scripts/xueqiu_monitor_v2.py` | Not the deep-report integration path. |
| `config/stocks.json` | Do not enable the feature globally or per stock without explicit user approval. |
| `data/raw/**`, `reports/**`, `knowledge/**` | Implementation tests should use fixtures/tmp dirs; no real data/report/knowledge churn. |

---

## 8. Data And Reporting Constraints

- Verification context comes only from local `knowledge/10-Stocks/<stock>/**` files read by the Phase 4 dry-run builder.
- The builder must remain dry-run; Phase 5 must not write to `knowledge/`.
- LLM synthesis must not fabricate data.
- Citation markers must still map only to numbered source list entries generated from `SynthesisItem`.
- Xueqiu detail-page access remains prohibited unless separately authorized with logged-in CDP and delay controls; Phase 5 does not need Xueqiu access.
- Any implemented prompt change requires user review of a sample prompt/output before considering the phase complete.

---

## 9. Acceptance Gates

### Focused Tests

```bash
python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py -q
```

If reporter config pass-through touches an existing reporter test file, include it:

```bash
python3 -m pytest tests/reporter/test_stock_reporter_agent_reach_config.py -q
```

### Report Generation

Report generation is required only after focused tests pass and the user approves the prompt sample.

Default validation entry:

```bash
cd scripts
python run_黑芝麻智能.py --fast-test
```

The fast-test run must not refresh Zhihu, run ZhihuCurator/DeepSeek curator, start Chrome/CDP, or fetch Xueqiu detail pages.

### Manual Review

- Confirm the prompt sample clearly distinguishes numbered citable sources from non-citable verification context.
- Confirm unverified claims are not phrased as facts.
- Confirm `core_facts` sample output does not include unverified social claims.
- Confirm no unexpected changes appear under `data/raw/**`, `reports/**`, or `knowledge/**` except natural report outputs during an explicitly requested runtime validation.

---

## 10. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| Should Phase 5 include `verified_claims` in report-facing narrative only when the same fact appears in numbered sources, or should it add evidence notes as citable `SynthesisItem`s in a later Phase 5B? | Codex + Claude | Initial recommendation: do not add evidence notes as citable items in Phase 5; defer to 5B. |
| Should `claim_verification` config live under `agent_reach` or as a separate per-stock block? | Codex + Claude | Initial recommendation: accept both in reporter pass-through if cheap, but do not edit `config/stocks.json`. |
| Is `supported` useful enough for prompt context, or should Phase 5 only pass `verified` and count `unverified`? | Claude review | Initial recommendation: include capped `supported` separately because medium-credit evidence can guide cautious wording. |

---

## 11. Claude Review Log

### Round 1 Feedback

```markdown
### Round 1 Feedback

Status: Must-fix before task

Decision:
- R2 recommended: No
- Reason: The overall integration shape is sound and the safety boundaries are correctly drawn (context-only, default-off, no new numbered sources, no knowledge writeback). The remaining issues are small but should be clarified in the design before implementation starts; they do not require a second full design round.

Findings:
- [Must-fix] Error-handling boundary is incomplete. Section 4.6 says to catch exceptions from `build_claim_verification_plan()`, but the new summary helper and any `ClaimVerificationPlan` -> prompt conversion can also raise. The design should state that the entire verification-context build (plan + summary + prompt rendering) is wrapped in a single try/except inside `SynthesisSkill`, with status `"error"` and normal synthesis continuing.
- [Must-fix] Legacy `SynthesisSkill._legacy_llm_synthesize()` path is undefined for verification context. Current `SynthesisSkill` branches to a `llm_client.chat(prompt)` legacy path when the client has a `.chat` attribute. If claim verification is enabled but this path is taken, the context would be silently dropped or the prompt would omit the guardrails. The design should decide: either disable claim verification when the legacy path is used, or state that the legacy path is out of scope and must not be used with verification enabled.
- [Must-fix] Summary helper field selection is not explicit. Section 4.5 shows a compact example dict, but the design does not mandate that the helper strip `url`, `source_file`, and other provenance fields before prompt insertion. Since verification context is non-citable, the prompt should only carry `claim_text`, status/category, optional `verified_by_titles`, and `confidence`/`reason`; URLs and file paths should be omitted to avoid leaking uncitable metadata.
- [Nice-to-have] Add a focused test that verification context does not alter citation parsing. `KnowledgeSynthesizer._parse_with_citations` should produce the same ref set with or without the verification appendix when the LLM output is identical, confirming the appendix cannot accidentally be interpreted as a numbered source.
- [Nice-to-have] Add a prompt-position test. Section 4.4 says the context goes after numbered sources and before previous narratives; a unit test asserting that order would prevent future regressions if `_build_prompt` is reorganized.

Recommendations:
- Keep the Phase 5 scope as context-only; defer adding evidence notes as numbered `SynthesisItem`s to a later Phase 5B, as proposed in Open Question 1. This preserves the one-way trust boundary and avoids conflating citable sources with verification hints.
- Keep the feature default-off and do not modify `config/stocks.json`; the reporter pass-through should accept the config block only when explicitly provided at runtime.
- In the summary helper, cap total prompt budget in characters (not just claim counts) and truncate `claim_text` deterministically; this is more robust than per-bucket caps alone when claim text length varies.
- Require a sample prompt/output manual review before Phase 5 is marked complete, and include a checklist item to verify that no `core_facts` entry originates from an `unverified_claim` line.

Open Questions:
- None blocking; the three open questions in Section 10 are appropriately scoped and the initial recommendations are accepted.
```

### Design Delta After Round 1

Accepted:
- Context-only integration into `KnowledgeSynthesizer` via optional `claim_verification_context` key.
- Default-off gating with `enable_claim_verification_context=False` and no `config/stocks.json` changes.
- Prompt contract: verification context is explicitly non-citable; `verified`/`supported`/`unverified` guidance as written.
- Error fallback to normal synthesis with status tracking.
- Full verification-context build is wrapped in one `SynthesisSkill` try/except: builder, summary conversion, and prompt appendix rendering.
- Legacy `.chat(prompt)` synthesis receives the same guarded non-citable appendix when verification context is enabled.
- Prompt-facing summaries strip URLs, file paths, raw ids, and other uncitable provenance metadata.
- Nice-to-have tests for citation parsing isolation and prompt ordering are accepted as required focused tests.
- Deferring evidence-note-as-citable-source work to Phase 5B.

Rejected:
- None.

Deferred:
- Evidence notes becoming numbered `SynthesisItem` sources (Phase 5B).
- LLM-based claim extraction (already out of scope).

R2 Required:
- No.

### Round 2 Feedback

- Not run unless Round 1 finds blockers, unresolved must-fix items, high-risk design changes, or prompt safety concerns.

### Final Implementation Readiness

- Ready to implement. The three Round 1 must-fix items are addressed in Sections 4.3.1, 4.5, 4.6, and 5. No Round 2 required. Implementation may proceed with focused tests first and must produce a sample prompt for user review before Phase 5 is considered complete.
