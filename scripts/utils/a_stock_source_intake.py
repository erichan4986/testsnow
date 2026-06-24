"""Structured A-share source intake helpers.

This module provides deterministic adapters for A-share data sources. It is
intentionally pure: no network or browser calls are made at module load time.
All akshare dependencies are lazy-imported inside the functions that use them.
"""

from __future__ import annotations

import logging
import hashlib
import json
import random
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


logger = logging.getLogger(__name__)


DEFAULT_CNINFO_CATEGORIES = [
    "年度报告",
    "季度报告",
    "业绩预告",
    "权益分派",
    "投资者关系活动",
    "风险提示",
]

_CATEGORY_ALIASES = {
    "年报": ["年报", "年度报告"],
    "季报": ["季报", "季度报告"],
    "半年报": ["半年报", "半年度报告", "中报"],
    "月报": ["月报", "月度报告"],
}

_CNINFO_TITLE_COLUMN_OPTIONS = ["公告标题", "标题", "title"]
_CNINFO_TIME_COLUMN_OPTIONS = ["公告时间", "公告日期", "时间", "publish_time", "date"]
_CNINFO_URL_COLUMN_OPTIONS = ["公告链接", "链接", "url"]

_NEWS_TITLE_COLUMN_OPTIONS = ["新闻标题", "标题", "title"]
_NEWS_CONTENT_COLUMN_OPTIONS = ["新闻内容", "内容", "content", "summary"]
_NEWS_TIME_COLUMN_OPTIONS = ["发布时间", "时间", "publish_time", "date"]
_NEWS_SOURCE_COLUMN_OPTIONS = ["文章来源", "来源", "source"]
_NEWS_URL_COLUMN_OPTIONS = ["新闻链接", "链接", "url"]

_REPORT_TITLE_COLUMN_OPTIONS = ["title", "报告标题", "研报标题"]
_REPORT_DATE_COLUMN_OPTIONS = ["publishDate", "发布日期", "publish_date", "日期"]
_REPORT_ORG_COLUMN_OPTIONS = ["orgSName", "机构", "institution", "机构名称"]
_REPORT_INFO_CODE_COLUMN_OPTIONS = ["infoCode", "info_code"]
_REPORT_RATING_COLUMN_OPTIONS = ["emRatingName", "rating", "评级"]
_REPORT_EPS_COLUMN_OPTIONS = ["predictThisYearEps", "eps", "预测EPS"]
_REPORT_TARGET_PRICE_COLUMN_OPTIONS = ["targetPrice", "目标价", "predictNextYearPrice"]
_REPORT_STOCK_CODE_COLUMN_OPTIONS = [
    "code",
    "股票代码",
    "symbol",
    "stock_code",
    "stockCode",
    "secCode",
    "securityCode",
]
_REPORT_STOCK_NAME_COLUMN_OPTIONS = [
    "股票简称",
    "股票名称",
    "stockName",
    "securityName",
    "secName",
    "name",
]
_DEFAULT_DETAIL_CONTENT_CATEGORIES = ["业绩预告", "季度报告", "一季度报告", "三季度报告"]
_EASTMONEY_REPORT_API = "https://reportapi.eastmoney.com/report/list"
_EASTMONEY_STOCK_NEWS_API = "https://search-api-web.eastmoney.com/search/jsonp"
_DEFAULT_BROKER_RESEARCH_CACHE_ROOT = Path("data/raw/broker_research_reports")
_DEFAULT_RESEARCH_PDF_CACHE_DIR = Path("data/raw/research_reports/_downloads")
_PERIODIC_REPORT_SCHEMA_VERSION = "periodic_report_extractor.v1"
_PERIODIC_REPORT_USAGES = {
    "risk_disclosure",
    "management_view",
    "capital_action",
    "financial_forensics",
}

_EASTMONEY_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_EM_MIN_INTERVAL_SECONDS = 1.0
_em_session = None
_em_last_call = [0.0]


def _em_get(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 15):
    """Eastmoney request helper with serial throttling and session reuse."""
    try:
        import requests  # lazy import; disabled source intake should stay cheap
    except Exception as exc:  # pragma: no cover - environment failure
        raise RuntimeError(f"requests import failed: {exc}") from exc

    wait = _EM_MIN_INTERVAL_SECONDS - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))

    global _em_session
    if _em_session is None:
        _em_session = requests.Session()
        _em_session.headers.update({"User-Agent": _EASTMONEY_UA})

    request_headers = dict(headers or {})
    request_headers.setdefault("User-Agent", _EASTMONEY_UA)

    try:
        return _em_session.get(url, params=params, headers=request_headers, timeout=timeout)
    finally:
        _em_last_call[0] = time.time()


def _find_column(row: Dict[str, Any], options: List[str]) -> Optional[Any]:
    """Return the first matching column value from a row."""
    for key in options:
        if key in row:
            return row[key]
    return None


def _parse_publish_time(value: Any) -> str:
    """Best-effort convert a timestamp-like value to ISO-ish string."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return ""
    return text


def _parse_date_value(value: Any) -> Optional[date]:
    text = _parse_publish_time(value)
    if not text:
        return None
    text = text[:10].replace("/", "-")
    try:
        year, month, day = text.split("-")
        return date(int(year), int(month), int(day))
    except Exception:
        return None


def _today_yyyymmdd(today: Optional[date] = None) -> str:
    d = today or date.today()
    return d.strftime("%Y%m%d")


def _start_yyyymmdd(lookback_days: int, today: Optional[date] = None) -> str:
    d = today or date.today()
    start = d - timedelta(days=lookback_days)
    return start.strftime("%Y%m%d")


def _today_iso(today: Optional[date] = None) -> str:
    d = today or date.today()
    return d.strftime("%Y-%m-%d")


def _start_iso(lookback_days: int, today: Optional[date] = None) -> str:
    d = today or date.today()
    start = d - timedelta(days=lookback_days)
    return start.strftime("%Y-%m-%d")


def _within_lookback(publish_time: str, lookback_days: int, today: Optional[date] = None) -> bool:
    parsed = _parse_date_value(publish_time)
    if parsed is None:
        return True
    end = today or date.today()
    start = end - timedelta(days=lookback_days)
    return start <= parsed <= end


def _matches_category(title: str, categories: List[str]) -> bool:
    if not categories:
        return True
    for cat in categories:
        if cat in title:
            return True
        for alias in _CATEGORY_ALIASES.get(cat, []):
            if alias in title:
                return True
    return False


def _should_read_detail_content(title: str, source_config: Dict[str, Any]) -> bool:
    """Return True when a cninfo detail page is short enough / relevant enough to read."""
    if not source_config.get("read_detail_content", False):
        return False
    categories = source_config.get("detail_content_categories") or _DEFAULT_DETAIL_CONTENT_CATEGORIES
    if not _matches_category(title, categories):
        return False
    # Avoid long annual and semi-annual reports in this phase unless explicitly
    # named in detail_content_categories with a non-default category.
    if "年度报告" in title or "半年度报告" in title:
        return "年度报告" in categories or "半年度报告" in categories
    return True


def _periodic_extraction_config(source_config: Dict[str, Any]) -> Dict[str, Any]:
    config = source_config.get("periodic_report_extraction") or {}
    return config if isinstance(config, dict) else {}


def _periodic_extraction_enabled(source_config: Dict[str, Any]) -> bool:
    return bool(_periodic_extraction_config(source_config).get("enabled", False))


def _is_long_periodic_report_title(title: str) -> bool:
    if not title:
        return False
    if "摘要" in title:
        return False
    return "年度报告" in title or "半年度报告" in title or "半年报" in title


def _periodic_excerpt_id(url: str, usage: str, index: int) -> str:
    digest = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:10]
    return f"{digest}-{usage}-{index}"


def _read_jina_content(url: str, timeout: int = 15, max_chars: int = 6000) -> Tuple[str, str]:
    """Read a web/detail URL via Jina Reader.

    Returns (content, status). Failures are reported as status strings and do
    not raise, so source intake can continue with title-only metadata.
    """
    if not url:
        return "", "missing_url"
    try:
        import urllib.request
        from urllib.parse import quote

        safe_url = quote(url.strip(), safe=":/?&=%#")
        jina_url = f"https://r.jina.ai/{safe_url}"
        req = urllib.request.Request(jina_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("[a_stock_source_intake] Jina detail read failed for %s: %s", url, exc)
        return "", "error"

    content = (content or "").strip()
    if not content:
        return "", "empty"
    if len(content) > max_chars:
        content = content[:max_chars].rstrip() + "..."
    return content, "ok"


def _extract_periodic_report_result(text: str, source_config: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if __name__.startswith("utils."):
            from .periodic_report_extractor import extract_periodic_report
        else:
            import importlib.util
            import sys

            module_path = Path(__file__).with_name("periodic_report_extractor.py")
            module_name = "_utils_periodic_report_extractor"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            extract_periodic_report = module.extract_periodic_report
    except Exception as exc:
        return {"schema_version": "", "items": [], "error": f"periodic extractor import failed: {exc}"}

    periodic_config = _periodic_extraction_config(source_config)
    try:
        return extract_periodic_report(
            text,
            industry=str(periodic_config.get("industry", "generic")),
        )
    except Exception as exc:
        return {"schema_version": "", "items": [], "error": f"periodic extractor failed: {exc}"}


def _periodic_excerpt_items(
    *,
    original_title: str,
    original_url: str,
    publish_time: str,
    extracted: Dict[str, Any],
) -> List[SynthesisItem]:
    if extracted.get("schema_version") != _PERIODIC_REPORT_SCHEMA_VERSION:
        return []

    notes = extracted.get("forensics_notes") or {}
    not_extracted = notes.get("not_extracted", []) if isinstance(notes, dict) else []
    items: List[SynthesisItem] = []
    for index, item in enumerate(extracted.get("items", []) or []):
        if not isinstance(item, dict):
            continue
        usage = str(item.get("usage", "")).strip()
        if usage not in _PERIODIC_REPORT_USAGES:
            continue
        evidence = str(item.get("evidence", "")).strip()
        if not evidence:
            continue
        title = str(item.get("title", usage)).strip() or usage
        interpretation = str(item.get("interpretation", "")).strip()
        content = evidence if not interpretation else f"{evidence}\n解读：{interpretation}"
        items.append(
            SynthesisItem(
                title=f"{original_title} | {title}",
                content=content,
                author="",
                source_platform="定期报告摘录",
                url=original_url,
                publish_time=publish_time,
                interaction_score=0,
                extra={
                    "source_credit": 75,
                    "source_type": "periodic_report_excerpt",
                    "source_domain": "cninfo.com.cn",
                    "verification_status": usage,
                    "knowledge_eligible": True,
                    "report_eligible": True,
                    "periodic_report_excerpt_id": _periodic_excerpt_id(original_url, usage, index),
                    "periodic_report_schema_version": extracted.get("schema_version", ""),
                    "periodic_report_type": extracted.get("report_type", "unknown"),
                    "periodic_report_audit_status": extracted.get("audit_status", "unknown"),
                    "periodic_report_usage": usage,
                    "periodic_report_severity": item.get("severity", "info"),
                    "periodic_report_not_extracted": list(not_extracted) if isinstance(not_extracted, list) else [],
                },
            )
        )
    return items


def _contains_stock_reference(text: str, stock_name: str, stock_code: str) -> bool:
    """Return True if text strongly references the target stock."""
    if not text:
        return False
    text = str(text)
    refs = [stock_name] if stock_name else []
    if stock_code:
        refs.append(stock_code)
        # Accept prefix-stripped code for Shanghai/Shenzhen prefixes.
        if len(stock_code) == 6:
            refs.append(stock_code)
    for ref in refs:
        if ref and ref in text:
            return True
    return False


def _contains_reference_value(value: Any, reference: str) -> bool:
    if value is None or not reference:
        return False
    return reference in str(value).strip()


def _report_row_matches_target(row: Dict[str, Any], stock_name: str, stock_code: str) -> bool:
    """Return True when a research report row clearly belongs to the target stock."""
    code_values = [
        row.get(key)
        for key in _REPORT_STOCK_CODE_COLUMN_OPTIONS
        if key in row and row.get(key) not in (None, "")
    ]
    if code_values and any(_contains_reference_value(value, stock_code) for value in code_values):
        return True

    stock_name_values = [
        row.get(key)
        for key in _REPORT_STOCK_NAME_COLUMN_OPTIONS
        if key in row and row.get(key) not in (None, "")
    ]
    if stock_name_values and any(_contains_reference_value(value, stock_name) for value in stock_name_values):
        return True

    title = _find_column(row, _REPORT_TITLE_COLUMN_OPTIONS) or ""
    return _contains_stock_reference(str(title), stock_name, stock_code)


def _iter_record_rows(data: Any):
    """Yield dict-like rows from a pandas DataFrame, list of dicts, or similar object."""
    if data is None:
        return
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                yield row
        return
    if hasattr(data, "iterrows"):
        for _, row in data.iterrows():
            yield dict(row)


def _strip_html(text: Any) -> str:
    value = "" if text is None else str(text)
    value = re.sub(r"<[^>]+>", "", value)
    return value.strip()


def _parse_jsonp_payload(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start + 1 : end])
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_research_pdf_filename(*parts: Any) -> str:
    raw = "_".join(str(part or "").strip() for part in parts if str(part or "").strip())
    raw = re.sub(r'[\\/:*?"<>|\s]+', "_", raw).strip("_")
    raw = raw[:160].strip("_") or "research_report"
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    return raw


def _safe_research_folder_name(stock_name: str, stock_code: str) -> str:
    raw = "_".join(part for part in [str(stock_name or "").strip(), str(stock_code or "").strip()] if part)
    raw = re.sub(r'[\\/:*?"<>|\s]+', "_", raw).strip("_")
    return raw[:120].strip("_") or "unknown_stock"


def _broker_research_stock_dir(stock_name: str, stock_code: str, source_config: Dict[str, Any]) -> Path:
    root = Path(source_config.get("broker_research_cache_root") or _DEFAULT_BROKER_RESEARCH_CACHE_ROOT)
    return root / _safe_research_folder_name(stock_name, stock_code)


def _research_pdf_cache_dir(stock_name: str, stock_code: str, source_config: Dict[str, Any]) -> Tuple[Path, Optional[Path]]:
    """Return PDF download dir and optional stock-level manifest path."""
    if source_config.get("pdf_cache_dir"):
        return Path(source_config["pdf_cache_dir"]), None
    if stock_name or stock_code:
        stock_dir = _broker_research_stock_dir(stock_name, stock_code, source_config)
        return stock_dir / "_downloads", stock_dir / "manifest.json"
    return _DEFAULT_RESEARCH_PDF_CACHE_DIR, None


def _record_research_pdf_manifest(
    *,
    manifest_path: Optional[Path],
    stock_name: str,
    stock_code: str,
    title: str,
    publish_time: str,
    institution: str,
    url: str,
    target: Path,
    content: bytes,
    status: str,
) -> None:
    if manifest_path is None:
        return
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {}
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    reports = payload.get("reports") if isinstance(payload.get("reports"), list) else []
    sha256 = hashlib.sha256(content).hexdigest() if content else ""
    entry = {
        "title": title,
        "institution": institution,
        "publish_time": publish_time[:10],
        "url": url,
        "path": str(target),
        "filename": target.name,
        "bytes": len(content),
        "sha256": sha256,
        "source": "eastmoney",
        "status": status,
        "added_by": "pipeline",
    }
    dedupe_key = sha256 or str(target)
    kept = []
    for report in reports:
        old_key = report.get("sha256") or report.get("path")
        if old_key != dedupe_key and report.get("url") != url and report.get("path") != str(target):
            kept.append(report)
    kept.append(entry)
    payload = {
        "schema_version": "broker_research_cache_manifest.v1",
        "stock_name": stock_name,
        "stock_code": stock_code,
        "reports": kept,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _download_research_report_pdf(
    *,
    url: str,
    title: str,
    publish_time: str,
    institution: str,
    source_config: Dict[str, Any],
    stock_name: str = "",
    stock_code: str = "",
    em_get=None,
) -> Dict[str, Any]:
    if not url:
        return {"pdf_download_status": "failed", "pdf_download_error": "missing PDF URL"}

    cache_dir, manifest_path = _research_pdf_cache_dir(stock_name, stock_code, source_config)
    filename = _safe_research_pdf_filename(publish_time[:10], institution, title)
    target = cache_dir / filename
    if target.exists() and target.stat().st_size > 0:
        content = target.read_bytes()
        _record_research_pdf_manifest(
            manifest_path=manifest_path,
            stock_name=stock_name,
            stock_code=stock_code,
            title=title,
            publish_time=publish_time,
            institution=institution,
            url=url,
            target=target,
            content=content,
            status="cached",
        )
        return {
            "pdf_download_status": "cached",
            "pdf_url": url,
            "pdf_local_path": str(target),
            "pdf_bytes": len(content),
            "pdf_sha256": hashlib.sha256(content).hexdigest(),
            **({"pdf_cache_manifest_path": str(manifest_path)} if manifest_path else {}),
        }

    request = em_get or _em_get
    timeout = int(source_config.get("pdf_timeout", source_config.get("timeout", 30)))
    min_bytes = int(source_config.get("pdf_min_bytes", 1024))
    try:
        response = request(
            url,
            params=None,
            headers={"Referer": "https://data.eastmoney.com/"},
            timeout=timeout,
        )
        status_code = int(getattr(response, "status_code", 200) or 200)
        content = bytes(getattr(response, "content", b"") or b"")
        if status_code != 200:
            return {
                "pdf_download_status": "failed",
                "pdf_url": url,
                "pdf_download_error": f"PDF HTTP {status_code}",
            }
        if len(content) < min_bytes or not content.lstrip().startswith(b"%PDF"):
            return {
                "pdf_download_status": "failed",
                "pdf_url": url,
                "pdf_download_error": f"invalid PDF payload ({len(content)} bytes)",
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        _record_research_pdf_manifest(
            manifest_path=manifest_path,
            stock_name=stock_name,
            stock_code=stock_code,
            title=title,
            publish_time=publish_time,
            institution=institution,
            url=url,
            target=target,
            content=content,
            status="ok",
        )
        return {
            "pdf_download_status": "ok",
            "pdf_url": url,
            "pdf_local_path": str(target),
            "pdf_bytes": len(content),
            "pdf_sha256": hashlib.sha256(content).hexdigest(),
            **({"pdf_cache_manifest_path": str(manifest_path)} if manifest_path else {}),
        }
    except Exception as exc:
        return {
            "pdf_download_status": "failed",
            "pdf_url": url,
            "pdf_download_error": str(exc),
        }


def _eastmoney_stock_news_param(keyword: str, page_size: int) -> str:
    return json.dumps(
        {
            "uid": "",
            "keyword": keyword,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": page_size,
                    "preTag": "",
                    "postTag": "",
                }
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _build_cninfo_url(row: Dict[str, Any]) -> str:
    url = _find_column(row, _CNINFO_URL_COLUMN_OPTIONS)
    if url:
        return str(url).strip()
    return ""


def _adapt_cninfo_announcements(
    stock_code: str,
    source_config: Dict[str, Any],
    stock_name: str = "",
    today: Optional[date] = None,
    ak_module: Optional[Any] = None,
) -> List[SynthesisItem] | Dict[str, Any]:
    """Fetch and convert cninfo announcements to high-credit SynthesisItems.

    Returns a list of items on success, or a dict {"status": "error", "error": ...}
    on failure so that per-source status can be recorded without blocking others.
    """
    ak = ak_module
    if ak is None:
        try:
            import akshare as ak  # lazy import
        except Exception as exc:
            return {"status": "error", "error": f"akshare import failed: {exc}"}

    if not hasattr(ak, "stock_zh_a_disclosure_report_cninfo"):
        return {"status": "unsupported_function", "error": "stock_zh_a_disclosure_report_cninfo not available"}

    lookback_days = int(source_config.get("lookback_days", 365))
    max_items = int(source_config.get("max_items", 12))
    categories = source_config.get("categories") or DEFAULT_CNINFO_CATEGORIES

    start_date = _start_yyyymmdd(lookback_days, today)
    end_date = _today_yyyymmdd(today)

    try:
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=stock_code,
            market="沪深京",
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        return {"status": "error", "error": f"cninfo fetch failed: {exc}"}

    if df is None or len(df) == 0:
        return []

    items = []
    announcement_count = 0
    detail_reads = 0
    max_detail_items = int(source_config.get("max_detail_items", 3))
    detail_timeout = int(source_config.get("detail_timeout", 15))
    detail_max_chars = int(source_config.get("detail_max_chars", 6000))
    periodic_config = _periodic_extraction_config(source_config)
    periodic_reads = 0
    periodic_chars_used = 0
    max_periodic_reports = int(periodic_config.get("max_reports", 1))
    periodic_max_chars = int(periodic_config.get("max_chars", 120000))
    periodic_max_total_chars = int(periodic_config.get("max_total_chars", periodic_max_chars))
    for _, row in df.iterrows():
        title = _find_column(row, _CNINFO_TITLE_COLUMN_OPTIONS) or ""
        title = str(title).strip()
        if not title:
            continue
        if categories and not _matches_category(title, categories):
            continue
        publish_time = _parse_publish_time(_find_column(row, _CNINFO_TIME_COLUMN_OPTIONS))
        url = _build_cninfo_url(row)
        content = title
        detail_content_status = "skipped"
        periodic_content = ""
        periodic_status = "skipped"
        if detail_reads < max_detail_items and _should_read_detail_content(title, source_config):
            detail_content, detail_content_status = _read_jina_content(
                url,
                timeout=detail_timeout,
                max_chars=detail_max_chars,
            )
            detail_reads += 1
            if detail_content:
                content = detail_content

        should_extract_periodic = (
            _periodic_extraction_enabled(source_config)
            and periodic_reads < max_periodic_reports
            and periodic_chars_used < periodic_max_total_chars
            and _is_long_periodic_report_title(title)
        )
        if should_extract_periodic:
            remaining_chars = max(0, periodic_max_total_chars - periodic_chars_used)
            read_chars = min(periodic_max_chars, remaining_chars) if remaining_chars else 0
            if read_chars > 0:
                periodic_content, periodic_status = _read_jina_content(
                    url,
                    timeout=detail_timeout,
                    max_chars=read_chars,
                )
                periodic_reads += 1
                periodic_chars_used += len(periodic_content or "")

        original_item = SynthesisItem(
            title=title,
            content=content,
            author="",
            source_platform="公告",
            url=url,
            publish_time=publish_time,
            interaction_score=0,
            extra={
                "source_credit": 95,
                "source_type": "exchange_announcement",
                "source_domain": "cninfo.com.cn",
                "verification_status": "confirmed_fact",
                "knowledge_eligible": True,
                "report_eligible": True,
                "detail_content_status": detail_content_status,
                "periodic_report_extraction_status": periodic_status,
                "raw_metadata": dict(row),
            },
        )
        items.append(original_item)
        announcement_count += 1

        if periodic_content:
            extracted = _extract_periodic_report_result(periodic_content, source_config)
            if extracted.get("schema_version") == _PERIODIC_REPORT_SCHEMA_VERSION:
                items.extend(
                    _periodic_excerpt_items(
                        original_title=title,
                        original_url=url,
                        publish_time=publish_time,
                        extracted=extracted,
                    )
                )
            else:
                original_item.extra["periodic_report_extraction_status"] = "schema_mismatch"

        if announcement_count >= max_items:
            break

    return items


def _adapt_eastmoney_stock_news(
    stock_code: str,
    source_config: Dict[str, Any],
    stock_name: str = "",
    today: Optional[date] = None,
    ak_module: Optional[Any] = None,
    em_get=None,
) -> List[SynthesisItem] | Dict[str, Any]:
    """Fetch and convert Eastmoney stock news to medium-credit SynthesisItems."""
    max_items = int(source_config.get("max_items", 10))
    lookback_days = int(source_config.get("lookback_days", 30))
    page_size = int(source_config.get("page_size", max_items))
    page_size = max(page_size, max_items)
    request = em_get or _em_get

    articles: List[Dict[str, Any]] = []
    keywords = [stock_code]
    if stock_name and stock_name not in keywords:
        keywords.append(stock_name)
    for keyword in keywords:
        try:
            response = request(
                _EASTMONEY_STOCK_NEWS_API,
                params={"cb": "jQuery_news", "param": _eastmoney_stock_news_param(keyword, page_size)},
                headers={"Referer": "https://so.eastmoney.com/"},
                timeout=int(source_config.get("timeout", 15)),
            )
            payload = _parse_jsonp_payload(getattr(response, "text", ""))
        except Exception as exc:
            return {"status": "error", "error": f"eastmoney stock news fetch failed: {exc}"}

        candidate_articles = payload.get("result", {}).get("cmsArticleWebOld", []) or []
        if isinstance(candidate_articles, list) and candidate_articles:
            articles = [row for row in candidate_articles if isinstance(row, dict)]
            break

    if not articles:
        return []

    items = []
    for row in articles:
        if not isinstance(row, dict):
            continue
        title = _strip_html(row.get("title", ""))
        content = _strip_html(row.get("content", ""))[:300]
        text = f"{title} {content}"
        if not _contains_stock_reference(text, stock_name, stock_code):
            continue
        publish_time = _parse_publish_time(row.get("date", ""))
        if not _within_lookback(publish_time, lookback_days, today):
            continue
        source = row.get("mediaName", "") or "东方财富"
        url = row.get("url", "") or ""

        items.append(
            SynthesisItem(
                title=title,
                content=content,
                author=str(source),
                source_platform="新闻",
                url=str(url),
                publish_time=publish_time,
                interaction_score=0,
                extra={
                    "source_credit": 65,
                    "source_type": "mainstream_media",
                    "source_domain": "eastmoney.com",
                    "verification_status": "secondary_source",
                    "knowledge_eligible": True,
                    "report_eligible": True,
                    "raw_metadata": dict(row),
                },
            )
        )
        if len(items) >= max_items:
            break

    return items


def _fetch_eastmoney_reportapi_rows(
    stock_code: str,
    source_config: Dict[str, Any],
    em_get=None,
    today: Optional[date] = None,
) -> List[Dict[str, Any]] | Dict[str, Any]:
    """Fetch target-stock research reports from Eastmoney reportapi.

    This direct fetch is intentionally metadata-only: it does not download
    research PDFs, and requests is lazy-imported to keep disabled runs cheap.
    """
    max_pages = int(source_config.get("direct_max_pages", source_config.get("max_pages", 2)))
    timeout = int(source_config.get("timeout", 30))
    request = em_get or _em_get

    rows: List[Dict[str, Any]] = []
    lookback_days = int(source_config.get("lookback_days", 90))
    begin_time = source_config.get("begin_time") or _start_iso(lookback_days, today=today)
    end_time = source_config.get("end_time") or _today_iso(today=today)
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*",
            "pageSize": "100",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": begin_time,
            "endTime": end_time,
            "pageNo": str(page),
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": stock_code,
            "rcode": "",
            "p": str(page),
            "pageNum": str(page),
            "pageNumber": str(page),
        }
        try:
            response = request(
                _EASTMONEY_REPORT_API,
                params=params,
                headers={"Referer": "https://data.eastmoney.com/"},
                timeout=timeout,
            )
            payload = response.json()
        except Exception as exc:
            return {"status": "error", "error": f"eastmoney reportapi fetch failed: {exc}"}

        page_rows = payload.get("data") or []
        if not page_rows:
            break
        rows.extend(row for row in page_rows if isinstance(row, dict))
        total_page = payload.get("TotalPage", 1) or 1
        try:
            if page >= int(total_page):
                break
        except (TypeError, ValueError):
            break

    return rows


def _build_research_report_item(row: Dict[str, Any], fetch_method: str = "akshare") -> Optional[SynthesisItem]:
    title = _find_column(row, _REPORT_TITLE_COLUMN_OPTIONS) or ""
    title = str(title).strip()
    if not title:
        return None
    publish_time = _parse_publish_time(_find_column(row, _REPORT_DATE_COLUMN_OPTIONS))
    org = _find_column(row, _REPORT_ORG_COLUMN_OPTIONS) or ""
    info_code = _find_column(row, _REPORT_INFO_CODE_COLUMN_OPTIONS) or ""
    rating = _find_column(row, _REPORT_RATING_COLUMN_OPTIONS) or ""
    eps = _find_column(row, _REPORT_EPS_COLUMN_OPTIONS)
    target_price = _find_column(row, _REPORT_TARGET_PRICE_COLUMN_OPTIONS)

    url = ""
    if info_code:
        url = f"https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"

    metadata = {
        "rating": rating,
        "eps": eps,
        "target_price": target_price,
        "institution": org,
        "info_code": info_code,
        "fetch_method": fetch_method,
    }
    metadata = {k: v for k, v in metadata.items() if v not in (None, "")}

    return SynthesisItem(
        title=title,
        content=title,
        author=str(org),
        source_platform="研报",
        url=url,
        publish_time=publish_time,
        interaction_score=0,
        extra={
            "source_credit": 72,
            "source_type": "broker_research",
            "source_domain": "reportapi.eastmoney.com",
            "verification_status": "professional_observation",
            "knowledge_eligible": True,
            "report_eligible": True,
            "raw_metadata": dict(row),
            **metadata,
        },
    )


def _adapt_eastmoney_research_reports(
    stock_code: str,
    source_config: Dict[str, Any],
    stock_name: str = "",
    today: Optional[date] = None,
    ak_module: Optional[Any] = None,
    em_get=None,
) -> List[SynthesisItem] | Dict[str, Any]:
    """Fetch and convert Eastmoney research report rows to medium-credit SynthesisItems.

    Uses Eastmoney reportapi directly. No PDF download.
    """
    max_items = int(source_config.get("max_items", 8))

    items = []
    lookback_days = int(source_config.get("lookback_days", 90))
    download_pdfs = bool(source_config.get("download_pdfs", False))
    direct_rows = _fetch_eastmoney_reportapi_rows(stock_code, source_config, em_get=em_get, today=today)
    if isinstance(direct_rows, dict):
        return direct_rows
    for row in direct_rows:
        publish_time = _parse_publish_time(_find_column(row, _REPORT_DATE_COLUMN_OPTIONS))
        if not _within_lookback(publish_time, lookback_days, today):
            continue
        item = _build_research_report_item(row, fetch_method="eastmoney_reportapi")
        if item is None:
            continue
        if download_pdfs:
            item.extra.update(
                _download_research_report_pdf(
                    url=item.url,
                    title=item.title,
                    publish_time=item.publish_time,
                    institution=str(item.extra.get("institution", "")),
                    source_config=source_config,
                    stock_name=stock_name,
                    stock_code=stock_code,
                    em_get=em_get,
                )
            )
        items.append(item)
        if len(items) >= max_items:
            break

    return items


_SOURCE_ADAPTERS = {
    "cninfo_announcements": _adapt_cninfo_announcements,
    "eastmoney_stock_news": _adapt_eastmoney_stock_news,
    "eastmoney_research_reports": _adapt_eastmoney_research_reports,
    "eastmoney_global_news": None,  # disabled in Phase 1
}


def _collect_single_source(
    name: str,
    adapter,
    stock_code: str,
    source_config: Dict[str, Any],
    stock_name: str,
    today: Optional[date],
) -> Tuple[List[SynthesisItem], Dict[str, Any]]:
    """Run one adapter and return (items, status_dict)."""
    if not source_config.get("enabled", False):
        return [], {"status": "disabled", "count": 0, "error": ""}

    if adapter is None:
        return [], {"status": "unsupported_function", "count": 0, "error": f"{name} not implemented in Phase 1"}

    try:
        result = adapter(
            stock_code=stock_code,
            source_config=source_config,
            stock_name=stock_name,
            today=today,
        )
    except Exception as exc:
        return [], {"status": "error", "count": 0, "error": f"{name} adapter crashed: {exc}"}

    if isinstance(result, dict):
        return [], {"status": result.get("status", "error"), "count": 0, "error": result.get("error", "")}

    if not result:
        return [], {"status": "empty", "count": 0, "error": ""}

    return result, {"status": "ok", "count": len(result), "error": ""}


def collect_a_stock_source_items(
    *,
    stock_name: str,
    stock_code: str,
    config: Dict[str, Any],
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Collect source-credit tagged SynthesisItems from configured A-share sources.

    Args:
        stock_name: Display name of the stock.
        stock_code: 6-digit A-share code.
        config: Per-stock source_intake configuration block.
        today: Optional date override for deterministic tests.

    Returns:
        Dict with keys: status, items, source_statuses, warnings.
    """
    if not config.get("enabled", False):
        return {
            "status": "disabled",
            "items": [],
            "source_statuses": {
                name: {"status": "disabled", "count": 0, "error": ""}
                for name in _SOURCE_ADAPTERS
            },
            "warnings": [],
        }

    a_stock_config = config.get("a_stock", {})
    warnings: List[str] = []
    all_items: List[SynthesisItem] = []
    source_statuses: Dict[str, Any] = {}

    for name, adapter in _SOURCE_ADAPTERS.items():
        source_config = a_stock_config.get(name, {"enabled": False})
        items, status = _collect_single_source(
            name=name,
            adapter=adapter,
            stock_code=stock_code,
            source_config=source_config,
            stock_name=stock_name,
            today=today,
        )
        source_statuses[name] = status
        if isinstance(items, list):
            all_items.extend(items)
        if status["status"] not in ("ok", "disabled", "empty"):
            warnings.append(f"[{name}] {status['status']}: {status['error']}")

    status = "ok" if any(s["status"] == "ok" for s in source_statuses.values()) else "empty"
    if warnings:
        status = "partial"

    return {
        "status": status,
        "items": all_items,
        "source_statuses": source_statuses,
        "warnings": warnings,
    }
