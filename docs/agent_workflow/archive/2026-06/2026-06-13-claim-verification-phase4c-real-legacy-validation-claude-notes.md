# Claim Verification Phase 4C Real Legacy Corpus Validation Notes

**Date**: 2026-06-13  
**Scope**: Runtime validation of `scripts/utils/claim_verification.py` against real legacy Xueqiu/Zhihu social notes for 三花智控. No source code modifications.

---

## Constraints Followed

- Did **not** modify `scripts/**`, `tests/**`, `config/**`, `reports/**`, or real `knowledge/10-Stocks/**`.
- Did **not** run `xueqiu_monitor_v2.py`, `run_黑芝麻智能.py`, or any `run_*.py` entry.
- Did **not** call LLMs, network, browsers, or subprocesses.
- Temporary files written only to `/tmp/claim_verification_phase4c_validation/**`.
- Allowed repo write: only this notes file.

---

## Commands Run

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

```bash
mkdir -p /tmp/claim_verification_phase4c_validation/knowledge/10-Stocks/三花智控/evidence
python3 /tmp/claim_verification_phase4c_validation/run_validation.py
```

---

## Test Result

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

**23 passed**

No failures, no warnings.

---

## Stock Selection

| Candidate | Legacy `.md` files (excl. MOC) |
|---|---|
| 三花智控 | 8 |
| 中简科技 | 6 |
| 乐鑫科技 | 12 |
| 圣邦股份 | 33 |
| 长春高新 | 8 |

**Selected stock: 三花智控** (preferred by task; has >= 3 legacy notes).

- Legacy files copied: 9 (including `MOC.md`)
- No real files were edited.

---

## Temp Paths Used

- `/tmp/claim_verification_phase4c_validation/knowledge/10-Stocks/三花智控/`
- `/tmp/claim_verification_phase4c_validation/knowledge/10-Stocks/三花智控/evidence/`
- `/tmp/claim_verification_phase4c_validation/claim_verification_plan.json`
- `/tmp/claim_verification_phase4c_validation/summary.json`

---

## Verification Plan Summary

| Metric | Value |
|---|---|
| High-credit claims | 2 |
| Low-credit claims | 4 |
| Explicit frontmatter claims | 0 |
| Coarse `legacy_social_stub` claims | 4 |
| Skipped files | 5 |
| `verified` | 0 (0%) |
| `supported` | 0 (0%) |
| `needs_review` | 0 (0%) |
| `unverified` | 4 (100%) |
| `conflicted` | 0 (0%) |

### Skipped Files

| Reason | Count |
|---|---|
| `moc_index` | 1 (MOC.md) |
| `unknown_source_type` | 4 (2026-05-26 notes without `source_type=social_discussion` / `verification_status=market_opinion`) |

Only the 2026-06-12 notes carried the new Phase 4 social frontmatter; the older 2026-05-26 notes did not.

---

## Representative Verification Rows

All four low-credit claims were `unverified`:

1. `20260612-公司公告.md`
   - Claim: `公司公告：该社区笔记包含待验证观点，需用高信用来源核查。`
   - Action: `unverified`
   - Confidence: `20`
   - Reasons: `no high or medium credit source with matching topic and terms`

2. `20260612-技术指标.md`
   - Claim: `技术指标：该社区笔记包含待验证观点，需用高信用来源核查。`
   - Action: `unverified`
   - Confidence: `20`
   - Reasons: same

3. `20260612-最新研报.md`
   - Claim: `最新研报：该社区笔记包含待验证观点，需用高信用来源核查。`
   - Action: `unverified`
   - Confidence: `20`
   - Reasons: same

4. `20260612-深度分析.md`
   - Claim: `深度分析：该社区笔记包含待验证观点，需用高信用来源核查。`
   - Action: `unverified`
   - Confidence: `20`
   - Reasons: same

---

## Analysis Questions Answered

1. **Did the module skip `MOC.md` correctly?**
   - Yes. `MOC.md` was recorded in `skipped_files` with reason `moc_index`.

2. **Did all real legacy notes remain low-credit?**
   - Yes. The four processed 2026-06-12 notes all became `social_discussion` / `market_opinion` low-credit claims.

3. **Did any social note verify another social note?**
   - No. Social notes never verify other claims; all four ended `unverified`.

4. **How many low-credit claims came from explicit frontmatter claims vs `legacy_social_stub`?**
   - Explicit frontmatter claims: 0
   - Coarse stubs: 4
   - All real legacy notes lack explicit `claims` frontmatter.

5. **What percentage of low-credit claims became each action?**
   - `verified`: 0%
   - `supported`: 0%
   - `needs_review`: 0%
   - `unverified`: 100%
   - `conflicted`: 0%

6. **Are `verified` results credible, or driven by generic terms?**
   - No `verified` results occurred, so this concern did not materialize.

7. **Are many useful claims stuck as `unverified` because stubs are too coarse?**
   - Yes. The coarse stub text only contains the category title (`公司公告`, `技术指标`, etc.) plus a generic suffix. It does not expose the substantive content from the note body, so it cannot match the high-credit evidence claims about thermal management or robotics.

8. **Are medium-credit evidence notes producing only `supported`, never `verified`?**
   - N/A — no matches at all. The medium-credit broker-research earnings note had no opportunity to produce `supported` because the social stubs lacked earnings-related specific terms.

9. **Does this suggest Phase 5 integration is ready, or do we need Phase 4D claim extraction?**
   - **This result strongly suggests we need Phase 4D claim extraction before Phase 5 integration.**
   - 100% `unverified` on a real legacy corpus means the verification plan provides almost no value to `KnowledgeSynthesizer`.
   - Coarse stubs are too shallow to match real evidence claims.

10. **What exact next change do you recommend?**
    - Implement Phase 4D: deterministic or lightweight LLM-based claim extraction from legacy social note bodies.
    - Extract specific claims (e.g., from `confirmed_facts`, `inferences`, `opinions`, body paragraphs) while preserving the low-credit source metadata.
    - Re-run this same validation after Phase 4D to confirm the `unverified` rate drops and `verified`/`supported` rates become meaningful.
    - Only then proceed to Phase 5 KnowledgeSynthesizer integration.

---

## Key Findings

- Phase 4 module behaves correctly on real legacy corpus:
  - `MOC.md` skipped.
  - Social notes stay low-credit.
  - Social notes never verify other notes.
  - No false `verified` from generic terms.
- The **coarse stub strategy is insufficient** for real legacy notes:
  - All four processable social notes became stubs.
  - Stubs carry only category labels, not substantive claims.
  - Zero matches against the high/medium-credit evidence notes.
- Older 2026-05-26 notes were skipped because they lack the new `source_type=social_discussion` / `verification_status=market_opinion` frontmatter.

---

## Blockers / Limitations

- **100% unverified rate on real corpus**: the main blocker for Phase 5 integration.
- **Coarse stubs lack content**: Phase 4 deliberately avoids LLM extraction, but this makes verification against real evidence nearly useless.
- **Older legacy notes not tagged as social**: four 2026-05-26 notes were skipped due to missing frontmatter tags.
- **Temporary evidence notes are fixtures**: the three temp evidence notes were hand-crafted for validation, not real sourced knowledge.

---

## Confirmations

- No source code was modified.
- No real `knowledge/10-Stocks/**` files were written.
- No pipeline wiring was added.
- No LLM/network/browser/subprocess was used.
- `xueqiu_monitor_v2.py` and `run_*.py` entries were not run.

---

## Artifacts

- `/tmp/claim_verification_phase4c_validation/claim_verification_plan.json`
- `/tmp/claim_verification_phase4c_validation/summary.json`
