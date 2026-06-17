# Claude Task: Fresh Social Low-Credit Intake

Date: 2026-06-15

## Goal

Implement a bounded fresh social low-credit smoke for **中简科技 / 300777**.

This task tests fresh, less-filtered external community/social pages without using open web search. It must keep all accepted claims low-credit and unverified until claim verification compares them against higher-credit evidence.

Read first:

- `docs/agent_workflow/2026-06-15-fresh-social-low-credit-intake-design.md`
- `scripts/utils/community_claim_note_writer.py`
- `scripts/smoke_cached_community_claims.py`
- `scripts/utils/claim_verification.py`

## Allowed Files

You may add or edit:

- `scripts/utils/fresh_social_claim_intake.py`
- `scripts/smoke_fresh_social_claims.py`
- `tests/utils/test_fresh_social_claim_intake.py`
- `tests/reporter/test_fresh_social_claim_smoke_script.py`
- `docs/agent_workflow/2026-06-15-fresh-social-low-credit-intake-claude-notes.md`

Only if needed for import/test conventions:

- `tests/utils/test_claim_verification.py`

## Forbidden Files / Areas

Do not modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/data_fetcher.py`
- `scripts/utils/a_stock_source_intake.py`
- `scripts/utils/report_skills/**`
- report renderers
- technical analysis modules
- `config/stocks.json`
- `data/raw/**`
- `reports/**` except optional smoke audit JSON if explicitly requested by `--write-audit`
- `knowledge/**` except the one fresh social note when `--write` is explicitly used

Do not:

- use `s.jina.ai` or any open web search provider
- scrape Xueqiu detail pages
- use logged-in Chrome/CDP
- store cookies or credentials
- call Zhihu curator or LLMs
- download videos/PDFs
- wire this into Source Intake, Agent-Reach, report assembly, scoring, risk, EV, technical analysis, or final recommendation

## Implementation Requirements

### 1. Helper Module

Add `scripts/utils/fresh_social_claim_intake.py`.

It should be pure at import time:

- no network calls at module import
- no `yt-dlp`, browser, or optional CLI import at module import
- standard-library only unless an existing project dependency is already used

Core functions should support:

- building provider records from explicit URL reads
- sanitizing text
- applying the strict claim gate
- deduplicating claims
- rendering one low-credit note

### 2. Explicit URL Reader Provider

Only support explicit URLs.

The smoke script may accept:

```bash
--url <community-url>
```

repeated up to 5 times.

Allowed read path:

```text
https://r.jina.ai/<target-url>
```

No `s.jina.ai`. No open search.

Provider status enum:

- `ok`
- `empty`
- `error`
- `rate_limited`
- `blocked`

Failure handling:

- sequential calls only
- per-call timeout: 15 seconds
- global budget: 60 seconds
- retry count <= 1
- 429 => `rate_limited`
- 403 / anti-bot placeholder => `blocked`
- empty / placeholder / no useful text => `empty`
- never crash the smoke because one URL failed

### 3. URL / Domain Layer Filter

Reject official/news/research-like URLs before text extraction.

Reject at least:

- `cninfo.com.cn`
- `eastmoney.com` news/research/report paths where source is not community/forum
- `reportapi.eastmoney.com`
- `pdf.dfcfw.com`
- `finance.sina.com.cn`
- `stcn.com`
- `cls.cn`
- `gelonghui.com`

Allow only community-like domains/classes for this sprint, for example:

- Eastmoney 股吧 / guba style pages if URL path/domain clearly indicates forum/community
- public Weibo pages if readable without login
- other explicit community URLs only if they pass text gate

If no URL passes domain filter, return `empty`.

### 4. Claim Gate

Implement the gate as strict AND:

```text
stock name or stock code present
AND community-like marker present
AND verifiable business/event predicate present
AND no URL/domain/text negative signal present
```

Community-like markers include:

- `我认为`, `我觉得`, `个人`, `看法`, `猜`, `可能`, `估计`, `担心`, `有观点`
- `帖子`, `评论`, `雪球`, `股吧`, `微博`, `讨论`, `社区`

Verifiable predicates include:

- `收入下降`, `营收下降`
- `研发费用增长`, `研发费用同比`
- `订单`, `客户`, `发货`, `需求阶段性减少`
- `价格下调`, `毛利率承压`
- `减持`, `解禁`, `资金流出`

Reject pure sentiment / noise:

- `起飞`, `垃圾`, `庄家`, `韭菜`, `玄学`

Reject SEO/news/official text:

- `点击阅读全文`, `查看更多`, `相关股票`, `新浪财经`, `证券时报`, `东方财富网`, `每经`, `格隆汇`
- `公告编号`, `证券代码`, `本公司及董事会`, `PDF`, `研报`

Strip numbered citations:

- `[^n]`
- `[n]`

Caps:

- max raw items: 20
- max claims per provider: 5
- max total claims: 10
- max claim length: 180 chars

### 5. Output Contract

Default dry-run writes nothing.

`--write` writes one note:

```text
knowledge/10-Stocks/中简科技/<YYYYMMDD>-新鲜外部社媒claims.md
```

Frontmatter must include:

```yaml
stock: 中简科技
code: "300777"
source_type: social_discussion
source_credit: 30
verification_status: market_opinion
claim_status: unverified_claim
category: 新鲜社媒低信用线索
fresh: true
collected_via: fresh_social_smoke
claims:
  - claim_text: ...
    claim_status: unverified_claim
    source_url: ...
    source_platform: ...
```

Hard requirements:

- every claim is `claim_status: unverified_claim`
- output must never contain `confirmed_fact`
- output must never contain numbered citation markers
- file name must not collide with cached note `*-雪球缓存社区claims.md`

### 6. Smoke Script

Add `scripts/smoke_fresh_social_claims.py`.

Arguments:

- `--stock` default/required should support 中简科技
- `--code` default `300777`
- `--url` repeated
- `--date`
- `--base-dir`
- `--write`
- `--overwrite`
- `--write-audit`
- `--output-dir`
- `--json`

If no URLs are supplied, return a useful empty JSON summary and do not fail.

Optional audit JSON under `reports/` only when `--write-audit` is passed.

## Required Tests

Write failing tests first, then implement.

Helper tests:

- import does not access network
- official/news/research URLs are rejected at URL/domain layer
- community-like URL/text with stock reference and predicate becomes `unverified_claim`
- gate requires all AND conditions
- SEO/news text is rejected
- pure sentiment is rejected
- duplicate claims across provider records are deduplicated
- citations `[^n]` / `[n]` are stripped
- output note uses `source_credit: 30`
- output note never contains `confirmed_fact`
- fresh note filename does not collide with cached note
- caps are enforced

Smoke tests:

- dry-run default writes nothing
- `--write` writes only when explicit
- no URLs returns status `empty` and exit 0
- provider failure records status and does not crash
- `--write-audit` writes compact audit JSON without full page content

Run:

```bash
python3 -m pytest tests/utils/test_fresh_social_claim_intake.py tests/reporter/test_fresh_social_claim_smoke_script.py -q
```

Also run:

```bash
python3 -m pytest tests/utils/test_claim_verification.py -q
```

## Runtime Validation

After tests pass:

1. Run dry-run without URLs:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --json
```

2. If you have 1-2 known public community URLs for 中简科技 that are safe to read without login, run dry-run with them. If not, record that first dry-run is expected to be empty.

3. Only if useful claims are found, run:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url <url> --write --overwrite --json
```

4. Build claim verification plan for 中简科技 and confirm fresh note claims enter `low_credit_claims`.

5. Run at most one `scripts/run_中简科技.py --fast-test` only if fresh claims were written and useful.

## Notes Output

Write:

- `docs/agent_workflow/2026-06-15-fresh-social-low-credit-intake-claude-notes.md`

Include:

- files changed
- tests run and results
- dry-run summary
- whether any URLs were tested
- whether a fresh note was written
- claim verification counts if note was written
- whether any report runtime was run
- generated files
- deviations
- blocker

## Stop Conditions

Stop and report before implementing if:

- you need open search / `s.jina.ai`
- you need Xueqiu logged-in detail scraping or CDP
- you need credentials/cookies
- you need to modify scoring/risk/technical/EV/LLM/report pipeline
- useful implementation requires broad unrelated rewrites
