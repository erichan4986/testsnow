# Claude Read-Only Review Prompt: Technical Entry Consolidation Batch C

Worktree: `/Users/erichan/testsnow`

Read:

- `docs/agent_workflow/2026-08-04-technical-entry-consolidation-batch-c-design.md`
- `AGENTS.md`
- the three `scripts/run_*技术分析_真实数据.py` entries;
- `scripts/utils/data_collector.py`;
- `scripts/utils/reporter/technical_analyzer.py`;
- `scripts/utils/reporter/sections/technical_renderer.py`;
- the tests named by the design.

Perform a read-only design review. Do not edit runtime, tests, configuration,
prompts, data, knowledge, or reports. Verify the design against actual imports,
direct-script execution semantics, payload shapes, renderer requirements, and
stock-specific side effects.

Pay particular attention to:

1. whether the proposed `scripts/utils` import root works for all three direct
   script invocations without adding a second import strategy;
2. whether Zhongjian analyzer output and collector output can be projected by
   one explicit function without dropping judgment, target, fund-flow, concept,
   or resonance fields;
3. whether current `market_resonance` is the correct diagnostic projection and
   retiring entry-level `market_regime` access is behaviorally safe;
4. whether Montage raw/weekly CSV side effects and all exact acquisition
   parameters remain wrapper-owned;
5. whether empty/sparse payload handling changes technical decisions or only
   improves boundary diagnostics;
6. whether the TDD plan can test wrappers without network or repository output;
7. whether the 180-line minimum net deletion is credible without dense or
   readability-damaging code.

Write findings to:

`docs/agent_workflow/2026-08-04-technical-entry-consolidation-batch-c-claude-review-round1-notes.md`

Use `blocker`, `must-fix`, and `nice-to-have`; include a requirement-test matrix,
scope audit, exact runtime deletion estimate, and
`implementation_ready: yes|no`. Stop after writing notes. Do not implement or
commit.
