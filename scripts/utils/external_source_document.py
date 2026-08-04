"""Canonical, paragraph-preserving external source documents."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

SOURCE_DOCUMENT_SCHEMA = "curated_external_source_document.v1"
SOURCE_DOCUMENT_NORMALIZATION_VERSION = "external_source_document.v1"

_HEADING_RE = re.compile(r"^(?:[一二三四五六七八九十]+[、.]|\d+[、.)]|[（(][一二三四五六七八九十\d]+[）)])")
_NOISE_MARKERS = ("免责声明", "风险提示", "本文不构成投资建议", "点击上方", "关注公众号", "阅读原文")
_COMPARISON_RE = re.compile(r"对比|比较|谁领先|\bvs\b", re.IGNORECASE)


def build_external_source_document(packet: Mapping[str, Any]) -> dict:
    """Return one immutable source document without collapsing paragraph boundaries."""
    raw = str(packet.get("content") or "")
    blocks, canonical_parts, cursor, noise_tail = [], [], 0, False
    for ordinal, value in enumerate(_paragraphs(raw)):
        kind = "structural_noise" if noise_tail or _is_noise(value) else _block_kind(value)
        noise_tail = noise_tail or _is_noise(value)
        start = cursor
        canonical_parts.append(value)
        cursor += len(value)
        blocks.append({
            "block_id": f"{_clean(packet.get('source_id'))}:block:{ordinal}",
            "block_ordinal": ordinal, "block_kind": kind, "text": value,
            "start": start, "end": cursor, "block_hash": _hash(value),
        })
        cursor += 2
    canonical = "\n\n".join(canonical_parts)
    comparable = _is_comparative(str(packet.get("title") or ""), str(packet.get("stock_name") or ""), blocks)
    narratives = sum(block["block_kind"] == "narrative" for block in blocks)
    boundary = "scope_input_degraded" if comparable and narratives <= 1 else "preserved"
    return {
        "schema_version": SOURCE_DOCUMENT_SCHEMA,
        "normalization_version": SOURCE_DOCUMENT_NORMALIZATION_VERSION,
        "source_id": _clean(packet.get("source_id")),
        "stock_name": _clean(packet.get("stock_name")),
        "title": _clean(packet.get("title")),
        "account": _clean(packet.get("account")),
        "publish_time": _clean(packet.get("publish_time")),
        "source_kind": _clean(packet.get("source_kind")),
        "source_ref": _clean(packet.get("source_ref")),
        "source_url": _clean(packet.get("source_url")),
        "raw_content_hash": _hash(raw),
        "canonical_text": canonical,
        "document_hash": _hash(canonical),
        "boundary_status": boundary,
        "blocks": blocks,
    }


def validate_external_source_document(document: Mapping[str, Any]) -> dict:
    """Fail closed when source/document/block identity cannot be reconstructed."""
    if not isinstance(document, Mapping) or document.get("schema_version") != SOURCE_DOCUMENT_SCHEMA:
        return _result("invalid", "schema_version")
    canonical = document.get("canonical_text")
    blocks = document.get("blocks")
    if not isinstance(canonical, str) or not isinstance(blocks, list):
        return _result("invalid", "document_shape")
    if document.get("document_hash") != _hash(canonical):
        return _result("invalid", "document_hash")
    if canonical != "\n\n".join(
        str(block.get("text") or "") for block in blocks if isinstance(block, Mapping)
    ):
        return _result("invalid", "block_sequence")
    noise_tail = False
    for ordinal, block in enumerate(blocks):
        if not isinstance(block, Mapping) or block.get("block_ordinal") != ordinal:
            return _result("invalid", "block_ordinal")
        text, start, end = block.get("text"), block.get("start"), block.get("end")
        if not isinstance(text, str) or not isinstance(start, int) or not isinstance(end, int):
            return _result("invalid", "block_shape")
        if not 0 <= start < end <= len(canonical) or canonical[start:end] != text:
            return _result("invalid", "block_offset")
        if block.get("block_hash") != _hash(text):
            return _result("invalid", "block_hash")
        expected_kind = "structural_noise" if noise_tail or _is_noise(text) else _block_kind(text)
        if block.get("block_kind") != expected_kind:
            return _result("invalid", "block_kind")
        noise_tail = noise_tail or _is_noise(text)
    expected_boundary = "scope_input_degraded" if (
        _is_comparative(str(document.get("title") or ""), str(document.get("stock_name") or ""), blocks)
        and sum(block.get("block_kind") == "narrative" for block in blocks) <= 1
    ) else "preserved"
    if document.get("boundary_status") != expected_boundary:
        return _result("invalid", "boundary_status")
    if expected_boundary == "scope_input_degraded":
        return _result("invalid", "scope_input_degraded")
    return _result("ok", "")


def is_comparative_external_document(document: Mapping[str, Any], *, stock_name: str) -> bool:
    """Return whether a source's title or headings explicitly announce a comparison."""
    return _is_comparative(
        str(document.get("title") or ""),
        str(stock_name or ""),
        document.get("blocks") or [],
    )


def _paragraphs(raw: str) -> list[str]:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    return [value for value in (_normalize_paragraph(part) for part in re.split(r"\n\s*\n+", normalized)) if value]


def _normalize_paragraph(value: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _block_kind(text: str) -> str:
    return "heading" if _HEADING_RE.match(text) or (len(text) <= 48 and not text.endswith(("。", "！", "？", "；"))) else "narrative"


def _is_noise(text: str) -> bool:
    return any(marker in text for marker in _NOISE_MARKERS)


def _is_comparative(title: str, stock: str, blocks: Iterable[Mapping[str, Any]]) -> bool:
    title, stock = _clean(title), _clean(stock)
    headings = [str(block.get("text") or "") for block in blocks if block.get("block_kind") == "heading"]
    return bool(stock and any(stock in value and _COMPARISON_RE.search(value) for value in (title, *headings)))


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _result(status: str, reason: str) -> dict:
    return {"status": status, "reason": reason}
