# Claude Code Review Round 1: Agent-Reach Fundamental Research Integration

### Round 1 Feedback

Status: Ready with changes

---

Findings:

- **[Severity: High] Pipeline insertion point bypasses the quality gate.**
  The design proposes inserting `query_generation_skill` and `agent_reach_skill` immediately after `data_loading_skill`, before `quality_gate_skill`. `quality_gate_skill` (`scripts/utils/report_skills/data_skills.py:67-96`) currently calls `ContentQualityGate.process_xueqiu_posts(all_posts)`, which only evaluates Xueqiu items. Agent-Reach items would flow directly into `cross_source_consolidation_skill` and downstream synthesis without any quality filtering. Either move the insertion point to after `quality_gate_skill`, or explicitly extend the quality gate to handle `agent_reach_items` in phase 1.

- **[Severity: Medium] `stock_raw["agent_reach"]` mutation is unsafe without a copy.**
  The design says store items under `stock_raw["agent_reach"]` "only if doing so does not mutate user-provided raw data unexpectedly." `data_loading_skill` loads `stocks_data` and `raw_data` from the caller; mutating the same dict could leak back to the caller. If this path is used, the skill must deep-copy `stock_raw` first or store exclusively on `ctx`.

- **[Severity: Medium] `adapt_all()` contract expansion needs explicit test coverage for empty/malformed Agent-Reach items.**
  `scripts/utils/source_adapter.py` `adapt_all()` currently accepts `xueqiu_items`, `zhihu_items`, `reports`, `announcements`, `fundflow`, `news`, `wechat_items`. Adding `agent_reach_items` is straightforward, but the adapter must handle records where `url` is missing, `publish_time` is unparseable, or `interaction_score` is absent. These are common in scraped social data. The design should require tests for `adapt_all(agent_reach_items=[...])` with missing-field records.

- **[Severity: Medium] CLI timeout + global cap need per-platform timeout, not just per-command.**
  The design specifies 30 s per command and 100 items global / 10 per query cap. If Agent-Reach CLI spawns multiple parallel searches per platform, the total wall-clock time can exceed the intended budget. Recommend adding a per-stock total timeout (e.g., 60 s) wrapping all CLI calls, and documenting that the skill must serialize or bound concurrent calls.

- **[Severity: Low] Phase 1 should explicitly log `agent_reach_status` even when disabled.**
  The design sets `agent_reach_status = "disabled"` when off. Acceptance tests should assert this status is present in `ctx` after the pipeline so that renderers can rely on it in phase 3 without guessing absence.

- **[Severity: Low] `query_generation_skill` name collision risk.**
  The module `scripts/utils/report_skills/query_generation_skill.py` is generic. If later phases add LLM-based query generation, the deterministic templates should remain testable. Recommend naming the initial module `agent_reach_query_skill.py` or keeping deterministic logic in a clearly scoped submodule.

- **[Severity: Low] Missing acceptance test for pipeline skill count change.**
  `tests/reporter/test_pipeline_integration.py` currently asserts `len(pipeline.skills) == 11`. When Agent-Reach is enabled, the skill count becomes 13. The design should specify whether the integration test uses a parameterized builder (`build_stock_report_pipeline(enable_agent_reach=True/False)`) or separate pipeline tests, so the existing assertion does not break.

---

Recommendations:

1. **Move insertion point to after `quality_gate_skill`, or expand the gate.**
   Preferred: insert after `quality_gate_skill` in phase 1. If Agent-Reach data needs its own quality filtering before synthesis, add a dedicated lightweight gate in phase 2 rather than mixing it into `ContentQualityGate.process_xueqiu_posts`.

2. **Prohibit `stock_raw` mutation; use `ctx` only in phase 1.**
   Remove the `stock_raw["agent_reach"]` option from phase 1. Store `agent_reach_items` and `agent_reach_status` exclusively on `ctx`. This avoids all deep-copy concerns and keeps raw data immutable.

3. **Add per-stock total CLI budget and document serialization.**
   Wrap all CLI calls in a single 60 s deadline. If the CLI tool supports parallel platform search internally, pass `--max-results` and `--timeout` flags rather than spawning multiple subprocesses from Python.

4. **Require `adapt_all` contract tests for malformed Agent-Reach records.**
   In `tests/utils/test_source_adapter.py`, add cases for missing `url`, missing `publish_time`, missing `interaction_score`, and empty `content`. Adapter should return a valid `SynthesisItem` with `None` fields rather than raising.

5. **Update pipeline integration test plan.**
   Change the existing `test_pipeline_builder_returns_pipeline` to use a parameterized builder, or split into `test_default_pipeline_has_11_skills` and `test_agent_reach_pipeline_has_13_skills`.

6. **Keep deterministic query generation testable without subprocess.**
   `agent_reach_query_skill` should expose a pure function `generate_queries(stock_name, code, competitors) -> list[str]` that requires no env var and no LLM, so unit tests can call it directly.

---

Open Questions:

- Does the Agent-Reach CLI support a `--max-results` / `--timeout` flag natively, or does the skill need to implement per-platform spawning and result capping itself?
- When phase 3 adds a report-visible project-intelligence section, will it read from `ctx.agent_reach_items` directly, or will a new renderer adapter be introduced?

---

### Round 2 Feedback

Status: Ready to implement

---

Findings:

- **[Severity: Resolved] All Round 1 blockers addressed.**
  Codex accepted every Round 1 item and updated the design accordingly:
  - Insertion point moved after `quality_gate_skill` (`scripts/utils/report_skills/__init__.py`), preventing unfiltered Agent-Reach data from bypassing the existing gate.
  - `agent_reach_items` stored exclusively on `ctx`; `stock_raw` mutation is prohibited in phase 1.
  - `agent_reach_query_skill.py` replaces the generic name; `generate_agent_reach_queries()` is required as a pure, testable function.
  - Per-stock total CLI budget (60 s) and serialized/bounded subprocess rules added.
  - Adapter contract tests for missing URL, publish time, interaction score, and empty content required in acceptance gates.
  - Pipeline integration tests updated to cover disabled/default and enabled optional modes.

- **[Severity: Low] `build_stock_report_pipeline` signature does not yet expose `enable_agent_reach`.**
  The design states "Optional per-run input override: `enable_agent_reach=True`" but does not specify whether this is a builder parameter or a runtime context key. The current `build_stock_report_pipeline(llm_client=None)` in `scripts/utils/report_skills/__init__.py` returns a fixed 11-skill list. If Agent-Reach is enabled, the skill count becomes 13. The implementation task should decide whether to:
  (a) add `enable_agent_reach: bool = False` to the builder signature, or
  (b) always include the two new skills and let them no-op when disabled.
  Option (a) is preferred because it preserves the existing `len(pipeline.skills) == 11` contract for the default case.

- **[Severity: Low] `SynthesisSkill` is not in "Files Expected To Change" but `adapt_all` signature will expand.**
  `scripts/utils/report_skills/synthesis_skills.py:83-92` calls `adapt_all(xueqiu_items=..., zhihu_items=..., ...)`. Adding `agent_reach_items` as a new optional parameter to `adapt_all` is safe because `SynthesisSkill` does not pass it. However, the implementation guardrail must explicitly prohibit modifying `SynthesisSkill._build_synthesis_items()` in phase 1 to pass `agent_reach_items`; otherwise Agent-Reach data would enter `KnowledgeSynthesizer` prematurely.

- **[Severity: Low] `cross_source_consolidation_skill` is not in "Files Expected To Change."**
  The current `cross_source_consolidation_skill` (`scripts/utils/report_skills/analysis_skills.py`) deduplicates `keep_posts + zhihu report_items`. Since `agent_reach_items` lives only on `ctx` and is not fed into consolidation or synthesis in phase 1, no change is needed. This is correct, but the implementation task should confirm that no downstream skill reads `ctx.agent_reach_items` unexpectedly.

---

Implementation Guardrails:

1. **Do not modify `SynthesisSkill._build_synthesis_items()` in phase 1.** `agent_reach_items` must not be passed to `adapt_all()` or `KnowledgeSynthesizer.synthesize()` until phase 4.
2. **Do not mutate `stock_raw` or `raw_data` in any new skill.** Use `ctx.set()` / `ctx.get()` exclusively.
3. **Preserve the existing 11-skill default.** `build_stock_report_pipeline()` without `enable_agent_reach=True` must return exactly 11 skills so existing tests and callers remain stable.
4. **Agent-Reach adapters must use `.get("field", "")` for all string fields.** `SynthesisItem` fields `title`, `content`, `author`, `source_platform`, `url`, `publish_time` are required strings; passing `None` will raise a dataclass validation error.
5. **Agent-Reach disabled skills must be fast and silent.** When `ENABLE_AGENT_REACH` is unset and `enable_agent_reach` is not passed, the skills should set status and return without subprocess, network, or LLM calls.
6. **Keep `deep_analysis_renderer.py`, `scoring_engine.py`, `technical_analyzer.py`, and entry scripts untouched in phase 1.**

---

Open Questions:

- Should `build_stock_report_pipeline` accept `enable_agent_reach: bool = False` as a parameter, or should the two new skills always be present and self-disable?
- When the CLI binary is missing, should `agent_reach_status` be `"missing_binary"` or folded into `"disabled"` with a warning?

---

## Implementation Notes

### Summary

- Created `scripts/utils/report_skills/agent_reach_query_skill.py` with deterministic `generate_agent_reach_queries()` and `agent_reach_query_skill`.
- Created `scripts/utils/report_skills/agent_reach_skill.py` with safe subprocess runner, JSON/JSONL parser, dedupe, per-stock budget, and `agent_reach_fetch_skill`.
- Added `AgentReachAdapter` to `scripts/utils/source_adapter.py` and expanded `adapt_all(agent_reach_items=...)` without breaking existing callers.
- Modified `scripts/utils/report_skills/__init__.py` to add `enable_agent_reach: bool = False` parameter; when `True`, inserts two new skills after `quality_gate_skill`.
- All output stored on `ctx` only; `stock_raw` and `raw_data` are never mutated.
- `SynthesisSkill._build_synthesis_items()` is untouched; `agent_reach_items` does not enter `KnowledgeSynthesizer` in phase 1.

### Files Changed

- `scripts/utils/report_skills/agent_reach_query_skill.py` — new
- `scripts/utils/report_skills/agent_reach_skill.py` — new
- `scripts/utils/source_adapter.py` — added `AgentReachAdapter`, expanded `adapt_all`
- `scripts/utils/report_skills/__init__.py` — added `enable_agent_reach` builder parameter
- `tests/reporter/test_agent_reach_skills.py` — new
- `tests/utils/test_source_adapter.py` — added malformed/missing-field Agent-Reach tests
- `tests/reporter/test_pipeline_integration.py` — added default/enabled pipeline assertions

### Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/utils/test_source_adapter.py -q` | 23 passed | All focused skill and adapter tests green |
| `python3 -m pytest tests/reporter/test_pipeline_integration.py -q` | 5 passed | Default 11-skill, enabled 13-skill, disabled no-subprocess assertions green |
| `python3 -m pytest tests/reporter/test_synthesis_skills.py -q` | 3 passed | Synthesis behavior unchanged |

### Local Command Used

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/utils/test_source_adapter.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py -q
python3 -m pytest tests/reporter/test_synthesis_skills.py -q
```

### Deviations From Task

- None.

### Blockers Or Follow-Ups

- None.
