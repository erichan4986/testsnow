# External Producer v4 - Codex Self-review Round 1

Verdict before fixes: `needs_revision`
Verdict after fixes: `ok_for_round2`

## Findings and resolution

1. **Blocker - reader could not prove offsets from fingerprints alone.** Accepted. Pack v4 now embeds canonical
   source documents and blocks; fingerprints remain freshness metadata.
2. **Must-fix - comparative owner transitions were underspecified.** Accepted. The design now separates immutable
   block primary owner from per-unit local owner. An inline contrast does not transitively change the paragraph's
   omitted subject.
3. **Must-fix - suffix-less peer entities were not reconstructable.** Accepted. Added a document-local exact entity
   inventory from comparative titles, headings, action subjects and explicit relation grammar.
4. **Must-fix - mixed target/peer units had no provenance state.** Accepted. Added `target_peer_relation`; simple
   co-occurrence cannot create it.
5. **Must-fix - report adapter still implicitly depended on v3.1 display spans.** Accepted. The v4 adapter consumes
   canonical unit text and ID-only narrative order directly; `external_display_text()` is deleted.
6. **Must-fix - size baseline was not reproducible in a dirty worktree.** Accepted. Batch A must record HEAD, diff
   fingerprint and per-file numstat before implementation.
7. **Nice-to-have - separate source sidecar.** Rejected. It creates a second freshness/transaction boundary and
   makes strict reader verification less reliable than embedding the modest canonical source blocks.

## Scope audit

- No scoring, target, risk, technical or recommendation changes.
- No report-time LLM.
- No source-provider or browser changes.
- Clean v4 cutover remains intact.
