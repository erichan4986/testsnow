# Chapter 4 External Topic Grouping Design

## Goal

Make Chapter 4.3 read as a small number of coherent topic blocks instead of a
sequence of cards with repeated headings and repeated framing text.

## Scope

- Change only the shared formal-medium/formal-thin 4.3 projection in
  `deep_analysis_renderer.py` and its focused tests.
- Keep target-company observations before peer/industry background.
- Within each entity scope, group rows by canonical display title in this order:
  需求与客户、商业化进展、技术与产品、财务质量、竞争格局、供应链与交付、政策与地缘、估值与预期、其他。
- Render each topic heading once and preserve source order within the topic.
- Keep the existing row-level external/verification framing and inline citations
  on every visible paragraph; only the duplicated topic headings are collapsed.

## Non-Goals

- No producer, pack, taxonomy, material selection, dedupe, card count, citation
  allocation, scoring, risk, target, recommendation, or LLM prompt changes.
- No table layout and no display cap.
- Do not change the formal-rich legacy 4.4 addendum in this batch.

## Rendering Contract

1. The existing section heading and Preview disclaimer remain unchanged.
2. Target rows render first under grouped topic headings.
3. The peer/industry disclaimer starts a separate scope; its rows are grouped
   independently and never merge with target rows.
4. Every row retains its existing relation framing so strong external claims
   remain auditable to line-oriented quality gates.
5. Multi-paragraph verified source units retain the same inline citation on each
   visible paragraph. Citation offsets are applied before grouping exactly as now.
6. Unknown/non-canonical titles sort after canonical topics and retain their
   first-seen order.

## Failure Modes And Tests

- Repeated topic headings: two target technology rows must produce one heading.
- Entity contamination: peer technology must remain after the peer disclaimer,
  not join target technology.
- Lost or moved citations: all source paragraphs retain their shifted footnotes.
- Hidden material: output contains every admitted row; grouping is stable and
  uncapped.
- Reordered arguments inside a topic: rows preserve input order.
- Scope creep: producer packs and Chapter4ViewModel rows remain byte-for-byte
  outside renderer projection.
