"""Deterministic fund-flow material pack for deep-analysis 4.3."""

from __future__ import annotations

from typing import Any, Iterable


SCHEMA = "fundflow_material_pack.v1"

SIGNAL_LABELS = {
    "inflow_with_price_up": "资金与价格同向",
    "inflow_with_price_down": "资金流入但价格走弱，资金/价格分歧",
    "outflow_with_price_up": "资金流出但价格上涨，上涨质量待验证",
    "outflow_with_price_down": "资金流出与价格下跌同向",
    "mixed_or_insufficient": "资金方向不稳定或数据不足",
}


def build_fundflow_material_pack(rows: Iterable[dict] | None, max_rows: int = 5) -> dict:
    """Build a deterministic summary pack from raw/normalized fund-flow rows."""
    normalized = [normalize_fundflow_row(row) for row in (rows or []) if isinstance(row, dict)]
    normalized = [row for row in normalized if row.get("date") or row.get("main_net") != 0]
    normalized = normalized[:max_rows]
    if not normalized:
        return {"schema": SCHEMA, "rows": [], "summary": {}}

    main_net_total = round(sum(row["main_net"] for row in normalized), 2)
    super_large_net_total = round(sum(row["super_large_net"] for row in normalized), 2)
    small_net_total = round(sum(row["small_net"] for row in normalized), 2)
    price_change_total_pct = round(sum(row["change_pct"] for row in normalized), 2)

    summary = {
        "days": len(normalized),
        "main_net_total": main_net_total,
        "super_large_net_total": super_large_net_total,
        "small_net_total": small_net_total,
        "price_change_total_pct": price_change_total_pct,
        "signal": _signal(main_net_total, price_change_total_pct),
    }
    return {
        "schema": SCHEMA,
        "rows": normalized,
        "summary": summary,
    }


def format_fundflow_material_pack(pack: dict | None) -> str:
    """Render a compact prompt appendix for 4.3 synthesis."""
    if not isinstance(pack, dict):
        return ""
    summary = pack.get("summary") or {}
    rows = pack.get("rows") or []
    if not summary or not rows:
        return ""

    signal = str(summary.get("signal") or "mixed_or_insufficient")
    signal_label = SIGNAL_LABELS.get(signal, SIGNAL_LABELS["mixed_or_insufficient"])
    lines = [
        "资金流向确定性汇总（仅供4.3使用，非新增引用）",
        "",
        "使用规则：",
        "- 以下数据为确定性汇总，请基于 summary 写资金面，不要自行求和或从日度原始行反推相反结论。",
        "- signal 只能写成资金与价格同向/背离/分歧等客观描述，不得写成买入信号、卖出信号或投资建议。",
        "- 不得为本附录生成新的 [^n] 引用编号；如需引用，仍使用信息来源中的资金流向来源。",
        "",
        (
            f"- summary: 近{int(summary.get('days', 0))}日主力净流入合计 "
            f"{_fmt(summary.get('main_net_total'))}万；超大单+大单合计 "
            f"{_fmt(summary.get('super_large_net_total'))}万；小单合计 "
            f"{_fmt(summary.get('small_net_total'))}万；区间涨跌 "
            f"{_fmt(summary.get('price_change_total_pct'))}%；signal={signal}（{signal_label}）"
        ),
        "- recent_rows:",
    ]
    for row in rows[:5]:
        lines.append(
            f"  - {row.get('date', '')}: 主力净流入 {_fmt(row.get('main_net'))}万，"
            f"超大单+大单 {_fmt(row.get('super_large_net'))}万，"
            f"小单 {_fmt(row.get('small_net'))}万，涨跌 {_fmt(row.get('change_pct'))}%"
        )
    return "\n".join(lines)


def normalize_fundflow_row(row: dict[str, Any]) -> dict:
    """Normalize one fund-flow row across legacy, Baidu PAE and push2-like fields."""
    main_in = _first_number(row, ("main_inflow", "main_in", "main_net"))
    main_out = _first_number(row, ("main_outflow",))
    main_net = main_in - main_out if "main_outflow" in row else main_in
    super_net = _first_number(row, ("super_net_in", "super_big_net"))
    large_net = _first_number(row, ("large_net_in", "big_net"))
    medium_net = _first_number(row, ("medium_net_in", "mid_net"))
    small_net = _first_number(row, ("small_net_in", "small_net"))
    return {
        "date": str(row.get("date") or ""),
        "main_net": round(main_net, 2),
        "main_inflow": main_in,
        "main_outflow": main_out,
        "super_net_in": super_net,
        "large_net_in": large_net,
        "super_large_net": round(super_net + large_net, 2),
        "medium_net": medium_net,
        "small_net": small_net,
        "change_pct": _first_number(row, ("change_pct",)),
        "close": _first_number(row, ("close",)),
        "main_pct": _first_number(row, ("main_pct",)),
        "source": str(row.get("source") or ""),
    }


def _first_number(row: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        if key in row:
            return _num(row.get(key))
    return 0.0


def _num(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _signal(main_net_total: float, price_change_total_pct: float) -> str:
    if main_net_total > 0 and price_change_total_pct > 0:
        return "inflow_with_price_up"
    if main_net_total > 0 and price_change_total_pct < 0:
        return "inflow_with_price_down"
    if main_net_total < 0 and price_change_total_pct > 0:
        return "outflow_with_price_up"
    if main_net_total < 0 and price_change_total_pct < 0:
        return "outflow_with_price_down"
    return "mixed_or_insufficient"


def _fmt(value: Any) -> str:
    number = _num(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.2f}".rstrip("0").rstrip(".")
