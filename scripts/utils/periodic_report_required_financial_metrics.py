"""Deterministic required financial-risk metrics for periodic reports.

This helper is deliberately separate from the LLM output schema.  It extracts
high-value financial risk numbers that should be visible to the annual-report
LLM path, while keeping the numbers deterministic and independently renderable.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional

if __name__.startswith("utils."):
    from .periodic_report_contract_utils import percentage_ratio_cell
    from .periodic_report_required_metrics import _normalize_numeric, _value_cell
else:
    from periodic_report_contract_utils import percentage_ratio_cell
    from periodic_report_required_metrics import _normalize_numeric, _value_cell


REQUIRED_FINANCIAL_METRICS_SCHEMA_VERSION = "periodic_report_required_financial_metrics.v1"


def build_required_financial_risk_metrics(
    evidence_pack: Dict[str, Any],
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Build deterministic financial-risk metrics from evidence-pack blocks and raw text."""
    blocks = [block for block in (evidence_pack.get("blocks") or []) if isinstance(block, dict)]
    source_text = _source_text(blocks, raw_text)
    if not source_text:
        return _empty_metrics(evidence_pack.get("schema_version", ""))

    metrics = {
        "schema_version": REQUIRED_FINANCIAL_METRICS_SCHEMA_VERSION,
        "source_pack_schema_version": evidence_pack.get("schema_version", ""),
        "profit_quality": _extract_profit_quality(source_text),
        "cash_flow_quality": _extract_cash_flow_quality(source_text),
        "inventory_risk": _extract_inventory_risk(source_text),
        "receivables_collection": _extract_receivables_collection(source_text),
        "supplier_concentration": _extract_supplier_concentration(source_text),
        "capex_capacity": _extract_capex_capacity(source_text),
        "asset_impairment": _extract_asset_impairment(source_text),
        "financial_assets": _extract_financial_assets(source_text),
        "leverage_liquidity": _extract_leverage_liquidity(source_text),
        "goodwill_risk": _extract_goodwill_risk(source_text),
        "audit_governance": _extract_audit_governance(source_text),
        "government_grants": _extract_government_grants(source_text),
        "corporate_actions": _extract_corporate_actions(source_text),
    }
    metrics["normalized_values"] = sorted(set(_collect_normalized_values(metrics)))
    metrics["derived_financial_metrics"] = _build_derived_financial_metrics(metrics)
    return metrics


def _empty_metrics(pack_schema: str) -> Dict[str, Any]:
    return {
        "schema_version": REQUIRED_FINANCIAL_METRICS_SCHEMA_VERSION,
        "source_pack_schema_version": pack_schema,
        "profit_quality": {},
        "cash_flow_quality": {},
        "inventory_risk": {},
        "receivables_collection": {},
        "supplier_concentration": {},
        "capex_capacity": {},
        "asset_impairment": {},
        "financial_assets": {},
        "leverage_liquidity": {},
        "goodwill_risk": {},
        "audit_governance": {},
        "government_grants": {},
        "corporate_actions": {},
        "derived_financial_metrics": {},
        "normalized_values": [],
    }


def _source_text(blocks: List[Dict[str, Any]], raw_text: Optional[str]) -> str:
    parts = [str(block.get("text", "")) for block in blocks if block.get("text")]
    if raw_text:
        parts.append(raw_text)
    return _clean_text("\n".join(parts))


def _clean_text(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"(\d)\s*,\s*(\d)", r"\1,\2", text)
    text = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", text)
    text = re.sub(r"(\d+\.\d)\s+(\d)\b", r"\1\2", text)
    text = re.sub(r"(\d)\s*%", r"\1%", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def _extract_hk_profit_quality(text: str) -> Dict[str, Any]:
    """Extract common HK annual-report P&L metrics from Traditional Chinese text."""
    contract_revenue, contract_revenue_yoy = _hk_summary_row_metric_and_rate(
        text, "來自客戶合同的收入"
    )
    summary_gross_profit, _gross_profit_yoy = _hk_summary_row_metric_and_rate(text, "毛利")
    rd_expense, _rd_yoy = _hk_summary_row_metric_and_rate(text, "研發開支")
    _adjusted_operating_loss, _adjusted_operating_yoy = _hk_summary_row_metric_and_rate(
        text, "經調整經營虧損"
    )
    adjusted_loss, _adjusted_loss_yoy = _hk_summary_row_metric_and_rate(
        text, "經調整虧損淨額"
    )
    revenue = (
        contract_revenue
        or _hk_statement_metric(text, "來自客戶合同的收入")
        or _hk_statement_metric(text, "收入")
        or _hk_thousand_metric(text, "收入")
    )
    gross_profit = (
        _hk_statement_metric(text, "毛利")
        or summary_gross_profit
        or _hk_thousand_metric(text, "毛利")
    )
    net_profit = (
        _hk_thousand_metric(text, "本公司權益持有人應佔年內")
        or _hk_thousand_metric(text, "年內虧損")
    )
    operating_loss = _hk_thousand_metric(text, "經營虧損")
    adjusted_loss = adjusted_loss or _hk_thousand_metric(text, "經調整虧損淨額") or _hk_thousand_metric(text, "年內經調整虧損淨額")
    rd_expense = rd_expense or _hk_thousand_metric(text, "研發開支")
    revenue_yoy = contract_revenue_yoy or _hk_rate_near(text, "同比增長")
    gross_margin = _hk_gross_margin(text) or _hk_rate_near(text, "毛利率為")
    return _drop_empty({
        "revenue": revenue,
        "revenue_yoy": revenue_yoy,
        "gross_profit": gross_profit,
        "gross_margin": gross_margin,
        "net_profit": net_profit,
        "operating_loss": operating_loss,
        "adjusted_net_loss": adjusted_loss,
        "rd_expense": rd_expense,
    })


def _hk_summary_row_metric_and_rate(
    text: str,
    label: str,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Extract HK summary rows shaped as: label current previous yoy."""
    pattern = (
        rf"{re.escape(label)}\s+"
        rf"(?P<current_paren>\()?(-?[\d,]+(?:\.\d+)?)(?(current_paren)\))\s+"
        rf"(?P<previous_paren>\()?(-?[\d,]+(?:\.\d+)?)(?(previous_paren)\))\s+"
        rf"(?P<rate>-?\d+(?:\.\d+)?)"
    )
    for match in re.finditer(pattern, text):
        current = match.group(2)
        if not current:
            continue
        if match.groupdict().get("current_paren"):
            current = "-" + current
        return _amount_cell(current, "千元"), _value_cell(match.group("rate"), "%")
    return None, None


def _hk_thousand_metric(text: str, label: str) -> Optional[Dict[str, Any]]:
    """Return the first HK-style metric after a label, assuming RMB thousand unit."""
    patterns = [
        rf"{re.escape(label)}\s*(?P<paren>\()?(-?[\d,]+(?:\.\d+)?)(?(paren)\))",
        rf"{re.escape(label)}[^\n\r]{{0,80}}?(?P<paren>\()?(-?[\d,]+(?:\.\d+)?)(?(paren)\))",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            number = match.group(match.lastindex or 0)
            if not number or not re.search(r"\d", number):
                continue
            prefix_window = text[max(0, match.start() - 30): match.start()]
            if label == "收入" and "其他" in prefix_window:
                continue
            value = "-" + number if match.groupdict().get("paren") else number
            return _amount_cell(value, "千元")
    return None


def _hk_statement_metric(text: str, label: str) -> Optional[Dict[str, Any]]:
    """Prefer the primary HK income statement row over summaries and sub-ledgers."""
    candidates: List[tuple[int, Decimal, Dict[str, Any]]] = []
    for match in re.finditer(r"人民幣千元\s+人民幣千元", text):
        window = text[match.end(): match.end() + 700]
        score = 0
        context = text[max(0, match.start() - 180): match.start() + 80]
        if re.search(r"2025\s*年\s+2024\s*年", context):
            score += 20
        if "比較數字" in context or "比較" in context:
            score += 5
        for cell in _hk_note_row_metric_candidates(window, label):
            candidates.append((score, abs(_amount_in_wan(cell)), cell))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _hk_note_row_metric(text: str, label: str) -> Optional[Dict[str, Any]]:
    """Extract the first material current-year value from a HK note/table row."""
    candidates = _hk_note_row_metric_candidates(text, label)
    return candidates[0] if candidates else None


def _hk_note_row_metric_candidates(text: str, label: str) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for match in re.finditer(re.escape(label), text):
        before = text[max(0, match.start() - 18): match.start()]
        current_line_prefix = text[text.rfind("\n", 0, match.start()) + 1: match.start()]
        if "#" in current_line_prefix:
            continue
        if label.startswith("流動") and before.endswith("非"):
            continue
        if label == "收入" and any(token in before for token in ("財務", "其他", "利息", "政府")):
            continue
        if label == "毛利" and "整體" in before:
            continue
        window = text[match.end(): match.end() + 120]
        window = re.sub(r"[（(][^）)]{0,40}[）)]", " ", window)
        for number_match in re.finditer(r"(?P<paren>\()?(-?[\d,]+(?:\.\d+)?)(?(paren)\))", window):
            number = number_match.group(number_match.lastindex or 0)
            if _looks_like_hk_date_fragment(number) or _looks_like_hk_note_number(number):
                continue
            value = "-" + number if number_match.groupdict().get("paren") else number
            cell = _amount_cell(value, "千元")
            if cell:
                candidates.append(cell)
    return candidates


def _hk_note_table_metric(text: str, marker: str, label: str, *, chars: int = 1200) -> Optional[Dict[str, Any]]:
    start = text.find(marker)
    if start < 0:
        return None
    window = text[start: start + chars]
    return _hk_note_row_metric(window, label)


def _hk_million_metric(text: str, label: str) -> Optional[Dict[str, Any]]:
    pattern = (
        rf"{re.escape(label)}[^\n\r。；;]{{0,80}}?"
        rf"(?P<paren>\()?(-?[\d,]+(?:\.\d+)?)(?(paren)\))\s*百萬(?:港元|元)?"
    )
    for match in re.finditer(pattern, text):
        number = match.group(match.lastindex or 0)
        if not number:
            continue
        value = "-" + number if match.groupdict().get("paren") else number
        return _million_cell(value)
    return None


def _hk_placing_net_proceeds(text: str) -> Optional[Dict[str, Any]]:
    pattern = (
        r"配售所得款項淨額[^\n\r。；;]{0,120}?"
        r"相當於人民\s*幣\s*([\d,]+(?:\.\d+)?)\s*百萬元"
    )
    match = re.search(pattern, text)
    if match:
        return _million_cell(match.group(1))
    return _hk_million_metric(text, "配售所得款項淨額")


def _hk_ezhi_acquisition_consideration(text: str) -> Optional[Dict[str, Any]]:
    for match in re.finditer(r"總代\s*價為人民\s*幣\s*([\d,]+(?:\.\d+)?)\s*百萬元", text):
        context = text[max(0, match.start() - 260): match.end() + 80]
        if "億智電子" in context and "收購" in context:
            return _million_cell(match.group(1))
    return _hk_million_metric(text, "總代價為人民幣")


def _million_cell(amount: str) -> Optional[Dict[str, Any]]:
    if not re.search(r"\d", str(amount or "")):
        return None
    try:
        value = Decimal(_normalize_numeric(amount)) * Decimal("100")
        normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return {"text": amount, "unit": "百万元", "normalized": f"{normalized}万元"}
    except (InvalidOperation, ValueError):
        return {"text": amount, "unit": "百万元", "normalized": _normalize_numeric(amount + "百万元")}


def _hk_rate_near(text: str, label: str) -> Optional[Dict[str, Any]]:
    pattern = rf"{re.escape(label)}\s*(?P<rate>-?\d+(?:\.\d+)?)\s*%"
    match = re.search(pattern, text)
    if not match:
        return None
    return _value_cell(match.group("rate"), "%")


def _hk_gross_margin(text: str) -> Optional[Dict[str, Any]]:
    rate = r"-?\d+(?:\.\d+)?"
    patterns = (
        rf"綜合毛利率(?:達|为|為)?\s*(?P<rate>{rate})\s*%",
        rf"综合毛利率(?:达|为|為)?\s*(?P<rate>{rate})\s*%",
        rf"毛利率由[^\n\r。；;]{{0,120}}?(?:下降|增加|增長|增长|上升|提升)至\s*(?:2025\s*年的?)?\s*(?P<rate>{rate})\s*%",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _value_cell(match.group("rate"), "%")
    return None


def _hk_current_thousand_metric(text: str, label: str) -> Optional[Dict[str, Any]]:
    """Extract the current-year amount immediately following a HK note label."""
    for match in re.finditer(re.escape(label), text):
        window = text[match.end(): match.end() + 180]
        window = re.sub(r"[（(][^）)]{0,40}[）)]", " ", window)
        for number_match in re.finditer(r"(?P<paren>\()?(-?[\d,]+(?:\.\d+)?)(?(paren)\))", window):
            number = number_match.group(number_match.lastindex or 0)
            if _looks_like_hk_date_fragment(number):
                continue
            value = "-" + number if number_match.groupdict().get("paren") else number
            return _amount_cell(value, "千元")
    return None


def _looks_like_hk_date_fragment(number: str) -> bool:
    try:
        value = Decimal(_normalize_numeric(number))
    except (InvalidOperation, ValueError):
        return False
    return value in {Decimal("12"), Decimal("31"), Decimal("2024"), Decimal("2025")}


def _looks_like_hk_note_number(number: str) -> bool:
    try:
        value = abs(Decimal(_normalize_numeric(number)))
    except (InvalidOperation, ValueError):
        return False
    return value < Decimal("100")


def _extract_profit_quality(text: str) -> Dict[str, Any]:
    revenue, revenue_yoy = _line_metric(text, "营业收入")
    net_profit, net_profit_yoy = _line_metric(text, "归属于上市公司股东的净利润")
    deducted_profit, deducted_yoy = _line_metric(
        text,
        "归属于上市公司股东的扣除非经常性损益的净利润",
    )
    hk = _extract_hk_profit_quality(text)
    values = {
        "revenue": revenue,
        "revenue_yoy": revenue_yoy,
        "net_profit": net_profit,
        "net_profit_yoy": net_profit_yoy,
        "deducted_net_profit": deducted_profit,
        "deducted_net_profit_yoy": deducted_yoy,
    }
    for key, value in hk.items():
        if value and not values.get(key):
            values[key] = value
    return _drop_empty(values)


def _extract_cash_flow_quality(text: str) -> Dict[str, Any]:
    operating_cash_flow, operating_yoy = _line_metric(text, "经营活动产生的现金流量净额")
    hk_operating_cash_flow = _hk_thousand_metric(text, "經營活動所用現金淨額")
    return _drop_empty({
        "operating_cash_flow": operating_cash_flow or hk_operating_cash_flow,
        "operating_cash_flow_yoy": operating_yoy,
    })


def _extract_inventory_risk(text: str) -> Dict[str, Any]:
    values = {
        "inventory_book_value": _amount_after(text, "存货账面价值"),
        "inventory_book_value_yoy": _rate_after(text, "存货账面价值", ("同比增长", "同比增加", "同比")),
        "inventory_to_total_assets": _rate_after(text, "存货账面价值", ("占总资产",)),
        "inventory_balance": _amount_after(text, "存货余额"),
        "inventory_impairment_allowance": _amount_after(text, "存货跌价准备", reject_prefixes=("本期计提", "新增", "报告期新增")),
        "current_impairment_provision": _amount_after(text, "存货跌价准备", prefixes=("本期计提", "新增", "报告期新增")),
    }
    hk_values = {
        "inventory_impairment_allowance": _hk_thousand_metric(text, "存貨減值撥備"),
        "current_impairment_provision": _hk_million_metric(text, "確認為銷售成本的存貨減值撥備"),
    }
    for key, value in hk_values.items():
        if value and not values.get(key):
            values[key] = value
    table_values = _inventory_values_from_note_table(text)
    for key, value in table_values.items():
        if not values.get(key):
            values[key] = value
    return _drop_empty(values)


def _extract_receivables_collection(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "accounts_receivable": (
            _amount_after(text, "应收账款", suffixes=("期末余额", "账面价值", "余额"))
            or _hk_note_table_metric(text, "# 23 貿易應收款項及應收票據", "貿易應收款項")
            or _hk_note_row_metric(text, "貿易應收款項")
        ),
        "top_five_ar_percentage": _rate_after(text, "应收账款余额前五名客户占比", ("",)),
        "commercial_bills_receivable": _amount_after(text, "商业承兑汇票", suffixes=("期末余额", "余额")),
        "bills_receivable": (
            _hk_note_table_metric(text, "# 23 貿易應收款項及應收票據", "應收票據")
            or _hk_note_row_metric(text, "應收票據")
        ),
    })


def _extract_supplier_concentration(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "top_five_amount": _amount_after(text, "前五名供应商采购额"),
        "top_five_percentage": _rate_after(text, "前五名供应商采购额", ("占年度采购总额",)),
        "largest_amount": _amount_after(text, "第一大供应商采购额"),
        "largest_percentage": _rate_after(text, "第一大供应商采购额", ("占比",)),
    })


def _extract_capex_capacity(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "construction_in_progress": _amount_after(text, "在建工程"),
        "capex_cash_paid": _amount_after(text, "购建固定资产、无形资产和其他长期资产支付的现金") or _capex_cash_paid(text),
        "investing_cash_flow": _amount_after(text, "投资活动产生的现金流量净额"),
    })


def _extract_asset_impairment(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "asset_impairment_loss": _material_asset_impairment(text),
    })


def _extract_financial_assets(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "monetary_funds": (
            _largest_amount_after_label(text, "货币资金")
            or _hk_note_table_metric(text, "# 24 現金及銀行結餘", "現金及現金等價物")
            or _hk_note_row_metric(text, "年末現金及現金等價物")
        ),
        "trading_financial_assets": _amount_after(text, "交易性金融资产"),
        "trading_financial_assets_to_total_assets": _rate_after(text, "交易性金融资产", ("占总资产",)),
        "investment_income": _amount_after(text, "投资收益"),
        "fair_value_gain": _amount_after(text, "公允价值变动收益"),
        "fair_value_financial_assets": _hk_thousand_metric(text, "金融資產總值"),
    })


def _extract_leverage_liquidity(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "short_term_borrowings": _amount_after(text, "短期借款"),
        "accounts_payable_yoy": _rate_after(text, "应付账款", ("同比增长", "同比增加", "同比")),
        "debt_ratio": _rate_after(text, "资产负债率", ("",)),
        "borrowings": _hk_thousand_metric(text, "借款") if _looks_like_hk_report(text) else None,
    })


def _looks_like_hk_report(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "人民幣",
            "港元",
            "經營虧損",
            "貿易應收",
            "按公允價值計入損益",
        )
    )


def _extract_goodwill_risk(text: str) -> Dict[str, Any]:
    goodwill_balance = _amount_after(text, "商誉")
    if goodwill_balance and _amount_in_wan(goodwill_balance) < Decimal("100"):
        goodwill_balance = None
    return _drop_empty({
        "goodwill_balance": goodwill_balance,
        "goodwill_yoy": _rate_after(text, "商誉", ("同比增长", "同比增加", "同比")),
    })


def _extract_audit_governance(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if "标准的无保留意见" in text or "标准无保留意见" in text:
        result["audit_opinion"] = "标准无保留意见"
    key_matters = []
    if "收入确认" in text:
        key_matters.append("收入确认")
    if "应收账款减值" in text:
        key_matters.append("应收账款减值")
    if "存货跌价" in text:
        key_matters.append("存货跌价")
    if key_matters:
        result["key_audit_matters"] = key_matters
    if _governance_dissent_present(text):
        result["governance_dissent_present"] = True
    return result


def _extract_government_grants(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "government_grants_current": _hk_government_grants_current(text),
    })


def _hk_government_grants_current(text: str) -> Optional[Dict[str, Any]]:
    window = _window_after(text, "# 31 其他應付款項及應計費用", 1600) or text
    candidates = [
        _amount_cell(match.group(1), "千元")
        for match in re.finditer(
            r"政府補助\s*\(a\)\s*(?:Ð|–|-)?\s*([\d,]+(?:\.\d+)?)",
            window,
        )
    ]
    candidates = [cell for cell in candidates if cell]
    if not candidates:
        return None
    return max(candidates, key=_amount_in_wan)


def _extract_corporate_actions(text: str) -> Dict[str, Any]:
    return _drop_empty({
        "placing_net_proceeds": _hk_placing_net_proceeds(text),
        "acquisition_consideration": _hk_ezhi_acquisition_consideration(text),
    })


def _line_metric(text: str, label: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    candidates = []
    for index, line in enumerate(_candidate_lines(text, label)):
        if _is_adjusted_metric_candidate(text, line, label):
            continue
        tail = line[line.find(label) + len(label):] if label in line else line
        tokens = _number_tokens(tail)
        if len(tokens) < 2:
            continue
        explicit_unit = tokens[0][1] if tokens[0][1] in {"亿元", "万元", "千元", "元"} else ""
        contextual_unit = _nearest_table_amount_unit(text, line) if not explicit_unit else ""
        candidates.append((0 if explicit_unit else 1 if contextual_unit else 2, index, tokens, explicit_unit or contextual_unit or "元"))
    for _, _, tokens, unit in sorted(candidates):
        amount = _amount_cell(tokens[0][0], unit)
        rate_token = _rate_token_from_financial_row(tokens)
        rate = _value_cell(rate_token, "%") if rate_token is not None else None
        return amount, rate
    return None, None


def _is_adjusted_metric_candidate(text: str, line: str, label: str) -> bool:
    qualifiers = ("剔除", "经调整", "經調整", "调整后", "調整後")
    label_index = line.find(label)
    if label_index >= 0 and any(token in line[max(0, label_index - 48):label_index] for token in qualifiers):
        return True

    prefixes = []
    start = 0
    while line and (position := text.find(line, start)) >= 0:
        prefixes.append(text[max(0, position - 48):position])
        start = position + max(1, len(line))
    return bool(prefixes) and all(any(token in prefix for token in qualifiers) for prefix in prefixes)


def _nearest_table_amount_unit(text: str, line: str, max_context: int = 600) -> str:
    """Infer a unit only from the nearest table header in the same text block."""
    start = 0
    matches = []
    while line and (position := text.find(line, start)) >= 0:
        context = text[max(0, position - max_context):position].rsplit("\n\n", 1)[-1]
        markers = list(re.finditer(r"单位\s*[:：]\s*(亿元|万元|千元|元)", context))
        if markers:
            matches.append((len(context) - markers[-1].end(), markers[-1].group(1)))
        start = position + max(1, len(line))
    return min(matches, default=(0, ""))[1]


def _candidate_lines(text: str, label: str) -> List[str]:
    lines = [line for line in text.splitlines() if label in line]
    lines.extend(match.group(0) for match in re.finditer(rf"{re.escape(label)}[^\n\r。；;]{{0,260}}", text))
    spaced_label = _spaced_label_pattern(label)
    if spaced_label != re.escape(label):
        lines.extend(
            match.group(0)
            for match in re.finditer(rf"{spaced_label}[^。；;]{{0,260}}", text)
        )
    return lines


def _spaced_label_pattern(label: str) -> str:
    """Match labels that Jina sometimes splits with spaces or line breaks."""
    return r"\s*".join(re.escape(char) for char in str(label or ""))


def _number_tokens(text: str) -> List[tuple[str, str, str]]:
    token_re = re.compile(r"(?P<num>-?[\d,]+(?:\.\d+)?)\s*(?P<unit>亿元|万元|千元|元|%)?")
    return [
        (match.group("num"), match.group("unit") or "", match.group(0))
        for match in token_re.finditer(text)
    ]


def _rate_token_from_financial_row(tokens: List[tuple[str, str, str]]) -> Optional[str]:
    for number, unit, raw in tokens:
        if unit == "%" or "%" in raw:
            return number
    # Common report tables are: current, previous, yoy, third-year.
    if len(tokens) >= 3 and _looks_like_rate(tokens[2][0]):
        return tokens[2][0]
    # Some compact tables are: current, previous, yoy.
    if len(tokens) == 3 and _looks_like_rate(tokens[-1][0]):
        return tokens[-1][0]
    return None


def _looks_like_rate(value: str) -> bool:
    try:
        return abs(Decimal(_normalize_numeric(value))) <= Decimal("500")
    except (InvalidOperation, ValueError):
        return False


def _amount_after(
    text: str,
    label: str,
    *,
    suffixes: Iterable[str] = ("",),
    prefixes: Iterable[str] = ("",),
    reject_prefixes: Iterable[str] = (),
) -> Optional[Dict[str, Any]]:
    for prefix in prefixes:
        for suffix in suffixes:
            pattern = (
                rf"{re.escape(prefix)}\s*{re.escape(label)}\s*{re.escape(suffix)}"
                rf"\s*(?:为人民币|人民币|为|[:：])?\s*"
                rf"(?P<amount>-?[\d,]+(?:\.\d+)?)\s*(?P<unit>亿元|万元|千元|元)?"
            )
            for match in re.finditer(pattern, text):
                before = text[max(0, match.start() - 12): match.start()]
                if reject_prefixes and any(token in before for token in reject_prefixes):
                    continue
                return _amount_cell(match.group("amount"), match.group("unit") or "元")
    return None


def _amount_cell(amount: str, unit: str = "元") -> Optional[Dict[str, Any]]:
    if not re.search(r"\d", str(amount or "")):
        return None
    unit = unit or "元"
    if unit == "元":
        return _value_cell(amount, "元")
    if unit == "万元":
        return {"text": amount, "unit": "万元", "normalized": _normalize_numeric(amount + "万元")}
    if unit == "亿元":
        return {"text": amount, "unit": "亿元", "normalized": _normalize_numeric(amount + "亿元")}
    if unit == "千元":
        try:
            value = Decimal(_normalize_numeric(amount)) / Decimal("10")
            normalized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return {"text": amount, "unit": "千元", "normalized": f"{normalized}万元"}
        except (InvalidOperation, ValueError):
            return {"text": amount, "unit": "千元", "normalized": _normalize_numeric(amount + "千元")}
    return _value_cell(amount, unit)


def _largest_amount_after_label(text: str, label: str) -> Optional[Dict[str, Any]]:
    cells = []
    for match in re.finditer(
        rf"{re.escape(label)}(?:\s+七、\s*\d+)?\s+(?P<amount>-?[\d,]+(?:\.\d+)?)\s*(?P<unit>亿元|万元|千元|元)?",
        text,
    ):
        cell = _amount_cell(match.group("amount"), match.group("unit") or "元")
        if cell:
            cells.append(cell)
    if not cells:
        return None
    return max(cells, key=lambda cell: abs(_amount_in_wan(cell)))


def _material_asset_impairment(text: str) -> Optional[Dict[str, Any]]:
    cells = []
    for label in ("资产减值损失", "资产减值"):
        for match in re.finditer(
            rf"{re.escape(label)}(?:（[^）]*）)?\s*(?P<amount>-?[\d,]+(?:\.\d+)?)\s*(?P<unit>亿元|万元|千元|元)?",
            text,
        ):
            cell = _amount_cell(match.group("amount"), match.group("unit") or "元")
            if cell:
                cells.append(cell)
    if not cells:
        return None
    return max(cells, key=lambda cell: abs(_amount_in_wan(cell)))


def _amount_in_wan(cell: Optional[Dict[str, Any]]) -> Decimal:
    if not isinstance(cell, dict):
        return Decimal("0")
    normalized = str(cell.get("normalized") or "")
    try:
        if normalized.endswith("万元"):
            return Decimal(normalized[:-2])
        if normalized.endswith("亿元"):
            return Decimal(normalized[:-2]) * Decimal("10000")
        return Decimal(_normalize_numeric(normalized or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _inventory_values_from_note_table(text: str) -> Dict[str, Any]:
    window = _inventory_note_window(text)
    sentence_values = _inventory_values_from_sentence(text)
    if sentence_values:
        return sentence_values
    if not window:
        return {}
    total_match = re.search(
        r"合计\s+"
        r"(?P<balance>[\d,]+(?:\.\d+)?)\s+"
        r"(?P<allowance>[\d,]+(?:\.\d+)?)\s+"
        r"(?P<book>[\d,]+(?:\.\d+)?)",
        window,
    )
    if not total_match:
        return {}
    values = {
        "inventory_balance": _amount_cell(total_match.group("balance"), "元"),
        "inventory_impairment_allowance": _amount_cell(total_match.group("allowance"), "元"),
        "inventory_book_value": _amount_cell(total_match.group("book"), "元"),
    }
    provision_window = _window_after(text, "(3). 存货跌价准备", 2000) or _window_after(text, "本期增加金额", 1200)
    current_total = re.search(
        r"合计\s+[\d,]+(?:\.\d+)?\s+(?P<provision>[\d,]+(?:\.\d+)?)",
        provision_window,
    )
    if current_total:
        values["current_impairment_provision"] = _amount_cell(current_total.group("provision"), "元")
    return values


def _capex_cash_paid(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(
        r"购建固定资产、无形资产和其他长期资产支付\s+的现金\s+"
        r"(?P<amount>-?[\d,]+(?:\.\d+)?)",
        text,
    )
    if not match:
        return None
    return _amount_cell(match.group("amount"), "元")


def _inventory_values_from_sentence(text: str) -> Dict[str, Any]:
    match = re.search(
        r"存货账面(?:余额|原值)(?:为人民币|人民币|为)?\s*(?P<balance>[\d,]+(?:\.\d+)?)\s*(?P<unit>亿元|万元|千元|元)"
        r"[^\n\r。；;]{0,100}?已计提存货跌价准备(?:为人民币|人民币|为)?\s*(?P<allowance>[\d,]+(?:\.\d+)?)\s*(?P=unit)",
        text,
    )
    if not match:
        return {}
    balance = _amount_cell(match.group("balance"), match.group("unit"))
    allowance = _amount_cell(match.group("allowance"), match.group("unit"))
    values = {
        "inventory_balance": balance,
        "inventory_impairment_allowance": allowance,
    }
    book_value = _subtract_amounts(match.group("balance"), match.group("allowance"), match.group("unit"))
    if book_value:
        values["inventory_book_value"] = book_value
    return values


def _subtract_amounts(left: str, right: str, unit: str) -> Optional[Dict[str, Any]]:
    try:
        value = Decimal(_normalize_numeric(left)) - Decimal(_normalize_numeric(right))
    except (InvalidOperation, ValueError):
        return None
    text = str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return _amount_cell(text, unit)


def _inventory_note_window(text: str) -> str:
    pos = text.find("账面余额 存货跌价准备")
    if pos < 0:
        balance_pos = text.find("账面余额")
        allowance_pos = text.find("存货跌价准备", balance_pos if balance_pos >= 0 else 0)
        if balance_pos >= 0 and allowance_pos >= 0 and allowance_pos - balance_pos < 200:
            pos = balance_pos
    if pos < 0:
        return ""
    return text[pos: pos + 1800]


def _window_after(text: str, marker: str, chars: int) -> str:
    pos = text.find(marker)
    if pos < 0:
        return ""
    return text[pos: pos + chars]


def _governance_dissent_present(text: str) -> bool:
    named_dissent = re.search(
        r"(董事|监事)[\u4e00-\u9fff]{2,4}(?:认为|因|对|表示).{0,80}(提出异议|表示反对|持反对意见)",
        text,
    )
    if "未提出异议" in text or "无异议" in text:
        return bool(named_dissent)
    return bool(named_dissent or re.search(r"(提出异议|表示反对|持反对意见)", text))


def _rate_after(
    text: str,
    label: str,
    triggers: Iterable[str],
) -> Optional[Dict[str, Any]]:
    for trigger in triggers:
        if trigger:
            pattern = rf"{re.escape(label)}[^\n\r。；;]{{0,180}}?{re.escape(trigger)}\s*(?P<rate>-?\d+(?:\.\d+)?)\s*%"
        else:
            pattern = rf"{re.escape(label)}\s*(?P<rate>-?\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, text)
        if match:
            return _value_cell(match.group("rate"), "%")
    return None


def _last_rate_cell(text: str) -> Optional[Dict[str, Any]]:
    rates = re.findall(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if not rates:
        return None
    return _value_cell(rates[-1], "%")


def _drop_empty(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value not in (None, [], {})}


def _collect_normalized_values(obj: Any) -> List[str]:
    values: List[str] = []
    if isinstance(obj, dict):
        normalized = obj.get("normalized")
        if isinstance(normalized, str) and normalized:
            values.append(normalized)
        for value in obj.values():
            values.extend(_collect_normalized_values(value))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(_collect_normalized_values(item))
    elif isinstance(obj, str) and re.search(r"\d", obj):
        values.append(_normalize_numeric(obj))
    return values


def _build_derived_financial_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Compute deterministic derived risk ratios from normalized required metrics.

    Numerators that represent outflows or losses (R&D, operating cash outflow,
    inventory impairment allowance) use their absolute values so the ratios read
    as "X% of denominator" regardless of sign conventions in the source report.
    """
    derived: Dict[str, Any] = {}

    profit = metrics.get("profit_quality") or {}
    cash_flow = metrics.get("cash_flow_quality") or {}
    inventory = metrics.get("inventory_risk") or {}
    receivables = metrics.get("receivables_collection") or {}
    financial_assets = metrics.get("financial_assets") or {}
    corporate = metrics.get("corporate_actions") or {}

    revenue = _amount_in_wan(profit.get("revenue"))
    gross_profit = _amount_in_wan(profit.get("gross_profit"))
    rd_expense = _amount_in_wan(profit.get("rd_expense"))
    operating_cash_flow = _amount_in_wan(cash_flow.get("operating_cash_flow"))
    monetary_funds = _amount_in_wan(financial_assets.get("monetary_funds"))
    fair_value_financial_assets = _amount_in_wan(financial_assets.get("fair_value_financial_assets"))
    accounts_receivable = _amount_in_wan(receivables.get("accounts_receivable"))
    bills_receivable = _amount_in_wan(receivables.get("bills_receivable"))
    acquisition_consideration = _amount_in_wan(corporate.get("acquisition_consideration"))
    inventory_balance = _amount_in_wan(inventory.get("inventory_balance"))
    inventory_impairment_allowance = _amount_in_wan(inventory.get("inventory_impairment_allowance"))

    if revenue and revenue != 0 and rd_expense:
        derived["rd_expense_to_revenue"] = percentage_ratio_cell(abs(rd_expense), revenue)
    if gross_profit and gross_profit != 0 and rd_expense:
        derived["rd_expense_to_gross_profit"] = percentage_ratio_cell(abs(rd_expense), gross_profit)
    if monetary_funds and monetary_funds != 0 and operating_cash_flow:
        derived["operating_cash_outflow_to_cash"] = percentage_ratio_cell(
            abs(operating_cash_flow), monetary_funds
        )
    if revenue and revenue != 0:
        total_receivables = Decimal("0")
        if accounts_receivable:
            total_receivables += accounts_receivable
        if bills_receivable:
            total_receivables += bills_receivable
        if total_receivables:
            derived["receivables_to_revenue"] = percentage_ratio_cell(total_receivables, revenue)

    cash_and_fv = Decimal("0")
    if monetary_funds:
        cash_and_fv += monetary_funds
    if fair_value_financial_assets:
        cash_and_fv += fair_value_financial_assets
    if cash_and_fv and cash_and_fv != 0 and acquisition_consideration:
        derived["acquisition_to_cash_and_fv_assets"] = percentage_ratio_cell(
            acquisition_consideration, cash_and_fv
        )

    if (
        inventory_balance
        and inventory_balance != 0
        and inventory_impairment_allowance
    ):
        derived["inventory_impairment_allowance_to_inventory_if_available"] = percentage_ratio_cell(
            abs(inventory_impairment_allowance), inventory_balance
        )

    return _drop_empty(derived)
