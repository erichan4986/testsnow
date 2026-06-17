"""Structured A-share source intake helpers.

This module provides deterministic adapters for A-share data sources. It is
intentionally pure: no network or browser calls are made at module load time.
All akshare dependencies are lazy-imported inside the functions that use them.
"""

from __future__ import annotations

import logging
import hashlib
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
_PERIODIC_REPORT_SCHEMA_VERSION = "periodic_report_extractor.v1"
_PERIODIC_REPORT_USAGES = {
    "risk_disclosure",
    "management_view",
    "capital_action",
    "financial_forensics",
}


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


def _today_yyyymmdd(today: Optional[date] = None) -> str:
    d = today or date.today()
    return d.strftime("%Y%m%d")


def _start_yyyymmdd(lookback_days: int, today: Optional[date] = None) -> str:
    d = today or date.today()
    start = d - timedelta(days=lookback_days)
    return start.strftime("%Y%m%d")


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
) -> List[SynthesisItem] | Dict[str, Any]:
    """Fetch and convert Eastmoney stock news to medium-credit SynthesisItems."""
    ak = ak_module
    if ak is None:
        try:
            import akshare as ak  # lazy import
        except Exception as exc:
            return {"status": "error", "error": f"akshare import failed: {exc}"}

    if not hasattr(ak, "stock_news_em"):
        return {"status": "unsupported_function", "error": "stock_news_em not available"}

    max_items = int(source_config.get("max_items", 10))

    try:
        df = ak.stock_news_em(symbol=stock_code)
    except Exception as exc:
        return {"status": "error", "error": f"eastmoney stock news fetch failed: {exc}"}

    if df is None or len(df) == 0:
        return []

    items = []
    for _, row in df.iterrows():
        title = _find_column(row, _NEWS_TITLE_COLUMN_OPTIONS) or ""
        title = str(title).strip()
        content = _find_column(row, _NEWS_CONTENT_COLUMN_OPTIONS) or ""
        content = str(content).strip()
        text = f"{title} {content}"
        if not _contains_stock_reference(text, stock_name, stock_code):
            continue
        publish_time = _parse_publish_time(_find_column(row, _NEWS_TIME_COLUMN_OPTIONS))
        source = _find_column(row, _NEWS_SOURCE_COLUMN_OPTIONS) or "东方财富"
        url = _find_column(row, _NEWS_URL_COLUMN_OPTIONS) or ""

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
                    "source_credit": 60,
                    "source_type": "news",
                    "source_domain": "finance.eastmoney.com",
                    "verification_status": "professional_observation",
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
) -> List[Dict[str, Any]] | Dict[str, Any]:
    """Fetch target-stock research reports from Eastmoney reportapi.

    This direct fallback is intentionally metadata-only: it does not download
    research PDFs, and requests is lazy-imported to keep disabled runs cheap.
    """
    try:
        import requests  # lazy import
    except Exception as exc:
        return {"status": "error", "error": f"requests import failed: {exc}"}

    max_pages = int(source_config.get("direct_max_pages", source_config.get("max_pages", 2)))
    timeout = int(source_config.get("timeout", 30))
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/",
        }
    )

    rows: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*",
            "pageSize": "100",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": source_config.get("begin_time", "2000-01-01"),
            "endTime": source_config.get("end_time", "2030-01-01"),
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
            response = session.get(_EASTMONEY_REPORT_API, params=params, timeout=timeout)
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
            "source_credit": 65,
            "source_type": "research_report",
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
) -> List[SynthesisItem] | Dict[str, Any]:
    """Fetch and convert Eastmoney research report rows to medium-credit SynthesisItems.

    Uses akshare.stock_research_report_em if available; otherwise falls back to a
    direct reportapi call wrapped in a lazy function. No PDF download.
    """
    max_items = int(source_config.get("max_items", 8))
    direct_fallback = source_config.get("direct_fallback", True)

    df = None
    ak = ak_module
    ak_error = ""
    if ak is None:
        try:
            import akshare as ak  # lazy import
        except Exception as exc:
            ak_error = f"akshare import failed: {exc}"

    if ak is not None and hasattr(ak, "stock_research_report_em"):
        try:
            df = ak.stock_research_report_em()
        except Exception as exc:
            ak_error = f"stock_research_report_em failed: {exc}"
    elif ak is not None:
        ak_error = "stock_research_report_em not available"

    items = []
    for row in _iter_record_rows(df):
        if not _report_row_matches_target(row, stock_name, stock_code):
            continue
        item = _build_research_report_item(row)
        if item is None:
            continue
        items.append(item)
        if len(items) >= max_items:
            break

    if not items and direct_fallback:
        direct_rows = _fetch_eastmoney_reportapi_rows(stock_code, source_config)
        if isinstance(direct_rows, dict):
            if ak_error:
                direct_rows["error"] = f"{ak_error}; {direct_rows.get('error', '')}".strip("; ")
            return direct_rows
        for row in direct_rows:
            item = _build_research_report_item(row, fetch_method="eastmoney_reportapi")
            if item is None:
                continue
            items.append(item)
            if len(items) >= max_items:
                break

    if not items and ak_error and not direct_fallback:
        status = "unsupported_function" if "not available" in ak_error else "error"
        return {"status": status, "error": ak_error}

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
