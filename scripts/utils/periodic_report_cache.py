"""Local periodic-report cache standardization helpers.

This module only standardizes already available local report files.  It does
not fetch network resources, open browsers, or write reports/Knowledge.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.request
from urllib.parse import parse_qs, quote, urlparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Tuple


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


def cache_periodic_report_from_url(
    *,
    stock_name: str,
    stock_code: str,
    report_year: int,
    market: str,
    url: str,
    cache_dir: str | Path,
    report_type: str = DEFAULT_REPORT_TYPE,
    downloader: Callable[[str], bytes] | None = None,
) -> PeriodicReportCacheResult:
    """Download a periodic report URL and register it into the standard cache.

    The downloaded source file is kept under ``cache_dir/_downloads`` for
    traceability, then the existing local-file cache path performs extraction
    and metadata writing.
    """
    if not str(url or "").strip():
        raise ValueError("Periodic report URL is required")

    cache_dir = Path(cache_dir)
    source_dir = cache_dir / "_downloads"
    source_dir.mkdir(parents=True, exist_ok=True)

    suffix = _source_suffix_from_url(url)
    source_name = (
        f"{_safe_filename(stock_name or stock_code)}_{int(report_year)}_"
        f"{_safe_filename(report_type or DEFAULT_REPORT_TYPE)}_source{suffix}"
    )
    source_path = source_dir / source_name
    download = downloader or _download_url_bytes
    payload = download(url)
    if not payload:
        raise ValueError(f"No bytes downloaded from periodic report URL: {url}")
    source_path.write_bytes(payload)

    return cache_periodic_report(
        stock_name=stock_name,
        stock_code=stock_code,
        report_year=report_year,
        market=market,
        input_path=source_path,
        cache_dir=cache_dir,
        report_type=report_type,
        official_url=url,
    )


def get_cninfo_market(code: str) -> str:
    """Return akshare/cninfo column label for A-share disclosures."""
    return "沪深京"


def discover_cninfo_annual_report(
    *,
    stock_code: str,
    report_year: int,
    disclosure_loader: Callable[[str, str], Any] | None = None,
) -> Dict[str, Any]:
    """Discover the official A-share annual report announcement via cninfo.

    This function only discovers metadata. It does not download PDFs.
    ``disclosure_loader`` is injectable for tests and should return an
    akshare-like DataFrame with ``to_dict("records")``.
    """
    code = _normalize_a_share_code(stock_code)
    market = get_cninfo_market(code)
    loader = disclosure_loader or _load_cninfo_disclosures
    start_date, end_date = _cninfo_annual_report_window(int(report_year))
    rows = _records_from_disclosure_frame(loader(code, market, start_date, end_date))

    candidates = []
    for row in rows:
        title = _first_present(row, ("公告标题", "title", "TITLE", "announcementTitle"))
        category = _first_present(row, ("公告类型", "category", "CATEGORY", "announcementType"))
        date = _first_present(row, ("公告日期", "公告时间", "date", "DATE", "announcementDate"))
        raw_url = str(_first_present(row, ("公告链接", "url", "URL", "adjunctUrl")) or "")
        url = _cninfo_download_url(raw_url, str(date or ""))
        title_text = str(title or "")
        category_text = str(category or "")
        if not _is_target_annual_report(title_text, category_text, int(report_year)):
            continue
        candidates.append({
            "title": title_text,
            "category": category_text,
            "date": str(date or ""),
            "url": url,
            "detail_url": raw_url if raw_url != url else "",
            "stock_code": code,
            "market": market,
            "report_year": int(report_year),
            "report_type": "annual",
        })

    if not candidates:
        raise ValueError(
            f"No annual report announcement found for {code} {report_year} on cninfo"
        )

    candidates.sort(key=_annual_report_candidate_sort_key)
    return candidates[0]


def _load_cninfo_disclosures(
    symbol: str,
    market: str,
    start_date: str = "",
    end_date: str = "",
) -> Any:
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "CNINFO discovery requires akshare. Install akshare or pass a local report file."
        ) from exc
    kwargs = {"symbol": symbol, "market": market}
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    return ak.stock_zh_a_disclosure_report_cninfo(**kwargs)


def _download_url_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        _sanitize_url_for_request(url),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def _records_from_disclosure_frame(frame: Any) -> list[dict]:
    if hasattr(frame, "to_dict"):
        records = frame.to_dict("records")
        return [dict(row) for row in records]
    if isinstance(frame, Iterable):
        return [dict(row) for row in frame]
    return []


def _cninfo_annual_report_window(report_year: int) -> tuple[str, str]:
    year = int(report_year)
    return f"{year}0101", f"{year + 1}0630"


def _cninfo_download_url(url: str, announcement_date: str = "") -> str:
    parsed = urlparse(str(url or ""))
    query = parse_qs(parsed.query)
    announcement_id = (query.get("announcementId") or [""])[0]
    if "cninfo.com.cn" not in parsed.netloc or not announcement_id:
        return _sanitize_url_for_request(url)

    date_text = str(announcement_date or "").strip()
    if not date_text:
        date_text = (query.get("announcementTime") or [""])[0]
    report_date = date_text.split()[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", report_date):
        return _sanitize_url_for_request(url)

    return f"http://static.cninfo.com.cn/finalpage/{report_date}/{announcement_id}.PDF"


def _sanitize_url_for_request(url: str) -> str:
    return quote(str(url or ""), safe=":/?&=%#")


def _is_target_annual_report(title: str, category: str, report_year: int) -> bool:
    combined = f"{title} {category}"
    if str(report_year) not in combined:
        return False
    if "年度报告" not in combined:
        return False
    if "半年度报告" in combined:
        return False
    if "摘要" in combined:
        return False
    if "英文" in combined or "取消" in combined or "更正" in combined:
        return False
    return True


def _annual_report_candidate_sort_key(row: Dict[str, Any]) -> tuple:
    title = str(row.get("title") or "")
    category = str(row.get("category") or "")
    url = str(row.get("url") or "")
    exact_title = title.endswith("年度报告") or title.endswith("年度報告")
    pdf_url = url.lower().endswith(".pdf")
    return (
        0 if exact_title else 1,
        0 if "年度报告" == category else 1,
        0 if pdf_url else 1,
        str(row.get("date") or ""),
        title,
    )


def _first_present(row: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return ""


def _detect_input_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    return "txt"


def _source_suffix_from_url(url: str) -> str:
    suffix = Path(urlparse(str(url)).path).suffix.lower()
    if suffix in {".pdf", ".txt"}:
        return suffix
    return ".pdf"


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


def _normalize_a_share_code(code: str) -> str:
    code = str(code or "").strip().upper()
    code = code.removeprefix("SH").removeprefix("SZ").removeprefix("BJ")
    if "." in code:
        code = code.split(".", 1)[0]
    return code
