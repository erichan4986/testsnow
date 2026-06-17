# Fresh Social Low-Credit Intake Design

Date: 2026-06-15

## Goal

Probe fresh, low-credit social/community information for one stock without relying only on pre-filtered Xueqiu JSON caches.

The purpose is to test real-world noise and freshness:

- new/less-filtered social or community snippets
- weakly structured pages
- duplicates
- sentiment-only noise
- stale or irrelevant mentions
- anti-bot / access failures

All useful outputs remain low-credit `unverified_claim` material. Fresh social claims must not directly affect scoring, EV, technical analysis, LLM synthesis, citations, or final recommendations. If a fresh low-credit claim is later independently verified or supported by higher-credit evidence, the existing claim-risk bridge may convert it into a structured risk signal; that is an intentional downstream behavior and must be visible in runtime validation.

## Pilot Stock

Use **中简科技 / 300777** first.

Reason:

- high-credit cninfo evidence notes already exist
- the existing claim verification path has already verified community claims for 中简科技
- failures are easier to diagnose than 黑芝麻智能, which currently lacks comparable high-credit evidence notes

## Non-Goals

- Do not fix the whole `agent-reach` install in this sprint.
- Do not force installation/login for Xiaohongshu, Twitter, Reddit, or other CLIs.
- Do not store cookies or credentials.
- Do not scrape Xueqiu detail pages.
- Do not use logged-in Chrome/CDP.
- Do not refresh Zhihu collection.
- Do not change `KnowledgeSynthesizer` prompts.
- Do not wire fresh social intake into Source Intake, Agent-Reach, report assembly, EV, technical analysis, LLM synthesis, or final recommendation.
- Do not directly score fresh social text. Risk scoring may only be affected later through the existing `claim_verification -> structured_risk_signals` path after high/medium-credit evidence independently verifies or supports the claim.
- Do not write report-visible sections.

## Available Local Capabilities

Current inventory shows:

- `curl`: available
- `yt-dlp`: available
- `agent-reach`: command exists but broken (`ModuleNotFoundError: agent_reach.cli`)
- `xhs`, `twitter`, `rdt`, `mcporter`: unavailable

So this sprint should not depend on the unified `agent-reach` CLI.

## Proposed Implementation

Add a small isolated smoke path:

- `scripts/utils/fresh_social_claim_intake.py`
- `scripts/smoke_fresh_social_claims.py`
- tests for helper and smoke script

The helper should support provider-style records so we can add/disable sources safely.

### Provider 1: Bounded Known-URL Reader via Jina Reader

Use a small explicit URL list for the pilot. Do not use open web search as a provider.

Allowed reader endpoint:

```text
https://r.jina.ai/<target-url>
```

Candidate URL policy:

- URLs must be explicitly configured in the smoke command or a small in-script pilot list for 中简科技.
- URLs should be community-like pages, not news / official / SEO pages.
- Examples of acceptable classes:
  - public stock forum or discussion pages
  - public Weibo search/result pages if readable without login
  - public Snowball / stock discussion pages only if accessible without logged-in Chrome and without detail scraping
- Examples of rejected classes:
  - Eastmoney news pages
  - cninfo announcements
  - broker research pages
  - generic SEO aggregator pages
  - pages already covered by Source Intake high/medium-credit adapters

If no explicit URLs are available, the provider returns `empty` and the smoke still succeeds.

### Provider 2: Optional User-Provided URLs

The smoke script may accept `--url` repeatedly:

```bash
python3 scripts/smoke_fresh_social_claims.py --stock 中简科技 --code 300777 --url <community-url> --json
```

The same Jina Reader path is used. This supports user-curated fresh social/community URLs without open search.

Limits for all URL reads:

- max URLs: 5
- timeout: short
- max chars per page: capped
- no cookies
- no browser
- no Xueqiu logged-in detail scraping

Bilibili / `yt-dlp` is deferred to a separate social inventory smoke. It is not a claim intake provider in this sprint.

## Claim Extraction Gate

Fresh raw items must pass stricter rules before becoming claim candidates:

- stock name or code must appear
- raw record must be from an allowed community-like URL class or contain community-like markers
- require at least one community-style marker, such as:
  - first-person / opinion terms: `我认为`, `我觉得`, `个人`, `看法`, `猜`, `可能`, `估计`, `担心`, `有观点`
  - forum/post terms: `帖子`, `评论`, `雪球`, `股吧`, `微博`, `讨论`, `社区`
- text must contain verifiable predicates such as:
  - 收入下降 / 营收下降
  - 研发费用增长
  - 订单 / 客户 / 发货 / 需求阶段性减少
  - 价格下调 / 毛利率承压
  - 减持 / 解禁 / 资金流出
- skip pure sentiment:
  - 看好 / 起飞 / 垃圾 / 庄家 / 韭菜 / 玄学 / 情绪发泄
- skip news / SEO / aggregator-like snippets, including:
  - `点击阅读全文`, `查看更多`, `相关股票`, `新浪财经`, `证券时报`, `东方财富网`, `每经`, `格隆汇`
  - `公告编号`, `证券代码`, `本公司及董事会`, `PDF`, `研报`
  - pages whose URL/domain is official/news/research rather than community-like
- skip pure technical commentary unless it contains a verifiable business/event claim
- deduplicate by normalized claim text
- cap:
- max raw items per provider: 20
  - max claims per provider: 5
  - max total claims: 10

Provider failure and rate-limit handling:

- sequential calls only
- per-call timeout: 15 seconds
- global budget: 60 seconds
- retry count: at most 1
- status enum: `ok`, `empty`, `error`, `rate_limited`, `blocked`
- 429 / 5xx should not crash the smoke; record provider status and continue

## Output Contract

Default mode is dry-run and writes no knowledge notes.

Dry-run output:

- JSON summary to stdout
- optional audit JSON under `reports/` only if `--write-audit` is passed

Write mode:

- only with `--write`
- writes one note:
  - `knowledge/10-Stocks/中简科技/<YYYYMMDD>-新鲜外部社媒claims.md`

This filename must not collide with cached community notes such as `<YYYYMMDD>-雪球缓存社区claims.md`.

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

Every claim remains `unverified_claim`. The script must never produce `confirmed_fact`.

## Validation

After dry-run/write:

1. Run focused tests.
2. Build claim verification plan for 中简科技.
3. Confirm fresh social note enters `low_credit_claims`.
4. Confirm matching high-credit official evidence can verify/support claims if applicable.
5. Run at most one 中简科技 fast-test report if the fresh claims are useful.

Do not run all three reports in this sprint.

## Required Tests

If implementation proceeds:

- module import does not access network or import heavy optional CLIs
- dry-run is default and writes nothing
- `--write` is required for knowledge note output
- raw search/page records are capped and deduplicated
- pure sentiment snippets are skipped
- business/event snippets become `unverified_claim`
- generated note uses `source_credit: 30`
- generated note never contains `confirmed_fact`
- generated note does not contain numbered citations `[^n]` / `[n]`
- provider failures are recorded but do not crash the smoke
- SEO/news snippets are rejected by the community-like gate
- duplicate claims are deduplicated across providers
- fresh note filename does not collide with cached community claim notes

## Acceptance Criteria

- Fresh social smoke can run for 中简科技 in dry-run mode.
- It records provider status for bounded URL reader sources.
- If useful claims are found, `--write` produces one low-credit note.
- Claim verification can read the note as low-credit claims.
- No report/scoring/risk/LLM/pipeline code is modified.
- No credentials, cookies, Xueqiu detail scraping, CDP, or browser automation are used.

## Design Delta After Round 1

Round 1 feedback identified two blockers:

1. Open Jina Search was too noisy and unbounded.
2. The extraction gate was not strict enough for fresh web snippets.

Accepted changes:

- Removed open search (`s.jina.ai`) from the claim intake path.
- Replaced it with bounded, explicit URL reading through Jina Reader (`r.jina.ai`).
- Deferred Bilibili / `yt-dlp` to separate inventory, not claim intake.
- Added community-like positive markers and news/SEO/official negative filters.
- Made risk impact explicit: fresh claims do not directly score, but verified fresh claims can later become structured risk signals through the existing claim verification bridge.
- Changed output filename to `<YYYYMMDD>-新鲜外部社媒claims.md` to avoid collision with cached Xueqiu notes.

## Round 2 Feedback

- **Status**: Ready to implement
- **R2 Needed**: No
- **Remaining blocker**: None

### Blocker resolution

1. **Open Jina Search removed — resolved.**
   - Provider 1 is now a bounded, explicit URL reader using `https://r.jina.ai/<target-url>`.
   - No open web search (`s.jina.ai`) appears anywhere in the claim intake path.
   - The design accepts that if no explicit community URLs are available the provider returns `empty` and the smoke still succeeds, which is a safe, reproducible default.

2. **Claim extraction gate tightened — resolved.**
   - Added positive community-style markers (`我认为`, `我觉得`, `猜`, `可能`, `帖子`, `股吧`, `雪球`, etc.).
   - Added explicit negative signals for SEO/news/official snippets (`点击阅读全文`, `查看更多`, `相关股票`, `新浪财经`, `公告编号`, `证券代码`, `PDF`, `研报`, etc.).
   - Retained stock-name/code requirement and verifiable business/event predicates.
   - Added caps (max raw items 20, max claims 5/provider, max total 10) and deduplication.

### Required task adjustments

1. **Implementation must treat the gate as a two-pass AND filter.**
   - A snippet must satisfy **all** of:
     - stock name or code present;
     - at least one community-style marker or known community domain;
     - at least one verifiable business/event predicate;
     - **no** strong negative news/SEO/official signal.
   - Forum-name markers (`雪球`, `股吧`, `微博`) can appear in news/SEO text, so they must not alone override negative-signal rejection.

2. **URL-level rejection must be implemented, not only text-level.**
   - If the input URL's domain or path pattern matches official/news/research/SEO aggregators, the provider should mark it `blocked` or `empty` before Jina Reader is even called.
   - This prevents redundant network traffic and keeps the provider contract honest.

3. **Concrete pilot URL list for 中简科技.**
   - The design is correct to allow empty results, but the first implementation should include at least one or two concrete, publicly accessible community URLs for 中简科技 (e.g., a known Eastmoney 股吧 list page, a specific Snowball discussion page if reachable without login, or a Weibo search result URL).
   - If no reliable URL is known at implementation time, document that the first dry-run is expected to be empty and add the URLs only after manual verification.

4. **Defensive `claim_status` enforcement.**
   - The writer must hardcode `claim_status: unverified_claim` in both note frontmatter and every claim entry.
   - Add an assertion in the smoke/serialization path that aborts if any claim would be emitted as `confirmed_fact`.

5. **Rate-limit/failure handling.**
   - Confirm per-call timeout 15s, global budget 60s, sequential calls, retry ≤1, and status enum (`ok`, `empty`, `error`, `rate_limited`, `blocked`) in implementation.
   - 429 and 5xx must be caught and recorded; the smoke must not crash.

6. **Verified-claims risk impact remains explicit.**
   - The current wording in Goal and Non-Goals correctly states that verified fresh claims may flow into structured risk signals through the existing claim-risk bridge.
   - Do not weaken this language during implementation.

### Missing tests that must be in the task

- Module import does not access network or import heavy optional CLIs.
- Dry-run is default and writes nothing to `knowledge/`.
- `--write` is required for knowledge note output; `--write-audit` only writes under `reports/`.
- `source_credit: 30` in generated note forces placement in `low_credit_claims`.
- Generated note and every claim inside it use `claim_status: unverified_claim`; no `confirmed_fact` is produced.
- Generated claims contain no numbered citations (`[^n]` / `[n]`).
- Positive gate requires community-style marker; negative gate rejects SEO/news/official snippets even if stock name is present.
- URL-level domain filter rejects official/news/research URLs.
- Pure sentiment snippets (`起飞`, `垃圾`, `庄家`, `韭菜`) are skipped.
- Duplicate claims are deduplicated across providers.
- Provider failure (timeout, 429, 5xx, empty response) returns a status entry and does not crash the smoke.
- Caps are enforced: max raw items 20, max claims 5/provider, max total 10.
- Fresh note filename (`<YYYYMMDD>-新鲜外部社媒claims.md`) does not collide with cached community notes.
- Jina Reader returning very short/empty/placeholder text is treated as `empty`, not as a valid claim.

### Final recommendation

The two Round 1 blockers are resolved. The design is now a bounded, low-risk pilot for **中简科技 only** with safe defaults (dry-run, explicit `--write`, low source credit, strict gate, rate limits, and no browser/credentials).

Proceed to implementation with the adjustments above. After implementation:

1. Run focused tests.
2. Run dry-run for 中简科技 and review JSON/provider status.
3. If quality is acceptable, run with `--write`.
4. Build claim verification plan for 中简科技 and confirm fresh claims enter `low_credit_claims`.
5. Run at most one 中简科技 fast-test report if useful claims are found.
6. Do not expand to other stocks in this sprint.

## Round 1 Feedback

- **Status**: Must-fix before task
- **R2 Needed**: Yes

### Findings by severity

#### Critical / Must-fix

1. **Jina Search endpoint is not a safe or reliable source for fresh low-credit claims.**
   - `https://s.jina.ai/<query>` performs an unauthenticated web search and may return snippets from paywalled, SEO-spam, or unrelated pages. It is not designed for bounded, stock-specific Chinese community content.
   - For A/H-share Chinese names, the signal-to-noise ratio will be very low; likely results include Eastmoney reposts, robot-generated summary pages, and stock-bar scrapers rather than genuine community discussion.
   - Treating this as a "provider" gives the design a false sense of modularity; the real risk is that raw search results are easy to misclassify as community claims.

2. **The design does not solve the stated problem as clearly as it claims.**
   - The sprint goal is to test "real-world noise and freshness" without relying only on pre-filtered Xueqiu JSON caches. However, the proposed Provider 1 (Jina Search) and Provider 2 (Jina Reader) will mostly return the same web content that Source Intake already processes (Eastmoney news, cninfo, SEO pages).
   - There is no concrete plan to obtain genuinely fresh community snippets from 雪球股吧 / 东方财富股吧 / 微博等. Jina Search is not a substitute for a community API or a logged-in community feed.
   - If the goal is simply to read arbitrary URLs through Jina Reader, that capability already exists inside `a_stock_source_intake.py` for high-credit detail reads. Reusing it for low-credit social material needs a much stronger justification.

3. **Risk of accidentally entering scoring/risk via `claim_risk_signal` skill.**
   - The design states that fresh social output should not affect scoring, risk, EV, technical, LLM synthesis, or final recommendations.
   - However, `claim_risk_signal_skill` reads **all** low-credit claims in `knowledge/10-Stocks/<stock>/*.md` (excluding `MOC.md`) and converts verified/supported ones into `structured_risk_signals`, which `risk_score_section` then adds to the risk table when confidence >= 60.
   - If `--write` produces a fresh social note with claims that happen to match high-credit evidence topics, those claims will be verified and become scored risk factors, exactly like the existing 中简科技 cached-community claims did.
   - This is not necessarily wrong, but the design must be honest: **fresh social claims that get verified will flow into risk scoring**. The non-goal language should be revised from "nothing affects scoring" to "fresh social claims remain low-credit and only affect risk scoring if independently verified by high-credit evidence."

#### High / Serious

4. **Source credit 30 is appropriate, but the output contract is not robust against accidental escalation.**
   - `source_credit: 30` is safely below the 55 medium-credit threshold, so fresh social claims can never verify other claims.
   - However, `_build_claim_candidate` in `claim_verification.py` currently sets `claim_status = str(meta.get("claim_status") or "fact_candidate").strip()` for evidence claims; for social claims it falls back to whatever the frontmatter says. The design must guarantee that the generated note always uses `claim_status: unverified_claim` and never lets a downstream bug or malformed writer emit `confirmed_fact`.
   - `verification_status: market_opinion` and `source_type: social_discussion` are correct.

5. **Claim extraction gate is too permissive for web search snippets.**
   - The proposed predicate list (`收入下降`, `研发费用增长`, `订单`, `客户`, `发货`, `需求阶段性减少`, `价格下调`, `毛利率承压`, `减持`, etc.) overlaps heavily with the high-credit evidence vocabulary used by Source Intake.
   - This increases the chance that a generic Eastmoney/SEO snippet will be turned into a low-credit claim that then gets verified by a matching high-credit announcement, amplifying noise rather than testing it.
   - The gate needs stronger **negative signals**: exclude snippets that contain SEO boilerplate, "点击阅读全文", "新浪财经", "查看更多", "相关股票", or that do not contain a stock-specific reference.
   - The gate should also require that the snippet explicitly looks like a community opinion (e.g., contains first-person markers, hedging words, or is from a known community domain) rather than looking like a news headline.

6. **Bilibili provider is speculative and adds scope creep.**
   - `yt-dlp` can fetch metadata/subtitles, but finding relevant Bilibili videos for a specific A-share name requires either search (which returns mostly unrelated content) or a human-curated URL list.
   - The design says "Only if a Bilibili URL is discovered or explicitly provided." Discovery from Jina Search will be noisy and infrequent.
   - Recommendation: drop Bilibili from this sprint, or restrict it to a one-off inventory smoke with hardcoded URLs, not a general claim provider.

#### Medium / Suggestions

7. **Pilot scope: 中简科技 only is the right choice.**
   - The design correctly limits the pilot to 中简科技 because it already has high-credit evidence notes and a working claim verification path.
   - This should be strictly enforced: do not expand to 黑芝麻智能 or 圣邦股份 until the smoke path, provider status logging, and claim quality gates are proven.

8. **Dry-run default and explicit `--write` are correct and safe.**
   - The default dry-run mode and JSON-only output keep the repo safe until a human reviews the claims.
   - `--write-audit` under `reports/` is also a good safety mechanism because `reports/*.json` is gitignored.

9. **Missing explicit anti-bot / rate-limit handling.**
   - The design mentions "If the endpoint fails, returns irrelevant content, or is blocked, record provider status" but does not specify concrete rate-limit behavior.
   - Jina's free endpoints are known to rate-limit aggressively. The implementation must include:
     - per-call timeout (e.g., 15s)
     - global timeout budget (e.g., 60s total)
     - sequential calls, not parallel
     - retry count <= 1
     - cooldown / backoff on 429 or 5xx
     - user-agent header

10. **Output note filename should clearly indicate fresh/external provenance.**
    - `knowledge/10-Stocks/中简科技/<YYYYMMDD>-新鲜社媒claims.md` is fine, but consider adding a `fresh` or `external` token so it is visually distinct from cached notes.
    - The existing cached note is `20260615-雪球缓存社区claims.md`; the new one should not overwrite it (different date or different name suffix).

### Required task adjustments

1. **Revise Provider 1 to be a bounded, known-URL smoke, not an open web search.**
   - Replace Jina Search with a small, explicit list of candidate community URLs/pages for 中简科技 (e.g., Eastmoney 股吧 list page, a specific 雪球 page if already publicly accessible, a known Weibo search result URL).
   - Read those URLs through Jina Reader only.
   - This removes the unbounded search noise and makes the test reproducible.

2. **Add a strict "community-like" filter before claim extraction.**
   - Require at least one community-style marker or first-person/hedging language.
   - Reject news-like, SEO-like, or headline-like snippets.
   - Maintain the stock-name/code requirement.

3. **Explicitly address the verified-claims-enter-risk-scoring consequence.**
   - Update Non-Goals/Goals to say: fresh social claims are low-credit inputs; if high-credit evidence verifies them, they may flow into structured risk signals exactly like cached community claims.
   - This keeps the design honest and prevents surprise during runtime validation.

4. **Drop or defer Provider 3 (Bilibili).**
   - Unless a concrete, relevant Bilibili URL is already known for 中简科技, exclude it from implementation.
   - If kept, move it to a separate one-off inventory script under `scripts/smoke_social_inventory.py`, not the claim intake path.

5. **Specify rate-limit and failure handling in the design.**
   - Add concrete timeouts, retry limits, sequential call policy, and status enums (`ok`, `empty`, `error`, `rate_limited`, `blocked`).

6. **Clarify the relationship to existing cached community claims.**
   - The fresh smoke note must use a different filename suffix from the cached note.
   - Both notes will be read by `build_claim_verification_plan`; the implementation must be prepared for duplicate claims and deduplicate or handle them gracefully.

### Missing tests

Before implementation:

- Test that `source_credit: 30` notes are always placed in `low_credit_claims`.
- Test that fresh social notes with `claim_status: unverified_claim` never produce `confirmed_fact` candidates.
- Test that provider failure (timeout, 429, empty) does not crash the smoke and returns `status` in JSON.
- Test that SEO/news snippets are rejected by the community-like gate.
- Test that pure sentiment snippets (`起飞`, `垃圾`, `庄家`) are skipped.
- Test that duplicate claims are deduplicated across providers.
- Test that fresh note filename does not collide with cached note.
- Test that no `[^n]` or `[n]` citation markers appear in generated claims.

### Recommended execution order

1. Rewrite Provider 1 as bounded Jina Reader over a small, explicit URL list for 中简科技.
2. Drop Provider 3.
3. Implement `fresh_social_claim_intake.py` with strict community-like gate and rate-limit handling.
4. Implement `smoke_fresh_social_claims.py` default dry-run + `--write` + `--write-audit`.
5. Add focused tests for helper and smoke script.
6. Dry-run for 中简科技; review JSON output and provider status.
7. If quality is acceptable, `--write` the note.
8. Run `build_claim_verification_plan` for 中简科技; confirm new claims enter `low_credit_claims`.
9. Run at most one 中简科技 fast-test report; confirm any verified fresh claims appear in structured risk signals.
10. Do not expand to other stocks in this sprint.

### Blocker

- **Open web search via Jina Search as Provider 1 is a blocker**: it is unbounded, low-signal, and likely to return SEO/news spam that the existing Source Intake already covers.
- **Claim extraction gate is insufficiently anti-noise** for web content and must be tightened before writing claims to `knowledge/`.

After addressing these two items, the sprint can proceed as a bounded pilot for 中简科技 only.
