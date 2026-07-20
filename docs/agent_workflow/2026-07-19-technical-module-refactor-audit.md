# Technical Module Refactor Audit

## Scope

Read-only audit after the Phase 2.2 behavior-preserving compression. No scoring, risk, target, recommendation, collection, or report behavior is changed by this document.

## Current Shape

| Module | Lines | Main responsibility |
| --- | ---: | --- |
| `technical_state_machine.py` | 1,254 | Trend scoring, invalidation, target checks, action and interpretation contract |
| `technical_structure.py` | 1,047 | Price structure, levels, channel/box, bottoming and Phase 2.2 facts |
| `technical_analyzer.py` | 977 | Data preparation and orchestration |
| `technical_renderer.py` | 480 | Judgment projection plus legacy fallback |
| `technical_patterns.py` | 318 | Candle, double-top/bottom and momentum patterns |

The audit found one definition-only helper, `_is_support_resistance`; it has been deleted. All other public and private top-level technical functions have an active runtime or test caller. There is no second safe bulk-deletion list.

## Ranked Refactor Candidates

### P0: Preserve Shared Media In Core-Judgment Fallback

**Problem**

`TechnicalRenderer._render_projection()` returns `_render_core_judgment()` immediately when a valid
judgment has no interpretation. That bypasses the technical chart even though `TechnicalAnalysisSkill`
successfully populated `chart_paths`. The full-suite chart integration failure reproduces this path:
all three chart mocks are called, but the Markdown omits the technical image.

**Recommended change**

Extract one technical-chart projection helper and call it from full projection, core-only projection,
and legacy projection. This both fixes the regression and removes the duplicated chart block.

**Expected benefit**

Restores the full-suite contract and establishes one chart-format owner with a small net line reduction.

### P1: Canonicalize Package Imports

**Problem**

The repository can load the same code under both `utils.report_skills.*` and top-level `report_skills.*` /
`reporter.*`. Runtime modules also mutate `sys.path` and retry imports. This is independent of the chart
projection failure above, but isolated test execution already demonstrates a `reports/` namespace collision
when the expected package root is not installed first.

**Evidence**

- `technical_analyzer.py` contains multiple relative/top-level import fallbacks.
- `technical_renderer.py` mutates `sys.path` in two dynamic import helpers.
- `chart_skills.py` mutates `sys.path` and imports top-level `reporter`.
- Tests independently insert `scripts`, `scripts/utils`, or `scripts/utils/reporter` into `sys.path`.

**Recommended change**

Choose `utils.*` as the canonical runtime package when `scripts` is on `sys.path`. Convert package-internal imports to relative imports and update tests to import/patch the same identity. Keep entry scripts responsible for adding `scripts`, not leaf modules.

**Expected benefit**

- Fixes the chart integration test's module-identity failure.
- Removes roughly 30-60 lines of import fallback and path mutation across the technical/report path.
- Makes mocks deterministic and prevents modules from being initialized twice.

**Required tests**

- Import-identity smoke test asserting one module object for chart skills and reporter components.
- Existing chart integration test in isolation and in the full suite.
- Direct report entry smoke test to protect script execution.

### P1: Separate State Facts From Judgment Projection

**Problem**

`technical_state_machine.py` owns two large, valid but distinct areas:

- trend state, trend health and invalidation (roughly the first half);
- target trigger checks, action state and interpretation schema (roughly the second half).

**Recommended change**

After Phase 2.2 is accepted, move the judgment-contract half to `technical_judgment.py`. Preserve `technical_state_machine.py` re-exports for one release only if external imports require them.

**Expected benefit**

Primarily maintainability and test ownership, not immediate line reduction. Do not undertake this as a "slimming" batch.

### P2: Split Structure Algorithms By Ownership

**Problem**

`technical_structure.py` contains several independent algorithms: Phase 2.2 path/shock facts, support/resistance, trend structure, channel/box and bottoming.

**Recommended change**

Move the path/shock fact layer to `technical_path_facts.py` or move the older level/channel algorithms to a dedicated module. Keep one public owner per algorithm and avoid adapter copies.

**Expected benefit**

Smaller review units and clearer tests. This will be line-neutral or slightly positive, so it should not be sold as code compression.

### P2: Thin The Analyzer Into Orchestration

**Problem**

`advanced_medium_term_resonance()` combines data adjustment, indicator computation, index lookup, fact production and final payload assembly.

**Recommended change**

First canonicalize imports. Then extract only cohesive input preparation and payload assembly helpers already covered by integration tests. Do not add a second analysis pipeline.

**Expected benefit**

Lower cyclomatic complexity and easier fixture construction; limited net line reduction.

### P3: Consolidate Test Import Setup, Do Not Delete Coverage Blindly

The full suite contains 2,532 runnable tests in this worktree. The current problem is inconsistent import setup, not simply test count. Replace per-file `sys.path.insert()` calls with one canonical test bootstrap before considering deletion. Any test deletion should follow a requirement-to-test matrix and demonstrate duplicate assertions, especially for scoring and source-boundary gates.

## Recommended Sequence

1. Merge/accept Phase 2.2 compression and behavior first.
2. Preserve the technical chart in core-only judgment projection and deduplicate the chart block.
3. Run a narrow canonical-import batch and remove fallback imports.
4. Reassess module splits only after import identity is stable.
5. Do not delete legacy rendering or active structure algorithms solely to reduce line count.
