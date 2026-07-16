"""Shared credit-aware synthesis helpers.

Pure deterministic helpers used by both KnowledgeSynthesizer and the legacy
SynthesisSkill prompt path.  No network, LLM, or browser calls.
"""

import re
from typing import Any, Dict, Mapping, Union

try:
    from .source_adapter import SynthesisItem
except ImportError:
    from source_adapter import SynthesisItem


# Source families that may support core facts when no explicit metadata says
# otherwise.  Everything else is rejected.
_CORE_FACT_SUPPORTING_FAMILIES = frozenset({
    "公告",
    "官方",
    "交易所",
    "巨潮",
})

# Source families that are never allowed to support core facts.
_REJECTED_CORE_FACT_FAMILIES = frozenset({
    "研报",
    "新闻",
    "雪球",
    "知乎",
    "微信公众号",
    "AgentReach",
    "资金流向",
})

# Minimum numeric credit to be treated as high-credit confirmed.
_HIGH_CREDIT_THRESHOLD = 80

# Source types / verification statuses that indicate a confirmed-fact source.
_CONFIRMED_SOURCE_TYPES = frozenset({
    "exchange_announcement",
    "company_ir",
    "company_official",
    "announcement",
    "official",
    "confirmed_fact",
})

_CONFIRMED_VERIFICATION_STATUSES = frozenset({
    "primary_source",
    "confirmed_fact",
})


class _ItemMeta:
    """Normalized read-only view of SynthesisItem-or-dict metadata."""

    def __init__(self, item_or_meta: Union[SynthesisItem, Dict[str, Any], None]):
        self.source_platform = ""
        self.source_credit = None
        self.source_type = ""
        self.verification_status = ""
        self.extra: Dict[str, Any] = {}

        if item_or_meta is None:
            return

        if isinstance(item_or_meta, SynthesisItem):
            self.source_platform = item_or_meta.source_platform or ""
            self.extra = item_or_meta.extra or {}
        elif isinstance(item_or_meta, dict):
            self.source_platform = item_or_meta.get("source", item_or_meta.get("source_platform", ""))
            self.extra = item_or_meta.get("extra", {}) or {}
            if not isinstance(self.extra, dict):
                self.extra = {}
            # Citation metadata may have these at top level.
            if item_or_meta.get("source_credit") is not None:
                self.source_credit = item_or_meta.get("source_credit")
            if item_or_meta.get("source_type"):
                self.source_type = item_or_meta.get("source_type")
            if item_or_meta.get("verification_status"):
                self.verification_status = item_or_meta.get("verification_status")
        else:
            return

        if self.source_credit is None and self.extra.get("source_credit") is not None:
            self.source_credit = self.extra.get("source_credit")
        if not self.source_type and self.extra.get("source_type"):
            self.source_type = self.extra.get("source_type")
        if not self.verification_status and self.extra.get("verification_status"):
            self.verification_status = self.extra.get("verification_status")


def credit_usage_rules_text() -> str:
    """Return the shared credit-usage rules block for synthesis prompts."""
    return """证据信用与写法规则：
- 高信用/官方/公告/交易所来源可作为事实，可写为“公司公告披露/业绩预告显示”。
- 中信用/研报/新闻/政策/微信公众号来源只能写为“券商研报关注/媒体报道显示/政策文件指向/微信公众号观点”，不得写成公司确认。
- verified discussion 必须写为“社区讨论线索已与……相互印证”或“已验证讨论线索”，并且正文引用必须来自上方编号的高信用来源。
- supported discussion 只能写成“该线索获得部分支持，但仍非官方确认”，不能直接作为确认事实。
- 多个低信用来源重复出现只表示“社区共振/市场关注”，不得写成事实确认。Phase 1 不使用 corroborated schema。
- unverified discussion 只能作为待验证观点，不得进入核心事实、结论或风险加分。
- needs_review/unverified/supported 等 claim verification 状态不是引用编号，禁止输出 [^verified] / [^supported] / [^needs_review] / [^unverified]；正文只允许使用 [^n] 形式的数字引用。
- needs_review/unverified 不得进入执行摘要、核心事实、结论。
- 推论必须显式使用“可能/若/需要验证”，不得把推论写成事实。
- 中信用新闻/研报/微信公众号可进入风险观察文字，但不得生成结构化风险信号，不得影响风险评分。"""


def sanitize_citation_markers(text: str) -> str:
    """Remove non-numeric citation markers while preserving [^n].

    LLMs sometimes emit [^supported], [^needs_review], [^unverified], or
    [^verified] by mistake.  Those markers are not valid citations and must be
    stripped from narrative output.  Numeric markers such as [^1] or [^23]
    are preserved.
    """
    if not isinstance(text, str):
        return text
    # Remove [^<non-digit>] and plain [<non-digit>] markers.
    text = re.sub(r"\[\^(?!\d+\])[^\]]*\]", "", text)
    text = re.sub(r"\[(?!\d+\])[a-zA-Z_]+\]", "", text)
    return text


def citation_identity(meta: Any, fallback_ref: Any = None) -> tuple:
    """Return the stable exact-source identity used across display layers."""
    if not isinstance(meta, Mapping):
        return ("ref", fallback_ref) if fallback_ref is not None else ()
    url = str(meta.get("url") or "").strip()
    if url:
        return ("url", url)
    fields = tuple(str(meta.get(key) or "").strip() for key in ("source", "author", "title"))
    if any(fields):
        return ("meta",) + fields
    return ("ref", fallback_ref) if fallback_ref is not None else ()


def _normalize_source_platform(platform: str) -> str:
    return str(platform or "").strip()


def _is_high_credit_confirmed(meta: _ItemMeta) -> bool:
    """Return True if metadata indicates a confirmed high-credit source."""
    try:
        credit = int(meta.source_credit) if meta.source_credit is not None else 0
    except (TypeError, ValueError):
        credit = 0
    if credit < _HIGH_CREDIT_THRESHOLD:
        return False

    source_type = (meta.source_type or "").strip().lower()
    verification_status = (meta.verification_status or "").strip().lower()

    if source_type in _CONFIRMED_SOURCE_TYPES:
        return True
    if verification_status in _CONFIRMED_VERIFICATION_STATUSES:
        return True
    return False


def _source_family(platform: str) -> str:
    """Map a source_platform value to a stable family name."""
    s = _normalize_source_platform(platform)
    lower = s.lower()

    if "知乎" in s:
        return "知乎"
    if lower in ("xueqiu", "雪球"):
        return "雪球"
    if "研报" in s or lower == "research_report":
        return "研报"
    if "公告" in s or lower == "announcement":
        return "公告"
    if "资金流向" in s or lower == "fundflow":
        return "资金流向"
    if "新闻" in s or lower == "news":
        return "新闻"
    if "微信" in s or lower == "wechat" or lower == "微信公众号":
        return "微信公众号"
    if lower.startswith("agentreach") or "agentreach" in lower:
        return "AgentReach"
    if any(tok in s for tok in ("巨潮", "交易所", "官方", "cninfo", "sse", "szse")):
        return "官方"
    return s


def derive_synthesis_usage(item_or_meta: Union[SynthesisItem, Dict[str, Any], None]) -> Dict[str, str]:
    """Derive credit tier, usage, and display label for a synthesis source.

    Prefer structured metadata (source_credit / source_type / verification_status)
    when present; otherwise fall back to source_platform.
    """
    meta = _ItemMeta(item_or_meta)
    platform = meta.source_platform
    family = _source_family(platform)

    # Periodic-report full-text material layer: medium credit, display-only.
    # Never core-fact eligible (enforced separately by is_core_fact_supporting_source).
    if (meta.source_type or "").strip() == "periodic_report_fulltext_analysis":
        return {
            "credit_tier": "medium",
            "usage": "annual_report_material",
            "display_label": "中信用/annual_report_material",
        }

    # High-credit confirmed metadata overrides platform fallback.
    if _is_high_credit_confirmed(meta):
        return {
            "credit_tier": "high",
            "usage": "core_fact_allowed",
            "display_label": f"高信用/{meta.source_type or 'confirmed_fact'}",
        }

    # Explicit platform mapping.
    if family == "公告" or family == "官方":
        return {
            "credit_tier": "high",
            "usage": "core_fact_allowed",
            "display_label": "高信用/confirmed_fact",
        }

    if family == "研报":
        return {
            "credit_tier": "medium",
            "usage": "professional_observation",
            "display_label": "中信用/professional_observation",
        }

    if family == "新闻":
        return {
            "credit_tier": "medium",
            "usage": "professional_observation",
            "display_label": "中信用/professional_observation",
        }

    if family == "微信公众号":
        # Prefer medium only when explicit metadata indicates publisher/article.
        account = (meta.extra.get("account") or "").strip()
        account_type = (meta.extra.get("account_type") or "").strip().lower()
        source_type = (meta.source_type or "").strip().lower()
        is_publisher = (
            account_type in ("official", "publisher", "media")
            or source_type in ("official", "publisher", "article", "media")
            or bool(account)
        )
        if is_publisher:
            return {
                "credit_tier": "medium",
                "usage": "professional_observation",
                "display_label": "中信用/professional_observation",
            }
        return {
            "credit_tier": "low",
            "usage": "discussion_only",
            "display_label": "低信用/market_discussion",
        }

    if family == "资金流向":
        return {
            "credit_tier": "medium",
            "usage": "quantitative_observation",
            "display_label": "中信用/quantitative_observation",
        }

    if family in ("雪球", "知乎"):
        return {
            "credit_tier": "low",
            "usage": "discussion_only",
            "display_label": "低信用/market_discussion",
        }

    if family == "AgentReach":
        # AgentReach already embeds source_credit in extra; if we still reach
        # the fallback, treat it conservatively.
        return {
            "credit_tier": "low",
            "usage": "discussion_only",
            "display_label": "低信用/limited_discussion",
        }

    return {
        "credit_tier": "unknown",
        "usage": "background_limited",
        "display_label": "未知/background_limited",
    }


def format_synthesis_source_line(index: int, item: SynthesisItem) -> str:
    """Format a numbered source line with credit/usage labels."""
    usage = derive_synthesis_usage(item)
    extra = item.extra or {}
    # Periodic-report full-text material is allowed a larger excerpt cap; all
    # other sources keep the default 500-char cap.
    cap = 1200 if extra.get("source_type") == "periodic_report_fulltext_analysis" else 500
    content_snippet = item.content[:cap] if len(item.content) > cap else item.content
    return (
        f"[{index}] 标题: {item.title} | "
        f"来源: {item.source_platform} | "
        f"信用层: {usage['credit_tier']} | "
        f"可用方式: {usage['usage']} | "
        f"作者: {item.author} | "
        f"时间: {item.publish_time} | "
        f"内容: {content_snippet}"
    )


def is_core_fact_supporting_source(source: str, meta: Dict[str, Any] | None = None) -> bool:
    """Return True if `source` (with optional metadata) may support a core fact.

    Allowed:
      - source family 公告 / 官方 / 交易所 / 巨潮
      - any source whose metadata indicates source_credit >= 80 and a
        confirmed-fact source_type or verification_status

    Rejected:
      - 研报 / 新闻 / 雪球 / 知乎 / 微信公众号 (unless high-credit metadata)
      - AgentReach / 资金流向 / unknown
    """
    normalized = _normalize_source_platform(source)
    if not normalized:
        return False

    family = _source_family(normalized)

    if family in _CORE_FACT_SUPPORTING_FAMILIES:
        return True

    if meta and _is_high_credit_confirmed(_ItemMeta(meta)):
        return True

    return False


def format_claim_verification_appendix(
    context: Dict[str, Any],
    *,
    is_legacy: bool = False,
) -> str:
    """Render a guarded, non-citable claim verification appendix.

    Used by both KnowledgeSynthesizer and the legacy SynthesisSkill path.
    """
    if not context or not context.get("enabled"):
        return ""

    counts = context.get("counts", {})
    lines = [
        "Claim Verification Context（以下不是新的引用来源）",
        "",
        "重要约束：",
        "- 以下内容不是新的引用来源，不能用 [^n] 引用，也不能单独作为事实写入正文。",
        "- claim verification 状态（verified / supported / needs_review / unverified）不是引用编号，禁止输出 [^verified] / [^supported] / [^needs_review] / [^unverified]。",
        "- 它只用于判断社区观点的可信度，帮助你决定如何强调或弱化某些信息。",
        "- 多个低信用来源重复出现只表示“社区共振/市场关注”，不得写成事实确认。Phase 1 不输出 corroborated bucket。",
        "",
        f"统计：高信用声明 {counts.get('high_credit_claims', 0)} 条，低信用声明 {counts.get('low_credit_claims', 0)} 条，"
        f"已验证 {counts.get('verified', 0)} 条，部分支持 {counts.get('supported', 0)} 条，"
        f"未验证 {counts.get('unverified', 0)} 条，需复核 {counts.get('needs_review', 0)} 条。",
        "",
        "可信度使用规则：",
        "- verified（已验证讨论线索）：只有当同一事实也出现在上方编号信息来源中时，才可作为重点线索使用；如写入正文，必须写为“社区讨论线索已与……相互印证”或“已验证讨论线索”，并必须引用上方编号的高信用来源。",
        "- supported（部分支持讨论线索）：只能写成“该线索获得部分支持，但仍非官方确认”；可参与市场分歧/关注点，但不得写成官方确认事实。",
        "- unverified（未验证市场讨论）：只能作为“待验证市场观点/社区讨论”，不得进入核心事实基座、结论或风险加分。",
        "- needs_review：仅提示存在相关信息，但当前证据不足，不得写入正文。",
        "",
    ]

    def _render_bucket(label: str, rows: list) -> list:
        if not rows:
            return []
        out = [f"{label}："]
        for row in rows:
            text = row.get("claim_text", "")
            action = row.get("action", "")
            confidence = row.get("confidence")
            reason = row.get("reason", "")
            titles = row.get("verified_by_titles", [])
            parts = [f"- [{action}] {text}"]
            if confidence is not None:
                parts.append(f"（置信度 {confidence}）")
            if titles:
                parts.append(f"[依据标题: {' / '.join(titles)}]")
            if reason:
                parts.append(f"[原因: {reason}]")
            out.append(" ".join(parts))
        return out

    lines.extend(_render_bucket("已验证声明（已验证讨论线索）", context.get("verified_claims", [])))
    if context.get("supported_claims"):
        lines.append("")
    lines.extend(_render_bucket("中等支持声明（部分支持讨论线索）", context.get("supported_claims", [])))
    if context.get("needs_review_claims"):
        lines.append("")
    lines.extend(_render_bucket("需复核声明", context.get("needs_review_claims", [])))
    if context.get("unverified_claims"):
        lines.append("")
    lines.extend(_render_bucket("未验证声明（未验证市场讨论）", context.get("unverified_claims", [])))

    return "\n".join(lines)
