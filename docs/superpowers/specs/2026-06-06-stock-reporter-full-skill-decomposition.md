# Stock Reporter 完全 Skill 化解耦设计

## 目标

将 `scripts/utils/stock_reporter.py` 从 **2655 行** 压缩到 **< 300 行**，所有报告板块拆分为独立的 `SectionRenderer`，由 `SkillPipeline` 统一编排。

## 现状

- `stock_reporter.py`: 2655 行，God Class (`PerStockReporter`)
- `generate_stock_report_legacy`: ~300 行，已废弃，从未被调用
- 已提取的 renderer: `TechnicalRenderer`、`PriceTargetRenderer`
- Pipeline 已存在: `build_stock_report_pipeline()` 包含 data → quality_gate → scoring → chart → assembly
- `ReportAssemblySkill` 仍通过 `reporter._xxx()` 调用旧方法，依赖 `PerStockReporter`

## 设计决策

### 确认移除/内联

| 原内容 | 处理方式 | 理由 |
|--------|----------|------|
| Header / Footer | 内联到 `ReportAssemblySkill` | 纯模板字符串，无业务逻辑，不值得拆文件 |
| FeaturedPosts | **从报告移除**，解读后存知识库 | 减少报告噪音，提升精品内容价值 |
| CommentHighlights | **从报告移除**，存知识库 | 与 FeaturedPosts 同类，同属帖子摘录 |
| `generate_stock_report_legacy` | **直接删除** | 已废弃，从未被调用 |

### 最终 Renderer 清单（8 个）

每个 renderer 实现 `render(ctx: Dict[str, Any]) -> str`，只读 `ctx`，不修改。

| # | Renderer | 包含原方法 | 估计行数 | 状态 |
|---|----------|-----------|----------|------|
| 1 | `ExecutiveSummaryRenderer` | `_executive_summary` + `_extract_thesis_points` + `_extract_conclusion` + 多空对比图 | ~100 | 新增 |
| 2 | `CompositeScoreRenderer` | `composite_score_section` + 雷达图 + 目标价区间 + EV | ~150 | 新增 |
| 3 | `ValuationRenderer` | `_valuation_forecast_compact` + `_quarterly_financials_table` + `competitor_metrics_table` + 估值对比图 | ~200 | 新增 |
| 4 | `TechnicalRenderer` | `_technical_analysis_section` | 150 | **已存在** |
| 5 | `PriceTargetRenderer` | `_price_target_section` | 110 | **已存在** |
| 6 | `DeepAnalysisRenderer` | `_core_facts_table` + `_deep_analysis` + `_citations_section` | ~220 | 新增 |
| 7 | `RiskRenderer` | `risk_score_section` + `_risks_and_watch` | ~120 | 新增 |
| 8 | `HTMLDashboardRenderer` | `_generate_html_dashboard` | ~300 | 新增 |

### 不拆的理由

- **CoreFacts/Citations** 并入 `DeepAnalysisRenderer`：核心事实是分析前提，来源汇总是分析注脚，同一业务上下文
- **CompositeScore** 与 **Valuation** 不合并：前者是"评分+推荐"，后者是"数据展示"，职责不同
- **ExecutiveSummary** 与 **DeepAnalysis** 不合并：前者是"电梯演讲"，后者是"展开论证"，层级不同

## 架构设计

### 1. PerStockReporter 职责（最终 < 300 行）

```python
class PerStockReporter:
    def __init__(self, stocks_data, stock_codes, raw_data):
        ...

    def generate_stock_report(self, stock_name, output_dir):
        """唯一入口：调用 Skill Pipeline"""
        pipeline = build_stock_report_pipeline()
        ctx = pipeline.run({...})
        return ctx.output.get("md_path"), ctx.output.get("html_path")

    def generate_all_reports(self, output_dir):
        for stock in self.stocks_data:
            self.generate_stock_report(stock, output_dir)
```

所有 `_xxx_section` 方法全部删除。

### 2. ReportAssemblySkill 重构

```python
class ReportAssemblySkill(BaseSkill):
    def _assemble_markdown(self, ctx) -> str:
        sections = []
        sections.append(self._header(ctx))          # 内联常量
        sections.append(ExecutiveSummaryRenderer().render(ctx))
        sections.append(CompositeScoreRenderer().render(ctx))
        sections.append(ValuationRenderer().render(ctx))
        tech = TechnicalRenderer().render(ctx)
        if tech:
            sections.append(tech)
        pt = PriceTargetRenderer().render(ctx)
        if pt:
            sections.append(pt)
        deep = DeepAnalysisRenderer().render(ctx)
        if deep:
            sections.append(deep)
        risk = RiskRenderer().render(ctx)
        if risk:
            sections.append(risk)
        sections.append(self._footer(ctx))          # 内联常量
        return "\n\n".join(filter(None, sections))

    def _header(self, ctx):
        return f"""# {stock_name} 舆情深度报告
**报告日期**: ..."""

    def _footer(self, ctx):
        return "---\n*本报告基于雪球网公开讨论数据...*"
```

**不再构造 `PerStockReporter` 实例。**

### 3. 删除项清单

- `generate_stock_report_legacy()` 及其中所有引用
- `PerStockReporter` 中所有 `_xxx_section` 方法（已外移到 renderer）
- `_featured_posts()`、`_get_featured_analyses()`、`_extract_argument_chain()` → 移至知识库模块
- `_comment_highlights()` → 移至知识库模块
- `_annotate_cross_sources()` → 移至 `cross_source_consolidation_skill`
- `_get_judgment_generator()`、`_get_llm_judgment()`、`_generic_judgment()` → 移至知识库/FeaturedPosts 模块

### 4. 知识库迁移（非本次重点，标记 TODO）

FeaturedPosts 和 CommentHighlights 的解读逻辑需要一个新的 "知识沉淀 Skill"，在 Pipeline 中于 `ReportAssemblySkill` 之前运行，将解读结果写入 `knowledge/` 目录。**本次设计只负责从报告中移除它们，不实现知识库 Skill。**

### 5. 数据流

所有 renderer 只读 `ctx`，不修改。`ctx` 中已有的关键键：

- `stock_name`, `date_str`, `output_dir`
- `all_posts`, `keep_posts`
- `stock_raw`, `quote`, `consensus`, `ind_fwd_pe`
- `pillar_scores`, `total_score`
- `synthesis`
- `chart_paths` / `chart_technical`, `chart_radar`, etc.

## 验证标准

- [ ] `stock_reporter.py` < 300 行
- [ ] 89 个现有测试全部通过
- [ ] 圣邦股份 / 黑芝麻智能 报告输出与重构前完全一致（除移除 FeaturedPosts/CommentHighlights）
- [ ] 新增 section 只需：写 renderer → 在 `ReportAssemblySkill` 中插入一行
