# Claude Review Task: Formal-Medium Chapter 4.4 Retirement

你是只读设计审查模型。工作目录：

`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

请完整阅读：

- `docs/agent_workflow/2026-07-22-formal-medium-chapter44-retirement-design.md`
- `docs/agent_workflow/2026-07-22-formal-medium-chapter44-retirement-codex-self-review-round1-notes.md`

重点核对真实代码：

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_quality.py`
- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_report_quality.py`
- `tests/reporter/test_report_source_boundary.py`

只读审查以下问题：

1. 删除范围是否严格限定为 formal-medium 固定 price-path 4.4，且不会误删 formal-rich legacy external 4.4？
2. formal-thin 三节布局、full-snapshot citation offsets 是否保持不变？
3. `_select_price_path_rows`、`_select_price_row`、`_generic_broker_price_row` 和 `_formal_medium_price_path_section` 是否确实没有其他 runtime consumer？
4. `is_informative_variable_title`、`argument_complete` 等共享契约是否正确保留？
5. 从 `Chapter4ViewModel.sections` 移除 4.4 是否会导致 citation、quality/source-boundary、执行摘要、评分或其他隐藏 consumer 回归？
6. Tests 是否覆盖 formal-medium absence、formal-thin offset、formal-rich legacy 4.4、4.1--4.3 内容/引用不变和 dead-code removal？
7. Future reintroduction gate 是否足以阻止 renderer 再次生成无来源支撑的通用条件句？
8. 删除预算和 allowed scope 是否可信？

禁止：

- 不修改任何源码、测试、设计、配置、data、knowledge 或 reports。
- 不联网，不生成报告，不提交、不推送。

把结果写入：

`docs/agent_workflow/2026-07-22-formal-medium-chapter44-retirement-claude-review-round1-notes.md`

输出格式：

- `verdict: ok | needs_revision`
- blockers
- must-fix
- nice-to-have
- requirement-test gaps
- scope/budget audit
- implementation_ready: yes|no

若无 blocker/must-fix，明确说明可直接进入 implementation plan；不要为了形式要求 Round 2。
