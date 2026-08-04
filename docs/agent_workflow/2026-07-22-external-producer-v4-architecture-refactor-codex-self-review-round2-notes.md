# External Producer v4 - Codex Self-review Round 2

Verdict before fixes: `needs_revision`
Verdict after fixes: `ok`

## Findings and resolution

1. **Must-fix - narrative relation labels created another semantic owner.** Accepted. The plan now contains only
   paragraph grouping and order. Free prose and relation labels are forbidden.
2. **Must-fix - report compatibility was specified only at MaterialSnapshot.** Accepted. The current display
   envelope keys remain stable, while freshness, synthesis and assembly are explicitly forbidden from branching on
   pack schema.
3. **Must-fix - LLM efficiency contract was qualitative.** Accepted. Selector batches use a versioned 24,000
   character budget with at most one malformed-response retry; narrative planning uses one request at most and no
   retry.
4. **Must-fix - source truncation and collapsed comparative input were not fail-closed.** Accepted. Canonical
   production forbids truncation, persists boundary status and rejects degraded comparative documents.
5. **Must-fix - structural suffix cleanup could silently delete facts.** Accepted. Trailing disclaimers/navigation
   become noise blocks instead of truncating the body.
6. **Must-fix - deletion budget lacked a concrete replacement ledger.** Accepted. The design names the complete
   projection/narrative modules and v3 branches that must disappear, with per-batch numstat.
7. **Nice-to-have - remove all acquisition utilities during Batch D.** Rejected. WeChat, video and discovery tools
   still have live callers. Only call-graph-proven dead modules are deleted.
8. **Nice-to-have - preserve semantic `contrast` connectors for prose quality.** Rejected. An unverified relation
   can distort exact evidence; neutral connectors plus coherent grouping are safer.

## Final design assessment

- One source canonicalizer, scope owner, family owner, pack reader and display-envelope writer.
- LLM owns selection/order only.
- Exact evidence is reconstructable from embedded canonical blocks.
- Clean cutover and rollback are atomic.
- Batch A is ready for an implementation plan after the required independent Level 3 design review.
