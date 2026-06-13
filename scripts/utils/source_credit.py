"""Deterministic source-credit scoring for evidence items.

This module is intentionally pure: it performs no network, browser, subprocess,
or LLM calls. It derives source credibility solely from URL, platform name,
author, and raw metadata.

Source-credit is independent from content quality. A high-credit source may
still be filtered out by content-quality gates elsewhere.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourceCreditResult:
    """Immutable result of source-credit scoring.

    Fields:
        source_type: categorical source class (e.g. exchange_announcement).
        source_domain: normalized domain extracted from URL, or empty string.
        source_credit: numeric credibility score (0-100).
        verification_status: high-level trust label.
        credit_reasons: human-readable reasons for the assigned credit.
        knowledge_eligible: whether the item may enter the knowledge base.
        report_eligible: whether the item may appear in report evidence sections.
    """

    source_type: str
    source_domain: str
    source_credit: int
    verification_status: str
    credit_reasons: List[str]
    knowledge_eligible: bool
    report_eligible: bool


# ---------------------------------------------------------------------------
# Domain / platform constants
# ---------------------------------------------------------------------------

_EXCHANGE_DOMAINS: frozenset[str] = frozenset({
    "hkexnews.hk",
    "sse.com.cn",
    "szse.cn",
    "cninfo.com.cn",
})

_COMPANY_OFFICIAL_DOMAINS: frozenset[str] = frozenset({
    "blacksesame.com",
    "blacksesame.com.cn",
})

_MAINSTREAM_MEDIA_DOMAINS: frozenset[str] = frozenset({
    "eastmoney.com",
    "finance.eastmoney.com",
    "sina.com.cn",
    "finance.sina.com.cn",
    "stcn.com",
    "yicai.com",
    "caixin.com",
})

_INDUSTRY_MEDIA_DOMAINS: frozenset[str] = frozenset({
    "36kr.com",
    "jiemian.com",
    "leiphone.com",
})

_SOCIAL_PLATFORMS: frozenset[str] = frozenset({
    "zhihu", "知乎",
    "xueqiu", "雪球",
    "twitter", "x",
    "reddit",
    "bilibili", "哔哩哔哩",
    "weibo", "微博",
    "xiaohongshu", "小红书",
})

_SOCIAL_DOMAINS: frozenset[str] = frozenset({
    "zhihu.com",
    "xueqiu.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "bilibili.com",
    "weibo.com",
    "xiaohongshu.com",
    "xhslink.com",
})

_BROKER_RESEARCH_KEYWORDS: frozenset[str] = frozenset({
    "研报",
    "research",
    "broker",
    "broker_research",
    "report",
    "institution",
})

# Detection priority (highest to lowest). The first matching rule wins.
# exchange_announcement > company_ir > company_official > broker_research
# > mainstream_media > industry_media > social_discussion > unknown_web > missing_source

_VERIFICATION_STATUS_MAP: Dict[str, str] = {
    "exchange_announcement": "primary_source",
    "company_ir": "primary_source",
    "company_official": "primary_source",
    "broker_research": "professional_analysis",
    "mainstream_media": "secondary_source",
    "industry_media": "secondary_source",
    "social_discussion": "market_opinion",
    "unknown_web": "unverified",
    "missing_source": "unverified",
}

_CREDIT_SCORE_MAP: Dict[str, int] = {
    "exchange_announcement": 98,
    "company_ir": 88,
    "company_official": 85,
    "broker_research": 72,
    "mainstream_media": 65,
    "industry_media": 55,
    "social_discussion": 35,
    "unknown_web": 30,
    "missing_source": 10,
}

_KNOWLEDGE_ELIGIBLE_MAP: Dict[str, bool] = {
    "exchange_announcement": True,
    "company_ir": True,
    "company_official": True,
    "broker_research": True,
    "mainstream_media": True,
    "industry_media": True,
    "social_discussion": True,
    "unknown_web": True,
    "missing_source": False,
}

_REPORT_ELIGIBLE_MAP: Dict[str, bool] = {
    "exchange_announcement": True,
    "company_ir": True,
    "company_official": True,
    "broker_research": True,
    "mainstream_media": True,
    "industry_media": False,
    "social_discussion": False,
    "unknown_web": False,
    "missing_source": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """Return normalized domain or empty string for malformed input.

    Normalization rules:
    - accept URLs with or without scheme
    - lowercase host
    - strip leading www.
    - ignore query string and fragment
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    if not url:
        return ""

    # Reject strings that are clearly not valid URLs (e.g. free text).
    if " " in url:
        return ""

    if "://" not in url:
        url = "https://" + url

    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return ""
        host = host.lower()
        # Hostname must look like a real domain (contains a dot).
        if "." not in host:
            return ""
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _normalize_path(url: str) -> str:
    """Return lowercase path from URL, or empty string."""
    if not url or not isinstance(url, str):
        return ""
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
        return (parsed.path or "").lower()
    except Exception:
        return ""


def _is_company_ir(url: str, raw: Dict[str, Any]) -> bool:
    """Detect investor-relations source from raw metadata or URL path."""
    if raw.get("source_type") == "ir":
        return True

    path = _normalize_path(url)
    if not path:
        return False

    ir_indicators = ("/ir", "/investor", "/announcement")
    for indicator in ir_indicators:
        if path.startswith(indicator + "/") or path == indicator:
            return True
    return False


def _is_company_official(domain: str, raw: Dict[str, Any]) -> bool:
    """Detect official company source from known domain or explicit metadata."""
    if domain in _COMPANY_OFFICIAL_DOMAINS:
        return True

    # Explicit official metadata only helps when the domain is already known
    # to be official. It must not upgrade random blogs.
    if domain in _COMPANY_OFFICIAL_DOMAINS and (
        raw.get("is_official")
        or raw.get("source_type") == "official"
        or raw.get("account_type") == "official"
    ):
        return True

    return False


def _is_broker_research(source_platform: str, raw: Dict[str, Any]) -> bool:
    """Detect broker/institution research from platform name or raw metadata."""
    if source_platform and source_platform.lower() in _BROKER_RESEARCH_KEYWORDS:
        return True
    if raw.get("source_type") in _BROKER_RESEARCH_KEYWORDS:
        return True
    if raw.get("institution"):
        return True
    return False


def _is_social(source_platform: str, domain: str, raw: Dict[str, Any]) -> bool:
    """Detect social/forum discussion platform."""
    if source_platform and source_platform.lower() in _SOCIAL_PLATFORMS:
        return True
    if domain in _SOCIAL_DOMAINS or any(domain.endswith("." + d) for d in _SOCIAL_DOMAINS):
        return True
    raw_source_type = raw.get("source_type", "")
    if raw_source_type and raw_source_type.lower() in _SOCIAL_PLATFORMS:
        return True
    return False


def _build_reasons(
    source_type: str,
    domain: str,
    source_platform: str,
    raw: Dict[str, Any],
) -> List[str]:
    """Generate human-readable credit reasons."""
    reasons: List[str] = []

    if source_type == "exchange_announcement":
        reasons.append(f"交易所/监管公告域名: {domain}")
    elif source_type == "company_ir":
        if raw.get("source_type") == "ir":
            reasons.append("raw metadata 标识为投资者关系")
        else:
            reasons.append(f"URL 含投资者关系路径: {domain}")
    elif source_type == "company_official":
        reasons.append(f"公司官网域名: {domain}")
        if raw.get("user_provided_url"):
            reasons.append("用户显式提供官网URL")
    elif source_type == "broker_research":
        reasons.append("券商/机构研报来源")
    elif source_type == "mainstream_media":
        reasons.append(f"主流财经媒体域名: {domain}")
    elif source_type == "industry_media":
        reasons.append(f"行业媒体域名: {domain}")
    elif source_type == "social_discussion":
        platform_label = source_platform or domain or raw.get("platform", "")
        reasons.append(f"社交/讨论平台: {platform_label}")
    elif source_type == "unknown_web":
        reasons.append(f"未知来源网站: {domain or source_platform}")
    elif source_type == "missing_source":
        reasons.append("缺少URL、平台或来源元数据")

    return reasons


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_source_credit(
    *,
    url: str = "",
    source_platform: str = "",
    author: str = "",
    raw: Optional[Dict[str, Any]] = None,
) -> SourceCreditResult:
    """Assign deterministic source credit to an evidence item.

    Args:
        url: source URL, with or without scheme.
        source_platform: platform label, e.g. "知乎", "雪球", "AgentReach(web)".
        author: author name (reserved for future weighting, currently unused).
        raw: optional raw metadata dict from the original connector.

    Returns:
        SourceCreditResult with category, score, eligibility, and reasons.
    """
    raw = raw or {}
    domain = _normalize_url(url)

    # Priority 1: exchange / regulatory announcement
    if domain in _EXCHANGE_DOMAINS:
        source_type = "exchange_announcement"
    # Priority 2: company IR
    elif _is_company_ir(url, raw):
        source_type = "company_ir"
    # Priority 3: company official
    elif _is_company_official(domain, raw):
        source_type = "company_official"
    # Priority 4: broker research
    elif _is_broker_research(source_platform, raw):
        source_type = "broker_research"
    # Priority 5: mainstream media
    elif domain in _MAINSTREAM_MEDIA_DOMAINS:
        source_type = "mainstream_media"
    # Priority 6: industry media
    elif domain in _INDUSTRY_MEDIA_DOMAINS:
        source_type = "industry_media"
    # Priority 7: social discussion
    elif _is_social(source_platform, domain, raw):
        source_type = "social_discussion"
    # Priority 8: unknown web (has URL but no known class)
    elif domain:
        source_type = "unknown_web"
    # Priority 9: missing source
    else:
        source_type = "missing_source"

    reasons = _build_reasons(source_type, domain, source_platform, raw)

    return SourceCreditResult(
        source_type=source_type,
        source_domain=domain,
        source_credit=_CREDIT_SCORE_MAP[source_type],
        verification_status=_VERIFICATION_STATUS_MAP[source_type],
        credit_reasons=reasons,
        knowledge_eligible=_KNOWLEDGE_ELIGIBLE_MAP[source_type],
        report_eligible=_REPORT_ELIGIBLE_MAP[source_type],
    )
