# Fresh Social Low-Credit Intake — Implementation Notes

Date: 2026-06-15

## Files Changed

- `scripts/utils/fresh_social_claim_intake.py` (new)
- `scripts/smoke_fresh_social_claims.py` (new)
- `tests/utils/test_fresh_social_claim_intake.py` (new)
- `tests/reporter/test_fresh_social_claim_smoke_script.py` (new)
- `docs/agent_workflow/2026-06-15-fresh-social-low-credit-intake-claude-notes.md` (this file)

No existing source files were modified. No scoring/risk/technical/EV/LLM/report pipeline code was touched.

## Implementation Summary

### Helper module

`scripts/utils/fresh_social_claim_intake.py` provides:

- Pure-at-import helper with no network or optional CLI imports.
- Explicit URL reader URL builder (`https://r.jina.ai/<target-url>`).
- URL/domain layer filter:
  - Blocks: `cninfo.com.cn`, `reportapi.eastmoney.com`, `pdf.dfcfw.com`, `finance.sina.com.cn`, `stcn.com`, `cls.cn`, `gelonghui.com`, and non-forum Eastmoney paths.
  - Allows: `guba.eastmoney.com`, `xueqiu.com`, `weibo.com`, `m.weibo.cn`, plus generic `/guba/`, `/oa/`, `/article/` path markers.
- Strict AND claim gate:
  - stock name or code present
  - AND community marker present (`我认为`, `股吧`, `微博`, etc.)
  - AND verifiable predicate present (`收入下降`, `研发费用增长`, etc.)
  - AND no negative signal present (SEO/news/official markers or pure sentiment)
- Page-level negative-signal rejection so a news/SEO page cannot yield a clean sentence as a claim.
- Deduplication by normalized claim text.
- Caps: 20 raw items, 5 claims/provider, 10 total claims, 180 chars per claim.
- Citation stripping (`[^n]`, `[n]`).
- Low-credit note rendering with `source_credit: 30`, `verification_status: market_opinion`, `claim_status: unverified_claim`, `fresh: true`, `collected_via: fresh_social_smoke`.
- Defensive writer that raises `ValueError` if any claim would be emitted as `confirmed_fact`.

### Smoke script

`scripts/smoke_fresh_social_claims.py` provides:

- CLI: `--stock`, `--code`, `--url` (up to 5), `--date`, `--base-dir`, `--output-dir`, `--write`, `--overwrite`, `--write-audit`, `--max-claims`, `--json`.
- Default dry-run; writes nothing to `knowledge/` without `--write`.
- Sequential URL reads through Jina Reader.
- Per-call timeout 15s, global budget 60s, retry ≤1.
- Status enum: `ok`, `empty`, `error`, `rate_limited`, `blocked`.
- No crash on timeout/429/5xx/empty.
- Optional compact audit JSON under `reports/` via `--write-audit` (no full page content).
- Writes one note: `knowledge/10-Stocks/中简科技/<YYYYMMDD>-新鲜外部社媒claims.md`.

## Tests Run and Results

Failing tests were written first, then implementation.

```bash
python3 -m pytest tests/utils/test_fresh_social_claim_intake.py tests/reporter/test_fresh_social_claim_smoke_script.py tests/utils/test_claim_verification.py -q
```

Result: **95 passed**.

Covered:

- import purity / no network
- URL/domain filter rejects official/news/research URLs
- community-like URL/text becomes `unverified_claim`
- gate requires all AND conditions
- SEO/news text rejected at page level
- pure sentiment rejected
- duplicate claims deduplicated
- citations stripped
- `source_credit: 30`
- no `confirmed_fact` output
- filename distinct from cached community note
- caps enforced
- dry-run default writes nothing
- `--write` required for disk output
- no URLs returns `empty` and exit 0
- provider failure records status and does not crash
- `--write-audit` writes compact JSON

## Dry-Run Summary

### Without URLs

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --json
```

```json
{
  "stock_name": "中简科技",
  "stock_code": "300777",
  "status": "empty",
  "claim_count": 0,
  "path": "knowledge/10-Stocks/中简科技/20260615-新鲜外部社媒claims.md",
  "providers": [],
  "write": false,
  "overwrite": false,
  "write_audit": false,
  "date_str": "20260615"
}
```

Exit code: 0.

### With blocked URL

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url https://www.cninfo.com.cn/announcement/123.html --json
```

Provider status: `blocked`, error: `blocked_by_domain_filter`. Smoke returned empty and exit 0.

## URLs Tested

No real public community URLs for 中简科技 were available that are known to be safe and login-free. The first runtime dry-run is expected to be empty. All network behaviors are covered by unit tests with mocked fetch responses.

## Fresh Note Written?

No. No useful claims were found in runtime dry-run, so `--write` was not invoked. The write path is fully covered by focused tests.

## Claim Verification Counts

No fresh note was written, so no new claims entered `low_credit_claims` at runtime. The existing cached community note for 中简科技 (`20260615-雪球缓存社区claims.md`) still feeds the verification plan.

## Report Runtime Run?

No. The task specified running at most one `scripts/run_中简科技.py --fast-test` only if fresh claims were written and useful. Neither condition was met.

## Generated Files

None beyond the four new implementation/test files and this notes file. No `knowledge/` or `reports/` artifacts were created during dry-run.

## Deviations

- None from the allowed file list or design contract.
- The page-level negative-signal rejection is slightly stricter than per-sentence rejection; this aligns with the design intent of keeping news/SEO content out of fresh claims.
- Forum-only markers (e.g., `股吧`, `微博`) are accepted as community markers, but the negative-signal layer prevents most news articles that merely mention those platforms from passing.

## Blockers

None. Implementation is complete and all required tests pass.

## Remaining Follow-Up

If the user later provides 1–2 safe explicit community URLs for 中简科技, run:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url <url1> [--url <url2>] --json
```

Review claims; if useful:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url <url1> --write --overwrite --json
```

Then build the claim verification plan:

```bash
python3 -c "from scripts.utils.claim_verification import build_claim_verification_plan; print(build_claim_verification_plan('中简科技', 'knowledge'))"
```

Only if fresh claims are verified/support by high-credit evidence, optionally run one fast-test report.

## Codex Validation Addendum

Codex review found one implementation gap in the real URL fetch path:

- `_fetch_url()` originally called `build_provider_record()` without `stock_name` / `stock_code`.
- Because the claim gate requires stock name/code + community marker + predicate, real fetched pages could return `empty` even when they contained valid candidate sentences.

Fix applied:

- `scripts/smoke_fresh_social_claims.py`: `_fetch_url()` now accepts `stock_name` / `stock_code` and passes them into `build_provider_record()`.
- `_read_urls_sequentially()` now passes the stock context to `_fetch_url()`.
- `tests/reporter/test_fresh_social_claim_smoke_script.py`: added a mocked `urlopen` regression test proving fetched text can produce an `unverified_claim`.

Fresh verification:

```bash
python3 -m pytest tests/utils/test_fresh_social_claim_intake.py tests/reporter/test_fresh_social_claim_smoke_script.py tests/utils/test_claim_verification.py -q
# 96 passed
```

Smoke checks:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --json
# status=empty, claim_count=0, providers=[]

python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url https://www.cninfo.com.cn/announcement/123.html --json
# provider status=blocked, error=blocked_by_domain_filter
```

One explicit community URL was also tried as a dry-run:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url https://guba.eastmoney.com/list,300777.html --json
```

Result: provider `error`, `The read operation timed out`; no note was written. This is an external fetch availability issue, not a write or verification-plan issue.

## Direct Eastmoney Guba Follow-Up

Jina Reader timed out on the explicit Eastmoney guba list URL, but direct access to the same public list page was available locally.

Implementation follow-up:

- Added `--eastmoney-guba` to `scripts/smoke_fresh_social_claims.py`.
- The direct provider reads only `https://guba.eastmoney.com/list,<code>.html`.
- It parses list-page titles with the existing `EastmoneyParser`.
- It does not fetch post detail pages, comments, cookies, CDP, browser, or Xueqiu.
- It remains opt-in and dry-run by default.

Gate follow-up:

- Expanded verifiable predicates for low-credit business/shareholder claims:
  - `前十大股东`, `持股比例`, `股本`, `散户`, `竞争压力`, `护城河`, `绝对龙头`, `唯一实现`, `碳纤维`
- Added negative sentiment filters:
  - `狂跌`, `狂涨`, `神奇`

Fresh verification:

```bash
python3 -m pytest tests/utils/test_fresh_social_claim_intake.py tests/reporter/test_fresh_social_claim_smoke_script.py tests/utils/test_claim_verification.py -q
# 101 passed
```

Runtime:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --eastmoney-guba --write --overwrite --json
```

Result:

- Provider: `https://guba.eastmoney.com/list,300777.html`
- Status: `ok`
- Parsed posts: 20
- Written claims: 2
- Path: `knowledge/10-Stocks/中简科技/20260615-新鲜外部社媒claims.md`

Claim verification check:

- `high_credit_claims`: 11
- `low_credit_claims`: 20
- Fresh guba claims in `low_credit_claims`: 2
- Fresh claim metadata: `source_credit=30`, `claim_status=unverified_claim`, `verification_status=market_opinion`
- Fresh claim verification actions:
  - `unverified`, confidence 20
  - reason: no high or medium credit source with matching topic and terms

Structured risk signals:

- Total signals remain 2.
- Both come from pre-existing verified 中简科技 risk claims:
  - `业绩预期下调`
  - `盈利压力`
- The two fresh guba claims did not produce structured risk signals.
