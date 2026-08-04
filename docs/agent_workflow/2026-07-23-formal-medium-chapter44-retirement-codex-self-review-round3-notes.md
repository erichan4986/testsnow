# Formal-Medium Chapter 4.4 Retirement: Codex Self-Review Round 3

日期：2026-07-23
Verdict：`ok after fixes`

## Findings

### S1. Diagnostics retained a hidden-section assumption

`visible_rows_count=sum(len(section.rows) for section in sections[:3])` currently excludes 4.4 intentionally. Once the view model has only three sections, leaving the slice would be correct by accident and misleading to future maintainers.

**Fix:** Design now requires iterating all visible `sections`.

### S2. A private-renderer test would not prove profile integration

Calling `_formal_medium_source_layer_body()` directly would miss a regression where `_deep_analysis()` or profile routing later appends a 4.4 block.

**Fix:** The new absence fixture must use the public `render()` entry with a formal-medium context and assert the complete heading/label contract.

### S3. Fresh-report acceptance assumed fixed profile routing

Report material can change profile decisions. Hard-coding only a stock name and expected heading count could misclassify a legitimate profile change.

**Fix:** Acceptance first reads embedded profile metadata, then applies the profile-specific contract. formal-medium and formal-thin must have three sections; formal-rich legacy may retain external 4.4.

### S4. Shared title hardcode cleanup would widen scope

After deletion, the title helper is only used by 4.2, which suggests a future rename and deny-list reduction. Doing that now would change broker-summary behavior and require separate fixtures.

**Fix:** Explicitly deferred. This batch only deletes price-path ownership.

## Final Self-Review Verdict

- Blockers: 0
- Must-fix remaining: 0
- Scope expansion: none
- Implementation ready after the user-approved replacement of Claude review with two additional Codex self-review rounds: yes
