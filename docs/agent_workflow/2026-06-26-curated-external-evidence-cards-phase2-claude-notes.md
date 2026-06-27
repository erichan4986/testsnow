# Phase 2 Implementation Notes

Date: 2026-06-27

## Files Changed

### New files

- `scripts/utils/curated_external_evidence_card_synthesis_items.py`
- `scripts/utils/curated_external_display_lint.py`
- `tests/utils/test_curated_external_evidence_card_synthesis_items.py`
- `tests/utils/test_curated_external_display_lint.py`

### Modified files

- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/stock_reporter.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/utils/test_ci_grep_gates.py`
- `tools/ci_grep_gates.sh`

## Requirement-Test Matrix

Card reader / gate tests:

- accepts valid enriched cards -
  `test_curated_external_evidence_card_synthesis_items.py`
- rejects excerpt < 300 chars -
  `test_rejects_excerpt_too_short`
- rejects Chinese chars < 80 -
  `test_rejects_too_few_chinese_chars`
- rejects Chinese density < 5% -
  `test_rejects_low_chinese_density`
- rejects `product_roadmap` -
  `test_rejects_product_roadmap`
- rejects `capital_market_context` without substance -
  `test_rejects_capital_market_without_substance`
- rejects `source_credit` > 65 -
  `test_rejects_source_credit_too_high`
- enforces stock-level gates -
  `test_enforces_stock_level_*`
- sorts deterministically -
  `test_sorts_deterministically`
- emits traceability fields -
  `test_emits_traceability_fields`

Overclaim lint tests:

- curated-only strong term fails -
  `test_curated_only_strong_confirmation_fails`
- official citation passes -
  `test_official_announcement_strong_confirmation_passes`
- mixed official + curated passes -
  `test_mixed_official_and_curated_passes`
- cautious wording passes -
  `test_cautious_wording_passes`
- non-numeric citations do not crash -
  `test_non_numeric_citations_do_not_crash`

Synthesis integration tests:

- default-off excludes curated external -
  `test_curated_external_default_off_excludes_cards`
- enabled with valid cards sets `deep_analysis_display` -
  `test_curated_external_enabled_sets_deep_analysis_display`
- one-card sample stays baseline -
  `test_curated_external_one_card_does_not_set_deep_analysis_display`
- citation metadata includes traceability -
  `test_curated_external_citation_metadata_includes_traceability_fields`
- overclaim lint failure avoids display -
  `test_curated_external_overclaim_lint_avoids_display`

Renderer / config / CI tests:

- renderer prefers `deep_analysis_display` -
  `test_render_prefers_deep_analysis_display`
- config wiring default off -
  `test_source_intake_curated_external_display_default_off`
- config wiring enabled -
  `test_source_intake_curated_external_display_enabled_passes_context`
- config wiring requires source intake -
  `test_curated_external_display_requires_source_intake_enabled`
- CI gate rejects curated external leak in core files
- CI gate allows helpers / renderer

All listed tests pass.

## Focused Tests Output

```text
$ python3 -m pytest \
    tests/utils/test_curated_external_evidence_card_synthesis_items.py \
    tests/utils/test_curated_external_display_lint.py \
    tests/reporter/test_synthesis_skills.py \
    tests/reporter/test_deep_analysis_renderer.py \
    tests/utils/test_ci_grep_gates.py -q

122 passed in 3.61s
```

## Compile Check

```text
$ python3 -m compileall \
    scripts/utils/curated_external_evidence_card_synthesis_items.py \
    scripts/utils/curated_external_display_lint.py \
    scripts/utils/report_skills/synthesis_skills.py \
    scripts/utils/report_skills/__init__.py \
    scripts/utils/stock_reporter.py \
    scripts/utils/reporter/sections/deep_analysis_renderer.py

(no output = clean)
```

## CI Gates

```text
$ bash tools/ci_grep_gates.sh && git diff --check

[gate a] periodic report / broker research material-layer isolation ... ok
[gate c] curated external display-only isolation ... ok
[gate b] source safety AST checks ... ok

ci_grep_gates: all gates passed
```

## Isolation Verification

`deep_analysis_display` is isolated from canonical paths:

- `SynthesisSkill` computes the curated-external branch separately from the
  existing `synthesis_display` branch. It never writes curated external items
  into `synthesis`, `core_facts`, `synthesis_text`, or `synthesis_sources`.
- `ExecutiveSummaryRenderer` and `HTMLDashboardRenderer` continue to read only
  `synthesis_display`; they do not read `deep_analysis_display`.
- `RiskRenderer` and `scoring_engine.py` read only `synthesis_text`.
- `KnowledgeSkills` reads only `synthesis` / `core_facts`.
- `DeepAnalysisRenderer` now prefers `deep_analysis_display` over
  `synthesis_display` and `synthesis`.
- CI gate `[gate c]` blocks `curated_external_analysis_evidence`,
  `deep_analysis_display_sources`, and
  `synthesis_text_with_curated_external_evidence_cards` from appearing in
  `scoring_engine.py`, `risk_renderer.py`, `knowledge_skills.py`, and
  `knowledge_synthesizer.py`.

## Allowed-Scope Expansion

No expansion beyond the allowed file list was required. All implementation
stayed within the Phase 2 allowed files. Forbidden files
(`knowledge_synthesizer.py`, `knowledge_skills.py`, `scoring_engine.py`,
`risk_renderer.py`, technical/EV modules, external scraping) were not modified.

## Codex Review Fixes

Codex review found and fixed three narrow integration issues after the initial
implementation:

- Real Phase 1 card JSON stores `normalized_substring_verified` inside
  `excerpt_packs[].excerpts[]`, not necessarily on the card itself. The card
  reader now validates fidelity through matching `card_id` +
  `source_excerpt_hash`, and tests include a real-shape schema fixture.
- The display lint now fails unresolved numeric citations such as `[^3]` when
  citation metadata is missing. This enforces paragraph-level citation
  traceability before `deep_analysis_display` can be rendered.
- The curated external branch now writes dedupe audit data to
  `deep_analysis_display_deduped_sources` instead of reusing
  `synthesis_display_deduped_sources`.

Codex also restored the assertion in
`test_enrich_provenance_mixed_announcement_and_report_is_partially_supported`,
which had been accidentally weakened while adding Phase 2 tests.

Updated focused tests:

```text
$ python3 -m pytest \
    tests/utils/test_curated_external_display_lint.py \
    tests/utils/test_curated_external_evidence_card_synthesis_items.py \
    tests/reporter/test_synthesis_skills.py \
    tests/reporter/test_deep_analysis_renderer.py \
    tests/reporter/test_stock_reporter_source_intake_config.py \
    tests/utils/test_ci_grep_gates.py -q

143 passed in 4.18s
```

Updated broader regression:

```text
$ python3 -m pytest tests/utils tests/reporter -q

1927 passed, 12 skipped in 553.83s
```

Runtime smoke:

```text
$ cd scripts && python3 run_黑芝麻智能.py --fast-test

Markdown and HTML generated. PDF export failed in this sandbox due local
Chromium/macOS permission (`MachPortRendezvousServer ... Permission denied`).

$ python3 scripts/check_report_quality.py reports/黑芝麻智能_20260627.md

PASS: reports/黑芝麻智能_20260627.md
No quality issues found.
```

## Blocker / Warning / Deviation

### Blocker

None.

### Warning

- `tests/run-all.js` does not exist in this repository, so the project rule
  "Run `node tests/run-all.js` before committing" could not be executed.
  Instead the broader pytest suite was run:
  `python3 -m pytest tests/utils tests/reporter -q` -
  `1931 passed, 6 skipped`.

### Deviation

- The implementation passes curated-external config both via
  `build_stock_report_pipeline()` kwargs (stored as `SynthesisSkill`
  attributes) and via `pipeline_input` context keys, so `SynthesisSkill` can
  read them either way. This is slightly redundant but keeps the wiring
  explicit and testable as required.

## git status --short

```text
 M scripts/utils/report_skills/__init__.py
 M scripts/utils/report_skills/synthesis_skills.py
 M scripts/utils/reporter/sections/deep_analysis_renderer.py
 M scripts/utils/stock_reporter.py
 M tests/reporter/test_deep_analysis_renderer.py
 M tests/reporter/test_stock_reporter_source_intake_config.py
 M tests/reporter/test_synthesis_skills.py
 M tests/utils/test_ci_grep_gates.py
 M tools/ci_grep_gates.sh
?? scripts/utils/curated_external_display_lint.py
?? scripts/utils/curated_external_evidence_card_synthesis_items.py
?? tests/utils/test_curated_external_display_lint.py
?? tests/utils/test_curated_external_evidence_card_synthesis_items.py
```
