# Technical Analysis v2 Phase 2.2 Codex Review Round 2

## Verdict

`needs_revision`, repaired inline.

## Must-Fix Findings

### M1. Terminal shock would duplicate the Phase 2.1 volume formula

- Evidence: `_score_volume_confirmation()` currently owns the preceding-20 baseline, direction context, and
  reliability behavior. The first draft asked `analyze_terminal_shock()` to calculate the same facts.
- Risk: trend health and shock prose can print different ratios or disagree after a corporate action.
- Repair: one `build_volume_context()` fact helper is computed once by the analyzer and consumed by both
  paths. The accepted score matrix remains in the state machine.
- Status: closed.

### M2. Scenario interpretation had no explicit indicators input

- Evidence: current `_interpretation()` receives only resonance, trend, target, and action, while the design
  selects MA20, MA60, and current close.
- Risk: implementation would read hidden globals, copy indicators into a second payload, or select levels in
  the renderer.
- Repair: the exact signature and caller change are now part of the contract.
- Status: closed.

### M3. Cache shape validation could not prove level provenance

- Evidence: `_valid_interpretation()` has no resonance/indicators context. A cached numeric level with a valid
  enum could pass even when it no longer equals MA20 or a current zone.
- Risk: stale or malformed exact prices reach the report.
- Repair: `ensure_technical_judgment()` performs context-aware source/value matching and strips context-free
  additive projections to the valid core judgment.
- Status: closed.

## Scope Review

The repairs reuse the same five runtime files. Moving raw volume facts to `technical_structure.py` replaces
duplicate computation and does not create a new score owner. No blocker remains for the second edge-case
review.
