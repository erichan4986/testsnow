"""Deterministic peer comparison material pack builder.

Phase 3b: builds structured peer comparison rows from competitor_metrics
with deterministic confidence scores. No LLM involvement.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from .reporter.peer_config import get_peer_names
except ImportError:
    from reporter.peer_config import get_peer_names

# Supported metrics and their display dimension/unit.
# Phase 3b coverage: profitability, valuation, market cap.
SUPPORTED_METRICS: Dict[str, Dict[str, Any]] = {
    "gross_margin": {
        "dimension": "盈利能力",
        "label": "毛利率",
        "unit": "%",
    },
    "pe_ttm": {
        "dimension": "估值水平",
        "label": "PE(TTM)",
        "unit": "倍",
    },
    "forward_pe": {
        "dimension": "估值水平",
        "label": "Forward PE",
        "unit": "倍",
    },
    "ps": {
        "dimension": "估值水平",
        "label": "PS(市销率)",
        "unit": "倍",
    },
    "mcap": {
        "dimension": "估值水平",
        "label": "总市值",
        "unit": "亿",
    },
}

# Allowed source ref prefixes (formal/professional only).
_ALLOWED_SOURCE_PREFIXES = {
    "公告:", "年报:", "研报:", "指标:", "行业研报:", "行业资讯:", "iwencai:",
}

# Max rows to produce.
_MAX_PEERS_PER_METRIC = 2
_MAX_TOTAL_ROWS = 8


def build_peer_comparison_material(
    stock_name: str,
    competitor_metrics: dict | None = None,
    source_items: list[dict] | None = None,
    stock_config: dict | None = None,
) -> dict:
    """Build deterministic peer comparison material from available data sources.

    Args:
        stock_name: Target stock name (e.g. "复旦微电").
        competitor_metrics: Dict from fetch_competitor_metrics, keyed by name.
        source_items: Formal/professional source-intake items (optional).
        stock_config: Stock config dict with competitors/peer_codes.

    Returns:
        Material dict conforming to schema peer_comparison_material.v1.
    """
    if not competitor_metrics:
        return _empty_material(stock_name, "No competitor_metrics available")

    target_metrics = competitor_metrics.get(stock_name, {})
    if not target_metrics:
        return _empty_material(stock_name, "Target stock has no metrics")

    peer_names = get_peer_names(stock_name, stock_config)
    # Only include peers that actually have metrics data
    available_peers = [p for p in peer_names if p in competitor_metrics]
    if not available_peers:
        return _empty_material(stock_name, "No peers with metrics data")

    rows: List[Dict[str, Any]] = []
    seen_peer_metrics: Dict[str, int] = {}  # "metric" -> count

    for peer_name in available_peers:
        peer_metrics = competitor_metrics[peer_name]
        if not peer_metrics:
            continue

        for metric_key, meta in SUPPORTED_METRICS.items():
            target_val = target_metrics.get(metric_key)
            peer_val = peer_metrics.get(metric_key)
            if target_val is None or peer_val is None:
                continue

            # Enforce peer cap per metric
            if seen_peer_metrics.get(metric_key, 0) >= _MAX_PEERS_PER_METRIC:
                continue

            # Build row
            comparison_text = _build_comparison_text(
                stock_name, peer_name,
                meta["label"], target_val, peer_val, meta["unit"],
            )
            confidence = _compute_confidence(
                base=0.85,
                periods_differ=False,
                units_differ=False,
                industry_news_source=False,
            )
            usage = _usage_from_confidence(confidence)

            row = {
                "dimension": meta["dimension"],
                "target": stock_name,
                "peer": peer_name,
                "metric": metric_key,
                "target_value": target_val,
                "peer_value": peer_val,
                "period": "latest",
                "unit": meta["unit"],
                "comparison": comparison_text,
                "source_refs": ["指标:competitor_metrics"],
                "confidence": confidence,
                "usage": usage,
            }
            rows.append(row)
            seen_peer_metrics[metric_key] = seen_peer_metrics.get(metric_key, 0) + 1

        if len(rows) >= _MAX_TOTAL_ROWS:
            break

    # Limit total rows
    rows = rows[:_MAX_TOTAL_ROWS]

    return {
        "schema": "peer_comparison_material.v1",
        "target": stock_name,
        "peers": available_peers,
        "rows": rows,
        "warnings": [],
    }


def filter_peer_rows_for_prompt(material: dict) -> dict:
    """Filter peer material rows for prompt construction.

    - Drops rows with confidence < 0.50.
    - Strips comparison/values from rows with 0.50 <= confidence < 0.70.
    - Leaves rows with confidence >= 0.70 unchanged.

    Args:
        material: Raw peer comparison material dict.

    Returns:
        Filtered material dict suitable for prompt appendix.
    """
    if not material or not isinstance(material, dict):
        return material or {}

    rows = material.get("rows", [])
    if not rows:
        return dict(material)

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        confidence = row.get("confidence", 0.0)
        if confidence < 0.50:
            continue  # drop entirely

        if 0.50 <= confidence < 0.70:
            # Strip comparison wording and values, keep context
            filtered.append({
                "dimension": row.get("dimension", ""),
                "target": row.get("target", ""),
                "peer": row.get("peer", ""),
                "metric": row.get("metric", ""),
                "period": row.get("period", ""),
                "unit": row.get("unit", ""),
                "source_refs": row.get("source_refs", []),
                "confidence": confidence,
                "usage": "context_only",
            })
        else:
            # keep as-is
            filtered.append(dict(row))

    result = dict(material)
    result["rows"] = filtered
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_material(stock_name: str, warning: str) -> dict:
    return {
        "schema": "peer_comparison_material.v1",
        "target": stock_name,
        "peers": [],
        "rows": [],
        "warnings": [warning],
    }


def _compute_confidence(
    base: float,
    periods_differ: bool = False,
    units_differ: bool = False,
    industry_news_source: bool = False,
) -> float:
    """Compute deterministic confidence score with adjustments."""
    confidence = base
    if periods_differ:
        confidence -= 0.15
    if units_differ:
        confidence -= 0.15
    if industry_news_source:
        confidence -= 0.10
    confidence = min(confidence, 0.95)  # cap
    confidence = max(confidence, 0.0)   # floor
    return round(confidence, 2)


def _usage_from_confidence(confidence: float) -> str:
    if confidence >= 0.70:
        return "claim_eligible"
    elif confidence >= 0.50:
        return "context_only"
    return "audit_only"


def _build_comparison_text(
    target_name: str,
    peer_name: str,
    label: str,
    target_val: float,
    peer_val: float,
    unit: str,
) -> str:
    """Build a deterministic comparison string."""
    diff = target_val - peer_val
    abs_diff = abs(diff)
    formatted_diff = f"{abs_diff:.1f}{unit}" if unit else f"{abs_diff:.1f}"

    if abs_diff < 0.01:
        return f"{label}接近{peer_name}"
    elif diff > 0:
        return f"{label}高于{peer_name}{formatted_diff}"
    else:
        return f"{label}低于{peer_name}{formatted_diff}"
