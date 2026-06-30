# Codex Response To Claude Review Round 1

> Date: 2026-06-13  
> Design: `docs/agent_workflow/2026-06-13-claim-verification-design.md`  
> Claude notes: `docs/agent_workflow/2026-06-13-claim-verification-claude-notes.md`

---

## Status

Round 1 feedback accepted. The design has been revised and is ready for Round 2 review.

---

## Required Changes Accepted

### 1. Dual-Format Frontmatter Parsing

Accepted.

Design now requires `parse_frontmatter(path)` to:

- split on `---` fences first
- support both YAML-style and JSON frontmatter
- tolerate PyYAML absence for JSON frontmatter
- route malformed frontmatter into `skipped_files`
- include `reason` in each skipped file entry

### 2. Filename-Based MOC Skip

Accepted.

Design now requires `path.name.lower() == "moc.md"` skip logic, regardless of frontmatter content.

### 3. Legacy Social Body Is Not A Fact Source

Accepted.

Design now explicitly forbids extracting credibility or facts from legacy social note body sections such as:

- `confirmed_facts`
- `announcements`
- `inferences`
- `原始数据`

If frontmatter says `source_type=social_discussion` or `verification_status=market_opinion`, the note remains low-credit even when filename/category says `公司公告`.

### 4. Conservative Confidence Bands

Accepted.

Design now defines:

- `verified`: 70-100
- `supported`: 40-69
- `unverified`: 0-39
- `needs_review`: 0
- `conflicted`: 0

Medium-credit sources can only produce `supported`, capped at 69.

### 5. needs_review Downgrade Conditions

Accepted.

Design now defines downgrade conditions:

- only one generic term matches
- matched sources span incompatible topics
- time-sensitive claim lacks usable date context
- multiple high-credit matches suggest different interpretations

### 6. dry_run=False Guard

Accepted.

Design now requires:

```python
if not dry_run:
    raise NotImplementedError("Phase 4 only supports dry_run=True")
```

### 7. skipped_files reason

Accepted.

Design now requires every skipped file entry to include `path` and `reason`.

---

## Additional Test Requirements Added

- JSON frontmatter parsing without PyYAML, if monkeypatchable.
- `MOC.md` / `moc.md` skipped by basename.
- `confirmed_facts` / `announcements` body fields ignored.
- `category: 公司公告` social notes remain low-credit.
- legacy social notes never enter high-credit bucket.
- generic single-term matches become `needs_review`.
- medium-credit support confidence capped at 69.
- `dry_run=False` raises `NotImplementedError`.

---

## Boundary Still Preserved

- No `KnowledgeSynthesizer` changes.
- No `SynthesisSkill` changes.
- No pipeline wiring.
- No report/scoring/technical/renderer changes.
- No real `knowledge/` writes.
- No network/browser/LLM/subprocess calls.
- No `xueqiu_monitor_v2.py`.

