"""Evidence note writer for Agent-Reach source-credit items.

This module converts already-quality-gated Agent-Reach ``SynthesisItem``
objects into standalone Markdown evidence notes in the knowledge base.

Important semantics (Phase 2):

- ``fact_candidate`` means the source is high-credit enough to become a fact
  candidate. It does **not** mean the claim has been independently verified.
- ``professional_analysis`` means professional/secondary analysis. It may
  contain conflicts of interest and still requires cross-source verification.
- ``unverified_claim`` means a hypothesis or low-credit claim. It must be
  retained for later verification but must not be treated as fact.

The module is intentionally pure: it performs no network, browser, subprocess,
or LLM calls. Source-credit fields are passed through directly from
``item.extra`` without recomputation.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

try:
    import yaml
except Exception:  # pragma: no cover - yaml is a standard dependency in this repo
    yaml = None

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from scripts.utils.source_adapter import SynthesisItem

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FOLLOW_UP_QUESTIONS: List[str] = [
    "该 claim 是否能在更高信用来源（交易所公告、公司 IR）中得到交叉验证？",
    "是否有时间更近、来源更权威的反向或补充信息？",
    "原始 URL 是否仍然可访问？",
]

_CONTENT_TRUNCATE_LENGTH = 800

# Fallback topic keywords used when the renderer classifier is unavailable.
_TOPIC_KEYWORDS: List[tuple] = [
    ("product_progress", ["产品", "芯片", "量产", "交付", "出货", "良率", "产能", "版本", "发布"]),
    ("customer_orders", ["客户", "定点", "订单", "合作", "供应商", "主机厂"]),
    ("competition", ["竞争", "对手", "同业", "替代", "英伟达", "高通", "地平线"]),
    ("earnings_business", ["财报", "营收", "收入", "利润", "毛利率", "指引", "同比", "环比", "亏损"]),
    ("market_sentiment", ["热度", "讨论", "舆情", "关注", "投资者", "机构", "评级", "观点"]),
]

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass
class EvidenceWritePlan:
    """Result of ``write_evidence_notes``.

    Attributes:
        written: items that would be / were written.
        skipped_existing: items whose canonical URL already exists in evidence/.
        filtered: items excluded by eligibility or source-credit rules.
    """

    written: List[Dict[str, Any]] = field(default_factory=list)
    skipped_existing: List[Dict[str, Any]] = field(default_factory=list)
    filtered: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _canonical_url(url: str) -> str:
    """Return a normalized canonical URL for deduplication.

    Normalization rules:
    - lowercase
    - strip leading ``www.``
    - ignore query string and fragment
    - remove trailing slash
    - strip common trailing page extensions (.html, .htm, .php, .aspx, .jsp)
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    if not url:
        return ""

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
        if host.startswith("www."):
            host = host[4:]
        if "." not in host:
            return ""
        path = (parsed.path or "").rstrip("/")
        # Strip common page extensions that do not affect content identity.
        for ext in (".html", ".htm", ".php", ".aspx", ".jsp"):
            if path.lower().endswith(ext):
                path = path[: -len(ext)]
                break
        path = path.rstrip("/")
        return f"{host}{path}"
    except Exception:
        return ""


def _canonical_key(item: SynthesisItem) -> str:
    """Return a stable canonical key for deduplication.

    Prefer canonical URL. If no usable URL exists, fall back to a hash of
    platform + title + publish_time. The fallback is intentionally less stable
    and may produce duplicates if those fields vary slightly across fetches.
    """
    canonical = _canonical_url(item.url)
    if canonical:
        return canonical

    fallback = "|".join([
        str(item.source_platform or ""),
        str(item.title or ""),
        str(item.publish_time or ""),
    ])
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


def _short_hash(item: SynthesisItem) -> str:
    """Return an 8-character hex hash for the filename."""
    key = _canonical_key(item)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def _safe_filename_segment(segment: str) -> str:
    """Return a filesystem-safe filename segment.

    - lowercase
    - replace non-alphanumeric characters with ``-``
    - collapse consecutive hyphens
    - strip leading/trailing hyphens
    """
    if not segment:
        return ""
    segment = segment.lower()
    segment = re.sub(r"[^a-z0-9\-]", "-", segment)
    segment = re.sub(r"-+", "-", segment)
    return segment.strip("-")


def _parse_date_to_yyyymmdd(value: str) -> Optional[str]:
    """Extract YYYYMMDD from a date/datetime string if possible."""
    if not value or not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    # Try common formats.
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue

    # Loose regex extraction of YYYY-MM-DD or YYYY/MM/DD.
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if match:
        year, month, day = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y%m%d")
        except ValueError:
            pass

    return None


def _format_filename_date(item: SynthesisItem, collected_at: Optional[str]) -> str:
    """Return the date prefix for the evidence note filename."""
    parsed = _parse_date_to_yyyymmdd(item.publish_time)
    if parsed:
        return parsed

    parsed = _parse_date_to_yyyymmdd(collected_at or "")
    if parsed:
        return parsed

    return "unknown-date"


def _build_filename(item: SynthesisItem, collected_at: Optional[str]) -> str:
    """Return the evidence note filename."""
    date_prefix = _format_filename_date(item, collected_at)
    source_type = _safe_filename_segment(item.extra.get("source_type", "")) or "unknown"
    domain = _safe_filename_segment(item.extra.get("source_domain", "")) or "no-domain"
    short_hash = _short_hash(item)
    return f"{date_prefix}-{source_type}-{domain}-{short_hash}.md"


def _find_unique_path(evidence_dir: Path, filename: str) -> Path:
    """Return a path that does not already exist, appending ``-1``, ``-2`` etc."""
    target = evidence_dir / filename
    if not target.exists():
        return target

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = evidence_dir / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _dedupe_existing(evidence_dir: Path) -> Dict[str, Path]:
    """Scan ``evidence_dir`` and map canonical URL keys to file paths.

    Parses YAML frontmatter of existing ``.md`` files and extracts
    ``canonical_url``. Files without frontmatter or without ``canonical_url``
    are ignored.
    """
    existing: Dict[str, Path] = {}
    if not evidence_dir.exists():
        return existing

    for path in evidence_dir.glob("*.md"):
        canonical = _extract_canonical_url_from_file(path)
        if canonical:
            existing[canonical] = path

    return existing


def _extract_canonical_url_from_file(path: Path) -> Optional[str]:
    """Read frontmatter from a Markdown file and return canonical_url if present."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_text = parts[1].strip()
    if not frontmatter_text:
        return None

    if yaml is None:
        return _extract_simple_frontmatter_value(frontmatter_text, "canonical_url")

    try:
        data = yaml.safe_load(frontmatter_text)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    return data.get("canonical_url") or None


def _extract_simple_frontmatter_value(frontmatter_text: str, key: str) -> Optional[str]:
    """Extract a top-level scalar from simple frontmatter without PyYAML."""
    prefix = f"{key}:"
    for line in frontmatter_text.splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        return value or None
    return None


def _classify_topics(item: SynthesisItem) -> List[str]:
    """Return deterministic topic labels for an item.

    First tries to reuse ``AgentReachEvidenceRenderer.classify_agent_reach_topic``.
    If the renderer cannot be imported or returns an empty value, falls back to
    a minimal internal keyword table so the writer remains self-contained.
    """
    try:
        from scripts.utils.reporter.sections.agent_reach_evidence_renderer import (
            classify_agent_reach_topic,
        )
        topic = classify_agent_reach_topic(item)
        if topic:
            return [topic]
    except Exception:
        pass

    text_parts = [
        str(item.title or ""),
        str(item.content or ""),
    ]
    text = " ".join(text_parts)

    for topic_key, keywords in _TOPIC_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return [topic_key]

    return ["to_verify"]


def _claim_status(source_credit: int) -> Optional[str]:
    """Map source_credit to claim_status tier.

    Returns ``None`` when the item should not be written to the knowledge base.
    """
    if source_credit >= 80:
        return "fact_candidate"
    if source_credit >= 55:
        return "professional_analysis"
    if source_credit >= 30:
        return "unverified_claim"
    return None


def _build_claim_stub(item: SynthesisItem, status: str) -> Dict[str, Any]:
    """Build a deterministic Phase 2 claim stub from title and excerpt."""
    title = str(item.title or "").strip()
    content = str(item.content or "").strip()

    # Use first sentence of content as excerpt, truncated.
    excerpt = ""
    if content:
        first_sentence_match = re.split(r"(?<=[。！？.!?])\s+", content)
        if first_sentence_match:
            excerpt = first_sentence_match[0].strip()
        if len(excerpt) > 200:
            excerpt = excerpt[:200].rstrip() + "..."

    parts = [p for p in (title, excerpt) if p]
    claim_text = "；".join(parts)
    if not claim_text:
        claim_text = "（无标题或摘要）"

    return {
        "claim_id": "c1",
        "claim_text": claim_text,
        "claim_status": status,
        "extracted_from": "title_and_excerpt",
    }


def _truncate_content_for_excerpt(content: str, max_length: int = _CONTENT_TRUNCATE_LENGTH) -> str:
    """Return the first ``max_length`` characters of content, preserving newlines."""
    if not content:
        return ""
    if len(content) <= max_length:
        return content
    return content[:max_length].rstrip() + "..."


def _render_frontmatter(data: Dict[str, Any]) -> str:
    """Render a dict as YAML frontmatter."""
    if yaml is None:
        return _render_simple_frontmatter(data)
    dumped = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    return f"---\n{dumped}---\n"


def _render_simple_frontmatter(data: Dict[str, Any]) -> str:
    """Render deterministic frontmatter for this module without PyYAML.

    This intentionally supports only the value shapes produced by
    ``_render_note``: scalars, lists of scalars, lists of shallow dicts, and
    empty lists. It avoids making PyYAML a hard dependency for evidence notes.
    """
    lines = ["---"]
    for key, value in data.items():
        lines.extend(_render_simple_yaml_entry(key, value))
    lines.append("---")
    return "\n".join(lines) + "\n"


def _render_simple_yaml_entry(key: str, value: Any) -> List[str]:
    if isinstance(value, list):
        if not value:
            return [f"{key}: []"]
        lines = [f"{key}:"]
        for item in value:
            if isinstance(item, dict):
                item_lines = list(item.items())
                if not item_lines:
                    lines.append("  - {}")
                    continue
                first_key, first_value = item_lines[0]
                lines.append(f"  - {first_key}: {_format_simple_yaml_scalar(first_value)}")
                for sub_key, sub_value in item_lines[1:]:
                    lines.append(f"    {sub_key}: {_format_simple_yaml_scalar(sub_value)}")
            else:
                lines.append(f"  - {_format_simple_yaml_scalar(item)}")
        return lines

    return [f"{key}: {_format_simple_yaml_scalar(value)}"]


def _format_simple_yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)

    text = str(value)
    if text == "":
        return '""'
    if _simple_yaml_plain_safe(text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _simple_yaml_plain_safe(text: str) -> bool:
    if text.strip() != text:
        return False
    if "\n" in text or "\r" in text:
        return False
    if text.startswith(("-", "?", ":", "{", "}", "[", "]", ",", "&", "*", "#", "!", "|", ">", "@", "`")):
        return False
    return not any(ch in text for ch in [": ", " #"])


def _render_note(
    item: SynthesisItem,
    stock_name: str,
    stock_code: str,
    collected_at: Optional[str],
    claim_status: str,
) -> str:
    """Render the full Markdown evidence note."""
    source_type = item.extra.get("source_type", "")
    source_domain = item.extra.get("source_domain", "")
    source_credit = item.extra.get("source_credit", 0)
    verification_status = item.extra.get("verification_status", "")
    credit_reasons = item.extra.get("credit_reasons", []) or []
    knowledge_eligible = bool(item.extra.get("knowledge_eligible", False))
    report_eligible = bool(item.extra.get("report_eligible", False))
    quality_score = item.extra.get("agent_reach_quality_score", 0)
    quality_action = item.extra.get("agent_reach_quality_action", "keep")

    topics = _classify_topics(item)
    claim = _build_claim_stub(item, claim_status)
    claims = [claim]

    frontmatter = {
        "stock": stock_name,
        "code": stock_code,
        "source_type": source_type,
        "source_domain": source_domain,
        "source_credit": int(source_credit),
        "verification_status": verification_status,
        "credit_reasons": list(credit_reasons),
        "knowledge_eligible": knowledge_eligible,
        "report_eligible": report_eligible,
        "url": item.url or "",
        "canonical_url": _canonical_url(item.url) or _canonical_key(item),
        "title": item.title or "",
        "published_at": item.publish_time or "",
        "collected_at": collected_at or "",
        "topics": topics,
        "claims": claims,
        "claim_status": claim_status,
        "verified_by": [],
        "conflicts_with": [],
        "source_platform": item.source_platform or "",
        "agent_reach_quality_score": int(quality_score),
        "agent_reach_quality_action": quality_action,
    }

    title = item.title or "（无标题）"
    excerpt = _truncate_content_for_excerpt(item.content or "")
    summary_parts = [p for p in (title, excerpt) if p]
    summary = "\n\n".join(summary_parts) if summary_parts else "（无内容）"

    body_lines = [
        _render_frontmatter(frontmatter),
        f"# {title}",
        "",
        "## 摘要",
        summary,
        "",
        "## 原始证据摘录",
        excerpt if excerpt else "（无摘录）",
        "",
        "## 初步 Claims",
        f"- **[{claim_status}]** {claim['claim_text']}",
        f"  - 来源: {source_domain or 'unknown'} ({source_type or 'unknown'})",
        f"  - 置信: {verification_status or 'unknown'}",
        "",
        "## 信用评分理由",
    ]
    if credit_reasons:
        for reason in credit_reasons:
            body_lines.append(f"- {reason}")
    else:
        body_lines.append("- （未提供）")

    body_lines.extend([
        "",
        "## 后续核查问题",
    ])
    for question in _FOLLOW_UP_QUESTIONS:
        body_lines.append(f"- {question}")

    return "\n".join(body_lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_evidence_notes(
    stock_name: str,
    stock_code: str,
    items: List[SynthesisItem],
    base_dir: Union[str, Path],
    collected_at: Optional[str] = None,
    dry_run: bool = False,
) -> EvidenceWritePlan:
    """Write quality-gated Agent-Reach items to knowledge-base evidence notes.

    Args:
        stock_name: display name of the stock, used in the directory path.
        stock_code: stock code, written into frontmatter.
        items: ``SynthesisItem`` objects that have already passed the Agent-Reach
            quality gate and are limited to ``keep`` or ``demote`` actions.
        base_dir: root of the knowledge base (e.g. ``knowledge/``).
        collected_at: ISO datetime string of when the evidence was collected.
        dry_run: if True, return the write plan without touching disk.

    Returns:
        ``EvidenceWritePlan`` with written, skipped_existing, and filtered lists.
    """
    plan = EvidenceWritePlan()
    evidence_dir = Path(base_dir) / "10-Stocks" / stock_name / "evidence"

    existing_keys = _dedupe_existing(evidence_dir)

    for item in items:
        title = item.title or "（无标题）"
        url = item.url or ""
        canonical_key = _canonical_key(item)

        meta = {
            "title": title,
            "url": url,
            "canonical_key": canonical_key,
        }

        # Filter: must have source-credit metadata.
        if not item.extra or "source_credit" not in item.extra:
            meta["reason"] = "missing source-credit metadata"
            plan.filtered.append(meta)
            continue

        source_credit = item.extra.get("source_credit", 0)
        knowledge_eligible = bool(item.extra.get("knowledge_eligible", False))
        quality_action = item.extra.get("agent_reach_quality_action", "keep")

        # Filter: discard action.
        if quality_action == "discard":
            meta["reason"] = "quality action is discard"
            plan.filtered.append(meta)
            continue

        # Filter: not knowledge eligible.
        if not knowledge_eligible:
            meta["reason"] = "knowledge_eligible=False"
            plan.filtered.append(meta)
            continue

        # Filter: source_credit below minimum threshold.
        claim_status = _claim_status(int(source_credit))
        if claim_status is None:
            meta["reason"] = f"source_credit {source_credit} below 30"
            plan.filtered.append(meta)
            continue

        # Filter: duplicate canonical URL/key.
        if canonical_key in existing_keys:
            meta["reason"] = "canonical URL/key already exists"
            meta["path"] = str(existing_keys[canonical_key])
            plan.skipped_existing.append(meta)
            continue

        filename = _build_filename(item, collected_at)
        target_path = _find_unique_path(evidence_dir, filename)
        meta["planned_path"] = str(target_path)
        meta["reason"] = f"claim_status={claim_status}"

        if not dry_run:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            note = _render_note(item, stock_name, stock_code, collected_at, claim_status)
            target_path.write_text(note, encoding="utf-8")

        plan.written.append(meta)
        existing_keys[canonical_key] = target_path

    return plan
