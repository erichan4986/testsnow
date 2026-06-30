# Social Source Inventory

Date: 2026-06-15

Scope: low-credit claim source inventory only. Nothing here is wired into report generation, scoring, risk scoring, EV, technical analysis, LLM synthesis, or final recommendations.

## Local Tool Availability

Checked from `/Users/erichan/testsnow` on 2026-06-15.

| Tool | Local status | Notes |
|------|--------------|-------|
| `agent-reach` | installed but broken | `agent-reach doctor` fails with `ModuleNotFoundError: No module named 'agent_reach.cli'`. |
| `curl` | available | Can be used for public web/Jina/V2EX style reads, subject to network access. |
| `yt-dlp` | available | Can inspect Bilibili video metadata/subtitles if a relevant URL is known. |
| `xhs` | unavailable | Xiaohongshu requires separate CLI install and login; do not force in this repo. |
| `twitter` | unavailable | Twitter/X requires CLI install and auth tokens; not suitable as default. |
| `rdt` | unavailable | Reddit CLI unavailable; Reddit is generally low relevance for A/H-share Chinese names. |
| `mcporter` | unavailable | Exa/web-reader MCP commands unavailable from shell in this environment. |
| `gh` | unavailable | Not relevant for social claim intake. |

## Source Candidates

| Source | Availability | Auth requirement | A/H-share relevance | Status | Recommendation |
|--------|--------------|------------------|---------------------|--------|----------------|
| Local Xueqiu raw cache | available | none | high | `keep_now` | Primary low-credit claim source. Already feeds `smoke_cached_community_claims.py`. |
| Local knowledge posts | available | none | high | `keep_now` | Fallback when raw cache is empty. Now supported by default fallback. |
| Weibo via Jina/web URLs | possible | none for public pages, but brittle | medium | `safe_smoke_only` | Use only as one-off inventory when concrete URLs or search results exist; do not pipeline yet. |
| Bilibili via `yt-dlp` | tool available | no login for many public videos; may hit 412 | low/medium | `safe_smoke_only` | Useful only for specific analyst/interview videos; not broad stock search. |
| Xiaohongshu | not installed | login/cookies required | low/medium | `needs_login` | Do not install/login by default. Consider only if user explicitly wants consumer sentiment. |
| Twitter/X | not installed | auth tokens required | low for A-share Chinese names | `needs_login` | Not a default source; avoid credentials in repo. |
| Reddit | not installed | no login for search/read if CLI installed | low | `irrelevant_for_now` | Low relevance for Chinese single-stock reports. |
| V2EX public API | possible via `curl` | none | low | `irrelevant_for_now` | General tech community; unlikely stock-specific enough. |
| Douyin | unavailable | MCP setup needed, no login for parsing URLs | low/medium | `defer` | Only useful for known video links; do not configure in this sprint. |

## Recommended Execution Order

1. Keep using local Xueqiu raw cache and local `knowledge/.../posts` as the low-credit claim pool.
2. Treat all generated community claims as:
   - `source_type: social_discussion`
   - `source_credit: 35`
   - `verification_status: market_opinion`
   - `claim_status: unverified_claim`
3. Let high-credit official evidence verify or reject these claims through `claim_verification`.
4. Only after the local claim pool is stable, run one-off social source smoke tests for Weibo/Bilibili when concrete stock-specific URLs are available.
5. Do not add social adapters to Source Intake or report assembly until a source consistently returns useful, stock-specific, text-rich records.

## Current Sprint Result

The local low-credit claim path is already useful:

| Stock | Source used | Low-credit claim note | Claim count |
|-------|-------------|-----------------------|-------------|
| 黑芝麻智能 | `data/raw/xueqiu_data_20260602_黑芝麻智能.json` | `knowledge/10-Stocks/黑芝麻智能/20260615-雪球缓存社区claims.md` | 30 |
| 中简科技 | `knowledge/10-Stocks/中简科技/posts` | `knowledge/10-Stocks/中简科技/20260615-雪球缓存社区claims.md` | 6 |
| 圣邦股份 | `knowledge/10-Stocks/圣邦股份/posts` | `knowledge/10-Stocks/圣邦股份/20260615-雪球缓存社区claims.md` | 2 |

The strongest validation case is 中简科技:

- low-credit claims: 18
- high-credit claims: 11
- verified: 6
- structured risk signals:
  - `业绩预期下调` verified, confidence 84
  - `盈利压力` verified, confidence 84

This confirms the desired trust chain:

```text
low-credit community claim -> high-credit announcement verification -> structured risk signal
```

## Blockers / Risks

- `agent-reach doctor` is currently broken locally due to missing `agent_reach.cli`.
- Social channels that require login/cookies should not be forced from Codex or committed to repo config.
- Broad social search is noisy and can easily create unverified claim floods; keep caps and require high-credit verification before any scoring use.
- Xueqiu detail scraping remains out of scope unless the user explicitly authorizes CDP with logged-in browser and rate limits.
