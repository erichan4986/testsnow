# Claude Review Prompt — Peer Comparison Material Layer Round 1

把下面这段交给 Claude Code：

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一次只读设计审查。

目标：
审查 Codex 写的同行/对手材料层设计：
docs/agent_workflow/2026-07-02-peer-comparison-material-layer-design.md

背景：
复旦微电 trial 暴露出 4.1/4.2 同行对比不足。用户希望后续报告能形成：
产业趋势 -> 同行/产业平均 -> 公司暴露 -> 优于/劣于同行 -> 个股机会/待验证变量
的闭环。

但上一轮 review 已明确：
- 不要过早引入自动 peer research agent；
- Batch 3 不应新增 broad peer_source_queries；
- 4.1-4.3 必须保持 formal_first/source boundary；
- 社媒/雪球/知乎/微信只可 display-only 或 4.4，不支撑正式同行结论。

请重点审查：
1. 设计是否真的避免了 peer_source_queries / 自动联网 Agent 过早膨胀；
2. config shape 是否足够，但不会让 config/stocks.json 继续臃肿失控；
3. peer material pack 是否能支持“优于/劣于同行/产业平均”的结论，又不会让 LLM 编造 peer 数字；
4. peer pack 接入 4.1/4.2 是否会破坏 topic ownership 或让报告过度表格化；
5. quality gates 是否能抓住 unsupported peer superlative / peer claim without sidecar / social leak；
6. 是否会破坏 formal_first source boundary、4.4 display-only 隔离、引用可追溯；
7. 实现是否可分阶段、可测试，是否避免频繁完整跑 LLM 报告。

禁止事项：
- 不要修改任何代码、配置、测试、报告。
- 不要运行报告入口。
- 不要访问网络，不要启动 Chrome/CDP/Playwright。
- 不要提交。

可以读取：
- docs/agent_workflow/2026-07-02-peer-comparison-material-layer-design.md
- docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-claude-review-round1.md
- docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-design-delta.md
- scripts/utils/reporter/data_fetcher.py
- scripts/utils/reporter/constants.py
- scripts/utils/report_skills/data_skills.py
- scripts/utils/knowledge_synthesizer.py
- scripts/utils/synthesis_source_policy.py
- config/stocks.json
- relevant tests if needed

输出要求：
写审查报告到：
docs/agent_workflow/2026-07-02-peer-comparison-material-layer-claude-review-notes.md

报告格式：
- verdict: ok / needs_revision / blocked
- blocker: 数量 + 列表
- must_fix: 数量 + 列表
- nice_to_have: 数量 + 列表
- 是否建议 Codex 进入实现
- 若不建议，列出进入实现前必须改的设计点
- 特别说明是否应拆成 3a/3b/3c，或者进一步收窄
- git status 是否变化

请不要泛泛而谈；每条 blocker/must-fix 都要引用具体设计段落或现有代码风险。
```

