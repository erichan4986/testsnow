# Claude Code Review Round 1: Agent-Reach Phase 3B Themed Evidence

### Round 1 Feedback

Status: Ready to implement

---

Findings:

- **[Severity: Resolved] Upgrading the existing `AgentReachEvidenceRenderer` is the correct boundary.**
  The design modifies only the renderer internals (`scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`) without adding new pipeline skills, new renderers, or new assembly logic. This preserves the Phase 3 safety boundary: no pipeline skill count changes, no new `ctx` keys, and no assembly/RISKERS impact.

- **[Severity: Resolved] Deterministic topic classification is sufficient for a display layer.**
  The six topics (`product_progress`, `customer_orders`, `competition`, `earnings_business`, `market_sentiment`, `to_verify`) cover the five standard A/H stock research angles plus a fallback. The "first match wins" rule with a fixed order is deterministic, testable, and requires no LLM.

- **[Severity: Low] Some keywords are stock-specific but acceptable as a first pass.**
  The `customer_orders` topic includes `比亚迪, 理想, 蔚来, 小鹏` and `competition` includes `英伟达, 高通, 地平线, Mobileye`. These are appropriate for 黑芝麻智能 but may misfire on unrelated A/H stocks. This is acceptable for Phase 3B because the fallback `to_verify` will catch mismatches, but recommend adding a note that topic keywords should be extracted from `COMPETITOR_MAP` / `INDUSTRY_MAP` in a future phase.

- **[Severity: Low] Demote items grouped under a single `待人工复核线索` subsection is the right call.**
  Separating demote items into topic groups would imply they are credible enough to be part of the thematic evidence. Keeping them in one consolidated "weak signal" bucket correctly signals lower confidence.

- **[Severity: Low] Topic order is appropriate for automotive-semiconductor research.**
  `product_progress -> customer_orders -> competition -> earnings_business -> market_sentiment` places operational evidence before financial/market noise, which aligns with fundamental-research priority.

- **[Severity: Low] `tests/reporter/test_assembly_skills.py` should not need changes, but verify no regression.**
  The design correctly lists `assembly_skills.py` and `test_assembly_skills.py` as files that "should not need changes." However, any renderer signature change (e.g., adding new helper imports) should not break assembly. The existing `ReportAssemblySkill._render_section()` only calls `required_keys()` and `render(ctx)`, so internal renderer refactoring is safe.

- **[Severity: Low] Design preserves all Phase 3 defensive behaviors.**
  Markdown escaping, 120-character truncation, `(title, source, url)` quality-result lookup, missing-metadata fallback, disabled/empty/skip states, and caps (6 keep / 4 demote) are all explicitly preserved. No regression risk.

---

Recommendations:

1. **Keep the upgrade inside the existing renderer only.** No new pipeline skills, no new assembly changes, no new `ctx` outputs.

2. **Make `classify_agent_reach_topic()` a pure standalone helper inside the renderer module.** This keeps it unit-testable without instantiating the renderer.

3. **Add explicit classification-order tests.** Tests should assert that a record containing keywords from multiple topics (e.g. both `量产` and `营收`) gets classified by the first matching topic in the fixed order, not the highest-scoring one.

4. **Add a test for the `to_verify` fallback.** A record with no matching keywords should classify as `待核查线索` and still render in the output (not be hidden).

5. **Document the stock-specific keywords as a known limitation.** Add a comment near the keyword lists noting that `比亚迪, 理想, ...` are 黑芝麻智能-centric and should be generalized later.

---

Open Questions:

- Should the overview bullet list include demote topics, or only keep topics? The design says "主要主题" without specifying; recommend showing only keep-item topics in the overview to avoid overstating weak signals.
- Should the topic classification inspect `quality_result["reasons"]` in addition to title/content? The design says "Use title + content + quality reasons text" — this is fine but should be tested.

---

## Implementation Notes

## Summary

- Modified `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` to add deterministic topic classification and themed grouping.
- Added `classify_agent_reach_topic()` pure helper with six topics and fixed keyword lists.
- Added stock-centric keyword comment as requested in task.
- Changed render output from raw `高优先级证据`/`低优先级观察` tables to:
  - `本期外部证据概览` summary with counts, keep-item topics, and status
  - `主题化证据观察` with topic-grouped tables for keep items
  - `待人工复核线索` subsection for demote items
- Overview `主要主题` only shows keep-item topics, not demote topics.
- All Phase 3 defensive behaviors preserved: Markdown escaping, 120-char truncation, `(title, source, url)` quality lookup, missing-metadata fallback, disabled/empty/skip silence, caps (6 keep / 4 demote).
- No assembly, pipeline, synthesis, scoring, entry script, or Xueqiu/CDP files modified.

## Files Changed

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` — added `classify_agent_reach_topic()`, rewrote render logic for themed grouping
- `tests/reporter/test_agent_reach_evidence_renderer.py` — 24 tests covering classification, themed rendering, and all existing regressions

## Files NOT Changed

- `scripts/utils/report_skills/assembly_skills.py` — no changes needed, renderer contract unchanged
- `scripts/utils/reporter/sections/__init__.py` — no changes needed, existing export sufficient
- `tests/reporter/test_assembly_skills.py` — no changes needed, no regressions

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q` | 24 passed | All classification and themed rendering tests green |
| `python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q` | 15 passed | No regressions in assembly, pipeline, or synthesis |

## Local Command Used

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

## Deviations From Design

- None.

## Blockers Or Follow-Ups

- None.
