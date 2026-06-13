# Agent-Reach Official URL Smoke Test Notes

## URL

https://www.blacksesame.com/zh/list_10/972.html

## Goal

Verify whether Phase 0B Web connector + quality gate can fetch and keep/demote an official Black Sesame article.

## Pipeline Run

### Query

- `agent_reach_enabled`: True
- `search_queries`: `[{'query': 'web_read', 'target_platforms': ['web'], 'rationale': '读取已知网页', 'urls': [URL], 'timeout': 15}]`

### Fetch

- `agent_reach_status`: `ok`
- Items fetched: 1
- Warnings: none

Fetched item:

| Field | Value |
| --- | --- |
| title | Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 |
| source_platform | AgentReach(web) |
| content length | 25,924 chars |
| url | https://www.blacksesame.com/zh/list_10/972.html |

### Quality Gate

- `agent_reach_quality_status`: `ok`
- Summary: keep=0, demote=0, discard=1, total=1

**Quality result for the single item:**

| Metric | Value |
| --- | --- |
| action | discard |
| score | 29 |
| reasons | 包含股票名称; 含 4 个业务关键词; 有URL; 含 2 类数据指标; 含 10 个日期; 标题充实; 内容较长; 标题+内容完整; **疑似门户/导航页，内容价值低** |

**Raw score before portal penalty**: ~66 (keep threshold for web is 50).

**Portal detection triggered because**:
- Link density: 356 links across 157 non-empty lines → ratio 2.27 (> 0.5 threshold)
- Portal keywords found: `首页`, `网站地图`, `更多` (3 keywords, >= 2 threshold)
- `_is_portal_page()` returned True (2+ signals matched)

**Portal penalty applied**: -15, capped at `demote_threshold - 1 = 29`.

### Root Cause

Jina Reader returned the **full page HTML rendered as markdown**, including:
- Top navigation bar with 20+ site links (`首页`, `公司信息`, `基本介绍`, etc.)
- Footer with site-map links (`网站地图`, `知识产权声明`)
- Contact sidebar (`联系我们`, `商务合作`, `加入我们`, `媒体资讯`)

The article body itself is high-quality and data-rich, but it is buried inside page chrome that triggers portal heuristics.

### Renderer

- Output path: `/tmp/agent_reach_official_url_smoke/agent_reach_section.md`
- Rendered length: 0 chars
- Readable: N/A — no keep or demote items to display (single item was discarded)

The renderer correctly returned an empty string when there are no keep/demote items.

## Assessment

| Question | Result |
| --- | --- |
| Did the Web connector fetch the URL? | **Yes** — fetch status `ok`, content retrieved (25,924 chars). |
| Did the quality gate score it correctly on substance? | **Yes** — raw score ~66 would have been `keep` based on rich content, stock name match, dates, data metrics. |
| Did portal detection behave as designed? | **Yes, but with a false positive** — the heuristic correctly identifies the Jina output as portal-like because Jina includes the full page navigation chrome. |
| Is the renderer readable when items exist? | **Not tested** — no keep/demote items survived to render. Prior validation confirmed renderer works. |

## Follow-Up

- **Jina Reader returns full-page markdown on official corporate sites**, not article-extracted content. This causes portal detection false positives on otherwise high-quality pages.
- Options to consider (outside Phase 0B scope):
  1. Add a whitelist or source-trust bonus for known official domains (`blacksesame.com`, investor relations sites, etc.).
  2. Strip common navigation/footer patterns before portal detection.
  3. Use an alternative extraction service that returns article-body only.
  4. Relax portal penalty cap for URLs explicitly provided by the user (they already vouched for the URL).
