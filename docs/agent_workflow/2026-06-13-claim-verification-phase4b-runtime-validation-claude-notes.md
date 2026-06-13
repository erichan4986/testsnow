# Claim Verification Phase 4B Runtime Validation Notes

**Date**: 2026-06-13  
**Scope**: Runtime validation of `scripts/utils/claim_verification.py` using a temporary knowledge base. No source code modifications.

---

## Constraints Followed

- Did **not** modify `scripts/**`, `tests/**`, `config/**`, `reports/**`, or real `knowledge/10-Stocks/**`.
- Did **not** run `xueqiu_monitor_v2.py` or `run_黑芝麻智能.py`.
- Did **not** call LLMs, network, browsers, or subprocesses.
- Temporary files written only to `/tmp/claim_verification_phase4b_validation/**`.
- Allowed repo write: only this notes file.

---

## Commands Run

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

```bash
mkdir -p /tmp/claim_verification_phase4b_validation/knowledge/10-Stocks/黑芝麻智能/evidence
python3 /tmp/claim_verification_phase4b_validation/run_validation.py
```

---

## Test Result

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

**23 passed**

No failures, no warnings.

---

## Temp Paths Used

- `/tmp/claim_verification_phase4b_validation/knowledge/10-Stocks/黑芝麻智能/`
- `/tmp/claim_verification_phase4b_validation/knowledge/10-Stocks/黑芝麻智能/evidence/`
- `/tmp/claim_verification_phase4b_validation/claim_verification_plan.json`
- `/tmp/claim_verification_phase4b_validation/summary.json`

---

## Validation Setup

- Real `knowledge/10-Stocks/黑芝麻智能/*.md` had **no legacy social notes** (only `posts/` directory exists).
- Validation script therefore created **two fallback low-credit social notes** under the temp tree so the module could still be smoke-tested.
- Six temporary high-credit official evidence notes were created under temp `evidence/`.

---

## Verification Plan Summary

| Metric | Value |
|---|---|
| High-credit claims | 6 |
| Low-credit claims | 2 |
| Skipped files | 0 |
| `verified` | 2 |
| `supported` | 0 |
| `needs_review` | 0 |
| `unverified` | 0 |
| `conflicted` | 0 |

---

## Representative Verification Rows

1. **A2000U ASIL-D certification**
   - Claim: `黑芝麻智能A2000U获ASIL-D认证：该社区笔记包含待验证观点，需用高信用来源核查。`
   - Action: `verified`
   - Confidence: `82`
   - Verified by: 1 high-credit claim
   - Reasons: `specific terms: a2000u, asil-d, 认证`

2. **理想汽车合作预期**
   - Claim: `黑芝麻智能与理想汽车合作预期：该社区笔记包含待验证观点，需用高信用来源核查。`
   - Action: `verified`
   - Confidence: `84`
   - Verified by: 1 high-credit claim
   - Reasons: `specific terms: 理想`, `generic terms: 合作`

---

## Review Questions Answered

1. **Did the module skip `MOC.md` correctly?**
   - No `MOC.md` was present in the temp validation tree. The focused tests confirm `MOC.md` / `moc.md` are skipped by filename. ✓

2. **How many high-credit official claims were loaded?**
   - 6 (one per temporary official evidence note).

3. **How many low-credit Xueqiu/Zhihu social claims were loaded?**
   - 2 (fallback social stubs, because real legacy social notes do not exist for 黑芝麻智能 yet).

4. **Action counts?**
   - `verified`: 2
   - `supported`: 0
   - `needs_review`: 0
   - `unverified`: 0
   - `conflicted`: 0

5. **Are any social claims incorrectly treated as high-credit or used to verify other claims?**
   - No. Both low-credit claims stayed in the low bucket and were verified **by** high-credit evidence, not the reverse.

6. **Are official evidence matches too broad because of generic terms?**
   - Not in this run. The two verified matches were driven by specific terms (`a2000u`, `asil-d`, `理想`). The `合作` generic term appeared only as an additional signal, not the sole basis.

7. **Are useful social claims failing to match because stubs are too coarse?**
   - Not observed here, but the fallback stubs were intentionally constructed to match the six official evidence notes. With real legacy notes, coarse stubs (title + "该社区笔记包含待验证观点…") may miss nuanced claims because Phase 4 does no LLM claim extraction.

8. **Does the output look useful enough for Phase 5 KnowledgeSynthesizer integration?**
   - The plan shape is useful: it clearly separates high/low claims and records `verified_by` with reasons.
   - However, with only 2 coarse stubs the validation is too shallow to judge real-world utility. If most real legacy stubs remain `unverified`, Phase 5 should add deterministic/LLM claim extraction before integration.

9. **Did any evidence or social note write to real `knowledge/10-Stocks/**`?**
   - No. All notes were written under `/tmp/claim_verification_phase4b_validation/knowledge/`.

10. **What exact next change do you recommend?**
    - Re-run this validation once real legacy social notes exist for 黑芝麻智能 (or use a stock that already has them, e.g., 三花智控).
    - If real social stubs are mostly `unverified`, prioritize adding deterministic/LLM claim extraction for legacy social notes before Phase 5 integration.
    - If matches become too broad with real data, tighten the generic-term guardrails.

---

## Blockers / Limitations

- **Real legacy social notes missing for 黑芝麻智能**: only fallback stubs were available, so the validation is a smoke test rather than a realistic corpus test.
- **Shallow claim extraction**: Phase 4 intentionally uses coarse stubs; expect many `unverified` results on a real corpus until claim extraction improves.
- **No `MOC.md` present in temp tree**: the MOC skip path was not exercised at runtime, only in unit tests.

---

## Confirmations

- No source code was modified.
- No real `knowledge/10-Stocks/**` files were written.
- No pipeline wiring was added.
- No LLM/network/browser/subprocess was used.
- `xueqiu_monitor_v2.py` and `run_黑芝麻智能.py` were not run.

---

## Artifacts

- `/tmp/claim_verification_phase4b_validation/claim_verification_plan.json`
- `/tmp/claim_verification_phase4b_validation/summary.json`
