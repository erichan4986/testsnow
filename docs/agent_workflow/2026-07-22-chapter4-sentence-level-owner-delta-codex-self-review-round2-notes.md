# Chapter 4 Sentence-Level Owner Delta: Codex Self-Review Round 2

## Verdict

`ok`，implementation ready。

## Findings and Repairs

### S1 — Peer/industry facts must not use target owners

4.1/4.2 owner rows describe the target company. Comparing peer/industry narratives against them could suppress a peer fact that happens to share products, metrics or wording.

**修复：**owner-equivalence only applies to `scope_bucket == "target"`; peer/industry narratives bypass this filter and retain their existing partition/order behavior.

### S2 — Polarity and relation anchors needed explicit protection

High textual similarity can hide a semantic reversal (`存在瓶颈` versus `没有瓶颈`) or a new partner relation.

**修复：**the design now requires separate polarity/constraint and relation-anchor comparisons before containment or similarity admission.

### S3 — Citation behavior is already single-owner

The renderer already calls `_visible_citations_only()` after assembling the final body. No new citation-pruning path is needed; tests only need to prove full-snapshot offsets remain stable while hidden definitions disappear from the final source list.

### S4 — Price-path independence remains intact

4.4 continues to consume the original admitted external rows. Empty narrative sentinels affect only 4.3 rendering, so owner-delta display cleanup cannot silently alter price-path material.

## Final Scope and Budget

- Runtime files: 2
- Test files: 2
- No producer, pack, quality gate, taxonomy or scoring changes
- Runtime target: net +70; hard stop: +100
- Remaining prose theme warnings may persist for legitimate recent external updates and are not an implementation failure.
