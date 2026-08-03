# Chapter 4.3 External Framing Narrow Fix

## Goal

Improve Chapter 4.3 readability without dropping producer material or weakening
source traceability. The existing sentence-level owner-delta projection remains
the sole fact deduplication owner.

## Design

- Keep canonical external cards, source units, topic narratives, row admission,
  citation offsets and target/peer partition unchanged.
- Replace generic topic leads with explicit incremental/background attribution:
  target material is an external incremental observation; peer material is
  external comparison context.
- Join continuation units with punctuation instead of repeating `此外`; preserve
  explicit connectors already present in source text and preserve separate-part
  paragraph boundaries.
- Keep every retained quote byte-for-byte unchanged apart from existing terminal
  punctuation handling.
- Ignore strong-assertion tokens only when they occur inside the narrow negated
  disclaimer pattern `不代表...已确认事实`; real claims such as `已确认订单` still
  trigger the advisory warning.

## Failure Modes And Tests

- Source quote rewritten or dropped: renderer test checks both quotes and refs.
- Peer context presented as target fact: renderer test checks distinct peer lead.
- `此外` remains repeated: renderer test rejects generated `；此外，` chains.
- Strong claims hidden too broadly: prose tests require negated disclaimer to pass
  while a real `已确认` claim still warns.
- Existing owner-delta, formal-thin citation offsets or quality/source boundaries
  regress: focused and downstream suites must remain green.

## Scope

Runtime:

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_prose_quality.py`

Tests:

- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_report_prose_quality.py`

No producer, canonical pack, prompt, scoring, technical, risk, target,
recommendation, source-boundary or citation-generation changes.

## Approval And Self-Review

The user approved the display-only path with `推进`. Self-review found that a new
selector would duplicate the existing sentence-level owner-delta implementation,
so the design explicitly avoids material filtering. No placeholders, stock rules
or ambiguous fallback paths remain.
