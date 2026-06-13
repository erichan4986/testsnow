# Codex Review: Agent-Reach Fundamental Research Phase 1

> **Date**: 2026-06-11
> **Design**: `docs/agent_workflow/2026-06-11-agent-reach-fundamental-research-design.md`
> **Task**: `docs/agent_workflow/2026-06-11-agent-reach-fundamental-research-claude-task.md`
> **Status**: Accepted after Codex follow-up fixes

## Scope Review

| Check | Result | Notes |
|-------|--------|-------|
| Default pipeline remains 11 skills | Pass | `build_stock_report_pipeline()` default unchanged by behavior. |
| Optional Agent-Reach pipeline has 13 skills | Pass | New skills inserted after `quality_gate_skill`. |
| No synthesis prompt/report renderer/scoring changes for Agent-Reach | Pass | No `agent_reach` references in no-touch files. Existing unrelated dirty files remain outside this review. |
| No `stock_raw`/`raw_data` mutation | Pass | New skills write Agent-Reach output to `ctx` only. |
| Disabled mode avoids subprocess/network/LLM | Pass | Focused test asserts runner is not called. |

## Codex Follow-Up Fixes

- Added regression coverage for partial timeout behavior: if one command succeeds and a later command times out, keep collected items but set `agent_reach_status = "timeout"`.
- Added regression coverage for per-query/platform cap: one platform response with more than 10 records is truncated to 10.
- Added regression coverage for parse failures: non-empty invalid CLI output sets `agent_reach_status = "error"`.
- Fixed `agent_reach_fetch_skill` to enforce the per-query/platform cap and preserve timeout status when partial results exist.

## Tests Run

| Command | Result |
|---------|--------|
| `python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/utils/test_source_adapter.py -q` | 27 passed |
| `python3 -m pytest tests/reporter/test_pipeline_integration.py -q` | 5 passed |
| `python3 -m pytest tests/reporter/test_synthesis_skills.py -q` | 3 passed |

## Follow-Ups

- Phase 2 should add a dedicated quality gate for Agent-Reach `SynthesisItem` records before any report-visible usage.
- Phase 3 should render only sourced factual bullets/timelines, not LLM conclusions.
- Phase 4 prompt integration still requires user review of sample LLM output.
