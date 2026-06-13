# Claude Code Review Round 1: Agent-Reach Quality Gate Phase 2

### Round 1 Feedback

Status: Ready to implement

---

Findings:

- **[Severity: Resolved] Dedicated `agent_reach_quality_skill.py` is the correct boundary.**
  The design keeps Agent-Reach quality filtering separate from `ContentQualityGate` (`scripts/utils/content_quality_gate.py`), which is Xueqiu-centric and includes LLM fallback logic. A standalone deterministic skill avoids coupling social-web heuristics to existing hard-gate/LLM-assessor pipelines and preserves Xueqiu behavior.

- **[Severity: Resolved] Scoring heuristics are transparent, deterministic, and testable.**
  The 0-100 rule score with explicit dimension weights (relevance 25, credibility 25, evidence 20, substance 20, engagement 10) and threshold boundaries (keep >= 60, demote >= 35, discard < 35) can be unit-tested with fixed inputs. No LLM or external dependency is required.

- **[Severity: Resolved] Default pipeline stays 11 skills; enabled becomes 14 skills.**
  The design inserts `agent_reach_quality_skill` inside the existing `if enable_agent_reach:` block in `scripts/utils/report_skills/__init__.py`, after `agent_reach_fetch_skill` and before `cross_source_consolidation_skill`. This matches the current builder structure and requires only adding one skill to the extend list.

- **[Severity: Resolved] Agent-Reach data remains isolated from `SynthesisSkill`.**
  The design explicitly prohibits modifying `SynthesisSkill._build_synthesis_items()`. Current code (`scripts/utils/report_skills/synthesis_skills.py:83-92`) calls `adapt_all()` without `agent_reach_items`. Phase 2 outputs (`agent_reach_keep_items`, etc.) are stored only on `ctx` and are not consumed by any downstream skill in the default pipeline.

- **[Severity: Resolved] Status handling covers all Phase 1 terminal states.**
  Disabled, missing_binary, error, timeout (with/without partial items), empty, and ok are all mapped to quality statuses (disabled/skipped/ok/empty). Partial-timeout scoring is explicitly required, which matches Phase 1 fetch skill behavior where timeout can still yield partial `agent_reach_items`.

- **[Severity: Low] `score_agent_reach_item()` relevance scoring may need `search_queries` for query-term matching.**
  The heuristic says "Text contains stock name, code, or product/industry terms from generated queries." The pure function signature only accepts `SynthesisItem` and optional `stock_name`. If query-term matching is desired (e.g. matching "量产" or "客户定点"), the skill wrapper should pass `search_queries` from `ctx` into the scorer. This is an implementation detail, not a blocker.

- **[Severity: Low] Source-credibility inspection of `extra.raw` must tolerate missing keys gracefully.**
  The design says check `extra.raw.is_official`, `verified`, `account_type == "official"`, etc. Since `AgentReachAdapter` stores the entire raw record under `extra["raw"]`, the scorer must use chained `.get()` calls. This is implied by the design but worth highlighting in the implementation task.

- **[Severity: Low] `agent_reach_quality_results` metadata-only shape should avoid duplicating full content.**
  The design recommends storing metadata/reasons only in `agent_reach_quality_results`, while full items stay in `agent_reach_keep_items`/`demote_items`/`discard_items`. This avoids bloating ctx with duplicated text.

---

Recommendations:

1. **Keep `score_agent_reach_item()` as a pure function and pass `search_queries` from the skill wrapper if query-term matching is needed.** This preserves testability.
2. **Use `item.extra.get("raw", {}).get("is_official", False)` style access in the scorer.** Do not assume any social-platform metadata keys exist.
3. **Update `tests/reporter/test_pipeline_integration.py` to assert 14 skills when enabled and confirm `agent_reach_quality_skill` position.** The existing Phase 1 test asserts 13 skills.
4. **Add a test for partial-timeout scoring:** mock fetch skill producing `agent_reach_status="timeout"` with one item, then run quality skill and assert `agent_reach_quality_status="ok"` and the item is scored.

---

Open Questions:

- Should `agent_reach_quality_results` include the original `agent_reach_status` from fetch for audit traceability (e.g. `{"fetch_status": "timeout", "quality_status": "ok", ...}`)?

---

## Implementation Notes

## Summary

- Created `scripts/utils/report_skills/agent_reach_quality_skill.py` with deterministic `score_agent_reach_item()` and `agent_reach_quality_skill`.
- Scorer uses five dimensions (relevance 25, credibility 25, evidence 20, substance 20, engagement 10) with transparent thresholds (keep >= 60, demote >= 35, discard < 35).
- No LLM, subprocess, network, or browser calls in the quality skill.
- Skill inserted after `agent_reach_fetch_skill` and before `cross_source_consolidation_skill` when `enable_agent_reach=True`.
- Default `build_stock_report_pipeline()` remains 11 skills; enabled returns 14 skills.
- All output stored only on `ctx` (`agent_reach_keep_items`, `agent_reach_demote_items`, `agent_reach_discard_items`, `agent_reach_quality_results`, `agent_reach_quality_status`, `agent_reach_quality_summary`).
- `SynthesisSkill`, `KnowledgeSynthesizer`, `scoring_engine`, `ContentQualityGate`, renderers, and entry scripts are untouched.
- `agent_reach_quality_results` stores compact metadata only (no full content duplication); each result includes `fetch_status` and `quality_status` for audit traceability.

## Files Changed

- `scripts/utils/report_skills/agent_reach_quality_skill.py` — new
- `scripts/utils/report_skills/__init__.py` — imported quality skill, inserted into enabled pipeline
- `tests/reporter/test_agent_reach_quality_skill.py` — new
- `tests/reporter/test_pipeline_integration.py` — updated to assert 14 skills and quality skill position

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py -q` | 29 passed | All focused quality/skill tests green |
| `python3 -m pytest tests/reporter/test_pipeline_integration.py -q` | 5 passed | Default 11-skill, enabled 14-skill, ordering assertions green |
| `python3 -m pytest tests/reporter/test_synthesis_skills.py -q` | 3 passed | Synthesis behavior unchanged |

## Local Command Used

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py -q
python3 -m pytest tests/reporter/test_synthesis_skills.py -q
```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
