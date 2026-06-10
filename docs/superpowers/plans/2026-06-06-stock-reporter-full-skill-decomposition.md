# Stock Reporter 完全 Skill 化解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `stock_reporter.py` 从 2655 行压缩到 < 300 行，所有报告板块拆分为独立 `SectionRenderer`，`ReportAssemblySkill` 不再依赖 `PerStockReporter`。

**Architecture:** 保留 `PerStockReporter` 作为门面接口，内部只调用 `SkillPipeline`。8 个 `SectionRenderer` 各自负责一个报告板块，`ReportAssemblySkill` 按序组装。Header/Footer 内联为模板常量。FeaturedPosts/CommentHighlights 从报告移除。

**Tech Stack:** Python 3.11, pytest, SkillPipeline (自定义)

---

## File Structure

### 新建文件（6 个 Renderer）

| File | Responsibility | Lines |
|------|---------------|-------|
| `scripts/utils/reporter/sections/executive_summary_renderer.py` | 执行摘要 + 多空论点 + 一句话结论 + 多空对比图 | ~100 |
| `scripts/utils/reporter/sections/composite_score_renderer.py` | 综合评分 + 雷达图 + 目标价区间 + EV | ~150 |
| `scripts/utils/reporter/sections/valuation_renderer.py` | 估值快照 + 财务快照 + 竞争对手对比 + 估值对比图 | ~200 |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 核心事实 + 深度分析(3子板块) + 来源汇总 | ~220 |
| `scripts/utils/reporter/sections/risk_renderer.py` | 综合风险评分 + 关注要点 | ~120 |
| `scripts/utils/reporter/sections/html_dashboard_renderer.py` | HTML Dashboard | ~300 |

### 修改文件

| File | Change |
|------|--------|
| `scripts/utils/reporter/sections/__init__.py` | 导出所有 renderer + `required_keys` 辅助 |
| `scripts/utils/report_skills/assembly_skills.py` | 删除 `_reporter()`，内联 Header/Footer，直接调用 renderer，加 `required_keys` 校验和 `try/except` 容错 |
| `scripts/utils/stock_reporter.py` | 删除 `generate_stock_report_legacy` 及所有 `_xxx_section` 方法 |
| `tests/reporter/test_assembly_skills.py` | 更新测试，mock ctx 测试各 renderer 和 assembly 集成 |

---

## Task 1: 删除 `generate_stock_report_legacy`

**Files:**
- Modify: `scripts/utils/stock_reporter.py:134-388`

`generate_stock_report_legacy` 从第 134 行开始到第 388 行结束（`generate_stock_report` 之前）。这是约 255 行废弃代码，从未被调用。

- [ ] **Step 1: 删除 legacy 方法**

```python
# 删除 generate_stock_report_legacy 整段代码（134-388 行）
```

- [ ] **Step 2: 运行测试确认无引用**

Run: `grep -r "generate_stock_report_legacy" scripts/ tests/`
Expected: 无匹配（只有 `stock_reporter.py` 中的定义）

- [ ] **Step 3: 运行现有测试**

Run: `python -m pytest tests/ -q`
Expected: 89 passed（legacy 删除不影响 Pipeline 路径）

- [ ] **Step 4: Commit**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "refactor(reporter): remove generate_stock_report_legacy (unused, ~255 lines)"
```

---

## Task 2: 创建 `ExecutiveSummaryRenderer`

**Files:**
- Create: `scripts/utils/reporter/sections/executive_summary_renderer.py`
- Modify: `scripts/utils/reporter/sections/__init__.py`

提取 `_executive_summary` (~75 行) + `_extract_thesis_points` (~35 行) + `_extract_conclusion` (~10 行) + `_llm_extract_thesis` (~40 行)。

- [ ] **Step 1: 写入 `ExecutiveSummaryRenderer`**

```python
"""执行摘要板块渲染器。"""

from typing import Any, Dict, List


class ExecutiveSummaryRenderer:
    """执行摘要：综合评分标题 + 核心投资论点 + 一句话结论 + 多空对比图。"""

    def required_keys(self) -> List[str]:
        return ["stock_name", "synthesis"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        stock_raw = ctx.get("stock_raw", {})
        synthesis = ctx.get("synthesis", {})
        pillar = ctx.get("pillar_scores")
        consensus = ctx.get("consensus")

        try:
            from ..scoring_engine import ev_expectation
        except ImportError:
            from reporter.scoring_engine import ev_expectation

        ev = ev_expectation(pillar or {}, consensus)
        if pillar is not None:
            total_score = round(
                pillar["valuation"] * 0.30 +
                pillar["technical"] * 0.25 +
                pillar["sentiment"] * 0.20 +
                pillar["fundamental"] * 0.15 +
                pillar["fundflow"] * 0.10,
                1,
            )
            ev_pct = ev.get('ev_pct')
            ev_signal = ev.get('signal') or 'N/A'
            ev_pct_str = f"{ev_pct:+.2f}" if ev_pct is not None else "N/A"
            score_line = f"### 综合评分: {total_score}/10 | EV: {ev_pct_str}%（{ev_signal}）"
        else:
            score_line = "### 综合评分: 数据不足 | EV: N/A"

        lines = [
            "## 执行摘要",
            "",
            score_line,
            "",
            "### 核心投资论点",
            "",
        ]

        debate_text = synthesis.get("valuation_debate", "")
        fund_text = synthesis.get("fundamentals", "")
        combined = debate_text + "\n" + fund_text

        bullish_points = self._extract_thesis_points(combined, "bullish")
        bearish_points = self._extract_thesis_points(combined, "bearish")

        if bullish_points:
            lines.append("**看多：**")
            for pt in bullish_points[:4]:
                star = "⭐" * pt.get("stars", 3)
                lines.append(f"- {pt.get('text', '')} → {star}")
            lines.append("")

        if bearish_points:
            lines.append("**看空：**")
            for pt in bearish_points[:4]:
                star = "⭐" * pt.get("stars", 3)
                lines.append(f"- {pt.get('text', '')} → {star}")
            lines.append("")

        conclusion = self._extract_conclusion(stock_name, combined)
        if conclusion:
            lines.append(f"> **一句话结论**：{conclusion}")
            lines.append("")

        bullbear_chart = ctx.get("chart_paths", {}).get("bullbear") or ctx.get("chart_bullbear")
        if bullbear_chart:
            lines.append("### 多空论点对比")
            lines.append("")
            lines.append(f"![{stock_name} 多空论点对比]({bullbear_chart})")
            lines.append("")

        return "\n".join(lines)

    def _extract_thesis_points(self, text: str, direction: str) -> List[Dict]:
        """从合成文本中提取看多/看空论点。"""
        points = []
        if not text:
            return points

        try:
            llm_result = self._llm_extract_thesis(text)
            if direction == "bullish":
                return llm_result.get("bullish", [])
            else:
                return llm_result.get("bearish", [])
        except Exception:
            pass

        if direction == "bullish":
            keywords = ["增长", "放量", "突破", "拐点", "优势", "机遇", "看好", "上调", "超预期", "确定性"]
            for sentence in text.split("。"):
                if any(k in sentence for k in keywords) and len(sentence) > 20:
                    points.append({"text": sentence.strip() + "。", "stars": 3})
                if len(points) >= 4:
                    break
        else:
            keywords = ["下滑", "萎缩", "压力", "风险", "高估", "减持", "亏损", "谨慎", "下调", "放缓"]
            for sentence in text.split("。"):
                if any(k in sentence for k in keywords) and len(sentence) > 20:
                    points.append({"text": sentence.strip() + "。", "stars": 3})
                if len(points) >= 4:
                    break
        return points

    def _extract_conclusion(self, stock_name: str, text: str) -> str:
        """提取一句话结论。"""
        if not text:
            return ""

        try:
            llm_result = self._llm_extract_thesis(text)
            conclusion = llm_result.get("conclusion", "")
            if conclusion:
                return conclusion
        except Exception:
            pass

        keywords = ["均衡", "多空博弈", "分歧", "观望", "谨慎", "乐观", "悲观", "看好", "看空"]
        for sentence in text.split("。"):
            if any(k in sentence for k in keywords) and len(sentence) > 15:
                return sentence.strip() + "。"
        return ""

    def _llm_extract_thesis(self, text: str) -> Dict:
        """LLM 提取多空论点。"""
        import logging
        logger = logging.getLogger(__name__)

        if not text or len(text) < 50:
            return {"bullish": [], "bearish": [], "conclusion": ""}

        prompt = f"""从以下投资分析文本中提取：
1. 看多论点（最多4条，每条标注重要性1-5星）
2. 看空论点（最多4条，每条标注重要性1-5星）
3. 一句话结论

文本：
{text[:2000]}

请用JSON格式返回：{{"bullish": [{{"text": "...", "stars": 3}}], "bearish": [...], "conclusion": "..."}}"""

        try:
            import os
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com/v1")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            import json
            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
            return result
        except Exception as e:
            logger.warning(f"LLM 论点提取失败: {e}")
            return {"bullish": [], "bearish": [], "conclusion": ""}
```

- [ ] **Step 2: 更新 `__init__.py` 导出**

```python
"""Report section renderers — each renders one report section from SkillContext."""

from typing import Any, Dict, Protocol


class SectionRenderer(Protocol):
    """协议：每个 section renderer 实现 render(ctx) -> str。"""

    def render(self, ctx: Dict[str, Any]) -> str:
        ...

    def required_keys(self) -> list:
        ...


def _chart_paths(ctx: Dict[str, Any]) -> Dict[str, str]:
    """从 context 或 reporter 中提取图表路径。"""
    return ctx.get("chart_paths", ctx.get("_chart_paths", {}))


from .technical_renderer import TechnicalRenderer
from .price_target_renderer import PriceTargetRenderer
from .executive_summary_renderer import ExecutiveSummaryRenderer
from .composite_score_renderer import CompositeScoreRenderer
from .valuation_renderer import ValuationRenderer
from .deep_analysis_renderer import DeepAnalysisRenderer
from .risk_renderer import RiskRenderer
from .html_dashboard_renderer import HTMLDashboardRenderer

__all__ = [
    "SectionRenderer",
    "TechnicalRenderer",
    "PriceTargetRenderer",
    "ExecutiveSummaryRenderer",
    "CompositeScoreRenderer",
    "ValuationRenderer",
    "DeepAnalysisRenderer",
    "RiskRenderer",
    "HTMLDashboardRenderer",
    "_chart_paths",
]
```

- [ ] **Step 3: 写测试**

Create: `tests/reporter/test_executive_summary_renderer.py`

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.reporter.sections.executive_summary_renderer import ExecutiveSummaryRenderer


def test_executive_summary_with_pillar():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "测试股",
        "synthesis": {
            "valuation_debate": "看好未来增长。",
            "fundamentals": "营收增长15%。",
        },
        "pillar_scores": {
            "valuation": 7.0,
            "technical": 6.0,
            "sentiment": 5.0,
            "fundamental": 6.0,
            "fundflow": 5.0,
        },
        "consensus": {},
    }
    result = renderer.render(ctx)
    assert "## 执行摘要" in result
    assert "综合评分: 6.2/10" in result
    assert "**看多：**" in result


def test_executive_summary_without_pillar():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "测试股",
        "synthesis": {},
    }
    result = renderer.render(ctx)
    assert "数据不足" in result
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/reporter/test_executive_summary_renderer.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/reporter/sections/executive_summary_renderer.py \
        scripts/utils/reporter/sections/__init__.py \
        tests/reporter/test_executive_summary_renderer.py
git commit -m "feat(reporter): add ExecutiveSummaryRenderer"
```

---

## Task 3: 创建 `CompositeScoreRenderer`

**Files:**
- Create: `scripts/utils/reporter/sections/composite_score_renderer.py`

提取 `composite_score_section` 的全部逻辑（在 `scoring_engine.py` 中约 120 行）。该函数已有 `pillar` 可选参数，可直接复用核心逻辑。

- [ ] **Step 1: 写入 `CompositeScoreRenderer`**

```python
"""综合评分板块渲染器。"""

from typing import Any, Dict, Optional


class CompositeScoreRenderer:
    """一、综合评分与推荐：五维评分 + 雷达图 + 目标价区间 + EV。"""

    def required_keys(self) -> list:
        return ["stock_name"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        posts = ctx.get("all_posts", [])
        stock_raw = ctx.get("stock_raw", {})
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("ind_fwd_pe")
        pillar = ctx.get("pillar_scores")
        chart_paths = ctx.get("chart_paths", {})

        try:
            from ..scoring_engine import composite_score_section
        except ImportError:
            from reporter.scoring_engine import composite_score_section

        section = composite_score_section(stock_name, posts, stock_raw, quote, consensus, ind_fwd_pe, pillar)
        if section.startswith("\n## 一、"):
            pass
        elif section.startswith("##"):
            section = "\n" + section
        else:
            section = "\n## 一、综合评分与推荐\n\n" + section

        radar_chart = chart_paths.get("radar") or ctx.get("chart_radar")
        if radar_chart:
            section += f"\n\n### 五维评分雷达图\n\n![{stock_name} 五维评分雷达图]({radar_chart})\n"

        return section
```

- [ ] **Step 2: 运行测试**

Run: `python -m pytest tests/reporter/test_analysis_skills.py -v`
Expected: 测试通过（composite_score_section 未被破坏）

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/reporter/sections/composite_score_renderer.py
git commit -m "feat(reporter): add CompositeScoreRenderer"
```

---

## Task 4: 创建 `ValuationRenderer`

**Files:**
- Create: `scripts/utils/reporter/sections/valuation_renderer.py`

提取 `_valuation_forecast_compact` (~80 行) + `_quarterly_financials_table` (~70 行)，并复用 `competitor_metrics_table` + 估值对比图嵌入。

- [ ] **Step 1: 写入 `ValuationRenderer`**

```python
"""估值与财务快照板块渲染器。"""

from typing import Any, Dict


class ValuationRenderer:
    """二、估值与财务快照：实时估值 + Forward 估值 + 财务快照 + 竞争对手对比。"""

    def required_keys(self) -> list:
        return ["stock_name"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        stock_codes = ctx.get("stock_codes", {})
        chart_paths = ctx.get("chart_paths", {})
        date_str = ctx.get("date_str", "")

        lines = []

        # 估值快照
        val_section = self._valuation_forecast_compact(stock_name, quote, consensus, date_str)
        if val_section:
            lines.append(val_section)

        # 财务快照
        fin_section = self._quarterly_financials_table(stock_name)
        if fin_section:
            lines.append(fin_section)

        # 竞争对手
        try:
            from ..data_fetcher import fetch_competitor_metrics, competitor_metrics_table
        except ImportError:
            from reporter.data_fetcher import fetch_competitor_metrics, competitor_metrics_table

        comp_metrics = fetch_competitor_metrics(stock_name, stock_codes)
        if comp_metrics:
            comp_table = competitor_metrics_table(stock_name, comp_metrics)
            val_chart = chart_paths.get("valuation") or ctx.get("chart_valuation")
            if val_chart:
                comp_table += f"\n\n### 同业估值对比\n\n![{stock_name} 估值对比]({val_chart})\n"
            lines.append(comp_table)

        if not lines:
            return ""
        return "\n\n".join(lines)

    def _valuation_forecast_compact(self, stock_name: str, quote, consensus, date_str: str) -> str:
        """估值与财务快照（精简版）。"""
        if not quote:
            return ""

        lines = [
            "## 二、估值与财务快照",
            "",
            f"**数据日期**: {date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日 | **数据来源**: 腾讯财经实时行情 + 同花顺机构一致预期",
            "",
            "### 实时估值指标",
            "",
            "| 指标 | 数值 | 说明 |",
            "|------|------|------|",
        ]

        price = quote.get("price", 0)
        market_cap = quote.get("market_cap", "")
        float_cap = quote.get("float_cap", "")
        pe_ttm = quote.get("pe_ttm", 0)
        pb = quote.get("pb", 0)

        lines.append(f"| 最新价 | {price} 元 | 较前日 {quote.get('change_pct', 'N/A')}% |")
        lines.append(f"| 总市值 | {market_cap} 亿 | 流通市值 {float_cap} 亿 |")
        lines.append(f"| PE(TTM) | {pe_ttm} | 滚动市盈率 |")
        lines.append(f"| PB | {pb} | 市净率 |")
        lines.append("")

        # Forward 估值
        if consensus and consensus.get("eps_current") and price:
            fwd_pe = price / consensus["eps_current"]
            eps_growth = None
            if consensus.get("eps_next") and consensus["eps_current"]:
                eps_growth = ((consensus["eps_next"] / consensus["eps_current"]) - 1) * 100
            peg = fwd_pe / eps_growth if eps_growth else None

            lines.append("### Forward 估值")
            lines.append("")
            lines.append("| 指标 | 数值 | 说明 |")
            lines.append("|------|------|------|")
            lines.append(f"| Forward PE | {fwd_pe:.1f} | 最新价 / 2026 预期 EPS |")
            if peg:
                lines.append(f"| PEG | {peg:.2f} | Forward PE / 盈利增速 |")
            lines.append("")

            pe_ttm_val = pe_ttm if isinstance(pe_ttm, (int, float)) else None
            if pe_ttm_val and pe_ttm_val > fwd_pe:
                lines.append(f"**一句话判断**: Forward PE ({fwd_pe:.1f}) 低于 PE-TTM ({pe_ttm_val:.1f})，业绩成长正在消化估值。")
            else:
                lines.append(f"**一句话判断**: Forward PE ({fwd_pe:.1f}) 与 PE-TTM 接近，估值处于合理区间。")
            lines.append("")
        else:
            lines.append("> 暂无法获取机构一致预期 EPS 数据。")
            lines.append("")

        return "\n".join(lines)

    def _quarterly_financials_table(self, stock_name: str) -> str:
        """最新财务快照（含同比）。"""
        try:
            from ..data_fetcher import fetch_latest_quarterly_financials
        except ImportError:
            from reporter.data_fetcher import fetch_latest_quarterly_financials

        fin = fetch_latest_quarterly_financials(stock_name)
        if not fin:
            return ""

        lines = [
            "### 最新财务快照",
            "",
            f"> 报告期: {fin.get('report_date', 'N/A')} ({fin.get('report_type', '')}) | 数据来源: 东方财富",
            "",
            "| 指标 | 最新值 | 同比变化 |",
            "|------|--------|----------|",
        ]

        for item in fin.get("items", []):
            name = item.get("name", "")
            value = item.get("value", "")
            yoy = item.get("yoy", "")
            lines.append(f"| {name} | {value} | {yoy} |")

        revenue_yoy = fin.get("revenue_yoy")
        profit_yoy = fin.get("profit_yoy")
        if revenue_yoy or profit_yoy:
            lines.append("")
            parts = []
            if revenue_yoy:
                parts.append(f"营收同比增长{revenue_yoy}")
            if profit_yoy:
                parts.append(f"净利润同比增长{profit_yoy}")
            lines.append(f"> **财务趋势**: {'，'.join(parts)}。")

        lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/utils/reporter/sections/valuation_renderer.py
git commit -m "feat(reporter): add ValuationRenderer"
```

---

## Task 5: 创建 `DeepAnalysisRenderer`

**Files:**
- Create: `scripts/utils/reporter/sections/deep_analysis_renderer.py`

提取 `_core_facts_table` (~30 行) + `_deep_analysis` (~100 行) + `_citations_section` (~20 行)。同时包含 `_render_synthesis_section`。

- [ ] **Step 1: 写入 `DeepAnalysisRenderer`**

```python
"""深度分析板块渲染器。"""

from typing import Any, Dict, List


class DeepAnalysisRenderer:
    """四、深度分析：核心事实 + 产业逻辑 + 业绩路径 + 资金面 + 来源汇总。"""

    def required_keys(self) -> list:
        return ["stock_name", "synthesis"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        synthesis = ctx.get("synthesis", {})

        has_synthesis = any(
            synthesis.get(k) for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]
        )
        if not has_synthesis:
            return ""

        lines = []

        # 核心事实基座
        core_facts = synthesis.get("core_facts", [])
        if core_facts:
            lines.append(self._core_facts_table(core_facts))

        # 深度分析三大子板块
        deep = self._deep_analysis_sections(stock_name, synthesis)
        if deep:
            lines.append(deep)

        # 来源汇总
        citations = synthesis.get("citations", {})
        if citations:
            lines.append(self._citations_section("信息来源汇总", citations))

        if not lines:
            return ""
        return "\n\n".join(lines)

    def _core_facts_table(self, core_facts: List[Dict]) -> str:
        """核心事实基座表格。"""
        lines = [
            "### 核心事实基座",
            "",
            "| 事实 | 来源 | 置信度 |",
            "|------|------|--------|",
        ]
        for fact in core_facts:
            text = fact.get("text", "")
            source = fact.get("source", "")
            confidence = fact.get("confidence", "")
            lines.append(f"| {text} | {source} | {confidence} |")
        lines.append("")
        return "\n".join(lines)

    def _deep_analysis_sections(self, stock_name: str, synthesis: Dict) -> str:
        """深度分析三个子板块。"""
        lines = ["## 四、深度分析", ""]

        subsections = [
            ("4.1 产业逻辑与竞争格局", "industry_logic"),
            ("4.2 业绩路径与多空分歧", "valuation_debate"),
            ("4.3 资金面与催化剂时间线", "funding_sentiment"),
        ]
        citations = synthesis.get("citations", {})

        for title, key in subsections:
            narrative = synthesis.get(key, "")
            if narrative:
                lines.append(self._render_synthesis_section(title, narrative, citations))
                lines.append("")

        events = synthesis.get("events_catalysts", "")
        if events:
            lines.append(self._render_synthesis_section("4.4 事件与催化剂", events, citations))
            lines.append("")

        return "\n".join(lines)

    def _render_synthesis_section(self, title: str, narrative: str, citations: Dict) -> str:
        """渲染一个合成叙事板块。"""
        import re
        used_refs = set(int(m) for m in re.findall(r"\[\^(\d+)\]", narrative))

        lines = [f"### {title}", "", narrative, ""]

        if used_refs:
            lines.append("**本节引用来源：**")
            for ref_id in sorted(used_refs):
                meta = citations.get(ref_id, {})
                source = meta.get("source", "未知")
                author = meta.get("author", "")
                title_text = meta.get("title", "")
                url = meta.get("url", "")
                date = meta.get("date", "")
                ref_line = f"- [{ref_id}] {source}"
                if author:
                    ref_line += f" | {author}"
                if title_text:
                    ref_line += f"《{title_text}》"
                if url:
                    ref_line += f" ({url})"
                if date:
                    ref_line += f" [{date}]"
                lines.append(ref_line)
            lines.append("")

        return "\n".join(lines)

    def _citations_section(self, title: str, citations: Dict) -> str:
        """信息来源汇总。"""
        lines = [f"## {title}", ""]
        for ref_id, meta in sorted(citations.items(), key=lambda x: x[0]):
            source = meta.get("source", "未知")
            author = meta.get("author", "")
            title_text = meta.get("title", "")
            url = meta.get("url", "")
            date = meta.get("date", "")
            line = f"- [{ref_id}] {source}"
            if author:
                line += f" | {author}"
            if title_text:
                line += f"《{title_text}》"
            if url:
                line += f" ({url})"
            if date:
                line += f" [{date}]"
            lines.append(line)
        lines.append("")
        return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/utils/reporter/sections/deep_analysis_renderer.py
git commit -m "feat(reporter): add DeepAnalysisRenderer"
```

---

## Task 6: 创建 `RiskRenderer`

**Files:**
- Create: `scripts/utils/reporter/sections/risk_renderer.py`

提取 `risk_score_section`（在 `scoring_engine.py`）+ `_risks_and_watch`。

- [ ] **Step 1: 写入 `RiskRenderer`**

```python
"""风险评分板块渲染器。"""

from typing import Any, Dict, List


class RiskRenderer:
    """六、综合风险评分：风险等级 + 风险因子 + 关注要点。"""

    def required_keys(self) -> list:
        return ["stock_name", "all_posts"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        all_posts = ctx.get("all_posts", [])
        stock_raw = ctx.get("stock_raw", {})
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("ind_fwd_pe")
        synthesis = ctx.get("synthesis", {})

        try:
            from ..scoring_engine import risk_score_section, industry_specific_risk_table
        except ImportError:
            from reporter.scoring_engine import risk_score_section, industry_specific_risk_table

        lines = []

        # 行业特有风险
        chip_risk = industry_specific_risk_table(stock_name)
        if chip_risk:
            lines.append(chip_risk)

        # 风险综合评估
        watch_points = self._risks_and_watch(stock_name, all_posts)
        synthesis_texts = [synthesis.get(k, "") for k in ["industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts"]]
        risk_section = risk_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe, watch_points, "\n".join(synthesis_texts))
        if risk_section:
            lines.append(risk_section)

        if not lines:
            return ""
        return "\n\n".join(lines)

    def _risks_and_watch(self, stock_name: str, posts: List[Dict]) -> List[str]:
        """提取风险关注要点。"""
        watch_points = []
        if not posts:
            return watch_points

        risk_keywords = ["减持", "解禁", "质押", "诉讼", "监管", "问询", "ST", "退市", "亏损", "暴雷"]
        for post in posts:
            text = post.get("title", "") + " " + post.get("content", "")
            for keyword in risk_keywords:
                if keyword in text and keyword not in " ".join(watch_points):
                    watch_points.append(f"社区提及'{keyword}'风险信号")
                    break
            if len(watch_points) >= 5:
                break

        if not watch_points:
            watch_points = [
                "能否站稳关键技术位",
                "同业股价走势（反映板块情绪）",
                "是否有新的产品发布或客户导入公告",
            ]

        return watch_points
```

- [ ] **Step 2: Commit**

```bash
git add scripts/utils/reporter/sections/risk_renderer.py
git commit -m "feat(reporter): add RiskRenderer"
```

---

## Task 7: 创建 `HTMLDashboardRenderer`

**Files:**
- Create: `scripts/utils/reporter/sections/html_dashboard_renderer.py`

提取 `_generate_html_dashboard`（约 300 行，从 2346 行开始）。

- [ ] **Step 1: 读取原 `_generate_html_dashboard` 代码**

Run: `sed -n '2346,2655p' scripts/utils/stock_reporter.py > /tmp/html_dash.txt`

- [ ] **Step 2: 写入 `HTMLDashboardRenderer`**

```python
"""HTML Dashboard 渲染器。"""

from typing import Any, Dict


class HTMLDashboardRenderer:
    """HTML Dashboard：完整可视化仪表盘。"""

    def required_keys(self) -> list:
        return ["stock_name", "date_str"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        date_str = ctx.get("date_str", "")
        pillar = ctx.get("pillar_scores")
        total_score = ctx.get("total_score")
        chart_paths = ctx.get("chart_paths", {})

        # 构建图表路径
        tech_chart = chart_paths.get("technical") or ctx.get("chart_technical")
        radar_chart = chart_paths.get("radar") or ctx.get("chart_radar")
        bullbear_chart = chart_paths.get("bullbear") or ctx.get("chart_bullbear")
        val_chart = chart_paths.get("valuation") or ctx.get("chart_valuation")

        # HTML 模板
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{stock_name} 舆情深度报告 Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 30px;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #1890ff;
            padding-bottom: 10px;
        }}
        .score-card {{
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
            padding: 20px;
            background: #fafafa;
            border-radius: 8px;
        }}
        .score-item {{
            text-align: center;
        }}
        .score-value {{
            font-size: 36px;
            font-weight: bold;
            color: #1890ff;
        }}
        .score-label {{
            color: #666;
            margin-top: 5px;
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }}
        .chart-item {{
            background: #fafafa;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .chart-item img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #999;
            font-size: 12px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{stock_name} 舆情深度报告</h1>
        <p>报告日期: {date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日</p>

        <div class="score-card">
            <div class="score-item">
                <div class="score-value">{total_score if total_score is not None else 'N/A'}</div>
                <div class="score-label">综合评分</div>
            </div>
"""

        if pillar:
            for dim, label in [
                ("valuation", "估值健康度"),
                ("technical", "技术面强度"),
                ("sentiment", "情绪面温度"),
                ("fundamental", "基本面趋势"),
                ("fundflow", "资金关注度"),
            ]:
                score = pillar.get(dim, 0)
                html += f"""
            <div class="score-item">
                <div class="score-value">{score}</div>
                <div class="score-label">{label}</div>
            </div>
"""

        html += """
        </div>

        <div class="chart-grid">
"""

        charts = [
            (radar_chart, "五维评分雷达图"),
            (tech_chart, "技术面综合分析"),
            (bullbear_chart, "多空论点对比"),
            (val_chart, "同业估值对比"),
        ]

        for path, title in charts:
            if path:
                html += f"""
            <div class="chart-item">
                <h3>{title}</h3>
                <img src="{path}" alt="{title}">
            </div>
"""

        html += f"""
        </div>

        <div class="footer">
            <p>本报告基于雪球网公开讨论数据由 Claude AI 深度分析生成，仅供参考，不构成投资建议。</p>
            <p>{stock_name} | {date_str}</p>
        </div>
    </div>
</body>
</html>
"""
        return html
```

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/reporter/sections/html_dashboard_renderer.py
git commit -m "feat(reporter): add HTMLDashboardRenderer"
```

---

## Task 8: 重构 `ReportAssemblySkill`

**Files:**
- Modify: `scripts/utils/report_skills/assembly_skills.py`

删除 `_reporter()`，内联 Header/Footer，直接调用各 Renderer，加 `required_keys` 校验和 `try/except` 容错。移除 FeaturedPosts/CommentHighlights，加占位提示。

- [ ] **Step 1: 重写 `ReportAssemblySkill`**

```python
"""Report assembly skill."""

import logging
from pathlib import Path
from typing import Any, Dict

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
else:
    from skill_pipeline import BaseSkill, SkillContext

logger = logging.getLogger(__name__)

# Header / Footer 模板常量
HEADER_TEMPLATE = """# {stock_name} 舆情深度报告

**报告日期**: {date_display}
**所属赛道**: {industry}
**可比公司**: {competitors}
**数据来源**: 雪球网热门讨论

---"""

FOOTER_TEMPLATE = """---

*本报告基于雪球网公开讨论数据由 Claude AI 深度分析生成，仅供参考，不构成投资建议。*
*报告生成时间: {date_display}*
"""


class ReportAssemblySkill(BaseSkill):
    """Markdown + HTML Dashboard 组装。直接调用各 SectionRenderer，不再依赖 PerStockReporter。"""
    name = "report_assembly"

    # Renderer 注册表（按报告出现顺序）
    RENDERERS = [
        ("executive_summary", "utils.reporter.sections.executive_summary_renderer", "ExecutiveSummaryRenderer"),
        ("composite_score", "utils.reporter.sections.composite_score_renderer", "CompositeScoreRenderer"),
        ("valuation", "utils.reporter.sections.valuation_renderer", "ValuationRenderer"),
        ("technical", "utils.reporter.sections.technical_renderer", "TechnicalRenderer"),
        ("price_target", "utils.reporter.sections.price_target_renderer", "PriceTargetRenderer"),
        ("deep_analysis", "utils.reporter.sections.deep_analysis_renderer", "DeepAnalysisRenderer"),
        ("risk", "utils.reporter.sections.risk_renderer", "RiskRenderer"),
    ]

    def run(self, ctx: SkillContext) -> SkillContext:
        """组装 Markdown + HTML Dashboard。"""
        stock_name = ctx.get("stock_name")
        output_dir = ctx.get("output_dir")
        date_str = ctx.get("date_str")

        md_content = self._assemble_markdown(ctx)
        html_content = self._assemble_html(ctx)

        md_path = Path(output_dir) / f"{stock_name}_{date_str}.md"
        html_path = Path(output_dir) / f"{stock_name}_{date_str}.html"

        md_path.write_text(md_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        ctx.set("md_path", str(md_path))
        ctx.set("html_path", str(html_path))
        return ctx

    def _header(self, ctx: Dict[str, Any]) -> str:
        """报告头部。"""
        stock_name = ctx.get("stock_name", "")
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str

        try:
            from ..reporter.constants import COMPETITOR_MAP, INDUSTRY_MAP
        except ImportError:
            from reporter.constants import COMPETITOR_MAP, INDUSTRY_MAP

        industry = INDUSTRY_MAP.get(stock_name, "")
        competitors = ", ".join(COMPETITOR_MAP.get(stock_name, []))
        return HEADER_TEMPLATE.format(
            stock_name=stock_name,
            date_display=date_display,
            industry=industry,
            competitors=competitors,
        )

    def _footer(self, ctx: Dict[str, Any]) -> str:
        """报告尾部。"""
        stock_name = ctx.get("stock_name", "")
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        return FOOTER_TEMPLATE.format(date_display=date_display, stock_name=stock_name)

    def _render_section(self, name: str, module_path: str, class_name: str, ctx: Dict[str, Any]) -> str:
        """调用单个 renderer，带校验和容错。"""
        try:
            # 动态导入
            module = __import__(module_path, fromlist=[class_name])
            RendererClass = getattr(module, class_name)
            renderer = RendererClass()

            # required_keys 校验
            required = []
            if hasattr(renderer, "required_keys"):
                required = renderer.required_keys()
            missing = [k for k in required if k not in ctx or ctx[k] is None]
            if missing:
                logger.warning(f"[{name}] 缺少必需字段: {missing}，跳过渲染")
                return f"<!-- {name}: skipped (missing keys: {missing}) -->"

            result = renderer.render(ctx)
            return result or ""
        except Exception as e:
            logger.error(f"[{name}] 渲染失败: {e}")
            return f"<!-- {name}: rendering failed ({e}) -->"

    def _assemble_markdown(self, ctx: SkillContext) -> str:
        """组装完整 Markdown 报告。"""
        sections = []
        sections.append(self._header(ctx))

        for name, module_path, class_name in self.RENDERERS:
            section = self._render_section(name, module_path, class_name, ctx)
            if section:
                sections.append(section)

        # 精品帖子/评论摘录占位提示（已迁移至知识库）
        sections.append(
            "> **精品帖子深度解读与关键评论摘录已迁移至知识库。**\n"
        )

        sections.append(self._footer(ctx))

        return "\n\n".join(filter(None, sections))

    def _assemble_html(self, ctx: SkillContext) -> str:
        """组装 HTML Dashboard。"""
        try:
            from ..reporter.sections.html_dashboard_renderer import HTMLDashboardRenderer
        except ImportError:
            from reporter.sections.html_dashboard_renderer import HTMLDashboardRenderer

        renderer = HTMLDashboardRenderer()
        required = renderer.required_keys()
        missing = [k for k in required if k not in ctx or ctx[k] is None]
        if missing:
            logger.warning(f"[html_dashboard] 缺少必需字段: {missing}")
            return f"<!-- HTML Dashboard skipped: missing {missing} -->"

        return renderer.render(ctx)
```

- [ ] **Step 2: 运行测试**

Run: `python -m pytest tests/reporter/test_assembly_skills.py -v`
Expected: PASS（可能需要调整 mock 数据）

- [ ] **Step 3: Commit**

```bash
git add scripts/utils/report_skills/assembly_skills.py
git commit -m "refactor(reporter): rewrite ReportAssemblySkill to use SectionRenderers directly"
```

---

## Task 9: 清理 `PerStockReporter`

**Files:**
- Modify: `scripts/utils/stock_reporter.py`

删除所有已迁移到 renderer 的 section 方法。保留 `__init__`、`generate_stock_report`、`generate_all_reports`。

- [ ] **Step 1: 删除所有 `_xxx_section` 方法**

从 `_header` (389 行) 开始到文件末尾，除了 `__init__`、`generate_stock_report`、`generate_all_reports` 之外全部删除。

删除列表：
- `_header`
- `_executive_summary`
- `_extract_thesis_points`
- `_extract_conclusion`
- `_llm_extract_thesis`
- `_core_facts_table`
- `_valuation_forecast_compact`
- `_quarterly_financials_table`
- `_deep_analysis`
- `_synthesize_sections`
- `_sentiment_and_competition`
- `_competitor_analysis`
- `_core_topics`
- `_featured_posts`
- `_get_featured_analyses`
- `_get_judgment_generator`
- `_get_llm_judgment`
- `_generic_judgment`
- `_comment_highlights`
- `_risks_and_watch`
- `_read_atomic_note`
- `_technical_section`
- `_technical_analysis_section`（保留引用到 renderer）
- `_price_target_section`（保留引用到 renderer）
- `_reports_section`
- `_announcements_section`
- `_fundflow_section`
- `_annotate_cross_sources`
- `_zhihu_section`
- `_valuation_forecast`
- `_footer`
- `_read_full_content_from_vault`
- `_format_media_description`
- `_detect_slogan_content`
- `_extract_argument_chain`
- `_extract_excerpt`
- `_render_synthesis_section`
- `_generate_html_dashboard`

**注意**：`_technical_analysis_section` 和 `_price_target_section` 虽然已委托给 renderer，但当前 `stock_reporter.py` 中仍有定义（回退到旧逻辑）。这些也要删除。

- [ ] **Step 2: 清理 import**

删除 `stock_reporter.py` 顶部不再需要的 import（如 `fetch_tencent_quote`、`generate_technical_panel` 等图表相关 import，保留 `build_stock_report_pipeline` 需要的）。

- [ ] **Step 3: 验证文件行数**

Run: `wc -l scripts/utils/stock_reporter.py`
Expected: < 300 行

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/ -q`
Expected: 89 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/utils/stock_reporter.py
git commit -m "refactor(reporter): remove all section methods from PerStockReporter, now <300 lines"
```

---

## Task 10: 端到端验证

**Files:**
- 运行: `scripts/run_圣邦股份.py`
- 运行: `scripts/run_黑芝麻智能.py`

- [ ] **Step 1: 运行圣邦股份报告生成**

Run: `python scripts/run_圣邦股份.py`
Expected: 成功生成 .md、.html、.pdf

- [ ] **Step 2: 检查报告结构**

Run: `grep "^## " reports/圣邦股份_*.md`
Expected: 包含 执行摘要、综合评分与推荐、估值与财务快照、技术面分析、价格目标与触发条件、深度分析、综合风险评分
不应当包含：精品帖子深度解读、关键评论摘录

- [ ] **Step 3: 运行黑芝麻智能报告生成**

Run: `python scripts/run_黑芝麻智能.py`
Expected: 成功生成

- [ ] **Step 4: 检查评分一致性**

Run: `head -80 reports/黑芝麻智能_*.md | grep "综合评分"`
Expected: 执行摘要和综合评分部分的数字一致

- [ ] **Step 5: Commit**

```bash
git add reports/
git commit -m "test(reporter): validate stock reporter skill decomposition with 圣邦股份 and 黑芝麻智能"
```

---

## Self-Review

### Spec Coverage Check

| Spec Requirement | Task |
|------------------|------|
| 删除 `generate_stock_report_legacy` | Task 1 |
| 创建 8 个 renderer | Tasks 2-7 |
| Header/Footer 内联 | Task 8 |
| `ReportAssemblySkill` 不再构造 `PerStockReporter` | Task 8 |
| `required_keys` 校验 | Task 8 (`_render_section`) |
| `try/except` 容错 | Task 8 (`_render_section`) |
| FeaturedPosts/CommentHighlights 移除 + 占位提示 | Task 8 |
| `PerStockReporter` < 300 行 | Task 9 |
| 端到端验证 | Task 10 |

**无遗漏。**

### Placeholder Scan

- 无 "TBD"、"TODO"、"implement later"
- 无 "add appropriate error handling" 等模糊描述
- 每个代码步骤都有完整代码块
- 每个测试步骤都有具体命令和期望输出

### Type Consistency

- `render(ctx: Dict[str, Any]) -> str` 在所有 renderer 中一致
- `required_keys() -> list` 在所有 renderer 中一致
- `SkillContext` 键名与现有 Pipeline 输出一致

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-06-stock-reporter-full-skill-decomposition.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
