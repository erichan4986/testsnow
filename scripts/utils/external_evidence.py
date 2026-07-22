"""Exact units, family taxonomy and deterministic external-evidence admission."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

EVIDENCE_UNIT_SCHEMA = "curated_external_evidence_unit.v2"
EVIDENCE_TAXONOMY_VERSION = "external_family_taxonomy.v1"

EXTERNAL_FAMILY_TITLES = {
    "demand_customer": "需求与客户", "commercialization": "商业化进展",
    "technology_product": "技术与产品", "financial_quality": "财务质量",
    "competitive_landscape": "竞争格局", "capacity_delivery": "供应链与交付",
    "policy_geopolitics": "政策与地缘", "valuation_expectation": "估值与预期",
}
EXTERNAL_DISPLAY_TOPIC_ORDER = tuple(EXTERNAL_FAMILY_TITLES.values())
EXTERNAL_FAMILY_ORDER = (
    "financial_quality", "technology_product", "commercialization", "competitive_landscape",
    "demand_customer", "capacity_delivery", "policy_geopolitics", "valuation_expectation",
)

_FAMILY_RULES = (
    ("financial_quality", ("财务", "营收", "收入", "利润", "毛利", "费用", "现金流", "业绩")),
    ("technology_product", ("技术", "产品", "fpga", "cpo", "npo", "xpo", "硅光", "芯片", "mcu", "自研")),
    ("commercialization", ("商业化", "量产", "认证", "验证", "导入", "定点", "出货", "送样")),
    ("competitive_landscape", ("竞争", "同业", "格局", "份额", "市占率", "市场份额", "领先")),
    ("demand_customer", ("客户", "需求", "订单", "资本开支", "capex")),
    ("capacity_delivery", ("供应链", "交付", "产能", "物料", "原材料", "预付款", "瓶颈")),
    ("policy_geopolitics", ("政策", "制裁", "管制", "清单", "地缘")),
    ("valuation_expectation", ("估值", "市值", "股价", "pe", "预期差", "情景", "催化")),
)
_SENTENCE_RE = re.compile(r"[^。！？；!?;]+[。！？；!?;]|[^。！？；!?;]+$")
_ARGUMENT_RE = re.compile(
    r"增长|下降|改善|承压|加剧|回升|领先|第一|达到|占比|成为|支持|提供|完成|具备|实现|形成|演进|"
    r"应用于|展出|主营|覆盖|依托|接到|拥有|发布|推出|量产|交付|扩产|合作|收购|不存在|未出现|"
    r"没有(?:明显)?(?:的)?瓶颈|催化|影响有限|更高|更低|强劲|紧张"
)


def materialize_external_evidence_units(document: Mapping[str, Any]) -> list[dict]:
    """Split narrative blocks into exact, ordered source units without rewriting text."""
    if not isinstance(document, Mapping):
        return []
    result = []
    for block in document.get("blocks") or []:
        if not isinstance(block, Mapping) or block.get("block_kind") != "narrative":
            continue
        text = str(block.get("text") or "")
        for ordinal, match in enumerate(_SENTENCE_RE.finditer(text)):
            value = match.group(0).strip()
            if not value:
                continue
            start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            end = start + len(value)
            unit_hash = _hash(value)
            result.append({
                "schema_version": EVIDENCE_UNIT_SCHEMA,
                "unit_id": f"external-unit:{document.get('source_id')}:{block.get('block_ordinal')}:{ordinal}:{unit_hash[-16:]}",
                "source_id": str(document.get("source_id") or ""),
                "document_hash": str(document.get("document_hash") or ""),
                "block_id": str(block.get("block_id") or ""),
                "block_ordinal": int(block.get("block_ordinal") or 0),
                "unit_ordinal": ordinal,
                "start": start, "end": end, "text": value, "unit_hash": unit_hash,
                "block_hash": str(block.get("block_hash") or ""),
                "coverage_families": external_coverage_families(value),
                "argument_status": argument_status(value),
            })
    return result


def external_coverage_families(text: Any) -> list[str]:
    value = str(text or "").lower()
    return [family for family, terms in _FAMILY_RULES if any(term.lower() in value for term in terms)]


def external_family_title(family: Any, fallback: str = "外部变量") -> str:
    return EXTERNAL_FAMILY_TITLES.get(str(family or ""), fallback)


def argument_status(text: Any) -> str:
    """Return a stable admission reason for one exact evidence sentence."""
    value = str(text or "").strip()
    if not value or not value.endswith(("。", "！", "？", "；", ";")):
        return "incomplete"
    if not external_coverage_families(value):
        return "unclassified"
    return "admitted" if _ARGUMENT_RE.search(value) or re.search(r"\d", value) else "incomplete"


def validate_external_evidence_unit(unit: Mapping[str, Any], document: Mapping[str, Any]) -> dict:
    """Verify that one unit is an immutable substring of its canonical block."""
    if not isinstance(unit, Mapping) or unit.get("schema_version") != EVIDENCE_UNIT_SCHEMA:
        return _result("invalid", "schema_version")
    blocks = {str(block.get("block_id") or ""): block for block in document.get("blocks") or [] if isinstance(block, Mapping)}
    block = blocks.get(str(unit.get("block_id") or ""))
    if not isinstance(block, Mapping) or unit.get("document_hash") != document.get("document_hash"):
        return _result("invalid", "document_reference")
    text, start, end = unit.get("text"), unit.get("start"), unit.get("end")
    source = str(block.get("text") or "")
    if not isinstance(text, str) or not isinstance(start, int) or not isinstance(end, int):
        return _result("invalid", "unit_shape")
    if not 0 <= start < end <= len(source) or source[start:end] != text:
        return _result("invalid", "unit_offset")
    if unit.get("unit_hash") != _hash(text) or unit.get("block_hash") != block.get("block_hash"):
        return _result("invalid", "unit_hash")
    expected = next((
        row for row in materialize_external_evidence_units(document)
        if row.get("unit_id") == unit.get("unit_id")
    ), None)
    fields = (
        "source_id", "document_hash", "block_id", "block_ordinal", "unit_ordinal",
        "start", "end", "text", "unit_hash", "block_hash", "coverage_families", "argument_status",
    )
    if expected is None or any(unit.get(field) != expected.get(field) for field in fields):
        return _result("invalid", "unit_identity")
    return _result("ok", "")


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _result(status: str, reason: str) -> dict:
    return {"status": status, "reason": reason}
