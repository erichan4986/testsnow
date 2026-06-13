:
# Claim Extraction Phase 4D — Implementation Notes

**Date**: 2026-06-13  
**Task**: Implement deterministic legacy social body claim extraction for Phase 4D.

---

## Files Changed

| File | Change Type | Reason |
|---|---|---|
| `scripts/utils/claim_verification.py` | Modified | Added `extract_legacy_social_claims_from_body()`, topic inference, technical-note skip, neutral `confirmed_facts` prefix, global cap, and wired extraction into `_extract_social_claims()`. |
| `tests/utils/test_claim_verification.py` | Modified | Added 20+ tests for body extraction; updated `confirmed_facts` test to assert low-credit extraction. |
| `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md` | Created | This file. |
| `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md` | Created | Runtime validation notes. |

---

## Helper Functions Added

- `extract_legacy_social_claims_from_body(stock_name, meta, body, source_file)` — public pure helper.
- `_clean_bullet_text(text)` — normalize Markdown bullet lines.
- `_is_useful_bullet(text)` — filter empty/noisy bullets.
- `_collect_field_bullets(body, field_name)` — collect child bullets under a top-level field header.
- `_build_body_claim_candidate(...)` — build a low-credit `ClaimCandidate` from a bullet.
- `_infer_topics(text, category)` — deterministic topic inference from keywords/category.
- `_is_technical_note(meta)` — identify `category=技术指标` or `data_source=mootdx+stockstats`.

---

## Key Behaviors

### Trust Metadata (Hard Boundaries)

Every body-extracted claim has:

- `source_type="social_discussion"`
- `verification_status="market_opinion"`
- `claim_status="unverified_claim"`
- `source_credit=min(meta_source_credit, 35)`
- `extraction_method="legacy_social_body_rule"`

Body extraction never creates high-credit or medium-credit candidates.

### Technical Notes Skipped

Notes with `category=技术指标` or `data_source=mootdx+stockstats` are skipped with `reason="technical_note_skipped"` and no fallback stub.

### Older Untagged Notes Skipped

Notes without `source_type=social_discussion` or `verification_status=market_opinion` are skipped with `reason="unknown_source_type"`.

### Supported Fields And Prefixes

| Field | Max | Prefix |
|---|---|---|
| `reports` | 5 | `{stock}研报线索：` |
| `announcements` | 5 | `{stock}公告线索：` |
| `catalysts` | 3 | `{stock}催化线索：` |
| `key_risks` | 3 | `{stock}风险线索：` |
| `inferences` | 3 | `{stock}推断线索：` |
| `opinions` | 3 | `{stock}观点线索：` |
| `confirmed_facts` | 3 | `{stock}疑似事实线索：` |

`position_suggestion`, `report_sections`, `_resonance`, raw numeric indicators, H1 title, source marker, and `相关链接` are not extracted.

### Limits

- Per-field limits applied during collection.
- Global `MAX_BODY_CLAIMS_PER_FILE = 8` applied after fixed field priority:
  `reports` → `announcements` → `catalysts` → `key_risks` → `inferences` → `opinions` → `confirmed_facts`.

### Topic Inference

Keywords map to `product_progress`, `customer_orders`, `earnings_business`, or `market_sentiment`. Fallback by category: `最新研报` → `earnings_business`; `公司公告` / `深度分析` → `market_sentiment`. Default is `market_sentiment`.

---

## Tests Added/Updated

New tests cover:

- `reports` / `announcements` bullet extraction
- social metadata preservation
- body-extracted claims never enter high-credit bucket
- `confirmed_facts` neutral prefix (`疑似事实线索`, no `确认事实`)
- empty counts without child bullets fall back to stub
- noisy bullet filtering (`*AI分析暂缺*`, wikilinks, pure counts, empty/whitespace bullets)
- global max 8 cap after field priority
- frontmatter claims precedence
- fallback stub when nothing extractable
- topic inference for robot/liquid-cooling/earnings/risk
- real-shaped 三花智控 latest-report fixture yields `仿生机器人`, `服务器液冷`, `净利润`
- body-extracted claims can be verified by evidence
- technical notes skipped (by category and by data_source)
- older untagged notes skipped
- `position_suggestion` not extracted
- social body claims never verify other social claims
- direct `extract_legacy_social_claims_from_body` API

Updated:

- `test_social_body_confirmed_facts_ignored` → `test_social_body_confirmed_facts_extracted_as_unverified`

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

## Runtime Validation

See `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md`.

Quick summary on 三花智控:

- High-credit claims: 2
- Low-credit claims: 11
  - `legacy_social_body_rule`: 10
  - `legacy_social_stub`: 1
- Skipped files: 6
  - `technical_note_skipped`: 1
  - `unknown_source_type`: 4
  - `moc_index`: 1
- Action counts: `verified`: 4, `unverified`: 7

The Phase 4C 100% `unverified` blocker is resolved: body-extracted claims about `机器人`, `服务器液冷`, `储能`, etc. are now matched by the temporary official evidence notes and marked `verified`.

---

## Deviations From Design

None.

Codex verification follow-up aligned `_MIN_CLAIM_TEXT_LENGTH` to 6 effective characters and updated synthetic test fixtures to use substantive phrases. This keeps the implementation consistent with the Phase 4D design rule that very short bullets should be treated as noise.

---

## Boundary Compliance

The following files were **not modified**:

- `scripts/utils/knowledge_synthesizer.py` ✓
- `scripts/utils/report_skills/synthesis_skills.py` ✓
- `scripts/utils/report_skills/__init__.py` ✓
- `scripts/utils/report_skills/evidence_note_skill.py` ✓
- `scripts/utils/evidence_note_writer.py` ✓
- `scripts/utils/source_credit.py` ✓
- `scripts/utils/source_adapter.py` ✓
- `scripts/utils/reporter/scoring_engine.py` ✓
- `scripts/run_黑芝麻智能.py` ✓
- `scripts/xueqiu_monitor_v2.py` ✓
- `config/stocks.json` ✓
- `reports/**` ✓
- real `knowledge/10-Stocks/**` ✓

No pipeline wiring, no LLM/network/browser/subprocess, no report entry runs.

---

## Notes

- The module remains dry-run only; `dry_run=False` still raises `NotImplementedError`.
- Technical notes are intentionally skipped; future phases can design technical claim extraction separately if needed.
- Older untagged notes remain skipped pending explicit migration/retagging.
