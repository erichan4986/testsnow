# 复旦微电 Trial Pipeline Quality Fix v2 — Claude Review Round 1 Prompt

把下面这段交给 Claude Code：

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库做一次只读设计审查。不要修改任何代码、配置、测试或报告。

目标：
审查 docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md。

背景：
复旦微电正式 trial 报告已经生成，但人工扫读发现：
1. MLCC 泛行业材料污染 4.1/4.2，且报告自己承认复旦微电不直接涉及 MLCC。
2. 核心事实基座把 2025 年营业收入/净利润等亿元级数据写成万元。
3. 4.3 资金面与催化剂章节缺失，但质量门没拦住。
4. 4.2 没消费前文已有财务快照，反复说外部材料未提供营收/利润数据。
5. Header 的所属赛道/可比公司没有读取 config。

请只读以下文件：
- docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md
- reports/复旦微电_20260702.md
- config/stocks.json
- scripts/utils/knowledge_synthesizer.py
- scripts/utils/industry_news_relevance.py
- scripts/utils/report_skills/synthesis_skills.py
- scripts/utils/periodic_report_structured_facts.py
- scripts/utils/reporter/sections/deep_analysis_renderer.py
- scripts/utils/report_quality.py
- scripts/utils/reporter/sections/valuation_renderer.py（仅用于确认 header/估值相关上下文，如无关可略读）
- tests/reporter/test_report_quality.py
- tests/utils/test_knowledge_synthesizer.py

重点审查：
1. Direct-Only Canonical 规则是否能真正阻止 MLCC 这类无直接关系材料进入 4.1/4.2。
2. 设计是否过度收紧，可能误杀中际旭创/圣邦股份这类已有正式行业研报。
3. product_exposure_terms 的位置和维护方式是否合理：放 stock_config 还是 derive from keywords，如何避免把“半导体/AI/汽车电子/国产替代”当直接产品。
4. formal_financial_fact_pack 是否应该新建，还是复用现有 periodic_report_filing_core_facts / financial_abstract。
5. 核心事实单位错误的 root cause 是否判断准确，是否还要看 upstream extractor。
6. 4.3 缺失的修复放在 renderer fallback 还是 quality gate，哪边是主修。
7. 新增 quality gates 是否会误报，尤其是 product-industry mismatch 和 financial unit sanity。
8. 实施切分 Batch A-E 是否合理，是否应调整顺序。

输出要求：
请写审查报告到：
docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-notes.md

报告格式：

verdict: ok | needs_revision | blocked

summary:
  one_line: ...

blockers:
  - id: B1
    title: ...
    evidence:
      - file:line
    required_change: ...

must_fix:
  - id: MF1
    title: ...
    evidence:
      - file:line
    required_change: ...

nice_to_have:
  - id: N1
    title: ...
    rationale: ...

risk_assessment:
  direct_only_filter_false_positive_risk: low|medium|high
  financial_fact_pack_complexity: low|medium|high
  quality_gate_false_positive_risk: low|medium|high

implementation_recommendation:
  proceed_to_implementation: yes|no
  suggested_batch_order:
    - ...

git_status:
  before: ...
  after: ...

禁止事项：
- 不要修改任何 repo 文件（除了写上述 review notes）。
- 不要运行正式报告入口。
- 不要调用 LLM。
- 不要访问外部网站。
- 不要启动 Chrome/CDP/Playwright。

停止条件：
- 如果设计缺少足够上下文，写 blocked 并列出缺失文件/信息。
- 如果你发现 Direct-Only 会破坏 formal_first 或 4.4 display-only 边界，标 blocker。
```

