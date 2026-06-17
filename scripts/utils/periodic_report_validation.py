"""Shared validation helpers for periodic-report LLM outputs."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


_CITATION_RE = re.compile(r"\[\^?\w+\]")
_URL_RE = re.compile(r"https?://\S+")
_REPEATED_SPACE_RE = re.compile(r"\s+")


def has_citation_markers(text: str) -> bool:
    return bool(_CITATION_RE.search(text))


def has_raw_url(text: str) -> bool:
    return bool(_URL_RE.search(text))


def normalize_confidence(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        confidence = value
    else:
        try:
            confidence = int(value)
        except (TypeError, ValueError):
            return None
    if confidence < 0 or confidence > 100:
        return None
    return confidence


def sanitize_text(text: str) -> str:
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _REPEATED_SPACE_RE.sub(" ", text)
    return text.strip()


def check_fidelity(summary: str, refs: List[str], item_map: Dict[str, Any]) -> bool:
    """Return True if summary numbers/entities are grounded in refs."""
    evidence_text = "\n".join(_ref_text(ref, item_map) for ref in refs)
    evidence_text = _normalize_for_fidelity(evidence_text)
    summary_norm = _normalize_for_fidelity(summary)

    contextual_years = _extract_contextual_years(summary_norm)

    for number, raw in _extract_numbers(summary_norm):
        if raw in contextual_years:
            continue
        if _number_supported_by_evidence(number, raw, evidence_text):
            continue
        if _is_derived_growth_rate(raw, refs, item_map):
            continue
        return False

    for entity in _extract_entities(summary_norm):
        if entity not in evidence_text:
            return False

    return True


def _ref_text(ref: str, item_map: Dict[str, Any]) -> str:
    block = item_map.get(ref) or {}
    parts = [
        str(block.get("section", "")),
        str(block.get("title", "")),
        str(block.get("text", "")),
    ]
    return "\n".join(parts)


def _normalize_for_fidelity(text: str) -> str:
    text = text.replace(",", "")
    text = re.sub(r"\s+", "", text)
    return _normalize_units(text)


def _normalize_units(text: str) -> str:
    text = re.sub(r"(-?[\d\.]+)\s*亿元", lambda m: _convert_yuan(m.group(1), 100_000_000), text)
    text = re.sub(r"(-?[\d\.]+)\s*万元", lambda m: _convert_yuan(m.group(1), 10_000), text)
    return text


def _convert_yuan(raw: str, multiplier: int) -> str:
    number = _parse_number(raw)
    if number is None:
        return raw
    return str(int(round(number * multiplier)))


def _extract_numbers(text: str) -> List[Tuple[Optional[float], str]]:
    results: List[Tuple[Optional[float], str]] = []
    for match in re.finditer(r"-?\d+(?:\.\d+)?(?:%|pct|个百分点)?", text):
        prev_char = text[match.start() - 1] if match.start() > 0 else ""
        next_char = text[match.end()] if match.end() < len(text) else ""
        if _is_model_code_neighbor(prev_char) or _is_model_code_neighbor(next_char):
            continue
        raw = match.group(0)
        number = _parse_number(raw.replace("%", "").replace("pct", "").replace("个百分点", ""))
        results.append((number, raw))
    return results


def _is_model_code_neighbor(char: str) -> bool:
    return bool(char and re.match(r"[A-Za-z]", char))


def _number_supported_by_evidence(
    number: Optional[float],
    raw: str,
    evidence_text: str,
) -> bool:
    if number is None:
        return False
    if raw in evidence_text or str(number) in evidence_text:
        return True
    if "%" in raw or "pct" in raw or "个百分点" in raw:
        return False
    if abs(number) < 10_000:
        return False
    for evidence_number, _ in _extract_numbers(evidence_text):
        if evidence_number is None or abs(evidence_number) < 10_000:
            continue
        tolerance = max(10_000.0, abs(evidence_number) * 0.01)
        if abs(evidence_number - number) <= tolerance:
            return True
    return False


def _extract_contextual_years(text: str) -> List[str]:
    years = set()
    for match in re.finditer(r"20\d{2}\s*(?:年|年度|财年)?", text):
        years.add(match.group(0).replace(" ", ""))
        years.add(match.group(0)[:4])
    return list(years)


def _extract_entities(text: str) -> List[str]:
    entities: List[str] = []
    predicate_chars = set("占高较风险的是为达约等主来源合计销售收入贡献订单来看向及与在")
    pattern = re.compile(
        r"(?:客户|产品|供应商)\s*(?:[是为叫]?[：:]?)?"
        r"([一-鿿A-Za-z0-9（）()]{1,8}?)"
        r"(?=\s*(?:占比|销售|收入|订单|贡献|合计|的|是|为|达|约|分别|主要|等|，|。|；|！|？|$))"
    )
    for match in pattern.finditer(text):
        entity = match.group(1)
        if any(ch in predicate_chars for ch in entity):
            continue
        entities.append(entity)
    return entities


def _is_derived_growth_rate(raw: str, refs: List[str], item_map: Dict[str, Any]) -> bool:
    if "%" not in raw and "pct" not in raw and "百分点" not in raw:
        return False
    value = _parse_number(raw.replace("%", "").replace("pct", "").replace("个百分点", ""))
    if value is None:
        return False
    evidence_text = "\n".join(_ref_text(ref, item_map) for ref in refs)
    evidence_text = _normalize_for_fidelity(evidence_text)
    numbers = []
    for match in re.finditer(r"-?[\d\.]+(?:%|pct|个百分点)?", evidence_text):
        n = _parse_number(match.group(0).replace("%", "").replace("pct", "").replace("个百分点", ""))
        if n is not None and abs(n) < 1_000_000_000_000:
            numbers.append(n)
    for i, a in enumerate(numbers):
        for b in numbers[i + 1 :]:
            if b == 0:
                continue
            derived = (a - b) / abs(b) * 100
            if abs(derived - value) < 0.5:
                return True
    return False


def _parse_number(value: str) -> Optional[float]:
    try:
        cleaned = str(value).replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return float(cleaned)
    except (TypeError, ValueError):
        return None
