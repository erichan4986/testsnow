# Social Source Inventory Runtime — 2026-06-15

## Scope

This is a read-only runtime inventory. It does **not** connect any social source to the report pipeline, does **not** write to `knowledge/`, and does **not** generate claim notes. The goal is to determine which social/community sources are suitable for future **fresh low-credit claim intake** for single A-share stocks, with the constraints:

- Recent (ideally ≤ 7 days)
- Stock-specific (by name or 6-digit code)
- Low-credit discussion (not official/announcement)
- Signal-to-noise ratio is controllable with the existing strict claim gate

Pilot stocks: **中简科技 / 300777** (primary) and **圣邦股份 / 300661** (secondary).

---

## Environment

### agent-reach doctor

```bash
$ agent-reach doctor
Traceback (most recent call last):
  File ".../agent-reach", line 3, in <module>
    from agent_reach.cli import main
ModuleNotFoundError: No module named 'agent_reach.cli'
```

- **Result**: `agent-reach` binary is installed, but the underlying `agent_reach.cli` module is missing.
- **Impact**: Agent-Reach CLI path is currently non-functional in this environment. Existing `agent-reach` integrations in code/cache were not exercised here.

### Available CLI list

| Tool | Status | Path |
|------|--------|------|
| `curl` | ✅ available | `/usr/bin/curl` |
| `yt-dlp` | ✅ available | `/Library/Frameworks/Python.framework/Versions/3.10/bin/yt-dlp` |
| `agent-reach` | ⚠️ broken (missing module) | `/Library/Frameworks/Python.framework/Versions/3.10/bin/agent-reach` |
| `xhs` | ❌ unavailable | not found |
| `twitter` / `x` / `twt` | ❌ unavailable | not found |
| `rdt` / `reddit` | ❌ unavailable | not found |
| `mcporter` | ❌ unavailable | not found |
| `douyin` / `tiktok` | ❌ unavailable | not found |
| `v2ex` | ❌ unavailable | not found |

### Python packages

No relevant social-media CLI packages are installed globally (`pip3 list | grep -iE "xhs|weibo|twitter|reddit|v2ex|douyin|bilibili"` returned nothing).

---

## Platform Matrix

| platform | status | auth_required | stock_specific | freshness | noise_level | suggested_role | notes |
|----------|--------|---------------|----------------|-----------|-------------|----------------|-------|
| 东方财富股吧 | `ready_for_claim_intake` | no | yes | recent | medium | primary low-credit social feed | 80 posts parsed per stock; strict gate passes ~1-5 claims per stock; some off-topic/peer-stock noise |
| 雪球 | `inventory_only` | no for list pages, but currently blocked/empty | yes | unknown/stale | medium | fallback when cache exists | Existing cache empty for 圣邦股份；Jina Reader probe returned empty/timed out; detail scraping remains forbidden |
| 微博 | `defer` | no for public pages, but network blocked/empty | partial | unknown | high | one-off inventory only | Jina Reader on `s.weibo.cn` and `m.weibo.cn` returned empty or timed out; high noise if accessible |
| Bilibili | `defer` | no for public videos (when accessible) | partial | unknown | medium | video analyst/interview metadata only | `yt-dlp` installed; Bilibili search URL unsupported; sample video returned HTTP 412 precondition failed |
| 小红书 | `defer` | yes (login/cookies) | partial | unknown | high | consumer sentiment only if explicitly requested | `xhs` CLI not installed; no login |
| 抖音 | `defer` | MCP/login required | partial | unknown | high | video-only, not text-rich | no CLI; do not install/login |
| Twitter/X | `defer` | yes (auth tokens) | low | unknown | high | not relevant for A-share Chinese names | CLI not installed; direct HTTP probe returned 000 |
| Reddit | `defer` | no for read if CLI installed | low | unknown | high | low relevance for Chinese single-stock | CLI not installed; direct HTTP probe returned 000 |
| V2EX | `defer` | no | low | unknown | medium | general tech community, rarely stock-specific | direct HTTP probe returned 000 |

---

## Findings By Platform

### 1. 东方财富股吧

- **Detection method**: Existing `scripts/smoke_fresh_social_claims.py --eastmoney-guba` (dry-run) + direct `requests` parse with `scripts/utils/parser.py`.
- **Result**: ✅ Works for both 中简科技 (300777) and 圣邦股份 (300661).
  - 中简科技: 80 posts parsed, 20 inspected, 1 claim passed strict gate.
  - 圣邦股份: 80 posts parsed, 20 inspected, 1 claim passed strict gate.
- **Sample titles (中简科技)**:
  - "马斯克的SpaceX又大涨利好中简科技，三、四期项目是战略性储备……"
  - "今天创业板指数大涨5.2%，我们的中简科技怒涨1.2%……"
  - "我看了这家公司的财务，为什么今年利润腰斩呢？"
  - "中简科技最近表现差，杨董事长该出手了！"
- **Sample titles (圣邦股份)**:
  - "明天突破124，有木有？"
  - "跪求明天低开，我错了，尾盘不该下车……"
  - "会到二百吗"
  - "明天高开要跑，低开更要跑"
- **Noise type**: Off-topic peer-stock mentions (e.g., 恒神股份，杰华特), emotional price cheering, low-info taunts.
- **Recommendation**: ✅ **Ready for fresh low-credit claim intake**. Use the existing list-page parser (no detail scraping), apply the strict claim gate and cap claims per provider.

### 2. 雪球

- **Detection method**:
  - Inspected existing cache `data/raw/xueqiu_data_20260605_圣邦股份.json`.
  - Jina Reader probe on `https://xueqiu.com/S/SZ300777` and `https://xueqiu.com/query/stockSearch.json?code=300777`.
  - Checked report input JSONs for recent runs.
- **Result**:
  - Existing 圣邦股份 cache: `posts: []` (empty).
  - 中简科技 report input: 0 Xueqiu items.
  - Jina Reader returned empty body (HTTP 200 with no content) or timed out.
- **Noise type**: N/A — currently inaccessible in this environment.
- **Recommendation**: `inventory_only`. Do not rely on live Xueqiu fetches. Use only when pre-existing cache is populated by other means. Detail-page scraping remains out of scope.

### 3. 微博

- **Detection method**: Jina Reader on `https://s.weibo.com/weibo?q=中简科技300777` and `https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D中简科技`.
- **Result**: Empty body or SSL handshake timeout. No usable content retrieved.
- **Noise type**: Expected high noise — celebrity/viral content, SEO reposts, vague market commentary.
- **Recommendation**: `defer`. Even if accessible, search results would require heavy filtering to be stock-specific and recent enough.

### 4. Bilibili

- **Detection method**:
  - `yt-dlp` availability check: installed.
  - `yt-dlp --flat-playlist --dump-single-json` on Bilibili search URL.
  - `yt-dlp --dump-json` on a sample Bilibili video URL.
- **Result**:
  - Search URL (`search.bilibili.com`) unsupported by yt-dlp.
  - Sample video URL returned `HTTP Error 412: Precondition Failed`.
- **Noise type**: Video-only, titles may be clickbait, need transcript extraction.
- **Recommendation**: `defer`. Tool exists but Bilibili is rate-limiting/authenticating public requests. Only useful if a known, relevant analyst video URL is provided.

### 5. 小红书 / 抖音

- **Detection method**: `which xhs`, `which douyin`, `which tiktok`; `npm list -g xhs-cli` (empty); pip search (no relevant packages).
- **Result**: No CLI installed. Both platforms require login/cookies/MCP for useful access.
- **Noise type**: High lifestyle/consumer noise; stock-specific signal rare.
- **Recommendation**: `defer`. Do not install new dependencies or perform login in this repo.

### 6. Twitter/X / Reddit / V2EX

- **Detection method**: `which twitter/x/rdt/reddit/v2ex`; direct `curl` HTTP probe to public endpoints.
- **Result**:
  - No CLI installed.
  - Direct HTTP probes returned `000` (connection failure/timeout).
- **Noise type**: English/General tech discussion; low A-share Chinese stock specificity.
- **Recommendation**: `defer` / `unavailable`. Not suitable as default sources for 中简科技/圣邦股份 low-credit claim intake.

---

## Recommended Next Step

### Priority 1: ready_for_claim_intake

**东方财富股吧** is the only source that is immediately usable today:

- Uses existing, committed code (`fresh_social_claim_intake.py`, `smoke_fresh_social_claims.py`, `parser.py`).
- No authentication.
- Stock-specific by URL.
- Returns recent posts.
- Strict claim gate keeps output bounded (~1 claim per 20-80 posts in this run).

Suggested integration pattern (for a future task, not done here):

1. Add `eastmoney_guba=True` to the fresh-social smoke step in the report pipeline.
2. Keep caps: `DEFAULT_MAX_RAW_ITEMS=20`, `DEFAULT_MAX_CLAIMS_PER_PROVIDER=5`, `DEFAULT_MAX_CLAIMS=10`.
3. Tag claims as `source_type: social_discussion`, `source_credit: 35`, `verification_status: market_opinion`.
4. Route through `claim_verification` using high-credit announcements before any scoring or report use.

### Priority 2: inventory_only

**雪球** should be monitored. If a future run populates `data/raw/xueqiu_data_YYYYMMDD_<stock>.json` with non-empty posts, the existing cache-based path can be used. Do not add live scraping or CDP detail fetches without explicit user authorization.

### Priority 3: defer

微博, Bilibili, 小红书, 抖音, Twitter/X, Reddit, V2EX. Re-evaluate only if:

- A concrete stock-specific URL or search query is provided by the user.
- Authentication is already configured outside the repo.
- The source demonstrates reliably better signal-to-noise than 股吧 for the target stock.

---

## Stop Conditions / Risks

| Risk | Mitigation in this run | Future guardrail |
|------|------------------------|------------------|
| Platform rate-limit / anti-bot | Stopped after 1-2 probes; no retries | Keep per-call timeout ≤15s, global budget ≤60s, max 1 retry |
| Login/credential requirement | Marked `defer`; no login performed | Never commit credentials; use env-only auth if ever enabled |
| High noise / off-topic posts | Strict claim gate already filters most posts | Keep claim caps and require high-credit verification |
| SEO/news reposts masquerading as social discussion | Domain filter blocks `stcn.com`, `cls.cn`, `gelonghui.com`, etc. | Maintain blocklist and source-type tagging |
| Xueqiu detail scraping policy | Not attempted | Continue to forbid detail-page scraping and CDP unless user explicitly authorizes logged-in browser with rate limits |
| Agent-Reach CLI broken | Recorded; did not block inventory | Fix or remove broken CLI dependency before relying on Agent-Reach as a fetch path |

---

## Runtime Output Files

Only this inventory document was created/updated. No source code, config, tests, prompts, knowledge notes, or report artifacts were modified.

- `docs/agent_workflow/2026-06-15-social-source-inventory-runtime.md` (this file)
