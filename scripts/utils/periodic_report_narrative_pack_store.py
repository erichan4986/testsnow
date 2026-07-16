"""Validated JSON shadow storage for periodic-report narrative cards."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from .annual_argument_schema import CARD_SCHEMA_VERSION, ENVELOPE_SCHEMA_VERSION, SELECTION_VERSION, validate_card_v2
except ImportError:  # pragma: no cover - script-style imports
    from annual_argument_schema import CARD_SCHEMA_VERSION, ENVELOPE_SCHEMA_VERSION, SELECTION_VERSION, validate_card_v2

PACK_SCHEMA_VERSION = "periodic_report_narrative_material_pack.v1"
MANIFEST_SCHEMA_VERSION = "periodic_report_narrative_pack_manifest.v1"
PACK_DIRNAME, MANIFEST_FILENAME = "periodic_narrative_packs", "periodic_narrative_pack_manifest.json"


class PeriodicNarrativePackStorageError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PeriodicNarrativePackWriteResult:
    state: str
    pack_path: Path
    manifest_path: Path


def normalized_source_excerpt_hash(text: object) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", str(text or "")).strip().encode("utf-8")).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _fail_if(condition: bool, code: str) -> None:
    if condition:
        raise PeriodicNarrativePackStorageError(code)


def _root(base_dir: str | Path, stock_name: str) -> Path:
    segment = re.sub(r"[\\/]+|\.{2,}", "-", str(stock_name or "").replace("\x00", ""))
    return Path(base_dir) / "10-Stocks" / ("-".join(segment.split()).strip("-. ") or "unknown")


def _period(year: object, report_type: object) -> tuple[int, str]:
    try:
        return int(year), str(report_type)
    except (TypeError, ValueError) as exc:
        raise PeriodicNarrativePackStorageError("invalid_period") from exc


def _relative_path(year: object, report_type: object) -> str:
    year, report_type = _period(year, report_type)
    safe_type = re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", report_type.lower())).strip("-") or "unknown"
    return f"{PACK_DIRNAME}/{year}-{safe_type}.json"


_PAYLOAD_FIELDS = (
    "schema_version", "producer_schema_version", "selection_version", "stock_code",
    "stock_name", "report_year", "report_type", "cards", "producer_diagnostics",
)


def _payload(envelope: Dict[str, Any]) -> Dict[str, Any]:
    return {key: envelope[key] for key in _PAYLOAD_FIELDS}


def _integrity(envelope: Dict[str, Any]) -> Dict[str, Any]:
    cards, diagnostics = envelope["cards"], envelope["producer_diagnostics"]
    return {
        "card_count": len(cards),
        "source_unit_count": sum(len(card.get("source_units") or []) for card in cards),
        "cards_sha256": _hash(cards),
        "producer_diagnostics_sha256": _hash(diagnostics),
        "payload_sha256": _hash(_payload(envelope)),
    }


def v2_note_card_fingerprint(card: Dict[str, Any]) -> str:
    fields = (
        "schema_version", "selection_version", "card_id", "argument_family", "argument_complete",
        "title", "report_year", "report_type", "source_type", "source_credit", "source_block_id",
        "source_unit_ids", "source_units", "fact_anchors", "secondary_signals", "score_parts",
        "quality_score", "selection_reason",
    )
    payload = {field: deepcopy(card.get(field)) for field in fields}
    payload["source_excerpt_hash"] = normalized_source_excerpt_hash(card.get("source_excerpt"))
    return _hash(payload)


def validate_periodic_narrative_pack_envelope(
    envelope: Dict[str, Any], *, stock_name: str = "", stock_code: str = "",
    report_year: object = None, report_type: object = None,
) -> None:
    _fail_if(not isinstance(envelope, dict) or envelope.get("schema_version") != PACK_SCHEMA_VERSION, "invalid_pack_schema")
    _fail_if(envelope.get("producer_schema_version") != ENVELOPE_SCHEMA_VERSION or envelope.get("selection_version") != SELECTION_VERSION, "invalid_producer_schema")
    _fail_if(bool(stock_name) and envelope.get("stock_name") != str(stock_name), "pack_stock_name_mismatch")
    _fail_if(bool(stock_code) and envelope.get("stock_code") != str(stock_code), "pack_stock_code_mismatch")
    year, kind = _period(envelope.get("report_year"), envelope.get("report_type"))
    _fail_if(report_year is not None and year != int(report_year) or report_type is not None and kind != str(report_type), "pack_period_mismatch")
    cards, diagnostics, integrity = envelope.get("cards"), envelope.get("producer_diagnostics"), envelope.get("integrity")
    _fail_if(not isinstance(cards, list) or not isinstance(diagnostics, dict) or not isinstance(integrity, dict), "invalid_pack_payload")
    card_ids, unit_ids = set(), set()
    for card in cards:
        _fail_if(not isinstance(card, dict) or bool(validate_card_v2(card)) or card.get("schema_version") != CARD_SCHEMA_VERSION, "invalid_pack_card")
        _fail_if(card.get("report_year") != year or card.get("report_type") != kind, "card_period_mismatch")
        card_id, units = str(card.get("card_id") or ""), set(card.get("source_unit_ids") or [])
        _fail_if(card_id in card_ids, "duplicate_card_id")
        _fail_if(bool(unit_ids & units), "reused_source_unit")
        card_ids.add(card_id)
        unit_ids.update(units)
    _fail_if(integrity != _integrity(envelope), "pack_integrity_mismatch")


def _envelope(stock_name: str, stock_code: str, card_pack: Dict[str, Any]) -> Dict[str, Any]:
    cards, candidates, diagnostics = card_pack.get("cards"), card_pack.get("candidate_cards"), card_pack.get("diagnostics")
    _fail_if(not isinstance(cards, list) or not isinstance(candidates, list) or not isinstance(diagnostics, dict), "invalid_producer_envelope")
    _fail_if(cards != candidates, "candidate_cards_mismatch")
    _fail_if(card_pack.get("stock_name") != stock_name or str(card_pack.get("stock_code") or "") != str(stock_code), "producer_identity_mismatch")
    year, kind = _period(card_pack.get("report_year"), card_pack.get("report_type"))
    result = {
        "schema_version": PACK_SCHEMA_VERSION,
        "producer_schema_version": str(card_pack.get("schema_version") or ""),
        "selection_version": str(card_pack.get("selection_version") or ""),
        "stock_code": str(stock_code), "stock_name": stock_name,
        "report_year": year, "report_type": kind,
        "cards": deepcopy(cards), "producer_diagnostics": deepcopy(diagnostics),
    }
    result["integrity"] = _integrity(result)
    validate_periodic_narrative_pack_envelope(result, stock_name=stock_name, stock_code=stock_code)
    return result


def _read(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise PeriodicNarrativePackStorageError("invalid_json") from exc
    _fail_if(not isinstance(value, dict), "invalid_json")
    return value


def _write(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _manifest(stock_name: str, stock_code: str, entries: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    periods = sorted(map(dict, entries), key=lambda item: (item["report_year"], item["report_type"], item["pack_path"]))
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION, "stock_code": str(stock_code),
        "stock_name": stock_name, "periods": periods, "periods_sha256": _hash(periods),
    }


def _manifest_entries(root: Path, stock_name: str, stock_code: str) -> List[Dict[str, Any]]:
    manifest = _read(root / MANIFEST_FILENAME)
    _fail_if(manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION or manifest.get("stock_name") != stock_name or manifest.get("stock_code") != str(stock_code), "invalid_manifest")
    periods = manifest.get("periods")
    _fail_if(not isinstance(periods, list) or manifest.get("periods_sha256") != _hash(periods), "invalid_manifest")
    seen, paths = set(), set()
    for entry in periods:
        _fail_if(not isinstance(entry, dict), "invalid_manifest")
        key = _period(entry.get("report_year"), entry.get("report_type"))
        path = str(entry.get("pack_path") or "")
        _fail_if(key in seen or path in paths or path != _relative_path(*key), "manifest_path_invalid")
        seen.add(key)
        paths.add(path)
    actual = {path.relative_to(root).as_posix() for path in (root / PACK_DIRNAME).glob("*.json")} if (root / PACK_DIRNAME).exists() else set()
    _fail_if(paths != actual, "manifest_incomplete")
    return sorted(periods, key=lambda item: (item["report_year"], item["report_type"], item["pack_path"]))


def write_periodic_report_narrative_pack(
    *, stock_name: str, stock_code: str, card_pack: Dict[str, Any], base_dir: str | Path,
) -> PeriodicNarrativePackWriteResult:
    envelope, root = _envelope(stock_name, stock_code, card_pack), _root(base_dir, stock_name)
    manifest_path, packs_dir = root / MANIFEST_FILENAME, root / PACK_DIRNAME
    if manifest_path.exists():
        entries, state = _manifest_entries(root, stock_name, stock_code), "upsert"
    else:
        _fail_if(packs_dir.exists() and any(packs_dir.glob("*.json")), "repair_required")
        entries, state = [], "bootstrap"
    year, kind = envelope["report_year"], envelope["report_type"]
    entry = {
        "report_year": year, "report_type": kind, "pack_path": _relative_path(year, kind),
        "cards_sha256": envelope["integrity"]["cards_sha256"],
        "payload_sha256": envelope["integrity"]["payload_sha256"],
    }
    entries = [old for old in entries if _period(old["report_year"], old["report_type"]) != (year, kind)] + [entry]
    pack_path = root / entry["pack_path"]
    _write(pack_path, envelope)
    _write(manifest_path, _manifest(stock_name, stock_code, entries))
    return PeriodicNarrativePackWriteResult(state, pack_path, manifest_path)


def load_validated_periodic_narrative_pack_set(
    *, stock_name: str, stock_code: str, base_dir: str | Path,
) -> Dict[str, Any]:
    root, packs = _root(base_dir, stock_name), []
    for entry in _manifest_entries(root, stock_name, stock_code):
        envelope = _read(root / entry["pack_path"])
        validate_periodic_narrative_pack_envelope(
            envelope, stock_name=stock_name, stock_code=stock_code,
            report_year=entry["report_year"], report_type=entry["report_type"],
        )
        _fail_if(envelope["integrity"]["cards_sha256"] != entry.get("cards_sha256") or envelope["integrity"]["payload_sha256"] != entry.get("payload_sha256"), "manifest_hash_mismatch")
        packs.append(envelope)
    return {"packs": packs, "cards": [card for pack in packs for card in pack["cards"]]}
