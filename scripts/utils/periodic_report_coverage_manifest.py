"""Compact audit ledger for periodic-report evidence coverage."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from copy import deepcopy

SCHEMA_VERSION = "annual_document_coverage_manifest.v1"
COORDINATE_SPACE = "periodic_report_cleaned_text.v1"
SECTION_STATES = ("selected_for_review", "card_selected", "reviewed_no_card", "candidate_not_reviewed", "unmapped", "structural_only")
EVIDENCE_STATES = ("selected_for_producer", "omitted_usage_limit", "omitted_capacity")
PRODUCER_STATES = ("card_selected", "reviewed_no_card", "not_reviewed")
FORBIDDEN_KEYS = {"text", "source_excerpt", "source_units"}
def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
def _span(row: object) -> tuple[int, int]:
    row = row if isinstance(row, dict) else {}
    try:
        return int(row.get("start", -1)), int(row.get("end", -1))
    except (TypeError, ValueError):
        return -1, -1
def _markers(text: str) -> list[tuple[int, int, int]]:
    rows = []
    token = re.compile(r"年度报告|年報|ANNUAL\s+REPORT", re.I)
    for line in re.finditer(r"(?m)^.*$", text):
        value = line.group().strip()
        if not token.search(value):
            continue
        match = re.match(r"^(\d{1,4})\s+.+", value) or re.search(
            r"(?:年度报告|年報|ANNUAL\s+REPORT)\D{0,80}(\d{1,4})$", value, re.I
        )
        if match:
            rows.append((line.start(), line.end(), int(match.group(1))))
    return rows
def _headings(text: str) -> list[tuple[int, int, int, str]]:
    rows = [(m.start(), m.end(), len(m.group(1)), m.group(2).strip())
            for m in re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$", text)]
    return rows or [(m.start(), m.end(), 1, m.group(1).strip()) for m in re.finditer(
        r"(?m)^(第[一二三四五六七八九十百零〇0-9]+节[ \t　]*[^\n\r]+?)[ \t]*$", text
    )]
def _sections(text: str) -> list[dict]:
    headings, markers = _headings(text), _markers(text)
    synthetic = not headings
    headings = headings or [(0, 0, 0, "document-root")]
    rows = []
    for index, (start, heading_end, level, heading) in enumerate(headings):
        end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        body_start = 0 if synthetic else heading_end
        previous_start = headings[index - 1][0] if index else -1
        before = [m for m in markers if m[1] <= start and start - m[1] <= 240 and m[0] >= previous_start]
        inside = [m for m in markers if start <= m[0] < end]
        rows.append({
            "section_id": f"section:{_hash(f'{heading}|{level}|{start}|{end}')}",
            "heading": heading, "heading_level": level,
            "source_span": {"start": start, "end": end},
            "page_start": before[-1][2] if before else (inside[0][2] if inside else None),
            "page_end": inside[-1][2] if inside else None,
            "matched_coverage_block_ids": [],
            "coverage_state": "structural_only" if not synthetic and len(re.sub(r"\s+", "", text[body_start:end])) < 12 else "unmapped",
        })
    return rows
def _identity(block: dict) -> tuple[str, str, int, int]:
    start, end = _span(block.get("source_span"))
    source_hash = _hash(str(block.get("text") or ""))
    payload = {"usage": str(block.get("usage") or ""), "section": str(block.get("section") or ""),
               "title": str(block.get("title") or ""), "start": start, "end": end,
               "source_text_sha256": source_hash}
    return _hash(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))), source_hash, start, end
def _mapped_section(sections: list[dict], start: int, end: int) -> dict | None:
    candidates = []
    for index, section in enumerate(sections):
        left, right = _span(section["source_span"])
        if (overlap := min(end, right) - max(start, left)) > 0:
            candidates.append((-overlap, index, section))
    return min(candidates, default=(0, 0, None))[2]
def _block_rows(sections: list[dict], extracted: list[dict], prioritized: list[dict], selected: list[dict]) -> list[dict]:
    extracted = [b for b in extracted if isinstance(b, dict)]
    priority = {_identity(b)[0]: b for b in prioritized if isinstance(b, dict)}
    selected_ids = {_identity(b)[0] for b in selected if isinstance(b, dict)}
    occurrences, first = Counter(_identity(b)[0] for b in extracted), {}
    for block in extracted:
        first.setdefault(_identity(block)[0], block)
    rows = []
    for identity, block in first.items():
        _, source_hash, start, end = _identity(block)
        survivor, section = priority.get(identity), _mapped_section(sections, start, end)
        row = {
            "coverage_block_id": f"coverage-block:{identity}",
            "evidence_block_id": str(survivor.get("id") or "") if survivor else None,
            "usage": str(block.get("usage") or ""), "section_id": section["section_id"] if section else None,
            "source_span": {"start": start, "end": end}, "source_text_sha256": source_hash,
            "candidate_occurrences": occurrences[identity],
            "evidence_disposition": "selected_for_producer" if identity in selected_ids else "omitted_capacity" if survivor else "omitted_usage_limit",
        }
        if section:
            section["matched_coverage_block_ids"].append(row["coverage_block_id"])
        rows.append(row)
    selected_coverage = {r["coverage_block_id"] for r in rows if r["evidence_disposition"] == "selected_for_producer"}
    for section in sections:
        if section["coverage_state"] == "structural_only":
            continue
        matched = set(section["matched_coverage_block_ids"])
        section["coverage_state"] = "selected_for_review" if matched & selected_coverage else "candidate_not_reviewed" if matched else "unmapped"
    return sorted(rows, key=lambda row: (*_span(row["source_span"]), row["coverage_block_id"]))
def _summary(sections: list[dict], blocks: list[dict]) -> dict:
    section_counts, evidence_counts, producer_counts = (Counter(s.get("coverage_state") for s in sections), Counter(b.get("evidence_disposition") for b in blocks), Counter(b.get("producer_disposition") for b in blocks))
    return {
        "section_states": {key: section_counts[key] for key in SECTION_STATES},
        "evidence_dispositions": {key: evidence_counts[key] for key in EVIDENCE_STATES},
        "producer_dispositions": {key: producer_counts[key] for key in PRODUCER_STATES},
        "recognized_section_count": len(sections),
        "mapped_section_count": sum(bool(s.get("matched_coverage_block_ids")) for s in sections),
        "unresolved_section_count": sum(s.get("coverage_state") in {"candidate_not_reviewed", "unmapped"} for s in sections),
        "candidate_block_count": sum(int(b.get("candidate_occurrences", 0)) for b in blocks),
        "selected_evidence_block_count": evidence_counts["selected_for_producer"],
        "source_unit_count": sum(int(b.get("source_unit_count", 0)) for b in blocks),
        "selected_source_unit_count": sum(int(b.get("selected_source_unit_count", 0)) for b in blocks),
    }
def _page_status(sections: list[dict]) -> str:
    substantive = [s for s in sections if s["coverage_state"] != "structural_only"]
    located = sum(s.get("page_start") is not None for s in substantive)
    return "available" if substantive and located == len(substantive) else "partial" if located else "unavailable"
def _analysis_status(stage: str, sections: list[dict]) -> str:
    accepted, substantive = ({"selected_for_review"} if stage == "evidence" else {"card_selected", "reviewed_no_card"}, [s for s in sections if s["coverage_state"] != "structural_only"])
    return "complete" if substantive and all(s["coverage_state"] in accepted for s in substantive) else "partial"
def unavailable_periodic_report_coverage_manifest(*, report_type: str = "", document_style: str = "", reason: str) -> dict:
    return {"schema_version": SCHEMA_VERSION, "coordinate_space": COORDINATE_SPACE, "stage": "evidence",
            "status": "unavailable", "analysis_coverage_status": "unavailable", "unavailable_reason": reason,
            "document_sha256": "", "cleaned_char_count": 0, "report_type": report_type,
            "document_style": document_style, "page_locator_status": "unavailable", "sections": [],
            "block_decisions": [], "summary": _summary([], [])}
def build_periodic_report_coverage_manifest(cleaned_text: str, *, report_type: str, document_style: str,
                                            extracted_candidates: list[dict], prioritized_candidates: list[dict],
                                            selected_blocks: list[dict]) -> dict:
    if not cleaned_text.strip():
        return unavailable_periodic_report_coverage_manifest(report_type=report_type, document_style=document_style, reason="empty_document")
    sections = _sections(cleaned_text)
    blocks = _block_rows(sections, extracted_candidates, prioritized_candidates, selected_blocks)
    manifest = {"schema_version": SCHEMA_VERSION, "coordinate_space": COORDINATE_SPACE, "stage": "evidence",
                "status": "ready", "analysis_coverage_status": _analysis_status("evidence", sections),
                "document_sha256": _hash(cleaned_text), "cleaned_char_count": len(cleaned_text),
                "report_type": report_type, "document_style": document_style,
                "page_locator_status": _page_status(sections), "sections": sections,
                "block_decisions": blocks, "summary": _summary(sections, blocks)}
    if errors := validate_periodic_report_coverage_manifest(manifest):
        raise ValueError(f"invalid_coverage_manifest:{errors[0]}")
    return manifest
def _unavailable_producer(report_type: str, document_style: str, reason: str) -> dict:
    result = unavailable_periodic_report_coverage_manifest(report_type=report_type, document_style=document_style, reason=reason)
    result["stage"] = "producer"
    return result
def finalize_periodic_report_coverage_manifest(manifest: object, *, source_unit_decisions: list[dict],
                                               cards: list[dict], report_type: str = "",
                                               document_style: str = "") -> dict:
    if manifest is None:
        return _unavailable_producer(report_type, document_style, "upstream_missing")
    if validate_periodic_report_coverage_manifest(manifest) or not isinstance(manifest, dict) or manifest.get("status") != "ready":
        return _unavailable_producer(report_type, document_style, "upstream_invalid")
    result = deepcopy(manifest)
    blocks = result["block_decisions"]
    selected_blocks = {b.get("evidence_block_id") for b in blocks if b.get("evidence_disposition") == "selected_for_producer"}
    card_map = {str(c.get("card_id") or ""): c for c in cards if isinstance(c, dict) and c.get("card_id")}
    decisions = [d for d in source_unit_decisions if isinstance(d, dict)]
    unit_ids = [str(d.get("source_unit_id") or "") for d in decisions]
    referenced_cards = {str(card_id) for d in decisions for card_id in d.get("selected_by_card_ids", [])}
    invalid = (not all(unit_ids) or len(unit_ids) != len(set(unit_ids)) or len(card_map) != len(cards) or any(d.get("disposition") not in {"selected", "rejected"} or d.get("source_block_id") not in selected_blocks for d in decisions)
               or any((d.get("disposition") == "selected") != bool(d.get("selected_by_card_ids")) for d in decisions)
               or not referenced_cards <= set(card_map) or set(card_map) != referenced_cards
               or any(card_map[card_id].get("source_block_id") != d.get("source_block_id")
                      for d in decisions for card_id in d.get("selected_by_card_ids", []) if card_id in card_map))
    if invalid:
        return _unavailable_producer(report_type, document_style, "producer_invalid")
    by_block = {block_id: [d for d in decisions if d.get("source_block_id") == block_id] for block_id in selected_blocks}
    for block in blocks:
        block_id = block.get("evidence_block_id")
        units = by_block.get(block_id, [])
        selected = [d for d in units if d.get("disposition") == "selected"]
        block["source_unit_count"] = len(units)
        block["selected_source_unit_count"] = len(selected)
        block["selected_by_card_ids"] = list(dict.fromkeys(card_id for d in selected for card_id in d.get("selected_by_card_ids", [])))
        block["unit_rejection_counts"] = dict(Counter(str(d.get("reason") or "unknown") for d in units if d.get("disposition") != "selected"))
        block["producer_disposition"] = "not_reviewed" if block["evidence_disposition"] != "selected_for_producer" else "card_selected" if selected else "reviewed_no_card"
    by_coverage = {b["coverage_block_id"]: b for b in blocks}
    for section in result["sections"]:
        if section["coverage_state"] == "structural_only":
            continue
        mapped = [by_coverage[item] for item in section["matched_coverage_block_ids"]]
        states = {b["producer_disposition"] for b in mapped}
        section["coverage_state"] = "card_selected" if "card_selected" in states else "reviewed_no_card" if "reviewed_no_card" in states else "candidate_not_reviewed" if mapped else "unmapped"
    result.update(stage="producer", analysis_coverage_status=_analysis_status("producer", result["sections"]), summary=_summary(result["sections"], blocks))
    return result if not validate_periodic_report_coverage_manifest(result) else _unavailable_producer(report_type, document_style, "producer_invalid")
def _forbidden(value: object) -> bool:
    return (bool(FORBIDDEN_KEYS & set(value)) or any(_forbidden(v) for v in value.values())) if isinstance(value, dict) else any(_forbidden(v) for v in value) if isinstance(value, list) else False
def validate_periodic_report_coverage_manifest(manifest: object) -> tuple[str, ...]:
    if not isinstance(manifest, dict):
        return ("manifest_not_object",)
    errors = []
    if manifest.get("schema_version") != SCHEMA_VERSION: errors.append("schema_version_invalid")
    if manifest.get("coordinate_space") != COORDINATE_SPACE: errors.append("coordinate_space_invalid")
    if manifest.get("status") == "unavailable":
        if manifest.get("analysis_coverage_status") != "unavailable": errors.append("analysis_coverage_status_invalid")
        return tuple(errors)
    stage, count = manifest.get("stage"), manifest.get("cleaned_char_count")
    if manifest.get("status") != "ready": errors.append("status_invalid")
    if stage not in {"evidence", "producer"}: errors.append("stage_invalid")
    if not isinstance(count, int) or count <= 0: errors.append("cleaned_char_count_invalid"); count = -1
    if not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("document_sha256") or "")): errors.append("document_sha256_invalid")
    sections, blocks = manifest.get("sections"), manifest.get("block_decisions")
    if not isinstance(sections, list) or not isinstance(blocks, list): return tuple(dict.fromkeys(errors + ["rows_invalid"]))
    section_ids = [s.get("section_id") for s in sections if isinstance(s, dict)]
    if len(section_ids) != len(sections) or len(set(section_ids)) != len(section_ids): errors.append("section_id_invalid")
    allowed = {"selected_for_review", "candidate_not_reviewed", "unmapped", "structural_only"} if stage == "evidence" else {"card_selected", "reviewed_no_card", "candidate_not_reviewed", "unmapped", "structural_only"}
    previous = -1
    for section in sections:
        start, end = _span(section.get("source_span")) if isinstance(section, dict) else (-1, -1)
        if start < previous or start < 0 or end <= start or end > count: errors.append("section_span_invalid")
        if not isinstance(section, dict) or section.get("coverage_state") not in allowed: errors.append("section_state_invalid")
        previous = start
    block_ids = [b.get("coverage_block_id") for b in blocks if isinstance(b, dict)]
    if len(block_ids) != len(blocks) or len(set(block_ids)) != len(block_ids): errors.append("coverage_block_id_invalid")
    for block in blocks:
        start, end = _span(block.get("source_span")) if isinstance(block, dict) else (-1, -1)
        if start < 0 or end <= start or end > count: errors.append("block_span_invalid")
        if not isinstance(block, dict) or block.get("evidence_disposition") not in EVIDENCE_STATES: errors.append("evidence_disposition_invalid"); continue
        if (block.get("evidence_disposition") != "omitted_usage_limit") != bool(block.get("evidence_block_id")): errors.append("evidence_block_id_invalid")
        if block.get("section_id") not in set(section_ids): errors.append("section_reference_invalid")
        if not re.fullmatch(r"coverage-block:[0-9a-f]{64}", str(block.get("coverage_block_id") or "")): errors.append("coverage_block_id_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(block.get("source_text_sha256") or "")): errors.append("source_text_sha256_invalid")
        if not isinstance(block.get("candidate_occurrences"), int) or block["candidate_occurrences"] < 1: errors.append("candidate_occurrences_invalid")
        if stage == "producer" and block.get("producer_disposition") not in PRODUCER_STATES: errors.append("producer_disposition_invalid")
    for section in sections:
        if set(section.get("matched_coverage_block_ids", [])) != {b.get("coverage_block_id") for b in blocks if b.get("section_id") == section.get("section_id")}: errors.append("section_block_links_invalid")
    if _forbidden(manifest): errors.append("source_payload_forbidden")
    if manifest.get("page_locator_status") != _page_status(sections): errors.append("page_locator_status_invalid")
    if manifest.get("analysis_coverage_status") != _analysis_status(str(stage), sections): errors.append("analysis_coverage_status_invalid")
    if manifest.get("summary") != _summary(sections, blocks): errors.append("summary_mismatch")
    return tuple(dict.fromkeys(errors))
