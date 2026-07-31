"""Experimental HKEX periodic-report fetch/cache helper.

This module is helper-only. It does **not** register a pipeline skill, does
**not** render Source Intake sections, and does **not** write to
knowledge/reports.  It exposes pure helpers for resolving HKEX stock IDs,
finding annual/interim reports in HKEX title-search responses, building stable
cache paths, and (optionally) downloading PDF text.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode


HKEX_BASE_URL = "https://www1.hkexnews.hk"
_ACTIVE_STOCK_PATH = "/ncms/script/eds/activestock_sehk_c.json"
_TITLE_SEARCH_ENDPOINT = "/search/titleSearchServlet.do"
logger = logging.getLogger(__name__)


def resolve_hkex_stock_id(stock_code: str, active_stock_json_text: str) -> Optional[str]:
    """Resolve HKEX stockId from the active stock JSON text.

    HKEX active stock JSON looks like:

        {"count": N, "data": [{"stockId": "...", "stockCode": "02533", ...}]}

    Returns the ``stockId`` string or ``None`` if not found / parse error.
    """
    if not stock_code or not isinstance(active_stock_json_text, str):
        return None

    try:
        payload = json.loads(active_stock_json_text)
    except Exception as exc:
        logger.warning("failed to parse HKEX active stock JSON: %s", exc)
        return None

    if isinstance(payload, list):
        data = payload
    elif isinstance(payload, dict):
        data = payload.get("data") or []
    else:
        return None

    if not isinstance(data, list):
        return None

    normalized_code = stock_code.lstrip("0") or "0"
    for entry in data:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("stockCode") or entry.get("c") or "").lstrip("0") or "0"
        if code == normalized_code:
            stock_id = entry.get("stockId") or entry.get("i")
            if stock_id:
                return str(stock_id)
    return None


def _report_type_title_keywords(report_type: str, lang: str = "ZH") -> list[str]:
    """Return title keywords used to identify report_type from HKEX title."""
    lang = (lang or "ZH").upper()
    if report_type in ("annual", "annual_report"):
        if lang == "ZH":
            return ["年報", "年度報告", "年报", "年度报告", "annual report"]
        return ["annual report"]
    if report_type in ("interim", "interim_report"):
        if lang == "ZH":
            return ["中期報告", "中期报告", "中報", "中报", "interim report"]
        return ["interim report"]
    return [str(report_type).lower().replace("_", " ")]


def _report_type_search_title(report_type: str, lang: str = "ZH") -> str:
    lang = (lang or "ZH").upper()
    if report_type in ("annual", "annual_report"):
        return "年報" if lang == "ZH" else "annual report"
    if report_type in ("interim", "interim_report"):
        return "中期報告" if lang == "ZH" else "interim report"
    return str(report_type).lower().replace("_", " ")


def _disclosure_items(disclosure_json: Dict[str, Any]) -> list[Dict[str, Any]]:
    if not isinstance(disclosure_json, dict):
        return []
    data = disclosure_json.get("data")
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    result = disclosure_json.get("result")
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except Exception as exc:
            logger.warning("failed to parse HKEX title-search result JSON: %s", exc)
            return []
        if isinstance(parsed, list):
            return [entry for entry in parsed if isinstance(entry, dict)]
    return []


def find_hk_periodic_report(
    disclosure_json: Dict[str, Any],
    *,
    report_type: str = "annual",
    lang: str = "ZH",
    report_year: int | None = None,
) -> Optional[Dict[str, Any]]:
    """Find the first matching periodic report in HKEX titleSearchServlet JSON.

    The expected input shape is:

        {"count": N, "data": [{"title": "...", "date_time": "...", "file_link": "..."}]}

    Returns a dict with normalized fields including ``pdf_url``, or ``None`` if
    no match.
    """
    data = _disclosure_items(disclosure_json)
    keywords = _report_type_title_keywords(report_type, lang)

    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or entry.get("TITLE") or "")
        title_lower = title.lower()
        if not any(keyword in title_lower for keyword in keywords):
            continue
        if report_year is not None and str(int(report_year)) not in title:
            continue

        file_link = str(entry.get("file_link") or entry.get("FILE_LINK") or "").strip()
        pdf_url = ""
        if file_link:
            if file_link.startswith("http://") or file_link.startswith("https://"):
                pdf_url = file_link
            else:
                pdf_url = HKEX_BASE_URL.rstrip("/") + "/" + file_link.lstrip("/")

        return {
            "title": title,
            "date_time": str(entry.get("date_time") or entry.get("DATE_TIME") or ""),
            "file_link": file_link,
            "pdf_url": pdf_url,
            "raw": dict(entry),
        }

    return None


def build_hkex_title_search_url(
    stock_id: str,
    *,
    start_date: str,
    end_date: str,
    report_type: str = "annual",
    lang: str = "ZH",
) -> str:
    """Build HKEX titleSearchServlet URL.

    ``start_date`` and ``end_date`` must be ``YYYYMMDD``.
    ``report_type`` is used as the title keyword; ``annual`` becomes
    ``title=annual+report`` and ``interim`` becomes ``title=interim+report``.
    """
    lang = (lang or "ZH").upper()
    title = _report_type_search_title(report_type, lang)
    params = {
        "sortDir": "0",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": stock_id,
        "documentType": "-1",
        "title": title,
        "lang": lang,
        "from": start_date,
        "to": end_date,
    }
    return f"{HKEX_BASE_URL}{_TITLE_SEARCH_ENDPOINT}?" + urlencode(params, quote_via=quote)


def discover_hkex_periodic_report(
    *,
    stock_code: str,
    report_year: int,
    report_type: str = "annual",
    lang: str = "ZH",
    active_stock_loader: Any | None = None,
    title_search_loader: Any | None = None,
) -> Dict[str, Any]:
    """Discover an HKEX periodic report PDF URL for a stock/year.

    The discovery chain mirrors HKEX's title-search page: resolve ``stockId``
    from the official active-stock JSON, then query ``titleSearchServlet.do``.
    The function only returns metadata; it does not download PDFs.
    """
    active_loader = active_stock_loader or _load_hkex_active_stock_text
    active_text = active_loader(lang=lang)
    stock_id = resolve_hkex_stock_id(stock_code, active_text)
    if not stock_id:
        raise ValueError(f"No HKEX stockId found for {stock_code}")

    start_date, end_date = _hkex_report_window(int(report_year))
    search_url = build_hkex_title_search_url(
        stock_id,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
        lang=lang,
    )
    search_loader = title_search_loader or _load_hkex_title_search_json
    disclosure_json = search_loader(search_url)
    report = find_hk_periodic_report(
        disclosure_json,
        report_type=report_type,
        lang=lang,
        report_year=report_year,
    )
    if not report or not report.get("pdf_url"):
        raise ValueError(f"No HKEX {report_type} report found for {stock_code} {report_year}")

    return {
        "title": report["title"],
        "date": report["date_time"],
        "url": report["pdf_url"],
        "file_link": report["file_link"],
        "stock_code": _normalize_hk_stock_code(stock_code),
        "stock_id": stock_id,
        "market": "HK",
        "report_year": int(report_year),
        "report_type": "annual" if report_type in ("annual", "annual_report") else report_type,
        "lang": (lang or "ZH").upper(),
        "search_url": search_url,
    }


def build_hk_periodic_report_cache_path(
    cache_dir: str,
    *,
    stock_code: str,
    year: int,
    report_type: str,
    lang: str = "ZH",
) -> Path:
    """Return stable cache path for HK periodic report text.

    Example: ``data/raw/periodic_reports/hk/02533_2025_annual_jina.txt``
    """
    normalized_type = "annual" if report_type in ("annual", "annual_report") else "interim"
    normalized_lang = "zh" if (lang or "ZH").upper() == "ZH" else "en"
    filename = f"{stock_code}_{year}_{normalized_type}_{normalized_lang}_jina.txt"
    return Path(cache_dir) / "hk" / filename


def _hkex_report_window(report_year: int) -> tuple[str, str]:
    return f"{int(report_year)}0101", f"{int(report_year) + 1}0630"


def _normalize_hk_stock_code(stock_code: str) -> str:
    digits = re.sub(r"\D", "", str(stock_code or ""))
    return digits.zfill(5) if digits else str(stock_code or "")


def _load_hkex_active_stock_text(*, lang: str = "ZH") -> str:
    suffix = "_c" if (lang or "ZH").upper() == "ZH" else "_e"
    url = f"{HKEX_BASE_URL}/ncms/script/eds/activestock_sehk{suffix}.json"
    req = urllib.request.Request(url, headers=_hkex_headers())
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
        return response.read().decode("utf-8-sig", errors="ignore")


def _load_hkex_title_search_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=_hkex_headers())
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8-sig", errors="ignore"))


def _hkex_headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
    }


def _download_pdf_to_cache(
    pdf_url: str,
    cache_path: Path,
    *,
    retries: int = 2,
    delay_seconds: float = 1.0,
) -> None:
    """Download Jina Reader text for ``pdf_url`` to ``cache_path``.

    This function performs an HTTP GET.  Callers that need to avoid network
    access in tests should monkeypatch it.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        pdf_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    )
    attempts = max(1, int(retries or 1))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                cache_path.write_bytes(response.read())
            return
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            logger.warning(
                "HK periodic report download failed, retrying (%s/%s): %s",
                attempt,
                attempts,
                exc,
            )
            if delay_seconds > 0:
                time.sleep(delay_seconds)
    logger.warning("failed to download HK periodic report text: %s", last_error)
    if last_error:
        raise last_error


def _read_cached_pdf_text(cache_path: Path) -> str:
    """Read text from a cached PDF-derived file.

    For now this simply reads the cached text file.  A future implementation
    may parse the PDF bytes here.
    """
    return cache_path.read_text(encoding="utf-8")


def _jina_reader_url(pdf_url: str) -> str:
    if pdf_url.startswith("https://r.jina.ai/"):
        return pdf_url
    return "https://r.jina.ai/http://" + pdf_url


def fetch_hk_periodic_report_text(
    pdf_url: str,
    cache_path: Path,
    *,
    force_download: bool = False,
) -> Optional[str]:
    """Fetch HK periodic report text, downloading only if cache is missing.

    Returns the text content or ``None`` on failure.  Network access only
    happens when ``cache_path`` does not exist or ``force_download=True``.
    """
    try:
        if force_download or not cache_path.exists():
            _download_pdf_to_cache(_jina_reader_url(pdf_url), cache_path)
        return _read_cached_pdf_text(cache_path)
    except Exception as exc:
        logger.warning("failed to fetch HK periodic report text: %s", exc)
        return None
