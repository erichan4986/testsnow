# Chapter 4 External Topic Grouping Codex Review Round 1

verdict: ok

## Findings

- blocker: none
- must-fix: none
- nice-to-have: formal-rich 4.4 may adopt the same presentation later, after the
  current formal-medium/formal-thin output is accepted.

## Review Notes

- Grouping belongs in the renderer because producer taxonomy and material
  selection are already correct; changing either would risk material loss.
- Entity scope must be the outer grouping key. Topic-first grouping across scopes
  would make peer facts look like target-company observations.
- Citation offsets must be calculated from each row before rendering. Grouping
  may reorder rows but must not allocate or renumber references.
- Row-level external/verification framing must remain. A scope-only disclaimer is
  insufficient for line-oriented market-share and strong-confirmation gates.
- A fixed canonical topic order improves scanning, while stable first-seen order
  inside each topic preserves the producer's argument sequence.
- Runtime impact should remain small: one grouping helper plus projection cleanup.

implementation_ready: yes
