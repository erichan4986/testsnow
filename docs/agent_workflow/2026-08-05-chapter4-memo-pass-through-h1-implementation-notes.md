# Chapter 4 Memo Pass-Through H1 Implementation Notes

## Verdict

`PASS`

H1 removed the annual/broker memo intermediate runtime schemas and made the
Chapter 4 snapshot the only formal-material preparation and row-projection
owner. H2 content-policy changes were not included.

## Modified Files

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/report_skills/synthesis_skills.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/utils/test_external_v4_snapshot.py`
- `tests/test_runtime_hygiene.py`

## RED / GREEN

- Direct formal projection: two tests failed because the diagnostics API did
  not exist and snapshot still read memo ctx keys; both passed after direct
  annual/broker projection and keyed citation allocation.
- Synthesis orchestration: two of three tests failed because diagnostics and
  stored empty broker items were absent; all three passed after one-load
  orchestration and removal of memo ctx writes.
- Obsolete memo-schema tests were removed. Canonical projection tests now own
  status, cleanup, exact dedupe, source preservation, zero-metric warning,
  unique citation keys, broker admission, six-row projection, and offsets.

## Requirement / Test Matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Current annual cards precede persisted pack | `_prepare_annual_material` | direct projection precedence test |
| Canonical family admission and exact body dedupe | `_prepare_annual_material` | annual canonical cleanup/dedupe test |
| Existing cleanup and 300-char bound | `_clean_annual_excerpt` | OCR/traditional text and bounded-body assertions |
| Suspicious zero fact behavior | `_is_suspicious_zero_metric` | zero warning/filter assertions |
| Broker guards/status/all-usable diagnostics | `_prepare_broker_material` | direct diagnostics and seven-item test |
| Broker first-six display compatibility | `_prepare_broker_material` | seven usable / six projected assertion |
| Stable SHA source ids and mixed-order refs | `_broker_source_id`, `_CitationAllocator.allocate` | source hash and 7/8/9 ref-order test |
| External refs start after full formal snapshot | allocator offset path | external ref 10 and v4 offset tests |
| One broker loader call, including empty result | `SynthesisSkill.run` | loader call-count tests |
| No memo schema/builder/raw ctx read | runtime hygiene gate | Batch H1 hygiene test and `rg` audit |
| Profile/coverage compatibility keys retained | diagnostics-backed profile/coverage | synthesis profile and coverage tests |

## Runtime Numstat

Against `e504cb9`:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 338 | 91 | +247 |
| `report_skills/synthesis_skills.py` | 34 | 392 | -358 |
| **Combined** | **372** | **483** | **-111** |

The locked minimum reduction of 110 runtime lines was met. No second formal
eligibility owner remains.

## Verification

- H1 focused suite: `267 passed`
- Full pytest: `2857 passed, 10 skipped`
- `tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean
- Runtime memo-schema/name scan: no schema, builder, or raw ctx-read hits

## Three-Stock Baseline Comparison

The old `e504cb9` memo builders were loaded from `git show` in memory and run
against the same local canonical packs. No network, LLM, report generation, or
file writes were used.

| Stock | Annual status / rows | Broker status / rows | Citations | Comparison |
|---|---|---|---:|---|
| 中际旭创 | ready / 60 | ready / 4 | 23 | annual title/body/source ids equal; broker body/source ids equal |
| 复旦微电 | ready / 68 | absent / 0 | 17 | equal |
| 黑芝麻智能 | ready / 59 | absent / 0 | 19 | equal |

Row counts and citation counts matched the old path for all three stocks.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: compatibility output field names containing `memo_` remain in the
  evidence profile, material coverage, and `MaterialRow`; they no longer refer
  to runtime memo objects.
- Warning: the annual 300-character display bound and broker first-six bound
  remain intentionally unchanged for H2.
- Deviation: no report rerun was performed because H1 is a deterministic
  ownership refactor and the locked task prohibited report/data/Knowledge
  changes.

## Acceptance

`H1 accepted: yes`
