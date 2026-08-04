# Scripts 全栈审计 Batch A — Claude Code 只读 Review Prompt

你是只读代码审查模型，在以下 worktree 审查一个确定性死代码清理设计：

`/Users/erichan/testsnow/.worktrees/annual-producer-v2`

完整阅读：

- `docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-design.md`
- `AGENTS.md`

并核对真实代码、import、动态 registry、preview/tool/README 契约和 tests。不要只复述设计。

重点回答：

1. A1-A5 每个删除项是否真的没有 active 调用或必须保留的公共兼容契约？
2. `PriceTargetRenderer` 是否已被 `TechnicalRenderer` 完整替代，删除 package export 是否安全？
3. `fetch_index_bars` 是否确实被 v2 technical cache/index owner 替代？
4. 三个 fulltext `*_from_cache` wrapper 是否可删，而 rows helpers 与 preview/public入口仍完整？
5. `v2_note_card_fingerprint`、plural external document helper、`RequiredMetricsError` 是否存在动态或仓库外合理使用风险？
6. focused tests、full suite、offline smoke 是否覆盖主要 failure modes？
7. 净减不少于 185 runtime 行是否可信，是否存在通过删兼容能力换行数的问题？
8. 主仓库后续同步边界是否足够安全？

输出写入：

`docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-claude-review-round1-notes.md`

格式必须包含：

- `verdict: ok | needs_revision`
- `blockers`
- `must_fix`
- `nice_to_have`
- 每个 A1-A5 的 `safe | revise | defer` 判断与证据
- requirement-test gaps
- scope / compatibility audit
- runtime deletion budget audit
- `implementation_ready: yes | no`

只读约束：

- 不修改源码、测试、配置、prompt、data、knowledge、reports；
- 除上述 review notes 外不写任何文件；
- 不联网、不运行报告、不启动 Chrome/CDP、不抓雪球；
- 不提交、不推送。

完成 notes 后停止，等待 Codex 读取真实审查结果。
