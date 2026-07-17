"""Refresh-time source packets and ID-only external evidence selection."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

try:
    from .curated_external_argument_cards import (
        SELECTION_SCHEMA,
        SELECTOR_VERSION,
        build_external_argument_pack,
        external_selection_batches,
        materialize_external_source_units,
        prepare_external_argument_material,
        validate_external_unit_selection,
    )
except ImportError:
    from curated_external_argument_cards import (
        SELECTION_SCHEMA,
        SELECTOR_VERSION,
        build_external_argument_pack,
        external_selection_batches,
        materialize_external_source_units,
        prepare_external_argument_material,
        validate_external_unit_selection,
    )


SOURCE_PACKET_SCHEMA_VERSION = "curated_external_source_packet.v1"


class FullBodyExtractorError(Exception):
    """Structured refresh failure that leaves no partial ready pack."""

    def __init__(self, status: str, message: str = ""):
        super().__init__(message or status)
        self.status = status


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_hash(value: str | None) -> str:
    return hashlib.sha256(_normalize_text(value).encode("utf-8")).hexdigest()


def _clean_source_content(value: Any) -> str:
    text = _normalize_text(value)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+|<[^>]+>|[#.]\w+[^\{]*\{[^}]*\}", "", text)
    markers = ("免责声明", "风险提示", "点击上方", "关注公众号", "设为星标", "扫码", "原文链接", "阅读原文", "广告", "往期热文推荐", "相关推荐", "联系我们", "商务合作", "进群交流", "-END-", "End", "视频推荐", "文章推荐")
    ends = [text.find(marker) for marker in markers if text.find(marker) > 0]
    return _normalize_text(text[:min(ends)] if ends else text)


def _read_json_or_jsonl(path: str | Path) -> list[Any]:
    source = Path(path)
    if not source.exists() or not (text := source.read_text(encoding="utf-8").strip()):
        return []
    if text.startswith(("[", "{")):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("items", []) if isinstance(payload.get("items"), list) else [payload]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build_source_packets(
    jsonl_path: str | Path, *, stock_name: str = "", max_sources: int | None = None,
    max_source_chars: int | None = None,
) -> list[dict]:
    """Canonicalize local source bodies into preview-only source packets."""
    def score(item: dict) -> float:
        return float(item.get("quality_score") or 0) * 10 + float(item.get("discovery_score") or 0)

    packets, seen = [], set()
    for item in sorted(_read_json_or_jsonl(jsonl_path), key=score, reverse=True):
        if not isinstance(item, dict) or not (ref := str(item.get("source_ref") or item.get("url") or "")) or ref in seen:
            continue
        seen.add(ref)
        content = _clean_source_content(item.get("content"))
        if max_source_chars:
            content = content[:max_source_chars]
        if not content:
            continue
        kind = str(item.get("source_kind") or item.get("source_type") or "external")
        packets.append({
            "schema_version": SOURCE_PACKET_SCHEMA_VERSION,
            "source_id": f"curated-source:{kind}:{normalized_hash(ref)[:16]}",
            "stock_name": stock_name, "title": _normalize_text(item.get("title")),
            "account": _normalize_text(item.get("account")),
            "publish_time": _normalize_text(item.get("publish_time")), "source_kind": kind,
            "source_ref": ref, "source_url": str(item.get("url") or ref), "content": content,
            "source_content_hash": normalized_hash(content), "quality_action": "preview_only",
            "knowledge_eligible": False, "scoring_eligible": False, "risk_score_eligible": False,
            "synthesis_eligible": bool(item.get("synthesis_eligible", True)),
            "synthesis_display_only": True,
            "verification_status": str(item.get("verification_status") or "professional_observation"),
        })
        if max_sources and len(packets) >= max_sources:
            break
    return packets


def _extract_json(value: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip())
    if not (match := re.search(r"\{.*\}", text, re.DOTALL)):
        raise ValueError("no JSON object in selector response")
    return json.loads(match.group(0))


def _request_json(*, model: str, base_url: str, api_key: str, client: Any, prompt: str,
                  max_api_retries: int, sleep_fn: Callable[[float], None]) -> dict:
    for attempt in range(max(0, max_api_retries) + 1):
        try:
            active = client
            if active is None:
                import openai
                active = openai.OpenAI(base_url=base_url, api_key=api_key)
            response = active.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, timeout=120,
            )
            return _extract_json(response.choices[0].message.content or "")
        except Exception as exc:
            if attempt >= max(0, max_api_retries):
                raise FullBodyExtractorError("selector_failed", str(exc)) from exc
            sleep_fn(2 ** attempt)
    raise AssertionError("unreachable")


def _selector_prompt(stock_name: str, source_units: list[dict]) -> str:
    units = "\n".join(json.dumps({key: unit.get(key, "") for key in ("unit_id", "source_id", "source_ordinal", "text")}, ensure_ascii=False) for unit in source_units)
    return (
        "你是一名投研外部材料证据选择助手。只选择或分组已给出的原文单元，输出 JSON。\n"
        f"目标公司：{stock_name}\n原文单元：{units}\n"
        "每个输入 unit_id 必须恰好出现一次；action 只能是 keep 或 skip；输入均为同业或行业背景材料。"
        "非空 group_id 只能包含同一来源中相邻的 1-3 个单元。不得输出正文、实体、类别、数字、价格、评分、风险或建议。\n"
        '输出：{"schema_version":"curated_external_unit_selection.v1","decisions":[{"unit_id":"...","action":"keep|skip","group_id":"...","reason":"incremental_target_fact|incremental_peer_context|baseline_duplicate|low_signal"}]}'
    )


def llm_unit_selector_factory(
    model: str, base_url: str, api_key: str, *, stock_name: str = "", client: Any | None = None,
    max_api_retries: int = 2, sleep_fn: Callable[[float], None] | None = None,
) -> Callable[[list[dict]], dict]:
    """Return the sole v3 LLM boundary: stable-ID selection, never prose."""
    pause = sleep_fn or time.sleep

    def select(source_units: list[dict]) -> dict:
        payload = _request_json(
            model=model, base_url=base_url, api_key=api_key, client=client,
            prompt=_selector_prompt(stock_name, source_units),
            max_api_retries=max_api_retries, sleep_fn=pause,
        )
        if payload.get("schema_version") != SELECTION_SCHEMA or not isinstance(payload.get("decisions"), list):
            raise FullBodyExtractorError("selector_failed", "selector schema mismatch")
        return payload

    return select


def _downgrade_nonconsecutive_peer_groups(source_units: list[dict], selection: dict) -> dict:
    """Keep ID decisions but turn unsafe ordinal-gap groups into singletons."""
    decisions = selection.get("decisions") if isinstance(selection, dict) else None
    if not isinstance(decisions, list):
        return selection
    units_by_id = {str(unit.get("unit_id") or ""): unit for unit in source_units}
    groups: dict[str, list[dict]] = {}
    for decision in decisions:
        if isinstance(decision, dict) and (group_id := str(decision.get("group_id") or "")):
            groups.setdefault(group_id, []).append(decision)
    downgrade_ids = set()
    for members in groups.values():
        units = [units_by_id.get(str(row.get("unit_id") or "")) for row in members]
        safe_shape = (
            1 <= len(members) <= 3
            and all(row.get("action") == "keep" for row in members)
            and all(unit is not None for unit in units)
        )
        if not safe_shape:
            continue
        source_ids = {str(unit.get("source_id") or "") for unit in units}
        ordinals = sorted(int(unit.get("source_ordinal") or 0) for unit in units)
        if len(source_ids) == 1 and ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
            downgrade_ids.update(str(row.get("unit_id") or "") for row in members)
    if not downgrade_ids:
        return selection
    return {**selection, "decisions": [
        {**row, "group_id": ""} if str(row.get("unit_id") or "") in downgrade_ids else row
        for row in decisions
    ]}


def build_curated_external_argument_pack(
    source_packets: list[dict], baseline_text: str, *, selector: Callable[[list[dict]], dict], stock_name: str,
) -> dict:
    """Build a ready v3 pack only after every selector batch validates."""
    units = materialize_external_source_units(source_packets, stock_name=stock_name)
    prepared = prepare_external_argument_material(
        units, stock_name=stock_name, baseline_text=baseline_text,
    )
    selections = []
    request_count = 0
    for batch in external_selection_batches(prepared["optional_peer_units"]):
        for _ in range(2):
            request_count += 1
            try:
                selection = selector(batch)
            except FullBodyExtractorError:
                selection = {}
            selection = _downgrade_nonconsecutive_peer_groups(batch, selection)
            if validate_external_unit_selection(batch, selection, mandatory_ids=set())["status"] == "ok":
                selections.append(selection)
                break
        else:
            return build_external_argument_pack(
                stock_name=stock_name, source_packets=source_packets, baseline_text=baseline_text,
                selections=[], prepared_material=prepared, selector_request_count=request_count,
            )
    return build_external_argument_pack(
        stock_name=stock_name, source_packets=source_packets, baseline_text=baseline_text,
        selections=selections, selector_version=SELECTOR_VERSION,
        prepared_material=prepared, selector_request_count=request_count,
    )


def write_curated_external_argument_pack(pack: dict, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
