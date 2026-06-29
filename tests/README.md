# Test Suite Layout

The full test suite is intentionally broad and includes report rendering,
technical analysis, external-material previews, entrypoint smoke tests, and
legacy phase regressions.  For normal report work, prefer a scoped command
instead of running every file under `tests/reporter`.

## Recommended Commands

Fast report-core regression:

```bash
python3 -m pytest tests/reporter -m "report_core and not slow and not legacy" -q
```

Curated external / 4.4 focused regression:

```bash
python3 -m pytest \
  tests/utils/test_curated_external_full_body_viewpoint_claims.py \
  tests/utils/test_curated_external_viewpoint_narrative.py \
  tests/reporter/test_curated_external_full_body_viewpoint_preview.py \
  tests/reporter/test_curated_external_viewpoint_narrative_preview.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_deep_analysis_renderer.py \
  -q
```

External-material subsystem tests:

```bash
python3 -m pytest tests/reporter -m "external_material and not slow and not legacy" -q
```

Broader non-slow regression:

```bash
python3 -m pytest tests -m "not slow and not legacy" -q
```

Full regression, including slow tests and any future legacy tests:

```bash
python3 -m pytest
```

## Markers

- `report_core`: fast report-generation, synthesis, renderer, scoring, and risk tests.
- `external_material`: Agent-Reach, WeChat, broker, periodic, or curated external material flows.
- `integration`: entrypoint, pipeline, chart, PDF, or cross-module integration tests.
- `slow`: expensive rendering, large fixtures, or broader integration paths.
- `legacy`: historical tests kept for regression reference when they are still
  present in the active tree.

Markers are assigned centrally in `tests/conftest.py` based on test file names.
