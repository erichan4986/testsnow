# Public Compatibility Cleanup Batch F Audit

## Verdict

`PARTIAL_GO`: one detached external-preview group is safe to hard-delete. Public/manual compatibility surfaces require a separate explicit decision.

This audit is read-only with respect to runtime, tests, configuration, data, knowledge, and reports.

## F1: Safe Detached External Preview Group

| Runtime module | Lines | Repository callers |
| --- | ---: | --- |
| `scripts/utils/social_viewpoint_source_packets.py` | 227 | isolated test module only |
| `scripts/utils/curated_external_video_subtitles.py` | 313 | isolated test module only |
| `scripts/utils/curated_external_candidate_discovery.py` | 685 | isolated test module only |

Associated isolated tests total 790 lines:

- `tests/utils/test_social_viewpoint_source_packets.py` (180)
- `tests/utils/test_curated_external_video_subtitles.py` (147)
- `tests/utils/test_curated_external_candidate_discovery.py` (463)

Evidence:

- The candidate-discovery and video-subtitle preview CLIs were intentionally deleted in commit `48a893d`.
- The social viewpoint preview CLI was intentionally deleted during the v3 cutover in commit `cb35b7b`.
- No active runtime, preview, tool, README command, package export, or dynamic renderer registry imports these three modules.
- External Producer v4 is owned by `external_pack.py`, `external_scope.py`, `external_source_document.py`, and the active full-body viewpoint producer path.

Recommendation: delete the three modules and their three isolated test files in Batch F1. Runtime delta: **-1,225 lines**; test delta: **-790 lines**.

## F2: Manual/Public Surfaces Requiring Explicit Hard Cut

### Standalone utilities

| Module | Lines | Why not automatically safe |
| --- | ---: | --- |
| `scripts/utils/wechat_sogou_fetcher.py` | 222 | README-advertised manual browser collector with a `__main__` demo |
| `scripts/utils/judgment_generator.py` | 271 | README-advertised manual LLM utility with a `__main__` demo |

Neither has an active repository caller or dedicated test, but deleting them removes documented manual capabilities. They should not be bundled with F1 without an explicit user-approved hard cut.

### Package re-exports

- `scripts/utils/reporter/__init__.py` eagerly re-exports constants, data fetchers, and scoring functions that have no in-repository package-level caller. `ReportManager` remains active through `xueqiu_monitor_v2.py`.
- `scripts/utils/reporter/sections/__init__.py` eagerly imports every renderer. Active assembly uses module-string imports; one test imports `ExecutiveSummaryRenderer` from the package.

Slimming these packages would reduce import-time coupling by roughly 55-65 lines, but it changes documented public import surfaces. Treat as a separate F2 hard cut with explicit tests for the retained package contracts.

## Keep

- `scripts/high_risk/extract_detail_via_cdp.py`: explicit deprecated safety shim documented in README/runbook and covered by CLI tests.
- `DataCollector.compute_indicators()` and `_compute_indicators_legacy()`: active technical skill wrapper and live fallback.
- `TechnicalRenderer._render_legacy()`: active data-degradation path.
- `SynthesisSkill._legacy_llm_synthesize()`: active adapter for chat-only LLM clients.
- Annual v1 adapters and broker legacy-cleaning paths: active migration/read contracts.
- `use_pack` / legacy keyword swallowing in periodic narrative material loading: low-cost explicit fail-closed compatibility boundary.

## Recommended Sequence

1. Implement F1 only, using absence hygiene tests and the full suite.
2. Re-audit F2 after F1 lands; decide whether documented manual tools and package imports are still operator requirements.
3. Do not mix F2 with large-file internal-owner refactoring.

## Stop Conditions

- Any active preview/tool/runtime caller appears for an F1 module.
- External Producer v4 tests or report smoke require one of the deleted utilities.
- Deletion requires changing canonical pack, scope, evidence, LLM, scoring, risk, or citation behavior.
- Runtime is not a pure deletion.
