# Codex Round 2 Self-Review: Chapter 4 Annual Display Selection

日期：2026-07-13
结论：`ok`

## Verified

| Review item | Result | Evidence |
|---|---|---|
| B1 deterministic dedupe | closed | Design now permits exact normalized equality and same-role containment only. No fuzzy/token/embedding rule remains. |
| B2 formal-thin citation integrity | closed | Existing formal-thin builds a full snapshot before rendering, derives broker/external offsets from that full snapshot, then calls `_visible_citations_only()` over final Markdown. Selector rows retain snapshot refs and are never renumbered. |
| M1 4.4 annual selection | closed | Design requires role-priority selection and explicitly forbids arbitrary first-row fallback. |
| M2 portrait fallback | closed | Portrait can fall back only to selected operating/technology company descriptions, never confirmed financial rows or pure industry paragraphs. |
| M3 ownership split | closed | Selector owns admission and segment rejection; renderer retains only normalization, grouping, compacting and citation attachment. |
| M4 mixed row safety | closed | Segment-level projection preserves source-order high-value sentences while removing display-only clauses. |

## Additional Corrections

- `argument_complete` cannot be a 4.1 admission requirement. In both real stocks most v2 cards are atomic (`false`), including material that is useful in a report. It remains a 4.4 preference only.
- Do not extend `Chapter4ViewModel` to formal-thin. The view-model change would pull formal-thin 4.2/4.3 into a new citation/visibility path unnecessarily. Pass selected annual MaterialRows to a shared 4.1 formatter while retaining full snapshot offsets and existing 4.2/4.3 renderers.
- Do not add semantic display filters to `report_quality.py`; that would create a duplicate selector. Use focused selector/renderer tests plus existing report quality/source/citation gates.

## Scope / Budget

Runtime files remain limited to:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests remain limited to the snapshot and renderer suites. Target runtime net delta is `+80`; hard stop is `+120`, excluding docs/tests.

## Required Implementation Guards

1. Build the full snapshot before selection for formal-thin.
2. Never renumber MaterialRow refs after selection.
3. Test rejection of the highest annual ref while broker and external refs remain stable and resolvable.
4. Keep the full snapshot citation map until `_visible_citations_only()` prunes final Markdown citations.
5. A row with no retained segment must disappear; a mixed row with one retained segment must preserve that segment verbatim and keep its citation.

## Recommended Next Step

Write a compact implementation task, then hand off implementation through the user's manual model-switch workflow.
