# Claude Review Notes: Xueqiu Detail Refill (Round 2)

Source design: `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-design.md`
Previous review: `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-claude-review-round1.md`

Reviewed files:
- `scripts/utils/fetcher.py` (XueqiuFetcher.fetch_stock_posts — current TopN selection)
- `scripts/utils/content_quality.py` (featured/sentiment split, content_score)
- `scripts/utils/detail_page_fetcher.py` (browser control, vault writing)
- `scripts/high_risk/extract_detail.py` (post-cache batch extraction)
- `scripts/utils/social_viewpoint_source_packets.py` (4.4 display-only packet builder)
- `tests/utils/test_detail_page_fetcher.py` (fixture tests, no CDP)
- `tests/utils/test_social_viewpoint_source_packets.py` (fixture tests, dedupe, display-only flags)
- `tests/reporter/test_report_source_boundary.py` (4.1-4.3 / 4.4 isolation)
- Fudan trial preflight output (5.5 section — actual failure-mode data)

---

## Verdict

**verdict: needs_revision**

Three issue classes detected:

- **1 blocker** — the default `min_topic_coverage=3` will cause false refill triggers on most stocks.
- **3 must-fix** — dedupe gaps, topic bucket stock-specificity, and post-refill packet pipeline integration.
- **3 nice-to-have** — time cost estimate, generic bucket layer, selection audit metadata scope.

---

## Blockers

### B1: `min_topic_coverage=3` will false-trigger on most stocks

The design sets `min_topic_coverage: 3` as default and uses the Fudan-shaped bucket set (`valuation`, `earnings`, `product`, `aerospace`, `risk`). Most A-share stocks will only have posts in **2 buckets** at most (valuation and earnings). If `product` and `aerospace` are Fudan-specific, a stock like 圣邦股份 or 长春高新 would have coverage ≤ 2, perpetually triggering the refill. The refill would then exhaust its page cap looking for an aerospace post that cannot exist, and the pipeline would burn 8 detail pages fetching nothing useful.

Suggested fix: Set `min_topic_coverage: 2` as default, or make it configurable per stock. The design already accepts the idea of "required topic configured for the stock" — that same mechanism should override the coverage threshold. A fallback rule should also say: if `min_topic_coverage > len(non_sentiment_buckets_that_have_candidates)`, lower it to match what's actually in the candidate pool.

---

## Must-Fix

### M1: Dedupe only covers exact URL match, not semantically identical posts

The design says "excludes all URLs already attempted" but FM5 tests duplicate post content from different URLs. The Fudan trial found the same "三问预期差" article published by two accounts (`青竹锋云` and `金飙弄潮儿`) at different URLs. A URL-only dedupe would count them as 2 usable items, suppressing the refill.

The `build_detail_plan` / `evaluate_detail_attempts` need a content-hash dedupe step *before* counting usable items for the refill trigger. The `social_viewpoint_source_packets` already uses `normalized_hash` — reuse that or a simpler title-similarity check.

See `tests/utils/test_social_viewpoint_source_packets.py` lines 75-113 for the existing dedupe fixture pattern. The refill selection should borrow that approach.

### M2: Topic buckets are Fudan-overfitted; need a generic base layer

Current buckets:
- `valuation` ✅ generic
- `earnings` ✅ generic
- `product` — Fudan-biased (FPGA/MCU/EEPROM). Works for semiconductor CO but not for most stocks.
- `aerospace` — clearly Fudan-specific (G60/千帆/抗辐照). Would be zero on 90% of stocks.
- `risk` ✅ generic
- `sentiment_only` ✅ generic

The design already acknowledges this in FM4, but the bucket list itself is a problem. Stock-generic buckets should be `valuation`, `earnings`, `risk`, plus maybe `industry_trend` (行业趋势, 景气, 周期) and `catalyst` (订单, 政策, 中标, 补贴). The semiconductor/fintech specific buckets (`product`, `aerospace`, etc.) should be a *separate extension layer* that the stock config optionally enables.

Suggested fix:
```python
# Generic buckets for ALL stocks
GENERIC_BUCKETS = {
    "valuation": ["估值", "PE", "市值", "目标价"...],
    "earnings": ["净利", "营收", "毛利率", "半年报"...],
    "risk": ["价格战", "竞争", "下修", "亏损"...],
    "catalyst": ["订单", "中标", "政策", "补贴"...],
}
# Extension layer for stocks whose config enables it
SEMICONDUCTOR_BUCKETS = {
    "product": ["FPGA", "MCU", "EEPROM"...],
    "aerospace": ["航天", "卫星", "G60"...],
}
```

The helper should detect which buckets have candidates and never require coverage above what's populated.

### M3: Post-refill content has no pipeline into 4.4 source packets

The design produces `xueqiu_detail_vault` content (Markdown files) and a detail-posts JSON. But the current 4.4 pipeline reads from `social_viewpoint_source_packets.build_social_source_packets()`, which reads from `report_input.json` (structured via `stocks_data` and `raw_data.zhihu`).

Newly refilled Xueqiu detail content has no adaptor into the source packet format. Without one, the refill adds pages to `/tmp` but never feeds the narrative composer. The design should either:
1. Document a small integration point in `social_viewpoint_source_packets.py` that can also read from the detail vault JSON format, or
2. Make the refill output structure compatible with the existing `stocks_data` format so the packets builder already picks it up.

Note: `social_viewpoint_source_packets._xueqiu_like_candidates` reads from `payload["stocks_data"][stock_name]`. If the refill output includes detail content in that shape, integration is minimal. If it uses a completely different schema, someone has to write a bridge.

---

## Nice-To-Have

### N1: Document time cost in the design

25 pages max at 5s interval + 4-9s page delay ≈ 4-7 minutes per stock. This is well within acceptable bounds but the design should mention it explicitly so implementers know the refill is not free. If the fetcher processes 6 stocks (current `extract_detail.py` conf), a worst-case run could last 30-40 minutes. The refill design is intended for the live-fetch path within XueqiuFetcher, which processes one stock per call, so this is less of a concern.

### N2: `detail_candidate_reason` over-engineered for list-time info

Adding `detail_candidate_reason` as a multi-reason list is clean, but at list-extract time the text is truncated. Reason types like `truncated_long_post` and `high_interaction` are already implicitly available from `content_score` and the `content` length. The most valuable reason types (`valuation_topic`, `earnings_topic`) depend on text matching against truncated list content, which will be less accurate than post-detail text.

Consider making the topic classification two-pass: rough at list time (for batch allocation), refined after detail extraction (for refill accounting). The design already implies this (evaluate_detail_attempts is post-extraction) but the doc should say so.

### N3: Selection audit metadata structure is well-designed but not yet wired to output

The design lists: attempted URLs, first-batch URLs, refill URLs, drop reasons, topic buckets, dedupe groups, refill trigger reason, total fetched. This is exactly what's needed. But the current `XueqiuFetcher.fetch_stock_posts` return shape (`{"featured": [...], "sentiment": [...]}`) has no room for this metadata.

The helper should either return the audit trail separately, or the fetcher's return dict should grow an `_selection_audit` key. Prefer a structured return type (dataclass or TypedDict) since the current duck-typed dict passing is already fragile.

---

## Specific Answers

### 1. Does one-time refill solve the actual failure mode?

**Yes, with caveats.**

The Fudan trial's failure mode was:
- `_track=featured` post was in the list cache → good.
- It ranked high enough by `content_score` → good.
- It was not fetched because the sampler used a "first batch + stop-if-usable" rule → **this is what the refill fixes**.

The refill's "usable count < 5" trigger would catch the case where 15 fetches yield 5 usable posts (the Fudan trial had 5 substantive out of 15) and the desired valuation post was in the unfetched remainder. Topic quota in the first batch helps by reserving slots, but the refill is the safety net.

The one-time constraint is critical. The Fudan trial's `usable = 5` would not trigger a refill under `min_usable_details=5` (exactly at threshold). Consider whether the threshold should be strict "< 5" or lenient "<= 5" — if the valuation post is the 6th candidate, a `< 5` trigger still misses it. This is borderline; 5 posts might be enough for 4.4 narrative, but the user wanted the valuation post specifically. I'd recommend `min_usable_details = 4` or `< 5` to give the refill more room.

### 2. Thresholds reasonable?

| Threshold | Value | Assessment |
|-----------|-------|------------|
| `first_batch_size` | 15 | ✅ Matches Fudan trial |
| `refill_batch_size` | 8 | ✅ 8/25 ≈ 1/3 of cap |
| `max_detail_pages_total` | 25 | ✅ Generous but capped |
| `min_usable_details` | 5 | ⚠️ Consider 4 for safety margin |
| `max_drop_rate` | 0.40 | ✅ 9/15 = 60% drop in Fudan → triggers refill |
| `min_topic_coverage` | 3 | ❌ **BLOCKER** — see B1 |

### 3. Topic bucket design overfitted to semiconductor?

**Yes — see M2.**

The `product` and `aerospace` buckets are explicitly Fudan-focused. A generic stock (consumer, finance, healthcare) would have zero posts in these buckets. The proposed fix: separate GENERIC_BUCKETS from extension layers, and make `min_topic_coverage` default to 2 unless overridden by stock config.

### 4. Testable without Chrome or Xueqiu network?

**Yes — the helper module design makes this possible.**

The design explicitly separates deterministic selection logic (`build_detail_plan`, `evaluate_detail_attempts`, `build_refill_plan`) from browser code. Existing test patterns prove this works:

- `test_detail_page_fetcher.py` uses fake objects (`FakeContext`, `FakeBrowser`) for Playwright-adjacent code
- `test_social_viewpoint_source_packets.py` uses json fixtures
- `test_report_source_boundary.py` uses static markdown strings

All six failure modes (FM1-FM6) can be tested with 3-5 fixtures:
- a fixture of ~30 list posts with diverse topics
- a fixture with duplicate content
- a fixture where detail extraction mostly fails
- a fixture with only 2 topic buckets populated
- a fixture with a generic stock (no semiconductor terms)

The helper function `classify_detail_topics(post)` is the only thing that touches post text, and it's a pure text-match function. No CDP needed.

### 5. Preserves 4.1-4.3 / 4.4 boundary?

**Yes, as designed. But see M3.**

The `social_viewpoint_source_packets.py` already sets `synthesis_display_only=True`, `scoring_eligible=False`, `risk_score_eligible=False`, and `verification_status="professional_observation"` for all social content. The source boundary test (`test_report_source_boundary.py`) flags any social reference appearing in sections 4.1-4.3.

The refill output would naturally inherit these properties since it goes through the same packet builder. The open question (M3) is whether there's a pipeline to feed refill output *into* the packet builder at all — but the boundary mechanism itself is correct.

### 6. Helper module boundary: `xueqiu_detail_selection.py` vs inline in fetcher/high_risk

**Strongly prefer the dedicated helper module.**

Arguments for `xueqiu_detail_selection.py`:
- The selection logic has 4 functions with non-trivial state (first batch, refill, dedupe). Inlining this into `fetcher.py` (already 880 lines) would make it harder to test.
- The logic is needed in two places: live fetch (`fetcher.py`) and post-cache extraction (`extract_detail.py`). A shared module avoids duplication.
- Unit tests can import the helper without any Playwright dependency.
- The module boundary matches the existing pattern: `content_quality.py` handles classification, `detail_page_fetcher.py` handles browser, `fetcher.py` orchestrates. This new module is selection/planning, which fits between them.

Arguments against (considered but rejected):
- "Too many tiny modules" — valid concern, but the project already has 50+ utils. One more is fine given the behavioral complexity.
- "High-risk scripts should be self-contained" — `extract_detail.py` already imports from `detail_page_fetcher.py`. It can import from `xueqiu_detail_selection.py` the same way.

The only concern is relative imports in the `scripts/utils/` package (no `__init__.py`). The new helper must avoid relative imports (no `from .content_quality`). The design doc already shows it as a set of functions with explicit imports. Use the same pattern as `social_viewpoint_source_packets.py` — it imports via optional-relative-fallback:

```python
try:
    from .curated_external_full_body_viewpoint_claims import ...
except ImportError:
    from curated_external_full_body_viewpoint_claims import ...
```

Or better, since the helpers are all at the same level, just use absolute imports from `scripts.utils.*`.

---

## Failure Mode Coverage Audit

| FM# | Failure Mode | Covered? | Notes |
|-----|-------------|----------|-------|
| FM1 | Long valuation post missed | ✅ | FM1 test + refill trigger |
| FM2 | Noisy first batch stops refill | ✅ | Drop rate trigger |
| FM3 | Infinite refill | ✅ | One-pass cap + max_pages_total cap |
| FM4 | Theme quota overfits one stock | ✅ | FM4 test, but the bucket list itself is still Fudan-shaped (M2) |
| FM5 | Duplicate posts inflate usable | ⚠️ | FM5 test exists but document needs URL-level dedupe; content-hash dedupe is implicit |
| FM6 | 4.1-4.3 boundary regression | ✅ | Existing boundary tests cover this |

**Missing failure modes:**

| FM7 | List-topic misclassification | Not covered | A post classified as `valuation` at list time might be pure emotion post-detail. The design's post-detail reclassification handles this, but the test fixtures don't include a misclassification case. |
|-----|-----------------------------|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FM8 | Refill exhaustive with no candidates | Not covered | If the refill's remaining candidates are all already-attempted or sentiment_only, the refill batch would have < 8 items. The design should say "refill selects from what's available; it does not pad with noise." |
| FM9 | Author reply chain inflating topic count | Not covered | 回复@xxx posts often appear as separate articles with their own URL but are actually comments on the same parent. They should be deduped or grouped. The `content_quality.is_featured` already deprioritizes replies (no truncation flag, less interaction), but the topic bucket classifier might still pick them up. |

---

## Recommendation

**Revise before implementation — address B1 and M1-M2, then proceed.**

Blockers: 1 (B1 — coverage threshold)
Must-fix: 3 (M1 dedupe, M2 generic buckets, M3 pipeline)
Nice-to-have: 3 (N1-N3)

The design is structurally sound. The one-time-refill-with-cap mechanism is the right answer to the Fudan trial failure mode. The helper module and fixture-based testing approach align well with existing project patterns. The source boundary mechanism is proven and doesn't need changes.

The three non-trivial revisions are:
1. Fix the default topic coverage threshold and make buckets orthogonal (B1 + M2 — heaviest lift)
2. Add content-hash dedupe to candidate selection (M1 — moderate)
3. Define the integration point between refill output and the 4.4 packet builder (M3 — lightweight)

After these, the design is ready for implementation.
