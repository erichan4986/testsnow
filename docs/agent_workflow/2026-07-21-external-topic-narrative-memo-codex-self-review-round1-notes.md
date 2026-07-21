# External Topic Narrative Memo Codex Self-Review Round 1

## Verdict

`needs_revision`, repaired in the design before Round 2.

## Findings And Resolution

### SR1-01 — Memo could become a hidden second selector

- Severity: must-fix.
- Finding: card-level coverage allowed the LLM to omit secondary evidence units from a multi-unit canonical card.
- Resolution: design section 7 now requires every evidence unit in every card to be represented exactly once. Projection applies the same rule after filtering hidden cards.

### SR1-02 — Clause suffix could lose the grammatical subject

- Severity: blocker.
- Finding: allowing a quote to start after arbitrary punctuation could turn a target-with-peer-context unit into an unattributed or wrongly attributed claim.
- Resolution: quotes must start at the normalized source-unit start and may only shorten at a complete terminal boundary. The LLM cannot extract a suffix.

### SR1-03 — "One call" contradicted inherited retry behavior

- Severity: must-fix.
- Finding: the draft said one request but also inherited configured retries, so worst-case latency and request count were not bounded.
- Resolution: the memo uses the existing JSON request helper with `max_api_retries=0`: one logical call, one HTTP attempt, no repair loop.

### SR1-04 — Optional-envelope reader contract was underspecified

- Severity: must-fix.
- Finding: the design did not define how narrative status coexists with current core pack status or how duplicate card ownership is handled.
- Resolution: the reader retains all current core fields and adds `topic_narrative_status/topic_narratives`; duplicate card identity invalidates only the envelope.

### SR1-05 — Client ownership risked a circular dependency

- Severity: must-fix.
- Finding: assigning a composer adapter to the new narrative module while the existing full-body module imports narrative validation could produce duplicated request code or a cycle.
- Resolution: the new module is pure. The existing full-body module owns the OpenAI-compatible request factory and reuses `_request_json`.

### SR1-06 — Rejected model prose could leak into persisted packs

- Severity: must-fix.
- Finding: partial status did not explicitly forbid storing invalid draft groups or raw model output.
- Resolution: only validated groups persist; raw responses and rejected quotes are diagnostics counts/reason codes only.

## Remaining Focus For Round 2

- schema compatibility and fingerprint completeness;
- actual citation-offset and final visible-citation behavior;
- punctuation rendering and quality-gate framing;
- one-call payload/no-cap failure behavior;
- test/budget realism.
