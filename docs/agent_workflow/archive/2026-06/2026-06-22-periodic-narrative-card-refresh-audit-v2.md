# Periodic Narrative Card Refresh Audit v2

Date: 2026-06-22

Scope: read-only maintenance audit after commit `c430fba Improve periodic narrative card extraction quality`.

Inputs:

- `/tmp/saiweiwei_refresh_audit_v2.md`
- `/tmp/huadajiutian_refresh_audit_v2.md`
- `/tmp/zhongjixuchuang_refresh_audit_v2.md`
- `/tmp/debangkeji_refresh_audit_v2.md`

No Knowledge notes were deleted or refreshed in this audit.

## 1. Maintenance Summary

| Stock | Generated cards | Existing notes | Refreshable | Dangling | New candidates |
| --- | ---: | ---: | ---: | ---: | ---: |
| 赛微微电 | 10 | 4 | 3 | 1 | 7 |
| 华大九天 | 24 | 24 | 23 | 1 | 1 |
| 中际旭创 | 8 | 9 | 8 | 1 | 0 |
| 德邦科技 | 19 | 20 | 18 | 2 | 1 |

## 2. Decisions

| Stock | File / candidate | Decision | Reason |
| --- | --- | --- | --- |
| 赛微微电 | `2025-annual-rd-product-progress-1.md` | Keep for now; mark as extractor-miss candidate | The note is still useful: it captures battery-management chip precision, safety, stability, low power, SOC estimation, charging management, and cell balancing. The current extractor no longer reproduces it, but deleting it would lose useful product evidence. |
| 赛微微电 | 7 new management/margin candidates | Do not write yet | Several look useful, but this stock was not part of the current sample refresh target. Review separately before expanding Saiweiwei notes. |
| 华大九天 | `2025-annual-financial-note-8.md` | Keep for now; likely index-shift, not true dangling | The old note is a useful financing cash-flow explanation. The regenerated pack still contains a similar statement as `financial_note:7`, so this is mostly stable-id/index drift rather than low-quality content. |
| 华大九天 | new `financial_note:9` candidate | Reject / do not write | It is generic inventory-policy wording: "在确定存货的可变现净值时..." This is not useful company-specific evidence and should be filtered in a later `financial_note` noise pass. |
| 中际旭创 | `2025-annual-market-outlook-0.md` | Keep for now; reclassified duplicate | The text is still useful company strategy/product roadmap evidence. It became dangling because the `future_strategy` duplicate now collapses into the management/market scope. Do not delete until stable-id migration is designed. |
| 德邦科技 | `2025-annual-market-outlook-2.md` | Delete-later candidate | It is only a short risk sentence about新能源 policy/overcapacity/supply-chain volatility. It is not wrong, but it is weak as a market-outlook Knowledge card and was removed by stricter extraction. |
| 德邦科技 | `2025-annual-market-outlook-3.md` | Delete-later candidate | It duplicated the company strategy paragraph and included checkbox markers. The useful content is now represented by `management_market_view:5` with checkbox markers stripped. |
| 德邦科技 | new `financial_note:4` candidate | Do not write yet | It is a narrow government-grant line. It may be factual, but it is low priority compared with product/R&D/market cards and should not be added automatically. |

## 3. Findings

### Stable ID / Index Drift

Some dangling notes are not true quality failures. They appear because card indexes are generated per type after filtering. When a noisy card is removed, later cards can shift from `financial_note:8` to `financial_note:7`, producing a dangling old file and a different generated target.

This affects at least:

- 华大九天 `financial-note-8`
- 中际旭创 `market-outlook-0`

Recommendation: do not delete dangling notes until the note identity strategy is improved. A future writer can use `source_excerpt_hash` / `source_block_hash` to detect moved cards and either refresh in place or emit a migration plan.

### Financial Note Still Needs One More Noise Pass

The borrowing-cost policy filter worked, but a new low-value inventory-policy candidate remains:

- 华大九天 generated `financial_note:9`: "在确定存货的可变现净值时..."

Add a filter for generic inventory valuation basis text unless it includes company-specific causal tokens such as `主要系`, `本期`, `报告期`, `较上年同期`, `回款`, `减值原因`, `计提金额`, or a specific risk/event.

### De-duplication Improved But Is Not Complete

The `future_strategy` duplicate was reduced, but non-`future_strategy` management/market overlap can still exist. For example, 德邦科技 has a market-demand paragraph represented under both management-market-view and market-outlook. That is acceptable for now because one describes industry judgment and one supports market outlook, but broad duplicate cleanup should be hash/overlap based and tested carefully.

## 4. Recommended Next Step

Do not batch refresh Knowledge yet.

Recommended next small code bucket:

1. Add hash-aware maintenance diagnostics:
   - show when a dangling note's `source_excerpt_hash` still exists in generated cards under a different filename;
   - classify as `moved_or_reindexed`, not `dangling`.
2. Add one more financial-note policy-noise filter:
   - reject generic inventory valuation basis snippets.
3. Re-run the same four previews.

Only after that should we refresh Knowledge samples. Deletion should remain a separate, explicit user-approved action.
