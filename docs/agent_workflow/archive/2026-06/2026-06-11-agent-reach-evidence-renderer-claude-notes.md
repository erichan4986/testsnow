# Claude Code Review Round 1: Agent-Reach Phase 3 Evidence Renderer

### Round 1 Feedback

Status: Ready to implement

---

Findings:

- **[Severity: Resolved] Standalone `AgentReachEvidenceRenderer` is the correct boundary.**
  Separating the renderer from `DeepAnalysisRenderer` avoids coupling external evidence with LLM-synthesized narrative. The current renderer contract (`render(ctx) -> str`, `required_keys() -> List[str]`) in `scripts/utils/reporter/sections/` supports this cleanly.

- **[Severity: Resolved] Position after `deep_analysis` and before `risk` is appropriate.**
  The existing `RENDERERS` list in `scripts/utils/report_skills/assembly_skills.py:35-43` is:
  `executive_summary -> composite_score -> valuation -> technical -> price_target -> deep_analysis -> risk`.
  Inserting the Agent-Reach evidence section after the LLM deep analysis and before risk lets users contextualize raw evidence against synthesized conclusions without mixing the two.

- **[Severity: Medium] Renderer must defend against `agent_reach_quality_results` being out of sync with item lists.**
  The design assumes `agent_reach_quality_results` exists and aligns with `keep_items`/`demote_items`. If the quality skill was skipped (e.g. `timeout` with zero items -> "skipped"), `quality_results` is an empty list, but the renderer should not raise if `keep_items` is unexpectedly non-empty (defensive programming). Recommend building a lookup dict keyed by `(title, source, url)` rather than relying on list index alignment.

- **[Severity: Medium] `required_keys()` should be permissive to avoid breaking default reports.**
  If `AgentReachEvidenceRenderer.required_keys()` requires `agent_reach_keep_items`, then `ReportAssemblySkill._render_section()` will log a warning and skip the section when Agent-Reach is disabled. This is acceptable behavior, but the key list should only include keys that are genuinely needed for rendering, not keys that are nice-to-have. A better contract: require `agent_reach_enabled` and `agent_reach_quality_status`, and let the renderer return `""` when disabled or empty.

- **[Severity: Low] Truncation of Chinese excerpts at 120 characters needs byte-length safety, not character-count safety.**
  The design suggests truncating to 120 Chinese characters. Python `len()` on a Chinese string counts characters (not bytes), so `text[:120]` is safe for Markdown. This is fine as stated.

- **[Severity: Low] Markdown pipe escaping in `reasons` is mentioned but not specified.**
  The design says "escape Markdown table separators (`|`) in title, excerpt, source, reasons." For `reasons`, which is a list of strings, the renderer should join them with a delimiter that does not contain `|`, or escape each reason individually before joining. Recommend joining with `; ` and escaping any remaining `|`.

- **[Severity: Low] `sections/__init__.py` needs to export the new renderer.**
  `scripts/utils/reporter/sections/__init__.py` maintains explicit imports and `__all__`. The design notes this file but it is not in the "Files Expected To Change" table. It should be added.

- **[Severity: Low] The data-source condition is correctly conservative.**
  `_data_sources()` should append `Agent-Reach外部检索` only when enabled, quality status is "ok", and at least one keep/demote item exists. This prevents disabled or failed runs from polluting the header.

---

Recommendations:

1. **Build a defensive quality-result lookup, not index alignment.**
   In the renderer, create `{ (r["title"], r["source"], r["url"]): r for r in quality_results }`. If a `keep_item` has no matching quality result, render score as `"—"` and reasons as `"未评分"` rather than raising `IndexError`.

2. **`required_keys()` should return `["agent_reach_enabled", "agent_reach_quality_status"]` (or empty list).**
   The renderer itself should handle the "disabled/empty -> return empty string" logic. Requiring `agent_reach_keep_items` would cause the section to be skipped entirely in reports where Agent-Reach is disabled, which is acceptable, but returning an empty string is more explicit and testable.

3. **Add tests for malformed/defensive cases:**
   - `keep_items` contains an item with no matching quality result.
   - `quality_results` is empty but `keep_items` is non-empty (should render with placeholder score).
   - Item `title` contains `|` (verify escaping).
   - Item `publish_time` is empty string (should render `—`).
   - `agent_reach_enabled=True` but `agent_reach_quality_status="skipped"` (should return empty string).

4. **Add `sections/__init__.py` to the "Files Expected To Change" table.**
   It must import and export `AgentReachEvidenceRenderer`.

5. **Keep the intro note verbatim as designed.**
   `> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。` is a clear disclaimer that prevents user misinterpretation.

---

Open Questions:

- Should the renderer support a `max_keep` / `max_demote` parameter on the class for easier test parameterization, or should the caps (6/4) remain hard-coded constants?
- When `agent_reach_enabled=True` but `quality_status="empty"`, should the renderer return `""` silently, or render a one-line note like `> Agent-Reach 未检索到可用外部证据。`? The design currently recommends silent for disabled and short status note for enabled-but-empty; either is fine, but the test should lock the behavior.

---

## Implementation Notes

## Summary

- Created `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` with `AgentReachEvidenceRenderer`.
- Renderer uses `(title, source_platform, url)` lookup dict for quality metadata, not index alignment.
- `required_keys()` returns `["agent_reach_enabled", "agent_reach_quality_status"]`; renderer returns `""` for disabled/skipped/error and renders empty note for empty status.
- Inserted into `ReportAssemblySkill.RENDERERS` after `deep_analysis` and before `risk`.
- `_data_sources()` appends `Agent-Reach外部检索` only when enabled + quality_status="ok" + keep/demote non-empty.
- `sections/__init__.py` exports `AgentReachEvidenceRenderer`.
- All forbidden files (SynthesisSkill, KnowledgeSynthesizer, scoring_engine, source_adapter, quality_skill, entry scripts, Xueqiu/CDP) were not modified.

## Files Changed

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` — new
- `scripts/utils/reporter/sections/__init__.py` — added import/export
- `scripts/utils/report_skills/assembly_skills.py` — inserted renderer into RENDERERS, updated _data_sources()
- `tests/reporter/test_agent_reach_evidence_renderer.py` — new (12 tests)
- `tests/reporter/test_assembly_skills.py` — added ordering and data-source header tests (5 tests)

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q` | 19 passed | All renderer and assembly tests green |
| `python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q` | 8 passed | Pipeline and synthesis unchanged |

## Local Command Used

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

## Deviations From Design

- None.

## Blockers Or Follow-Ups

- None.
