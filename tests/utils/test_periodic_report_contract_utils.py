from __future__ import annotations

from decimal import Decimal
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from periodic_report_contract_utils import (  # noqa: E402
    dedupe_filing_evidence,
    finite_decimal,
)


def _evidence(source_doc: str, block_id: str) -> dict[str, str]:
    return {
        "source_doc": source_doc,
        "source_block_id": block_id,
        "source_excerpt_hash": (source_doc + block_id).encode().hex().ljust(64, "0")[:64],
        "source_block_hash": (block_id + source_doc).encode().hex().ljust(64, "0")[:64],
    }


def test_finite_decimal_converts_scalars_without_normalizing_caller_syntax() -> None:
    assert finite_decimal("12.50") == Decimal("12.50")
    assert finite_decimal(3) == Decimal("3")
    assert finite_decimal("1,000.00") is None
    assert finite_decimal("NaN") is None
    assert finite_decimal("Infinity") is None
    assert finite_decimal(None) is None


def test_dedupe_filing_evidence_merges_groups_by_identity_in_stable_order() -> None:
    later = _evidence("b.txt", "block-2")
    earlier = _evidence("a.txt", "block-1")

    assert dedupe_filing_evidence([later, earlier], [dict(earlier)]) == [
        earlier,
        later,
    ]
