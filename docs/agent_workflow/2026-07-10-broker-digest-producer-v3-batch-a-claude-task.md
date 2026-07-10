# Broker Digest Producer V3 Batch A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use test-driven development and
> execute this plan task-by-task. Mark each checkbox as it is completed.

**Goal:** Replace legacy broker excerpt boundary/scoring/diagnostic logic with
boundary-safe excerpts, explainable score parts, severe OCR rejection, and a
versioned note refresh contract.

**Architecture:** Keep heading extraction and the existing four card families.
Batch A changes candidate integrity only; semantic claim/evidence pairing remains
Batch B. New logic replaces `_condense_excerpt`, `_quality_score`,
`_section_candidate_score`, and `_diagnostic_entry` rather than creating a
parallel producer path.

**Tech stack:** Python standard library, pytest, existing note writer and report
source-boundary gates.

---

## Scope

**Runtime files allowed:**

- `scripts/utils/broker_research_digest.py`
- `scripts/utils/broker_research_digest_note_writer.py`

**Test files allowed:**

- `tests/utils/test_broker_research_digest.py`
- `tests/utils/test_broker_research_digest_note_writer.py`
- `tests/utils/test_broker_research_digest_synthesis_items.py` only if the new
  frontmatter field changes reader behavior

**Notes output:**

- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-batch-a-claude-notes.md`

**Forbidden:** renderer, synthesis/profile routing, scoring, target price, risk,
technical analysis, recommendation, collection, PDF download, LLM prompt,
reports, data, and knowledge files.

**Runtime budget:** Calculate `git diff --numstat` for the two runtime files.
Target net delta is at most +80 lines; hard stop is +100. Tests and notes do not
count toward this runtime limit.

## Task 1: Version Cards And Note Freshness

**Files:**

- Modify: `scripts/utils/broker_research_digest.py:20-23,482-526`
- Modify: `scripts/utils/broker_research_digest_note_writer.py:13-30,110-203`
- Test: `tests/utils/test_broker_research_digest.py`
- Test: `tests/utils/test_broker_research_digest_note_writer.py`

- [ ] **Step 1: Add failing card-version test**

Add a focused test that builds a normal core-view card and asserts:

```python
assert cards[0]["selection_version"] == "broker_digest_v3"
```

- [ ] **Step 2: Add failing note freshness tests**

Add one test that writes an otherwise current note without
`selection_version`, reruns the writer, and asserts the file is rewritten with:

```text
selection_version: broker_digest_v3
```

Add or update one test proving a note containing all current markers, including
`selection_version: broker_digest_v3`, remains in `skipped_existing`.

- [ ] **Step 3: Run the new tests and confirm RED**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_broker_research_digest.py \
  tests/utils/test_broker_research_digest_note_writer.py \
  -q -p no:cacheprovider
```

Expected: failures specifically caused by the missing card/frontmatter version
and stale-note check.

- [ ] **Step 4: Implement one version owner**

In `broker_research_digest.py`, add:

```python
SELECTION_VERSION = "broker_digest_v3"
```

and include it in `_build_card()` as `selection_version`.

Import that constant into the note writer. `_render_note()` must write both:

```text
excerpt_cleaner_version: broker_ocr_v2
selection_version: broker_digest_v3
```

Update `_has_current_diagnostics_note_shape()` to require the current selection
version. Preserve the existing schema, cleaner, reason, and diagnostics checks.
Do not classify an otherwise current note missing only this field as an unrelated
file; the normal writer path must refresh it in place.

- [ ] **Step 5: Run Task 1 tests and confirm GREEN**

Expected: all digest and note-writer tests pass.

## Task 2: Explainable Scoring And Severe-Damage Rejection

**Files:**

- Modify: `scripts/utils/broker_research_digest.py:635-706,912-922`
- Modify: `scripts/utils/broker_research_digest_note_writer.py:159-175`
- Test: `tests/utils/test_broker_research_digest.py`
- Test: `tests/utils/test_broker_research_digest_note_writer.py`

- [ ] **Step 1: Add failing score-parts test**

Extend the repeated-heading diagnostics fixture so every diagnostic entry has:

```python
expected_parts = {
    "signal",
    "evidence",
    "completeness",
    "coherence",
    "ocr_penalty",
    "noise_penalty",
}
assert expected_parts == set(entry["score_parts"])
assert entry["score"] == (
    entry["score_parts"]["signal"]
    + entry["score_parts"]["evidence"]
    + entry["score_parts"]["completeness"]
    + entry["score_parts"]["coherence"]
    - entry["score_parts"]["ocr_penalty"]
    - entry["score_parts"]["noise_penalty"]
)
```

- [ ] **Step 2: Add failing severe-damage rejection test**

Use two occurrences of the same heading. The damaged occurrence should contain
multiple generic defects such as a Chinese-character gap, dangling decimal, and
broken year/unit sequence while also carrying many keywords. Assert:

```python
assert clean_claim in selected_card["source_excerpt"]
assert any(
    entry["status"] == "rejected"
    and entry["reason"] == "rejected_ocr_damage"
    for entry in selected_card["selection_diagnostics"]
)
```

Also add a negative-control test with valid values such as `2026年`、`57.3亿元`、
`262.3%` and `1.6T光模块`; it must not receive severe-damage rejection.

- [ ] **Step 3: Run the new tests and confirm RED**

Expected: missing `score_parts`, no rejected status, or damaged candidate still
eligible.

- [ ] **Step 4: Replace the legacy score functions**

Replace `_quality_score` and `_section_candidate_score` with one score-parts
owner and one total function. The implementation must remain generic:

```python
SCORE_PART_KEYS = (
    "signal", "evidence", "completeness", "coherence",
    "ocr_penalty", "noise_penalty",
)
_EXCERPT_TERMINATORS = "。；;！？!?"

def _candidate_score_parts(text: str) -> Dict[str, int]:
    digit_count = min(sum(ch.isdigit() for ch in text), 20)
    specific_count = sum(term in text for term in _SPECIFIC_TERMS)
    complete_sentences = len(re.findall(r"[。；;！？!?]", text))
    directional = any(
        term in text
        for term in ("预计", "认为", "维持", "受益", "推动", "带动", "提升", "改善", "风险", "不及预期")
    )
    evidence_signal = bool(re.search(r"\d+(?:\.\d+)?\s*(?:亿元|%|pct|倍|G|T)", text)) or any(
        term in text for term in ("客户", "订单", "产能", "产品", "毛利率", "净利润")
    )
    gap_count = len(re.findall(r"[\u4e00-\u9fff]\s+[\u4e00-\u9fff]", text))
    dangling_decimal_count = len(re.findall(r"\d+\.(?=\s|[，,；;。]|$)", text))
    broken_year_count = len(re.findall(r"(?:20\s+20\d{2}|20\d{2}\s+年)", text))
    noise_hits = sum(pattern in text for pattern in _GENERIC_NOISE_PATTERNS)
    table_noise = _looks_like_financial_table_fragment(text) or _looks_like_rating_table_fragment(text)
    return {
        "signal": min(specific_count * 3, 60),
        "evidence": digit_count + (8 if evidence_signal else 0),
        "completeness": min(complete_sentences * 4, 12),
        "coherence": 8 if directional and evidence_signal else 0,
        "ocr_penalty": gap_count * 8 + dangling_decimal_count * 24 + broken_year_count * 24,
        "noise_penalty": noise_hits * 12 + (80 if table_noise else 0),
    }

def _candidate_total(parts: Dict[str, int]) -> int:
    return sum(parts[key] for key in SCORE_PART_KEYS[:4]) - sum(
        parts[key] for key in SCORE_PART_KEYS[4:]
    )

def _has_severe_ocr_damage(parts: Dict[str, int]) -> bool:
    return parts["ocr_penalty"] >= 24

def _quality_score(text: str) -> int:
    return _candidate_total(_candidate_score_parts(text))

def _section_candidate_score(text: str) -> int:
    parts = _candidate_score_parts(text)
    return _candidate_total(parts)
```

The detector may recognize generic defect shapes, but must not guess repaired
words. Severe damage must be a deterministic threshold over generic defect
counts. Keep damaged candidates in diagnostics with their normal total/parts,
but exclude them from `_select_section_candidates()` eligibility with:

```python
eligible = [
    candidate for candidate in candidates
    if not _has_severe_ocr_damage(_candidate_score_parts(candidate[3]))
]
ordered = sorted(eligible, key=lambda item: (-item[0], item[1]))
```

This is the only Batch A admission change to that function; Batch B will replace
its semantic selection.

Replace `_diagnostic_entry()` so it stores the six score parts. Skipped and
selected entries must both expose the same stable shape. The note writer should
render the parts compactly in deterministic key order. Pass the candidate text
to `_diagnostic_entry()` from section, generic-driver, and fallback call sites:

```python
def _diagnostic_entry(
    *, heading: str, score: int, status: str, reason: str, text: str
) -> Dict[str, Any]:
    return {
        "heading": heading,
        "score": int(score),
        "score_parts": _candidate_score_parts(text),
        "status": status,
        "reason": reason,
    }
```

`_section_selection_diagnostics()` must assign
`status="rejected", reason="rejected_ocr_damage"` before checking selected or
near-duplicate status when `_has_severe_ocr_damage(parts)` is true.

The note writer serializes parts without a second key list:

```python
parts = entry.get("score_parts") or {}
parts_text = ",".join(f"{key}={parts.get(key, 0)}" for key in SCORE_PART_KEYS)
```

Import `SCORE_PART_KEYS` from the producer together with `SELECTION_VERSION`;
do not duplicate the order in the writer.

- [ ] **Step 5: Run Task 2 tests and confirm GREEN**

Expected: score-part arithmetic, rejected diagnostics, normal-number negative
control, and existing candidate-ranking tests all pass.

## Task 3: Boundary-Safe Excerpts

**Files:**

- Modify: `scripts/utils/broker_research_digest.py:709-762,810-819`
- Test: `tests/utils/test_broker_research_digest.py`

- [ ] **Step 1: Add failing retreat-to-boundary test**

Build a long heading section where character 900 falls inside a sentence and a
complete sentence ends before the limit. Assert the returned excerpt:

```python
assert len(excerpt) <= 900
assert excerpt.endswith(("。", "；", "！", "？"))
assert incomplete_tail not in excerpt
```

- [ ] **Step 2: Add failing nearby-extension test**

Build a section where the next terminator is shortly after 900 and the previous
terminator is far earlier. Assert the excerpt extends only to that nearby
terminator and remains within the documented bounded extension.

- [ ] **Step 3: Add source-substring and no-boundary tests**

Assert every returned complete sentence occurs verbatim in the cleaned source
and in original order. For a long string with no usable sentence boundary,
assert the candidate is rejected/empty rather than sliced mid-clause.

- [ ] **Step 4: Run the new tests and confirm RED**

Expected: existing `[:900]` behavior cuts a sentence or number.

- [ ] **Step 5: Replace `_condense_excerpt` and final slicing**

Implement one boundary helper with a preferred limit of 900 and a small fixed
extension window. Its policy is:

1. Return short text unchanged.
2. If the next terminator is inside the extension window, extend to it.
3. Otherwise retreat to the final terminator at or before the limit.
4. If neither exists, return an empty string rather than a partial long clause.

Use this exact single-owner shape (minor naming/style adjustments are allowed,
policy changes are not):

```python
def _bounded_complete_excerpt(text: str, limit: int = 900, extension: int = 80) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    hard_end = min(len(text), limit + extension)
    next_positions = [
        pos for mark in _EXCERPT_TERMINATORS
        if (pos := text.find(mark, limit, hard_end + 1)) >= 0
    ]
    if next_positions:
        return text[: min(next_positions) + 1].strip()
    previous = max(text.rfind(mark, 0, limit + 1) for mark in _EXCERPT_TERMINATORS)
    return text[: previous + 1].strip() if previous >= 0 else ""
```

Use this helper from `_clean_excerpt`, the replacement `_condense_excerpt`, and
the current fallback finalization. Do not create a second boundary algorithm.
Do not change Batch B's family admission or fallback unit selection yet.

- [ ] **Step 6: Run Task 3 tests and confirm GREEN**

Expected: new boundary tests and all existing digest tests pass.

## Task 4: Batch A Verification And Notes

- [ ] **Step 1: Run focused producer tests**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_broker_research_digest.py \
  tests/utils/test_broker_research_digest_note_writer.py \
  tests/utils/test_broker_research_digest_synthesis_items.py \
  -q -p no:cacheprovider
```

- [ ] **Step 2: Run downstream contract tests**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_report_quality.py \
  -q -p no:cacheprovider
```

- [ ] **Step 3: Run repository gates**

```text
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 4: Enforce runtime budget**

Report additions/deletions separately for:

```text
scripts/utils/broker_research_digest.py
scripts/utils/broker_research_digest_note_writer.py
```

Stop without committing if combined runtime net growth exceeds +100 lines.

- [ ] **Step 5: Write implementation notes**

Write the notes file with this requirement-test matrix:

| Requirement | Implementation | Test/result |
| --- | --- | --- |
| selection version card/note | file/function | test |
| stale note refresh | file/function | test |
| score parts | file/function | test |
| severe damage rejection | file/function | test |
| valid-number negative control | file/function | test |
| retreat/extension boundaries | file/function | test |
| source substring/order | file/function | test |
| source boundaries unchanged | gate | result |
| runtime budget | numstat | result |

Also record changed files, deviations, blocker/warning, and whether Batch B may
start. Do not run a formal report in Batch A.

## Stop Conditions

Stop immediately and report instead of expanding scope if:

- runtime net growth exceeds +100 lines;
- a third runtime file is required;
- severe OCR detection requires stock/report-specific replacement text;
- the implementation needs LLM rewriting, renderer changes, profile changes,
  scoring/target/risk/technical/recommendation changes, collection changes, or
  report/data/knowledge modifications;
- selected output cannot be proven to consist of original ordered source units.
