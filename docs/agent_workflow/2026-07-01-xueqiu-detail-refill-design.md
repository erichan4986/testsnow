# Xueqiu Detail Refill Design

Date: 2026-07-01

## Problem

Xueqiu list extraction can correctly identify long posts with `...` / `展开` as `featured`, but the detail-page stage still misses useful long-form posts when the first TopN batch is noisy, duplicated, or concentrated in one theme.

The Fudan Microelectronics trial exposed the failure mode:

- A valuation post comparing 复旦微电 with 紫光国微 was captured in the list cache and marked `_track=featured`.
- It ranked high enough by `content_score` to be a plausible detail candidate.
- It was not fetched as detail text because the temporary candidate sampler stopped after the first batch reached a small usable-count target.
- The fetched details over-covered G60 / FPGA / storage and under-covered valuation / A-H discount.

The goal is not to crawl more aggressively. The goal is to use the same safety budget more intelligently.

## Scope

In scope:

- Xueqiu detail candidate ordering and refill policy.
- One retry/refill pass after the first detail batch.
- Deterministic tests around candidate selection, drop accounting, dedupe, and topic coverage.
- Keeping the account-safety ceiling explicit.

Out of scope:

- Changing Xueqiu login/CDP mechanics.
- Increasing crawl frequency or removing delays.
- Changing 4.4 narrative composer logic.
- Feeding social materials into 4.1-4.3 canonical synthesis.
- Auto-running new Xueqiu detail fetches during ordinary tests.

## Design

### 1. Candidate Classification

Keep the existing `featured` / `sentiment` split, but add a structured detail-candidate layer for featured posts.

Each featured post gets deterministic metadata:

- `detail_candidate_reason`: list of reasons, such as `truncated_long_post`, `valuation_topic`, `earnings_topic`, `product_topic`, `risk_topic`, `high_interaction`.
- `detail_topic_buckets`: normalized buckets inferred from list text.
- `detail_score`: existing content score plus small topic bonuses.

Use a two-layer bucket model.

Generic buckets are enabled for every stock:

- `valuation`: 估值, PE, PS, 市值, 合理估值, 目标价, A/H, 港股, 折价, 可比公司, 紫光国微.
- `earnings`: 净利, 营收, 毛利率, 半年报, Q1, Q2, 业绩快报, 预告, 订单.
- `risk`: 价格战, 订单不及预期, 存货跌价, 竞争, 下修, 亏损.
- `catalyst`: 政策, 中标, 订单, 客户, 产能, 价格上行, 补贴, 并购.
- `industry_trend`: 行业景气, 周期, 供需, 国产替代, 产业链, 竞争格局.

Industry extension buckets are optional and must be enabled by stock config or a local collection config:

- `semiconductor_product`: FPGA, FPAI, MCU, EEPROM, NAND, 存储, PSoC, RFSoC.
- `aerospace`: 航天, 卫星, G60, 千帆, 星链, 抗辐照, 宇航.
- Future industries can add extension buckets without changing the generic defaults.

Common non-required bucket:

- `sentiment_only`: only price cheering, one-line emotion, or chart talk.

`sentiment_only` should not become a required coverage bucket.

Topic classification is two-pass:

- list-time rough classification allocates detail slots using truncated text;
- post-detail classification refines the bucket and can downgrade a fetched post to `sentiment_only`, `ui_noise`, or `duplicate`.

### 2. First Batch

The first batch remains bounded by the existing detail limit. It should select by:

1. Hard candidates: stock-specific long posts with `...` / `展开`, data, and logic words.
2. Topic quota: reserve slots for distinct populated non-sentiment buckets before filling by raw score.
3. Score: fill remaining slots by `detail_score`.

This keeps the normal path close to current behavior while preventing one hot theme from consuming every detail slot.

The topic quota must not require buckets that have no candidate posts. For example, if a non-semiconductor stock has only `valuation` and `earnings` candidates, the first-batch quota should allocate across those two buckets and should not reserve slots for `aerospace`.

### 3. Drop Accounting

After detail extraction, classify each fetched detail as:

- `usable`: enough cleaned body text and at least one analyzable claim.
- `duplicate`: substantially same article / repost / copied title and same core content.
- `ui_noise`: mostly page UI, navigation, repeated symbols, or extraction junk.
- `too_short`: body text too short after cleaning.
- `sentiment_only`: price mood without claim.
- `fetch_failed`: navigation or extraction failed.

The refill trigger should only count `usable` after duplicate collapse.

Duplicate collapse must use content-derived keys, not URL alone. The helper should compute a normalized content hash compatible with `curated_external_full_body_viewpoint_claims.normalized_hash`, falling back to a normalized title/hash key when detail content is missing. This handles copied posts such as the Fudan "三问预期差" article published by multiple accounts under different URLs.

### 4. One-Time Refill

Run a second detail batch only once when any trigger is true:

- usable details after dedupe `< min_usable_details` (default 5);
- first-batch drop rate `> max_drop_rate` (default 40%);
- non-sentiment topic coverage `< effective_min_topic_coverage`;
- a required topic configured for the stock is missing.

The refill batch:

- excludes all URLs already attempted;
- prioritizes missing topic buckets;
- still respects the global detail-page cap;
- does not recurse or trigger a third batch.

Recommended defaults:

- `first_batch_size`: 15
- `refill_batch_size`: 8
- `max_detail_pages_total`: 25
- `min_usable_details`: 5
- `max_drop_rate`: 0.40
- `min_topic_coverage`: 2

`effective_min_topic_coverage` is computed as:

```text
min(config.min_topic_coverage, count(populated_non_sentiment_candidate_buckets))
```

If a stock config provides `required_detail_topics`, those specific populated topics can still trigger refill when missing. Required topics that have zero list candidates must not trigger a refill by themselves; they should be logged as unavailable.

If `max_detail_pages_total` is reached, stop even if coverage remains imperfect.

### 5. Safety

The implementation must preserve Xueqiu account-safety rules:

- detail pages only under explicit user authorization and logged-in CDP;
- request interval at least existing default, preferably 5+ seconds;
- no background infinite loop;
- no detail-page fetch in standard unit tests;
- dry-run/selection tests must not touch network.

### 6. Output Metadata

The raw cache should record enough metadata to audit selection:

- attempted detail URLs;
- first-batch URLs;
- refill URLs;
- drop reasons per attempted URL;
- topic buckets per URL;
- dedupe groups;
- refill trigger reason;
- total detail pages fetched.

This makes it possible to explain why a high-quality post was missed or fetched.

The live fetch return shape should expose this audit without breaking current consumers. Prefer adding an optional `_selection_audit` key to the returned dict:

```python
{
    "featured": [...],
    "sentiment": [...],
    "_selection_audit": {...},
}
```

Downstream code that only reads `featured` / `sentiment` remains compatible.

### 7. 4.4 Packet Integration

Refill detail content must be available to the existing 4.4 packet builder. The preferred integration is to keep or export detail posts in a `stocks_data`-compatible shape:

```json
{
  "stocks_data": {
    "复旦微电": [
      {
        "title": "...",
        "content": "detail body",
        "url": "https://xueqiu.com/...",
        "author": "...",
        "time": "...",
        "source": "xueqiu",
        "_track": "featured",
        "source_detail_type": "xueqiu_column",
        "selection_audit": {"batch": "refill", "topics": ["valuation"]}
      }
    ]
  }
}
```

This lets `social_viewpoint_source_packets._xueqiu_like_candidates` read the same field family it already supports. If the live fetch writes vault Markdown as well, the JSON remains the source of truth for 4.4 packet generation.

## Failure Modes And Tests

### FM1: Long valuation post still missed

Symptom: a stock-specific post with `...展开`, valuation numbers, and peer comparison remains in sentiment-only cache.

Test:

- Fixture with Fudan valuation post and many G60 posts.
- Assert valuation post is in candidates.
- Assert it is selected in first batch or refill batch.

### FM2: Noisy first batch stops refill

Symptom: first batch has many fetches but few usable details; pipeline stops because attempted count is high.

Test:

- Fixture where 15 attempted details produce 4 usable and 8 UI-noise / duplicates.
- Assert one refill batch is requested.

### FM3: Infinite refill / account risk

Symptom: repeated refills keep opening detail pages after every bad batch.

Test:

- Fixture where refill also fails.
- Assert exactly one refill and total attempted URLs never exceed cap.

### FM4: Theme quota overfits one stock

Symptom: Fudan-specific keywords force every stock into FPGA / MCU categories.

Test:

- Generic stock fixture with valuation and earnings posts but no semiconductor terms.
- Assert valuation and earnings still work.
- Assert effective topic coverage is capped at the populated bucket count.
- Assert semiconductor extension buckets are optional.

### FM5: Duplicate posts inflate usable count

Symptom: copied "三问预期差" posts count as multiple usable details and suppress refill.

Test:

- Two same-content URLs plus several unfetched missing-topic posts.
- Assert content-hash duplicate collapse counts as one usable item and refill can still trigger.

### FM6: 4.1-4.3 source boundary regression

Symptom: newly fetched Xueqiu detail content enters canonical 4.1-4.3 synthesis.

Test:

- Existing source-boundary tests continue to pass.
- Xueqiu detail metadata remains display-only / social.

### FM7: Refill tries to pad missing candidates with noise

Symptom: the candidate pool has no remaining non-sentiment posts, but refill still fills all 8 slots with price emotion posts.

Test:

- Fixture where remaining candidates are already attempted or `sentiment_only`.
- Assert refill selects only available qualified candidates and can return fewer than `refill_batch_size`.

### FM8: List-time bucket classification is wrong

Symptom: a list excerpt looks like valuation but detail text is pure price emotion or UI junk.

Test:

- Fixture with a list-time `valuation` post whose detail body is `sentiment_only`.
- Assert post-detail classification downgrades it and drop accounting can trigger refill.

## Implementation Notes

Prefer a small deterministic helper module rather than embedding all logic inside Playwright code.

Possible helper shape:

- `scripts/utils/xueqiu_detail_selection.py`
  - `classify_detail_topics(post)`
  - `build_detail_plan(posts, config)`
  - `evaluate_detail_attempts(attempts, config)`
  - `build_refill_plan(candidates, attempts, config)`
  - `to_stocks_data_posts(attempts, stock_name)` or equivalent JSON adapter

Then wire the helper into:

- `scripts/utils/fetcher.py` for live fetch path;
- `scripts/high_risk/extract_detail.py` for post-cache detail extraction path, if compatible.

Unit tests should target the helper and use fixtures only. Live CDP smoke remains manual / Claude-run only.

The helper should avoid Playwright imports. It can import `normalized_hash` using the existing optional-relative-import pattern used elsewhere in `scripts/utils`.

## Runtime Cost

Worst-case per stock with defaults:

- first batch 15 detail pages;
- refill batch up to 8 detail pages;
- total detail cap 25 pages.

At 5+ seconds request interval plus human-like page dwell, this is roughly several minutes per stock. Batch runs across multiple stocks can take tens of minutes, so the refill path should remain opt-in with Xueqiu detail collection and should never run in ordinary CI or fast report validation.

## Acceptance Criteria

- Existing tests and gates pass.
- New unit tests cover first batch, one-time refill, dedupe, topic coverage, and cap behavior.
- No ordinary test opens Chrome or fetches Xueqiu.
- Fudan fixture proves the valuation post `https://xueqiu.com/1606930351/392467740` would be selected.
- Refill is capped to one pass and total detail pages are capped.
- Output metadata can explain selection, drop, and refill decisions.
- Generic-stock fixture proves `min_topic_coverage=2` and effective coverage do not force impossible buckets.
- Duplicate-content fixture proves copied posts with different URLs count once.
- Packet integration fixture proves refilled Xueqiu details can be converted into `stocks_data`-compatible items and then into display-only source packets.
