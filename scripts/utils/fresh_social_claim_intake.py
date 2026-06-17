"""Bounded fresh social low-credit claim intake.

This module is pure at import time: no network calls, no browser imports,
no optional CLI imports. It provides deterministic helpers to read explicit
community URLs through Jina Reader, apply a strict claim gate, and render
low-credit social-discussion notes.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence
from urllib.parse import urlparse

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_RAW_ITEMS = 20
DEFAULT_MAX_CLAIMS_PER_PROVIDER = 5
DEFAULT_MAX_CLAIMS = 10
DEFAULT_MAX_CLAIM_LENGTH = 180

_PROVIDER_STATUS_OK = "ok"
_PROVIDER_STATUS_EMPTY = "empty"
_PROVIDER_STATUS_ERROR = "error"
_PROVIDER_STATUS_RATE_LIMITED = "rate_limited"
_PROVIDER_STATUS_BLOCKED = "blocked"

_JINA_READER_BASE = "https://r.jina.ai/"


# ---------------------------------------------------------------------------
# URL / domain filter
# ---------------------------------------------------------------------------

# Domains that are never treated as fresh community sources.
_BLOCKED_DOMAINS = (
    "cninfo.com.cn",
    "reportapi.eastmoney.com",
    "pdf.dfcfw.com",
    "finance.sina.com.cn",
    "stcn.com",
    "cls.cn",
    "gelonghui.com",
)

# Eastmoney paths that are not the guba/forum area.
_BLOCKED_EASTMONEY_PATHS = (
    "/a/",
    "/news/",
    "/report/",
    "/reportapi/",
    "/research/",
    "/data/",
    "/stockdata/",
)

# Known community-like domains or path markers.
_ALLOWED_COMMUNITY_DOMAINS = (
    "guba.eastmoney.com",
    "xueqiu.com",
    "weibo.com",
    "m.weibo.cn",
    "weibo.cn",
)

_ALLOWED_COMMUNITY_PATH_MARKERS = (
    "/guba/",
    "/oa/",
    "/article/",
)


def _is_community_like_url(url: str) -> bool:
    """Return True if URL looks like a public community/forum page."""
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"

    # Hard-blocked news/official/research domains.
    for blocked in _BLOCKED_DOMAINS:
        if host == blocked or host.endswith(f".{blocked}"):
            return False

    # Eastmoney non-forum paths are news/research.
    if "eastmoney.com" in host:
        if host == "guba.eastmoney.com" or path.startswith("/oa/") or "/guba/" in path:
            return True
        for marker in _BLOCKED_EASTMONEY_PATHS:
            if path.startswith(marker) or marker in path:
                return False

    # Known community domains.
    for allowed in _ALLOWED_COMMUNITY_DOMAINS:
        if host == allowed or host.endswith(f".{allowed}"):
            return True

    # Generic community path markers are acceptable if host is not blocked.
    for marker in _ALLOWED_COMMUNITY_PATH_MARKERS:
        if marker in path:
            return True

    return False


def build_url_reader_url(target_url: str) -> str:
    """Build a Jina Reader URL for an explicit target URL."""
    return f"{_JINA_READER_BASE}{target_url}"


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_CITATION_RE = re.compile(r"\[\^?\d+\]")


def _strip_citations(text: str) -> str:
    return _CITATION_RE.sub("", text)


def _clean_text(text: str) -> str:
    text = str(text or "")
    text = _strip_citations(text)
    # Remove URLs.
    text = re.sub(r"https?://\S+", "", text)
    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    normalized = str(text or "").replace("\n", " ")
    pieces = re.split(r"[。！？!?；;]\s*", normalized)
    return [_clean_text(p) for p in pieces if _clean_text(p)]


# ---------------------------------------------------------------------------
# Claim gate
# ---------------------------------------------------------------------------

_COMMUNITY_MARKERS = (
    "我认为",
    "我觉得",
    "个人",
    "看法",
    "猜",
    "可能",
    "估计",
    "担心",
    "有观点",
    "帖子",
    "评论",
    "雪球",
    "股吧",
    "微博",
    "讨论",
    "社区",
)

_VERIFIABLE_PREDICATES = (
    "收入下降",
    "营收下降",
    "研发费用增长",
    "研发费用同比",
    "订单",
    "客户",
    "发货",
    "需求阶段性减少",
    "价格下调",
    "毛利率承压",
    "前十大股东",
    "持股比例",
    "股本",
    "散户",
    "竞争压力",
    "护城河",
    "绝对龙头",
    "唯一实现",
    "碳纤维",
    "减持",
    "解禁",
    "资金流出",
)

_NEGATIVE_SENTIMENT_MARKERS = (
    "起飞",
    "垃圾",
    "庄家",
    "韭菜",
    "玄学",
    "狂跌",
    "狂涨",
    "神奇",
)

_NEGATIVE_SEO_NEWS_MARKERS = (
    "点击阅读全文",
    "查看更多",
    "相关股票",
    "新浪财经",
    "证券时报",
    "东方财富网",
    "每经",
    "格隆汇",
    "公告编号",
    "证券代码",
    "本公司及董事会",
    "PDF",
    "研报",
)


def _has_stock_reference(text: str, stock_name: str, stock_code: str) -> bool:
    return stock_name in text or (stock_code and stock_code in text)


def _has_community_marker(text: str) -> bool:
    return any(marker in text for marker in _COMMUNITY_MARKERS)


def _has_verifiable_predicate(text: str) -> bool:
    return any(predicate in text for predicate in _VERIFIABLE_PREDICATES)


def _reject_negative_signals(text: str) -> bool:
    """Return True if text contains negative (reject) signals."""
    return any(marker in text for marker in _NEGATIVE_SENTIMENT_MARKERS + _NEGATIVE_SEO_NEWS_MARKERS)


def _is_claim_candidate(sentence: str, stock_name: str, stock_code: str) -> bool:
    if len(sentence) < 12 or len(sentence) > 220:
        return False
    if not _has_stock_reference(sentence, stock_name, stock_code):
        return False
    if not _has_community_marker(sentence):
        return False
    if not _has_verifiable_predicate(sentence):
        return False
    if _reject_negative_signals(sentence):
        return False
    return True


# ---------------------------------------------------------------------------
# Topic inference (lightweight, deterministic)
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS = {
    "product_progress": ["产品", "量产", "认证", "出货", "交付"],
    "customer_orders": ["客户", "订单", "发货", "供应链", "合作"],
    "earnings_business": ["营收", "收入", "毛利", "利润", "亏损", "费用", "研发"],
    "market_sentiment": ["减持", "解禁", "资金", "估值", "股价", "风险"],
}


def _infer_topics(text: str) -> List[str]:
    topics = [topic for topic, keywords in _TOPIC_KEYWORDS.items() if any(kw in text for kw in keywords)]
    return topics or ["market_sentiment"]


# ---------------------------------------------------------------------------
# Provider records
# ---------------------------------------------------------------------------


def _classify_provider_status(http_status: int) -> str:
    if http_status == 429:
        return _PROVIDER_STATUS_RATE_LIMITED
    if http_status in (403, 401):
        return _PROVIDER_STATUS_BLOCKED
    if http_status >= 500:
        return _PROVIDER_STATUS_ERROR
    if http_status == 200:
        return _PROVIDER_STATUS_OK
    if http_status == 0:
        return _PROVIDER_STATUS_ERROR
    # Other non-success codes are treated as errors (e.g., 404).
    return _PROVIDER_STATUS_ERROR if http_status >= 400 else _PROVIDER_STATUS_OK


def build_provider_record(
    url: str,
    raw_text: str = "",
    status: str = "",
    error: str = "",
    platform: str = "",
    stock_name: str = "",
    stock_code: str = "",
) -> Dict[str, Any]:
    """Build a provider record with extracted claims from raw text.

    If ``raw_text`` is provided, the record status is updated to ``empty``
    when no claims survive the gate.
    """
    if not _is_community_like_url(url):
        return {
            "url": url,
            "status": _PROVIDER_STATUS_BLOCKED,
            "platform": platform or _infer_platform(url),
            "claims": [],
            "error": error or "blocked_by_domain_filter",
        }

    claims: List[Dict[str, Any]] = []
    if raw_text:
        # Page-level negative signals: if the whole page reads like news/SEO,
        # do not extract any claims from it.
        if _reject_negative_signals(raw_text):
            return {
                "url": url,
                "status": _PROVIDER_STATUS_EMPTY,
                "platform": platform or _infer_platform(url),
                "claims": [],
                "error": "negative_signals_in_page",
            }

        sentences = _split_sentences(raw_text)
        for sentence in sentences:
            if not _is_claim_candidate(sentence, stock_name, stock_code):
                continue
            claims.append({
                "claim_text": sentence[:DEFAULT_MAX_CLAIM_LENGTH].strip(),
                "claim_status": "unverified_claim",
                "source_url": url,
                "source_platform": platform or _infer_platform(url),
                "topics": _infer_topics(sentence),
            })
            if len(claims) >= DEFAULT_MAX_CLAIMS_PER_PROVIDER:
                break

    effective_status = status
    if not effective_status:
        effective_status = _PROVIDER_STATUS_EMPTY if not claims else _PROVIDER_STATUS_OK

    return {
        "url": url,
        "status": effective_status,
        "platform": platform or _infer_platform(url),
        "claims": claims,
        "error": error,
    }


def _infer_platform(url: str) -> str:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    if "guba.eastmoney" in host:
        return "股吧"
    if "xueqiu" in host:
        return "雪球"
    if "weibo" in host:
        return "微博"
    return "external_social"


# ---------------------------------------------------------------------------
# Claim extraction across providers
# ---------------------------------------------------------------------------


def extract_claims_from_provider_records(
    provider_records: Sequence[Dict[str, Any]],
    stock_name: str,
    stock_code: str,
    max_claims: int = DEFAULT_MAX_CLAIMS,
) -> List[Dict[str, Any]]:
    """Extract and deduplicate claims from provider records.

    Each provider record may contain pre-extracted claims or raw text.
    """
    claims: List[Dict[str, Any]] = []
    seen = set()

    for record in provider_records:
        if not isinstance(record, dict):
            continue

        # Use pre-extracted claims if present; otherwise extract from raw text.
        record_claims = record.get("claims", [])
        if not record_claims and record.get("text"):
            rebuilt = build_provider_record(
                url=record.get("url", ""),
                raw_text=record.get("text", ""),
                status=record.get("status", ""),
                platform=record.get("platform", ""),
                stock_name=stock_name,
                stock_code=stock_code,
            )
            record_claims = rebuilt.get("claims", [])

        if not isinstance(record_claims, list):
            continue

        for claim in record_claims:
            if not isinstance(claim, dict):
                continue
            text = str(claim.get("claim_text") or "").strip()
            if not text:
                continue
            normalized = re.sub(r"\s+", "", text)
            if normalized in seen:
                continue
            seen.add(normalized)
            # Force metadata regardless of caller input.
            claim["claim_status"] = "unverified_claim"
            claim["source_url"] = claim.get("source_url") or record.get("url", "")
            claim["source_platform"] = claim.get("source_platform") or record.get("platform", "")
            claims.append(claim)
            if len(claims) >= max_claims:
                break
        if len(claims) >= max_claims:
            break

    # Assign sequential IDs.
    for idx, claim in enumerate(claims, start=1):
        claim["claim_id"] = f"c{idx}"

    return claims


# ---------------------------------------------------------------------------
# Note rendering and writing
# ---------------------------------------------------------------------------


def _render_frontmatter(data: Dict[str, Any]) -> str:
    if yaml is not None:
        return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120) + "---\n"
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in data.items() if k != "claims") + "\nclaims: []\n---\n"


def _render_note(stock_name: str, stock_code: str, claims: List[Dict[str, Any]], date_str: str) -> str:
    # Defensive: strip citations from every claim text before rendering.
    sanitized_claims = []
    for claim in claims:
        safe = dict(claim)
        safe["claim_text"] = _strip_citations(str(safe.get("claim_text") or "")).strip()
        sanitized_claims.append(safe)

    frontmatter = {
        "stock": stock_name,
        "code": stock_code,
        "source_type": "social_discussion",
        "source_credit": 30,
        "verification_status": "market_opinion",
        "claim_status": "unverified_claim",
        "category": "新鲜社媒低信用线索",
        "fresh": True,
        "collected_via": "fresh_social_smoke",
        "collected_at": datetime.now().isoformat(),
        "claims": sanitized_claims,
    }
    lines = [
        _render_frontmatter(frontmatter),
        f"# {stock_name} 新鲜外部社媒 Claims ({date_str})",
        "",
        "> 来源为 explicit 社区 URL 或站点列表读取的新鲜外部社区/社媒内容，保留为低信用待验证观点，不作为确认事实。",
        "",
        "## Claims",
    ]
    for claim in sanitized_claims:
        lines.append(f"- **[unverified_claim]** {claim['claim_text']}")
        if claim.get("source_url"):
            lines.append(f"  - 来源: {claim['source_url']}")
        if claim.get("source_platform"):
            lines.append(f"  - 平台: {claim['source_platform']}")
    lines.append("")
    return "\n".join(lines)


def write_fresh_social_claim_note(
    stock_name: str,
    stock_code: str,
    claims: Sequence[Dict[str, Any]],
    base_dir: Path,
    date_str: str,
    dry_run: bool = True,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Write one low-credit fresh social claim note."""
    claims = list(claims)
    target = Path(base_dir) / "10-Stocks" / stock_name / f"{date_str}-新鲜外部社媒claims.md"

    # Defensive: refuse to write any claim that is not unverified_claim.
    for claim in claims:
        if isinstance(claim, dict) and claim.get("claim_status") != "unverified_claim":
            raise ValueError("fresh social claims must use claim_status: unverified_claim")

    result = {
        "path": str(target),
        "claim_count": len(claims),
        "status": "dry_run" if dry_run else "written",
    }

    if not claims:
        result["status"] = "empty"
        return result
    if dry_run:
        return result
    if target.exists() and not overwrite:
        result["status"] = "skipped_existing"
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render_note(stock_name, stock_code, claims, date_str), encoding="utf-8")
    return result
