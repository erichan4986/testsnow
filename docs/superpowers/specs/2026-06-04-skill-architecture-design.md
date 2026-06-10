# Skill 架构设计

> 设计日期: 2026-06-04
> 目的: 将报告生成层从 monolithic `PerStockReporter` 重构为可扩展的 Skill 体系

---

## 1. 背景与目标

### 1.1 现状问题

`PerStockReporter` 当前 2500+ 行，职责混杂：
- 质量门筛选
- LLM 综合叙事
- 4 张 Plotly 图表生成
- Markdown + HTML Dashboard 组装
- 跨来源内容去重

新增功能（如估值对比图、多空论点图）只能在 `generate_stock_report()` 这个大函数里硬插代码，耦合严重。

### 1.2 目标

1. **单一职责**: 每个 Skill 只做一件事，可独立理解、测试、替换
2. **即插即用**: 新增报告模块只需新增一个 Skill，不改现有代码
3. **统一契约**: Skill 间通过 `SkillContext` 交换数据，接口稳定
4. **向后兼容**: 现有 `PerStockReporter` 接口不变，内部逐步迁移

---

## 2. 核心抽象

### 2.1 SkillContext

统一数据载体，贯穿整个 Pipeline。

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SkillContext:
    """Skill 间传递的上下文数据。"""
    input: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """先从 output 查，再从 input 查。"""
        return self.output.get(key, self.input.get(key, default))

    def set(self, key: str, value: Any) -> None:
        """写入 output。"""
        self.output[key] = value
```

**设计理由:**
- `input` / `output` 分离，避免 Skill 修改上游数据
- `get()` 回退到 `input`，减少 Skill 间显式数据搬运

### 2.2 BaseSkill

有状态 Skill 的基类，适用于需要外部依赖（LLM、Plotly、数据库连接）的 Skill。

```python
from abc import ABC, abstractmethod

class BaseSkill(ABC):
    """有状态 Skill 基类。"""

    name: str = ""

    def __init__(self, **kwargs):
        """子类可接收外部依赖（如 llm_client、logger）。"""
        for k, v in kwargs.items():
            setattr(self, k, v)

    @abstractmethod
    def run(self, ctx: SkillContext) -> SkillContext:
        raise NotImplementedError
```

### 2.3 @skill 装饰器

给函数式 Skill 注入通用能力：输入校验、异常捕获、耗时统计、日志记录。

```python
import functools
import time
import logging

logger = logging.getLogger(__name__)

def skill(name: str = None):
    """函数式 Skill 装饰器。"""
    def decorator(func):
        skill_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(ctx: SkillContext, *args, **kwargs):
            start = time.time()
            try:
                result = func(ctx, *args, **kwargs)
                if result is None:
                    result = ctx
                elapsed = time.time() - start
                logger.info(f"[{skill_name}] 完成，耗时 {elapsed:.2f}s")
                result.metadata.setdefault("_skill_times", {})[skill_name] = elapsed
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[{skill_name}] 失败: {e} (耗时 {elapsed:.2f}s)")
                raise
        wrapper._skill_name = skill_name
        return wrapper
    return decorator
```

**设计理由:**
- 简单 Skill 不需要写类，用函数 + 装饰器即可
- 装饰器统一处理横切关注点（日志、计时、异常），Skill 逻辑保持纯粹

---

## 3. Pipeline 编排器

### 3.1 SkillPipeline

```python
from typing import List, Union, Callable

SkillLike = Union[BaseSkill, Callable[[SkillContext], SkillContext]]

class SkillPipeline:
    """按顺序执行 Skill 列表，支持错误回退。"""

    def __init__(self, skills: List[SkillLike] = None):
        self.skills = skills or []

    def add(self, skill: SkillLike) -> "SkillPipeline":
        self.skills.append(skill)
        return self

    def run(self, initial_input: dict = None) -> SkillContext:
        ctx = SkillContext(input=initial_input or {})
        for s in self.skills:
            ctx = self._run_single(s, ctx)
        return ctx

    def _run_single(self, skill: SkillLike, ctx: SkillContext) -> SkillContext:
        if isinstance(skill, BaseSkill):
            return skill.run(ctx)
        elif callable(skill):
            return skill(ctx)
        else:
            raise TypeError(f"Unsupported skill type: {type(skill)}")
```

**错误回退策略:**
- 默认：任何 Skill 失败立即终止 Pipeline
- 可选：`SkillPipeline(continue_on_error=True)` — 失败 Skill 跳过，继续执行后续

---

## 4. 报告生成层 Skill 清单

### 4.1 函数式 Skill

#### DataLoadingSkill
```python
@skill(name="data_loading")
def data_loading_skill(ctx: SkillContext) -> SkillContext:
    """从 stocks_data / raw_data 加载单只股票的数据。"""
    stock_name = ctx.get("stock_name")
    stocks_data = ctx.get("stocks_data", {})
    raw_data = ctx.get("raw_data", {})

    all_posts = stocks_data.get(stock_name, [])
    stock_raw = raw_data.get(stock_name, {})

    ctx.set("all_posts", all_posts)
    ctx.set("stock_raw", stock_raw)
    return ctx
```

#### QualityGateSkill
```python
@skill(name="quality_gate")
def quality_gate_skill(ctx: SkillContext) -> SkillContext:
    """统一质量门筛选。"""
    all_posts = ctx.get("all_posts", [])
    from utils.content_quality_gate import ContentQualityGate
    gate = ContentQualityGate()
    results = gate.process_xueqiu_posts(all_posts)

    keep = [r.item.extra for r in results if r.action == "keep"]
    demote = [r.item.extra for r in results if r.action == "demote"]
    discard = [r.item.extra for r in results if r.action == "discard"]

    ctx.set("keep_posts", keep)
    ctx.set("demote_posts", demote)
    ctx.set("discard_posts", discard)
    return ctx
```

#### CrossSourceConsolidationSkill
```python
@skill(name="cross_source_consolidation")
def cross_source_consolidation_skill(ctx: SkillContext) -> SkillContext:
    """雪球 + 知乎 跨来源内容去重。"""
    keep_posts = ctx.get("keep_posts", [])
    stock_raw = ctx.get("stock_raw", {})
    zhihu_items = stock_raw.get("zhihu", {}).get("report_items", [])

    from utils.content_consolidator import ContentConsolidator
    consolidator = ContentConsolidator()
    consolidated = consolidator.consolidate(keep_posts + zhihu_items)
    summary = consolidator.generate_cross_source_summary(consolidated) or ""

    ctx.set("consolidated", consolidated)
    ctx.set("cross_source_summary", summary)
    return ctx
```

#### ScoringSkill
```python
@skill(name="scoring")
def scoring_skill(ctx: SkillContext) -> SkillContext:
    """五维评分 + 雷达图数据。"""
    stock_raw = ctx.get("stock_raw", {})
    keep_posts = ctx.get("keep_posts", [])
    quote = ctx.get("quote")
    consensus = ctx.get("consensus")
    ind_fwd_pe = ctx.get("ind_fwd_pe")
    ps = ctx.get("ps")

    from utils.reporter.scoring_engine import compute_pillar_scores
    pillar = compute_pillar_scores(stock_raw, keep_posts, quote, consensus, ind_fwd_pe, ps)
    total_score = round(
        pillar["valuation"] * 0.30 +
        pillar["technical"] * 0.25 +
        pillar["sentiment"] * 0.20 +
        pillar["fundamental"] * 0.15 +
        pillar["fundflow"] * 0.10,
        1,
    )
    ctx.set("pillar_scores", pillar)
    ctx.set("total_score", total_score)
    return ctx
```

### 4.2 类式 Skill

#### TechnicalAnalysisSkill
```python
class TechnicalAnalysisSkill(BaseSkill):
    name = "technical_analysis"

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_raw = ctx.get("stock_raw", {})
        stock_name = ctx.get("stock_name")
        date_str = ctx.get("date_str")
        output_dir = ctx.get("output_dir")

        daily_data = stock_raw.get("technical", {}).get("daily_data", {})
        indicators = stock_raw.get("technical", {}).get("indicators", {})
        patterns = indicators.get("_patterns", [])

        if not daily_data or not indicators:
            return ctx

        from utils.reporter.chart_generator import generate_technical_panel
        chart_dir = Path(output_dir) / "charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        path = chart_dir / f"{stock_name}_technical_{date_str}.png"

        generate_technical_panel(
            stock_name=stock_name,
            daily_data=daily_data,
            patterns=patterns,
            indicators=indicators,
            output_path=str(path),
        )
        ctx.set("chart_technical", str(path))
        return ctx
```

#### SynthesisSkill
```python
class SynthesisSkill(BaseSkill):
    name = "synthesis"

    def __init__(self, llm_client=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_client = llm_client

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        # ... LLM 调用逻辑
        synthesis = self._synthesize(stock_name, stock_raw)
        ctx.set("synthesis", synthesis)
        return ctx
```

#### ChartGenerationSkill
```python
class ChartGenerationSkill(BaseSkill):
    name = "chart_generation"

    def run(self, ctx: SkillContext) -> SkillContext:
        """生成多空论点图、雷达图、估值对比图。"""
        stock_name = ctx.get("stock_name")
        synthesis = ctx.get("synthesis", {})
        pillar = ctx.get("pillar_scores", {})
        total_score = ctx.get("total_score", 0)
        output_dir = ctx.get("output_dir")
        date_str = ctx.get("date_str")

        chart_dir = Path(output_dir) / "charts"
        chart_dir.mkdir(parents=True, exist_ok=True)

        # 1. 多空论点图
        debate = synthesis.get("valuation_debate", "")
        fund = synthesis.get("fundamentals", "")
        bull, bear = self._extract_thesis_points(debate + "\n" + fund)
        if bull or bear:
            path = chart_dir / f"{stock_name}_bullbear_{date_str}.png"
            from utils.reporter.chart_generator import generate_bull_bear_chart
            generate_bull_bear_chart(stock_name, bull, bear, str(path))
            ctx.set("chart_bullbear", str(path))

        # 2. 雷达图
        if pillar:
            path = chart_dir / f"{stock_name}_radar_{date_str}.png"
            from utils.reporter.chart_generator import generate_radar_chart
            generate_radar_chart(stock_name, pillar, total_score, str(path))
            ctx.set("chart_radar", str(path))

        # 3. 估值对比图
        comp_metrics = ctx.get("competitor_metrics", {})
        if comp_metrics:
            path = chart_dir / f"{stock_name}_valuation_{date_str}.png"
            from utils.reporter.chart_generator import generate_valuation_comparison
            generate_valuation_comparison(stock_name, comp_metrics, str(path))
            ctx.set("chart_valuation", str(path))

        return ctx
```

#### ReportAssemblySkill
```python
class ReportAssemblySkill(BaseSkill):
    name = "report_assembly"

    def run(self, ctx: SkillContext) -> SkillContext:
        """组装 Markdown + HTML Dashboard。"""
        stock_name = ctx.get("stock_name")
        output_dir = ctx.get("output_dir")
        # ... 从 ctx 取各板块内容
        md_content = self._assemble_markdown(ctx)
        html_content = self._assemble_html(ctx)

        md_path = Path(output_dir) / f"{stock_name}_{ctx.get('date_str')}.md"
        html_path = Path(output_dir) / f"{stock_name}_{ctx.get('date_str')}.html"

        md_path.write_text(md_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        ctx.set("md_path", str(md_path))
        ctx.set("html_path", str(html_path))
        return ctx
```

---

## 5. Pipeline 组装示例

### 5.1 单股报告 Pipeline

```python
from utils.skill_pipeline import SkillPipeline, SkillContext
from utils.report_skills import (
    data_loading_skill,
    quality_gate_skill,
    cross_source_consolidation_skill,
    scoring_skill,
    TechnicalAnalysisSkill,
    SynthesisSkill,
    ChartGenerationSkill,
    ReportAssemblySkill,
)

def build_stock_report_pipeline(llm_client=None) -> SkillPipeline:
    return SkillPipeline([
        data_loading_skill,
        quality_gate_skill,
        cross_source_consolidation_skill,
        TechnicalAnalysisSkill(),
        SynthesisSkill(llm_client=llm_client),
        scoring_skill,
        ChartGenerationSkill(),
        ReportAssemblySkill(),
    ])

# 使用
pipeline = build_stock_report_pipeline(llm_client=kimi_client)
ctx = pipeline.run({
    "stock_name": "圣邦股份",
    "date_str": "20260604",
    "output_dir": "/path/to/reports",
    "stocks_data": {...},
    "raw_data": {...},
    "stock_codes": {"圣邦股份": "300661"},
})

md_path = ctx.output["md_path"]
html_path = ctx.output["html_path"]
```

### 5.2 向后兼容：PerStockReporter 内部迁移

```python
class PerStockReporter:
    def generate_stock_report(self, stock_name, output_dir):
        # 旧接口不变，内部用 Pipeline 替代
        pipeline = build_stock_report_pipeline()
        ctx = pipeline.run({
            "stock_name": stock_name,
            "date_str": self.date_str,
            "output_dir": output_dir,
            "stocks_data": self.stocks_data,
            "raw_data": self.raw_data,
            "stock_codes": self.stock_codes,
        })
        return ctx.output.get("md_path", ""), ctx.output.get("html_path", "")
```

---

## 6. 数据流图

```
┌──────────────────────────────────────────────────────────────────────────┐
│  initial_input                                                           │
│  ├── stock_name          ──▶ DataLoadingSkill ──▶ all_posts / stock_raw │
│  ├── stocks_data                                                         │
│  ├── raw_data                                                            │
│  └── stock_codes                                                         │
│                                                                          │
│  all_posts ──▶ QualityGateSkill ──▶ keep_posts / demote_posts            │
│                                                                          │
│  keep_posts + zhihu_items ──▶ CrossSourceConsolidationSkill              │
│                               ──▶ consolidated / cross_source_summary    │
│                                                                          │
│  stock_raw ──▶ TechnicalAnalysisSkill ──▶ chart_technical                │
│                                                                          │
│  stock_raw + keep_posts ──▶ SynthesisSkill ──▶ synthesis                 │
│                                                                          │
│  stock_raw + keep_posts + quote ──▶ ScoringSkill ──▶ pillar / total_score│
│                                                                          │
│  synthesis + pillar ──▶ ChartGenerationSkill ──▶ chart_bullbear / radar  │
│                                                                          │
│  all_above ──▶ ReportAssemblySkill ──▶ md_path / html_path               │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 错误处理策略

| 场景 | 策略 |
|------|------|
| 图表生成失败（如 Kaleido 未装） | 捕获异常，跳过该图表，报告继续生成 |
| LLM 综合叙事失败 | 降级为模板化摘要，不阻断 Pipeline |
| 质量门失败 | 核心功能，失败则终止 Pipeline |
| 数据加载失败 | 终止 Pipeline，返回空结果 |

实现方式：在类式 Skill 的 `run()` 内部 try/except，或给 Pipeline 配置 `continue_on_error=True` + 单个 Skill 标记 `critical=True`。

---

## 8. 测试策略

1. **单元测试**: 每个 Skill 独立测试，mock 外部依赖（LLM、Plotly）
2. **集成测试**: 完整 Pipeline 端到端，验证输入 → 输出路径
3. **兼容性测试**: `PerStockReporter.generate_stock_report()` 接口返回值不变

---

## 9. 后续扩展

- **数据采集层 Skill 化**: 需要时将 `TechnicalCollector`、`ZhihuCollector` 等包装成 Skill，统一接入 Pipeline
- **条件分支**: Pipeline 支持 `IfSkill`、`SwitchSkill`，如港股跳过技术面 Skill
- **并行执行**: 无依赖的 Skill（如 TechnicalAnalysisSkill vs SynthesisSkill）可并行执行
- **缓存层**: Skill 结果按 `metadata["cache_key"]` 缓存，避免重复计算
