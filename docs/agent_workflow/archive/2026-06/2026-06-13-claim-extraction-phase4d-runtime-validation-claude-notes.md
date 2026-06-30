:
# Claim Extraction Phase 4D — Runtime Validation Notes

**Date**: 2026-06-13  
**Scope**: Runtime validation of Phase 4D body claim extraction on real 三花智控 legacy notes, using a temporary knowledge base.

---

## Constraints Followed

- Did **not** modify source code.
- Did **not** modify real `knowledge/10-Stocks/**`.
- Did **not** run `xueqiu_monitor_v2.py`, `run_黑芝麻智能.py`, or any `run_*.py` entry.
- Did **not** call LLMs, network, browsers, or subprocesses.
- Temporary files written only to `/tmp/claim_extraction_phase4d_validation/**`.
- Allowed repo write: only this notes file.

---

## Commands Run

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

```bash
python3 -m pytest tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_evidence_note_skill.py -q
```

```bash
mkdir -p /tmp/claim_extraction_phase4d_validation/knowledge/10-Stocks/三花智控/evidence
python3 /tmp/claim_extraction_phase4d_validation/run_validation.py
```

---

## Test Results

### Focused Tests

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

**42 passed**

### Safety Suite

```bash
python3 -m pytest tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_evidence_note_skill.py -q
```

**92 passed**

No failures, no warnings.

---

## Selected Stock

- **Stock**: 三花智控
- **Reason**: Preferred by task; has real legacy social notes.
- **Legacy files copied**: 9 (including `MOC.md`)

---

## Temp Paths

- `/tmp/claim_extraction_phase4d_validation/knowledge/10-Stocks/三花智控/`
- `/tmp/claim_extraction_phase4d_validation/knowledge/10-Stocks/三花智控/evidence/`
- `/tmp/claim_extraction_phase4d_validation/claim_verification_plan.json`
- `/tmp/claim_extraction_phase4d_validation/summary.json`

---

## Verification Plan Summary

| Metric | Value |
|---|---|
| High-credit claims | 2 |
| Low-credit claims | 11 |
| `legacy_social_body_rule` | 10 |
| `legacy_social_stub` | 1 |
| Skipped files | 6 |
| `verified` | 4 |
| `supported` | 0 |
| `needs_review` | 0 |
| `unverified` | 7 |
| `conflicted` | 0 |

### Skipped Reasons

| Reason | Count |
|---|---|
| `unknown_source_type` | 4 (older 2026-05-26 notes without social frontmatter) |
| `technical_note_skipped` | 1 (`20260612-技术指标.md`) |
| `moc_index` | 1 (`MOC.md`) |

---

## 10 Representative Extracted Claims

1. `[unverified]` `三花智控公告线索：三花智控:第八届董事会第十七次临时会议决议公告`
2. `[unverified]` `三花智控公告线索：三花智控:关于召开2025年度股东会的通知`
3. `[unverified]` `三花智控公告线索：三花智控:关于独立董事任期即将届满离任暨增补独立董事、非执行董事的公告`
4. `[verified, confidence=82]` `三花智控研报线索：2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发` — reason: `specific terms: 机器人`
5. `[verified, confidence=82]` `三花智控研报线索：2025年净利润较快增长，拓展机器人、服务器液冷等新领域` — reason: `specific terms: 机器人`
6. `[verified, confidence=84]` `三花智控研报线索：三花智控：2025Q4毛利率显著提升，积极布局机器人、储能等新兴业务` — reasons: `specific terms: 机器人`, `generic terms: 业务, 布局`
7. `[unverified]` `三花智控研报线索：业绩符合预期，盈利能力持续提升`
8. `[verified, confidence=82]` `三花智控研报线索：2025年年报点评：汽零&家电提质增效稳步增长，仿生机器人等新兴产业蓄势待发` — reason: `specific terms: 机器人`
9. `[unverified]` `深度分析：该社区笔记包含待验证观点，需用高信用来源核查。` (stub)
10. `[unverified]` `三花智控公告线索：三花智控:独立董事候选人声明与承诺(邵双全)`

---

## Design Requirements Verified

### `confirmed_facts` Prefix Is Neutral

The runtime validation did not exercise `confirmed_facts` extraction (the 三花智控 notes had empty `confirmed_facts`), but focused tests confirm the prefix is `{stock}疑似事实线索：` and never contains `确认事实`.

### Technical Notes Were Skipped

`20260612-技术指标.md` was skipped with `technical_note_skipped` and produced no claims/stubs.

### Older Notes Without Social Frontmatter Were Skipped

Four 2026-05-26 notes were skipped with `unknown_source_type` because they lack `source_type=social_discussion` / `verification_status=market_opinion`.

### No Social Content Elevated To Fact

All body-extracted claims have `source_credit=35`, `verification_status=market_opinion`, `claim_status=unverified_claim`, and `extraction_method=legacy_social_body_rule`.

### Body-Extracted Claims Can Be Verified By Evidence

Four report-derived claims mentioning `机器人`/`服务器液冷`/`储能` were matched by the temporary official evidence about robotics/thermal-management and marked `verified`.

---

## Comparison With Phase 4C

| Metric | Phase 4C (before extraction) | Phase 4D (after extraction) |
|---|---|---|
| Low-credit claims | 4 | 11 |
| `legacy_social_body_rule` | 0 | 10 |
| `legacy_social_stub` | 4 | 1 |
| `verified` | 0 | 4 |
| `unverified` | 4 (100%) | 7 (64%) |

The 100% `unverified` blocker is resolved.

---

## Confirmations

- No source code was modified during runtime validation.
- No real `knowledge/10-Stocks/**` files were written.
- No pipeline wiring was added.
- No LLM/network/browser/subprocess was used.
- `xueqiu_monitor_v2.py` and `run_*.py` entries were not run.

---

## Recommendation for Next Phase

Phase 4D body extraction is sufficient to make verification meaningful for product/customer/earnings-related social notes. Recommended next steps:

1. **Phase 5: KnowledgeSynthesizer integration (optional gated)** — pass the verification plan as context, not as facts; let synthesis explicitly distinguish `verified` vs `unverified` claims.
2. **Future enhancement (Phase 4E or later)** — add LLM-based claim extraction for notes with rich prose or non-structured bodies, but only after Phase 5 proves deterministic extraction is insufficient.
3. **Migration of older notes** — explicitly retag 2026-05-26 notes with `source_type=social_discussion` / `verification_status=market_opinion` if they should be included.

No blocker for Phase 5 from Phase 4D results.

---

## Artifacts

- `/tmp/claim_extraction_phase4d_validation/claim_verification_plan.json`
- `/tmp/claim_extraction_phase4d_validation/summary.json`
