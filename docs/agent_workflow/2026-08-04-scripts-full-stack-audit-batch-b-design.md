# Scripts Full-Stack Audit Batch B Design

## 1. Objective

Remove four repository-internal compatibility surfaces that have no runtime,
preview, tool, README, or behaviorally meaningful test callers and whose
responsibilities already have active owners. One test contains an inert
monkeypatch of B4; that monkeypatch is deleted with the helper. This batch is a
bounded hard cut: it does not add deprecation wrappers and accepts that an
unknown caller importing these undocumented names directly will break.

Baseline: `0e355e6` on `codex-report-quality-upgrade`. Existing broker-note,
old-report, and plan-packet worktree changes are user-owned and out of scope.

## 2. Approaches Considered

1. **Bounded hard cut (selected):** remove all four dead surfaces and lock their
   replacements in runtime-hygiene tests. Lowest continuing maintenance cost.
2. **Deprecation wrappers:** retain forwarding names with warnings. Rejected
   because it preserves duplicate ownership and adds code for undocumented,
   uncalled APIs.
3. **Defer public-surface cleanup:** remove only the private summary helper.
   Rejected because static search found no public contract for the other three,
   while active replacements are already exercised by the report pipeline.

## 3. Locked Deletion Ledger

### B1. Eastmoney quote helper

Delete `reporter/data_fetcher.py::stock_quote_eastmoney`.

- Repository references: definition and docstring example only.
- Active owner: `fetch_tencent_quote`, which routes A-share, HK, and US quote
  requests used by report skills and renderers.
- Not exported from `reporter.__init__` and not documented in README.

### B2. Eastmoney fund-flow helper

Delete `reporter/data_fetcher.py::fund_flow_daily`.

- Repository references: definition and docstring example only.
- Active owner: `TechnicalCollector` obtains optional fund-flow rows and
  `technical_skills._bridge_technical_fund_flow` projects them into report
  context.
- Not exported from `reporter.__init__` and not documented in README.

### B3. Hard-coded valuation prose

Delete `scoring_engine.py::valuation_industry_judgment` and its re-export from
`reporter/__init__.py`.

- Repository references: definition and package re-export only.
- The function contains stock-specific dated prose and is not used by scoring,
  valuation rendering, or recommendation logic.
- Active owners: `compute_pillar_scores`, structured valuation material, and
  executive-summary valuation projection.
- No replacement prose wrapper is introduced.

### B4. Legacy executive-summary conclusion helper

Delete `executive_summary_renderer.py::_extract_conclusion` and remove the
obsolete monkeypatch from `test_fulltext_material_isolation.py`.

- Repository references: definition and one test monkeypatch only; the test
  does not consume the helper result.
- Active owner: `_deterministic_conclusion(ctx)` and the structured decision
  chain used by `ExecutiveSummaryRenderer`.
- `_llm_extract_thesis` remains active for thesis-point extraction; its prompt
  and behavior are unchanged.

## 4. Explicitly Preserved

- `fetch_tencent_quote`, `fetch_consensus_eps`, financial-history providers,
  competitor metrics, and all report-skill imports.
- `TechnicalCollector`, optional fund-flow collection, and fund-flow rendering.
- `compute_pillar_scores`, scoring thresholds, EV, risk, target-price, and
  recommendation logic.
- `_deterministic_conclusion`, thesis-point extraction, LLM prompts, citations,
  report structure, and Pipeline order.
- All entry scripts, previews, tools, data, knowledge, and reports.

## 5. TDD Plan

### Task 1: RED runtime-hygiene contract

Extend `tests/test_runtime_hygiene.py` to assert:

- B1-B4 definitions are absent;
- `reporter` no longer exports `valuation_industry_judgment`;
- active owners remain: `fetch_tencent_quote`, `compute_pillar_scores`,
  `_deterministic_conclusion`, and `TechnicalCollector` fund-flow support.

Run the new focused test before runtime edits and require failure for the four
still-present definitions/export.

### Task 2: GREEN minimal deletion

Delete only the ledger entries and the stale test monkeypatch. Do not rewrite
or relocate active owners.

Focused tests:

```text
tests/test_runtime_hygiene.py
tests/reporter/test_data_fetcher_manual_financials.py
tests/reporter/test_data_fetcher_market_cap.py
tests/reporter/test_data_fetcher_peers.py
tests/reporter/test_scoring_engine_contract.py
tests/reporter/test_scoring_engine_risk.py
tests/reporter/test_executive_summary_renderer.py
tests/reporter/test_executive_summary_view.py
tests/reporter/test_fulltext_material_isolation.py
tests/reporter/test_technical_skills_contract.py
```

### Task 3: Full verification

- full `pytest` with repository `testpaths`;
- `tools/ci_grep_gates.sh`;
- `git diff --check`;
- `run_stock_report.py --stock 黑芝麻智能 --offline-smoke`;
- confirm smoke output remains under `/tmp/testsnow_offline_smoke` and contains
  no LLM request/retry.

## 6. Budget

- Expected runtime deletion: 90-100 lines.
- Runtime hard stop: net deletion must be at least 80 lines; no new runtime
  helper is allowed.
- Tests may grow only to encode absence and active-owner contracts; no existing
  behavioral test case may be deleted.

## 7. Failure Modes

| Failure | Symptom | Detection |
|---|---|---|
| Hidden dynamic import of a deleted name | import/attribute failure | full suite + offline smoke |
| Quote path depended on B1 | missing quote/valuation context | data-fetcher and pipeline tests |
| Fund-flow path depended on B2 | technical fund-flow bridge empty | technical-skills contract tests |
| Package consumer imports B3 | reporter package import failure | hygiene import assertion + full suite |
| Summary still calls B4 | render-time `NameError` | executive-summary tests + smoke |
| Cleanup changes report behavior | changed sections, scoring, or prompts | scope diff review + focused/full tests |

## 8. Stop Conditions

Stop and return to design if any candidate has a live repository caller, an
active owner must change behavior, focused tests reveal report-output changes,
runtime deletion is below 80 lines, or implementation requires edits to data
collection behavior, scoring, technical algorithms, risk, target price,
citations, Pipeline order, or LLM prompts.
