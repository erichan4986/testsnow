# Claude Review Round 1 Prompt — Curated External Evidence Cards Phase 2

请把下面 prompt 交给 Claude Code，在 `/Users/erichan/testsnow` 仓库中执行设计审查。

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库中做 Level 3 设计审查，不要修改源码。

目标：
审查 docs/agent_workflow/2026-06-26-curated-external-evidence-cards-phase2-design.md。
判断该设计是否能安全地让 enriched curated external evidence cards 进入报告的 display-only 深度分析路径，同时不污染核心事实、Knowledge、评分、风险或最终建议。

背景：
- Phase 1 已实现 curated external evidence cards preview。
- Phase 1.5 正文增强 smoke 显示 enriched cards 信息密度显著提升。
- 但材料仍来自微信 / 产业媒体等中低信用来源，只能作为 professional_observation。
- 现在要评估 Phase 2：让 enriched evidence cards 影响 `## 四、深度分析`，但保持 display-only。

重点检查：
1. 是否应该复用现有 `ctx["synthesis_display"]`，还是必须新增更窄的 `deep_analysis_display`，只影响 DeepAnalysisRenderer。
2. 输入门槛是否足够防止短摘要 card 或产品噪音进入 synthesis。
3. stock-level gate（至少 3 张卡、至少 1200 excerpt chars）是否合理。
4. topic whitelist 是否合理，尤其是是否应允许 `capital_market_context`。
5. 是否存在 display-only 材料进入 `ctx["synthesis"]`、`ctx["synthesis_text"]`、`ctx["core_facts"]`、Knowledge writer、scoring 或 risk 的泄漏路径。
6. 现有 `SynthesisSkill.run()` 的 display synthesis 结构能否安全容纳第四类 display extra（fulltext / narrative cards / broker digest / curated external）。
7. citation resolvability 方案是否足够：每个 `[^n]` 是否能追溯到 card_id/source_ref/source_excerpt_hash。
8. overclaim lint 是否可实现、是否过宽或过窄；是否应 reject whole display synthesis。
9. 是否需要修改 `KnowledgeSynthesizer` prompt。如果需要，请标为高风险 must-fix，并说明为什么不能仅靠 metadata + lint。
10. 测试计划是否覆盖：薄材料回退、圣邦 baseline、 中际旭创增强、引用缺失、overclaim、display-only 不进 scoring/risk/Knowledge。
11. 是否需要更新 `tools/ci_grep_gates.sh`，禁止 curated external evidence cards 进入 scoring/risk/final recommendation 路径。
12. 实现允许文件范围是否过宽或过窄。

禁止事项：
- 不要修改源码。
- 不要运行 LLM。
- 不要访问外部网络。
- 不要生成报告。
- 不要写 knowledge/、reports/、data/raw/。
- 不要启动 Chrome/CDP/Playwright。
- 不要抓雪球详情页。
- 不要打印 .env 或任何 API key。

允许：
- 只读检查相关代码与测试。
- 可以运行只读 grep / sed / pytest --collect-only 之类的本地检查，但不要写仓库文件，除非写 review feedback 到指定 design 文件。

输出要求：
把反馈追加到 docs/agent_workflow/2026-06-26-curated-external-evidence-cards-phase2-design.md 的 `## Round 1 Feedback` 小节。

反馈格式：
- Status: Ready to implement / Must-fix before task / Blocked
- R2 Needed: Yes/No
- Findings: 按 severity 排序，标注 blocker / must-fix / nice-to-have
- Required design deltas
- Missing tests
- Open questions
- Suggested implementation boundary

停止条件：
- 如果你认为设计会导致 LLM 编造事实、引用污染、评分/风险污染、或 Knowledge 污染，请标为 Must-fix before task 或 Blocked。
- 如果你认为必须修改 scoring_engine.py、risk_renderer.py、技术算法、外部采集逻辑或 KnowledgeSynthesizer prompt 才能成立，请标为 Blocked 或 high-risk must-fix。
- 如果缺少关键文件或当前仓库状态与设计假设不符，请停止并说明。
```
