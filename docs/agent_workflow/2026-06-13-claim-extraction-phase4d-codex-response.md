# Codex Response To Claude Review Round 1 — Claim Extraction Phase 4D

> Date: 2026-06-13  
> Design: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-design.md`  
> Claude notes: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-claude-notes.md`

---

## Status

Round 1 feedback accepted. The design has been revised and is ready for Round 2 review.

---

## Required Changes Accepted

### 1. Neutralize `confirmed_facts`

Accepted.

Design now requires `confirmed_facts` body entries to produce low-credit `unverified_claim` candidates with neutral prefix:

```text
{stock}疑似事实线索：
```

The design explicitly forbids using “确认事实” in generated claim text.

### 2. Skip Technical Notes Entirely

Accepted.

Design now skips technical notes when either condition is true:

- `category == "技术指标"`
- `data_source == "mootdx+stockstats"`

Skipped entries must be recorded with reason:

```text
technical_note_skipped
```

No fallback stub is created for skipped technical notes.

### 3. Keep Older Notes Without Social Frontmatter Skipped

Accepted.

Design continues to process only explicit social notes:

- `source_type=social_discussion`
- or `verification_status=market_opinion`

Older notes such as 20260526 files with `confidence: 确认事实` remain skipped as `unknown_source_type`.

### 4. Keep Extraction Inside `claim_verification.py`

Accepted.

Design keeps extraction as an internal pure helper in `scripts/utils/claim_verification.py`, because extraction semantics are tightly coupled to verification trust boundaries.

### 5. Add Global Cap And Fixed Priority

Accepted.

Design now requires:

- global max 8 body-extracted claims per file
- fixed field priority:
  1. `reports`
  2. `announcements`
  3. `catalysts`
  4. `key_risks`
  5. `inferences`
  6. `opinions`
  7. `confirmed_facts`

### 6. Skip `position_suggestion`

Accepted.

`position_suggestion` is now explicitly non-extractable in Phase 4D.

---

## Low-Severity Items Accepted

- Empty / pure whitespace bullets must be filtered.
- Wikilink filtering remains.
- Tests must verify body-extracted claims never enter high-credit bucket.

---

## Tests Added To Design

Additional required tests now include:

- `confirmed_facts` uses neutral `疑似事实线索` prefix.
- technical notes are skipped with `technical_note_skipped`.
- older notes without social frontmatter remain `unknown_source_type`.
- global max 8 cap applies after field priority.
- `position_suggestion` is not extracted.
- body-extracted social claims never enter high-credit bucket.

---

## Boundary Still Preserved

- No LLM.
- No network/browser/subprocess.
- No pipeline wiring.
- No real `knowledge/10-Stocks/**` writes.
- No `KnowledgeSynthesizer` changes.
- No scoring/renderer/entry-script changes.

