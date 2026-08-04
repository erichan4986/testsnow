"""Offline v4 external-material production with one ID-only LLM boundary."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

try:
    from .external_narrative_plan import deterministic_narrative_plan
    from .external_pack import (
        SELECTION_SCHEMA,
        build_external_argument_pack_v4,
        external_selection_batches_v4,
        prepare_external_argument_material_v4,
        validate_external_unit_selection_v4,
    )
    from .external_source_document import build_external_source_document
except ImportError:
    from external_narrative_plan import deterministic_narrative_plan
    from external_pack import SELECTION_SCHEMA, build_external_argument_pack_v4, external_selection_batches_v4, prepare_external_argument_material_v4, validate_external_unit_selection_v4
    from external_source_document import build_external_source_document


SOURCE_INPUT_SCHEMA_VERSION = "curated_external_source_input.v2"
MAX_SELECTOR_RETRIES = 1


class FullBodyExtractorError(Exception):
    """Structured producer failure that never creates a partial ready pack."""

    def __init__(self, status: str, message: str = ""):
        super().__init__(message or status)
        self.status = status


def normalized_hash(value: str | None) -> str:
    """Keep the stable source identity helper used by source-intake callers."""
    return hashlib.sha256(re.sub(r"\s+", " ", str(value or "")).strip().encode("utf-8")).hexdigest()


def build_source_documents(
    jsonl_path: str | Path,
    *,
    stock_name: str = "",
    max_sources: int | None = None,
) -> list[dict]:
    """Build paragraph-preserving canonical documents from local source input."""
    documents, seen = [], set()
    for item in sorted(_read_json_or_jsonl(jsonl_path), key=_source_score, reverse=True):
        if not isinstance(item, Mapping):
            continue
        source_ref = str(item.get("source_ref") or item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        if not source_ref or not content or source_ref in seen:
            continue
        seen.add(source_ref)
        kind = str(item.get("source_kind") or item.get("source_type") or "external").strip()
        document = build_external_source_document({
            "schema_version": SOURCE_INPUT_SCHEMA_VERSION,
            "source_id": f"curated-source:{kind}:{normalized_hash(source_ref)[:16]}",
            "stock_name": stock_name,
            "title": str(item.get("title") or "").strip(),
            "account": str(item.get("account") or "").strip(),
            "publish_time": str(item.get("publish_time") or "").strip(),
            "source_kind": kind,
            "source_ref": source_ref,
            "source_url": str(item.get("url") or source_ref).strip(),
            "content": content,
        })
        documents.append(document)
        if max_sources and len(documents) >= max_sources:
            break
    return documents


def _source_score(item: Mapping[str, Any]) -> float:
    return float(item.get("quality_score") or 0) * 10 + float(item.get("discovery_score") or 0)


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
        if isinstance(payload, Mapping):
            return payload.get("items", []) if isinstance(payload.get("items"), list) else [payload]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _extract_json(value: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip())
    if not (match := re.search(r"\{.*\}", text, re.DOTALL)):
        raise ValueError("no JSON object in selector response")
    return json.loads(match.group(0))


def _request_json(
    *,
    model: str,
    base_url: str,
    api_key: str,
    client: Any,
    prompt: str,
    timeout_seconds: int = 120,
) -> dict:
    try:
        active = client
        if active is None:
            import openai
            active = openai.OpenAI(base_url=base_url, api_key=api_key)
        response = active.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=timeout_seconds,
        )
        return _extract_json(response.choices[0].message.content or "")
    except Exception as exc:
        raise FullBodyExtractorError("selector_failed", str(exc)) from exc


def _selector_prompt(stock_name: str, source_units: list[dict]) -> str:
    rows = (
        {
            key: unit.get(key, "")
            for key in ("unit_id", "source_id", "block_id", "block_ordinal", "unit_ordinal", "text")
        }
        for unit in source_units
    )
    return (
        "你是一名投研外部材料证据选择助手。只选择或分组已给出的原文单元，输出 JSON。\n"
        f"目标公司：{stock_name}\n原文单元：" + "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
        "每个输入 unit_id 必须恰好出现一次；action 只能是 keep 或 skip。"
        "非空 group_id 只能包含同一 source_id、同一 block_id 的连续单元。"
        "不得输出正文、实体、类别、关系、数字、价格、评分、风险或建议。\n"
        '输出：{"schema_version":"curated_external_unit_selection.v2","decisions":[{"unit_id":"...","action":"keep|skip","group_id":"..."}]}'
    )


def llm_unit_selector_factory(
    model: str,
    base_url: str,
    api_key: str,
    *,
    stock_name: str = "",
    client: Any | None = None,
) -> Callable[[list[dict]], dict]:
    """Return the sole LLM boundary: a v4 unit-ID selection response."""

    def select(source_units: list[dict]) -> dict:
        payload = _request_json(
            model=model,
            base_url=base_url,
            api_key=api_key,
            client=client,
            prompt=_selector_prompt(stock_name, source_units),
        )
        if payload.get("schema_version") != SELECTION_SCHEMA or not isinstance(payload.get("decisions"), list):
            raise FullBodyExtractorError("selector_failed", "selector schema mismatch")
        return payload

    return select


def build_external_argument_pack_from_sources(
    documents: list[dict],
    baseline_text: str,
    *,
    selector: Callable[[list[dict]], dict],
    stock_name: str,
) -> dict:
    """Build v4 strictly from canonical documents and validated ID decisions."""
    prepared = prepare_external_argument_material_v4(
        documents,
        stock_name=stock_name,
        baseline_text=baseline_text,
    )
    if (prepared.get("diagnostics") or {}).get("rejected_source_documents"):
        return build_external_argument_pack_v4(
            documents,
            stock_name=stock_name,
            baseline_text=baseline_text,
            selections=[],
            prepared_material=prepared,
        )
    selections, request_count = [], 0
    for batch in external_selection_batches_v4(prepared["peer_units"]):
        for _ in range(MAX_SELECTOR_RETRIES + 1):
            request_count += 1
            try:
                selection = selector(batch)
            except FullBodyExtractorError:
                selection = {}
            if validate_external_unit_selection_v4(batch, selection)["status"] == "ok":
                selections.append(selection)
                break
        else:
            pack = build_external_argument_pack_v4(
                documents,
                stock_name=stock_name,
                baseline_text=baseline_text,
                selections=selections,
                prepared_material=prepared,
                selector_request_count=request_count,
            )
            pack.setdefault("diagnostics", {})["selector_failure"] = "invalid_or_failed_batch"
            return pack
    pack = build_external_argument_pack_v4(
        documents,
        stock_name=stock_name,
        baseline_text=baseline_text,
        selections=selections,
        prepared_material=prepared,
        selector_request_count=request_count,
    )
    if pack.get("status") == "ready":
        pack["narrative_plan"] = deterministic_narrative_plan(pack)
    return pack


def write_external_argument_pack_v4(pack: Mapping[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
