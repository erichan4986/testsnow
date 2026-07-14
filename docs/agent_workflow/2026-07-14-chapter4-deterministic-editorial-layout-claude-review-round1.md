# Claude Review Round 1: Chapter 4 Deterministic Editorial Projection

你是只读设计审查模型。工作目录：

`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

完整阅读：

- `docs/agent_workflow/2026-07-14-chapter4-deterministic-editorial-layout-design.md`
- `docs/agent_workflow/2026-07-13-report-quality-optimization-roadmap.md`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`
- 对应 tests。

只审查，不写代码，不生成报告，不联网，不修改 data/knowledge/reports。

重点检查：

1. formal-medium 的 `Chapter4ViewModel` 是否是全部 display rows 的正确 owner；formal-thin 仅复用 shared annual selector、保留既有 broker/external adapters 的受控 split 是否更安全；renderer 是否仍存在第二套 annual selection。
2. annual role budgets 与排序是否确定、可测试，会不会误改完整 snapshot/memo。
3. broker attribution diversity 和 external exact dedupe 是否会丢失关键分歧或引入模糊规则；formal-medium/formal-thin 的 external 不设 hard cap 时 renderer 是否仍残留 `[:N]`。
4. formal-thin 的 annual/broker/external offset 公式是否严格基于 full snapshot；隐藏最高 annual ref 后是否仍安全。
5. 删除新版路径的 `本节引用来源` 后，全局 `_visible_citations_only()` 是否足以保证无 missing/unused/orphan。
6. `source_intake_render_section` 是否能仅隐藏整节而不关闭 intake/material context；默认 False 是否有未覆盖的调用方回归。
7. formal-rich legacy 是否真正不受影响。
8. runtime `+80` 目标、`+140` hard stop 是否可信，哪些旧 renderer 逻辑必须删除而非叠加。
9. Required Tests 是否足以捕获 source boundary、citation drift、attribution 和 layout 回归。
10. 是否误触 producer、profile、scoring、target、risk、technical、recommendation 或 LLM prompt。

把结果写入：

`docs/agent_workflow/2026-07-14-chapter4-deterministic-editorial-layout-claude-review-round1-notes.md`

输出格式：

```text
verdict: ok | needs_revision | blocked

summary:

blockers:
  - id:
    issue:
    evidence:
    required_change:

must_fix:
  - id:
    issue:
    evidence:
    required_change:

nice_to_have:
  - id:
    suggestion:

contract_review:
  chapter4_view_model:
  formal_thin_offsets:
  global_citations:
  source_intake_toggle:
  formal_rich_regression:

requirement_test_gaps:
  - requirement:
    missing_test:

scope_and_budget:
  allowed_files:
  runtime_budget:
  deletion_candidates:

implementation_ready: yes | no
recommended_next_step:
```

若没有 finding，对相应列表写 `[]`。引用真实函数、测试和行号；不要只复述设计稿。
