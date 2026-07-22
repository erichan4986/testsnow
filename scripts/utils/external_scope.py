"""Deterministic scope ownership for canonical external evidence units."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

try:
    from .external_evidence import materialize_external_evidence_units
    from .external_source_document import is_comparative_external_document
except ImportError:
    from external_evidence import materialize_external_evidence_units
    from external_source_document import is_comparative_external_document

SCOPE_PROVENANCE_SCHEMA = "curated_external_scope_provenance.v2"
SCOPE_RESOLVER_VERSION = "external_scope_resolver.v2"

_INDUSTRY_RE = re.compile(
    r"^(?:\d{4}年)?(?:(?:全球|中国|国内|海外|高端)[^，。；]{0,16}(?:行业|市场)|"
    r"行业|市场|产业|供给|需求|厂商|供应链|同业|竞争格局|整体)"
)
_COMPANY_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9·]{2,16}(?:股份有限公司|有限责任公司|有限公司|科技|股份|集团|微电))"
)
_RELATION_ENTITY_RE = re.compile(
    r"(?:竞争对手|同行|同业|供应商|合作方|合作伙伴)\s*"
    r"(?P<actor>[\u4e00-\u9fffA-Za-z0-9]{2,16}?)(?=宣布|发布|推出|量产|验证|导入|交付|扩产|投产|合作|收购|称|表示)"
    r"|(?:与|同|和)(?P<partner>[\u4e00-\u9fffA-Za-z0-9]{2,16}?)(?=合作|联合|携手|共同开发|共同推进)"
)
_TITLE_PEER_RE = re.compile(
    r"(?:与|和|及)(?P<peer>[\u4e00-\u9fffA-Za-z0-9]{2,16}?)(?=技术|产品|能力|对比|比较|谁领先|竞争|$)"
)
_ACTOR_RE = re.compile(
    r"^(?P<actor>[\u4e00-\u9fffA-Za-z0-9·]{2,24}?)(?=宣布|发布|推出|量产|验证|导入|交付|扩产|投产|合作|收购|称|表示)"
)
_NON_ENTITY_ACTOR_RE = re.compile(
    r"^(?:能|可|已|将|正在|仍|还|需|应|有望)(?:够|大批量|批量|规模化|进一步|逐步|持续|正式|直接|开始|加快)|"
    r"\d{4}年|战略|芯片|系列|产品|平台|方向|市场|行业|全球|中国|预计|实现|成为|当前|目前|支持|提供|搭载|进入|[A-Za-z]+\d{2,}"
)
_COMPARE_RE = re.compile(r"相比|相较|与[^，。；]{1,24}相比|优于|低于|高于")
_COOPERATION_RE = re.compile(r"(?:与|同|和)[^，。；]{2,16}(?:合作|联合|携手|共同开发|共同推进)")
_GENERIC_SURFACES = {"公司", "本公司", "该公司", "行业", "市场", "产品", "客户", "管理层", "供应链", "整体"}
_NON_ENTITY_PARTS = ("公司", "产品", "客户", "行业", "市场", "供应链", "其", "本", "该")


def resolve_external_scope(
    document: Mapping[str, Any], *, stock_name: str, aliases: Sequence[str] = (),
) -> list[dict]:
    """Attach one reconstructable target/peer/industry provenance object per unit."""
    target_aliases = tuple(dict.fromkeys(value for value in (stock_name, *aliases) if value))
    units = materialize_external_evidence_units(document)
    peer_inventory = _document_peer_inventory(document, target_aliases)
    by_block: dict[str, list[dict]] = {}
    for unit in units:
        by_block.setdefault(str(unit["block_id"]), []).append(unit)
    target_centric = _target_centric(document, target_aliases)
    for members in by_block.values():
        primary_owner, primary_surface = _block_primary_owner(members, target_aliases, peer_inventory)
        for unit in members:
            unit["scope_provenance"] = _unit_scope(
                unit, target_aliases, peer_inventory, target_centric, primary_owner, primary_surface, document,
            )
    return units


def validate_scope_provenance(unit: Mapping[str, Any], document: Mapping[str, Any], *, stock_name: str) -> dict:
    """Reconstruct one scope result from the canonical document without trusting stored fields."""
    expected = resolve_external_scope(document, stock_name=stock_name)
    match = next((row for row in expected if row.get("unit_id") == unit.get("unit_id")), None)
    if match is None or unit.get("scope_provenance") != match.get("scope_provenance"):
        return {"status": "invalid", "reason": "scope_provenance"}
    return {"status": "ok", "reason": ""}


def _unit_scope(
    unit: Mapping[str, Any], aliases: tuple[str, ...], peer_inventory: tuple[str, ...], target_centric: bool,
    primary_owner: str, primary_surface: str, document: Mapping[str, Any],
) -> dict:
    text = str(unit.get("text") or "")
    target = _target_surface(text, aliases)
    peer = _peer_surface(text, aliases, peer_inventory)
    relation = _COMPARE_RE.search(text) or _COOPERATION_RE.search(text)
    if peer and relation and (target or primary_owner == "target" or target_centric):
        return _provenance("target_peer_relation", peer, "explicit_relation", peer, unit, document)
    if target:
        return _provenance("explicit_target", target, "explicit_target_surface", target, unit, document)
    if peer:
        return _provenance("explicit_peer", peer, "explicit_peer_surface", peer, unit, document)
    if _INDUSTRY_RE.match(text):
        return _provenance("industry_context", "", "industry_subject", _INDUSTRY_RE.match(text).group(0), unit, document)
    if primary_owner == "peer":
        return _provenance("explicit_peer", primary_surface, "block_primary_owner", primary_surface, unit, document)
    if primary_owner == "target" or target_centric:
        return _provenance("target_document_context", aliases[0] if aliases else "", "document_or_block_owner", aliases[0] if aliases else "", unit, document)
    return _provenance("ambiguous", "", "none", "", unit, document)


def _block_primary_owner(
    units: list[dict], aliases: tuple[str, ...], peer_inventory: tuple[str, ...],
) -> tuple[str, str]:
    for unit in units:
        text = str(unit.get("text") or "")
        if target := _target_surface(text, aliases):
            return "target", target
        if peer := _peer_surface(text, aliases, peer_inventory):
            return "peer", peer
    return "", ""


def _target_centric(document: Mapping[str, Any], aliases: tuple[str, ...]) -> bool:
    title = str(document.get("title") or "")
    return bool(
        _target_surface(title, aliases)
        and not is_comparative_external_document(document, stock_name=aliases[0] if aliases else "")
    )


def _target_surface(text: str, aliases: tuple[str, ...]) -> str:
    return next((alias for alias in aliases if alias and alias in text), "")


def _peer_surface(text: str, aliases: tuple[str, ...], peer_inventory: tuple[str, ...]) -> str:
    if relation := _RELATION_ENTITY_RE.search(text):
        value = relation.group("actor") or relation.group("partner")
        if value not in aliases:
            return value
    for value in peer_inventory:
        if value in text:
            return value
    for value in _COMPANY_RE.findall(text):
        if value not in aliases:
            return value
    if actor := _ACTOR_RE.search(text):
        value = actor.group("actor")
        if (
            value not in aliases
            and value not in _GENERIC_SURFACES
            and not any(part in value for part in _NON_ENTITY_PARTS)
            and not _NON_ENTITY_ACTOR_RE.search(value)
        ):
            return value
    return ""


def _document_peer_inventory(document: Mapping[str, Any], aliases: tuple[str, ...]) -> tuple[str, ...]:
    if not aliases or not is_comparative_external_document(document, stock_name=aliases[0]):
        return ()
    values = []
    for value in [str(document.get("title") or ""), *(
        str(block.get("text") or "")
        for block in document.get("blocks") or []
        if isinstance(block, Mapping) and block.get("block_kind") == "heading"
    )]:
        for match in _TITLE_PEER_RE.finditer(value):
            peer = match.group("peer")
            if peer not in aliases and peer not in _GENERIC_SURFACES:
                values.append(peer)
    return tuple(dict.fromkeys(values))


def _provenance(
    origin: str, surface: str, anchor_type: str, anchor_value: str,
    unit: Mapping[str, Any], document: Mapping[str, Any],
) -> dict:
    return {
        "schema_version": SCOPE_PROVENANCE_SCHEMA,
        "resolver_version": SCOPE_RESOLVER_VERSION,
        "origin": origin,
        "owner_surface": surface,
        "anchor_type": anchor_type,
        "anchor_value": anchor_value,
        "anchor_document_hash": str(document.get("document_hash") or ""),
        "anchor_block_id": str(unit.get("block_id") or ""),
        "anchor_unit_id": str(unit.get("unit_id") or ""),
    }
