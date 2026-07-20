# scripts/utils/reporter/chart_generator.py
"""Chart generator for stock reports using Plotly + Kaleido."""

import os
import html
from pathlib import Path
import re
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .executive_summary_view import ExecutiveSummaryViewModel
except ImportError:
    from executive_summary_view import ExecutiveSummaryViewModel


def _ensure_parent(path: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _compute_sma(values: list[float], window: int) -> list[float | None]:
    """Compute simple moving average; pad start with None."""
    if len(values) < window:
        return [None] * len(values)
    result: list[float | None] = [None] * (window - 1)
    for i in range(window - 1, len(values)):
        result.append(sum(values[i - window + 1 : i + 1]) / window)
    return result


def _compute_ema(values: list[float], span: int) -> list[float]:
    """Compute exponential moving average."""
    if not values:
        return []
    alpha = 2.0 / (span + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(alpha * v + (1 - alpha) * ema[-1])
    return ema


def _wrap_cjk(text: str, width: int = 22, max_lines: int = 2) -> str:
    """Wrap CJK text while keeping ASCII/numeric tokens intact."""
    tokens = re.findall(r"[A-Za-z0-9+.%()/:-]+|[\u3400-\u9fff]|[^\s]", str(text or ""))
    lines: list[str] = []
    current = ""
    for token in tokens:
        space = " " if current and current[-1].isascii() and token[0].isascii() else ""
        candidate = current + space + token
        if current and len(candidate) > width:
            lines.append(current)
            current = token
            if len(lines) == max_lines:
                break
        else:
            current = candidate
    if len(lines) < max_lines and current:
        lines.append(current)
    return "<br>".join(lines[:max_lines])


def generate_decision_chain_chart(
    view: ExecutiveSummaryViewModel,
    output_path: str,
) -> str:
    """Generate the A4-safe executive decision-chain image."""
    p = _ensure_parent(output_path)
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
    fig.update_yaxes(visible=False, range=[0, 1], fixedrange=True)
    fig.update_layout(
        width=1240,
        height=1600,
        paper_bgcolor="#f3f5f6",
        plot_bgcolor="#f3f5f6",
        margin=dict(l=60, r=60, t=60, b=55),
        showlegend=False,
        font=dict(family="PingFang SC, Microsoft YaHei, Arial", color="#203047"),
    )

    def annotation(x: float, y: float, text: str, **kwargs: Any) -> None:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, **kwargs)

    annotation(0.02, 0.975, "INVESTMENT DECISION", xanchor="left", font=dict(size=18, color="#62717d"))
    annotation(
        0.02, 0.94, f"<b>{html.escape(view.stock_name)}｜投资决策链</b>",
        xanchor="left", font=dict(size=34),
    )
    annotation(0.98, 0.972, html.escape(view.date_str), xanchor="right", font=dict(size=16))
    annotation(
        0.98, 0.94, f"<b>{html.escape(view.recommendation)}</b>",
        xanchor="right", font=dict(size=22, color="#9a403b"),
    )
    fig.add_shape(type="line", x0=0.02, x1=0.98, y0=0.905, y1=0.905, line=dict(color="#244b63", width=4))

    metrics = (
        ("综合评分", view.total_score, "#587a91"),
        ("模型 EV", view.ev, "#587a91"),
        ("风险等级", view.risk_level, "#9a6f42"),
        ("仓位上限", view.position_cap, "#9a403b"),
    )
    for index, (label, value, color) in enumerate(metrics):
        x0 = 0.02 + index * 0.245
        x1 = x0 + 0.225
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0.79, y1=0.88, fillcolor="white", line_width=0)
        fig.add_shape(type="line", x0=x0, x1=x1, y0=0.88, y1=0.88, line=dict(color=color, width=5))
        annotation(x0 + 0.012, 0.853, html.escape(label), xanchor="left", font=dict(size=16, color="#66747d"))
        annotation(x0 + 0.012, 0.818, f"<b>{html.escape(value)}</b>", xanchor="left", font=dict(size=25))

    nodes = (
        ("01", "基本面", view.fundamental, "#dce9e2"),
        ("02", "估值", view.valuation, "#e9e3d6"),
        ("03", "技术与风险", view.technical, "#eddad8"),
    )
    for index, (number, label, node, color) in enumerate(nodes):
        top = 0.73 - index * 0.21
        bottom = top - 0.15
        fig.add_shape(type="rect", x0=0.02, x1=0.98, y0=bottom, y1=top, fillcolor="white", line_width=0)
        fig.add_shape(type="rect", x0=0.02, x1=0.19, y0=bottom, y1=top, fillcolor=color, line_width=0)
        annotation(0.105, top - 0.055, f"<b>{number}</b><br>{label}", font=dict(size=22), align="center")
        annotation(
            0.22, top - 0.05, f"<b>{_wrap_cjk(html.escape(node.title), 29, 2)}</b>",
            xanchor="left", align="left", font=dict(size=24),
        )
        annotation(
            0.22, bottom + 0.035, _wrap_cjk(html.escape(node.detail), 39, 2),
            xanchor="left", align="left", font=dict(size=18, color="#66747d"),
        )
        if index < 2:
            annotation(0.5, bottom - 0.03, "▼", font=dict(size=18, color="#758690"))

    fig.add_shape(type="rect", x0=0.02, x1=0.98, y0=0.035, y1=0.12, fillcolor="#244b63", line_width=0)
    annotation(
        0.5, 0.078, f"<b>当前行动：{_wrap_cjk(html.escape(view.action), 34, 2)}</b>",
        font=dict(size=25, color="white"), align="center",
    )
    annotation(0.02, 0.012, "详细依据、引用与风险因子见正文。", xanchor="left", font=dict(size=14, color="#71808a"))
    fig.write_image(str(p), width=1240, height=1600, scale=1)
    return str(p)


def generate_technical_panel(
    stock_name: str,
    daily_data: dict[str, list],
    patterns: list[dict[str, Any]],
    indicators: dict[str, Any],
    output_path: str,
) -> str | None:
    """Generate a technical chart only from aligned, meaningful time series."""
    close = daily_data.get("close") or []
    n = len(close)
    opens = daily_data.get("open") or []
    highs = daily_data.get("high") or []
    lows = daily_data.get("low") or []
    if n < 60 or any(len(series) != n for series in (opens, highs, lows)):
        return None

    def aligned(value: Any) -> list | None:
        return list(value) if isinstance(value, (list, tuple)) and len(value) == n else None

    volume = aligned(daily_data.get("volume"))
    macd = aligned(indicators.get("macd"))
    macd_hist = aligned(indicators.get("macd_hist"))
    macd_signal = aligned(indicators.get("macd_signal"))
    rsi = aligned(indicators.get("rsi")) or aligned(indicators.get("rsi_14"))
    panels = [name for name, ready in (
        ("volume", volume is not None),
        ("macd", macd is not None and macd_hist is not None),
        ("rsi", rsi is not None),
    ) if ready]
    if not panels:
        return None

    p = _ensure_parent(output_path)
    idx = aligned(daily_data.get("date")) or list(range(n))
    titles = {"volume": "成交量", "macd": "MACD", "rsi": "RSI"}
    rows = 1 + len(panels)

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55] + [0.45 / len(panels)] * len(panels),
        subplot_titles=("价格与均线", *(titles[name] for name in panels)),
    )

    # Row 1: Candlestick + MA
    fig.add_trace(
        go.Candlestick(
            x=idx,
            open=opens,
            high=highs,
            low=lows,
            close=close,
            name="K线",
            increasing_line_color="red",
            decreasing_line_color="green",
        ),
        row=1,
        col=1,
    )

    for key, color, window in [("ma5", "orange", 5), ("ma20", "blue", 20), ("ma60", "purple", 60)]:
        val = indicators.get(key)
        if val is None or n == 0:
            continue
        if isinstance(val, list) and len(val) == n:
            ma_y = val
        elif isinstance(val, (int, float)):
            ma_y = _compute_sma(close, window)
        else:
            continue
        fig.add_trace(
            go.Scatter(
                x=idx,
                y=ma_y,
                mode="lines",
                name=key.upper(),
                line=dict(color=color, dash="dash"),
            ),
            row=1,
            col=1,
        )

    # Pattern annotations
    for pat in patterns or []:
        if "neckline" in pat:
            fig.add_hline(
                y=pat["neckline"],
                line=dict(color="green", dash="dot"),
                row=1,
                col=1,
                annotation_text="颈线",
            )
        for b in ("bottom1", "bottom2"):
            if b in pat:
                # Place marker at the approximate x-position of the pattern
                x_pos = pat.get(f"{b}_idx", n // 3 if b == "bottom1" else 2 * n // 3)
                if x_pos is not None and 0 <= x_pos < n:
                    fig.add_trace(
                        go.Scatter(
                            x=[x_pos],
                            y=[pat[b]],
                            mode="markers",
                            marker=dict(color="red", size=10, symbol="x"),
                            name=b,
                            showlegend=False,
                        ),
                        row=1,
                        col=1,
                    )

    panel_rows = {name: index + 2 for index, name in enumerate(panels)}
    if volume is not None:
        colors = ["red" if i > 0 and close[i] > close[i - 1] else "green" for i in range(n)]
        fig.add_trace(
            go.Bar(x=idx, y=volume, marker_color=colors, name="成交量"),
            row=panel_rows["volume"], col=1,
        )

    if macd is not None and macd_hist is not None:
        row = panel_rows["macd"]
        signal = macd_signal or _compute_ema(macd, 9)
        fig.add_trace(go.Bar(x=idx, y=macd_hist, marker_color="gray", name="MACD柱状"), row=row, col=1)
        fig.add_trace(
            go.Scatter(x=idx, y=macd, mode="lines", name="MACD", line=dict(color="blue")),
            row=row,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=idx,
                y=signal,
                mode="lines",
                name="MACD信号线",
                line=dict(color="orange", dash="dash"),
            ),
            row=row,
            col=1,
        )
        fig.add_hline(y=0, line=dict(color="black", width=0.5), row=row, col=1)

    if rsi is not None:
        row = panel_rows["rsi"]
        fig.add_trace(
            go.Scatter(x=idx, y=rsi, mode="lines", name="RSI", line=dict(color="purple")),
            row=row,
            col=1,
        )
        fig.add_hline(y=70, line=dict(color="red", dash="dash"), row=row, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dash"), row=row, col=1)

    fig.update_layout(
        title=f"{stock_name} 技术面分析",
        height=480 + rows * 150,
        showlegend=False,
        margin=dict(l=40, r=40, t=60, b=40),
    )
    fig.write_image(str(p), width=900, height=480 + rows * 150, scale=2)
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

    bull_texts = [f"{b.get('text', '')} ({b.get('credibility', '')})" for b in bull]
    bull_vals = [b.get("stars", 1) for b in bull]
    bear_texts = [f"{b.get('text', '')} ({b.get('credibility', '')})" for b in bear]
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
