# Claim Verification Phase 4B Runtime Validation Claude Task

> Date: 2026-06-13  
> Owner: Codex  
> Implementer: Claude Code  
> Scope: Runtime validation only  
> Depends on: `scripts/utils/claim_verification.py`  

---

## Mission

Run a dry-run validation of Phase 4 claim verification using a temporary knowledge base.

The goal is to see whether high-credit Black Sesame official evidence can verify or support existing low-credit Xueqiu/Zhihu legacy notes, and whether the generated verification plan is useful enough for the next design step.

This is not a coding task.

---

## Hard Boundaries

Do not modify source code.

Allowed repo write:

- Create only: `docs/agent_workflow/2026-06-13-claim-verification-phase4b-runtime-validation-claude-notes.md`

Allowed temporary writes:

- `/tmp/claim_verification_phase4b_validation/**`

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
- run ZhihuCurator or DeepSeek curator
- call LLMs
- call network
- launch browser, Playwright, Chrome, or CDP
- write evidence notes into real `knowledge/10-Stocks/**`
- connect claim verification to pipeline

---

## Validation Setup

Use a temporary knowledge base root:

```text
/tmp/claim_verification_phase4b_validation/knowledge
```

Create this shape:

```text
/tmp/claim_verification_phase4b_validation/knowledge/10-Stocks/黑芝麻智能/
  copied legacy social notes from real knowledge/10-Stocks/黑芝麻智能/*.md
  evidence/
    six temporary official evidence notes
```

Copy the current legacy social notes from:

```text
knowledge/10-Stocks/黑芝麻智能/*.md
```

Rules:

- Copy them into temp only.
- Include `MOC.md`; claim verification should skip it by filename.
- Do not edit the real files.
- If there are no legacy notes, record that as a blocker in notes and create two low-credit temp social notes so the module can still be smoke-tested.

---

## Temporary Official Evidence Notes

Create six high-credit evidence notes under:

```text
/tmp/claim_verification_phase4b_validation/knowledge/10-Stocks/黑芝麻智能/evidence/
```

Use YAML frontmatter. Each note should have:

- `stock: 黑芝麻智能`
- `source_type: company_official`
- `source_credit: 85`
- `verification_status: primary_source`
- `knowledge_eligible: true`
- `report_eligible: true`
- `source_platform: AgentReach(web)`
- `claims` with one `claim_text`
- `topics`

Use these six official evidence claims:

1. `972.html`

```yaml
title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证
url: https://www.blacksesame.com/zh/list_10/972.html
topics: [product_progress]
claims:
  - claim_text: 黑芝麻智能华山A2000U、A2000X芯片获得ISO 26262 ASIL-D功能安全认证。
    topics: [product_progress]
    claim_status: fact_candidate
```

2. `977.html`

```yaml
title: 黑芝麻智能与上实科技达成战略合作
url: https://www.blacksesame.com/zh/list_9/977.html
topics: [customer_orders]
claims:
  - claim_text: 黑芝麻智能与上实科技达成战略合作，双方将在智能驾驶与相关产业生态方面合作。
    topics: [customer_orders]
    claim_status: fact_candidate
```

3. `966.html`

```yaml
title: 黑芝麻智能加入理想星环OS开源生态
url: https://www.blacksesame.com/zh/list_9/966.html
topics: [customer_orders, product_progress]
claims:
  - claim_text: 黑芝麻智能加入理想星环OS开源生态，与理想汽车相关生态围绕智能驾驶开展合作。
    topics: [customer_orders, product_progress]
    claim_status: fact_candidate
```

4. `964.html`

```yaml
title: 黑芝麻智能与东风汽车深化平台级合作
url: https://www.blacksesame.com/zh/list_9/964.html
topics: [customer_orders]
claims:
  - claim_text: 黑芝麻智能与东风汽车推进平台级合作，合作方向涉及智能驾驶芯片和车端方案。
    topics: [customer_orders]
    claim_status: fact_candidate
```

5. `961.html`

```yaml
title: 黑芝麻智能与如祺出行达成战略合作
url: https://www.blacksesame.com/zh/list_9/961.html
topics: [customer_orders]
claims:
  - claim_text: 黑芝麻智能与如祺出行达成战略合作，合作围绕自动驾驶和出行场景落地。
    topics: [customer_orders]
    claim_status: fact_candidate
```

6. `912.html`

```yaml
title: 黑芝麻智能华山A1000获中国芯奖
url: https://www.blacksesame.com/zh/list_10/912.html
topics: [product_progress]
claims:
  - claim_text: 黑芝麻智能华山A1000芯片获得中国芯相关奖项。
    topics: [product_progress]
    claim_status: fact_candidate
```

---

## Commands To Run

First confirm focused tests still pass:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Then create and run a temporary validation script under `/tmp`, for example:

```bash
python3 /tmp/claim_verification_phase4b_validation/run_validation.py
```

The script should:

1. Create the temp knowledge tree.
2. Copy legacy notes from real `knowledge/10-Stocks/黑芝麻智能/*.md` into temp.
3. Write the six temporary official evidence notes into temp.
4. Import `build_claim_verification_plan` and `claim_verification_plan_to_dict` from `scripts/utils/claim_verification.py`.
5. Run:

```python
plan = build_claim_verification_plan("黑芝麻智能", temp_knowledge_root, dry_run=True)
plan_dict = claim_verification_plan_to_dict(plan)
```

6. Save the plain dict output to:

```text
/tmp/claim_verification_phase4b_validation/claim_verification_plan.json
```

7. Print a concise summary:

- high-credit claim count
- low-credit claim count
- skipped file count and reasons
- verification action counts
- top 10 verification rows: claim text, action, confidence, verified_by count, reasons

Do not leave any temporary script inside the repo.

---

## Review Questions

Answer these in the notes file:

1. Did the module skip `MOC.md` correctly?
2. How many high-credit official claims were loaded?
3. How many low-credit Xueqiu/Zhihu social claims were loaded?
4. What are the action counts for `verified`, `supported`, `needs_review`, `unverified`, `conflicted`?
5. Are any social claims incorrectly treated as high-credit or used to verify other claims?
6. Are official evidence matches too broad because of generic terms like `芯片`, `合作`, `公告`?
7. Are useful social claims failing to match because the legacy claim stubs are too coarse?
8. Does the current output look useful enough for Phase 5 KnowledgeSynthesizer integration, or do we need LLM claim extraction first?
9. Does any evidence note or social note write to real `knowledge/10-Stocks/**`?
10. What exact next change do you recommend?

---

## Expected Interpretation

Likely acceptable outcomes:

- Official evidence notes load as high-credit.
- Legacy Xueqiu/Zhihu notes load as low-credit.
- Some coarse social stubs remain `unverified`, because Phase 4 does not use LLM claim extraction.
- Some specific claims mentioning `A2000U`, `ASIL-D`, `理想`, `东风`, `如祺`, or `A1000` may become `verified` or `needs_review`.

Potential issue to watch:

- If almost everything is `unverified`, the next phase should probably add deterministic/LLM claim extraction for legacy social notes before KnowledgeSynthesizer integration.
- If too many vague claims become `verified`, matching is too loose and needs calibration before writeback.

---

## Notes File To Write

Create:

```text
docs/agent_workflow/2026-06-13-claim-verification-phase4b-runtime-validation-claude-notes.md
```

Include:

- commands run
- temp paths used
- test result
- verification plan summary
- action counts
- 5-10 representative rows
- answers to the review questions
- confirmation that no real `knowledge/10-Stocks/**` files were written
- confirmation that no source code was modified
- blockers or limitations

---

## Final Response Format

Reply with:

```text
Phase 4B runtime validation complete.

Tests:
- ...

Temp output:
- /tmp/claim_verification_phase4b_validation/claim_verification_plan.json

Summary:
- high_credit_claims: ...
- low_credit_claims: ...
- actions: ...

Key findings:
- ...

Notes:
- docs/agent_workflow/2026-06-13-claim-verification-phase4b-runtime-validation-claude-notes.md

Blockers:
- None / ...
```
