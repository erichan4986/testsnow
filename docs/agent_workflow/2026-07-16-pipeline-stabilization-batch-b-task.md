# Pipeline Stabilization Batch B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 34 out-of-scope baseline failures discovered by Batch A using
test-contract corrections only.

**Architecture:** Correct package imports, worktree path expectations, schema
version, and explicit synthesis identities at their test call sites. Split live
K-line smoke coverage from deterministic indicator math without modifying runtime
owners or pytest collection policy.

**Tech Stack:** Python 3.10, pytest, pandas, stockstats, repository test helpers.

---

### Task 1: Correct renderer package imports

**Files:**

- Modify: `tests/reporter/test_corporate_action_adjustment.py`
- Modify: `tests/reporter/test_market_resonance_integration.py`

- [ ] **Step 1: Confirm RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_corporate_action_adjustment.py::test_renderer_shows_corporate_action_warning \
  tests/reporter/test_market_resonance_integration.py::test_renderer_shows_market_resonance_with_impact_and_relative \
  tests/reporter/test_market_resonance_integration.py::test_renderer_shows_missing_when_index_data_unavailable \
  -q -p no:cacheprovider --tb=short
```

Expected: three package-relative import failures.

- [ ] **Step 2: Use canonical renderer imports**

In the three named tests, delete the adjacent function-local `sys.path.insert`
and replace:

```python
from sections.technical_renderer import TechnicalRenderer
```

with:

```python
from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer
```

Do not change passing legacy technical-module imports elsewhere in either file.

- [ ] **Step 3: Verify GREEN**

Run the Step 1 command. Expected: `3 passed`.

### Task 2: Correct worktree path and schema contracts

**Files:**

- Modify: `tests/reporter/test_evidence_note_skill.py`
- Modify: `tests/reporter/test_periodic_report_fulltext_intake_skill.py`

- [ ] **Step 1: Confirm RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_evidence_note_skill.py::test_noop_status_summary_has_stable_shape \
  tests/reporter/test_evidence_note_skill.py::test_default_base_dir_resolves_to_repo_root_knowledge \
  tests/reporter/test_periodic_report_fulltext_intake_skill.py::test_periodic_report_fulltext_intake_sets_narrative_cards_from_cache \
  -q -p no:cacheprovider --tb=short
```

Expected: two `/testsnow/knowledge` assertion failures and one v1/v2 schema
assertion failure.

- [ ] **Step 2: Add exact worktree-aware constants**

Near the imports in `test_evidence_note_skill.py`, add:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_KNOWLEDGE_DIR = (REPO_ROOT / "knowledge").resolve()
```

Replace both suffix assertions with exact resolved comparisons:

```python
assert Path(summary["base_dir"]).resolve() == EXPECTED_KNOWLEDGE_DIR
assert Path(captured["base_dir"]).resolve() == EXPECTED_KNOWLEDGE_DIR
```

- [ ] **Step 3: Require narrative schema v2**

Replace the fulltext intake assertion with:

```python
assert pack["schema_version"] == "periodic_report_narrative_evidence_cards.v2"
```

- [ ] **Step 4: Verify GREEN**

Run the Step 1 command. Expected: `3 passed`.

### Task 3: Isolate synthesis fixtures and supply identity

**Files:**

- Modify: `tests/reporter/test_synthesis_skills.py`

- [ ] **Step 1: Confirm the synthesis RED group**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_synthesis_skills.py -q -p no:cacheprovider --tb=short
```

Expected: 26 failures with `expected_stock_code_required`.

- [ ] **Step 2: Add the closed identity mapping and helper**

After imports, add:

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


def _with_stock_identity(payload):
    result = dict(payload)
    stock_name = str(result.get("stock_name") or "")
    if stock_name and "stock_codes" not in result:
        result["stock_codes"] = {stock_name: TEST_STOCK_CODES[stock_name]}
    result.setdefault("knowledge_base_dir", str(EMPTY_KNOWLEDGE_DIR))
    return result
```

- [ ] **Step 3: Wrap exactly the failing context payloads**

Change `SkillContext(input={...})` to
`SkillContext(input=_with_stock_identity({...}))` in these tests, adding the
matching closing parenthesis only:

```text
test_synthesis_skill_passes_stock_config_to_synthesizer
test_synthesis_skill_passes_formal_financial_fact_pack_to_synthesizer
test_synthesis_skill_passes_formal_financial_explanation_pack_to_synthesizer
test_synthesis_skill_builds_fundflow_pack_and_keeps_raw_fundflow_items
test_fundflow_pack_keeps_citable_fundflow_sources
test_synthesis_skill_replaces_financial_missing_contradiction_when_fact_pack_exists
test_formal_financial_fact_pack_drops_zero_amounts_and_sanitizer_uses_core_facts
test_synthesis_skill_enabled_modern_path_passes_context_to_synthesizer
test_periodic_report_excerpt_does_not_enter_synthesis_items
test_source_intake_keep_items_enter_baseline_synthesis_items
test_periodic_report_fulltext_items_do_not_enter_synthesis_items
test_curated_external_viewpoint_digest_rejects_mismatched_stock_identity
test_curated_external_viewpoint_digest_drops_foreign_only_target_claim
test_curated_external_viewpoint_narrative_hydrates_refs_from_claim_ids
test_curated_external_viewpoint_narrative_preserves_reasoning_cards_and_truncates_excerpt
test_periodic_report_fulltext_synthesis_default_off_excludes_fulltext
test_periodic_report_fulltext_synthesis_keeps_canonical_synthesis_baseline
test_periodic_report_fulltext_synthesis_does_not_change_synthesis_text_or_core_facts
test_empty_core_facts_fall_back_to_periodic_filing_core_facts
test_unsupported_core_facts_fall_back_to_periodic_filing_core_facts
test_periodic_report_fulltext_knowledge_persistence_would_receive_baseline
test_append_at_end_preserves_existing_source_order
test_periodic_report_fulltext_synthesis_no_items_skips_display
test_periodic_report_fulltext_synthesis_rejects_malformed_fulltext_item
test_display_synthesis_dedupes_duplicate_material_before_synthesizer
test_evidence_profile_has_annual_memo_fields
```

Do not wrap tests that already provide `stock_codes`. Do not alter
`SynthesisSkill` or material-pack runtime code.

- [ ] **Step 4: Verify GREEN**

Re-run the Step 1 command. Expected: the complete synthesis test file passes.

If a named context already supplies an intentional temporary
`knowledge_base_dir`, verify that `_with_stock_identity` preserves it.

### Task 4: Separate deterministic indicators from live K-line smoke

**Files:**

- Modify: `tests/test_data_collector.py`

- [ ] **Step 1: Confirm RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/test_data_collector.py::test_fetch_kline_300661 \
  tests/test_data_collector.py::test_compute_indicators \
  -q -p no:cacheprovider --tb=short
```

Expected: the live fetch returns unavailable data and both tests fail.

- [ ] **Step 2: Make the live smoke explicitly environment-dependent**

Import `pytest`. After the fetch, add:

```python
if df is None or df.empty:
    pytest.skip("live K-line source unavailable in this environment")
```

Keep all assertions when data exists.

- [ ] **Step 3: Use a local frame for real indicator math**

Rename `test_compute_indicators` to
`test_legacy_compute_indicators_from_local_frame` and replace its body with:

```python
collector = TechnicalCollector.__new__(TechnicalCollector)
close = pd.Series([10.0 + index * 0.05 for index in range(120)])
df = pd.DataFrame({
    "date": pd.date_range("2026-01-01", periods=120, freq="B"),
    "open": close - 0.02,
    "high": close + 0.08,
    "low": close - 0.08,
    "close": close,
    "volume": [1000 + index for index in range(120)],
})
result = collector._compute_indicators_legacy(df)
assert "macd" in result
assert "rsi_14" in result
assert "ma_60" in result
assert "boll_upper" in result
```

- [ ] **Step 4: Verify GREEN/SKIP**

Run the live smoke and renamed local test. Expected: local test passes; live smoke
passes or emits exactly one explicit skip.

Then run the complete file. Expected: zero failures.

### Task 5: Full acceptance and notes

**Files:**

- Modify: `docs/agent_workflow/2026-07-16-pipeline-stabilization-notes.md`

- [ ] **Step 1: Run all Batch B files**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_corporate_action_adjustment.py \
  tests/reporter/test_market_resonance_integration.py \
  tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_periodic_report_fulltext_intake_skill.py \
  tests/reporter/test_synthesis_skills.py \
  tests/test_data_collector.py \
  -q -p no:cacheprovider --tb=short
```

Expected: zero failures, at most one live-data skip.

- [ ] **Step 2: Re-run Batch A focused coverage**

Run the 118-test combined command recorded in
`2026-07-16-pipeline-stabilization-notes.md`. Expected: zero failures.

- [ ] **Step 3: Run the full offline suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider --tb=short
```

Expected: zero failures; existing explicit skips plus at most one live-data skip.
If a new root cause appears, stop before further edits.

- [ ] **Step 4: Run static and scope gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Confirm `git diff --name-only c02b46e` contains only Batch A files, the six Batch
B test files, and workflow documents. Batch B adds zero runtime lines.

- [ ] **Step 5: Run the sample report smoke test**

```bash
cd scripts
python run_黑芝麻智能.py --fast-test
```

Expected: exit zero and a new report output without Zhihu refresh, Xueqiu detail
access, or batch collection.

- [ ] **Step 6: Update implementation notes**

Replace the blocked status with final RED/GREEN counts, full-suite result, skip
reason, CI result, Batch A runtime delta, report path, warnings, deviations, and
final merge recommendation.

- [ ] **Step 7: Commit the verified implementation**

Stage only approved Batch A/B implementation, tests, task, and notes files. Do
not stage generated reports. Commit with:

```bash
git commit -m "fix: stabilize pipeline test contracts"
```
