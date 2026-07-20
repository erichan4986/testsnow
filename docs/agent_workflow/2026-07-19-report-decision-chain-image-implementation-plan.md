# Report Decision Chain Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a deterministic vertical investment-decision image, use it as the primary executive-summary projection, suppress low-value charts, and make local images reliable in PDF output.

**Architecture:** A dedicated immutable view model reads only existing structured report decisions and metrics. Report assembly creates the view once, generates a date-stamped Plotly/Kaleido PNG, and gives the same view to the image-first/text-fallback renderer. Existing radar remains Dashboard-only; bull/bear and technical charts are admitted only when useful.

**Tech Stack:** Python dataclasses, Plotly/Kaleido, Markdown, Playwright, pytest.

---

## File Structure

- Create `scripts/utils/reporter/executive_summary_view.py`: immutable view data, deterministic labels, compact text fallback.
- Modify `scripts/utils/reporter/chart_generator.py`: decision-chain generator and dynamic technical-panel admission.
- Modify `scripts/utils/report_skills/assembly_skills.py`: build the view and generate the dated image before renderers run.
- Modify `scripts/utils/reporter/sections/executive_summary_renderer.py`: image-first projection and view-based fallback.
- Modify `scripts/utils/reporter/sections/composite_score_renderer.py`: stop embedding standalone radar in Markdown/PDF.
- Modify `scripts/utils/report_skills/chart_skills.py`: skip empty bull/bear images and accept an omitted technical image.
- Modify `scripts/utils/reporter/sections/html_dashboard_renderer.py`: use same-directory chart filenames.
- Modify `scripts/utils/pdf_exporter.py`: resolve local image URIs and wait for local image loading.
- Add/modify focused tests under `tests/reporter/` and `tests/utils/`.

## Task 1: Canonical Executive Summary View

**Files:**
- Create: `scripts/utils/reporter/executive_summary_view.py`
- Create: `tests/reporter/test_executive_summary_view.py`

- [ ] **Step 1: Write failing view-model tests**

Test a complete context and assert:

```python
view = build_executive_summary_view(ctx)
assert view.total_score == "5.3 / 10"
assert view.ev == "+39.48%"
assert view.risk_level == "中等风险"
assert view.position_cap == "0-5%"
assert view.fundamental.title == "结构化基本面信号较强"
assert view.valuation.detail == "Forward PE 37.8x｜预期 EPS 增速 +65.5%"
assert view.technical.title == "趋势失效 / 破坏期"
assert view.image_ready is True
```

Also test missing fields, position extraction from existing decision text, no state-to-cap mapping, and fewer than two substantive nodes.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_executive_summary_view.py -q -p no:cacheprovider
```

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement the minimal immutable view model**

Use frozen dataclasses for the view and three nodes. Read total score/EV/risk/action from `RecommendationDecision`, score/valuation values from `pillar`, and technical state from `stock_raw.technical.indicators._resonance`. Extract only an already-rendered percentage range from position text.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 command. Expected: all Task 1 tests pass.

## Task 2: Decision-Chain PNG Generator

**Files:**
- Modify: `scripts/utils/reporter/chart_generator.py`
- Modify: `tests/reporter/test_chart_generator.py`

- [ ] **Step 1: Write failing generator tests**

Add tests that generate a PNG from the complete view, assert the returned path/file, assert fixed 1240 x 1600 export arguments, and test deterministic two-line CJK wrapping without splitting numeric values.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_chart_generator.py -q -p no:cacheprovider
```

Expected: failure because `generate_decision_chain_chart` is missing.

- [ ] **Step 3: Implement the Plotly decision chain**

Create a white/quiet-blue portrait figure with a status strip, three numbered nodes, arrows, final action band, and footer. Use only view-model strings. Keep shapes/annotations in one function and a small deterministic wrapping helper.

- [ ] **Step 4: Verify GREEN**

Run the Task 2 command. Expected: all chart-generator tests pass.

## Task 3: Assembly and Executive Summary Projection

**Files:**
- Modify: `scripts/utils/report_skills/assembly_skills.py`
- Modify: `scripts/utils/reporter/sections/executive_summary_renderer.py`
- Modify: `tests/reporter/test_assembly_skills.py`
- Modify: `tests/reporter/test_executive_summary_renderer.py`
- Modify: `tests/reporter/test_report_quality.py`

- [ ] **Step 1: Write failing integration tests**

Cover:

- assembly stores one view and a date-stamped `chart_paths["executive_summary"]`;
- direct assembly without output directory skips PNG generation;
- image success renders only heading, `一句话结论`, image, and optional cited freshness line;
- image success omits the old three paragraphs and bull/bear section;
- image failure renders the compact textual chain from the same view;
- the image-first summary still passes `empty_executive_summary_body` quality gate.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_executive_summary_renderer.py tests/reporter/test_report_quality.py -q -p no:cacheprovider
```

Expected: new assertions fail because no view/image projection exists.

- [ ] **Step 3: Implement assembly preparation and renderer projection**

Factor the existing recommendation-decision preparation only enough to build the view immediately afterward. Copy/update `chart_paths`; catch image-generation errors and leave the executive-summary path empty. Preserve legacy rendering only when the view is absent.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 command. Expected: all selected tests pass.

## Task 4: Existing Chart Admission and Markdown Cleanup

**Files:**
- Modify: `scripts/utils/reporter/chart_generator.py`
- Modify: `scripts/utils/report_skills/chart_skills.py`
- Modify: `scripts/utils/reporter/sections/composite_score_renderer.py`
- Modify: `tests/reporter/test_chart_generator.py`
- Modify: `tests/reporter/test_chart_skills.py`
- Modify: `tests/reporter/test_composite_score_renderer.py`
- Modify: `tests/reporter/test_stock_reporter_charts.py`

- [ ] **Step 1: Write failing media-policy tests**

Test that empty bull/bear inputs do not call the generator, standalone radar is absent from Markdown, scalar MACD/RSI values are not rendered, price plus aligned volume creates a compact two-panel chart, and fewer than two meaningful panels returns no path.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_chart_generator.py tests/reporter/test_chart_skills.py tests/reporter/test_composite_score_renderer.py tests/reporter/test_stock_reporter_charts.py -q -p no:cacheprovider
```

Expected: failures for empty bull/bear generation, radar Markdown embedding, and fixed four-panel technical behavior.

- [ ] **Step 3: Implement minimal policy changes**

Make technical subplots dynamic. Price is required; volume/MACD/RSI are admitted only by the design contract. Remove scalar repetition. Return `None` when fewer than two panels remain. Gate bull/bear generation on at least one argument and remove radar projection from `CompositeScoreRenderer`.

- [ ] **Step 4: Verify GREEN**

Run the Task 4 command. Expected: all selected tests pass.

## Task 5: Dashboard Media Paths

**Files:**
- Modify: `scripts/utils/reporter/sections/html_dashboard_renderer.py`
- Modify: `tests/reporter/test_html_dashboard_renderer.py`

- [ ] **Step 1: Write failing path test**

Provide chart paths and assert generated HTML contains `src='测试股_radar.png'` and does not contain `src='charts/`.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_html_dashboard_renderer.py -q -p no:cacheprovider
```

Expected: failure because the renderer prefixes `charts/`.

- [ ] **Step 3: Use same-directory relative filenames**

Remove the hard-coded `charts/` prefix for technical, bull/bear, radar, and valuation paths.

- [ ] **Step 4: Verify GREEN**

Run the Task 5 command. Expected: all Dashboard tests pass.

## Task 6: PDF Local Image Reliability

**Files:**
- Modify: `scripts/utils/pdf_exporter.py`
- Modify: `tests/utils/test_pdf_exporter.py`

- [ ] **Step 1: Write failing resolver tests**

Test absolute and Markdown-relative local images, raw HTML `<img>` sources, unchanged HTTPS/data sources, and a clear `FileNotFoundError` for a missing local image. Mock Playwright to assert export passes the Markdown directory and waits for local images before `page.pdf()`.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_pdf_exporter.py -q -p no:cacheprovider
```

Expected: failure because local source resolution is not implemented.

- [ ] **Step 3: Implement URI resolution and load wait**

Add optional `base_dir` to `_md_to_html`, rewrite controlled `<img src>` attributes after Markdown conversion, pass `md_file.parent` from `export_pdf`, and wait only for local `file:` images to be complete with non-zero natural width.

- [ ] **Step 4: Verify GREEN**

Run the Task 6 command. Expected: all PDF exporter tests pass.

## Task 7: Refactor, Budget, and Verification

**Files:**
- Modify only approved runtime/tests/docs if cleanup is needed.

- [ ] **Step 1: Remove duplication while green**

Keep one view builder, one image generator, one technical-panel admission path, and one local-image resolver. Do not add generic media frameworks.

- [ ] **Step 2: Measure runtime growth**

Use `git diff --numstat` for approved runtime files. Target <= +220 net; stop above +280 net.

- [ ] **Step 3: Run focused regression suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_executive_summary_view.py \
  tests/reporter/test_chart_generator.py \
  tests/reporter/test_chart_skills.py \
  tests/reporter/test_assembly_skills.py \
  tests/reporter/test_executive_summary_renderer.py \
  tests/reporter/test_composite_score_renderer.py \
  tests/reporter/test_html_dashboard_renderer.py \
  tests/reporter/test_stock_reporter_charts.py \
  tests/reporter/test_report_quality.py \
  tests/utils/test_pdf_exporter.py -q -p no:cacheprovider
```

- [ ] **Step 4: Run full verification**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 5: Defer report/PDF generation until code acceptance**

Do not use network, LLM, Chrome login, or formal report generation in this implementation batch. After acceptance, run one local sample and visually inspect the PNG and PDF.

## Stop Conditions

- Runtime growth exceeds +280 net lines.
- A second score/recommendation/position policy is required.
- Technical indicator algorithms must change.
- A new media dependency is required.
- Implementation needs files outside the approved report/chart/PDF surface.
