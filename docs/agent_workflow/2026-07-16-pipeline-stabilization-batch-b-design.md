# Pipeline Stabilization Batch B Design

Date: 2026-07-16  
Branch: `codex/pipeline-stabilization`  
Depends on: `2026-07-16-pipeline-stabilization-design.md`

## 1. Objective

Close the 34 additional failures exposed after Batch A removed the first four
default-suite blockers. Batch B repairs test contracts only. It must preserve all
runtime package, annual-pack identity, source, scoring, risk, technical, and
collection behavior.

Success means:

- all 34 previously failing tests pass or, for the single live K-line smoke,
  explicitly skip only when its external source is unavailable;
- the full offline `pytest` command has zero failures;
- Batch A focused tests and CLI behavior remain green;
- no runtime file changes are added in Batch B.

## 2. Verified Failure Groups

| Group | Count | Cause |
|---|---:|---|
| renderer package imports | 3 | tests import `sections` as a top-level package, breaking parent-relative imports |
| linked-worktree knowledge path | 2 | assertions hard-code `/testsnow/knowledge` |
| annual narrative schema | 1 | test still expects v1 after the validated v2 migration |
| synthesis stock identity | 26 | test contexts omit the stock code required by pack-first identity validation |
| live K-line environment | 2 | two tests repeat the same external fetch; current source returns no usable frame |

The groups are independent. No shared runtime fallback may be introduced to make
them pass.

## 3. Package Import Corrections

Allowed files:

- `tests/reporter/test_corporate_action_adjustment.py`
- `tests/reporter/test_market_resonance_integration.py`

Only the three failing renderer imports change to:

```python
from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer
```

Remove the adjacent function-local insertion of `scripts/utils/reporter` for
those renderer tests. Other legacy technical-module imports in the same files are
outside this batch and remain unchanged because they currently pass.

The runtime `reporter/sections` package is not modified and receives no fallback
import path.

## 4. Worktree-Safe Knowledge Path Assertions

Allowed file:

- `tests/reporter/test_evidence_note_skill.py`

Define the expected path from the checked-out repository containing the test:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_KNOWLEDGE_DIR = (REPO_ROOT / "knowledge").resolve()
```

Both assertions compare resolved `Path` objects exactly. They do not use suffix
matching, the main checkout path, the current working directory, or environment
variables.

## 5. Narrative Schema Contract

Allowed file:

- `tests/reporter/test_periodic_report_fulltext_intake_skill.py`

Update the exact schema assertion to:

```python
periodic_report_narrative_evidence_cards.v2
```

Keep the existing excerpt/content assertions. Do not weaken the test to accept
both schema versions.

## 6. Synthesis Fixture Identity

Allowed file:

- `tests/reporter/test_synthesis_skills.py`

The production material-pack loader requires a stock name/code identity pair.
Batch B keeps this fail-closed contract.

Add one file-local mapping for names used by tests:

```python
TEST_STOCK_CODES = {
    "复旦微电": "688385",
    "黑芝麻智能": "02533",
    "中简科技": "300777",
    "中际旭创": "300308",
    "圣邦股份": "300661",
    "韦尔股份": "603501",
    "测试股": "000001",
}

EMPTY_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "_empty_knowledge"
```

Add one explicit helper:

```python
def _with_stock_identity(payload):
    result = dict(payload)
    stock_name = str(result.get("stock_name") or "")
    if stock_name and "stock_codes" not in result:
        result["stock_codes"] = {stock_name: TEST_STOCK_CODES[stock_name]}
    result.setdefault("knowledge_base_dir", str(EMPTY_KNOWLEDGE_DIR))
    return result
```

Wrap only the `SkillContext(input=...)` payloads that currently fail because
they omit identity. Do not shadow or monkeypatch `SkillContext`, do not use an
autouse fixture, and do not add a generic unknown-code fallback. Existing tests
that already specify `stock_codes` remain unchanged.

The helper returns a new top-level payload dict and must not mutate a fixture
dict supplied by a test. Each wrapped call remains visibly written as
`SkillContext(input=_with_stock_identity({...}))`, so identity injection is
auditable at the call site.

The non-existent test-only knowledge root prevents these general synthesis unit
tests from reading developer-machine packs. A test that intentionally supplies a
temporary `knowledge_base_dir` keeps that explicit value because the helper uses
`setdefault`.

If a failing context uses a stock name absent from the mapping, add its real test
code to the mapping; do not invent a runtime fallback.

## 7. Data Collector Test Split

Allowed file:

- `tests/test_data_collector.py`

The current `test_compute_indicators` performs a second live K-line fetch even
though legacy indicator computation is deterministic. Replace that fetch with a
local 120-row OHLCV fixture containing `date/open/high/low/close/volume`, rename
the test to describe the local fallback, call `_compute_indicators_legacy`, and
retain the existing MACD/RSI/MA/BOLL assertions. The existing mocked
`test_compute_indicators_is_compatibility_wrapper_with_market` continues to own
the public-wrapper contract; the local-frame test owns real indicator math.

Keep one live smoke test for `fetch_kline`. If the external source returns `None`
or an empty frame, call:

```python
pytest.skip("live K-line source unavailable in this environment")
```

If data is returned, keep the existing shape and column assertions. Do not catch
arbitrary exceptions and do not skip deterministic indicator failures.
Do not add or modify pytest configuration, collection hooks, default marker
filters, or file-level skip markers. At most this one live smoke may add one skip
to the full-suite count.

## 8. TDD and Verification

The 34 failures already provide RED evidence. Execute groups separately in the
order above and run each group GREEN before moving on.

Verification order:

1. exact 34-test failure set, updated for any renamed test;
2. complete seven affected test files;
3. Batch A focused suite;
4. full `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider --tb=short`;
5. `bash tools/ci_grep_gates.sh`;
6. `git diff --check`;
7. `cd scripts && python run_黑芝麻智能.py --fast-test` only after full pytest has
   zero failures.

No new broad skip marker, ignore list, xfail, or collection filter is allowed.

## 9. Failure Modes

| Failure | Symptom | Guard |
|---|---|---|
| runtime import fallback added | package bug hidden outside tests | runtime file-scope audit |
| knowledge assertion accepts any suffix | wrong checkout silently accepted | exact resolved-path assertions |
| schema assertion accepts v1 or v2 | migration regression hidden | exact v2 assertion |
| synthesis helper inserts fake unknown code | identity mismatch no longer detected | closed name/code mapping |
| autouse fixture mutates every context | missing-identity tests become impossible | helper applied only to named failing contexts |
| live skip wraps indicator computation | deterministic regression hidden | only fetch smoke may skip |
| full suite reveals another root cause | scope expands without design | stop and classify before editing |

## 10. File Scope

Batch B may modify only:

- `tests/reporter/test_corporate_action_adjustment.py`
- `tests/reporter/test_market_resonance_integration.py`
- `tests/reporter/test_evidence_note_skill.py`
- `tests/reporter/test_periodic_report_fulltext_intake_skill.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/test_data_collector.py`
- Batch B workflow design/task/notes files.

`tests/conftest.py`, pytest configuration, and every runtime file are explicitly
outside the Batch B whitelist.

Batch A's existing uncommitted runtime/test diff remains in the worktree but must
not be broadened while implementing Batch B.

## 11. Stop Conditions

Stop before editing if:

- any failure requires a runtime source change;
- a synthesis test intentionally exercises missing stock identity;
- the live source fails by raising an unexpected application exception rather
  than returning unavailable data;
- another full-suite failure root cause appears after these five groups close;
- unrelated worktree changes appear.
