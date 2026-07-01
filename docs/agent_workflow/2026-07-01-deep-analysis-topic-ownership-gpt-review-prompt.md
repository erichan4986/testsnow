# GPT Review Prompt: Deep Analysis Topic Ownership And Repetition Control

You are reviewing a Chinese A/HK stock research report generation repository.

Your task is a read-only design and code-quality review. Do not propose direct code edits unless asked. Focus on whether the design is safe, sufficient, and not over-engineered.

## Context

The repo generates Chinese stock reports with:

- 4.1 产业逻辑与竞争格局
- 4.2 业绩路径与多空分歧
- 4.3 资金面与催化剂时间线
- 4.4 精选外部观察（Preview）

Current source policy:

- 4.1-4.3 are canonical main analysis and should use formal / professional sources.
- 4.4 is display-only external viewpoints from WeChat / Xueqiu / Zhihu / curated social sources.
- 4.4 must not affect score, risk, EV, summary, or final recommendation.

Recent work already fixed:

- source-boundary separation,
- citation format `[n]` -> `[^n]`,
- duplicate 4.4 footnotes,
- recommendation / EV / entry / risk consistency,
- stale Wind data handling for HK stock technical analysis.

The remaining problem is editorial structure: 4.1-4.3 sometimes repeat the same themes across sections. The advisory checker flags `repeated_theme_across_sections`, but the repo needs a clearer design for topic ownership and repetition control.

## Files In This Packet

Please review these files:

- `docs/agent_workflow/2026-07-01-deep-analysis-topic-ownership-design.md`
- `docs/agent_workflow/2026-06-30-deep-analysis-prose-structure-design.md`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_prose_quality.py`
- `scripts/check_report_prose_quality.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_report_prose_quality.py`
- `sample_reports/zhongji_20260701_deep_analysis_excerpt.md` if present
- `sample_reports/heizhima_20260701_deep_analysis_excerpt.md` if present
- `sample_reports/shengbang_20260701_deep_analysis_excerpt.md` if present

## Review Goals

Evaluate:

1. Whether the proposed topic ownership contract is a good boundary for 4.1 / 4.2 / 4.3.
2. Whether the "borrowed theme budget" can reduce repetition without deleting necessary context.
3. Whether the proposed deterministic checker is too heuristic or too brittle.
4. Whether the design preserves citation traceability and formal-first source boundaries.
5. Whether the implementation phases are safe and testable without excessive LLM/API runs.
6. Whether this design risks making reports too table-heavy or too mechanical.

## Required Output Format

Return your review in this structure:

```yaml
verdict: ready | needs_revision | risky
summary: >
  One paragraph summary.
blockers:
  - id: B1
    title: ...
    evidence: ...
    recommendation: ...
must_fix:
  - id: M1
    title: ...
    evidence: ...
    recommendation: ...
nice_to_have:
  - id: N1
    title: ...
    recommendation: ...
design_assessment:
  topic_ownership: ...
  borrowed_theme_budget: ...
  checker_precision: ...
  citation_safety: ...
  source_boundary_safety: ...
  implementation_sequence: ...
recommended_next_step: ...
```

If you think a concern is speculative, label it as such. Do not invent code behavior that is not visible in the provided files.
