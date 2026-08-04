# Public Compatibility Cleanup Batch F2 Design

## Goal

Hard-delete two documented but detached manual utilities and remove unused eager package re-exports. Preserve active report, collection, scoring, technical, and renderer owners.

## Locked Deletion Ledger

### Detached manual utilities

- Delete `scripts/utils/judgment_generator.py` (271 lines).
- Delete `scripts/utils/wechat_sogou_fetcher.py` (222 lines).
- Remove their two current capability rows from `README.md`.

Neither module has a repository caller, package export, dedicated test, active CLI entry, preview, or tool. `JudgmentGenerator` is superseded by `ContentQualityGate` plus `KnowledgeSynthesizer`; generic WeChat discovery is superseded by the active targeted-discovery and candidate-selector paths.

### Reporter package

- Reduce `scripts/utils/reporter/__init__.py` to the package description and active `ReportManager` export.
- Remove unused package-level re-exports of constants, data fetchers, and scoring functions.
- Correct the stale `PerStockReporter` package-import documentation; the canonical import remains `utils.stock_reporter`.

### Sections package

- Reduce `scripts/utils/reporter/sections/__init__.py` to a package marker.
- Delete the unused `SectionRenderer` protocol and all eager renderer re-exports.
- Change the one repository package-level renderer import to its direct module owner.
- Update the README row so it no longer advertises the removed re-export surface.

## Retained Contracts

- `from utils.reporter import ReportManager` remains valid.
- `from utils.reporter import data_fetcher` remains valid through normal Python submodule import semantics.
- Direct imports such as `utils.reporter.scoring_engine` and `utils.reporter.sections.technical_renderer` remain valid.
- Dynamic renderer module strings in `ReportAssemblySkill.RENDERERS` remain unchanged.
- High-risk collection scripts, report entries, scoring, technical algorithms, LLM synthesis, data, knowledge, reports, and configuration remain untouched.

## TDD

1. Add hygiene assertions that both utility files and README rows are absent.
2. Add package-boundary assertions for retained and removed exports.
3. Observe RED against current runtime.
4. Apply only the locked deletions and import correction.
5. Run focused reporter/package tests, full suite, CI gates, diff check, and offline report smoke.

## Failure Modes

| Failure | Signal | Guard |
| --- | --- | --- |
| `ReportManager` export removed | batch monitor import failure | package-boundary test + full suite |
| Submodule import broken | `from utils.reporter import data_fetcher` fails | package-boundary test |
| Dynamic renderer broken | report assembly import error | assembly tests + offline smoke |
| Hidden caller for deleted utility | import/test failure | repository search + full suite |
| Current README advertises removed capability | documentation drift | hygiene assertion |

## Budget

- Utility deletion target: 493 runtime lines.
- Package initializer deletion target: approximately 60 runtime lines.
- Final runtime must be a pure net deletion of at least 540 lines.

## Stop Conditions

- Any active runtime, preview, or tool caller appears.
- `ReportManager`, submodule import, or dynamic renderer contracts cannot be retained without a compatibility shim.
- Any scoring, technical, LLM, source, citation, or report behavior must change.
- Full suite or offline smoke exposes a behavior regression.
