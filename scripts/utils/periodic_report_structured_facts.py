"""Structured periodic-report facts built from deterministic metrics.

Phase A is helper-only: it does not register a pipeline skill, write Knowledge,
or feed scoring.  It turns a small set of required financial metrics into
evidence-bound filing facts plus display/compute-only derived facts and signals.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

if __name__.startswith("utils."):
    from .periodic_report_required_financial_metrics import _amount_in_wan, _ratio_cell
else:
    from periodic_report_required_financial_metrics import _amount_in_wan, _ratio_cell


STRUCTURED_FACT_SCHEMA_VERSION = "periodic_report_structured_fact.v1"
RISK_SIGNAL_SCHEMA_VERSION = "periodic_report_risk_signal.v1"

_PHASE_A_METRICS: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("revenue", "profit_quality", "revenue", ("营业收入", "收入", "來自客戶合同的收入", "来自客户合同的收入")),
    ("net_profit", "profit_quality", "net_profit", ("归属于上市公司股东的净利润",)),
    (
        "operating_cash_flow",
        "cash_flow_quality",
        "operating_cash_flow",
        (
            "经营活动产生的现金流量净额",
            "經營活動所用現金淨額",
            "经营活动所用现金净额",
            "經營活動產生的現金流量淨額",
        ),
    ),
)

_CORE_FACT_LABELS = {
    "revenue": "营业收入",
    "net_profit": "归母净利润",
    "operating_cash_flow": "经营现金流量净额",
}

_CORE_FACT_ORDER = {
    "revenue": 0,
    "net_profit": 1,
    "operating_cash_flow": 2,
}


def build_periodic_report_structured_fact_pack(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    evidence_pack: Dict[str, Any],
    required_financial_metrics: Dict[str, Any],
    source_doc: str = "",
) -> Dict[str, Any]:
    """Build a conservative Phase A structured fact pack."""
    diagnostics: List[Dict[str, Any]] = []
    filing_facts: List[Dict[str, Any]] = []

    blocks = [
        block
        for block in (evidence_pack.get("blocks") or [])
        if isinstance(block, dict) and block.get("id") and block.get("text")
    ]

    for metric_key, section_key, value_key, labels in _PHASE_A_METRICS:
        cell = (required_financial_metrics.get(section_key) or {}).get(value_key)
        if not isinstance(cell, dict):
            diagnostics.append({
                "code": "missing_required_metric",
                "metric_key": metric_key,
            })
            continue

        anchor: Optional[Dict[str, str]] = None
        matched_label = labels[0]
        for label in labels:
            anchor = _anchor_cell_to_block(blocks, label, cell)
            if anchor:
                matched_label = label
                break
        if not anchor:
            diagnostics.append({
                "code": "unanchored_filing_fact",
                "metric_key": metric_key,
            })
            continue

        filing_facts.append(_filing_fact(
            stock_code=stock_code,
            stock_name=stock_name,
            report_year=report_year,
            report_type=report_type,
            metric_key=metric_key,
            label=matched_label,
            cell=cell,
            anchor=anchor,
            source_doc=source_doc,
        ))

    derived_facts, derived_diagnostics = _build_derived_facts(
        filing_facts,
        stock_code=stock_code,
        report_year=report_year,
        report_type=report_type,
        source_doc=source_doc,
    )
    diagnostics.extend(derived_diagnostics)
    risk_signals = _build_risk_signals(
        derived_facts,
        stock_code=stock_code,
        report_year=report_year,
        report_type=report_type,
    )

    pack = {
        "schema_version": STRUCTURED_FACT_SCHEMA_VERSION,
        "source_pack_schema_version": evidence_pack.get("schema_version", ""),
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_year": int(report_year),
        "report_type": report_type,
        "filing_facts": filing_facts,
        "derived_facts": derived_facts,
        "filing_risk_signals": risk_signals,
        "diagnostics": diagnostics,
    }
    if source_doc:
        pack["source_doc"] = source_doc
    return pack


def _filing_fact(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    metric_key: str,
    label: str,
    cell: Dict[str, Any],
    anchor: Dict[str, str],
    source_doc: str = "",
) -> Dict[str, Any]:
    fact_id = _fact_id(stock_code, report_year, report_type, metric_key)
    unit = str(cell.get("unit") or "")
    fact = {
        "schema_version": STRUCTURED_FACT_SCHEMA_VERSION,
        "source_type": "periodic_report_filing_fact",
        "fact_id": fact_id,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_year": int(report_year),
        "report_type": report_type,
        "metric_key": metric_key,
        "label": label,
        "value": f"{cell.get('text', '')}{unit}",
        "normalized_value": str(cell.get("normalized") or ""),
        "display_value": _display_financial_amount(str(cell.get("normalized") or "")),
        "unit": "万元" if str(cell.get("normalized") or "").endswith("万元") else unit,
        "currency": "CNY",
        "period": str(report_year),
        "value_basis": "as_reported",
        "source_block_id": anchor["source_block_id"],
        "evidence_refs": [anchor["source_block_id"]],
        "source_excerpt": anchor["source_excerpt"],
        "source_excerpt_hash": anchor["source_excerpt_hash"],
        "source_block_hash": anchor["source_block_hash"],
        "confidence": "high",
        "source_credit": 75,
        "knowledge_eligible": False,
    }
    if source_doc:
        fact["source_doc"] = source_doc
    return fact


def filing_facts_to_core_facts(
    filing_facts: List[Dict[str, Any]],
    *,
    max_facts: int = 6,
) -> List[Dict[str, Any]]:
    """Convert anchored official filing facts into DeepAnalysis core facts.

    This adapter is intentionally narrow: only evidence-bound
    ``periodic_report_filing_fact`` rows become supported core facts. It does
    not consume fulltext summaries, derived facts, risk signals, news, or
    research reports.
    """
    eligible = [
        fact
        for fact in filing_facts or []
        if isinstance(fact, dict)
        and fact.get("source_type") == "periodic_report_filing_fact"
        and fact.get("metric_key") in _CORE_FACT_LABELS
        and fact.get("source_block_id")
        and fact.get("source_excerpt")
    ]
    ordered = sorted(
        eligible,
        key=lambda fact: (
            _CORE_FACT_ORDER.get(str(fact.get("metric_key")), 99),
            str(fact.get("fact_id") or ""),
        ),
    )

    core_facts: List[Dict[str, Any]] = []
    for index, fact in enumerate(ordered[:max_facts], 1):
        report_year = fact.get("report_year", "")
        report_type = str(fact.get("report_type") or "")
        label = _CORE_FACT_LABELS[str(fact.get("metric_key"))]
        data = str(fact.get("display_value") or fact.get("normalized_value") or fact.get("value") or "")
        core_facts.append({
            "fact_id": index,
            "fact": label,
            "data": data,
            "confidence": "高",
            "source_refs": [],
            "provenance_status": "supported",
            "source_labels": [f"{report_year}年{report_type}".strip()],
            "evidence_type": "periodic_report_filing_fact",
            "source_excerpt": fact.get("source_excerpt", ""),
            "filing_fact_id": fact.get("fact_id", ""),
        })
    return core_facts


def _display_financial_amount(value: str) -> str:
    """Render filing fact amounts in report-friendly units without changing compute normalization."""
    value = str(value or "").strip()
    if not value.endswith("万元"):
        return value
    try:
        amount_wan = Decimal(value[:-2])
    except (InvalidOperation, ValueError):
        return value
    amount_yi = (amount_wan / Decimal("10000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount_yi == Decimal("-0.00"):
        amount_yi = Decimal("0.00")
    return f"{amount_yi}亿元"


def _build_derived_facts(
    filing_facts: List[Dict[str, Any]],
    *,
    stock_code: str,
    report_year: int,
    report_type: str,
    source_doc: str = "",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_key = {fact.get("metric_key"): fact for fact in filing_facts}
    if not by_key.get("net_profit"):
        return [], [{"code": "missing_net_profit_for_cashflow_ratio"}]
    if not by_key.get("operating_cash_flow"):
        return [], [{"code": "missing_operating_cash_flow_for_cashflow_ratio"}]

    ocf = _amount_in_wan(_cell_from_fact(by_key.get("operating_cash_flow")))
    net_profit = _amount_in_wan(_cell_from_fact(by_key.get("net_profit")))
    diagnostics: List[Dict[str, Any]] = []

    if net_profit <= 0:
        diagnostics.append({"code": "non_positive_net_profit_for_cashflow_ratio"})
        return [], diagnostics

    ratio = _ratio_cell(ocf, abs(net_profit))
    if not ratio:
        diagnostics.append({"code": "cashflow_ratio_not_computable"})
        return [], diagnostics

    metric_key = "operating_cash_flow_to_net_profit"
    derived_fact = {
            "schema_version": STRUCTURED_FACT_SCHEMA_VERSION,
            "source_type": "periodic_report_derived_fact",
            "fact_id": _fact_id(stock_code, report_year, report_type, metric_key),
            "stock_code": stock_code,
            "report_year": int(report_year),
            "report_type": report_type,
            "period": str(report_year),
            "metric_key": metric_key,
            "label": "经营现金流/归母净利润",
            "value": ratio["text"],
            "signed_value": ratio["text"],
            "unit": "pct",
            "input_refs": [
                _fact_id(stock_code, report_year, report_type, "operating_cash_flow"),
                _fact_id(stock_code, report_year, report_type, "net_profit"),
            ],
            "calculation": "operating_cash_flow / abs(net_profit)",
            "formula_version": "cash_conversion.v1",
            "knowledge_eligible": False,
        }
    if source_doc:
        derived_fact["source_doc"] = source_doc
    return [derived_fact], diagnostics


def _build_risk_signals(
    derived_facts: List[Dict[str, Any]],
    *,
    stock_code: str,
    report_year: int,
    report_type: str,
) -> List[Dict[str, Any]]:
    ratio_fact = next(
        (
            fact
            for fact in derived_facts
            if fact.get("metric_key") == "operating_cash_flow_to_net_profit"
        ),
        None,
    )
    if not ratio_fact:
        return []

    ratio_value = _pct_decimal(str(ratio_fact.get("signed_value") or ratio_fact.get("value") or ""))
    if ratio_value is None or ratio_value >= Decimal("50"):
        return []

    return [
        {
            "schema_version": RISK_SIGNAL_SCHEMA_VERSION,
            "source_type": "periodic_report_risk_signal",
            "signal_id": _fact_id(stock_code, report_year, report_type, "cashflow_quality_weak"),
            "signal_type": "cashflow_quality_weak",
            "severity": "medium",
            "rationale": "经营现金流为负，或经营现金流/归母净利润低于 50%",
            "input_refs": [
                _fact_id(stock_code, report_year, report_type, "operating_cash_flow_to_net_profit")
            ],
            "scoring_eligible": False,
        }
    ]


def _anchor_cell_to_block(
    blocks: List[Dict[str, Any]],
    label: str,
    cell: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    text_value = str(cell.get("text") or "")
    if not text_value:
        return None
    text_value_compact = _compact_number(text_value)
    text_value_compact_candidates = {text_value_compact}
    if text_value_compact.startswith("-"):
        text_value_compact_candidates.add(text_value_compact[1:])
    label_compact = _compact_text(label)

    for block in blocks:
        block_text = str(block.get("text") or "")
        block_text_compact = _compact_text(block_text)
        if label_compact not in block_text_compact:
            continue
        block_number_compact = _compact_number(block_text)
        if text_value in block_text or any(
            candidate and candidate in block_number_compact
            for candidate in text_value_compact_candidates
        ):
            source_excerpt = _bounded_excerpt(block_text, label, text_value)
            return {
                "source_block_id": str(block["id"]),
                "source_excerpt": source_excerpt,
                "source_excerpt_hash": _source_text_hash(source_excerpt),
                "source_block_hash": _source_text_hash(block_text),
            }
    return None


def _source_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cell_from_fact(fact: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not fact:
        return None
    return {
        "text": fact.get("value", ""),
        "unit": fact.get("unit", ""),
        "normalized": fact.get("normalized_value", ""),
    }


def _pct_decimal(value: str) -> Optional[Decimal]:
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None
    return Decimal(match.group(0))


def _fact_id(stock_code: str, report_year: int, report_type: str, metric_key: str) -> str:
    return f"periodic:{stock_code}:{int(report_year)}:{report_type}:{metric_key}"


def _compact_number(text: str) -> str:
    return re.sub(r"[\s,，]", "", str(text or ""))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _bounded_excerpt(text: str, label: str, value: str, *, max_chars: int = 240) -> str:
    start_candidates = [idx for idx in (text.find(label), text.find(value)) if idx >= 0]
    center = min(start_candidates) if start_candidates else 0
    start = max(0, center - 60)
    excerpt = text[start : start + max_chars]
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    if start > 0:
        excerpt = "..." + excerpt
    if start + max_chars < len(text):
        excerpt = excerpt.rstrip() + "..."
    return excerpt
