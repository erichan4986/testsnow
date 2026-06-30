# Claude Notes — Periodic Report Fulltext As Synthesis Display Material (Phase A)

TDD implementation of the Round 2 design delta. Full-text periodic-report
material may optionally enter the **display** synthesis only; canonical
synthesis, core_facts, synthesis_text, synthesis_sources, risk scoring, and
Knowledge persistence all stay baseline.

## Files changed (source)

- `scripts/utils/report_skills/synthesis_skills.py`
  - `run()` now produces a baseline synthesis (canonical ctx keys) and, when
    `include_periodic_report_fulltext_in_synthesis` is True **and** eligible
    full-text items exist, a second enhanced synthesis written only to
    `synthesis_display` / `synthesis_display_sources` /
    `synthesis_text_with_periodic_report_fulltext`.
  - `_eligible_periodic_report_fulltext_items()` filters
    `periodic_report_fulltext_items` to `source_type ==
    periodic_report_fulltext_analysis`.
  - `_synthesize()` / `_build_synthesis_items()` accept `extra_items`, appended
    LAST so ordinary source numbering stays stable.
- `scripts/utils/synthesis_credit.py`
  - `derive_synthesis_usage()`: `source_type == periodic_report_fulltext_analysis`
    → `credit_tier=medium`, `usage=annual_report_material`,
    `display_label=中信用/annual_report_material` (checked after the
    high-credit-confirmed gate, which 75-credit full text never passes).
  - `format_synthesis_source_line()`: excerpt cap 1200 for full text by
    source_type; 500 for everything else.
  - `is_core_fact_supporting_source()` unchanged — full text remains False
    (family不匹配 + credit 75 < 80).
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`
  - All three now read `ctx.get("synthesis_display") or ctx.get("synthesis")`.

## Tests added

- `tests/reporter/test_synthesis_skills.py`: default-off exclusion, canonical
  baseline kept, synthesis_text/core_facts baseline, knowledge-receives-baseline,
  append-last order preservation, no-items-skips-display.
- `tests/utils/test_synthesis_credit.py`: full-text usage = annual_report_material,
  not core-fact supporting, 1200 cap for full text, 500 cap for ordinary.
- `tests/reporter/test_deep_analysis_renderer.py`,
  `tests/reporter/test_executive_summary_renderer.py`,
  `tests/reporter/test_html_dashboard_renderer.py`: prefer synthesis_display,
  fall back to synthesis.
- `tests/reporter/test_scoring_engine_risk.py`: risk keyword scan uses baseline
  synthesis_text only (invariant assertion).

## Invariants verified by tests

- `ctx["synthesis"]` stays baseline; `ctx["synthesis_display"]` is enhanced.
- `ctx["synthesis_text"]` stays baseline even when enhanced narrative carries
  降价 / 毛利率承压 / 净流出.
- `ctx["core_facts"]` stays baseline.
- Risk scoring path receives baseline synthesis_text → no full-text leak.
- Knowledge writer (unmodified) reads baseline `ctx["synthesis"]` → no
  full-text-derived narrative persisted.

## Forbidden files untouched

scoring_engine.py, risk_renderer.py, knowledge_skills.py,
KnowledgeSynthesizer prompt, claim_risk_signal_skill.py,
source_intake_merge_skill.py, evidence_note_writer.py — none modified.

## Deviations / blockers

None. No forbidden file required changes; display renderers consume
`synthesis_display` without any report-assembly restructuring.
