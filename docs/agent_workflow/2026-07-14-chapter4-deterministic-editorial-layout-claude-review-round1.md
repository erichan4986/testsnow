# Claude Review Round 1: Chapter 4 Deterministic Editorial Projection

你是只读设计审查模型。工作目录：

`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

完整阅读：

- `docs/agent_workflow/2026-07-14-chapter4-deterministic-editorial-layout-design.md`
- `docs/agent_workflow/2026-07-13-report-quality-optimization-roadmap.md`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/utils/report_quality.py`
- `scripts/utils/report_skills/assembly_skills.py`
- 对应 tests。

只审查，不写代码，不生成报告，不联网，不修改 data/knowledge/reports。

重点检查：

1. formal-medium 的 `Chapter4ViewModel` 是否是全部 display rows 的正确 owner；formal-thin 仅复用 shared annual selector、保留既有 broker/external adapters 的受控 split 是否更安全；renderer 是否仍存在第二套 annual selection。
2. annual role budgets 与排序是否确定、可测试，会不会误改完整 snapshot/memo。
3. portrait reservation + `editorial_slot` 是否能删除 renderer `_select_annual_portrait_row()` 而不丢失画像；diagnostics 旧 key 语义是否保持。
4. broker attribution diversity 和 exact-title consensus 是否会误写共识；formal-thin forecast range 是否始终有 attribution。
5. external 三套替代投影是否保持 snapshot 完整、display 只按 narrative → reasoning → topic 选一套；shared dedupe key 是否严格为 exact body + canonical citation identities；formal-medium/formal-thin 不设 hard cap 时 renderer 是否仍残留 `[:N]`。
6. formal-thin 的 annual/broker/external offset 公式是否严格基于 full snapshot；隐藏最高 annual ref 后是否仍安全。
7. 删除新版路径的 `本节引用来源` 后，全局 `_visible_citations_only()` 是否足以保证无 missing/unused/orphan；更新后的 external title/body inline-footnote gate 是否能阻止“正文和全局表同时漏引用”而不误杀 fallback/legacy。
8. 4.4 固定 role priority、排除 portrait 和“不复写完整 body”是否确定且不产生新事实。
9. `source_intake_render_section` 的 top-level override / nested config 优先级是否只隐藏整节；periodic preview 显式恢复是否完整。
10. formal-rich legacy 是否真正不受影响。
11. runtime `+80` 目标、`+140` hard stop 是否可信，哪些旧 renderer 逻辑必须删除而非叠加。
12. Required Tests 是否足以捕获 source boundary、citation drift、attribution、preview 和 layout 回归。
13. 是否误触 producer、profile、scoring、target、risk、technical、recommendation 或 LLM prompt。

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
  preview_regression:
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
