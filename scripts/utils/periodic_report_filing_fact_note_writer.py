"""Knowledge note writer for exact periodic-report filing facts (Phase B).

This module persists validated ``periodic_report_filing_fact`` entries from a
``PeriodicReportStructuredFactPack`` into standalone Knowledge Markdown notes.

Safety contract (Phase B, writer-only):

- It is **pure**: no network, browser, subprocess, LLM, or pipeline access. It
  reads a fact pack and writes Markdown under ``base_dir``.
- It uses a strict **allowlist**: only ``source_type == "periodic_report_filing_fact"``
  is ever written. Derived facts, risk signals, and material-layer summaries are
  excluded by construction -- they never match the allowlist.
- Notes are stamped ``knowledge_eligible: false`` regardless of the source value,
  matching the structured-facts contract that filing facts stay non-eligible
  until invalidation machinery exists. ``knowledge_fact_status: filing_fact`` and
  ``knowledge_persisted: true`` mark the note as a persisted structured fact.
- Path segments are sanitized and the final path is verified to stay inside the
  stock's ``filing_facts`` directory, so hostile stock/metric fields cannot
  escape the sandbox.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


FILING_FACT_SOURCE_TYPE = "periodic_report_filing_fact"
KNOWLEDGE_FACT_STATUS = "filing_fact"

_REQUIRED_FIELDS: Tuple[str, ...] = (
    "fact_id",
    "schema_version",
    "metric_key",
    "normalized_value",
    "period",
    "report_year",
    "report_type",
    "value_basis",
    "source_block_id",
    "evidence_refs",
    "source_excerpt",
)

_PLAIN_SCALAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


@dataclass
class FilingFactWritePlan:
    """Result of :func:`write_periodic_report_filing_fact_notes`.

    Attributes:
        written: facts written (or, in ``dry_run``, that would be written).
        skipped_existing: facts whose note already exists and was left untouched.
        refreshed: existing notes overwritten because ``refresh_existing=True``.
        filtered: entries rejected by source-type or field validation.
    """

    written: List[Dict[str, Any]] = field(default_factory=list)
    skipped_existing: List[Dict[str, Any]] = field(default_factory=list)
    refreshed: List[Dict[str, Any]] = field(default_factory=list)
    filtered: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------


def _safe_filename_segment(segment: str) -> str:
    """Return a filesystem-safe ASCII filename segment.

    Mirrors ``evidence_note_writer._safe_filename_segment`` deliberately so the
    two writers share the same proven, traversal-free sanitizer:

    - lowercase
    - replace non-alphanumeric characters with ``-``
    - collapse consecutive hyphens
    - strip leading/trailing hyphens
    """
    if not segment:
        return ""
    segment = str(segment).lower()
    segment = re.sub(r"[^a-z0-9\-]", "-", segment)
    segment = re.sub(r"-+", "-", segment)
    return segment.strip("-")


def _safe_dir_segment(segment: str, *, fallback: str = "unknown") -> str:
    """Return a path-segment that preserves CJK names but neutralizes traversal.

    Unlike :func:`_safe_filename_segment` this keeps non-ASCII characters (so
    Chinese stock names survive) while stripping path separators and parent-dir
    references.
    """
    seg = str(segment or "").replace("\x00", "")
    seg = re.sub(r"[\\/]+", "-", seg)  # path separators
    seg = re.sub(r"\.{2,}", "-", seg)  # parent-dir references
    seg = re.sub(r"\s+", "-", seg)
    seg = re.sub(r"-+", "-", seg)
    seg = seg.strip("-. ")
    return seg or fallback


# ---------------------------------------------------------------------------
# Frontmatter / note rendering
# ---------------------------------------------------------------------------


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if _PLAIN_SCALAR_RE.match(text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_frontmatter(entries: List[Tuple[str, Any]]) -> str:
    lines = ["---"]
    for key, value in entries:
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _source_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _refresh_frontmatter_hashes(
    note_text: str,
    *,
    source_excerpt_hash: str,
    source_block_hash: str = "",
) -> str:
    if not note_text.startswith("---\n"):
        return note_text
    parts = note_text.split("---", 2)
    if len(parts) != 3:
        return note_text

    frontmatter = parts[1].strip("\n")
    body = parts[2]
    lines = [
        line
        for line in frontmatter.splitlines()
        if not line.startswith("source_excerpt_hash:")
        and not (source_block_hash and line.startswith("source_block_hash:"))
    ]
    insert_at = next(
        (idx for idx, line in enumerate(lines) if line.startswith("knowledge_fact_status:")),
        len(lines),
    )
    hash_lines = [f"source_excerpt_hash: {_yaml_scalar(source_excerpt_hash)}"]
    if source_block_hash:
        hash_lines.append(f"source_block_hash: {_yaml_scalar(source_block_hash)}")
    lines[insert_at:insert_at] = hash_lines
    return "---\n" + "\n".join(lines) + "\n---" + body


def _render_note(
    fact: Dict[str, Any],
    collected_at: str,
    *,
    stock_name: str,
    stock_code: str,
) -> str:
    metric_key = str(fact.get("metric_key", ""))
    label = str(fact.get("label", ""))
    report_year = fact.get("report_year", "")
    report_type = str(fact.get("report_type", ""))
    normalized_value = str(fact.get("normalized_value", ""))
    unit = str(fact.get("unit", ""))
    evidence_refs = [str(ref) for ref in (fact.get("evidence_refs") or [])]
    excerpt = str(fact.get("source_excerpt", "")).strip() or "（无摘录）"
    source_excerpt_hash = str(fact.get("source_excerpt_hash") or _source_text_hash(excerpt))
    source_block_hash = str(fact.get("source_block_hash") or "")

    frontmatter_entries = [
        ("stock", stock_name),
        ("code", stock_code),
        ("source_type", FILING_FACT_SOURCE_TYPE),
        ("fact_id", str(fact.get("fact_id", ""))),
        ("schema_version", str(fact.get("schema_version", ""))),
        ("metric_key", metric_key),
        ("label", label),
        ("normalized_value", normalized_value),
        ("unit", unit),
        ("currency", str(fact.get("currency", ""))),
        ("period", str(fact.get("period", ""))),
        ("report_year", _coerce_int(report_year)),
        ("report_type", report_type),
        ("value_basis", str(fact.get("value_basis", ""))),
        ("confidence", str(fact.get("confidence", ""))),
        ("source_credit", _coerce_int(fact.get("source_credit", 75))),
        ("source_block_id", str(fact.get("source_block_id", ""))),
        ("evidence_refs", evidence_refs),
        ("source_excerpt_hash", source_excerpt_hash),
        ("knowledge_fact_status", KNOWLEDGE_FACT_STATUS),
        # Filing facts stay non-eligible until invalidation machinery exists.
        ("knowledge_eligible", False),
        ("knowledge_persisted", True),
        ("verified_by", []),
        ("conflicts_with", []),
        ("collected_at", collected_at),
    ]
    if source_block_hash:
        frontmatter_entries.insert(
            next(i for i, entry in enumerate(frontmatter_entries) if entry[0] == "knowledge_fact_status"),
            ("source_block_hash", source_block_hash),
        )
    frontmatter = _render_frontmatter(frontmatter_entries)

    body = [
        frontmatter,
        f"# {stock_name} {report_year} {report_type} {metric_key}",
        "",
        "## Fact",
        "",
        f"- 指标: {label} (`{metric_key}`)",
        f"- 数值: {normalized_value}",
        f"- 期间: {fact.get('period', '')}",
        f"- 口径: {fact.get('value_basis', '')}",
        "",
        "## Evidence",
        "",
        f"> {excerpt}",
        "",
        "## Guardrails",
        "",
        "- This note is an exact filing fact, not an LLM material-layer summary.",
        "- Derived facts and risk signals are not persisted in Phase B.",
        "",
    ]
    return "\n".join(body)


def _coerce_int(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _missing_required_field(fact: Dict[str, Any]) -> Optional[str]:
    for required in _REQUIRED_FIELDS:
        value = fact.get(required)
        if required == "evidence_refs":
            if not value or not isinstance(value, list):
                return required
            continue
        if value is None or value == "":
            return required
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_periodic_report_filing_fact_notes(
    stock_name: str,
    stock_code: str,
    fact_pack: Dict[str, Any],
    base_dir: Union[str, Path],
    collected_at: Optional[str] = None,
    dry_run: bool = False,
    refresh_existing: bool = False,
    refresh_frontmatter_only: bool = False,
) -> FilingFactWritePlan:
    """Write exact filing facts from a structured fact pack to Knowledge notes.

    Only ``fact_pack["filing_facts"]`` is read, and every item is re-asserted to
    have ``source_type == "periodic_report_filing_fact"``. Material-layer
    summaries, derived facts, and risk signals are filtered out.
    """
    plan = FilingFactWritePlan()
    collected = collected_at or ""

    facts_dir = (
        Path(base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "filing_facts"
    )
    facts_dir_resolved = facts_dir.resolve()

    filing_facts = fact_pack.get("filing_facts") or []
    for fact in filing_facts:
        if not isinstance(fact, dict):
            plan.filtered.append({
                "fact_id": "",
                "reason": "malformed entry is not a periodic_report_filing_fact dict",
            })
            continue

        fact_id = str(fact.get("fact_id", ""))
        source_type = str(fact.get("source_type", ""))

        # Allowlist: anything other than a filing fact is filtered out.
        if source_type != FILING_FACT_SOURCE_TYPE:
            plan.filtered.append({
                "fact_id": fact_id,
                "reason": f"source_type not periodic_report_filing_fact: {source_type or '<empty>'}",
            })
            continue

        missing = _missing_required_field(fact)
        if missing:
            plan.filtered.append({
                "fact_id": fact_id,
                "reason": f"missing required field: {missing}",
            })
            continue

        fact_stock_code = str(fact.get("stock_code", ""))
        if fact_stock_code and fact_stock_code != str(stock_code):
            plan.filtered.append({
                "fact_id": fact_id,
                "reason": f"stock_code mismatch: {fact_stock_code} != {stock_code}",
            })
            continue

        filename = "{year}-{rtype}-{metric}.md".format(
            year=_coerce_int(fact.get("report_year")),
            rtype=_safe_filename_segment(str(fact.get("report_type", ""))) or "unknown",
            metric=_safe_filename_segment(str(fact.get("metric_key", ""))) or "unknown",
        )
        target = facts_dir / filename

        # Defense-in-depth: never let a sanitized name escape the facts dir.
        if target.resolve().parent != facts_dir_resolved:
            plan.filtered.append({
                "fact_id": fact_id,
                "reason": "path escape blocked",
            })
            continue

        meta = {"fact_id": fact_id, "planned_path": str(target)}

        if target.exists():
            if not refresh_existing:
                meta["reason"] = "note already exists"
                plan.skipped_existing.append(meta)
                continue
            if not dry_run:
                if refresh_frontmatter_only:
                    excerpt = str(fact.get("source_excerpt", "")).strip() or "（无摘录）"
                    refreshed_text = _refresh_frontmatter_hashes(
                        target.read_text(encoding="utf-8"),
                        source_excerpt_hash=str(
                            fact.get("source_excerpt_hash") or _source_text_hash(excerpt)
                        ),
                        source_block_hash=str(fact.get("source_block_hash") or ""),
                    )
                    target.write_text(refreshed_text, encoding="utf-8")
                else:
                    target.write_text(
                        _render_note(
                            fact,
                            collected,
                            stock_name=stock_name,
                            stock_code=stock_code,
                        ),
                        encoding="utf-8",
                    )
            meta["reason"] = "refreshed_frontmatter_hashes" if refresh_frontmatter_only else "refreshed_existing"
            plan.refreshed.append(meta)
            continue

        if not dry_run:
            facts_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(
                _render_note(
                    fact,
                    collected,
                    stock_name=stock_name,
                    stock_code=stock_code,
                ),
                encoding="utf-8",
            )

        meta["reason"] = "written"
        plan.written.append(meta)

    return plan
