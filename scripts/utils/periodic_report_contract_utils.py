"""Small shared primitives for periodic-report compute contracts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


_EVIDENCE_KEYS = ("source_doc", "source_block_id", "source_excerpt_hash", "source_block_hash")


def finite_decimal(value: Any) -> Decimal | None:
    """Parse one scalar without applying caller-specific normalization."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def dedupe_filing_evidence(
    *groups: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return filing evidence once per stable four-field identity."""
    keyed = {
        tuple(str(row[key]) for key in _EVIDENCE_KEYS): dict(row)
        for group in groups
        for row in group
    }
    return [keyed[key] for key in sorted(keyed)]
