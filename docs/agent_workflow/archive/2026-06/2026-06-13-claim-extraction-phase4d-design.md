# Claim Extraction Phase 4D Design

> Date: 2026-06-13  
> Owner: Codex  
> Status: Draft for Claude review  
> Context: Phase 4C showed 100% `unverified` because legacy social notes became coarse category stubs.

---

## 1. Goal

Add deterministic claim extraction for legacy Xueqiu/Zhihu social notes so Phase 4 claim verification has real low-credit claims to verify.

Phase 4D should:

- read structured legacy social note bodies
- extract concrete claim candidates from body bullets
- preserve low-credit social metadata
- keep all extracted claims as `unverified_claim`
- continue dry-run only
- avoid LLM, network, browser, subprocess, and real `knowledge/` writes

The output is still a claim verification plan. The difference is that low-credit claims become substantive instead of empty stubs like:

```text
公司公告：该社区笔记包含待验证观点，需用高信用来源核查。
```

---

## 2. Phase 4C Findings

Phase 4C on `三花智控`:

- 9 legacy files copied
- 4 processable social notes
- 0 explicit frontmatter claims
- 4 `legacy_social_stub` claims
- 4/4 `unverified`

The module behaved safely, but the input claims were too shallow.

Observed legacy note body patterns:

### 2.1 Company Announcements

```markdown
## 原始数据
- **announcements**: 15 条
  - 三花智控:第八届董事会第十七次临时会议决议公告
  - 三花智控:关于召开2025年度股东会的通知
```

### 2.2 Research Reports

```markdown
## 原始数据
- **reports**: 5 条
  - 2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 2025年净利润较快增长，拓展机器人、服务器液冷等新领域
```

### 2.3 Deep Analysis

```markdown
## 原始数据
- **confirmed_facts**: 1 条
- **inferences**: 0 条
- **opinions**: 0 条
- **key_risks**: 1 条
- **catalysts**: 0 条
```

Some older notes include richer nested section content, but may not yet have social frontmatter.

### 2.4 Technical Indicators

```markdown
- **close**: 46.3
- **rsi_14**: 27.39
- **weekly_trend**: 震荡
- **_resonance**:
  - trend: 空头
  - momentum: 偏弱
```

Technical note bodies are large and noisy. Phase 4D skips technical notes entirely and records `technical_note_skipped` instead of extracting numeric/technical claims.

---

## 3. Non-Goals

Phase 4D does not:

- call LLMs
- call network
- launch browser / Playwright / Chrome / CDP
- run `xueqiu_monitor_v2.py`
- run report entry scripts
- write real `knowledge/10-Stocks/**`
- connect to pipeline
- modify `KnowledgeSynthesizer`
- modify scoring / renderer / report templates
- elevate social content into facts
- treat legacy body sections as high-credit evidence
- parse arbitrary Markdown prose deeply

---

## 4. Proposed Architecture

Modify only:

```text
scripts/utils/claim_verification.py
tests/utils/test_claim_verification.py
docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md
```

Do not create a new pipeline skill.

Add a deterministic internal extraction layer:

```python
def extract_legacy_social_claims_from_body(
    stock_name: str,
    meta: Dict[str, Any],
    body: str,
    source_file: str,
) -> List[ClaimCandidate]:
    """Return low-credit unverified claim candidates extracted from body bullets."""
```

This can be public if tests need direct access, but it should remain pure and deterministic.

Existing flow in `_extract_social_claims()` becomes:

1. if frontmatter has `claims`, use them as before
2. else try body extractor
3. if body extractor returns claims, use those
4. else fall back to `legacy_social_stub`

The fallback stub remains as safety net.

---

## 5. Extraction Rules

### 5.1 Trust And Metadata

Every extracted body claim from a legacy social note must have:

- `source_type="social_discussion"`
- `source_credit=35` unless frontmatter has a lower value
- `verification_status="market_opinion"`
- `claim_status="unverified_claim"`
- `source_platforms` from frontmatter, typically `["雪球", "知乎"]`
- `extraction_method="legacy_social_body_rule"`
- `source_file` pointing to the note path

If the frontmatter says `source_credit > 35`, cap extracted social body claim credit at `35`.

Body extraction must never create high-credit or medium-credit candidates.

### 5.2 Supported Body Fields

Before body extraction, skip technical notes entirely when either condition is true:

- `category == "技术指标"`
- `data_source == "mootdx+stockstats"`

Skipped technical notes should produce:

```python
{"path": str(path), "reason": "technical_note_skipped"}
```

They should not create fallback stubs.

Extract from these structured fields:

| Field | Extract? | Topic | Notes |
|---|---:|---|---|
| `announcements` | yes | `market_sentiment` or `earnings_business` | announcement title claims |
| `reports` | yes | `earnings_business`, `product_progress` | broker/report title claims, still low-credit because note source is social/legacy |
| `confirmed_facts` | yes, but as unverified social claim | inferred by keywords | claim text must use neutral `疑似事实线索` prefix; must not become fact |
| `inferences` | yes | inferred by keywords | already opinion-like |
| `opinions` | yes | `market_sentiment` | opinion-like |
| `key_risks` | yes | `market_sentiment` | risk candidate |
| `catalysts` | yes | `product_progress` or `market_sentiment` | catalyst candidate |
| `position_suggestion` | no | none | investment advice, not a verifiable claim in Phase 4D |

Do not extract from:

- `report_sections` prose blocks in Phase 4D
- `_resonance` nested technical dict
- raw numeric indicator fields such as `close`, `volume`, `macd`, `rsi_14`
- `相关链接`
- H1 title
- source marker blockquote

Technical notes are skipped entirely in Phase 4D. Technical claim extraction can be designed separately if it becomes useful later.

### 5.3 Bullet Parsing

The extractor should parse simple Markdown lists:

```markdown
- **reports**: 5 条
  - 2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
  - 2025年净利润较快增长，拓展机器人、服务器液冷等新领域
```

For a supported field:

- detect header line `- **field_name**:`
- collect indented child bullets until next top-level field header like `- **reports**:` or next heading
- each child bullet becomes a candidate if it has useful text

Compact scalar fields are not extracted in Phase 4D.

```markdown
- **position_suggestion**: 持有
```

Skip scalar values and generic values:

- `观望`
- `持有`
- `暂无`
- `*AI分析暂缺*`
- empty strings
- pure counts like `5 条`

### 5.4 Claim Text Format

Generated claim text should include stock name and field context:

```text
三花智控研报线索：2026年一季报点评：业绩符合市场预期，仿生机器人等新兴产业蓄势待发
```

Examples:

- `三花智控公告线索：三花智控:关于召开2025年度股东会的通知`
- `三花智控研报线索：2025年净利润较快增长，拓展机器人、服务器液冷等新领域`
- `三花智控风险线索：机构持仓减少可能导致短期资金面分歧`
- `三花智控疑似事实线索：公司主业稳健，新业务提供长期增长动力`

Do not prefix with “确认事实”.

Field-specific neutral prefixes:

| Field | Prefix |
|---|---|
| `reports` | `{stock}研报线索：` |
| `announcements` | `{stock}公告线索：` |
| `catalysts` | `{stock}催化线索：` |
| `key_risks` | `{stock}风险线索：` |
| `inferences` | `{stock}推断线索：` |
| `opinions` | `{stock}观点线索：` |
| `confirmed_facts` | `{stock}疑似事实线索：` |

### 5.5 Filtering And Limits

Filter out:

- empty bullets
- bullets with only punctuation
- bullets shorter than 6 Chinese/ASCII characters after cleanup
- `*AI分析暂缺*`
- links like `[[20260612-深度分析]]`
- repeated duplicate claim text within the same file

Limit per file:

- global max 8 body-extracted claims after applying field priority
- max 5 from `reports`
- max 5 from `announcements`
- max 3 from `key_risks`
- max 3 from `catalysts`
- max 3 from `inferences`
- max 3 from `opinions`
- max 3 from `confirmed_facts`

Field priority before the global cap:

1. `reports`
2. `announcements`
3. `catalysts`
4. `key_risks`
5. `inferences`
6. `opinions`
7. `confirmed_facts`

This keeps noisy notes from flooding verification.

### 5.6 Topic Inference

Infer topics from claim text using deterministic keywords:

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

If none match, use frontmatter category:

- `最新研报` -> `earnings_business`
- `公司公告` -> `market_sentiment`
- `深度分析` -> `market_sentiment`
- `技术指标` -> `market_sentiment`

If still none, use `market_sentiment`.

---

## 6. Backward Compatibility

Existing tests should continue to pass.

One existing behavior should be updated carefully:

Current test:

```python
test_social_body_confirmed_facts_ignored
```

Its original purpose was to ensure body fields are not treated as facts. Phase 4D changes the behavior to read some body fields, but still as low-credit unverified claims.

Update or replace this test so it asserts:

- body-derived claims are extracted
- `claim_status == "unverified_claim"`
- `source_credit == 35`
- `verification_status == "market_opinion"`
- `extraction_method == "legacy_social_body_rule"`
- claim text uses neutral `疑似事实线索` for `confirmed_facts`
- no body-derived claim enters high-credit bucket

Do not keep an obsolete test that forbids all body extraction.

---

## 7. Tests Required

Add or update tests in:

```text
tests/utils/test_claim_verification.py
```

Required cases:

1. report bullets under `reports` extract multiple low-credit claims.
2. announcement bullets under `announcements` extract low-credit claims.
3. extracted body claims preserve social metadata and never enter high-credit bucket.
4. `confirmed_facts` body entries extract as `unverified_claim`, not facts.
5. empty counts like `confirmed_facts: 1 条` without child bullets do not create fake claims.
6. `*AI分析暂缺*`, empty bullets, wikilinks, and pure counts are filtered.
7. per-file extraction limit prevents more than 8 claims after fixed field priority.
8. frontmatter claims still take precedence over body extraction.
9. if no frontmatter claims and no extractable body claims, fallback stub still works.
10. topic inference works for robot/liquid-cooling/earnings/risk keywords.
11. real-shaped 三花智控 latest-report fixture yields claims containing `仿生机器人`, `服务器液冷`, or `净利润`.
12. extracted claims can be verified/supported by high/medium evidence in the same dry-run plan.
13. social body extraction does not change `dry_run=False` behavior.
14. tests use `tmp_path`, no real `knowledge/` writes.
15. `category=技术指标` or `data_source=mootdx+stockstats` is skipped with `technical_note_skipped`.
16. older notes without `source_type=social_discussion` / `verification_status=market_opinion` remain skipped as `unknown_source_type`.
17. `position_suggestion` is not extracted.

Suggested test command:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

Safety command:

```bash
python3 -m pytest tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_evidence_note_skill.py -q
```

Do not run report entries or `xueqiu_monitor_v2.py`.

---

## 8. Runtime Revalidation Required After Implementation

After implementation and tests, rerun a Phase 4C-style validation on `三花智控` using `/tmp`, not real `knowledge/`.

Expected improvement:

- low-credit claims should be body-derived, not only stubs
- `legacy_social_body_rule` count should be greater than 0
- `unverified` rate should be below 100% if temporary evidence overlaps with extracted claims

Write validation notes to:

```text
docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md
```

---

## 9. Files Expected To Change

| File | Change Type | Reason |
|---|---|---|
| `scripts/utils/claim_verification.py` | Modify | Add deterministic legacy social body claim extraction. |
| `tests/utils/test_claim_verification.py` | Modify | Add extraction and verification tests. |
| `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-implementation-claude-notes.md` | Create | Implementation notes. |
| `docs/agent_workflow/2026-06-13-claim-extraction-phase4d-runtime-validation-claude-notes.md` | Create | Runtime validation notes after implementation. |

---

## 10. Files That Must Not Change

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

---

## 11. Review Questions

1. Is deterministic Markdown bullet extraction enough for Phase 4D, or should we design an LLM extractor now?
2. Does extracting from `confirmed_facts` as `unverified_claim` preserve the safety boundary clearly enough?
3. Should technical notes be skipped entirely in Phase 4D to avoid noisy technical claims?
   - Current design answer: yes, skip them entirely.
4. Are the per-file limits and fixed field priority appropriate?
5. Should older notes without social frontmatter remain skipped?
   - Current design answer: yes, continue requiring explicit social metadata.
6. Is modifying `claim_verification.py` still the right boundary, or should extraction move into a separate `legacy_claim_extractor.py` module?
7. What tests are missing to prevent social body content from becoming high-credit facts?
