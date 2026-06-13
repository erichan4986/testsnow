# Claim Extraction Phase 4D Claude Review Notes

**Date**: 2026-06-13  
**Design file reviewed**: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-design.md`  
**Scope**: Add deterministic body claim extraction to legacy social notes for Phase 4 verification.

---

## Status

**Ready with changes.**

The design is structurally sound and addresses the Phase 4C blocker (100% `unverified` due to coarse stubs). However, several safety and clarity issues must be tightened before implementation, especially around technical notes, older untagged notes, and the risk of accidentally treating `confirmed_facts` body content as verified.

---

## Findings

### High

- None.

### Medium

1. **`confirmed_facts` extraction risks semantic confusion.**
   - The design extracts from `confirmed_facts` as `unverified_claim`, which is correct from a source-credit perspective (the note itself is still `social_discussion` / `market_opinion`).
   - However, the field name strongly suggests the content is already confirmed. Future maintainers or downstream consumers may misread extracted `confirmed_facts` bullets as factual because the label is preserved in the source.
   - **Required clarification**: when extracting from `confirmed_facts`, the generated claim text should **not** include the word "确认事实" or "confirmed". Prefix with neutral field labels like `三花智控疑似事实线索：` to keep the social/notebook context visible.

2. **Technical notes should be skipped entirely in Phase 4D.**
   - The technical note body is large, noisy, and mostly numeric (`close`, `rsi_14`, `_resonance`, etc.). The design suggests extracting at most 2 concise text states, but even that is risky: `weekly_trend: 震荡` or `_resonance.trend: 空头` are model-generated technical opinions, not verifiable claims.
   - More importantly, these technical claims do not overlap with the expected high-credit evidence topics (product progress, customer orders, earnings). They will almost always remain `unverified` and add noise.
   - **Recommendation**: skip `category=技术指标` / `data_source=mootdx+stockstats` notes entirely in Phase 4D. Add a `skipped_files` reason `technical_note_skipped`. Revisit technical extraction in a dedicated phase if needed.

3. **Older notes without social frontmatter should remain skipped.**
   - Older 三花智控 notes have `confidence: 确认事实` and lack `source_type=social_discussion`. The design wisely keeps the `source_type=social_discussion` or `verification_status=market_opinion` gating requirement.
   - However, the design also raises a migration question. **Recommendation**: do not add a compatibility rule for `data_source=FinancialAgent/Kimi` in Phase 4D. Untagged older notes should stay skipped with reason `unknown_source_type`. A future migration phase can retag them explicitly.

4. **Extraction should live inside `claim_verification.py`, not a new module.**
   - The extraction is tightly coupled to claim verification semantics: it produces `ClaimCandidate` objects with fixed low-credit metadata, and its only caller is `_extract_social_claims()`.
   - Keeping it inside `claim_verification.py` minimizes surface area and preserves the Phase 4 boundary (no new public module, no pipeline wiring).
   - **Recommendation**: keep `extract_legacy_social_claims_from_body()` as an internal helper in `claim_verification.py`. It can be made public only if tests need direct access, but it should not become a standalone pipeline-facing module.

5. **Per-file limits need a global cap enforcement.**
   - The design lists per-field limits (`max 5 reports`, `max 3 key_risks`, etc.) and a global `max 8 body-extracted claims`.
   - The global cap must be applied **after** per-field collection, not per-field, otherwise a note with 5 reports + 5 announcements + 3 risks would produce 13 claims before the global cap.
   - **Recommendation**: document that per-field limits are collection limits, and a final global `MAX_BODY_CLAIMS_PER_FILE = 8` truncation is applied deterministically (e.g., preserve order: reports, announcements, catalysts, risks, inferences, opinions, confirmed_facts).

6. **Topic inference fallback by category may over-classify.**
   - Defaulting `技术指标` to `market_sentiment` is acceptable only if technical notes are skipped. If technical notes were processed, this would misclassify pure technical states as sentiment.
   - `深度分析` defaulting to `market_sentiment` is conservative but may miss earnings/product claims. The keyword table should catch most real cases, so this is acceptable.

7. **`position_suggestion` extraction is too generous.**
   - The design says "optional, usually skip" and then lists `观望`, `暂无`, `*AI分析暂缺*` as skips. But values like `持有` from older notes will be extracted even though they are investment opinions, not verifiable claims.
   - **Recommendation**: skip `position_suggestion` entirely in Phase 4D. It produces action recommendations, not factual claims, and does not overlap with high-credit evidence.

### Low

1. **Empty nested bullets in older notes will create noise.**
   - The 20260526 deep analysis note has `inferences: 3 条` followed by three empty bullets. The design filters short bullets, but empty or whitespace-only bullets should be explicitly dropped.
   - **Recommendation**: add a rule to drop bullets that are empty, whitespace-only, or contain only "-" / "*" punctuation.

2. **Wikilink filtering should include the entire line, not just the link.**
   - The design filters `[[20260612-深度分析]]`. Some lines may contain both a wikilink and useful text (rare in these notes). A simple filter that drops lines starting with `[[` or containing only wikilinks is sufficient.

3. **The "manual_validation" evidence fixtures need clear disclaimers.**
   - The runtime revalidation section uses `source_platform: manual_validation` and `example.com` URLs. This is fine, but the implementation notes must record that these are validation fixtures, not real sourced evidence.

4. **No test explicitly verifies that extracted body claims cannot become `verified_by` for high-credit evidence.**
   - This is already enforced by trust direction, but a dedicated test would document the boundary.

---

## Required Changes Before Implementation

1. **Skip `position_suggestion` entirely.**
   - Remove it from the supported extraction fields list.

2. **Skip technical notes (`category=技术指标` or `data_source=mootdx+stockstats`).**
   - Add `technical_note_skipped` to `skipped_files`.

3. **Keep older untagged notes skipped.**
   - Do not relax the `source_type=social_discussion` / `verification_status=market_opinion` gating for `data_source=FinancialAgent/Kimi` or other legacy sources.

4. **Neutralize `confirmed_facts` claim text.**
   - Use prefix like `疑似事实线索：` instead of `确认事实`.

5. **Enforce global per-file cap after per-field collection.**
   - Define `MAX_BODY_CLAIMS_PER_FILE = 8` and truncate deterministically.

6. **Document extraction order and truncation rules.**
   - Reports → announcements → catalysts → key_risks → inferences → opinions → confirmed_facts.

7. **Add explicit empty/whitespace bullet filtering.**

8. **Update `test_social_body_confirmed_facts_ignored`.**
   - Replace with `test_social_body_confirmed_facts_extracted_as_unverified` asserting low-credit metadata and no high-credit elevation.

---

## Nice To Have

- Add a helper `_is_technical_note(meta) -> bool` for clarity.
- Add a test for `position_suggestion` skip.
- Add a test for empty nested bullets in older notes.
- Add a test verifying that body-extracted claims are never used to verify other claims.

---

## Boundary Compliance Check

| Boundary | Design compliant? | Notes |
|---|---|---|
| No LLM / network / browser / subprocess | ✓ | Deterministic bullet parsing only. |
| No real `knowledge/` writes | ✓ | Dry-run plan only. |
| No pipeline wiring | ✓ | Internal helper only. |
| No `KnowledgeSynthesizer` changes | ✓ | Not involved. |
| No scoring/renderer changes | ✓ | Not involved. |
| No entry script changes | ✓ | Not involved. |
| Social content never elevated to fact | ✓ with changes | Need neutral `confirmed_facts` text and explicit unverified metadata. |
| Technical notes handled safely | ⚠️ | Recommend skip, not extract. |
| Older untagged notes handled safely | ✓ | Remain skipped. |

---

## Open Questions Responses

1. **Is deterministic Markdown bullet extraction enough for Phase 4D, or should we design an LLM extractor now?**
   - Deterministic extraction is enough for Phase 4D. It directly addresses the Phase 4C blocker without introducing LLM cost/latency. LLM extraction can be Phase 4E or 5 if deterministic extraction still leaves too many claims unverified.

2. **Does extracting from `confirmed_facts` as `unverified_claim` preserve the safety boundary clearly enough?**
   - Yes, but only if the generated claim text avoids the word "confirmed" and the `claim_status` is always `unverified_claim`. The source metadata must remain `social_discussion` / `market_opinion`.

3. **Should technical notes be skipped entirely in Phase 4D?**
   - **Yes.** They are noisy, numeric, and not meaningfully verifiable against product/customer/earnings evidence. Skip them and record the reason.

4. **Are the per-file limits too high or too low?**
   - Reasonable, but the global cap must be enforced after per-field collection. If technical notes are skipped, the 8-claim cap is unlikely to be hit by the current corpus.

5. **Should older notes without social frontmatter remain skipped?**
   - **Yes.** Do not add implicit migration rules. Retag them explicitly in a future migration phase.

6. **Is modifying `claim_verification.py` still the right boundary, or should extraction move into a separate module?**
   - Keep it in `claim_verification.py`. The extraction is an internal implementation detail of social claim extraction. A separate module would create an unnecessary public surface.

7. **What tests are missing to prevent social body content from becoming high-credit facts?**
   - A test that body-extracted claims have `source_credit=35`, `claim_status=unverified_claim`, and never appear in `high_credit_claims`.
   - A test that `confirmed_facts` body entries are extracted with neutral prefixes and low-credit metadata.

---

## Round 2 Review

### Status

**Ready to implement.**

All Round 1 required changes have been incorporated into the design. The revised Phase 4D design is safe, bounded, and sufficiently specified for implementation.

---

### Remaining Findings

#### High

- None.

#### Medium

- None.

#### Low

- None.

---

### Boundary Compliance Re-Check

| Boundary | Design compliant? | Notes |
|---|---|---|
| No LLM / network / browser / subprocess | ✓ | Deterministic Markdown bullet parsing only. |
| No real `knowledge/` writes | ✓ | Dry-run verification plan only. |
| No pipeline wiring | ✓ | Internal helper inside `claim_verification.py`. |
| No `KnowledgeSynthesizer` changes | ✓ | Not involved. |
| No scoring / renderer / report template changes | ✓ | Not involved. |
| No entry script changes | ✓ | Not involved. |
| `confirmed_facts` remains low-credit and neutral | ✓ | Prefix `{stock}疑似事实线索：`, `claim_status=unverified_claim`. |
| Technical notes skipped | ✓ | `category=技术指标` or `data_source=mootdx+stockstats` → `technical_note_skipped`. |
| Older untagged notes skipped | ✓ | Require explicit `source_type=social_discussion` or `verification_status=market_opinion`. |
| Global cap + fixed priority | ✓ | Max 8 after priority: reports → announcements → catalysts → key_risks → inferences → opinions → confirmed_facts. |
| `position_suggestion` skipped | ✓ | Explicitly non-extractable. |
| Social content never elevated to fact | ✓ | Body-extracted claims capped at `source_credit=35`, `verification_status=market_opinion`. |

---

### Implementation Guardrails

1. **Keep extraction inside `scripts/utils/claim_verification.py`.**
   - Add `extract_legacy_social_claims_from_body()` as an internal helper (public only if tests need direct access).

2. **Never produce high/medium-credit candidates from social body extraction.**
   - Force `source_type="social_discussion"`, `verification_status="market_opinion"`, `claim_status="unverified_claim"`.
   - Cap `source_credit` at `35` even if frontmatter has a higher value.

3. **Skip technical notes before body extraction.**
   - Skip if `category == "技术指标"` or `data_source == "mootdx+stockstats"`.
   - Record `{"path": ..., "reason": "technical_note_skipped"}`.
   - Do not create fallback stubs for skipped technical notes.

4. **Keep older untagged notes skipped.**
   - Only process notes with `source_type=social_discussion` or `verification_status=market_opinion`.
   - Untagged older notes go to `skipped_files` with `reason="unknown_source_type"`.

5. **Use neutral field-specific prefixes.**
   - `reports` → `{stock}研报线索：`
   - `announcements` → `{stock}公告线索：`
   - `catalysts` → `{stock}催化线索：`
   - `key_risks` → `{stock}风险线索：`
   - `inferences` → `{stock}推断线索：`
   - `opinions` → `{stock}观点线索：`
   - `confirmed_facts` → `{stock}疑似事实线索：`
   - Never use “确认事实” or “confirmed”.

6. **Apply per-field collection limits, then global cap.**
   - Per-field limits: reports/announcements max 5; key_risks/catalysts/inferences/opinions/confirmed_facts max 3.
   - Global `MAX_BODY_CLAIMS_PER_FILE = 8` applied after concatenating fields in fixed priority order.

7. **Filter noisy bullets.**
   - Drop empty, whitespace-only, punctuation-only, pure counts like `5 条`, `*AI分析暂缺*`, and wikilink-only lines.
   - Drop bullets shorter than 6 Chinese/ASCII characters after cleanup.
   - Deduplicate within the same file.

8. **Skip `position_suggestion`, `report_sections` prose, `_resonance`, raw numeric indicators, H1 title, source marker, and `相关链接`.**

9. **Update existing test `test_social_body_confirmed_facts_ignored`.**
   - Replace it with a test asserting body extraction as low-credit unverified claims.

10. **Add safety tests.**
    - Body-extracted claims never enter `high_credit_claims`.
    - `confirmed_facts` uses `疑似事实线索` prefix.
    - Technical notes skipped with `technical_note_skipped`.
    - Older untagged notes skipped with `unknown_source_type`.
    - `position_suggestion` not extracted.
    - Global 8-claim cap enforced after field priority.

11. **Run focused and safety tests before declaring done.**
    - `python3 -m pytest tests/utils/test_claim_verification.py -q`
    - `python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py -q`

12. **After implementation, run Phase 4D runtime revalidation on 三花智控 using `/tmp`.**
    - Confirm `legacy_social_body_rule` count > 0.
    - Confirm `unverified` rate < 100% if temp evidence overlaps with extracted claims.
