# Claude Review Round 1: Synthesis Source Boundary And External Viewpoint Taxonomy

Date: 2026-06-29

Review target:

```text
docs/agent_workflow/2026-06-29-synthesis-source-boundary-and-external-viewpoint-taxonomy-design.md
```

## Prompt For Claude Code

You are Claude Code in `/Users/erichan/testsnow`.  Do a read-only design
review.  Do not modify code.

Goal:

Review the proposed design for splitting `## 四、深度分析` into:

- `4.1-4.3`: canonical research layer using high / medium-high credit sources;
- `4.4`: external viewpoint layer for WeChat / Zhihu / Xueqiu / social or
  industry-media observations, grouped by topic and kept display-only.

Context:

- Current report system recently added a generic entry:
  `python3 scripts/run_stock_report.py --stock <股票名>`.
- 中际旭创 and 圣邦股份 formal runs now generate meaningful `4.1-4.3` from
  A-share source_intake materials.
- 中际旭创 and 黑芝麻智能 have cached curated-external `4.4` narratives.
- The current implementation still lets Xueqiu `keep_posts` and
  `zhihu.report_items` enter canonical synthesis, which may blur the source
  boundary.
- We want to plan the next step before coding.

Review tasks:

1. Read the design file completely.
2. Check whether the proposed source boundary is internally consistent.
3. Check whether excluding Xueqiu / Zhihu / WeChat from `4.1-4.3` could make
   reports too thin, especially for HK stocks or stocks without enough
   source_intake coverage.
4. Check whether the six-topic `4.4` taxonomy is sufficient and not too broad.
5. Check whether the cross-verified social viewpoint exception is safe enough:
   social source discovers the theme, formal source supports the claim, and
   `4.1-4.3` cites the formal source only.
6. Check whether broker research should be allowed in `4.1-4.3` as canonical
   professional analysis, or whether the design needs a stricter split between
   confirmed facts and professional opinions.
7. Check whether the rollout phases are safe and testable.
8. Check for missing tests / failure modes.

Output:

Write the review to:

```text
/tmp/synthesis_source_boundary_taxonomy_review_round1.md
```

Format:

- Overall status: one of
  - `ready_to_implement_preview`
  - `must_fix_before_task`
  - `needs_redesign`
- Blockers
- Must-fix before implementation
- Nice-to-have
- Specific recommendations for:
  - 4.1-4.3 source policy
  - 4.4 taxonomy
  - cross-verified social bridge
  - rollout / tests
- Final recommendation: whether to proceed to a preview-only implementation
  task.

Constraints:

- Do not edit repository files.
- Do not run report generation.
- Do not call LLM APIs.
- Do not access external websites.
- Do not propose changes to scoring, technical analysis, risk scoring, EV,
  target price, or final recommendation unless you mark them explicitly out of
  scope for this task.
