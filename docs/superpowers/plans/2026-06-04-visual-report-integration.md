# 可视化报告与 Markdown 报告集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `stock_reporter.py` 每次生成报告时，同时输出一份带图表嵌入的完整 Markdown 报告和一份精简的 HTML Dashboard 看板。

**Architecture:** 新增 `chart_generator.py` 模块负责 4 张 PNG 图表的生成；`stock_reporter.py` 在 `generate_stock_report()` 中先调图表生成、再拼装 Markdown（嵌入图片引用）、最后输出 HTML Dashboard。图表文件作为共享资产被两种格式引用。

**Tech Stack:** Python, Plotly + Kaleido (PNG 导出), markdown 标准图片语法, HTML + Tailwind CDN。

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/utils/reporter/chart_generator.py` (Create) | 4 张图表的生成：技术分析面板、多空对比、五维雷达、同业估值 |
| `scripts/utils/stock_reporter.py` (Modify) | 在 `generate_stock_report()` 中整合图表生成、Markdown 图片嵌入、HTML Dashboard 输出 |
| `tests/reporter/test_chart_generator.py` (Create) | 图表生成模块的单元测试 |
| `tests/reporter/test_stock_reporter_charts.py` (Create) | 集成测试：验证 Markdown 和 HTML 同时生成且包含图片引用 |

---

## Task 1: Chart Generator Module

**Files:**
- Create: `scripts/utils/reporter/chart_generator.py`
- Test: `tests/reporter/test_chart_generator.py`

- [ ] **Step 1: Write the failing test for chart generator**

```python
# tests/reporter/test_chart_generator.py
import pytest
from pathlib import Path
import tempfile

from scripts.utils.reporter.chart_generator import (
    generate_technical_panel,
    generate_bull_bear_chart,
    generate_radar_chart,
    generate_valuation_comparison,
)


def test_generate_technical_panel_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_tech.png"
        # Minimal data
        daily_data = {"close": [100.0, 101.0, 102.0], "volume": [1000, 2000, 1500]}
        result = generate_technical_panel(
            stock_name="测试股",
            daily_data=daily_data,
            patterns=[{"pattern": "双底", "bottom1": 90.0, "bottom2": 91.0, "neckline": 95.0}],
            indicators={"ma5": 101.0, "ma20": 100.0, "ma60": 98.0, "macd": 0.5, "macd_hist": 0.2, "rsi": 55.0},
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_generate_bull_bear_chart_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_bb.png"
        bull_args = [
            {"text": "营收增长", "stars": 5, "credibility": "高"},
            {"text": "AI驱动", "stars": 4, "credibility": "高"},
        ]
        bear_args = [
            {"text": "利润下滑", "stars": 4, "credibility": "高"},
            {"text": "估值高", "stars": 3, "credibility": "中"},
        ]
        result = generate_bull_bear_chart(
            stock_name="测试股",
            bullish_args=bull_args,
            bearish_args=bear_args,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_generate_radar_chart_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_radar.png"
        pillar = {
            "valuation": 8.0,
            "technical": 7.0,
            "sentiment": 4.0,
            "fundamental": 6.0,
            "fundflow": 5.0,
        }
        result = generate_radar_chart(
            stock_name="测试股",
            pillar_scores=pillar,
            total_score=6.8,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_generate_valuation_comparison_creates_png():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_val.png"
        metrics = {
            "测试股": {"forward_pe": 70.0, "ps": 15.0},
            "竞品A": {"forward_pe": 120.0, "ps": 8.0},
            "竞品B": {"forward_pe": 200.0, "ps": 5.0},
        }
        result = generate_valuation_comparison(
            stock_name="测试股",
            competitor_metrics=metrics,
            output_path=str(output_path),
        )
        assert output_path.exists()
        assert output_path.stat().st_size > 0
```

Run: `pytest tests/reporter/test_chart_generator.py -v`
Expected: FAIL with import errors (module doesn't exist yet)

- [ ] **Step 2: Implement chart_generator.py with all 4 functions**

Create `scripts/utils/reporter/chart_generator.py`:

```python
"""图表生成模块：为股票报告生成4张核心PNG图表。

使用 Plotly + Kaleido 导出静态PNG，支持中文标签。
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _safe_filename(stock_name: str) -> str:
    """生成安全的文件名（去除特殊字符）。"""
    return stock_name.replace(" ", "_").replace("/", "_")


def generate_technical_panel(
    stock_name: str,
    daily_data: Dict,
    patterns: List[Dict],
    indicators: Dict,
    output_path: str,
    date_str: Optional[str] = None,
) -> str:
    """生成技术分析面板：K线+MA+成交量+MACD+RSI，含形态标注。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 提取数据序列
    closes = daily_data.get("close", [])
    volumes = daily_data.get("volume", [])
    highs = daily_data.get("high", closes)
    lows = daily_data.get("low", closes)
    opens = daily_data.get("open", closes)
    dates = list(range(len(closes)))

    if not closes:
        # 无数据时生成占位图
        fig = go.Figure()
        fig.add_annotation(text="暂无日线数据", showarrow=False, font_size=20)
        fig.write_image(str(output_path), width=1200, height=800, scale=2)
        return str(output_path)

    # 创建4联图：价格(2/3高度) + 成交量(1/6) + MACD(1/6) + RSI(1/6)
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.175, 0.175],
        subplot_titles=("价格走势", "成交量", "MACD", "RSI(14)"),
    )

    # Row 1: K线 + MA
    fig.add_trace(go.Candlestick(
        x=dates, open=opens, high=highs, low=lows, close=closes,
        name="K线", increasing_line_color="#E74C3C", decreasing_line_color="#2ECC71",
    ), row=1, col=1)

    for ma_key, ma_color, ma_name in [
        ("ma5", "#F39C12", "MA5"),
        ("ma20", "#3498DB", "MA20"),
        ("ma60", "#9B59B6", "MA60"),
    ]:
        ma_val = indicators.get(ma_key)
        if ma_val and isinstance(ma_val, list) and len(ma_val) == len(closes):
            fig.add_trace(go.Scatter(x=dates, y=ma_val, mode="lines", name=ma_name, line=dict(color=ma_color, width=1.5)), row=1, col=1)

    # 形态标注（颈线、底部）
    for p in patterns:
        neckline = p.get("neckline")
        if neckline:
            fig.add_hline(y=neckline, line_dash="dash", line_color="#E67E22", annotation_text=f"颈线 {neckline}", row=1, col=1)
        bottom1 = p.get("bottom1")
        bottom2 = p.get("bottom2")
        for i, b in enumerate([bottom1, bottom2], 1):
            if b:
                fig.add_annotation(x=len(closes)*0.2*i, y=b, text=f"底{i}", showarrow=True, arrowhead=2, row=1, col=1)

    # 当前价标注
    if closes:
        fig.add_annotation(x=dates[-1], y=closes[-1], text=f"当前 {closes[-1]}", showarrow=False, yshift=15, row=1, col=1)

    # Row 2: 成交量
    colors = ["#E74C3C" if closes[i] >= opens[i] else "#2ECC71" for i in range(len(closes))]
    fig.add_trace(go.Bar(x=dates, y=volumes, marker_color=colors, name="成交量", showlegend=False), row=2, col=1)

    # Row 3: MACD
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    macd_hist = indicators.get("macd_hist")
    if macd and isinstance(macd, list) and len(macd) == len(closes):
        fig.add_trace(go.Scatter(x=dates, y=macd, mode="lines", name="MACD", line=dict(color="#3498DB", width=1.5)), row=3, col=1)
        if macd_signal and isinstance(macd_signal, list):
            fig.add_trace(go.Scatter(x=dates, y=macd_signal, mode="lines", name="信号线", line=dict(color="#E74C3C", width=1.5)), row=3, col=1)
        if macd_hist and isinstance(macd_hist, list):
            hist_colors = ["#E74C3C" if h >= 0 else "#2ECC71" for h in macd_hist]
            fig.add_trace(go.Bar(x=dates, y=macd_hist, marker_color=hist_colors, name="柱", showlegend=False), row=3, col=1)

    # Row 4: RSI
    rsi = indicators.get("rsi")
    if rsi and isinstance(rsi, list) and len(rsi) == len(closes):
        fig.add_trace(go.Scatter(x=dates, y=rsi, mode="lines", name="RSI", line=dict(color="#9B59B6", width=1.5)), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#E74C3C", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#2ECC71", row=4, col=1)

    fig.update_layout(
        title=f"{stock_name} 技术分析面板",
        xaxis_rangeslider_visible=False,
        height=900,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=40),
    )
    fig.update_xaxes(title_text="日期", row=4, col=1)
    fig.update_yaxes(title_text="价格（元）", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_text="RSI", row=4, col=1)

    fig.write_image(str(output_path), width=1200, height=900, scale=2)
    return str(output_path)


def generate_bull_bear_chart(
    stock_name: str,
    bullish_args: List[Dict],
    bearish_args: List[Dict],
    output_path: str,
) -> str:
    """生成多空观点对比图：横向条形图，看多绿色向右，看空红色向左。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 整理数据：看空在上（负值），看多在下（正值）
    bear_labels = [a["text"][:12] for a in bearish_args]  # 截断避免过长
    bear_values = [-a["stars"] for a in bearish_args]
    bull_labels = [a["text"][:12] for a in bullish_args]
    bull_values = [a["stars"] for a in bullish_args]

    all_labels = bear_labels + bull_labels
    all_values = bear_values + bull_values
    all_colors = ["#E74C3C"] * len(bear_labels) + ["#27AE60"] * len(bull_labels)
    all_hover = [f"强度:{a['stars']}/5 可信度:{a.get('credibility','中')}" for a in bearish_args + bullish_args]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=all_labels,
        x=all_values,
        orientation="h",
        marker_color=all_colors,
        text=all_hover,
        textposition="auto",
        hovertemplate="%{y}<br>%{text}<extra></extra>",
    ))

    fig.add_vline(x=0, line_width=2, line_color="#333")
    fig.update_layout(
        title=f"{stock_name} — 多空观点力量对比",
        xaxis_title="强度（负值=看空，正值=看多）",
        yaxis_title="",
        template="plotly_white",
        height=max(400, len(all_labels) * 50 + 100),
        margin=dict(l=150, r=40, t=60, b=40),
        showlegend=False,
    )

    fig.write_image(str(output_path), width=900, height=max(400, len(all_labels) * 50 + 100), scale=2)
    return str(output_path)


def generate_radar_chart(
    stock_name: str,
    pillar_scores: Dict[str, float],
    total_score: float,
    output_path: str,
) -> str:
    """生成五维评分雷达图。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    categories = ["估值健康度", "技术面强度", "情绪面温度", "基本面趋势", "资金关注度"]
    keys = ["valuation", "technical", "sentiment", "fundamental", "fundflow"]
    values = [pillar_scores.get(k, 5.0) for k in keys]
    values.append(values[0])  # 闭合

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor="rgba(52, 152, 219, 0.3)",
        line=dict(color="#3498DB", width=2),
        name=f"{stock_name}",
    ))
    # 及格线（6分）
    fig.add_trace(go.Scatterpolar(
        r=[6, 6, 6, 6, 6, 6],
        theta=categories + [categories[0]],
        mode="lines",
        line=dict(color="#E74C3C", width=1, dash="dash"),
        name="及格线(6分)",
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 12])),
        title=f"五维评分雷达（综合 {total_score}/10）",
        template="plotly_white",
        height=600,
        width=700,
        margin=dict(l=80, r=80, t=80, b=40),
    )

    fig.write_image(str(output_path), width=700, height=600, scale=2)
    return str(output_path)


def generate_valuation_comparison(
    stock_name: str,
    competitor_metrics: Dict[str, Dict],
    output_path: str,
) -> str:
    """生成同业估值对比图：Forward PE 柱状图 + PS 折线图（双Y轴）。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    names = list(competitor_metrics.keys())
    fwd_pe = [competitor_metrics[n].get("forward_pe", 0) or 0 for n in names]
    ps = [competitor_metrics[n].get("ps", 0) or 0 for n in names]

    # 目标股票高亮
    colors = ["#3498DB" if n == stock_name else "#95A5A6" for n in names]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=names, y=fwd_pe, name="Forward PE",
        marker_color=colors, text=[f"{v:.1f}" for v in fwd_pe], textposition="auto",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=names, y=ps, name="PS(市销率)", mode="lines+markers+text",
        line=dict(color="#E74C3C", width=2),
        marker=dict(size=10),
        text=[f"{v:.1f}" for v in ps], textposition="top center",
    ), secondary_y=True)

    fig.update_layout(
        title="同业估值对比（Forward PE + PS）",
        template="plotly_white",
        height=500,
        width=900,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=80, b=40),
    )
    fig.update_yaxes(title_text="Forward PE", secondary_y=False)
    fig.update_yaxes(title_text="PS", secondary_y=True)

    fig.write_image(str(output_path), width=900, height=500, scale=2)
    return str(output_path)
```

Run: `pytest tests/reporter/test_chart_generator.py -v`
Expected: 4 tests PASS (if plotly+kaleido installed), or import error if dependencies missing

- [ ] **Step 3: Add plotly + kaleido to requirements**

Check `requirements.txt` exists and append:

```
plotly>=5.18.0
kaleido>=0.2.1
```

If `requirements.txt` does not exist, create it at project root with the above lines.

Run: `pip install plotly kaleido`
Expected: Installation completes without error.

- [ ] **Step 4: Commit Task 1**

```bash
git add scripts/utils/reporter/chart_generator.py tests/reporter/test_chart_generator.py requirements.txt
git commit -m "feat(reporter): add chart generator module with 4 PNG outputs"
```

---

## Task 2: Integrate Charts into Markdown Report

**Files:**
- Modify: `scripts/utils/stock_reporter.py:92-256` (generate_stock_report flow)
- Modify: `scripts/utils/stock_reporter.py:1597-1725` (_technical_analysis_section)
- Modify: `scripts/utils/reporter/scoring_engine.py:280-360` (composite_score_section)
- Test: `tests/reporter/test_stock_reporter_charts.py`

- [ ] **Step 1: Add chart generation call in generate_stock_report**

In `scripts/utils/stock_reporter.py`, after line ~153 (before cross-source section), insert chart generation:

```python
        # === 图表生成 ===
        chart_paths = {}
        try:
            from .reporter.chart_generator import (
                generate_technical_panel,
                generate_bull_bear_chart,
                generate_radar_chart,
                generate_valuation_comparison,
            )
            chart_prefix = f"{stock_name}_"
            chart_dir = Path(output_dir)

            # 1. 技术分析面板
            tech = stock_raw.get("technical", {})
            daily = tech.get("daily", {})
            indicators = tech.get("indicators", {})
            patterns = indicators.get("_patterns", [])
            tech_path = chart_dir / f"{stock_name}_技术分析面板_{self.date_str}.png"
            if daily.get("close"):
                generate_technical_panel(
                    stock_name=stock_name,
                    daily_data=daily,
                    patterns=patterns,
                    indicators=indicators,
                    output_path=str(tech_path),
                )
                chart_paths["technical_panel"] = str(tech_path)

            # 2. 多空对比图（从 executive summary 数据中提取）
            ps = quote.get("ps") if quote else None
            pillar = compute_pillar_scores(stock_raw, all_posts, quote, consensus, ind_fwd_pe, ps)
            # 看多/看空论据从 synthesis 中提取
            bullish_points = self._extract_thesis_points(synthesis.get("valuation_debate", ""), "bullish")
            bearish_points = self._extract_thesis_points(synthesis.get("valuation_debate", ""), "bearish")
            # 如果 synthesis 中没有，回退到 all_posts 的情绪
            if not bullish_points and not bearish_points:
                sentiment = sentiment_ratio(all_posts)
                bullish_points = [{"text": "社区看多", "stars": min(5, max(1, int(sentiment["bullish"] / 20))), "credibility": "中"}]
                bearish_points = [{"text": "社区看空", "stars": min(5, max(1, int(sentiment["bearish"] / 20))), "credibility": "中"}]

            bb_path = chart_dir / f"{stock_name}_多空观点对比_{self.date_str}.png"
            if bullish_points or bearish_points:
                generate_bull_bear_chart(
                    stock_name=stock_name,
                    bullish_args=bullish_points[:6],   # 最多6条
                    bearish_args=bearish_points[:6],
                    output_path=str(bb_path),
                )
                chart_paths["bull_bear"] = str(bb_path)

            # 3. 五维雷达图
            radar_path = chart_dir / f"{stock_name}_五维评分雷达_{self.date_str}.png"
            total_score = round(
                pillar["valuation"] * 0.30 +
                pillar["technical"] * 0.25 +
                pillar["sentiment"] * 0.20 +
                pillar["fundamental"] * 0.15 +
                pillar["fundflow"] * 0.10, 1
            )
            generate_radar_chart(
                stock_name=stock_name,
                pillar_scores=pillar,
                total_score=total_score,
                output_path=str(radar_path),
            )
            chart_paths["radar"] = str(radar_path)

            # 4. 同业估值对比
            comp_metrics = fetch_competitor_metrics(stock_name, self.stock_codes)
            if comp_metrics:
                val_path = chart_dir / f"{stock_name}_同业估值对比_{self.date_str}.png"
                generate_valuation_comparison(
                    stock_name=stock_name,
                    competitor_metrics=comp_metrics,
                    output_path=str(val_path),
                )
                chart_paths["valuation"] = str(val_path)

        except Exception as e:
            logger.warning(f"[{stock_name}] 图表生成失败: {e}")
            chart_paths = {}
```

- [ ] **Step 2: Embed chart images in Markdown sections**

Modify `_technical_analysis_section()` at `scripts/utils/stock_reporter.py:1720-1725` (before `return`):

After the patterns loop (around line 1723), append:

```python
        # --- 技术分析图表 ---
        lines.append("### 技术分析图表")
        lines.append("")
        lines.append(f"![技术分析面板]({stock_name}_技术分析面板_{self.date_str}.png)")
        lines.append("")
        lines.append("> 图表说明：K线走势（含MA均线）、成交量、MACD、RSI。关键形态与颈线已标注。")
        lines.append("")
```

Modify `composite_score_section()` in `scripts/utils/reporter/scoring_engine.py`:

After the recommendation string (around line 357), before returning, append radar image:

```python
    # 五维雷达图（图片由调用方生成，这里只预留引用位置）
    # 实际图片引用在 stock_reporter.py 中处理
```

Actually, a cleaner approach: modify `composite_score_section()` to return both text and an image marker, or just have `stock_reporter.py` inject the image after calling `composite_score_section()`.

In `stock_reporter.py` line ~185, after `composite_score_section(...)`:

```python
        # 一、综合评分与推荐
        comp_section = composite_score_section(stock_name, all_posts, stock_raw, quote, consensus, ind_fwd_pe)
        # 插入雷达图
        if chart_paths.get("radar"):
            radar_img = f"\n### 五维评分雷达图\n\n![五维评分雷达]({stock_name}_五维评分雷达_{self.date_str}.png)\n"
            comp_section += radar_img
        sections.append(comp_section)
```

Modify `_executive_summary()` in `stock_reporter.py` to embed bull-bear chart:

After the conclusion (around line 340), before `return`, append:

```python
        # 多空观点对比图
        lines.append("### 多空观点拆解")
        lines.append("")
        lines.append(f"![多空观点对比]({stock_name}_多空观点对比_{self.date_str}.png)")
        lines.append("")
        lines.append("> 图表说明：绿色为看多论据，红色为看空论据，长度代表强度（1-5星）。")
        lines.append("")
```

Modify `competitor_metrics_table()` injection in `stock_reporter.py` line ~197:

After `competitor_metrics_table(...)`:

```python
        if comp_metrics:
            sections.append(competitor_metrics_table(stock_name, comp_metrics))
            # 插入估值对比图
            if chart_paths.get("valuation"):
                sections.append(f"\n### 同业估值对比\n\n![同业估值对比]({stock_name}_同业估值对比_{self.date_str}.png)\n")
```

- [ ] **Step 3: Write integration test**

Create `tests/reporter/test_stock_reporter_charts.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.utils.stock_reporter import PerStockReporter


class TestStockReporterChartIntegration:
    def test_generate_stock_report_creates_md_and_html(self, tmp_path):
        """验证 generate_stock_report 同时生成 .md 和 .html"""
        reporter = PerStockReporter()
        reporter.stocks_data = {"测试股": []}
        reporter.raw_data = {"测试股": {"technical": {"daily": {"close": [100, 101]}, "indicators": {}}}}
        reporter.stock_codes = {"测试股": "000001"}
        reporter.date_str = "20260101"
        reporter.date_display = "2026年01月01日"

        with patch("scripts.utils.stock_reporter.fetch_tencent_quote", return_value=None):
            with patch("scripts.utils.stock_reporter.fetch_consensus_eps", return_value=None):
                with patch("scripts.utils.stock_reporter.industry_fwd_pe", return_value=None):
                    with patch("scripts.utils.reporter.chart_generator.generate_technical_panel") as mock_tech:
                        with patch("scripts.utils.reporter.chart_generator.generate_bull_bear_chart") as mock_bb:
                            with patch("scripts.utils.reporter.chart_generator.generate_radar_chart") as mock_radar:
                                with patch("scripts.utils.reporter.chart_generator.generate_valuation_comparison") as mock_val:
                                    mock_tech.return_value = str(tmp_path / "test_tech.png")
                                    mock_bb.return_value = str(tmp_path / "test_bb.png")
                                    mock_radar.return_value = str(tmp_path / "test_radar.png")
                                    mock_val.return_value = str(tmp_path / "test_val.png")

                                    # Mock the synthesis to avoid LLM calls
                                    with patch.object(reporter, "_synthesize_sections", return_value={}):
                                        with patch.object(reporter, "_extract_thesis_points", return_value=[]):
                                            result_md, result_html = reporter.generate_stock_report("测试股", str(tmp_path))

        assert Path(result_md).exists()
        assert Path(result_md).suffix == ".md"
        assert Path(result_html).exists()
        assert Path(result_html).suffix == ".html"

        # Markdown 应包含图片引用
        md_content = Path(result_md).read_text(encoding="utf-8")
        assert "技术分析面板" in md_content
        assert "![" in md_content

        # HTML 应包含图片引用
        html_content = Path(result_html).read_text(encoding="utf-8")
        assert "<img" in html_content or "技术分析面板" in html_content
```

Run: `pytest tests/reporter/test_stock_reporter_charts.py -v`
Expected: May need adjustments based on actual method signatures; iterate until PASS.

- [ ] **Step 4: Commit Task 2**

```bash
git add scripts/utils/stock_reporter.py scripts/utils/reporter/scoring_engine.py tests/reporter/test_stock_reporter_charts.py
git commit -m "feat(reporter): embed chart images into markdown report sections"
```

---

## Task 3: HTML Dashboard Generator

**Files:**
- Modify: `scripts/utils/stock_reporter.py:92-256` (generate_stock_report return value and HTML writing)
- Create: `scripts/utils/reporter/html_dashboard.py` (optional: extract HTML template logic)

- [ ] **Step 1: Change generate_stock_report to return md+html paths**

Modify `generate_stock_report()` signature and return:

```python
    def generate_stock_report(self, stock_name: str, output_dir: str) -> tuple:
        """
        生成单只股票的深度报告（Markdown + HTML Dashboard）。

        Returns:
            (markdown_path, html_path) 元组
        """
```

At the end of the method (around line 255), replace:

```python
        # 保存文件
        filename = f"{stock_name}_{self.date_str}.md"
        filepath = Path(output_dir) / filename
        filepath.write_text(markdown, encoding="utf-8")
        return str(filepath)
```

With:

```python
        # 保存 Markdown
        md_filename = f"{stock_name}_{self.date_str}.md"
        md_path = Path(output_dir) / md_filename
        md_path.write_text(markdown, encoding="utf-8")

        # 生成 HTML Dashboard
        html_filename = f"{stock_name}_Dashboard_{self.date_str}.html"
        html_path = Path(output_dir) / html_filename
        html_content = self._generate_html_dashboard(stock_name, chart_paths, pillar, quote, consensus, ind_fwd_pe)
        html_path.write_text(html_content, encoding="utf-8")

        return str(md_path), str(html_path)
```

- [ ] **Step 2: Implement _generate_html_dashboard method**

Add to `scripts/utils/stock_reporter.py` (after `_footer()` method):

```python
    def _generate_html_dashboard(
        self,
        stock_name: str,
        chart_paths: Dict[str, str],
        pillar: Dict,
        quote: Optional[Dict],
        consensus: Optional[Dict],
        ind_fwd_pe: Optional[float],
    ) -> str:
        """生成精简 HTML Dashboard。"""
        from .reporter.scoring_engine import ev_expectation, sentiment_ratio

        ps = quote.get("ps") if quote else None
        ev = ev_expectation(pillar, consensus)
        total_score = round(
            pillar["valuation"] * 0.30 +
            pillar["technical"] * 0.25 +
            pillar["sentiment"] * 0.20 +
            pillar["fundamental"] * 0.15 +
            pillar["fundflow"] * 0.10, 1
        )
        ev_pct = ev.get("ev_pct")
        ev_pct_str = f"{ev_pct:+.2f}%" if ev_pct is not None else "N/A"
        rec_cn = ev.get("recommendation_cn", "N/A")
        price = quote.get("price", "N/A") if quote else "N/A"

        # 盈亏比（从 price_target 数据）
        pr_ratio = "N/A"
        pt = self.raw_data.get(stock_name, {}).get("price_target")
        if pt and pt.get("profit_risk_ratio"):
            pr_ratio = f"{pt['profit_risk_ratio']}:1"

        # 技术面文字
        tech_text = ""
        tech = self.raw_data.get(stock_name, {}).get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})
        if resonance:
            trend = resonance.get("trend", "")
            momentum = resonance.get("momentum", "")
            tech_text = f"趋势: {trend} | 动量: {momentum}"

        # 多空论据
        bullish = []
        bearish = []
        # 简化为从 pillar 和帖子中生成几条
        if pillar.get("fundamental", 5) >= 7:
            bullish.append({"text": "基本面趋势向上", "stars": 4})
        if pillar.get("valuation", 5) >= 7:
            bullish.append({"text": "估值健康度良好", "stars": 4})
        if pillar.get("technical", 5) >= 7:
            bullish.append({"text": "技术面偏强", "stars": 3})
        if pillar.get("sentiment", 5) <= 3:
            bearish.append({"text": "情绪面偏冷", "stars": 3})
        if pillar.get("valuation", 5) <= 3:
            bearish.append({"text": "估值偏高", "stars": 3})

        # 图片路径（仅文件名，因为 html 和 png 同目录）
        def _img(name):
            p = chart_paths.get(name, "")
            return Path(p).name if p else ""

        tech_img = _img("technical_panel")
        bb_img = _img("bull_bear")
        radar_img = _img("radar")
        val_img = _img("valuation")

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{stock_name} Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif}}</style>
</head>
<body class="bg-gray-50">
<div class="max-w-5xl mx-auto p-4 md:p-6">

<!-- Header -->
<div class="bg-white rounded-xl shadow-sm p-6 mb-4">
    <div class="flex justify-between items-start">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">{stock_name}</h1>
            <p class="text-gray-500 mt-1">{self.date_display}</p>
        </div>
        <div class="text-right">
            <p class="text-3xl font-bold text-gray-900">{price} <span class="text-base font-normal text-gray-500">元</span></p>
        </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
        <div class="text-center p-3 bg-blue-50 rounded-lg"><p class="text-xs text-gray-600">综合评分</p><p class="text-xl font-bold text-blue-600">{total_score}/10</p></div>
        <div class="text-center p-3 bg-green-50 rounded-lg"><p class="text-xs text-gray-600">AI推荐</p><p class="text-xl font-bold text-green-600">{rec_cn}</p></div>
        <div class="text-center p-3 bg-purple-50 rounded-lg"><p class="text-xs text-gray-600">EV</p><p class="text-xl font-bold text-purple-600">{ev_pct_str}</p></div>
        <div class="text-center p-3 bg-orange-50 rounded-lg"><p class="text-xs text-gray-600">盈亏比</p><p class="text-xl font-bold text-orange-600">{pr_ratio}</p></div>
        <div class="text-center p-3 bg-red-50 rounded-lg"><p class="text-xs text-gray-600">操作建议</p><p class="text-xl font-bold text-red-600">关注/不操作</p></div>
    </div>
</div>

<!-- 技术面 -->
<div class="bg-white rounded-xl shadow-sm p-6 mb-4">
    <h2 class="text-xl font-bold text-gray-900 mb-4">📈 技术面分析</h2>
    {f'<img src="{tech_img}" alt="技术分析面板" class="w-full rounded-lg border mb-4">' if tech_img else '<p class="text-gray-400">暂无图表</p>'}
    <p class="text-sm text-gray-600">{tech_text}</p>
</div>

<!-- 多空观点 -->
<div class="bg-white rounded-xl shadow-sm p-6 mb-4">
    <h2 class="text-xl font-bold text-gray-900 mb-4">⚖️ 多空观点拆解</h2>
    {f'<img src="{bb_img}" alt="多空对比" class="w-full rounded-lg border mb-4">' if bb_img else ''}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="p-3 bg-green-50 rounded-lg">
            <h3 class="font-semibold text-green-800 mb-2">🐂 看多力量</h3>
            {''.join(f'<div class="flex items-center gap-2 mb-1"><span class="text-xs">{"⭐"*b["stars"]}</span><span class="text-sm">{b["text"]}</span></div>' for b in bullish) or '<p class="text-sm text-gray-400">暂无明确看多信号</p>'}
        </div>
        <div class="p-3 bg-red-50 rounded-lg">
            <h3 class="font-semibold text-red-800 mb-2">🐻 看空力量</h3>
            {''.join(f'<div class="flex items-center gap-2 mb-1"><span class="text-xs">{"⭐"*b["stars"]}</span><span class="text-sm">{b["text"]}</span></div>' for b in bearish) or '<p class="text-sm text-gray-400">暂无明确看空信号</p>'}
        </div>
    </div>
</div>

<!-- 五维雷达 -->
<div class="bg-white rounded-xl shadow-sm p-6 mb-4">
    <h2 class="text-xl font-bold text-gray-900 mb-4">🎯 五维评分雷达</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
        {f'<img src="{radar_img}" alt="雷达图" class="w-full rounded-lg border">' if radar_img else ''}
        <div class="space-y-2">
            <div class="flex justify-between p-2 bg-green-50 rounded"><span>估值健康度</span><span class="font-bold text-green-600">{pillar.get("valuation",0):.1f}</span></div>
            <div class="flex justify-between p-2 bg-blue-50 rounded"><span>技术面强度</span><span class="font-bold text-blue-600">{pillar.get("technical",0):.1f}</span></div>
            <div class="flex justify-between p-2 bg-yellow-50 rounded"><span>基本面趋势</span><span class="font-bold text-yellow-600">{pillar.get("fundamental",0):.1f}</span></div>
            <div class="flex justify-between p-2 bg-gray-50 rounded"><span>资金关注度</span><span class="font-bold text-gray-600">{pillar.get("fundflow",0):.1f}</span></div>
            <div class="flex justify-between p-2 bg-red-50 rounded"><span>情绪面温度</span><span class="font-bold text-red-600">{pillar.get("sentiment",0):.1f}</span></div>
        </div>
    </div>
</div>

<!-- 同业估值 -->
<div class="bg-white rounded-xl shadow-sm p-6 mb-4">
    <h2 class="text-xl font-bold text-gray-900 mb-4">💰 同业估值对比</h2>
    {f'<img src="{val_img}" alt="估值对比" class="w-full rounded-lg border mb-4">' if val_img else ''}
</div>

<!-- 操作建议 -->
<div class="bg-white rounded-xl shadow-sm p-6 mb-4">
    <h2 class="text-xl font-bold text-gray-900 mb-4">📋 操作建议</h2>
    <table class="w-full text-sm">
        <thead class="bg-gray-100"><tr><th class="p-2 text-left">投资者类型</th><th class="p-2 text-left">建议</th><th class="p-2 text-left">仓位</th></tr></thead>
        <tbody>
            <tr class="border-b"><td class="p-2">短线交易者</td><td class="p-2 text-red-600 font-semibold">观望</td><td class="p-2">0%</td></tr>
            <tr class="border-b"><td class="p-2">波段交易者</td><td class="p-2 text-yellow-600 font-semibold">轻仓试多</td><td class="p-2">5-10%</td></tr>
            <tr><td class="p-2">长期投资者</td><td class="p-2 text-green-600 font-semibold">持有/定投</td><td class="p-2">10-15%</td></tr>
        </tbody>
    </table>
</div>

<!-- Footer -->
<div class="text-center text-xs text-gray-400 mt-6 mb-4">
    <p><a href="{stock_name}_{self.date_str}.md" class="text-blue-500 hover:underline">查看完整分析报告 →</a></p>
    <p class="mt-2">本报告由 AI 深度分析生成，仅供参考，不构成投资建议。</p>
</div>

</div>
</body>
</html>'''
        return html
```

- [ ] **Step 3: Update generate_all_reports to handle tuple return**

Modify `generate_all_reports()` in `stock_reporter.py:66-91`:

```python
    def generate_all_reports(self, output_dir: str = None) -> List[str]:
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "reports"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_paths = []
        for stock_name in self.stocks_data:
            md_path, html_path = self.generate_stock_report(stock_name, str(output_dir))
            if md_path:
                report_paths.append(md_path)
                logger.info(f"[{stock_name}] Markdown: {md_path}")
            if html_path:
                report_paths.append(html_path)
                logger.info(f"[{stock_name}] HTML Dashboard: {html_path}")

        # 同时生成一份汇总简报
        summary_path = self._generate_summary_report(str(output_dir))
        report_paths.append(summary_path)
        logger.info(f"汇总简报已生成: {summary_path}")

        return report_paths
```

- [ ] **Step 4: Commit Task 3**

```bash
git add scripts/utils/stock_reporter.py tests/reporter/test_stock_reporter_charts.py
git commit -m "feat(reporter): add HTML Dashboard output alongside markdown reports"
```

---

## Task 4: End-to-End Validation

**Files:**
- Run: existing stock reporter demo script

- [ ] **Step 1: Run a single stock report generation and verify outputs**

```bash
cd /Users/erichan/testsnow
python -c "
from scripts.utils.stock_reporter import PerStockReporter
import json
from pathlib import Path

reporter = PerStockReporter()
# Load minimal test data
reporter.stocks_data = {'圣邦股份': []}
reporter.raw_data = {'圣邦股份': {'technical': {'daily': {'close': [100, 101, 102, 103, 104]}, 'indicators': {'_resonance': {'trend': '多头', 'momentum': '中性'}, '_patterns': []}}}}
reporter.stock_codes = {'圣邦股份': '300661'}

output_dir = Path('reports/test_e2e')
output_dir.mkdir(parents=True, exist_ok=True)
md_path, html_path = reporter.generate_stock_report('圣邦股份', str(output_dir))
print(f'MD: {md_path}')
print(f'HTML: {html_path}')
print(f'MD exists: {Path(md_path).exists()}')
print(f'HTML exists: {Path(html_path).exists()}')
"
```

Expected: Both files created, md contains `![` image references, html contains `<img` tags.

- [ ] **Step 2: Run existing tests**

```bash
pytest tests/reporter/ -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git commit -m "test: validate md+html dual output end-to-end"
```

---

## Spec Coverage Self-Review

| Spec Requirement | Task | Status |
|-----------------|------|--------|
| 4 张 PNG 图表生成 | Task 1 | ✅ |
| Markdown 嵌入技术分析面板图 | Task 2 Step 2 | ✅ |
| Markdown 嵌入多空对比图 | Task 2 Step 2 | ✅ |
| Markdown 嵌入五维雷达图 | Task 2 Step 2 | ✅ |
| Markdown 嵌入同业估值对比图 | Task 2 Step 2 | ✅ |
| HTML Dashboard 精简结构 | Task 3 | ✅ |
| HTML 底部链接到 md | Task 3 Step 2 | ✅ |
| 一次运行双输出 | Task 2 Step 1 + Task 3 Step 1 | ✅ |
| 图表与 md/html 同目录 | Task 2 Step 1 (output_dir) | ✅ |

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-visual-report-integration.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
