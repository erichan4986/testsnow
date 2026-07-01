# Design Delta: Xueqiu Detail Refill

Date: 2026-07-01

Review source:

- `docs/agent_workflow/2026-07-01-xueqiu-detail-refill-claude-review-notes.md`

## Accepted

- B1 accepted: default `min_topic_coverage` changed from 3 to 2. The design now computes `effective_min_topic_coverage = min(config.min_topic_coverage, populated_non_sentiment_candidate_buckets)` so ordinary stocks do not refill while searching for nonexistent buckets.
- M1 accepted: URL-only dedupe is insufficient. The design now requires content-hash dedupe compatible with `normalized_hash`, with title/hash fallback when body text is missing.
- M2 accepted: the bucket model is split into generic buckets and opt-in industry extension buckets. Semiconductor and aerospace terms are no longer global requirements.
- M3 accepted: refill output must be available in a `stocks_data`-compatible JSON shape so the existing 4.4 packet builder can consume it as display-only social content.
- N1 accepted: runtime cost is documented.
- N2 accepted: topic classification is now explicitly two-pass, rough at list time and refined after detail extraction.
- N3 accepted: `_selection_audit` is specified as an optional return key to avoid breaking existing consumers.

## Rejected

- No review item rejected.

## Deferred

- Exact stock-config schema for enabling industry extension buckets is deferred to implementation. The design only requires that extension buckets be opt-in and testable.
- Live Xueqiu smoke is deferred until after deterministic unit tests pass; ordinary CI must remain no-network/no-Chrome.

## R2 Required

No. The blocker and must-fix items were addressed in the design without changing the high-risk account-safety boundary. The next step can be implementation planning or a Level 2 implementation task.

