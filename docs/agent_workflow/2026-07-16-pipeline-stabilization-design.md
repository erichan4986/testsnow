# Pipeline Stabilization Design

Date: 2026-07-16  
Branch: `codex/pipeline-stabilization`  
Base: `611c28a refactor: complete annual material pack migration`

## 1. Objective

Restore a green offline test baseline and make the three annual-material command
line entry points deterministic when the caller already supplies a relative or
absolute `PYTHONPATH`.

This batch is infrastructure stabilization between Annual Producer v2 completion
and the next report-quality feature batch. It must not change report content,
source relevance, scoring, risk, technical analysis, or collection behavior.

## 2. Verified Baseline

The failures belong to two separate classes and must remain separate in the
implementation and acceptance report.

### 2.1 Default offline test failures

The standard repository test environment currently exposes four stale test
contracts:

1. `test_output_structured_risk_signals_passes_to_risk_section` imports
   `scoring_engine` as a top-level module, so its package-relative import fails.
2. Two Eastmoney stock-news tests use a fixed 2026-06-10 article without passing
   a fixed `today`; the article eventually ages out of the intentional 30-day
   runtime window.
3. One source-intake test still expects industry-chain material in section 4.3,
   while the current dedicated relevance contract intentionally limits it to
   section 4.1.

These are test corrections only. Runtime behavior is the source of truth.

### 2.2 Inherited `PYTHONPATH` failures

With `PYTHONPATH=scripts/utils:scripts`, two CLI subprocess tests fail:

- `scripts/periodic_report_cache.py` can import its own wrapper instead of the
  utility module;
- `scripts/periodic_report_extractor.py` has the same path-order ambiguity.

The current guards check only string membership. They do not canonicalize
equivalent relative/absolute entries or guarantee that the intended directory is
first. `scripts/prepare_annual_report_materials.py` already repairs the order
manually, but duplicates the policy.

## 3. Chosen Architecture

Add one repository-local helper:

```text
scripts/_path_bootstrap.py
```

It exposes one single-purpose API:

```python
prepend_sys_path(path: str | Path) -> str
```

Contract:

1. Resolve `path` to one absolute canonical string.
2. Compare existing entries by resolved path, so relative and absolute aliases
   are equivalent.
3. Remove every equivalent entry.
4. Insert the canonical string at `sys.path[0]`.
5. Return the canonical string for diagnostics/tests.
6. Repeated calls are idempotent: one canonical entry remains at index zero.
7. Do not read environment variables, import application modules, or change the
   current working directory.
8. Preserve all non-equivalent entries, including an empty-string current-working-
   directory entry, in their original relative order.

Implementation may normalize an entry only for equality comparison. It must keep
the original text of non-equivalent `sys.path` entries rather than rewriting the
whole list to resolved absolute paths. The three scripts import the helper as
`from _path_bootstrap import prepend_sys_path`; this direct-script import is the
only supported import mode for the helper in this batch. Do not add an
`__init__.py` or begin a package migration.

The helper owns only interpreter path ordering. It is not a general CLI
framework and must not absorb project-root discovery, argument parsing, logging,
or module loading.

## 4. Runtime Migration Scope

Only these three top-level scripts adopt the helper:

1. `scripts/periodic_report_cache.py`
2. `scripts/periodic_report_extractor.py`
3. `scripts/prepare_annual_report_materials.py`

Each script imports `_path_bootstrap` from its own script directory and calls the
helper before importing same-named modules from `scripts/utils` or helpers from
`scripts/previews`.

For `prepare_annual_report_materials.py`, call order must preserve the current
effective precedence:

```text
scripts/previews
scripts/utils
scripts
...
```

This means prepending `scripts/utils` first and `scripts/previews` second.

No other `sys.path.insert` occurrence is migrated in this batch. A repository-wide
package migration would create a much larger compatibility surface and is
explicitly deferred.

## 5. Test-Contract Corrections

### 5.1 Time-dependent stock news

In the two affected Eastmoney stock-news tests, pass a fixed
`today=date(2026, 6, 24)`. Do not widen the production lookback window and do not
replace the fixture date with a moving clock.

### 5.2 Industry-chain section policy

Update the stale source-intake assertion to match the dedicated
`industry_news_relevance` tests:

```python
allowed_sections == ["4.1"]
```

The test should continue to assert the relevance class and chain identifier. No
runtime relevance policy changes are allowed.

### 5.3 Scoring package import

Remove the test's direct mutation of `sys.path` and import:

```python
from reporter.scoring_engine import risk_score_section
```

Do not add fallback imports to `scoring_engine.py` and do not alter risk scoring.

## 6. Allowed Files

Runtime:

- `scripts/_path_bootstrap.py` (new)
- `scripts/periodic_report_cache.py`
- `scripts/periodic_report_extractor.py`
- `scripts/prepare_annual_report_materials.py`

Tests:

- `tests/utils/test_path_bootstrap.py` (new)
- `tests/utils/test_periodic_report_cache.py`
- `tests/utils/test_periodic_report_extractor.py`
- `tests/reporter/test_prepare_annual_report_materials.py`
- `tests/utils/test_a_stock_source_intake.py`
- `tests/reporter/test_claim_risk_signal_skill.py`

Workflow notes for this batch may also be added under `docs/agent_workflow/`.

## 7. TDD Sequence

### A. Bootstrap helper

Write failing tests that prove:

1. a relative alias and its absolute equivalent collapse to one entry;
2. the canonical entry moves to index zero even when already present later;
3. repeated calls remain idempotent;
4. unrelated path entries preserve their relative order.

The test fixture must restore a copy of `sys.path` after each case. Its unrelated
entries include an empty string and at least two non-equivalent paths, proving
that equality normalization does not rewrite their stored values.

Then implement the smallest helper satisfying those contracts.

### B. CLI path-order regression

Extend the existing CLI subprocess tests so the child is launched with its cwd
set to the repository root and inherits:

```text
PYTHONPATH=scripts/utils:scripts
```

The test constructs this value with `os.pathsep`, rather than hard-coding a
platform separator, and starts from a copy of the ambient environment. It must
not remove unrelated environment variables.

The cache CLI must preserve its JSON registration payload. The extractor must
preserve both existing JSON and Markdown subprocess contracts under the inherited
environment, not just one output mode. For annual material preparation, run the
script's `--help` path under the same inherited environment. Import
initialization must complete and help must exit zero without entering discovery
or download code; the test asserts a stable help fragment as well as exit status.

Then replace the three scripts' local path-order snippets with the helper.

### C. Stale test contracts

Make the three test-only corrections in section 5. They should turn the verified
default failures green without any production change.

## 8. Requirement-Test Matrix

| Requirement | Test evidence |
|---|---|
| canonical relative/absolute dedupe | `test_path_bootstrap.py` alias fixture |
| canonical path at index zero | helper ordering test |
| idempotent repeated bootstrap | helper repeated-call test |
| unrelated entries keep order | helper stability test |
| cache CLI survives inherited path | cache subprocess test with explicit env |
| extractor CLI survives inherited path | extractor subprocess test with explicit env |
| prepare script retains precedence/behavior | inherited-path `--help` subprocess test |
| stock-news tests do not age with wall clock | fixed-`today` fixtures |
| source-intake test matches current policy | exact `allowed_sections == ["4.1"]` |
| scoring test loads package context | `reporter.scoring_engine` import test |
| no broader offline regression | full `pytest` |

## 9. Failure Modes

| Failure | Observable symptom | Guard |
|---|---|---|
| helper compares only raw strings | duplicate relative/absolute entries remain | alias-dedupe unit test |
| helper leaves target after script directory | wrapper self-import/circular import | inherited-`PYTHONPATH` CLI tests |
| helper reorders unrelated dependencies | unrelated imports change unexpectedly | stable-order unit test |
| prepare precedence changes | preview or utility module resolves to wrapper | prepare focused regression |
| runtime news window is widened to satisfy tests | stale articles enter reports | allowed-file audit; test-only diff |
| section relevance is changed back to 4.3 | external material crosses current boundary | dedicated relevance suite + runtime diff audit |
| scoring adds fallback import | duplicate module identities or hidden package errors | runtime file scope audit |
| blanket skip hides environment failure | offline suite appears green without coverage | no new broad skips allowed |

## 10. Verification

Run in this order:

1. helper unit tests;
2. three CLI-focused test files under the standard environment;
3. the same CLI-focused tests with inherited
   `PYTHONPATH=scripts/utils:scripts`;
4. source-intake and claim-risk focused tests;
5. full offline `python3 -m pytest`;
6. `bash tools/ci_grep_gates.sh`;
7. `git diff --check`;
8. `cd scripts && python run_黑芝麻智能.py --fast-test` as the sample pipeline
   smoke test.

Environment-dependent integrations may retain existing explicit skips. This
batch may not add blanket skips or weaken assertions to make the suite green.

## 11. Budget and Stop Conditions

Runtime target: net `+30` lines.  
Runtime hard stop: net `+60` lines across the four allowed runtime files,
measured against `611c28a`. Test and documentation lines are reported separately
and do not count toward this runtime budget.

Stop and return to design if:

- any fix requires production changes to source relevance, scoring, risk,
  technical analysis, report rendering, or collection;
- more top-level scripts must migrate to make the scoped tests pass;
- the helper grows into a dynamic importer or general framework;
- full offline failures reveal a real unrelated business-code regression;
- runtime net growth exceeds `+60` lines.

## 12. Deferred Work

- repository-wide package/import normalization;
- External Producer v2;
- Technical Analysis Phase 2;
- any new source, browser, network, or LLM behavior.

After this batch is green, the roadmap resumes with External Producer v2, then
Technical Analysis Phase 2.
