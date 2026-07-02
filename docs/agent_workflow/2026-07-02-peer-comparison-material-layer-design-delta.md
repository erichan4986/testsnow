# Design Delta — Peer Comparison Material Layer

## Review Source

- Review notes: `docs/agent_workflow/2026-07-02-peer-comparison-material-layer-claude-review-notes.md`
- Revised design: `docs/agent_workflow/2026-07-02-peer-comparison-material-layer-design.md`

## Accepted

### MF1: Peer Row Confidence Formula

Accepted.

The design now defines deterministic confidence tiers:

- `0.85`: same metric / same period / same unit / same deterministic source family;
- `0.75`: same metric but mixed formal/deterministic sources;
- `0.60`: formal refs mention both target and peer, no fully comparable metric;
- `0.40`: title/snippet-only context;
- no row when one side is absent, source is social-only, or the metric would be inferred.

Adjustments for period mismatch, unit mismatch, and weaker source families are also defined.

### MF2: Input-Layer Hard Filtering

Accepted.

The design now requires prompt construction to filter peer rows before the LLM sees them:

- `< 0.50`: removed;
- `0.50-0.70`: context labels only, no comparison wording or numeric spread;
- `>= 0.70`: full comparison row may enter 4.1/4.2 prompt.

This mirrors the Batch 2b hard-filter pattern.

### MF3: Broader Peer-Comparison Gate

Accepted.

The design now splits peer wording into:

- strong comparison terms, which trigger error without sidecar support;
- weak comparison terms, which also require sidecar support and should at least warn/error depending on context.

The sidecar source-ref whitelist is explicit.

### MF4: Existing Hard-Coded Stock Regression

Accepted.

The design now requires Phase 3a to prove:

- config-backed stock lookup works;
- fallback stock lookup still works;
- `competitor_metrics_table` uses the same peer ordering path;
- at least one existing stock regression is run before Phase 3c is considered complete.

## Deferred

### N1: Full Migration Order for All Existing Stocks

Partially deferred.

Phase 3a will prove fallback compatibility and migrate Fudan first. Bulk migration of all existing stocks can happen later after the helper is stable.

### N2: Peer Dimensions vs Existing Valuation Table

Accepted as a design constraint, but implementation is deferred to Phase 3b/3c.

The revised design now says 4.1 peer table is qualitative positioning only and must not duplicate the existing numeric competitor metrics table.

### N3: Reuse Source Boundary Whitelist

Accepted in design via explicit `source_refs` prefixes. Exact code reuse will be decided during implementation.

## Rejected

None.

## R2 Required

No for Phase 3a.

Phase 3a is limited to config migration and peer lookup/metrics fallback, with no LLM prompt change and no peer material pack. The revised design addresses the review's must-fix items sufficiently to begin Phase 3a.

Round 2 should be considered before Phase 3b/3c if implementation changes the confidence formula, source-ref schema, or prompt filtering boundary.

