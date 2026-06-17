"""Deterministic required business metrics for A-share annual/semiannual reports.

This helper consumes evidence-pack blocks first, and optionally falls back to
bounded raw-text parsing only when the pack contains no relevant blocks.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple


REQUIRED_METRICS_SCHEMA_VERSION = "periodic_report_required_metrics.v1"

_MAX_EXCERPT_CHARS = 300

_RELEVANT_USAGES = frozenset({
    "segment_margin_table",
    "segment_table",
    "region_table",
    "production_sales_inventory_table",
    "customer_supplier_table",
    "supplier_concentration_table",
})


class RequiredMetricsError(Exception):
    """Raised when required metrics extraction encounters an unrecoverable error."""


def build_required_business_metrics(
    evidence_pack: Dict[str, Any],
    raw_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Build deterministic required business metrics from evidence-pack blocks.

    Falls back to bounded raw-text parsing only when no relevant evidence-pack
    blocks are present.
    """
    pack_schema = evidence_pack.get("schema_version", "")
    blocks = evidence_pack.get("blocks") or []
    evidence_blocks = [b for b in blocks if isinstance(b, dict)]

    extraction_blocks = list(evidence_blocks)
    if raw_text:
        extraction_blocks.append({"id": "", "usage": "raw_text_fallback", "text": raw_text})

    source_text = ""
    source_block_ids: List[str] = []
    if extraction_blocks:
        source_text = "\n\n".join(str(b.get("text", "")) for b in extraction_blocks)
        source_block_ids = [str(b.get("id")) for b in evidence_blocks if b.get("id")]

    if not source_text:
        return _empty_metrics(pack_schema)

    segment_rows = _extract_segment_rows(source_text, source_block_ids, extraction_blocks)
    region_rows = _extract_region_rows(source_text, source_block_ids, extraction_blocks)
    sales_mode_rows = _extract_sales_mode_rows(source_text, source_block_ids, extraction_blocks)
    inventory_rows = _extract_inventory_rows(source_text, source_block_ids, extraction_blocks)
    customer_concentration = _extract_customer_concentration(
        source_text, source_block_ids, extraction_blocks
    )
    supplier_concentration = _extract_supplier_concentration(
        source_text, source_block_ids, extraction_blocks
    )

    normalized_values = _collect_normalized_values(
        segment_rows, region_rows, sales_mode_rows, inventory_rows,
        customer_concentration, supplier_concentration,
    )

    tables = _build_table_presence(
        source_text, segment_rows, region_rows, sales_mode_rows, inventory_rows,
        customer_concentration, supplier_concentration, source_block_ids,
    )

    return {
        "schema_version": REQUIRED_METRICS_SCHEMA_VERSION,
        "source_pack_schema_version": pack_schema,
        "segment_rows": segment_rows,
        "region_rows": region_rows,
        "sales_mode_rows": sales_mode_rows,
        "inventory_rows": inventory_rows,
        "customer_concentration": customer_concentration,
        "supplier_concentration": supplier_concentration,
        "tables": tables,
        "normalized_values": sorted(set(normalized_values)),
    }


def _empty_metrics(pack_schema: str) -> Dict[str, Any]:
    return {
        "schema_version": REQUIRED_METRICS_SCHEMA_VERSION,
        "source_pack_schema_version": pack_schema,
        "segment_rows": [],
        "region_rows": [],
        "sales_mode_rows": [],
        "inventory_rows": [],
        "customer_concentration": _empty_concentration(),
        "supplier_concentration": _empty_concentration(),
        "tables": _empty_tables(),
        "normalized_values": [],
    }


def _empty_concentration() -> Dict[str, Any]:
    return {
        "present": False,
        "headers_found": [],
        "top_five_amount": None,
        "top_five_percentage": None,
        "largest_amount": None,
        "largest_percentage": None,
        "related_party_amount": None,
        "related_party_percentage": None,
        "source_block_id": None,
        "source_usage": None,
        "source_excerpt": None,
    }


def _empty_tables() -> Dict[str, Any]:
    return {
        "segment_margin": {"headers_found": [], "present": False, "row_count": 0, "source_block_ids": []},
        "region": {"headers_found": [], "present": False, "row_count": 0, "source_block_ids": []},
        "sales_mode": {"headers_found": [], "present": False, "row_count": 0, "source_block_ids": []},
        "inventory": {"headers_found": [], "present": False, "row_count": 0, "source_block_ids": []},
        "customer_supplier": {"headers_found": [], "present": False, "row_count": 0, "source_block_ids": []},
    }


def _block_for_usage(relevant_blocks: List[Dict[str, Any]], usage: str) -> Optional[Dict[str, Any]]:
    for block in relevant_blocks:
        if block.get("usage") == usage:
            return block
    return None


def _source_info(blocks: List[Dict[str, Any]], text: str) -> Tuple[str, str, str]:
    """Return (block_id, usage, excerpt) for a row/excerpt derived from blocks or raw text."""
    if blocks:
        block = blocks[0]
        excerpt = _excerpt(text)
        return str(block.get("id") or ""), str(block.get("usage") or ""), excerpt
    return "", "", _excerpt(text)


def _excerpt(text: str, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Table parsing helpers
# ---------------------------------------------------------------------------


def _clean_lines(text: str) -> List[str]:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return lines


def _normalize_line(line: str) -> str:
    """Collapse repeated spaces and repair Jina line breaks inside tokens."""
    line = re.sub(r"\s+", " ", line).strip()
    # Jina sometimes splits numbers/percentages: "99. 42%" -> "99.42%"
    line = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", line)
    line = re.sub(r"(\d+\.\d)\s+(\d)\b", r"\1\2", line)
    line = re.sub(r"(\d)\s*([%])", r"\1\2", line)
    # Jina sometimes splits product names like "数 模 混 合\nSoC 类".
    # Collapse spaces between consecutive CJK chars; keep a single space between
    # CJK and Latin sequences so "SoC 类" stays readable.
    line = re.sub(r"([一-鿿])\s+(?=[一-鿿])", r"\1", line)
    # Preserve space around unit words so they remain separate tokens.
    line = re.sub(r"([一-鿿A-Za-z])\s*(万颗|kg|吨|万件|台|件|米|个)\s*", r"\1 \2 ", line)
    return line.strip()


def _merge_spaced_tokens(line: str) -> str:
    """Repair Jina-style spacing inside numeric tokens and product names."""
    line = _normalize_line(line)
    return line


def _normalize_numeric(text: str) -> str:
    """Return a canonical form for matching: no internal whitespace, half-width, signed pct."""
    text = str(text or "")
    # Normalize full-width digits/punctuation before stripping spaces.
    text = text.translate(str.maketrans({
        "＋": "+",
        "－": "-",
        "％": "%",
        "，": ",",
        "．": ".",
        "（": "(",
        "）": ")",
    }))
    # Repair spaced decimals/percentages before removing commas.
    text = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", text)
    text = re.sub(r"(\d+\.\d)\s+(\d)\b", r"\1\2", text)
    text = re.sub(r"(\d)\s*%", r"\1%", text)
    text = re.sub(r"\s+", "", text)
    text = text.replace(",", "")
    # Convert 增加/减少 X.XX 个百分点 to signed pct.
    increase = re.search(r"增加([\d\.]+)个百分点", text)
    decrease = re.search(r"减少([\d\.]+)个百分点", text)
    if increase:
        return f"+{increase.group(1)}pct"
    if decrease:
        return f"-{decrease.group(1)}pct"
    # Append pct unit if text contains percentage but no unit suffix yet.
    if "%" in text and not text.endswith("%"):
        text = text.replace("%", "")
    if "%" in text:
        return text
    return text


def _value_cell(text: str, unit_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    text = _merge_spaced_tokens(text)
    if not text or text in ("/", "—", "-"):
        return None
    unit = unit_hint

    if unit_hint == "%":
        value_match = re.search(r"-?[\d,\.]+", text)
        if not value_match:
            return None
        value = value_match.group(0)
        display = value if value.endswith("%") else f"{value}%"
        return {"text": display, "unit": "%", "normalized": _normalize_numeric(display)}

    if unit_hint == "pct":
        if "增加" in text or "减少" in text or "个百分点" in text:
            return {"text": text, "unit": "pct", "normalized": _normalize_numeric(text)}
        value_match = re.search(r"-?[\d,\.]+", text)
        if not value_match:
            return None
        value = value_match.group(0)
        return {"text": value, "unit": "pct", "normalized": _normalize_numeric(f"{value}pct")}

    # Percent / percentage points.
    pct_match = re.search(r"(-?[\d\.]+)\s*(%|pct|个百分点)", text)
    if pct_match:
        value = pct_match.group(1)
        unit = "%"
        normalized = _normalize_numeric(text)
        return {"text": value, "unit": unit, "normalized": normalized}

    # Amount with optional unit (preserve commas in text).
    amount_match = re.search(r"(-?[\d,\.]+)\s*([万亿元万颗kgtKG吨台件米个]+)?", text)
    if amount_match:
        value = amount_match.group(1)
        unit = unit or amount_match.group(2)
        if unit is None and "元" in text:
            unit = "元"
        normalized = _normalize_numeric(value + (unit or ""))
        if unit == "元":
            normalized = _yuan_to_wan_normalized(value)
            unit = "万元"
        return {"text": value, "unit": unit, "normalized": normalized}

    return None


def _yuan_to_wan_normalized(value: str) -> str:
    cleaned = _normalize_numeric(value)
    try:
        amount = Decimal(cleaned) / Decimal("10000")
    except (InvalidOperation, ValueError):
        return cleaned + "元"
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount}万元"


def _clean_table_text(text: str) -> str:
    text = "\n".join(_clean_lines(text))
    text = _normalize_line(text)
    return re.sub(r"\s+", " ", text).strip()


def _section_between(text: str, start_markers: Tuple[str, ...], end_markers: Tuple[str, ...]) -> str:
    compact = _clean_table_text(text)
    starts = [compact.find(marker) for marker in start_markers if compact.find(marker) >= 0]
    if not starts:
        return ""
    start = min(starts)
    end_candidates = [
        compact.find(marker, start + 1)
        for marker in end_markers
        if compact.find(marker, start + 1) >= 0
    ]
    end = min(end_candidates) if end_candidates else len(compact)
    return compact[start:end].strip()


def _normalize_label(label: str) -> str:
    label = _normalize_line(label)
    label = re.sub(r"\s+", " ", label).strip()
    label = re.sub(r"^[/\d\.\(\)（）]+", "", label).strip()
    label = re.sub(r"([一-鿿])\s+(?=[一-鿿])", r"\1", label)
    label = label.replace("数模混合 So C", "数模混合 SoC")
    label = label.replace("So C", "SoC")
    return label


_AMOUNT = r"-?[\d,]+(?:\.\d+)?"
_RATE = r"-?\d+(?:\.\d+)?"
_RATE_WITH_OPTIONAL_PERCENT = r"-?\d+(?:\.\d+)?%?"
_DELTA = r"(?:增加\s*)?(?:减少\s*)?-?\d+(?:\.\d+)?\s*(?:个百分点)?"
_LABEL = r"[\u4e00-\u9fffA-Za-z0-9\s]+?"


def _parse_metric_rows_from_section(section: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not section:
        return rows
    # Remove noisy header fragments that otherwise become labels.
    section = re.sub(
        r"(?:分行业|分产品|分地区|销售模式)\s+营业收入\s+营业成本\s+毛利率（?%?）?\s+"
        r"营业收入比上年增减（?%?）?\s+营业成本比上年增减（?%?）?\s+毛利率比上年增减（?%?）?",
        " ",
        section,
    )
    section = re.sub(
        r"(?:分行业|分产品|分地区|销售模式)\s+营业收入\s+营业成本\s+毛利率\s+"
        r"营业收入同比增减\s+毛利率同比增减",
        " ",
        section,
    )
    section = re.sub(
        r"(?:分行业|分产品|分地区|销售模式)"
        r"营业收入营业成本毛利率营业收入(?:比上年增减|同比增减)"
        r"(?:营业成本比上年增减)?毛利率(?:比上年增减|同比增减)",
        " ",
        section,
    )
    row_re = re.compile(
        rf"(?P<label>{_LABEL})\s+"
        rf"(?P<revenue>{_AMOUNT})\s+"
        rf"(?P<cost>{_AMOUNT})\s+"
        rf"(?P<gross_margin>{_RATE_WITH_OPTIONAL_PERCENT})\s+"
        rf"(?P<revenue_yoy>{_RATE_WITH_OPTIONAL_PERCENT})\s+"
        rf"(?P<cost_yoy>{_RATE_WITH_OPTIONAL_PERCENT})\s+"
        rf"(?P<gross_margin_delta>{_DELTA})"
    )
    for match in row_re.finditer(section):
        _append_metric_row(rows, match)
    if rows:
        return rows

    compact_row_re = re.compile(
        rf"(?P<label>{_LABEL})\s+"
        rf"(?P<revenue>{_AMOUNT})\s+"
        rf"(?P<cost>{_AMOUNT})\s+"
        rf"(?P<gross_margin>{_RATE_WITH_OPTIONAL_PERCENT})\s+"
        rf"(?P<revenue_yoy>{_RATE_WITH_OPTIONAL_PERCENT})\s+"
        rf"(?P<gross_margin_delta>{_DELTA})"
    )
    for match in compact_row_re.finditer(section):
        _append_metric_row(rows, match)
    return rows


def _append_metric_row(rows: List[Dict[str, Any]], match: re.Match[str]) -> None:
    label = _normalize_label(match.group("label"))
    if not label or any(token in label for token in ("主营业务", "营业收入", "毛利率", "单位")):
        return
    row = {
        "label": label,
        "revenue": _value_cell(match.group("revenue"), "元"),
        "cost": _value_cell(match.group("cost"), "元"),
        "gross_margin": _value_cell(match.group("gross_margin"), "%"),
        "revenue_yoy": _value_cell(match.group("revenue_yoy"), "%"),
        "cost_yoy": None,
        "gross_margin_delta": _value_cell(match.group("gross_margin_delta"), "pct"),
    }
    if "cost_yoy" in match.groupdict():
        row["cost_yoy"] = _value_cell(match.group("cost_yoy"), "%")
    rows.append(row)


def _parse_segment_table(text: str) -> List[Dict[str, Any]]:
    section = _section_between(
        text,
        ("主营业务分产品情况", "分产品"),
        ("主营业务分地区情况", "主营业务分销售模式情况", "产销量情况", "前五名客户", "(2)."),
    )
    rows = _parse_metric_rows_from_section(section)
    # If only an industry table exists, keep it as a conservative segment row.
    if not rows:
        section = _section_between(
            text,
            ("主营业务分行业情况", "分行业"),
            ("主营业务分产品情况", "主营业务分地区情况", "主营业务分销售模式情况", "产销量情况"),
        )
        rows = _parse_metric_rows_from_section(section)
    return rows


def _parse_region_or_sales_table(text: str, keyword: str) -> List[Dict[str, Any]]:
    if "地区" in keyword:
        end_markers = ("主营业务分销售模式情况", "产销量情况", "(2).")
        start_markers = ("主营业务分地区情况", "分地区")
    else:
        end_markers = ("产销量情况", "(2).")
        start_markers = ("主营业务分销售模式情况", "销售模式")
    section = _section_between(text, start_markers, end_markers)
    return _parse_metric_rows_from_section(section)


def _parse_inventory_table(text: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    section = _section_between(
        text,
        ("产销量情况分析表", "主要产品 单位 生产量 销售量 库存量"),
        ("产销量情况说明", "成本分析表", "公司前五名", "(3)."),
    )
    if not section:
        return rows
    section = re.sub(
        r"主要产品\s+单位\s+生产量\s+销售量\s+库存量\s+生产量比上年增减（?%?）?\s+"
        r"销售量比上年增减（?%?）?\s+库存量比上年增减（?%?）?",
        " ",
        section,
    )
    unit_re = r"万颗|KG|kg|吨|万件|台|件|米|个"
    row_re = re.compile(
        rf"(?P<label>{_LABEL})\s+"
        rf"(?P<unit>{unit_re})\s+"
        rf"(?P<production>{_AMOUNT})\s+"
        rf"(?P<sales>{_AMOUNT})\s+"
        rf"(?P<inventory>{_AMOUNT})\s+"
        rf"(?P<production_yoy>{_RATE})\s+"
        rf"(?P<sales_yoy>{_RATE})\s+"
        rf"(?P<inventory_yoy>{_RATE})"
    )
    for match in row_re.finditer(section):
        label = _normalize_label(match.group("label"))
        if not label or any(token in label for token in ("产销量", "主要产品", "库存量")):
            continue
        unit = match.group("unit")
        rows.append({
            "label": label,
            "quantity_unit": unit,
            "production_volume": _value_cell(match.group("production"), unit),
            "sales_volume": _value_cell(match.group("sales"), unit),
            "inventory_volume": _value_cell(match.group("inventory"), unit),
            "production_yoy": _value_cell(match.group("production_yoy"), "%"),
            "sales_yoy": _value_cell(match.group("sales_yoy"), "%"),
            "inventory_yoy": _value_cell(match.group("inventory_yoy"), "%"),
        })
    # Filter out rows that are clearly garbage (no numeric volumes).
    return [r for r in rows if r.get("production_volume") or r.get("sales_volume") or r.get("inventory_volume")]



def _parse_concentration(text: str, customer: bool = True) -> Dict[str, Any]:
    result = _empty_concentration()
    kind = "客户" if customer else "供应商"
    amount_keyword = "销售额" if customer else "采购额"
    compact_text = _clean_table_text(text)

    top_five_match = re.search(
        rf"前五名{kind}{amount_keyword}\s*([\d,\.]+)\s*([万亿元万]+)?\s*[，,；;]\s*占年度(?:销售|采购)总额\s*([\d\.]+)\s*%",
        compact_text,
    )
    if top_five_match:
        result["present"] = True
        result["headers_found"].append(f"前五名{kind}")
        result["top_five_amount"] = {
            "text": top_five_match.group(1),
            "unit": top_five_match.group(2),
            "normalized": _normalize_numeric(top_five_match.group(1) + (top_five_match.group(2) or "")),
        }
        result["top_five_percentage"] = {
            "text": top_five_match.group(3) + "%",
            "unit": "%",
            "normalized": _normalize_numeric(top_five_match.group(3) + "%"),
        }

    if not result["top_five_amount"]:
        total_match = re.search(
            rf"合计\s*/\s*([\d,\.]+)\s+([\d\.]+)\s*/",
            compact_text,
        )
        if total_match:
            result["present"] = True
            result["headers_found"].append(f"前五名{kind}")
            result["top_five_amount"] = {
                "text": total_match.group(1),
                "unit": "万元",
                "normalized": _normalize_numeric(total_match.group(1) + "万元"),
            }
            result["top_five_percentage"] = {
                "text": total_match.group(2) + "%",
                "unit": "%",
                "normalized": _normalize_numeric(total_match.group(2) + "%"),
            }

    if not result["top_five_percentage"]:
        top_five_pct_match = re.search(
            rf"前五名{kind}{amount_keyword}?占年度(?:销售|采购)总额\s*([\d\.]+)\s*%",
            compact_text,
        )
        if top_five_pct_match:
            result["present"] = True
            result["headers_found"].append(f"前五名{kind}")
            result["top_five_percentage"] = {
                "text": top_five_pct_match.group(1) + "%",
                "unit": "%",
                "normalized": _normalize_numeric(top_five_pct_match.group(1) + "%"),
            }

    largest_match = re.search(
        rf"\b1\s+{kind}\s*[一二三四五A]?\s+([\d,\.]+)\s+([\d\.]+)",
        compact_text,
    )
    if largest_match:
        result["present"] = True
        if f"前五名{kind}" not in result["headers_found"]:
            result["headers_found"].append(f"前五名{kind}")
        result["largest_amount"] = {
            "text": largest_match.group(1),
            "unit": result["top_five_amount"]["unit"] if result["top_five_amount"] else None,
            "normalized": _normalize_numeric(largest_match.group(1) + (result["top_five_amount"]["unit"] if result["top_five_amount"] else "")),
        }
        result["largest_percentage"] = {
            "text": largest_match.group(2) + "%",
            "unit": "%",
            "normalized": _normalize_numeric(largest_match.group(2) + "%"),
        }
    elif customer:
        largest_pct_match = re.search(r"第一大客户占比\s*([\d\.]+)\s*%", compact_text)
        if largest_pct_match:
            result["present"] = True
            if f"前五名{kind}" not in result["headers_found"]:
                result["headers_found"].append(f"前五名{kind}")
            result["largest_percentage"] = {
                "text": largest_pct_match.group(1) + "%",
                "unit": "%",
                "normalized": _normalize_numeric(largest_pct_match.group(1) + "%"),
            }

    related_match = re.search(
        rf"其中前五名{kind}{amount_keyword}中关联方{amount_keyword}\s*([\d,\.]+)\s*([万亿元万]+)?\s*[，,；;]\s*占年度(?:销售|采购)总额\s*([\d\.]+)\s*%",
        compact_text,
    )
    if related_match:
        result["related_party_amount"] = {
            "text": related_match.group(1),
            "unit": related_match.group(2),
            "normalized": _normalize_numeric(related_match.group(1) + (related_match.group(2) or "")),
        }
        result["related_party_percentage"] = {
            "text": related_match.group(3) + "%",
            "unit": "%",
            "normalized": _normalize_numeric(related_match.group(3) + "%"),
        }

    return result


# ---------------------------------------------------------------------------
# Extraction dispatch
# ---------------------------------------------------------------------------


def _blocks_for_usages(blocks: List[Dict[str, Any]], *usages: str) -> List[Dict[str, Any]]:
    selected = [block for block in blocks if block and block.get("usage") in usages]
    return selected


def _fallback_blocks_with(text_blocks: List[Dict[str, Any]], *markers: str) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for block in text_blocks:
        text = str(block.get("text", ""))
        if any(marker in text for marker in markers):
            selected.append(block)
    return selected


def _dedupe_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    seen = set()
    for block in blocks:
        marker = block.get("id") or id(block)
        if marker in seen:
            continue
        seen.add(marker)
        selected.append(block)
    return selected


def _parse_from_blocks(
    blocks: List[Dict[str, Any]],
    parser,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    for block in blocks:
        source_text = str(block.get("text", ""))
        rows = parser(source_text)
        if rows:
            return rows, block, source_text
    source_text = "\n\n".join(str(block.get("text", "")) for block in blocks)
    return parser(source_text), (blocks[0] if blocks else None), source_text


def _extract_segment_rows(text: str, source_block_ids: List[str], blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = _blocks_for_usages(blocks, "segment_margin_table", "segment_table")
    candidates = _dedupe_blocks(candidates + _fallback_blocks_with(blocks, "主营业务分产品情况", "分产品"))
    if not candidates:
        candidates = [{"id": "", "usage": "", "text": text}]
    rows, block, source_text = _parse_from_blocks(candidates, _parse_segment_table)
    block_id, usage, excerpt = _source_info([block] if block else blocks, source_text)
    for row in rows:
        row["source_block_id"] = block_id
        row["source_usage"] = usage
        row["source_excerpt"] = excerpt
    return rows


def _extract_region_rows(text: str, source_block_ids: List[str], blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = _blocks_for_usages(blocks, "region_table", "segment_margin_table", "segment_table")
    candidates = _dedupe_blocks(candidates + _fallback_blocks_with(blocks, "主营业务分地区情况", "分地区"))
    if not candidates:
        candidates = [{"id": "", "usage": "", "text": text}]
    rows, block, source_text = _parse_from_blocks(
        candidates, lambda value: _parse_region_or_sales_table(value, "主营业务分地区情况")
    )
    block_id, usage, excerpt = _source_info([block] if block else blocks, source_text)
    for row in rows:
        row["source_block_id"] = block_id
        row["source_usage"] = usage
        row["source_excerpt"] = excerpt
    return rows


def _extract_sales_mode_rows(text: str, source_block_ids: List[str], blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = _blocks_for_usages(blocks, "segment_margin_table", "segment_table")
    candidates = _dedupe_blocks(candidates + _fallback_blocks_with(blocks, "主营业务分销售模式情况", "销售模式"))
    if not candidates:
        candidates = [{"id": "", "usage": "", "text": text}]
    rows, block, source_text = _parse_from_blocks(
        candidates, lambda value: _parse_region_or_sales_table(value, "主营业务分销售模式情况")
    )
    block_id, usage, excerpt = _source_info([block] if block else blocks, source_text)
    for row in rows:
        row["source_block_id"] = block_id
        row["source_usage"] = usage
        row["source_excerpt"] = excerpt
    return rows


def _extract_inventory_rows(text: str, source_block_ids: List[str], blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = _blocks_for_usages(blocks, "production_sales_inventory_table")
    candidates = _dedupe_blocks(candidates + _fallback_blocks_with(blocks, "产销量情况", "库存量"))
    if not candidates:
        candidates = [{"id": "", "usage": "", "text": text}]
    rows, block, source_text = _parse_from_blocks(candidates, _parse_inventory_table)
    block_id, usage, excerpt = _source_info([block] if block else blocks, source_text)
    for row in rows:
        row["source_block_id"] = block_id
        row["source_usage"] = usage
        row["source_excerpt"] = excerpt
    return rows


def _extract_customer_concentration(text: str, source_block_ids: List[str], blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    candidates = _blocks_for_usages(blocks, "customer_supplier_table", "supplier_concentration_table")
    candidates = _dedupe_blocks(candidates + _fallback_blocks_with(blocks, "前五名客户", "公司前五名客户"))
    block = candidates[0] if candidates else None
    source_text = "\n\n".join(str(candidate.get("text", "")) for candidate in candidates) if candidates else text
    result = _parse_concentration(source_text, customer=True)
    if block:
        result["source_block_id"] = block.get("id")
        result["source_usage"] = block.get("usage")
        result["source_excerpt"] = _excerpt(source_text)
    return result


def _extract_supplier_concentration(text: str, source_block_ids: List[str], blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    candidates = _blocks_for_usages(blocks, "supplier_concentration_table", "customer_supplier_table")
    candidates = _dedupe_blocks(candidates + _fallback_blocks_with(blocks, "前五名供应商", "公司前五名供应商"))
    block = candidates[0] if candidates else None
    source_text = "\n\n".join(str(candidate.get("text", "")) for candidate in candidates) if candidates else text
    result = _parse_concentration(source_text, customer=False)
    if block:
        result["source_block_id"] = block.get("id")
        result["source_usage"] = block.get("usage")
        result["source_excerpt"] = _excerpt(source_text)
    return result


# ---------------------------------------------------------------------------
# Normalized values and table presence
# ---------------------------------------------------------------------------


def _add_value(values: List[str], cell: Optional[Dict[str, Any]]) -> None:
    if cell and cell.get("normalized"):
        values.append(str(cell["normalized"]))


def _collect_normalized_values(
    segment_rows: List[Dict[str, Any]],
    region_rows: List[Dict[str, Any]],
    sales_mode_rows: List[Dict[str, Any]],
    inventory_rows: List[Dict[str, Any]],
    customer_concentration: Dict[str, Any],
    supplier_concentration: Dict[str, Any],
) -> List[str]:
    values: List[str] = []
    for row in segment_rows + region_rows + sales_mode_rows + inventory_rows:
        for key in row:
            if key.startswith("source_") or key == "label" or key == "quantity_unit":
                continue
            _add_value(values, row[key])
    for key in ("top_five_amount", "top_five_percentage", "largest_amount", "largest_percentage", "related_party_amount", "related_party_percentage"):
        _add_value(values, customer_concentration.get(key))
        _add_value(values, supplier_concentration.get(key))
    return values


def _build_table_presence(
    text: str,
    segment_rows: List[Dict[str, Any]],
    region_rows: List[Dict[str, Any]],
    sales_mode_rows: List[Dict[str, Any]],
    inventory_rows: List[Dict[str, Any]],
    customer_concentration: Dict[str, Any],
    supplier_concentration: Dict[str, Any],
    source_block_ids: List[str],
) -> Dict[str, Any]:
    tables = _empty_tables()

    if "主营业务分产品情况" in text or "主营业务分行业情况" in text:
        tables["segment_margin"]["headers_found"].append("主营业务分产品情况" if "主营业务分产品情况" in text else "主营业务分行业情况")
        tables["segment_margin"]["present"] = True
        tables["segment_margin"]["row_count"] = len(segment_rows)
    if "主营业务分地区情况" in text:
        tables["region"]["headers_found"].append("主营业务分地区情况")
        tables["region"]["present"] = True
        tables["region"]["row_count"] = len(region_rows)
    if "主营业务分销售模式情况" in text:
        tables["sales_mode"]["headers_found"].append("主营业务分销售模式情况")
        tables["sales_mode"]["present"] = True
        tables["sales_mode"]["row_count"] = len(sales_mode_rows)
    if "产销量情况" in text:
        tables["inventory"]["headers_found"].append("产销量情况分析表")
        tables["inventory"]["present"] = True
        tables["inventory"]["row_count"] = len(inventory_rows)
    if "前五名客户" in text or "公司前五名客户" in text:
        tables["customer_supplier"]["headers_found"].append("前五名客户")
        tables["customer_supplier"]["present"] = True
        cs_rows = (1 if customer_concentration["present"] else 0) + (1 if supplier_concentration["present"] else 0)
        tables["customer_supplier"]["row_count"] = cs_rows

    tables["segment_margin"]["source_block_ids"] = _row_source_ids(segment_rows)
    tables["region"]["source_block_ids"] = _row_source_ids(region_rows)
    tables["sales_mode"]["source_block_ids"] = _row_source_ids(sales_mode_rows)
    tables["inventory"]["source_block_ids"] = _row_source_ids(inventory_rows)
    customer_supplier_ids = []
    for concentration in (customer_concentration, supplier_concentration):
        block_id = concentration.get("source_block_id")
        if block_id and block_id not in customer_supplier_ids:
            customer_supplier_ids.append(block_id)
    tables["customer_supplier"]["source_block_ids"] = customer_supplier_ids

    return tables


def _row_source_ids(rows: List[Dict[str, Any]]) -> List[str]:
    ids: List[str] = []
    for row in rows:
        block_id = row.get("source_block_id")
        if block_id and block_id not in ids:
            ids.append(str(block_id))
    return ids
