"""Formal financial explanation pack extracted from local periodic reports."""

from __future__ import annotations

import hashlib
import re
from typing import Any


SCHEMA = "formal_financial_explanation_pack.v1"
MAX_EXCERPT_CHARS = 220

_TOPIC_PATTERNS = (
    (
        "revenue_change",
        "营业收入",
        ("营业收入", "销售收入", "收入变动", "销售额"),
        ("主要系", "主要由于", "原因", "增加", "下降", "增长", "减少"),
    ),
    (
        "profit_change",
        "归母净利润",
        ("归属于上市公司股东的净利润", "归母净利润", "净利润", "利润总额"),
        ("主要系", "主要由于", "原因", "影响", "增加", "下降", "增长", "减少"),
    ),
    (
        "gross_margin_change",
        "毛利率",
        ("毛利率", "毛利", "成本", "价格"),
        ("主要系", "主要由于", "产品结构", "成本", "价格", "下降", "提升"),
    ),
    (
        "expense_rnd",
        "费用与研发",
        ("研发费用", "研发投入", "销售费用", "管理费用", "费用率", "研发"),
        ("投入", "增加", "下降", "项目", "产品", "平台", "推进"),
    ),
    (
        "inventory_cashflow",
        "存货与现金流",
        ("存货", "经营活动产生的现金流量净额", "经营现金流", "应收账款", "现金流"),
        ("增加", "减少", "下降", "回款", "采购", "备货", "周转"),
    ),
    (
        "orders_customers_guidance",
        "订单客户与经营计划",
        ("订单", "客户", "经营计划", "未来发展", "发展战略", "市场拓展", "应用"),
        ("拓展", "导入", "计划", "继续", "推进", "客户", "应用"),
    ),
)

_ALLOWED_HEADINGS = (
    "经营情况讨论与分析",
    "主营业务分析",
    "报告期内公司从事的主要业务",
    "核心竞争力分析",
    "经营计划",
    "未来发展",
    "管理层讨论与分析",
)

_BLOCKED_HEADINGS = (
    "风险因素",
    "重大风险提示",
    "可能面对的风险",
    "风险提示",
)

_REASON_TOPIC_RULES = (
    (("营业收入",), "revenue_change", "营业收入"),
    (("归属于上市公司股东的净利润", "归母净利润", "净利润"), "profit_change", "归母净利润"),
    (("毛利率", "营业成本"), "gross_margin_change", "毛利率"),
    (("研发费用", "研发投入", "销售费用", "管理费用", "财务费用"), "expense_rnd", "费用与研发"),
    (("存货", "应收账款", "经营活动产生的现金流量净额", "经营现金流"), "inventory_cashflow", "存货与现金流"),
)


def build_formal_financial_explanation_pack(
    raw_text: str,
    *,
    stock_name: str = "",
    source_doc: str = "",
    max_rows: int = 8,
) -> dict[str, Any]:
    """Build a compact, evidence-bound explanation pack from cached report text."""
    rows = []
    seen_topics = set()
    for topic_row in _extract_explicit_reason_rows(raw_text, source_doc=source_doc):
        topic = topic_row["topic"]
        if topic in seen_topics:
            continue
        rows.append(topic_row)
        seen_topics.add(topic)
        if len(rows) >= max_rows:
            break

    for block in _iter_candidate_blocks(raw_text):
        if len(rows) >= max_rows:
            break
        topic_row = _classify_block(block, source_doc=source_doc)
        if not topic_row:
            continue
        topic = topic_row["topic"]
        if topic in seen_topics:
            continue
        rows.append(topic_row)
        seen_topics.add(topic)
        if len(rows) >= max_rows:
            break

    return {
        "schema": SCHEMA,
        "stock_name": stock_name,
        "source_doc": source_doc,
        "rows": rows,
    }


def _extract_explicit_reason_rows(raw_text: str, *, source_doc: str) -> list[dict[str, Any]]:
    rows = []
    lines = [line.strip() for line in str(raw_text or "").splitlines()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if "变动原因说明" not in line or ("：" not in line and ":" not in line):
            index += 1
            continue

        label, body = re.split(r"[:：]", line, maxsplit=1)
        topic, metric = _topic_for_reason_label(label)
        if not topic:
            index += 1
            continue

        parts = [body.strip()]
        next_index = index + 1
        while next_index < len(lines):
            next_line = lines[next_index].strip()
            if not next_line:
                break
            if "变动原因说明" in next_line:
                break
            if _looks_like_heading(next_line):
                break
            parts.append(next_line)
            if len("".join(parts)) >= MAX_EXCERPT_CHARS:
                break
            next_index += 1

        excerpt = _truncate(re.sub(r"\s+", "", "".join(parts)), MAX_EXCERPT_CHARS)
        if excerpt:
            rows.append({
                "topic": topic,
                "metric": metric,
                "excerpt": excerpt,
                "normalized_summary": _summary(topic, excerpt),
                "source_doc": source_doc,
                "source_ref": source_doc,
                "page_hint": label.strip(),
                "excerpt_hash": _hash(excerpt),
                "confidence": 0.92,
            })
        index = max(next_index, index + 1)
    return rows


def _topic_for_reason_label(label: str) -> tuple[str, str]:
    text = re.sub(r"\s+", "", str(label or ""))
    for terms, topic, metric in _REASON_TOPIC_RULES:
        if any(term in text for term in terms):
            return topic, metric
    return "", ""


def _iter_candidate_blocks(raw_text: str):
    current_heading = ""
    allowed = False
    blocked = False
    buffer = []
    for raw_line in str(raw_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if buffer:
                yield {"heading": current_heading, "text": " ".join(buffer)}
                buffer = []
            continue

        if _looks_like_heading(line):
            if buffer:
                yield {"heading": current_heading, "text": " ".join(buffer)}
                buffer = []
            current_heading = _clean_heading(line)
            blocked = any(token in current_heading for token in _BLOCKED_HEADINGS)
            allowed = any(token in current_heading for token in _ALLOWED_HEADINGS)
            continue

        if blocked:
            continue
        if allowed:
            buffer.append(line)
        elif any(token in line for token in ("变动原因说明", "经营计划", "研发投入", "客户", "订单")):
            buffer.append(line)

    if buffer:
        yield {"heading": current_heading, "text": " ".join(buffer)}


def _classify_block(block: dict[str, str], *, source_doc: str) -> dict[str, Any] | None:
    text = re.sub(r"\s+", "", str(block.get("text") or ""))
    if not text:
        return None

    for topic, metric, primary_terms, context_terms in _TOPIC_PATTERNS:
        if not any(term in text for term in primary_terms):
            continue
        if topic in {"revenue_change", "profit_change", "gross_margin_change"} and "变动原因说明" not in text:
            continue
        if not any(term in text for term in context_terms):
            continue
        excerpt = _truncate(text, MAX_EXCERPT_CHARS)
        return {
            "topic": topic,
            "metric": metric,
            "excerpt": excerpt,
            "normalized_summary": _summary(topic, excerpt),
            "source_doc": source_doc,
            "source_ref": source_doc,
            "page_hint": str(block.get("heading") or ""),
            "excerpt_hash": _hash(excerpt),
            "confidence": 0.85 if "变动原因说明" in text else 0.72,
        }
    return None


def _looks_like_heading(line: str) -> bool:
    if "：" in line or ":" in line:
        return bool(re.match(r"^[一二三四五六七八九十]+、|^\d+(?:\.\d+)*[、.]\s*", line))
    if len(line) > 40:
        return False
    if re.match(r"^[一二三四五六七八九十]+、", line):
        return True
    if re.match(r"^\d+(?:\.\d+)*[、.]\s*", line):
        return True
    return any(token == line or token in line for token in _ALLOWED_HEADINGS + _BLOCKED_HEADINGS)


def _clean_heading(line: str) -> str:
    return re.sub(r"^[一二三四五六七八九十]+、|^\d+(?:\.\d+)*[、.]\s*", "", line).strip()


def _truncate(text: str, max_chars: int) -> str:
    text = str(text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip("，。；;、") + "..."


def _summary(topic: str, excerpt: str) -> str:
    labels = {
        "revenue_change": "收入变化原因",
        "profit_change": "利润变化原因",
        "gross_margin_change": "毛利率变化原因",
        "expense_rnd": "费用与研发投入说明",
        "inventory_cashflow": "存货/现金流说明",
        "orders_customers_guidance": "订单客户或经营计划说明",
    }
    return f"{labels.get(topic, '经营解释')}：{excerpt}"


def _hash(text: str) -> str:
    normalized = re.sub(r"\s+", "", str(text or ""))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
