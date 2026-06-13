# Claim Verification Phase 4C Real Legacy Corpus Validation Claude Task

> Date: 2026-06-13  
> Owner: Codex  
> Implementer: Claude Code  
> Scope: Runtime validation only  
> Depends on: `scripts/utils/claim_verification.py`  

---

## Mission

Run claim verification against a stock that has real legacy Xueqiu/Zhihu social notes.

Phase 4B only smoke-tested 黑芝麻智能 with fallback stubs because it had no real legacy social notes. Phase 4C should use a real legacy corpus, preferably `三花智控`, to judge whether Phase 4 claim verification is useful enough for Phase 5, or whether we need deterministic/LLM claim extraction first.

This is not a coding task.

---

## Hard Boundaries

Do not modify source code.

Allowed repo write:

- Create only: `docs/agent_workflow/2026-06-13-claim-verification-phase4c-real-legacy-validation-claude-notes.md`

Allowed temporary writes:

- `/tmp/claim_verification_phase4c_validation/**`

Do not modify:

- `scripts/**`
- `tests/**`
- `config/**`
- `reports/**`
- real `knowledge/10-Stocks/**`
- existing docs except the one notes file listed above

Do not:

- run `xueqiu_monitor_v2.py`
- run `run_黑芝麻智能.py`
- run any `run_*.py` report entry
- run ZhihuCurator or DeepSeek curator
- call LLMs
- call network
- launch browser, Playwright, Chrome, or CDP
- write evidence notes into real `knowledge/10-Stocks/**`
- connect claim verification to pipeline
- change `scripts/utils/claim_verification.py`

---

## Stock Selection

Prefer `三花智控`.

Before running verification, inspect the real knowledge directories read-only:

```text
knowledge/10-Stocks/三花智控/*.md
knowledge/10-Stocks/中简科技/*.md
knowledge/10-Stocks/乐鑫科技/*.md
knowledge/10-Stocks/圣邦股份/*.md
knowledge/10-Stocks/长春高新/*.md
```

Choose the first stock with at least 3 legacy markdown notes excluding `MOC.md`.

Record in notes:

- selected stock
- number of legacy markdown files found
- whether files are untracked or modified is irrelevant; do not edit them

If none have at least 3 files, use the stock with the most legacy files and record the limitation.

---

## Validation Setup

Use a temporary knowledge base root:

```text
/tmp/claim_verification_phase4c_validation/knowledge
```

Create this shape:

```text
/tmp/claim_verification_phase4c_validation/knowledge/10-Stocks/<selected_stock>/
  copied legacy social notes from real knowledge/10-Stocks/<selected_stock>/*.md
  evidence/
    temporary high-credit evidence notes
```

Rules:

- Copy real legacy notes into temp only.
- Include `MOC.md`; claim verification should skip it by filename.
- Do not edit the real files.
- Do not create fallback social stubs unless there are zero legacy files. If zero legacy files, record blocker and stop after focused tests.

---

## Temporary Evidence Notes

Create temporary high-credit evidence notes that are intentionally simple and source-specific.

For `三花智控`, create these evidence notes under temp `evidence/`:

1. `company-official-thermal-management.md`

```yaml
stock: 三花智控
source_type: company_official
source_credit: 85
verification_status: primary_source
knowledge_eligible: true
report_eligible: true
source_platform: manual_validation
title: 三花智控新能源汽车热管理业务说明
url: https://example.com/sanhua-official-thermal
topics: [product_progress, earnings_business]
claims:
  - claim_text: 三花智控业务包含新能源汽车热管理相关产品和客户应用。
    topics: [product_progress, earnings_business]
    claim_status: fact_candidate
```

2. `company-official-robotics.md`

```yaml
stock: 三花智控
source_type: company_official
source_credit: 85
verification_status: primary_source
knowledge_eligible: true
report_eligible: true
source_platform: manual_validation
title: 三花智控机器人执行器业务进展
url: https://example.com/sanhua-official-robotics
topics: [product_progress, market_sentiment]
claims:
  - claim_text: 三花智控存在机器人执行器相关业务布局或市场关注。
    topics: [product_progress, market_sentiment]
    claim_status: fact_candidate
```

3. `broker-research-earnings.md`

```yaml
stock: 三花智控
source_type: broker_research
source_credit: 65
verification_status: professional_analysis
knowledge_eligible: true
report_eligible: true
source_platform: manual_validation
title: 三花智控研报关注业绩与估值
url: https://example.com/sanhua-broker-earnings
topics: [earnings_business]
claims:
  - claim_text: 券商研究通常关注三花智控的营收、盈利和估值变化。
    topics: [earnings_business]
    claim_status: professional_analysis
```

Important:

- These are validation fixtures, not real sourced knowledge.
- They must live only under `/tmp`.
- Record this limitation clearly in notes.

If selected stock is not `三花智控`, create 2-3 generic validation evidence notes using that stock name and the obvious topics appearing in its legacy note filenames/categories. Keep `source_platform: manual_validation` and `url: https://example.com/...`.

---

## Commands To Run

First confirm focused tests still pass:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Then create and run a temporary validation script under `/tmp`, for example:

```bash
python3 /tmp/claim_verification_phase4c_validation/run_validation.py
```

The script should:

1. Choose stock according to the selection rule.
2. Create the temp knowledge tree.
3. Copy legacy notes from real `knowledge/10-Stocks/<selected_stock>/*.md` into temp.
4. Write temporary high/medium-credit evidence notes into temp.
5. Import `build_claim_verification_plan` and `claim_verification_plan_to_dict` from `scripts/utils/claim_verification.py`.
6. Run:

```python
plan = build_claim_verification_plan(selected_stock, temp_knowledge_root, dry_run=True)
plan_dict = claim_verification_plan_to_dict(plan)
```

7. Save plain dict output to:

```text
/tmp/claim_verification_phase4c_validation/claim_verification_plan.json
```

8. Save summary to:

```text
/tmp/claim_verification_phase4c_validation/summary.json
```

9. Print a concise summary:

- selected stock
- legacy file count copied
- high-credit claim count
- low-credit claim count
- skipped file count and reasons
- verification action counts
- top 20 verification rows: source file, claim text, action, confidence, verified_by count, reasons

Do not leave temporary scripts inside the repo.

---

## Analysis Requirements

In the notes file, inspect the plan and answer:

1. Did the module skip `MOC.md` correctly?
2. Did all real legacy notes remain low-credit?
3. Did any social note verify another social note? This must be no.
4. How many low-credit claims came from explicit frontmatter claims vs `legacy_social_stub`?
5. What percentage of low-credit claims became `verified`, `supported`, `needs_review`, and `unverified`?
6. Are `verified` results actually credible, or are they driven by generic terms like `合作`, `增长`, `收入`, `芯片`, `公告`?
7. Are many useful claims stuck as `unverified` because the social stub text is too coarse?
8. Are medium-credit evidence notes producing only `supported`, never `verified`?
9. Does this result suggest:
   - Phase 5 can integrate verification plan into KnowledgeSynthesizer, or
   - we need Phase 4D claim extraction before Phase 5?
10. What exact next change do you recommend?

---

## Expected Interpretation

Good signs:

- Real legacy notes load as low-credit.
- `MOC.md` is skipped.
- Social notes never verify other notes.
- Specific matches become `verified` or `supported`.
- Vague/generic matches become `needs_review` or `unverified`.

Warning signs:

- Most claims are `legacy_social_stub` with no useful content.
- Almost everything is `unverified` because stubs are too coarse.
- Too many claims are `verified` from one generic word.
- Medium-credit claims become `verified`; this would be a bug.

---

## Notes File To Write

Create:

```text
docs/agent_workflow/2026-06-13-claim-verification-phase4c-real-legacy-validation-claude-notes.md
```

Include:

- commands run
- selected stock and why
- temp paths used
- test result
- legacy corpus summary
- verification plan summary
- action counts and percentages
- 10-20 representative rows
- answers to the analysis questions
- confirmation that no real `knowledge/10-Stocks/**` files were written
- confirmation that no source code was modified
- blockers or limitations

---

## Final Response Format

Reply with:

```text
Phase 4C real legacy validation complete.

Tests:
- ...

Selected stock:
- ...

Temp output:
- /tmp/claim_verification_phase4c_validation/claim_verification_plan.json
- /tmp/claim_verification_phase4c_validation/summary.json

Summary:
- legacy_files: ...
- high_credit_claims: ...
- low_credit_claims: ...
- actions: ...

Key findings:
- ...

Recommendation:
- ...

Notes:
- docs/agent_workflow/2026-06-13-claim-verification-phase4c-real-legacy-validation-claude-notes.md

Blockers:
- None / ...
```
