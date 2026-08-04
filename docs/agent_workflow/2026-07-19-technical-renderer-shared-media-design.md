# Technical Renderer Shared Media Design

## Goal

Preserve the technical chart for full, core-only, and legacy technical projections while removing the duplicated chart-format block.

## Design

- Add one `_technical_chart_lines(stock_name, ctx)` projection helper.
- Full judgment projection appends the helper output after target judgment.
- Core-only judgment projection appends the same helper output instead of returning before shared media.
- Legacy projection appends the same helper output.
- No judgment, target, chart-generation, scoring, or report-layout policy changes.

## Test Contract

- Existing chart integration test is the RED case: chart generators run but Markdown lacks the technical image.
- Add a focused renderer test for a valid core judgment without interpretation and a populated chart path.
- Existing full/compact/legacy renderer tests must remain green.

## Stop Conditions

- The fix requires changes outside `technical_renderer.py` and its focused tests.
- Any technical judgment wording or target projection changes.
- The chart is duplicated in one projection mode.
