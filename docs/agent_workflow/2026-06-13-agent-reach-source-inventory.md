# Agent-Reach Source Inventory: 黑芝麻智能 / HK02533

> Date: 2026-06-13
> Target stock: 黑芝麻智能
> Stock code: 02533 (HK)
> Status: Initial inventory for single-stock source expansion

## Inventory Criteria

A source is recorded only if it is:

- Official/public (company, exchange, regulator, or established finance publisher).
- Stable enough to fetch via existing `WebConnector` (Jina Reader) or `RSSConnector`.
- Directly relevant to 黑芝麻智能's investment thesis.
- Low risk of anti-scraping or login walls for the existing fetch path.

Rejected source types:

- Search result pages.
- Login/paywall pages.
- Social feeds requiring scraping.
- Xueqiu detail pages.
- Pages that are mostly navigation/portal noise unless they are official article pages and have passed local Jina fetch.

## Candidate Sources

| Stock | Source type | URL/feed | Domain | Why useful for this stock report | Risk | Recommendation |
|-------|-------------|----------|--------|----------------------------------|------|----------------|
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_10/972.html` | `blacksesame.com` | ISO 26262 ASIL-D certification for Huashan A2000U / A2000X — primary-source product/safety evidence | Jina Reader may include navigation noise; official seed calibration already applied | Keep; official seed URL |
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_9/977.html` | `blacksesame.com` | Partnership with SSE Technology (上实科技) and Hong Kong robotics platform | Navigation noise risk | Keep; official seed URL |
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_9/966.html` | `blacksesame.com` | Joins Li Auto Star Ring OS open ecosystem | Navigation noise risk | Keep; official seed URL |
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_9/964.html` | `blacksesame.com` | Platform-level cooperation with Dongfeng Motor and Wudang C1296 chip | Navigation noise risk | Keep; official seed URL |
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_9/961.html` | `blacksesame.com` | Strategic cooperation with Ruqi Mobility (如祺出行) for L4 autonomous driving | Navigation noise risk | Keep; official seed URL |
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_10/912.html` | `blacksesame.com` | Huashan A1000 wins "China Core" award and co-launches industry-finance initiative | Navigation noise risk | Keep; official seed URL |
| 黑芝麻智能 | Investor relations portal | `https://ir.blacksesame.com/announcement.html?lang=zh-cn` | `ir.blacksesame.com` | Official HK IPO announcements and circulars | Page is JS-heavy / navigation container; Jina Reader may return incomplete list or portal noise | Rejected for now — content not stable enough for deterministic fetch |
| 黑芝麻智能 | Investor relations portal | `https://ir.blacksesame.com/report.html?lang=zh-cn` | `ir.blacksesame.com` | Official financial reports | Same as above; portal container without stable per-report URLs in rendered content | Rejected for now |
| 黑芝麻智能 | HKEX disclosure page | `https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh` (with form POST for 02533) | `hkexnews.hk` | Primary exchange disclosure source | Requires form submission; no stable direct URL for a given announcement; JS-heavy | Rejected for automated fetch in this phase |
| 黑芝麻智能 | News center listing | `https://www.blacksesame.com/zh/news-center/` | `blacksesame.com` | Lists latest company news | Portal/listing page; individual article URLs are preferred | Rejected — use per-article URLs instead |
| 黑芝麻智能 | Curated finance RSS | (none identified) | — | Could provide third-party coverage if a stable, stock-specific feed exists | No suitable feed identified; generic feeds would require heavy filtering and risk unrelated articles | Rejected for this phase; revisit only if a stable feed with stock-specific filter terms is found |

## Source Count Summary

- Keep (official seed URLs): 6
- Rejected: 5
- Needs-test: 0
- RSS enabled: 0

## Config Implications

- The 6 existing `blacksesame.com` article URLs remain the Agent-Reach web source for 黑芝麻智能.
- No new URLs are added because the remaining candidate pages are either portal/noise pages or require form submission/JS interaction beyond the current `WebConnector` capability.
- `official_domains` remains `["blacksesame.com"]`.
- `rss_feeds` is not enabled for this stock in this phase.
- No `agent_reach` config is added to other stocks.

## Notes

- The existing 6 URLs were already validated in the prior official-source calibration run: all 6 scored 90–95, were marked `official_seed_url=True`, and produced compact audit JSON without full content.
- `ir.blacksesame.com` and HKEX pages were inspected but rejected due to portal/JS behavior. If direct per-announcement PDF/article URLs become available later, they can be re-evaluated in a future inventory update.
- This inventory is intentionally conservative. Source expansion for 黑芝麻智能 in this phase is primarily about documenting what is available and adding a smoke-validation path, rather than increasing URL count.
