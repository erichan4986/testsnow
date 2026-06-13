# Claim Extraction Phase 4D Claude Implementation Task

> Date: 2026-06-13  
> Owner: Codex  
> Implementer: Claude Code  
> Design: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-design.md`  
> Review notes: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-claude-notes.md`  
> Status: Ready to implement

---

## Mission

Implement deterministic legacy social body claim extraction for Phase 4D.

Phase 4C showed that real legacy notes currently become empty category stubs and therefore produce 100% `unverified`. Phase 4D should extract substantive, low-credit, unverified claims from structured Markdown bullets in legacy social notes.

This must remain a dry-run verification framework. Do not integrate with report generation or KnowledgeSynthesizer.

---

## Hard Boundaries

You may modify or create only these files:

- Modify: `scripts/utils/claim_verification.py`
- Modify: `tests/utils/test_claim_verification.py`
- Create: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md`
- Create: `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md`

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
- call subprocess from production code
- run `xueqiu_monitor_v2.py`
- run `run_黑芝麻智能.py`
- run any `run_*.py` report entry
- run ZhihuCurator or DeepSeek curator
- write to real `knowledge/10-Stocks/**`
- wire this into pipeline
- change renderer/scoring/report template behavior

Temporary runtime validation may write only under:

```text
/tmp/claim_extraction_phase4d_validation/**
```

---

## Required Behavior

### Extraction Flow

In `scripts/utils/claim_verification.py`, update `_extract_social_claims()`:

1. Parse social note frontmatter and body.
2. Continue to skip non-social notes unless:
   - `source_type == "social_discussion"`, or
   - `verification_status == "market_opinion"`
3. Skip `MOC.md` by filename as before.
4. Skip technical notes before body extraction:
   - `category == "技术指标"`, or
   - `data_source == "mootdx+stockstats"`
   - record `{"path": str(path), "reason": "technical_note_skipped"}`
   - do not create fallback stubs for technical notes.
5. If frontmatter has explicit `claims`, keep current precedence and do not body-extract that file.
6. Else call `extract_legacy_social_claims_from_body(stock_name, meta, body, source_file)`.
7. If body extraction returns claims, use them.
8. Else fall back to existing `legacy_social_stub`.

### Extraction Helper

Add a pure deterministic helper inside `claim_verification.py`:

```python
def extract_legacy_social_claims_from_body(
    stock_name: str,
    meta: Dict[str, Any],
    body: str,
    source_file: str,
) -> List[ClaimCandidate]:
    """Return low-credit unverified claim candidates extracted from structured body bullets."""
```

It can be public for tests, but it must not import pipeline, renderer, scoring, network, or LLM code.

### Trust Metadata

Every body-extracted claim must have:

- `source_type="social_discussion"`
- `source_credit=min(int(meta.get("source_credit", 35)), 35)`
- `verification_status="market_opinion"`
- `claim_status="unverified_claim"`
- `source_platforms` from frontmatter, usually `["雪球", "知乎"]`
- `extraction_method="legacy_social_body_rule"`

Body extraction must never create high-credit or medium-credit candidates.

### Supported Fields And Prefixes

Extract only child bullets under these fields:

| Field | Max | Prefix |
|---|---:|---|
| `reports` | 5 | `{stock}研报线索：` |
| `announcements` | 5 | `{stock}公告线索：` |
| `catalysts` | 3 | `{stock}催化线索：` |
| `key_risks` | 3 | `{stock}风险线索：` |
| `inferences` | 3 | `{stock}推断线索：` |
| `opinions` | 3 | `{stock}观点线索：` |
| `confirmed_facts` | 3 | `{stock}疑似事实线索：` |

Do not extract:

- `position_suggestion`
- `report_sections`
- `_resonance`
- numeric indicator fields like `close`, `volume`, `macd`, `rsi_14`
- H1 title
- source marker blockquote
- `相关链接`

Never use the words `确认事实` or `confirmed` in generated claim text.

### Priority And Limits

Apply per-field limits first, then concatenate by this fixed priority:

1. `reports`
2. `announcements`
3. `catalysts`
4. `key_risks`
5. `inferences`
6. `opinions`
7. `confirmed_facts`

Then apply:

```python
MAX_BODY_CLAIMS_PER_FILE = 8
```

This global cap must happen after priority ordering.

### Bullet Parsing

Parse simple Markdown structures:

```markdown
- **reports**: 5 条
  - 2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 2025年净利润较快增长，拓展机器人、服务器液冷等新领域
```

Rules:

- detect top-level field headers like `- **reports**:`
- collect indented child bullets below supported fields
- stop at the next top-level field header or heading
- each useful child bullet becomes one claim

Filter out:

- empty or whitespace-only bullets
- punctuation-only bullets
- bullets shorter than 6 characters after cleanup
- `*AI分析暂缺*`
- pure counts like `5 条`
- wikilink-only lines like `[[20260612-深度分析]]`
- duplicate cleaned bullet text within the same file

### Topic Inference

Infer topics from claim text using deterministic keywords.

`product_progress`:

- `机器人`
- `仿生机器人`
- `液冷`
- `储能`
- `热管理`
- `新能源`
- `产品`
- `业务`
- `布局`

`customer_orders`:

- `客户`
- `订单`
- `定点`
- `合作`
- `供应`

`earnings_business`:

- `业绩`
- `营收`
- `净利润`
- `毛利率`
- `盈利`
- `增长`
- `年报`
- `季报`

`market_sentiment`:

- `机构`
- `持仓`
- `减持`
- `资金`
- `风险`
- `分歧`
- `估值`
- `预期`
- `关注`

Fallback by category:

- `最新研报` -> `earnings_business`
- `公司公告` -> `market_sentiment`
- `深度分析` -> `market_sentiment`

Technical notes are skipped before fallback, so no `技术指标` fallback is needed.

If still no topic, use `market_sentiment`.

---

## Test-First Requirements

Before implementation, add or update tests in:

```text
tests/utils/test_claim_verification.py
```

Run targeted tests after adding them and confirm they fail before implementation.

Required tests:

1. `reports` child bullets extract multiple low-credit claims.
2. `announcements` child bullets extract low-credit claims.
3. body-extracted claims preserve social metadata:
   - `source_type == "social_discussion"`
   - `source_credit == 35`
   - `verification_status == "market_opinion"`
   - `claim_status == "unverified_claim"`
   - `extraction_method == "legacy_social_body_rule"`
4. body-extracted claims never enter `high_credit_claims`.
5. `confirmed_facts` child bullets extract as neutral `疑似事实线索`, not `确认事实`.
6. empty counts like `confirmed_facts: 1 条` without child bullets do not create fake claims.
7. `*AI分析暂缺*`, empty bullets, whitespace-only bullets, punctuation-only bullets, wikilink-only lines, and pure counts are filtered.
8. global max 8 cap applies after field priority.
9. frontmatter `claims` still take precedence over body extraction.
10. no frontmatter claims and no extractable body claims still creates fallback stub.
11. topic inference works for robot/liquid-cooling/earnings/risk keywords.
12. real-shaped 三花智控 latest-report fixture yields claims containing `仿生机器人`, `服务器液冷`, or `净利润`.
13. extracted body claims can be verified or supported by high/medium evidence in the same dry-run plan.
14. `dry_run=False` behavior remains `NotImplementedError`.
15. `category=技术指标` or `data_source=mootdx+stockstats` is skipped with `technical_note_skipped`.
16. technical notes do not create fallback stubs.
17. older notes without social frontmatter remain skipped with `unknown_source_type`.
18. `position_suggestion` is not extracted.
19. tests use `tmp_path`; no real `knowledge/` writes.
20. social body-extracted claims never verify other social claims.

Update the old `test_social_body_confirmed_facts_ignored` behavior. It should no longer assert that body fields are ignored. Replace it with a test that asserts `confirmed_facts` body entries become low-credit unverified claims with neutral text.

---

## Commands To Run

Focused tests:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Safety suite:

```bash
python3 -m pytest tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_evidence_note_skill.py -q
```

Do not run:

```text
xueqiu_monitor_v2.py
run_黑芝麻智能.py
run_*.py
```

---

## Runtime Revalidation

After tests pass, rerun a Phase 4C-style validation on `三花智控` using `/tmp`.

Use temp root:

```text
/tmp/claim_extraction_phase4d_validation/knowledge
```

Copy real `knowledge/10-Stocks/三花智控/*.md` into temp only. Do not edit real notes.

Create temporary validation evidence notes in temp only, similar to Phase 4C:

- company official robotics claim
- company official thermal-management claim
- medium broker earnings claim

Run:

```python
plan = build_claim_verification_plan("三花智控", temp_knowledge_root, dry_run=True)
```

Save:

```text
/tmp/claim_extraction_phase4d_validation/claim_verification_plan.json
/tmp/claim_extraction_phase4d_validation/summary.json
```

Expected runtime improvement:

- `legacy_social_body_rule` count greater than 0
- low-credit claims are substantive, not only stubs
- technical note skipped with `technical_note_skipped`
- older untagged notes skipped with `unknown_source_type`
- no real `knowledge/` writes

Do not require every claim to be verified. The goal is to confirm extraction quality improves enough to make verification meaningful.

Write runtime notes to:

```text
docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md
```

Include:

- commands run
- selected stock
- temp paths
- tests result
- count of `legacy_social_body_rule`
- count of `legacy_social_stub`
- skipped reasons
- action counts
- 10 representative extracted claims
- whether `confirmed_facts` prefix is neutral
- whether technical notes were skipped
- recommendation for next phase

---

## Implementation Notes

Create:

```text
docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md
```

Include:

- files changed
- helper functions added
- tests added/updated
- tests run and results
- runtime validation result
- deviations from design
- confirmation that no forbidden files were changed
- confirmation that no real `knowledge/` files were written

---

## Acceptance Criteria

Accepted only if:

- new body extraction tests fail before implementation and pass after implementation
- focused tests pass
- safety suite passes
- technical notes are skipped with `technical_note_skipped`
- older untagged notes stay `unknown_source_type`
- `confirmed_facts` text is neutral and low-credit
- body-extracted claims never enter `high_credit_claims`
- body-extracted social claims never verify other social claims
- Phase 4D runtime validation shows body-derived claims on 三花智控
- no pipeline/LLM/network/browser/report entry/real knowledge write happens

---

## Final Response Format

After implementation and runtime validation, reply with:

```text
Phase 4D implementation complete.

Files changed:
- scripts/utils/claim_verification.py
- tests/utils/test_claim_verification.py
- docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md
- docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md

Tests:
- python3 -m pytest tests/utils/test_claim_verification.py -q
- python3 -m pytest tests/utils/test_claim_verification.py tests/utils/test_evidence_note_writer.py tests/reporter/test_evidence_note_skill.py -q

Runtime validation:
- temp output: /tmp/claim_extraction_phase4d_validation/claim_verification_plan.json
- legacy_social_body_rule: <count>
- legacy_social_stub: <count>
- actions: <action counts>

Key findings:
- <summarize extracted claim quality and verification outcome>

Notes:
- docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md
- docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md

Blockers or deviations:
- None, or list exact blocker/deviation
```
