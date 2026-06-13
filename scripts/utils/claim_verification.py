"""Pure, dry-run claim verification framework.

Phase 4 reads high-credit evidence notes and low-credit legacy social notes,
builds deterministic claim candidates, and returns a structured verification
plan. It does not call LLMs, fetch URLs, run subprocesses, or write to the
knowledge base by default.

Trust direction is strictly one-way:
- high-credit evidence (source_credit >= 80) can verify or downgrade claims
- medium-credit evidence (55-79) can only support claims
- social/legacy notes (source_credit < 55) are always low-credit and never
  used to verify other claims
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

logger = logging.getLogger(__name__)

try:
    import yaml

    _YAML_AVAILABLE = True
except Exception:  # pragma: no cover - yaml may be absent in minimal envs
    yaml = None
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimCandidate:
    claim_id: str
    stock: str
    source_file: str
    source_type: str
    source_credit: int
    verification_status: str
    claim_status: str
    claim_text: str
    topics: List[str]
    url: str = ""
    title: str = ""
    source_platforms: List[str] = field(default_factory=list)
    extraction_method: str = ""


@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    action: str
    verified_by: List[str]
    conflicts_with: List[str]
    confidence: int
    reasons: List[str]


@dataclass
class ClaimVerificationPlan:
    stock: str
    high_credit_claims: List[ClaimCandidate]
    low_credit_claims: List[ClaimCandidate]
    verifications: List[ClaimVerification]
    skipped_files: List[Dict[str, str]]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SPECIFIC_TERMS = {
    "a2000u",
    "a2000x",
    "a1000",
    "soc",
    "自动驾驶",
    "adas",
    "noa",
    "理想",
    "东风",
    "如祺",
    "上实",
    "定点",
    "订单",
    "交付",
    "asil-d",
    "iso 26262",
    "认证",
    "获奖",
    "营收",
    "亏损",
    "毛利率",
    "同比",
    "环比",
    "机器人",
    "仿生机器人",
    "液冷",
    "储能",
    "热管理",
    "新能源",
}

_GENERIC_TERMS = {
    "芯片",
    "公告",
    "合作",
    "收入",
    "增长",
    "投资者",
    "业务",
    "布局",
    "产品",
}

_TOPIC_COMPATIBILITY = {
    "product_progress": {"customer_orders", "competition", "earnings_business", "market_sentiment"},
    "customer_orders": {"product_progress", "competition", "earnings_business", "market_sentiment"},
    "competition": {"product_progress", "customer_orders", "earnings_business", "market_sentiment"},
    "earnings_business": {"product_progress", "customer_orders", "competition", "market_sentiment"},
    "market_sentiment": {"product_progress", "customer_orders", "competition", "earnings_business"},
}


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def parse_frontmatter(path: Path) -> Tuple[Dict[str, Any], str]:
    """Parse Markdown frontmatter and return (metadata, body).

    Supports both YAML-style and JSON frontmatter inside ``---`` fences.
    Falls back to JSON parsing if PyYAML is unavailable. Never uses ``eval``.
    Raises ``ValueError`` for malformed frontmatter.
    """
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Malformed frontmatter in {path}")

    fm_text = parts[1].strip()
    body = parts[2]

    if not fm_text:
        return {}, body

    # JSON frontmatter
    if fm_text.startswith("{"):
        try:
            return json.loads(fm_text), body
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON frontmatter in {path}: {exc}")

    # YAML frontmatter
    if _YAML_AVAILABLE and yaml is not None:
        try:
            data = yaml.safe_load(fm_text)
        except Exception as exc:
            raise ValueError(f"Malformed YAML frontmatter in {path}: {exc}")
        if not isinstance(data, dict):
            raise ValueError(f"YAML frontmatter is not a mapping in {path}")
        return data, body

    raise ValueError(f"Cannot parse frontmatter in {path}: PyYAML unavailable and content is not JSON")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stable_claim_id(source_file: str, claim_text: str) -> str:
    key = f"{source_file}|{claim_text}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _normalize_source_platforms(meta: Dict[str, Any]) -> List[str]:
    platforms = _normalize_list(meta.get("source_platforms"))
    if not platforms:
        sp = meta.get("source_platform")
        if sp:
            platforms = [str(sp)]
    return platforms


def _extract_terms(text: str) -> Tuple[set, set]:
    """Return (specific_terms, generic_terms) found in text."""
    lowered = text.lower()
    specific = {term for term in _SPECIFIC_TERMS if term in lowered}
    generic = {term for term in _GENERIC_TERMS if term in lowered}
    return specific, generic


def _topic_overlap(topics_a: List[str], topics_b: List[str]) -> bool:
    if not topics_a or not topics_b:
        return True  # empty topics are treated as compatible
    set_a = set(topics_a)
    set_b = set(topics_b)
    if set_a & set_b:
        return True
    for ta in set_a:
        compatible = _TOPIC_COMPATIBILITY.get(ta, set())
        if set_b & compatible:
            return True
    return False


def _parse_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    # Extract YYYY-MM-DD or YYYY/MM/DD
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return ""


def _date_proximity(date_a: str, date_b: str) -> bool:
    """Return True if dates are within 30 days."""
    if not date_a or not date_b:
        return False
    try:
        from datetime import datetime

        da = datetime.strptime(date_a, "%Y-%m-%d")
        db = datetime.strptime(date_b, "%Y-%m-%d")
        return abs((da - db).days) <= 30
    except Exception:
        return False


def _build_claim_candidate(
    stock_name: str,
    source_file: str,
    meta: Dict[str, Any],
    claim: Dict[str, Any],
    extraction_method: str,
) -> ClaimCandidate:
    claim_text = ""
    if isinstance(claim, dict):
        claim_text = str(claim.get("claim_text") or claim.get("text") or "").strip()
    elif isinstance(claim, str):
        claim_text = claim.strip()

    source_type = str(meta.get("source_type") or "unknown_web")
    source_credit = int(meta.get("source_credit") or 0)
    verification_status = str(meta.get("verification_status") or "unknown")
    claim_status = ""
    if isinstance(claim, dict):
        claim_status = str(claim.get("claim_status") or "").strip()
    if not claim_status:
        claim_status = str(meta.get("claim_status") or "fact_candidate").strip()

    topics = []
    if isinstance(claim, dict):
        topics = _normalize_list(claim.get("topics"))
    if not topics:
        topics = _normalize_list(meta.get("topics"))

    return ClaimCandidate(
        claim_id=_stable_claim_id(source_file, claim_text),
        stock=stock_name,
        source_file=source_file,
        source_type=source_type,
        source_credit=source_credit,
        verification_status=verification_status,
        claim_status=claim_status,
        claim_text=claim_text,
        topics=topics,
        url=str(meta.get("url") or ""),
        title=str(meta.get("title") or ""),
        source_platforms=_normalize_source_platforms(meta),
        extraction_method=extraction_method,
    )


def _build_stub_candidate(
    stock_name: str,
    source_file: str,
    meta: Dict[str, Any],
) -> ClaimCandidate:
    title = str(meta.get("title") or "").strip()
    category = str(meta.get("category") or "").strip()
    display = title or category or stock_name
    claim_text = f"{display}：该社区笔记包含待验证观点，需用高信用来源核查。"

    return ClaimCandidate(
        claim_id=_stable_claim_id(source_file, claim_text),
        stock=stock_name,
        source_file=source_file,
        source_type="social_discussion",
        source_credit=int(meta.get("source_credit") or 35),
        verification_status=str(meta.get("verification_status") or "market_opinion"),
        claim_status="unverified_claim",
        claim_text=claim_text,
        topics=_normalize_list(meta.get("topics")),
        url=str(meta.get("url") or ""),
        title=title,
        source_platforms=_normalize_source_platforms(meta),
        extraction_method="legacy_social_stub",
    )


# ---------------------------------------------------------------------------
# Legacy social body claim extraction
# ---------------------------------------------------------------------------

_MAX_BODY_CLAIMS_PER_FILE = 8

_FIELD_CONFIG: List[Tuple[str, int, str]] = [
    ("reports", 5, "研报线索"),
    ("announcements", 5, "公告线索"),
    ("catalysts", 3, "催化线索"),
    ("key_risks", 3, "风险线索"),
    ("inferences", 3, "推断线索"),
    ("opinions", 3, "观点线索"),
    ("confirmed_facts", 3, "疑似事实线索"),
]

_FIELD_PRIORITY = {field: idx for idx, (field, _max, _label) in enumerate(_FIELD_CONFIG)}

_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "product_progress": ["机器人", "仿生机器人", "液冷", "储能", "热管理", "新能源", "产品", "业务", "布局"],
    "customer_orders": ["客户", "订单", "定点", "合作", "供应"],
    "earnings_business": ["业绩", "营收", "净利润", "毛利率", "盈利", "增长", "年报", "季报"],
    "market_sentiment": ["机构", "持仓", "减持", "资金", "风险", "分歧", "估值", "预期", "关注"],
}

_CATEGORY_TOPIC_FALLBACK: Dict[str, str] = {
    "最新研报": "earnings_business",
    "公司公告": "market_sentiment",
    "深度分析": "market_sentiment",
}


# Minimum Chinese/ASCII characters after cleanup.
_MIN_CLAIM_TEXT_LENGTH = 6


def _clean_bullet_text(text: str) -> str:
    """Clean and normalize a Markdown bullet line."""
    text = text.strip()
    # Remove leading Markdown list markers and indentation.
    while text and text[0] in "-*":
        text = text[1:].lstrip()
    # Remove wikilinks entirely.
    text = re.sub(r"\[\[.*?\]\]", "", text)
    # Remove inline emphasis markers.
    text = re.sub(r"(?<!\\)[*_]{1,2}", "", text)
    return text.strip()


def _is_useful_bullet(text: str) -> bool:
    """Return True if cleaned bullet text is worth extracting."""
    cleaned = _clean_bullet_text(text)
    if not cleaned:
        return False
    if cleaned.lower() in {"", "-", "*", "观望", "持有", "暂无"}:
        return False
    if cleaned == "AI分析暂缺":
        return False
    if re.fullmatch(r"\d+\s*条", cleaned):
        return False
    if re.fullmatch(r"[\s\-,*._#\[\]():;\\/|+=&%$@!~`?<>\"']+", cleaned):
        return False
    # Effective length after removing punctuation and whitespace.
    effective = re.sub(r"[\s\-,*._#\[\]():;\\/|+=&%$@!~`?<>\"']+", "", cleaned)
    if len(effective) < _MIN_CLAIM_TEXT_LENGTH:
        return False
    return True


def _infer_topics(text: str, category: str) -> List[str]:
    """Infer deterministic topics from claim text and category."""
    topics: List[str] = []
    for topic_key, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            topics.append(topic_key)
    if not topics and category in _CATEGORY_TOPIC_FALLBACK:
        topics.append(_CATEGORY_TOPIC_FALLBACK[category])
    if not topics:
        topics.append("market_sentiment")
    return topics


def _build_body_claim_candidate(
    stock_name: str,
    source_file: str,
    meta: Dict[str, Any],
    field_name: str,
    field_label: str,
    bullet_text: str,
) -> ClaimCandidate:
    clean_text = _clean_bullet_text(bullet_text)
    prefix = f"{stock_name}{field_label}："
    claim_text = f"{prefix}{clean_text}"
    category = str(meta.get("category") or "").strip()
    topics = _infer_topics(clean_text, category)

    return ClaimCandidate(
        claim_id=_stable_claim_id(source_file, claim_text),
        stock=stock_name,
        source_file=source_file,
        source_type="social_discussion",
        source_credit=min(int(meta.get("source_credit") or 35), 35),
        verification_status="market_opinion",
        claim_status="unverified_claim",
        claim_text=claim_text,
        topics=topics,
        url=str(meta.get("url") or ""),
        title=str(meta.get("title") or ""),
        source_platforms=_normalize_source_platforms(meta),
        extraction_method="legacy_social_body_rule",
    )


def _is_technical_note(meta: Dict[str, Any]) -> bool:
    """Return True if the note is a technical indicator note."""
    category = str(meta.get("category") or "").strip()
    data_source = str(meta.get("data_source") or "").strip()
    return category == "技术指标" or data_source == "mootdx+stockstats"


def _collect_field_bullets(body: str, field_name: str) -> List[str]:
    """Collect child bullets under a top-level field header."""
    bullets: List[str] = []
    collecting = False
    field_pattern = re.compile(rf"^\s*[-*]\s*\*\*{re.escape(field_name)}\*\*\s*:.*")

    for line in body.splitlines():
        # A new top-level field header stops collection.
        if re.match(r"^\s*[-*]\s*\*\*[a-zA-Z_]+\*\*\s*:.*", line) and not field_pattern.match(line):
            collecting = False
            continue

        if field_pattern.match(line):
            collecting = True
            continue

        if collecting:
            # Stop at the next Markdown heading.
            if re.match(r"^\s*#", line):
                collecting = False
                continue
            # Only collect indented child bullets.
            if re.match(r"^\s{2,}[-*]\s+", line):
                bullets.append(line)

    return bullets


def extract_legacy_social_claims_from_body(
    stock_name: str,
    meta: Dict[str, Any],
    body: str,
    source_file: str,
) -> List[ClaimCandidate]:
    """Return low-credit unverified claim candidates extracted from structured body bullets.

    Extracts from supported Markdown list fields such as ``reports``,
    ``announcements``, ``confirmed_facts``, etc. All returned candidates are
    forced to social-discussion / market-opinion / unverified_claim metadata.
    """
    if _is_technical_note(meta):
        return []

    category = str(meta.get("category") or "").strip()
    seen_texts: set = set()
    all_claims: List[ClaimCandidate] = []

    for field_name, max_count, field_label in _FIELD_CONFIG:
        bullets = _collect_field_bullets(body, field_name)
        count = 0
        for bullet in bullets:
            if not _is_useful_bullet(bullet):
                continue
            cleaned = _clean_bullet_text(bullet)
            if cleaned in seen_texts:
                continue
            if count >= max_count:
                break
            seen_texts.add(cleaned)
            all_claims.append(
                _build_body_claim_candidate(
                    stock_name=stock_name,
                    source_file=source_file,
                    meta=meta,
                    field_name=field_name,
                    field_label=field_label,
                    bullet_text=bullet,
                )
            )
            count += 1

    # Apply global cap after fixed field priority.
    if len(all_claims) > _MAX_BODY_CLAIMS_PER_FILE:
        all_claims = all_claims[:_MAX_BODY_CLAIMS_PER_FILE]

    return all_claims


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------


def _extract_evidence_claims(
    stock_name: str,
    evidence_dir: Path,
    skipped_files: List[Dict[str, str]],
) -> Tuple[List[ClaimCandidate], List[ClaimCandidate]]:
    """Return (high_credit_claims, medium_credit_claims)."""
    high: List[ClaimCandidate] = []
    medium: List[ClaimCandidate] = []

    if not evidence_dir.exists():
        return high, medium

    for path in sorted(evidence_dir.glob("*.md")):
        try:
            meta, _body = parse_frontmatter(path)
        except Exception as exc:
            logger.warning(f"Skipping evidence note {path}: {exc}")
            skipped_files.append({"path": str(path), "reason": "malformed_frontmatter"})
            continue

        claims = meta.get("claims")
        if not claims:
            continue

        source_file = str(path.relative_to(path.parents[3]) if len(path.parents) >= 3 else path)
        for claim in claims:
            candidate = _build_claim_candidate(
                stock_name=stock_name,
                source_file=source_file,
                meta=meta,
                claim=claim,
                extraction_method="evidence_frontmatter_claim",
            )
            if not candidate.claim_text:
                continue
            if candidate.source_credit >= 80:
                high.append(candidate)
            elif candidate.source_credit >= 55:
                medium.append(candidate)
            # source_credit < 55 evidence is ignored as a verification source

    return high, medium


def _extract_social_claims(
    stock_name: str,
    stock_dir: Path,
    skipped_files: List[Dict[str, str]],
) -> List[ClaimCandidate]:
    """Extract low-credit claims from legacy social notes."""
    low: List[ClaimCandidate] = []

    if not stock_dir.exists():
        return low

    for path in sorted(stock_dir.glob("*.md")):
        if path.name.lower() == "moc.md":
            skipped_files.append({"path": str(path), "reason": "moc_index"})
            continue

        try:
            meta, body = parse_frontmatter(path)
        except Exception as exc:
            logger.warning(f"Skipping social note {path}: {exc}")
            skipped_files.append({"path": str(path), "reason": "malformed_frontmatter"})
            continue

        source_type = str(meta.get("source_type") or "").lower()
        verification_status = str(meta.get("verification_status") or "").lower()

        is_social = source_type == "social_discussion" or verification_status == "market_opinion"
        if not is_social:
            skipped_files.append({"path": str(path), "reason": "unknown_source_type"})
            continue

        source_file = str(path.relative_to(path.parents[3]) if len(path.parents) >= 3 else path)

        if _is_technical_note(meta):
            skipped_files.append({"path": str(path), "reason": "technical_note_skipped"})
            continue

        claims = meta.get("claims")
        if claims:
            social_meta = dict(meta)
            social_meta.setdefault("source_type", "social_discussion")
            social_meta.setdefault("verification_status", "market_opinion")
            social_meta["claim_status"] = "unverified_claim"
            for claim in claims:
                candidate = _build_claim_candidate(
                    stock_name=stock_name,
                    source_file=source_file,
                    meta=social_meta,
                    claim=claim,
                    extraction_method="legacy_social_frontmatter_claim",
                )
                if candidate.claim_text:
                    low.append(candidate)
            continue

        body_claims = extract_legacy_social_claims_from_body(stock_name, meta, body, source_file)
        if body_claims:
            low.extend(body_claims)
        else:
            low.append(_build_stub_candidate(stock_name, source_file, meta))

    return low


# ---------------------------------------------------------------------------
# Verification matching
# ---------------------------------------------------------------------------


def _score_match(low: ClaimCandidate, source: ClaimCandidate) -> Tuple[int, List[str]]:
    """Return (score, reasons) for how well source supports/low-conflicts low."""
    if low.stock != source.stock:
        return 0, []

    if not _topic_overlap(low.topics, source.topics):
        return 0, []

    low_text = f"{low.title} {low.claim_text}"
    source_text = f"{source.title} {source.claim_text}"
    low_specific, low_generic = _extract_terms(low_text)
    source_specific, source_generic = _extract_terms(source_text)

    shared_specific = low_specific & source_specific
    shared_generic = low_generic & source_generic

    reasons: List[str] = []
    score = 0

    if shared_specific:
        score += 60
        reasons.append(f"specific terms: {', '.join(sorted(shared_specific))}")

    if shared_generic:
        score += 10
        reasons.append(f"generic terms: {', '.join(sorted(shared_generic))}")

    low_date = _parse_date(low.title) or _parse_date(getattr(low, "published_at", ""))
    source_date = _parse_date(source.title) or _parse_date(getattr(source, "published_at", ""))
    if _date_proximity(low_date, source_date):
        score += 10
        reasons.append("date proximity within 30 days")

    return score, reasons


def _verify_claim(
    low: ClaimCandidate,
    high_claims: List[ClaimCandidate],
    medium_claims: List[ClaimCandidate],
) -> ClaimVerification:
    best_high_score = 0
    best_high_reasons: List[str] = []
    verified_by: List[str] = []
    conflicts_with: List[str] = []

    specific_high_matches: List[Tuple[ClaimCandidate, int, List[str]]] = []
    generic_high_matches: List[Tuple[ClaimCandidate, int, List[str]]] = []

    for source in high_claims:
        score, reasons = _score_match(low, source)
        if score > 0:
            if any("specific terms" in r for r in reasons):
                specific_high_matches.append((source, score, reasons))
            else:
                generic_high_matches.append((source, score, reasons))
        if score > best_high_score:
            best_high_score = score
            best_high_reasons = reasons

    # Determine action
    if specific_high_matches:
        # Strong high-credit match
        top_source, top_score, top_reasons = max(specific_high_matches, key=lambda x: x[1])
        verified_by = [top_source.claim_id]
        confidence = min(70 + top_score // 5, 100)
        return ClaimVerification(
            claim_id=low.claim_id,
            action="verified",
            verified_by=verified_by,
            conflicts_with=[],
            confidence=confidence,
            reasons=top_reasons,
        )

    if generic_high_matches:
        # Weak generic-only high-credit match -> needs review
        top_source, _score, top_reasons = max(generic_high_matches, key=lambda x: x[1])
        return ClaimVerification(
            claim_id=low.claim_id,
            action="needs_review",
            verified_by=[top_source.claim_id],
            conflicts_with=[],
            confidence=0,
            reasons=top_reasons + ["generic-only match, needs review"],
        )

    # Medium-credit support
    best_medium_score = 0
    best_medium_reasons: List[str] = []
    best_medium_id = ""
    for source in medium_claims:
        score, reasons = _score_match(low, source)
        if score > best_medium_score:
            best_medium_score = score
            best_medium_reasons = reasons
            best_medium_id = source.claim_id

    if best_medium_score > 0 and any("specific terms" in r for r in best_medium_reasons):
        confidence = min(40 + best_medium_score // 5, 69)
        return ClaimVerification(
            claim_id=low.claim_id,
            action="supported",
            verified_by=[best_medium_id],
            conflicts_with=[],
            confidence=confidence,
            reasons=best_medium_reasons,
        )

    # No useful match
    return ClaimVerification(
        claim_id=low.claim_id,
        action="unverified",
        verified_by=[],
        conflicts_with=[],
        confidence=20,
        reasons=["no high or medium credit source with matching topic and terms"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_claim_verification_plan(
    stock_name: str,
    base_dir: Union[str, Path],
    dry_run: bool = True,
) -> ClaimVerificationPlan:
    """Build a dry-run claim verification plan for a stock.

    Args:
        stock_name: display name of the stock.
        base_dir: root of the knowledge base (e.g. ``knowledge/``).
        dry_run: if False, raises ``NotImplementedError`` because Phase 4
            does not support writeback.

    Returns:
        ``ClaimVerificationPlan`` with high/low claims and verifications.
    """
    if not dry_run:
        raise NotImplementedError("Phase 4 only supports dry_run=True")

    base_path = Path(base_dir)
    stock_dir = base_path / "10-Stocks" / stock_name
    evidence_dir = stock_dir / "evidence"

    skipped_files: List[Dict[str, str]] = []

    high_credit_claims, medium_credit_claims = _extract_evidence_claims(
        stock_name, evidence_dir, skipped_files
    )
    low_credit_claims = _extract_social_claims(stock_name, stock_dir, skipped_files)

    verifications: List[ClaimVerification] = []
    for low in low_credit_claims:
        verifications.append(_verify_claim(low, high_credit_claims, medium_credit_claims))

    return ClaimVerificationPlan(
        stock=stock_name,
        high_credit_claims=high_credit_claims,
        low_credit_claims=low_credit_claims,
        verifications=verifications,
        skipped_files=skipped_files,
    )


# ---------------------------------------------------------------------------
# Prompt-safe summary
# ---------------------------------------------------------------------------


def summarize_claim_verification_plan(
    plan: ClaimVerificationPlan,
    max_verified: int = 6,
    max_supported: int = 4,
    max_unverified: int = 4,
    max_chars: int = 2500,
) -> Dict[str, Any]:
    """Return a prompt-safe, non-citable claim verification summary.

    The returned dict is intended for LLM prompt context only. It strips all
    uncitable provenance metadata (urls, file paths, raw ids) and keeps only
    claim text, status bucket, safe resolved titles, confidence, and short reason.
    """
    verified: List[Dict[str, Any]] = []
    supported: List[Dict[str, Any]] = []
    unverified: List[Dict[str, Any]] = []
    needs_review: List[Dict[str, Any]] = []

    # Build a lookup from claim_id to safe title.
    title_by_id: Dict[str, str] = {}
    for candidate in plan.high_credit_claims + plan.low_credit_claims:
        title = str(getattr(candidate, "title", "") or "").strip()
        if not title:
            continue
        title_by_id[candidate.claim_id] = title

    def _resolve_titles(verified_by: List[str]) -> List[str]:
        titles: List[str] = []
        seen: set = set()
        for vid in verified_by:
            title = title_by_id.get(vid, "").strip()
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
        return titles

    def _truncate_text(text: str, limit: int = 200) -> str:
        text = str(text or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    action_buckets: Dict[str, List[Dict[str, Any]]] = {
        "verified": verified,
        "supported": supported,
        "needs_review": needs_review,
        "unverified": unverified,
    }

    low_by_id = {c.claim_id: c for c in plan.low_credit_claims}
    for v in plan.verifications:
        low = low_by_id.get(v.claim_id)
        if low is None:
            continue
        bucket = action_buckets.get(v.action)
        if bucket is None:
            bucket = unverified
        row: Dict[str, Any] = {
            "claim_text": _truncate_text(low.claim_text),
            "action": v.action,
        }
        if v.confidence:
            row["confidence"] = v.confidence
        if v.reasons:
            row["reason"] = _truncate_text("; ".join(v.reasons), 160)
        if v.action in ("verified", "supported"):
            titles = _resolve_titles(v.verified_by)
            if titles:
                row["verified_by_titles"] = titles
        bucket.append(row)

    def _cap(rows: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        return rows[:limit]

    verified = _cap(verified, max_verified)
    supported = _cap(supported, max_supported)
    unverified = _cap(unverified, max_unverified)
    needs_review = _cap(needs_review, max_unverified)

    summary = {
        "enabled": True,
        "stock": plan.stock,
        "counts": {
            "high_credit_claims": len(plan.high_credit_claims),
            "low_credit_claims": len(plan.low_credit_claims),
            "verified": sum(1 for v in plan.verifications if v.action == "verified"),
            "supported": sum(1 for v in plan.verifications if v.action == "supported"),
            "unverified": sum(1 for v in plan.verifications if v.action == "unverified"),
            "needs_review": sum(1 for v in plan.verifications if v.action == "needs_review"),
            "skipped_files": len(plan.skipped_files),
        },
        "verified_claims": verified,
        "supported_claims": supported,
        "unverified_claims": unverified,
        "needs_review_claims": needs_review,
    }

    # Enforce total character budget by trimming claim text and, if needed,
    # dropping lower-priority rows.
    text = str(summary)
    if len(text) > max_chars:
        # First reduce claim text length per row.
        for bucket_key in ("verified_claims", "supported_claims", "unverified_claims", "needs_review_claims"):
            for row in summary.get(bucket_key, []):
                row["claim_text"] = _truncate_text(row["claim_text"], 80)
                if "reason" in row:
                    row["reason"] = _truncate_text(row["reason"], 80)
        text = str(summary)
    while len(text) > max_chars:
        trimmed = False
        for bucket_key in ("needs_review_claims", "unverified_claims", "supported_claims", "verified_claims"):
            rows = summary.get(bucket_key, [])
            if rows:
                rows.pop()
                trimmed = True
                break
        if not trimmed:
            break
        text = str(summary)

    return summary


def claim_verification_plan_to_dict(plan: ClaimVerificationPlan) -> Dict[str, Any]:
    """Convert a ``ClaimVerificationPlan`` to a plain dict."""
    return asdict(plan)
