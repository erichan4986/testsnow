"""Local periodic-report cache standardization helpers.

This module only standardizes already available local report files.  It does
not fetch network resources, open browsers, or write reports/Knowledge.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


SCHEMA_VERSION = "periodic_report_cache_meta.v1"
DEFAULT_REPORT_TYPE = "annual"


@dataclass(frozen=True)
class PeriodicReportCacheResult:
    text_path: Path
    meta_path: Path
    meta: Dict[str, Any]

    def to_cli_payload(self) -> Dict[str, Any]:
        return {
            "text_path": str(self.text_path),
            "meta_path": str(self.meta_path),
            "text_hash_sha256": self.meta.get("text_hash_sha256", ""),
            "text_chars": self.meta.get("text_chars", 0),
        }


def standard_cache_paths(
    *,
    stock_name: str,
    report_year: int,
    report_type: str = DEFAULT_REPORT_TYPE,
    cache_dir: str | Path,
) -> Tuple[Path, Path]:
    """Return standard text/meta cache paths for a periodic report."""
    label = _safe_filename(stock_name)
    report_type = _safe_filename(report_type or DEFAULT_REPORT_TYPE)
    stem = f"{label}_{int(report_year)}_{report_type}"
    cache_dir = Path(cache_dir)
    return (
        cache_dir / f"{stem}_jina.txt",
        cache_dir / f"{stem}_meta.json",
    )


def cache_periodic_report(
    *,
    stock_name: str,
    stock_code: str,
    report_year: int,
    market: str,
    input_path: str | Path,
    cache_dir: str | Path,
    report_type: str = DEFAULT_REPORT_TYPE,
    official_url: str = "",
    encoding: str = "utf-8",
) -> PeriodicReportCacheResult:
    """Register a local txt/pdf periodic report into the standard cache.

    TXT input is copied as text. PDF input is converted using local Python PDF
    readers when available. Empty extracted text is rejected explicitly.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Periodic report input not found: {input_path}")

    input_format = _detect_input_format(input_path)
    if input_format == "pdf":
        text = _extract_pdf_text(input_path)
        if not text.strip():
            raise ValueError(f"No text extracted from PDF: {input_path}")
    else:
        text = input_path.read_text(encoding=encoding, errors="ignore")

    if not text.strip():
        raise ValueError(f"No text found in periodic report input: {input_path}")

    text_path, meta_path = standard_cache_paths(
        stock_name=stock_name or stock_code,
        report_year=report_year,
        report_type=report_type,
        cache_dir=cache_dir,
    )
    text_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    text_path.write_text(normalized_text, encoding="utf-8")

    text_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    meta = {
        "schema_version": SCHEMA_VERSION,
        "stock_name": stock_name,
        "stock_code": stock_code,
        "market": str(market).upper(),
        "report_year": int(report_year),
        "report_type": report_type or DEFAULT_REPORT_TYPE,
        "input_format": input_format,
        "source_path": str(input_path),
        "official_url": official_url or "",
        "cached_text_path": str(text_path),
        "text_hash_sha256": text_hash,
        "text_chars": len(normalized_text),
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return PeriodicReportCacheResult(text_path=text_path, meta_path=meta_path, meta=meta)


def _detect_input_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    return "txt"


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as exc:
            try:
                import pdfplumber  # type: ignore
            except Exception as plumber_exc:
                raise RuntimeError(
                    "PDF text extraction requires pypdf, PyPDF2, or pdfplumber. "
                    "Install one of them, or pass a pre-extracted text file."
                ) from plumber_exc
            pages = []
            logging.getLogger("pdfminer").setLevel(logging.ERROR)
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            return "\n".join(pages)

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:\*\?\"<>\|\r\n\t]+", "_", str(value or "")).strip(" ._")
    return cleaned or "unknown"
