# scripts/utils/reporter/chart_generator.py
"""Chart generator for stock reports using Plotly + Kaleido."""

import os
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _ensure_parent(path: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def generate_technical_panel(
    stock_name: str,
    daily_data: dict[str, list],
    patterns: list[dict[str, Any]],
    indicators: dict[str, float],
    output_path: str,
) -> str:
    """Generate a 4-panel technical chart (K-line+MA, Volume, MACD, RSI)."""
    p = _ensure_parent(output_path)
    close = daily_data.get("close", [])
    volume = daily_data.get("volume", [])
    n = len(close)
    idx = list(range(n))

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=("价格与均线", "成交量", "MACD", "RSI"),
    )

    # Row 1: Price + MA
    fig.add_trace(go.Scatter(x=idx, y=close, mode="lines", name="收盘价", line=dict(color="black")), row=1, col=1)
    for key, color in [("ma5", "orange"), ("ma20", "blue"), ("ma60", "purple")]:
        val = indicators.get(key)
        if val is not None and n > 0:
            fig.add_trace(go.Scatter(x=idx, y=[val] * n, mode="lines", name=key.upper(), line=dict(color=color, dash="dash")), row=1, col=1)

    # Pattern annotations
    for pat in patterns or []:
        if "neckline" in pat:
            fig.add_hline(y=pat["neckline"], line=dict(color="green", dash="dot"), row=1, col=1, annotation_text="颈线")
        for b in ("bottom1", "bottom2"):
            if b in pat:
                fig.add_hline(y=pat[b], line=dict(color="red", dash="dot"), row=1, col=1)

    # Row 2: Volume
    if volume:
        colors = ["red" if i > 0 and close[i] > close[i - 1] else "green" for i in range(n)]
        fig.add_trace(go.Bar(x=idx, y=volume, marker_color=colors, name="成交量"), row=2, col=1)

    # Row 3: MACD
    macd = indicators.get("macd")
    macd_hist = indicators.get("macd_hist")
    if macd is not None and macd_hist is not None and n > 0:
        fig.add_trace(go.Bar(x=idx, y=[macd_hist] * n, marker_color="gray", name="MACD柱状"), row=3, col=1)
        fig.add_trace(go.Scatter(x=idx, y=[macd] * n, mode="lines", name="MACD", line=dict(color="blue")), row=3, col=1)
        fig.add_hline(y=0, line=dict(color="black", width=0.5), row=3, col=1)

    # Row 4: RSI
    rsi = indicators.get("rsi")
    if rsi is not None and n > 0:
        fig.add_trace(go.Scatter(x=idx, y=[rsi] * n, mode="lines", name="RSI", line=dict(color="purple")), row=4, col=1)
        fig.add_hline(y=70, line=dict(color="red", dash="dash"), row=4, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dash"), row=4, col=1)

    fig.update_layout(
        title=f"{stock_name} 技术面分析",
        height=800,
        showlegend=False,
        margin=dict(l=40, r=40, t=60, b=40),
    )
    fig.write_image(str(p), width=900, height=800, scale=2)
    return str(p)


def generate_bull_bear_chart(
    stock_name: str,
    bullish_args: list[dict[str, Any]],
    bearish_args: list[dict[str, Any]],
    output_path: str,
) -> str:
    """Generate horizontal bar chart: bearish left (red), bullish right (green)."""
    p = _ensure_parent(output_path)
    bull = bullish_args or []
    bear = bearish_args or []

    bull_texts = [f"{b['text']} ({b.get('credibility', '')})" for b in bull]
    bull_vals = [b.get("stars", 1) for b in bull]
    bear_texts = [f"{b['text']} ({b.get('credibility', '')})" for b in bear]
    bear_vals = [-b.get("stars", 1) for b in bear]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=bear_texts,
        x=bear_vals,
        orientation="h",
        name="看空",
        marker_color="crimson",
        text=[str(abs(v)) for v in bear_vals],
        textposition="inside",
    ))
    fig.add_trace(go.Bar(
        y=bull_texts,
        x=bull_vals,
        orientation="h",
        name="看多",
        marker_color="seagreen",
        text=[str(v) for v in bull_vals],
        textposition="inside",
    ))

    fig.update_layout(
        title=f"{stock_name} 多空论点对比",
        barmode="overlay",
        height=300 + max(len(bull), len(bear)) * 50,
        xaxis=dict(title="星级评分 (负=看空, 正=看多)", range=[-5.5, 5.5]),
        margin=dict(l=200, r=40, t=60, b=40),
    )
    fig.write_image(str(p), width=900, height=fig.layout.height or 600, scale=2)
    return str(p)


def generate_radar_chart(
    stock_name: str,
    pillar_scores: dict[str, float],
    total_score: float,
    output_path: str,
) -> str:
    """Generate radar chart with 5 dimensions and a passing threshold line at 6."""
    p = _ensure_parent(output_path)
    categories = ["估值", "技术", "情绪", "基本面", "资金流"]
    keys = ["valuation", "technical", "sentiment", "fundamental", "fundflow"]
    values = [pillar_scores.get(k, 0) for k in keys]
    values.append(values[0])  # close the loop
    categories.append(categories[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        name=f"总分 {total_score}",
        line=dict(color="royalblue"),
        fillcolor="rgba(65,105,225,0.2)",
    ))

    # Passing threshold at 6
    threshold = [6.0] * len(categories)
    fig.add_trace(go.Scatterpolar(
        r=threshold,
        theta=categories,
        mode="lines",
        name="及格线 (6)",
        line=dict(color="red", dash="dash"),
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        title=f"{stock_name} 五维评分雷达图 (总分: {total_score})",
        height=600,
        margin=dict(l=80, r=80, t=80, b=40),
    )
    fig.write_image(str(p), width=700, height=600, scale=2)
    return str(p)


def generate_valuation_comparison(
    stock_name: str,
    competitor_metrics: dict[str, dict[str, float]],
    output_path: str,
) -> str:
    """Generate dual-axis chart: Forward PE bars + PS line."""
    p = _ensure_parent(output_path)
    names = list(competitor_metrics.keys())
    forward_pe = [competitor_metrics[n].get("forward_pe", 0) for n in names]
    ps = [competitor_metrics[n].get("ps", 0) for n in names]

    colors = ["royalblue" if n == stock_name else "lightgray" for n in names]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=names,
        y=forward_pe,
        name="Forward PE",
        marker_color=colors,
        text=[f"{v:.1f}" for v in forward_pe],
        textposition="outside",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=names,
        y=ps,
        mode="lines+markers",
        name="PS",
        line=dict(color="crimson"),
        marker=dict(size=10),
    ), secondary_y=True)

    fig.update_layout(
        title=f"{stock_name} 估值对比 (Forward PE vs PS)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=80, b=40),
    )
    fig.update_yaxes(title_text="Forward PE", secondary_y=False)
    fig.update_yaxes(title_text="PS", secondary_y=True)
    fig.write_image(str(p), width=800, height=500, scale=2)
    return str(p)
