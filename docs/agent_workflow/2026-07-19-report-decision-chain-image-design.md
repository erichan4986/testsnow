# Report Decision Chain Image Design

## 1. Goal

Generate one deterministic investment-decision image for each stock report and
embed it in Markdown/PDF as the primary executive-summary projection.

The image must consolidate existing structured conclusions without recomputing
scores, targets, risk, technical judgments, position limits, or recommendations.

## 2. Current-State Audit

- The five-pillar radar is readable and remains useful in the HTML Dashboard.
- Current bull/bear images are empty when no arguments are available. They must
  not be generated or embedded in that state.
- Current technical images may render scalar MACD/RSI values as flat or empty
  panels. Such images are not decision-useful and must fail the display gate.
- `pdf_exporter.py` supports images, but temporary HTML rendering needs explicit
  local-image URI resolution and image-load waiting for reliable PDF output.
- Adding another full summary image beside the current three-paragraph summary
  would duplicate content. The image therefore replaces that projection rather
  than adding a fourth summary representation.

## 3. User-Approved Projection

Use a vertical decision chain:

1. Fundamental signal
2. Valuation and earnings expectation
3. Technical state and risk constraint
4. Current action

The header contains only total score, EV, risk level, and position cap. Evidence
boundary caveats remain in the report body and do not occupy the decision image.

When the image is available, the executive summary renders:

- the section title;
- one concise recommendation sentence;
- the decision-chain image.
- the optional cited `近期待验证变量` line after the image.

It does not render the current three explanatory paragraphs, the standalone
radar image, or the bull/bear image. Detailed score, target, and evidence tables
remain in later report sections.

When the view model is available but image generation fails, the renderer emits
the same four decision-chain nodes as compact text. It does not restore the old
three-paragraph summary or its evidence-boundary caveat. The old renderer path
is retained only for direct/legacy callers that do not provide the view model.

## 4. Single Source of Truth

Introduce one immutable `ExecutiveSummaryViewModel` built from values already
present in `SkillContext`:

- `RecommendationDecision` for recommendation, risk level, and position cap;
- pillar/total score for total and fundamental scores;
- consensus/pillar values for Forward PE and EPS growth;
- technical judgment for stage, health, and confidence;
- existing EV result exposed by the recommendation/scoring path.

The view model contains presentation-ready scalar values and short deterministic
labels. It does not parse rendered Markdown or LLM prose.

Both the image generator and the executive-summary fallback renderer consume
this same view model. No second recommendation or score owner is allowed.

Field ownership is explicit:

- total score and EV come from `RecommendationDecision`;
- risk level comes from `RecommendationDecision.risk.level`;
- position cap is extracted only from the already-rendered
  `entry_constraint.position_cap_note`, with `risk.position_advice` as a
  display-only fallback; no state-to-position policy is duplicated;
- fundamental score, Forward PE, and EPS growth come from `pillar`;
- technical stage and health come from
  `stock_raw.technical.indicators._resonance`;
- recommendation and action text come from `RecommendationDecision`.

## 5. Data Flow

1. `ReportAssemblySkill` ensures the existing `RecommendationDecision` is built.
2. It builds `ExecutiveSummaryViewModel` once and stores it in `SkillContext`.
3. It calls the decision-chain image generator before section rendering.
4. On success, the generated path is stored as
   `chart_paths["executive_summary"]`.
5. `ExecutiveSummaryRenderer` uses image-first projection with deterministic
   text fallback.
6. `export_pdf()` resolves local image sources relative to the Markdown file,
   converts them to file URIs, and waits for local images to finish loading.

Image generation is an assembly artifact. Renderers remain free of file-writing
side effects. The output filename includes stock name and report date so a later
run cannot change the image referenced by an older report.

Direct `_assemble_markdown()` callers without `output_dir` or `date_str` build
the view model but skip file generation and receive the compact text fallback.

## 6. Image Content

The PNG is portrait-oriented and A4-safe. It contains:

- stock name, report date, and recommendation status;
- total score, EV, risk level, and position cap;
- fundamental node: score-strength label and one available growth metric;
- valuation node: Forward PE/PE(TTM), EPS growth, and target source/status;
- technical/risk node: trend stage, health score, risk, and position cap;
- final action node copied from the unified recommendation decision;
- a small footer directing readers to detailed evidence and citations.

The generator reuses the repository's existing Plotly/Kaleido stack. It does
not introduce Pillow, browser screenshot generation, or another media runtime.

Long values are compacted by deterministic length limits. The generator must
not invent a missing value. Missing optional fields are rendered as
`证据不足`; if fewer than two substantive chain nodes can be built, no image is
generated and the renderer falls back to text.

Admission and formatting are deterministic:

- the fundamental node is substantive when fundamental score or EPS growth is
  present; score labels are `较强` at 8+, `中性偏强` at 6+, `中性` at 4+, and
  `偏弱` below 4;
- the valuation node is substantive when Forward PE, PE(TTM), or canonical EV
  targets are present;
- the technical/risk node is substantive when trend stage/health, risk level,
  or position cap is present;
- CJK text wraps at fixed character boundaries, with at most two detail lines
  per node and no ellipsis inside numeric values;
- the output canvas is fixed at 1240 x 1600 pixels.

The Markdown image has meaningful alt text containing the stock name and final
recommendation. The one-line textual conclusion is intentionally retained for
search, accessibility, and the existing executive-summary quality gate.

## 7. Existing Media Policy

### 7.1 Radar

- Keep standalone radar generation for the HTML Dashboard.
- Remove standalone radar embedding from Markdown/PDF.
- Fix Dashboard media paths to use filenames relative to the generated HTML,
  because chart files and Dashboard HTML share the same output directory.

### 7.2 Bull/Bear

- Do not generate a chart when both argument lists are empty.
- Remove bull/bear embedding from the executive summary.
- The HTML Dashboard may retain a non-empty chart.

### 7.3 Technical Chart

Embed the technical chart only when:

- OHLC series are aligned and contain at least 60 observations;
- volume, when rendered, is aligned with OHLC;
- MACD is rendered only when MACD, signal, and histogram are aligned series;
- RSI is rendered only when it is an aligned series;
- the dynamically selected chart contains price plus at least one other
  meaningful panel.

The gate affects display only. It does not change indicator calculations or the
technical judgment. `chart_generator.py` dynamically creates only admitted
panels and no longer repeats scalar snapshots across the time axis. Its
generator returns no path when fewer than two panels are admissible. The
technical chart skill stores that result, while `TechnicalRenderer` continues
to embed only a non-empty chart path.

## 8. PDF Reliability

- Resolve absolute and Markdown-relative local image paths to `file://` URIs.
- Preserve remote URLs unchanged.
- Raise a clear `FileNotFoundError` for a referenced local image that does not
  exist instead of silently exporting a PDF with a blank image.
- Wait until all local images report `complete` and non-zero `naturalWidth`
  before calling `page.pdf()`.
- Retain existing A4 image sizing and `object-fit: contain` CSS.

## 9. Failure Modes

| Failure | Required behavior | Test |
|---|---|---|
| Image generator raises | Render compact textual decision chain from the same view model | Renderer fallback test |
| View model lacks two substantive nodes | Do not generate/embed image | View-model admission test |
| Empty bull/bear arguments | No PNG and no Markdown reference | Chart skill test |
| Scalar-only MACD/RSI creates fake panels | Omit those panels; suppress chart if fewer than two panels remain | Technical chart gate test |
| Local relative image path | PDF HTML contains resolved file URI | PDF exporter test |
| Missing local image | Export validation exposes failure | PDF exporter negative test |
| Long Chinese label | Text remains within fixed image bounds | Generator fixture test |
| Image and fallback drift | Both consume identical view model fields | Contract test |
| Cited freshness variable disappears | Keep the original cited line outside the image | Renderer regression test |
| Dashboard points at nonexistent `charts/` directory | Render same-directory relative filenames | Dashboard test |
| Image-only summary bypasses readability gate | Keep one non-empty `一句话结论` line | Report-quality integration test |

## 10. Scope

Expected runtime files:

- `scripts/utils/reporter/chart_generator.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/composite_score_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`
- `scripts/utils/report_skills/chart_skills.py`
- `scripts/utils/pdf_exporter.py`

Corresponding focused test files may be modified. A small dedicated summary
view-model module is allowed if it keeps assembly and renderer responsibilities
smaller than embedding the model in either file.

The expected dedicated module is
`scripts/utils/reporter/executive_summary_view.py`; it owns only immutable view
data and deterministic projection labels, not report decisions or file output.

## 11. Non-Goals

- No scoring, target-price, risk-score, technical-indicator, EV, position, or
  recommendation-rule changes.
- No LLM prompt or synthesis changes.
- No data collection or profile-routing changes.
- No AI-generated decorative artwork.
- No report run or network access during implementation.

## 12. Verification

- Focused unit tests for the view model, generator, chart skill, renderer, and
  PDF image resolution.
- Reporter chart integration tests.
- Existing executive summary, recommendation decision, technical renderer, and
  PDF exporter tests.
- Full test suite, `tools/ci_grep_gates.sh`, and `git diff --check`.
- After code acceptance, generate one local sample report and visually inspect
  Markdown, HTML, and PDF. Browser/PDF verification may run locally if Chromium
  is unavailable in the sandbox.

## 13. Stop Conditions

Stop and return to design if implementation requires:

- a second score/recommendation calculation path;
- changing pipeline order outside report-media preparation;
- changing technical indicator algorithms;
- adding a new large dependency;
- modifying files outside the approved report/chart/PDF surface.

Runtime target is at most +220 net lines across the approved runtime surface;
stop and return to design above +280 net lines. Tests and design notes are not
part of this runtime budget.

## 14. Self-Review Delta

### Round 1

- Added `CompositeScoreRenderer` to scope because it owns standalone radar
  embedding in Markdown/PDF.
- Replaced the ambiguous technical-image gate with exact dynamic-panel rules;
  scalar MACD/RSI values can no longer be repeated as fake time series.
- Changed image-failure behavior from the old three-paragraph summary to a
  compact textual projection of the same view model.
- Required date-stamped decision-image filenames to prevent historical report
  references from drifting after later runs.

### Round 2

- Preserved the optional cited freshness variable outside the image so summary
  visualization cannot remove traceable external evidence.
- Locked every view-model field to its current structured owner and prohibited
  a duplicated state-to-position mapping.
- Added the existing Dashboard same-directory chart-path defect to scope so the
  retained radar is actually visible.
- Retained a textual `一句话结论` for accessibility and the current quality gate.
- Added a +220 target and +280 hard stop for runtime growth.
