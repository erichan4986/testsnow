# Design Delta — Theme Material Budget With Global Source IDs

Date: 2026-07-03

## Review Outcome

Claude Round 1 verdict: `proceed`.

The review confirmed the core bug:

- `KnowledgeSynthesizer.synthesize()` filters theme items once.
- `_build_prompt()` filters again.
- `_build_prompt()` renders local per-theme source ids.
- `SynthesisSkill._fill_citation_metadata()` resolves those ids against the global item list.

The global source-id material budget remains the right implementation boundary.

## Accepted Must-Fix

### MF1 — Theme-Isolated Source Refs

Accepted.

The budget must explicitly route fundflow items only to `funding_sentiment`. Fundflow rows must not leak into `events_catalysts`, `industry_logic`, `fundamentals`, or `valuation_debate`.

Implementation requirement:

- `_build_theme_material_budget()` builds `source_refs` per theme from global item ids.
- Funding items are assigned to `funding_sentiment`.
- Non-funding themes must reject `_is_funding_sentiment_item(item)` unless a future formal event/catalyst type explicitly permits it.

### MF2 — Supply-Chain Operating Variable Terms

Accepted with a small implementation adjustment.

The operating-variable term list should not be duplicated between budget and quality gate.

Implementation requirement:

- Move the operating-variable tuple to `scripts/utils/source_direct_relevance.py` as `OPERATING_VARIABLE_TERMS`.
- `report_quality.py` imports and reuses it.
- `KnowledgeSynthesizer` imports and reuses it for `supply_chain_state`.

Reason: `source_direct_relevance.py` already owns canonical-material relevance. Importing from `report_quality.py` would make synthesis depend on a checker module, which is the wrong direction.

### MF3 — Appendix Ordering

Accepted.

`_build_prompt()` must follow the budget's `appendices` order instead of hard-coded local order.

Implementation requirement:

For `fundamentals`, append:

1. `formal_financial_explanation_pack`
2. `formal_financial_fact_pack`
3. `peer_metrics_only`

For other themes, use their explicit budget appendix list.

## Deferred / Rejected

### N1 peer term integration

Deferred.

Peer quality warnings remain post-render checks. This V2 fixes source ids and routing, not peer-business semantics.

### N2 unified skip helper

Accepted only if tiny.

Claude suggested `_should_skip_theme()`. Implement only if it keeps code smaller and clearer than inline checks. Do not create a new module.

### N3 legacy synth warning

Optional.

Adding a one-line warning in `_legacy_llm_synthesize()` is allowed, but do not refactor that path in this batch.

## R2 Required

No.

Round 1 found implementable must-fix items that do not change the high-risk boundary. Proceed to implementation task.
