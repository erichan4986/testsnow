# External Topic Narrative Memo Codex Self-Review Round 2

## Verdict

`ok` after the design repairs below. No unresolved blocker or must-fix remains in the Codex self-review.

## Findings And Resolution

### SR2-01 — Narrative prose could leak into profile or synthesis consumers

- Severity: blocker.
- Finding: `deep_analysis_display` is consumed by evidence profile, freshness, and synthesis-text paths in addition to Chapter 4 rendering. Replacing `industry_logic` with memo prose would violate display-only ownership.
- Resolution: the design now exposes narratives only as `_curated_external_topic_narratives`. Exact-card `industry_logic`, synthesis text, taxonomy, item count, and source list remain unchanged.

### SR2-02 — Citation ownership was not explicit enough

- Severity: must-fix.
- Finding: allowing refs in the LLM draft or persisting quote-specific refs could create a second citation owner and conflict with full-unit quote hashes.
- Resolution: drafts/envelopes contain no refs. Reader/display projection inherits refs from the referenced evidence unit; the existing full-unit citation and hash remain canonical.

### SR2-03 — Paragraph punctuation could break inline markers

- Severity: must-fix.
- Finding: the earlier design allowed punctuation normalization but did not define whether refs appear before or after separators.
- Resolution: deterministic assembly now strips one joining terminator, attaches local refs to the exact quote text, and then adds `；此外，` or `。`. A focused punctuation/citation test is required.

### SR2-04 — Memo timeout inherited the selector's 120-second worst case

- Severity: must-fix.
- Finding: a no-retry memo could still stall refresh for two minutes.
- Resolution: the shared request helper receives an optional timeout argument; selector default stays 120 seconds, memo uses one attempt at 60 seconds.

### SR2-05 — Ordering language could reorder target scope variants

- Severity: must-fix.
- Finding: sorting by raw `entity_scope` could separate or reorder `target` and `target_with_peer_context` inside one target bucket.
- Resolution: group by scope bucket/topic, then retain existing canonical card and source-unit order.

### SR2-06 — Runtime budget lacked a reproducible baseline

- Severity: must-fix.
- Finding: the design stated net limits without defining the baseline or whether tests/docs count.
- Resolution: implementation-start `HEAD`, listed runtime files only, with per-file numstat in batch notes.

## Round 2 Requirement Audit

- Core v3 cards remain the only evidence/profile owner: yes.
- Every visible evidence unit remains represented: yes.
- Target and peer remain structurally isolated: yes.
- Report-time LLM/source reads: forbidden and tested.
- Formal-thin offsets use full snapshot refs: explicit and tested.
- Invalid/stale/partial memo cannot block core pack or report: explicit.
- Chapter 4.4 and decision paths remain row-based: explicit.
- One-call operational cost is bounded: one attempt, 60 seconds.
- No sidecar, note directory, second model, repair loop, or display cap: explicit.

## Implementation Readiness

Ready for the required independent Level 3 Round 1 review. Implementation must not begin before that review is resolved.
