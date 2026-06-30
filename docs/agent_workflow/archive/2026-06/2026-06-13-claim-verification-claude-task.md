# Claim Verification Phase 4 Claude Implementation Task

> Date: 2026-06-13  
> Owner: Codex  
> Implementer: Claude Code  
> Design: `docs/agent_workflow/2026-06-13-claim-verification-design.md`  
> Review notes: `docs/agent_workflow/2026-06-13-claim-verification-claude-notes.md`  
> Status: Ready to implement

---

## Mission

Implement Phase 4 claim verification as a pure, dry-run module.

This phase reads high-credit evidence notes and low-credit legacy social notes, builds deterministic claim candidates, and returns a structured verification plan showing which low-credit claims are verified, supported, unverified, conflicted, or need review.

Do not connect this module to the report pipeline yet.

---

## Hard Boundaries

You may create or modify only these files:

- Create: `scripts/utils/claim_verification.py`
- Create: `tests/utils/test_claim_verification.py`
- Create: `docs/agent_workflow/2026-06-13-claim-verification-implementation-claude-notes.md`

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/evidence_note_skill.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/source_credit.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/run_黑芝麻智能.py`
- `scripts/xueqiu_monitor_v2.py`
- `config/stocks.json`
- `reports/**`
- real `knowledge/10-Stocks/**`

Do not:

- call LLMs
- call network
- launch browsers, Playwright, Chrome, or CDP
- call subprocess
- run `xueqiu_monitor_v2.py`
- run ZhihuCurator or DeepSeek curator
- write to real `knowledge/10-Stocks/**`
- wire this into pipeline
- change renderer/scoring/report template behavior

All tests must use `tmp_path` fixtures.

---

## Required Public API

Create `scripts/utils/claim_verification.py` with these dataclasses:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union


@dataclass(frozen=True)
class ClaimCandidate:
    claim_id: str
    stock: str
    source_file: str
    source_type: str
    source_credit: int
    verification_status: str
    claim_status: str
    claim_text: str
    topics: List[str]
    url: str = ""
    title: str = ""
    source_platforms: List[str] = field(default_factory=list)
    extraction_method: str = ""


@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    action: str
    verified_by: List[str]
    conflicts_with: List[str]
    confidence: int
    reasons: List[str]


@dataclass
class ClaimVerificationPlan:
    stock: str
    high_credit_claims: List[ClaimCandidate]
    low_credit_claims: List[ClaimCandidate]
    verifications: List[ClaimVerification]
    skipped_files: List[Dict[str, str]]

```

Also provide these public functions with exactly these signatures:

```text
def parse_frontmatter(path: Path) -> Tuple[Dict[str, Any], str]

def build_claim_verification_plan(
    stock_name: str,
    base_dir: Union[str, Path],
    dry_run: bool = True,
) -> ClaimVerificationPlan

def claim_verification_plan_to_dict(plan: ClaimVerificationPlan) -> Dict[str, Any]
```

`dry_run=False` must raise:

```python
raise NotImplementedError("Phase 4 only supports dry_run=True")
```

---

## Data Locations

Given:

```python
base_dir = Path("/tmp/test-knowledge")
stock_name = "黑芝麻智能"
```

Read:

- high/medium evidence notes from `base_dir / "10-Stocks" / stock_name / "evidence" / "*.md"`
- legacy social notes from `base_dir / "10-Stocks" / stock_name / "*.md"`

Skip all `MOC.md` / `moc.md` files by filename before parsing:

```python
path.name.lower() == "moc.md"
```

Add skipped entry:

```python
{"path": str(path), "reason": "moc_index"}
```

---

## Frontmatter Parsing Rules

`parse_frontmatter(path)` must:

1. Read UTF-8 text.
2. Split frontmatter only when the file starts with `---`.
3. Support both YAML-style frontmatter and JSON frontmatter.
4. Use `yaml.safe_load` only if PyYAML is available.
5. Always support JSON frontmatter with `json.loads`.
6. Never use `eval` or unsafe loaders.
7. Return `(metadata, body)`.
8. If there is no frontmatter, return `({}, full_text)`.
9. Raise a local parse exception or `ValueError` for malformed frontmatter; `build_claim_verification_plan()` must catch it and record `malformed_frontmatter`.

Suggested behavior:

- Try JSON first if stripped frontmatter starts with `{`.
- Otherwise try YAML if available.
- If YAML is unavailable and content is not JSON, raise malformed parse error.

---

## Claim Extraction Rules

### Evidence Notes

Evidence note source:

```text
knowledge/10-Stocks/<stock>/evidence/*.md
```

Use frontmatter only.

For each frontmatter claim:

- accept claims shaped as strings or dicts
- if dict, use `claim_text`; if missing, try `text`; if missing, skip that claim
- stable claim id:

```python
sha256(f"{source_file}|{claim_text}".encode("utf-8")).hexdigest()[:12]
```

Metadata:

- `source_type` from frontmatter, default `unknown_web`
- `source_credit` integer from frontmatter, default `0`
- `verification_status` from frontmatter, default `unknown`
- `claim_status` from claim dict or frontmatter `claim_status`, default `fact_candidate`
- `topics` from claim dict `topics` or frontmatter `topics`, normalized to list of strings
- `url`, `title` from frontmatter
- `source_platforms`: normalize both `source_platforms` and singular `source_platform`
- `extraction_method`: `evidence_frontmatter_claim`

Bucket rules:

- `source_credit >= 80`: high-credit bucket
- `55 <= source_credit < 80`: professional/medium evidence bucket for verification support, not in `high_credit_claims`
- `source_credit < 55`: not a verification source; skip or classify low only if it is explicitly social

Implementation note: `ClaimVerificationPlan` only exposes `high_credit_claims` and `low_credit_claims`. You may keep a local `medium_credit_claims` list inside the function for `supported` matching.

### Legacy Social Notes

Legacy social source:

```text
knowledge/10-Stocks/<stock>/*.md
```

Rules:

- skip `MOC.md` by basename before parsing
- process only files whose frontmatter has:
  - `source_type == "social_discussion"`, or
  - `verification_status == "market_opinion"`
- these notes always become low-credit claims, never high-credit
- do not use body sections as fact sources
- do not parse `confirmed_facts`, `announcements`, `inferences`, `原始数据`, or similar body content

If frontmatter has `claims`:

- use those claims as low-credit claims
- `claim_status`: `unverified_claim`
- `extraction_method`: `legacy_social_frontmatter_claim`

If frontmatter has no `claims`, create one coarse stub:

```text
{title or stock/category}：该社区笔记包含待验证观点，需用高信用来源核查。
```

For example:

```text
公司公告：该社区笔记包含待验证观点，需用高信用来源核查。
```

Set:

- `source_type`: `social_discussion`
- `source_credit`: use frontmatter source_credit if present, otherwise `35`
- `verification_status`: `market_opinion`
- `claim_status`: `unverified_claim`
- `extraction_method`: `legacy_social_stub`
- `source_platforms`: from `source_platforms`; default `[]`

Even if the filename or category is `公司公告`, a social/market-opinion note stays low-credit.

---

## Verification Rules

Only verify low-credit claims.

Trust direction:

- high-credit evidence can produce `verified` or `needs_review`
- medium-credit evidence can produce `supported` only
- social claims can never verify another claim

Actions:

- `verified`
- `supported`
- `conflicted`
- `unverified`
- `needs_review`

Confidence bands must be enforced:

- `verified`: 70-100
- `supported`: 40-69
- `unverified`: 0-39
- `needs_review`: 0
- `conflicted`: 0

Medium-credit sources must never produce `verified`; their confidence must be `<= 69`.

### Deterministic Matching

Use no LLM and no complex NLP. Implement keyword/regex matching.

Specific terms:

- Products: `A2000U`, `A2000X`, `A1000`, `SoC`, `自动驾驶`, `ADAS`, `NOA`
- Customers/cooperation: `理想`, `东风`, `如祺`, `上实`, `定点`, `订单`, `交付`
- Certifications/events: `ASIL-D`, `ISO 26262`, `认证`, `获奖`
- Financial: `营收`, `亏损`, `毛利率`, `同比`, `环比`

Generic terms insufficient alone:

- `芯片`
- `公告`
- `合作`
- `收入`
- `增长`
- `投资者`

Suggested matching behavior:

- Find topic overlap between low claim and source claim.
- Extract specific terms and generic terms from `claim_text + title`.
- Strong high-credit match:
  - same stock
  - topic overlap or source/target topics are both empty
  - at least one shared specific term
  - action `verified`
  - confidence around `78`
  - `verified_by` includes high-credit claim id
- Weak high-credit generic-only match:
  - only one shared generic term
  - no shared specific term
  - action `needs_review`
  - confidence `0`
  - `verified_by` may include candidate id
- Medium-credit specific match:
  - at least one shared specific term
  - action `supported`
  - confidence around `58`
  - `verified_by` includes medium claim id
- No match:
  - action `unverified`
  - confidence around `20`

`needs_review` downgrade conditions:

- only one generic term matches and no specific term
- matched sources span incompatible topics
- time-sensitive claim lacks usable date context
- multiple high-credit matches suggest different interpretations

You may implement `conflicted` conservatively as unused in Phase 4 if no deterministic conflict rule is reliable, but the dataclass and action vocabulary must support it.

---

## Tests To Write First

Create `tests/utils/test_claim_verification.py`.

Use `tmp_path` only. Do not touch real `knowledge/`.

Write tests covering all of these behaviors:

1. YAML-style evidence frontmatter parses.
2. JSON legacy frontmatter parses.
3. JSON frontmatter parses even if PyYAML is unavailable, if this is monkeypatchable without brittle import tricks.
4. `MOC.md` and `moc.md` are skipped by filename regardless of frontmatter.
5. Social notes with no `claims` create one `legacy_social_stub` claim.
6. Legacy social body fields such as `confirmed_facts` and `announcements` are ignored.
7. Legacy social note with `category: 公司公告` still enters low-credit bucket if frontmatter says social/market opinion.
8. High-credit official evidence enters high-credit bucket.
9. Social claim enters low-credit bucket.
10. Legacy social notes never enter high-credit bucket even when they have a `claims` list.
11. Social claim never verifies another social claim.
12. High-credit shared topic and specific key terms verify a social claim.
13. Single generic term match downgrades to `needs_review`, not `verified`.
14. Medium professional source produces `supported`, not `verified`, and confidence `<= 69`.
15. Unrelated low-credit claim remains `unverified`.
16. Malformed frontmatter becomes a `skipped_files` entry with `reason`, no exception escapes.
17. `claim_verification_plan_to_dict()` returns a plain dict with nested dict/list values.
18. `dry_run=False` raises `NotImplementedError`.
19. All test data is under `tmp_path`.

Helpful test fixture shape:

```python
def write_note(path: Path, frontmatter: str, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path
```

Use paths like:

```python
root = tmp_path / "knowledge"
stock_dir = root / "10-Stocks" / "黑芝麻智能"
evidence_dir = stock_dir / "evidence"
```

---

## Implementation Order

1. Create `tests/utils/test_claim_verification.py` with the tests above.
2. Run:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Expected before implementation: failures due to missing module.

3. Create `scripts/utils/claim_verification.py`.
4. Implement dataclasses, frontmatter parsing, claim extraction, verification, and plain-dict conversion.
5. Re-run:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Expected: all new tests pass.

6. Run safety suite:

```bash
python3 -m pytest tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_evidence_note_skill.py -q
```

Expected: all pass.

7. Write implementation notes to:

```text
docs/agent_workflow/2026-06-13-claim-verification-implementation-claude-notes.md
```

Include:

- files changed
- public API implemented
- tests run and results
- any deviation from design
- confirmation that no real `knowledge/` files were written
- confirmation that no pipeline/renderer/scoring/entry-script files were modified

---

## Acceptance Criteria

Implementation is accepted only if:

- `scripts/utils/claim_verification.py` exists and is pure/deterministic.
- `tests/utils/test_claim_verification.py` exists and covers the required cases.
- `dry_run=False` raises `NotImplementedError`.
- `MOC.md` skip is filename-based and case-insensitive.
- frontmatter parser supports YAML and JSON.
- malformed frontmatter is reported in `skipped_files` with `reason`.
- legacy social notes are always low-credit and never used to verify other claims.
- legacy social note bodies are not treated as fact sources.
- high-credit official evidence can verify matching social claims.
- medium-credit evidence can only support, with confidence capped below verified.
- all new tests pass.
- safety suite passes.
- no forbidden files are modified.
- no real `knowledge/10-Stocks/**` files are written.

---

## Final Response Format

After implementation, reply with a concise summary:

```text
Phase 4 implementation complete.

Files changed:
- scripts/utils/claim_verification.py
- tests/utils/test_claim_verification.py
- docs/agent_workflow/2026-06-13-claim-verification-implementation-claude-notes.md

Tests:
- python3 -m pytest tests/utils/test_claim_verification.py -q
- python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py -q

Key behavior:
- dry-run claim verification plan generated
- high-credit evidence verifies/supports low-credit social claims
- social notes never verify other notes

Notes:
- docs/agent_workflow/2026-06-13-claim-verification-implementation-claude-notes.md

Blockers or deviations:
- None, or list the exact deviation and why it was necessary
```
