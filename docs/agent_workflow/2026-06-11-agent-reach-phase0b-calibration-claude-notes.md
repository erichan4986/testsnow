# Agent-Reach Phase 0B Calibration Design Notes

Date: 2026-06-11
Author: User Review + Claude
Scope: Design review only. No code changes in this task.

## Validation Findings Summary

Phase 0 runtime validation (see `2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md`) confirmed the connector architecture works, but revealed 4 design-level issues:

1. **Default RSS feeds are dead** — all 3 hard-coded feeds fail (SSL error, invalid XML, empty response).
2. **Quality gate false-negatives** — best RSS item scored 56 (demote), missing `keep` threshold by 4 points due to interaction_score=0 and content-length binary split.
3. **Filter terms too broad** — generic terms like "科技" or "UK" match unrelated articles (false positives).
4. **Portal pages evade quality detection** — baidu.com homepage and sina finance homepage returned 68KB of navigation HTML, got discarded only by SPAM_SIGNALS false positives, not by portal detection.

## Design Decisions

### 1. Default RSS Feeds — Remove, Not Replace

**Decision:** Do not hard-code any default RSS feeds in `agent_reach_query_skill.py`.

**Rationale:**
- Any hard-coded feed list will rot. Feed availability, SSL certs, and XML formats change.
- There is no stable, zero-maintenance public RSS feed for Chinese stock research.
- 36kr feed works but is broad tech/startup news, not stock-specific.

**New design:**
```python
_DEFAULT_RSS_FEEDS = []  # empty list
```

RSS query generation behavior:
- If `ctx.agent_reach_rss_feeds` is provided and non-empty → generate RSS query with those feeds.
- If `_DEFAULT_RSS_FEEDS` is empty and no ctx override → **do not generate RSS query at all**.
- If RSS query is generated but `rss_filter_terms` is empty → skip with warning `[rss] no filter terms`.

This means Phase 0B requires **explicit user-provided feeds** for RSS to activate. The connector layer remains fully functional; only the query generation defaults change.

**Downstream impact:**
- When no feeds and no URLs are provided, `search_queries` may be empty.
- `agent_reach_fetch_skill` already handles empty `search_queries` → status `"empty"`.
- No pipeline crash.

---

### 2. Filter Terms — Tighten to Identity-Only

**Decision:** `rss_filter_terms` should contain only stock-identifying terms, never broad industry keywords.

**Current behavior (problem):**
```python
filter_terms = ["黑芝麻智能", "02533", "芯片", "半导体", "自动驾驶"]
```
Terms like "芯片" match any semiconductor article, causing noise.

**New design:**
```python
def _build_rss_filter_terms(stock_name: str, code: str, competitors: list = None) -> list:
    terms = []
    if stock_name:
        terms.append(stock_name)
    if code:
        terms.append(code)
    # Competitors only if explicitly provided and non-empty
    if competitors:
        for comp in competitors:
            if comp and comp not in terms:
                terms.append(comp)
    # Short-name variants (e.g. "黑芝麻" from "黑芝麻智能") — only if derivable
    short = _derive_short_name(stock_name)
    if short and short not in terms:
        terms.append(short)
    return [t for t in terms if t]
```

**Removed:** `_INDUSTRY_KEYWORDS` constant and its heuristic injection.

**Rationale:**
- Industry keywords ("芯片", "自动驾驶") are high-recall, low-precision.
- Stock name + code + competitors are identity-specific. An article mentioning "黑芝麻智能" is almost certainly about that company.
- If the user wants broader industry monitoring, they can explicitly provide industry terms via `ctx.agent_reach_rss_filter_terms_override` (new optional key).

**New ctx override keys (optional, backward-compatible):**
- `agent_reach_rss_feeds` — list of feed URLs
- `agent_reach_rss_filter_terms` — explicit filter terms, bypass auto-generation

---

### 3. Source-Aware Quality Scoring

**Decision:** Add a `source_type` hint to scoring so RSS/Web are not penalized for missing social signals.

**Problem analysis:**
Current scoring assumes social-post signals:
```
interaction_score: 0-10 points (RSS/Web always 0)
author presence: 5 points (RSS author often empty, Web author always "")
content length: 5 vs 10 points (binary at 50/200 chars)
```

A 36kr article with dense financial data but no interaction score gets -10 points compared to a Twitter post with 100 likes and empty content.

**New design — scoring profile by source type:**

```python
_SCORING_PROFILES = {
    "social": {
        # Current default (Twitter/Reddit/Xiaohongshu in future)
        "interaction_weight": 1.0,
        "author_bonus": 5,
        "content_long_threshold": 200,
        "content_medium_threshold": 50,
        "data_pattern_bonus": 4,
        "spam_penalty_per_hit": 5,
    },
    "rss": {
        "interaction_weight": 0.0,      # ignore interaction_score
        "author_bonus": 3,             # RSS sometimes has author
        "content_long_threshold": 150,  # RSS summaries are shorter than social
        "content_medium_threshold": 30,
        "data_pattern_bonus": 5,       # RSS articles often have structured data
        "spam_penalty_per_hit": 3,     # lower penalty — RSS spam is rarer
    },
    "web": {
        "interaction_weight": 0.0,
        "author_bonus": 0,             # Jina Reader does not provide author
        "content_long_threshold": 300, # Web articles are longer
        "content_medium_threshold": 80,
        "data_pattern_bonus": 5,
        "spam_penalty_per_hit": 3,
        "portal_penalty": -15,         # NEW: penalty for suspected portal pages
    },
}
```

**Source type detection:**
```python
def _detect_source_type(item: SynthesisItem) -> str:
    platform = item.source_platform.lower()
    if "rss" in platform:
        return "rss"
    elif "web" in platform:
        return "web"
    else:
        return "social"  # default for future platforms
```

**Scoring function signature change:**
```python
def score_agent_reach_item(
    item: SynthesisItem,
    stock_name: str = "",
    search_queries: List[dict] = None,
) -> dict:
    profile = _SCORING_PROFILES[_detect_source_type(item)]
    # ... use profile thresholds and weights ...
```

**Key threshold implications:**

| Source | KEEP threshold | DEMOTE threshold | Notes |
|--------|---------------|-----------------|-------|
| social | 60 | 35 | current behavior preserved |
| rss | 50 | 30 | lower due to no interaction |
| web | 50 | 30 | lower due to no interaction; portal penalty compensates |

**Rationale for separate thresholds:**
- RSS/Web cannot have interaction scores. Penalizing them for a signal they cannot possess is structurally unfair.
- Lowering the threshold universally (e.g., KEEP=50 for all sources) would let low-quality social posts into `keep`.
- Source-aware thresholds keep social gate strict while allowing RSS/Web to compete on data/evidence density.

---

### 4. Portal/Navigation Page Detection for Web

**Decision:** Add a lightweight portal-page classifier to `agent_reach_quality_skill.py` for `source_type="web"`.

**Problem:**
- Baidu homepage: 8222 chars, mostly navigation links. Scored 24 (discard) only because "链接" triggered SPAM_SIGNALS.
- Sina finance homepage: 68181 chars, dense link lists. Scored 25 (discard) because "链接" and "涨停" triggered multiple penalties.
- Neither was recognized as a portal page. They were penalized by accident, not by design.

**Portal detection heuristics:**
```python
def _is_portal_page(item: SynthesisItem) -> bool:
    """Detect homepage/portal/navigation pages from Jina Reader output."""
    content = item.content
    if not content:
        return False

    signals = 0

    # Signal 1: Very high link density (many http:// in short text)
    link_count = content.count("http://") + content.count("https://")
    lines = content.splitlines()
    non_empty_lines = [l for l in lines if l.strip()]
    if non_empty_lines and link_count / len(non_empty_lines) > 0.5:
        signals += 1

    # Signal 2: Short average line length (navigation links are short)
    avg_line_len = sum(len(l) for l in non_empty_lines) / max(len(non_empty_lines), 1)
    if avg_line_len < 40:
        signals += 1

    # Signal 3: Presence of portal keywords
    portal_kws = ["首页", "导航", "网站地图", "sitemap", "友情链接", "所有分类", "更多"]
    kw_hits = sum(1 for kw in portal_kws if kw in content)
    if kw_hits >= 2:
        signals += 1

    # Signal 4: Title is generic (homepage titles are not article titles)
    generic_titles = ["首页", "首页_", "_首页", "主页", "home", "首页 -", "- 首页"]
    if any(item.title.lower().startswith(gt.lower()) for gt in generic_titles):
        signals += 1

    return signals >= 2
```

**Scoring integration:**
```python
if source_type == "web" and _is_portal_page(item):
    score += profile["portal_penalty"]  # -15
    reasons.append("疑似门户/导航页，内容价值低")
```

**Why not detect in WebConnector:**
- WebConnector's job is to fetch content faithfully. It should not make editorial judgments.
- Quality gate is the right layer for content-value classification.
- Portal detection may need scoring context (e.g., a short but valid article might share some signals with a portal page).

---

## Scope of Changes (Design-Only)

| File | What changes | What stays |
|------|-------------|-----------|
| `agent_reach_query_skill.py` | Remove `_DEFAULT_RSS_FEEDS` entries; tighten `_build_rss_filter_terms`; add ctx overrides | Connector registry, skill decorator, query spec shape |
| `agent_reach_quality_skill.py` | Add `_SCORING_PROFILES`, `_detect_source_type()`, `_is_portal_page()`; modify scoring dimensions per profile | KEEP/DEMOTE thresholds for social remain unchanged; downstream contract unchanged |
| `agent_reach_skill.py` | No changes needed | Already correct |

**Forbidden to touch:**
- `SynthesisSkill`, `KnowledgeSynthesizer`, `scoring_engine.py`
- `AgentReachEvidenceRenderer` (it consumes quality results unchanged)
- `source_adapter.py` (source_platform string already carries platform info)
- Entry scripts, Xueqiu/CDP

## Open Design Questions

1. **Short-name derivation:** Should `_derive_short_name("黑芝麻智能")` return `"黑芝麻"`? This requires a simple heuristic (strip suffixes like "智能", "科技", "股份"). What if the short name collides with common words (e.g., "苹果")?

2. **Web article vs portal boundary:** What if a legitimate news site article contains many links (e.g., a " roundup" article with 20 source links)? The portal detector may misfire. Should we whitelist known news domains?

3. **RSS feed user experience:** With empty default feeds, a user who enables Agent-Reach but provides no feeds will always get status `"empty"`. Is the error message clear enough to guide them to provide feeds?

4. **Threshold calibration:** KEEP=50 for rss/web was derived from the 36kr test item (score 56). Should it be 48 to provide margin? Or should we tune after more real data?

## Next Step Recommendation

Implement Phase 0B in this order:
1. Empty default RSS feeds + tightened filter terms (query skill, low risk)
2. `_detect_source_type()` + scoring profiles (quality skill, medium risk — affects all Agent-Reach scoring)
3. Portal page detection (quality skill, medium risk — new heuristic)
4. Re-run full validation suite + live smoke test
