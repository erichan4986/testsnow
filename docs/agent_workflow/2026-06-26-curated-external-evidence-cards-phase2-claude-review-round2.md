# Claude Review Round 2 Prompt — Curated External Evidence Cards Phase 2

请把下面 prompt 交给 Claude Code，在 `/Users/erichan/testsnow` 仓库中执行第二轮设计审查。

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库中做 Level 3 Round 2 设计审查，不要修改源码。

目标：
复审 docs/agent_workflow/2026-06-26-curated-external-evidence-cards-phase2-design.md。
重点检查 Round 1 的 blocker / must-fix 是否已被设计层面解决，并判断是否可以进入 implementation task。

Round 1 关键反馈：
- 不应直接复用 `ctx["synthesis_display"]`，因为 ExecutiveSummaryRenderer / HtmlDashboardRenderer 也读它。
- 应改为更窄的 `deep_analysis_display`，只让 DeepAnalysisRenderer 消费。
- 需要把 `report_skills/__init__.py` 和 `stock_reporter.py` 纳入允许修改范围，用于配置连线。
- `capital_market_context` 需要 substance filter。
- citation metadata 必须保留 card_id / source_ref / source_excerpt_hash / topic。
- overclaim lint 必须 sentence-level 且 citation-aware。
- CI grep gates 要覆盖新 helper。
- card gate 要识别图片/PDF 占位正文，增加中文字符数/密度检查。

请重点检查：
1. Round 1 blocker 是否已解决：正常报告配置能否通过 `source_intake_configs.<stock>.curated_external_evidence_cards_synthesis_display` 启用该功能。
2. `deep_analysis_display` 是否足够隔离 curated external 材料，是否仍有进入 executive summary、HTML dashboard、risk、Knowledge、scoring 的路径。
3. Quality gates 是否明确且可测试：
   - excerpt >=300 chars
   - 中文字符 >=80
   - 中文字符占比 >=5%
   - product_roadmap 默认排除
   - capital_market_context 必须满足 substance terms
   - stock-level >=3 cards / >=1200 excerpt chars
4. citation metadata 方案是否完整：card_id/source_ref/source_excerpt_hash/source_block_hash/topic 是否能从 SynthesisItem.extra 传到 citations。
5. overclaim lint 是否可实现且不会误伤官方公告句子。
6. fallback 策略是否清楚：lint failure 时不设置 deep_analysis_display，baseline synthesis 保持不变。
7. 是否仍需要修改 KnowledgeSynthesizer prompt。如果需要，请标为 must-fix；如果不需要，请说明 metadata + deterministic lint 是否足够。
8. 允许修改范围是否刚好足够，是否仍遗漏文件。
9. 测试计划是否足够进入 implementation task。
10. 是否还需要 Round 3。

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
- 可以运行只读 grep / sed / pytest --collect-only 之类的本地检查。
- 可以把反馈追加到指定设计文件。

输出要求：
把反馈追加到 docs/agent_workflow/2026-06-26-curated-external-evidence-cards-phase2-design.md 的 `## Round 2 Feedback` 小节。

反馈格式：
- Status: Ready to implement / Must-fix before task / Blocked
- R3 Needed: Yes/No
- Findings: 按 severity 排序，标注 blocker / must-fix / nice-to-have
- Required design deltas, if any
- Missing tests
- Implementation task recommendations

停止条件：
- 如果仍会导致 LLM 编造事实、引用污染、评分/风险污染、Knowledge 污染，标为 Must-fix before task 或 Blocked。
- 如果必须修改 scoring_engine.py、risk_renderer.py、技术算法、外部采集逻辑或 KnowledgeSynthesizer prompt 才能成立，标为 Blocked 或 high-risk must-fix。
- 如果缺少关键文件或当前仓库状态与设计假设不符，请停止并说明。
```
