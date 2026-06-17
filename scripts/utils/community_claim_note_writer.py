"""Write conservative low-credit claim notes from cached community posts.

This module is intentionally local-only: it reads already cached post payloads
passed by the caller and writes a single social-discussion note that
``build_claim_verification_plan`` can consume as low-credit claims.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


_NOISE_PATTERNS = (
    "扫码下载雪球App",
    "购买雪球币",
    "应付：0 雪球币",
    "账号余额：0 雪球币",
    "可到钱包中进行查看",
)

_TOPIC_KEYWORDS = {
    "product_progress": ["A2000", "A2000U", "A2000X", "A1000", "C1236", "C1296", "芯片", "量产", "认证", "ASIL-D", "ISO 26262"],
    "customer_orders": ["比亚迪", "理想", "东风", "如祺", "上实", "客户", "定点", "供应链", "合作"],
    "competition": ["价格战", "竞争", "地平线", "Mobileye", "高通", "英伟达", "替代", "份额"],
    "earnings_business": ["营收", "亏损", "毛利率", "费用", "盈利", "利润", "收入"],
    "market_sentiment": ["减持", "做空", "退通", "资金", "解禁", "估值", "股价", "风险"],
}

_CLAIM_KEYWORDS = sorted({kw for values in _TOPIC_KEYWORDS.values() for kw in values}, key=len, reverse=True)

_FACT_PREDICATE_RE = re.compile(
    r"(?:"
    r"获得|获|通过|加入|达成|签署|定点|进入|供应链|搭载|量产|出货|并表|指引|"
    r"营收|收入|毛利率|亏损|盈利|利润|费用|成本|同比|增长|下降|下滑|承压|扩张|"
    r"减持|做空|退通|解禁|压力|风险|替代|价格战|竞争.*加剧|"
    r"达到|超过|低于|高于|少于|便宜|压缩|改善|收窄|扩大|"
    r"\d+(?:\.\d+)?%|\d+(?:\.\d+)?[亿万]|"
    r"(?:营收|收入|毛利率|亏损|盈利|利润|费用|成本|市值|估值|算力)[^，。；;]{0,20}\d|"
    r"为\d"
    r")"
)


def _clean_text(text: str) -> str:
    text = str(text or "")
    for noise in _NOISE_PATTERNS:
        text = text.replace(noise, "")
    text = re.sub(r"\$[^$()]{0,40}\([^)]+\)\$", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    normalized = str(text or "").replace("\n", " ")
    pieces = re.split(r"[。！？!?；;]\s*", normalized)
    return [_clean_text(p) for p in pieces if _clean_text(p)]


def _is_candidate_sentence(text: str, stock_name: str) -> bool:
    if len(text) < 12 or len(text) > 220:
        return False
    if any(noise in text for noise in _NOISE_PATTERNS):
        return False
    if stock_name not in text and not any(kw in text for kw in _CLAIM_KEYWORDS):
        return False
    if not any(kw in text for kw in _CLAIM_KEYWORDS):
        return False
    return bool(_FACT_PREDICATE_RE.search(text))


def _infer_topics(text: str) -> List[str]:
    topics = [topic for topic, keywords in _TOPIC_KEYWORDS.items() if any(kw in text for kw in keywords)]
    return topics or ["market_sentiment"]


def _interaction_score(post: Dict[str, Any]) -> int:
    return int(post.get("like_count") or 0) + int(post.get("comment_count") or 0) + int(post.get("repost_count") or 0)


def _post_sort_key(post: Dict[str, Any]) -> tuple:
    featured_rank = 0 if post.get("_track") == "featured" else 1
    return (featured_rank, -_interaction_score(post), str(post.get("url") or ""))


def extract_claims_from_cached_posts(
    posts: Sequence[Dict[str, Any]],
    stock_name: str,
    max_posts: int = 20,
    max_claims: int = 40,
    max_claims_per_post: int = 2,
) -> List[Dict[str, Any]]:
    """Extract conservative unverified claims from cached community posts."""
    claims: List[Dict[str, Any]] = []
    seen = set()

    for post in sorted(posts, key=_post_sort_key)[:max_posts]:
        post_claims = 0
        title = _clean_text(post.get("title", ""))
        content = post.get("content", "")
        source_url = str(post.get("url") or "")
        source_title = title[:160]

        for sentence in _split_sentences(content):
            if len(claims) >= max_claims:
                return claims
            if post_claims >= max_claims_per_post:
                break
            if not _is_candidate_sentence(sentence, stock_name):
                continue
            claim_text = sentence[:180].strip()
            if claim_text in seen:
                continue
            seen.add(claim_text)
            post_claims += 1
            claims.append({
                "claim_id": f"c{len(claims) + 1}",
                "claim_text": claim_text,
                "claim_status": "unverified_claim",
                "topics": _infer_topics(claim_text),
                "source_url": source_url,
                "source_title": source_title,
                "interaction_score": _interaction_score(post),
                "extracted_from": "cached_xueqiu_sentence",
            })

    return claims


def _render_frontmatter(data: Dict[str, Any]) -> str:
    if yaml is not None:
        return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120) + "---\n"
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in data.items() if k != "claims") + "\nclaims: []\n---\n"


def _render_note(stock_name: str, stock_code: str, claims: List[Dict[str, Any]], date_str: str) -> str:
    frontmatter = {
        "stock": stock_name,
        "code": stock_code,
        "source_type": "social_discussion",
        "source_credit": 35,
        "verification_status": "market_opinion",
        "claim_status": "unverified_claim",
        "category": "雪球缓存社区观点",
        "data_source": "cached_xueqiu",
        "source_platforms": ["雪球"],
        "collected_at": datetime.now().isoformat(),
        "claims": claims,
    }
    lines = [
        _render_frontmatter(frontmatter),
        f"# {stock_name} 雪球缓存社区观点 Claims ({date_str})",
        "",
        "> 来源为本地已缓存雪球/community 内容，保留为低信用待验证观点，不作为确认事实。",
        "",
        "## Claims",
    ]
    for claim in claims:
        lines.append(f"- **[unverified_claim]** {claim['claim_text']}")
        if claim.get("source_url"):
            lines.append(f"  - 来源: {claim['source_url']}")
    lines.append("")
    return "\n".join(lines)


def write_cached_community_claim_note(
    stock_name: str,
    stock_code: str,
    posts: Sequence[Dict[str, Any]],
    base_dir: Path,
    date_str: str,
    dry_run: bool = True,
    overwrite: bool = False,
    max_posts: int = 20,
    max_claims: int = 40,
) -> Dict[str, Any]:
    """Write one low-credit claim note for cached community posts."""
    claims = extract_claims_from_cached_posts(posts, stock_name, max_posts=max_posts, max_claims=max_claims)
    target = Path(base_dir) / "10-Stocks" / stock_name / f"{date_str}-雪球缓存社区claims.md"

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
