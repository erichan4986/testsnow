# Annual Document Coverage Manifest - Codex Self-Review Round 2

Verdict: ok after incorporated revision; implementation-ready

## Findings

1. **Evidence and producer stages need distinct states.** The evidence builder cannot honestly emit
   `card_selected` or `reviewed_no_card`. Add a stage field and `selected_for_review` provisional state.
2. **Exact duplicate candidates can collide.** Collapse exact identity duplicates in the ledger and retain an
   occurrence count; do not create duplicate manifest IDs.
3. **Truncated IDs are unnecessary risk.** Use full SHA-256 section and coverage-block IDs.
4. **Page markers must not leak across distant sections.** A preceding page marker may attach only within a
   bounded source distance; page markers inside a section remain valid.
5. **Page locator status needs complete enum semantics.** Define available/partial/unavailable.

After these deltas the design has no blocker or unresolved must-fix.
