# Technical Entry Consolidation Batch C Design

## 1. Objective

Consolidate the repeated diagnostics, `TechnicalRenderer` context projection,
Markdown write, and completion logging in the three supported standalone
technical-analysis entry scripts:

- `scripts/run_中简科技技术分析_真实数据.py`
- `scripts/run_乐鑫科技技术分析_真实数据.py`
- `scripts/run_澜起科技技术分析_真实数据.py`

The entry names remain stable. Each wrapper continues to own data acquisition
and stock-specific side effects. This batch changes no indicator, price-target,
scoring, risk, recommendation, provider, cache, or report-rendering algorithm.

Baseline: `0258251` on `codex-report-quality-upgrade`. Existing broker-note,
old-report, and plan-packet worktree changes are user-owned and out of scope.

## 2. Current Problem

The three entry scripts contain 588 lines in total. About 100-130 lines per
script repeat the same duties:

1. print core indicators and trend diagnostics;
2. print Phase 2 signals and key levels;
3. build a full-mode `TechnicalRenderer` context;
4. write a dated Markdown file and print the full report.

The copies have already drifted. Zhongjian and Espressif print the legacy
`market_regime` projection, while Montage prints the current
`market_resonance` projection populated by the analyzer after index analysis.
Optional `price_target`, `fund_flow`, and `concept_blocks` fields are also
forwarded inconsistently.

## 3. Approaches Considered

1. **Shared output owner with thin wrappers (selected).** Extract only the
   repeated diagnostics, renderer projection, and Markdown write. Preserve each
   wrapper's acquisition and special outputs.
2. **One generic CLI.** Rejected for this batch. It would change user-facing
   entry contracts and require configuration for local-CSV versus collector
   acquisition and Montage CSV exports.
3. **Small helper extraction only.** Rejected because it leaves three copies of
   orchestration and does not remove the schema drift.
4. **Delete the standalone scripts.** Prohibited by `AGENTS.md` and unnecessary.

## 4. Locked Ownership Boundary

### 4.1 New shared owner

Add `scripts/utils/technical_report_entry.py` with one public orchestration
function and private formatting/logging helpers. The public function accepts:

- `stock_name`, `stock_code`;
- already-computed `indicators` and `resonance` dictionaries;
- `report_dir` and optional diagnostic `data_lines`;
- optional `price_target`, `fund_flow`, and `concept_blocks` values;
- optional title suffix and date value for deterministic tests.

It must:

1. log the common core/trend/signal/key-level diagnostics;
2. read market diagnostics only from `resonance["market_resonance"]`;
3. copy indicators before adding `_resonance`;
4. include optional technical fields only when supplied, without inventing
   defaults that change renderer behavior;
5. render once with `TechnicalRenderer` in `full` mode;
6. preserve the filename contract
   `{stock_name}_技术形态分析_真实数据_YYYYMMDD.md`;
7. write UTF-8 Markdown, log its path and full content, and return the path.

Each wrapper adds only `scripts/utils` to `sys.path`, once, and imports runtime
modules through that root (`reporter.technical_analyzer`, `data_collector`, and
`technical_report_entry`). The shared module imports
`reporter.sections.technical_renderer` through the same root and must not
modify `sys.path` itself. The old direct `scripts/utils/reporter` path and
top-level `technical_analyzer` / `sections.*` imports are removed, preventing a
second module identity.

### 4.2 Thin wrapper responsibilities

`run_中简科技技术分析_真实数据.py` retains:

- the fixed local CSV path;
- date parsing and the direct `technical_analyzer.analyze(df_daily)` call;
- its date-range/bar-count diagnostics;
- forwarding `result.get("price_target")`.

`run_乐鑫科技技术分析_真实数据.py` retains:

- `TechnicalCollector.collect("688018", market=1, days=250,
  adjustment="qfq")`;
- its adjustment/bar-count diagnostics;
- forwarding every optional field present in the collection payload rather
  than silently dropping it.

`run_澜起科技技术分析_真实数据.py` retains:

- `TechnicalCollector.collect("688008", market=1, days=250,
  adjustment="qfq")`;
- raw daily and weekly CSV fetch/export behavior and filenames;
- its adjustment/bar-count diagnostics;
- forwarding `price_target`, `fund_flow`, and `concept_blocks`.

All wrappers retain `main()` and the existing `if __name__ == "__main__"`
entry. None is renamed or removed.

### 4.3 Failure behavior

The wrappers must fail clearly before rendering when their required source data
is absent:

- Zhongjian preserves ordinary file/read/analyzer exceptions.
- Collector wrappers raise a concise `RuntimeError` when collection returns no
  usable `indicators`, instead of failing later with an opaque `KeyError` or
  formatting error.

This is an entry-boundary diagnostic improvement, not a data fallback or
algorithm change. The shared owner accepts partial indicator dictionaries and
logs missing values as `N/A`; `TechnicalRenderer` remains responsible for its
existing fail-closed judgment behavior.

## 5. Explicitly Preserved

- All three script paths, stock codes, markets, periods, and adjustment modes.
- Zhongjian local CSV input and Montage raw/weekly CSV outputs.
- `TechnicalCollector`, `technical_analyzer`, `TechnicalRenderer`, technical
  state machine, market-index cache, providers, and all calculations.
- Report filename, full render mode, chart-path input, and full-report logging.
- Main report pipeline, report sections, scoring, target-price formulas, risk,
  recommendation, LLM prompts, citations, data, knowledge, and reports.
- README/AGENTS statements that the three stock-specific entries exist; no
  generic CLI claim is introduced.

## 6. TDD Plan

### Task 1: RED shared-owner contracts

Add `tests/utils/test_technical_report_entry.py` with no network access:

1. renderer context contains a copied indicators mapping with `_resonance` and
   does not mutate the caller's indicators;
2. `price_target`, `fund_flow`, and `concept_blocks` are forwarded when supplied
   and omitted when absent;
3. output filename, UTF-8 content, full render mode, and returned path remain
   stable under an injected date;
4. diagnostics use `market_resonance` state/confidence/impact/missing and do not
   depend on `market_regime`;
5. sparse indicators log `N/A` without a formatting exception.

The tests monkeypatch `TechnicalRenderer` in the new module. They do not invoke
providers or technical algorithms.

### Task 2: GREEN shared owner

Implement the smallest module satisfying Task 1. Do not add a dataclass,
registry, generic stock configuration, second renderer, or compatibility
adapter.

### Task 3: RED/GREEN thin-wrapper contracts

Add `tests/test_technical_analysis_entries.py` using AST/source-level contracts
plus narrow monkeypatching where useful. Assert:

- all three scripts still expose `main()`;
- each imports and delegates to the shared output owner exactly once;
- all three use the single `scripts/utils` import root and package-qualified
  `reporter` imports; none inserts `scripts/utils/reporter`;
- Zhongjian still reads the fixed CSV and calls `analyze`;
- Espressif and Montage preserve their exact collector parameters;
- Montage alone retains both CSV exports;
- collector wrappers reject empty indicator payloads before delegation;
- the three wrappers no longer import `TechnicalRenderer` directly or contain
  duplicate diagnostic section headings.

No wrapper test may make a network request or write into repository `reports/`
or `data/`; use temporary paths and patched acquisition functions.

### Task 4: Verification

Focused tests:

```text
tests/utils/test_technical_report_entry.py
tests/test_technical_analysis_entries.py
tests/reporter/test_technical_renderer.py
tests/reporter/test_technical_state_machine.py
tests/reporter/test_market_resonance_integration.py
tests/reporter/test_corporate_action_adjustment.py
tests/test_data_collector.py
```

Then run the full repository test suite, `tools/ci_grep_gates.sh`, and
`git diff --check`. Do not run the three live entries during implementation;
they fetch market data and generate reports. A later local acceptance run may
exercise them explicitly.

## 7. Runtime Budget

- Current three-entry baseline: 588 lines.
- New shared module target: at most 135 lines.
- Three wrappers combined target: at most 235 lines, including Montage CSV
  export code.
- Final four-file runtime target: at most 370 lines, for net deletion of at
  least 218 lines.
- Hard stop: if net runtime deletion is below 180 lines, stop and return to the
  design with an exact ledger. Do not compress by hiding logic in dense
  expressions or by deleting diagnostics, acquisition behavior, or entry
  contracts.

Test lines are outside the runtime budget and may not be reduced by deleting
existing behavioral coverage.

## 8. Failure Modes

| Failure | Symptom | Detection |
|---|---|---|
| Wrapper changes data acquisition | different source, period, or adjustment | entry contract tests + diff review |
| Montage CSV side effects disappear | raw/weekly CSV no longer written | entry contract tests |
| Optional renderer material is lost | target/fund-flow/concepts absent | shared-owner context tests |
| Indicators mutated by projection | later caller sees `_resonance` injected | immutability test |
| Old market key remains an owner | market output differs by wrapper | diagnostics test + source hygiene assertion |
| Sparse payload crashes diagnostics | formatting `TypeError` | sparse-indicator test |
| Missing collection fails opaquely | `KeyError`/`NoneType` traceback | empty-payload wrapper tests |
| Filename/output changes | automation cannot find report | deterministic path/content test |
| Import-root behavior breaks direct execution | module import failure | wrapper import tests + later local entry run |
| Two import roots recreate module identities | inconsistent class/module state | source hygiene assertion |
| Cleanup changes technical decisions | report judgment or targets differ | existing renderer/state-machine/resonance suites |

## 9. Stop Conditions

Stop and return to design if implementation requires:

- deleting or renaming an entry;
- changing any provider, collector parameter, technical algorithm, indicator,
  target-price formula, score, risk, or recommendation;
- moving Montage CSV exports into the shared owner;
- introducing a generic CLI/config registry;
- touching report pipeline structure, LLM prompts, citations, data, knowledge,
  or reports;
- modifying more runtime modules than the new shared owner and three wrappers;
- accepting less than 180 lines of net runtime deletion.

## 10. Design Delta After Codex Self-Review

- **Accepted:** use current `market_resonance` as the sole diagnostic key; the
  analyzer still retains `market_regime` internally, but entry display no longer
  owns or chooses between two projections.
- **Accepted:** preserve Montage CSV acquisition/export in its wrapper, avoiding
  hidden network and filesystem side effects in the shared owner.
- **Accepted:** forward optional collector material for Espressif as well as
  Montage so consolidation cannot silently narrow renderer input.
- **Accepted:** replace the mixed `scripts/utils` and `scripts/utils/reporter`
  roots with one `scripts/utils` root and package-qualified reporter imports.
- **Accepted:** make empty collector payload failure explicit and keep sparse
  diagnostic formatting safe.
- **Rejected:** generic CLI, dataclass/config registry, renderer injection in
  production API, and compatibility adapters; each adds code without reducing
  active ownership.
- **Deferred:** running all three live market-data entries. That belongs to
  local acceptance after implementation, not deterministic TDD.
- **Round 2 required:** only if review finds a blocker, unresolved must-fix, or a
  change to the locked ownership/data-acquisition boundary.
