"""Conservative claim-risk-signal derivation from ClaimVerificationPlan.

This module converts the dry-run claim verification output into structured risk
signals accepted by ``risk_score_section()``. It uses deterministic regex-based
phrase matching with explicit risk and exclusion patterns, so positive/official
claims do not generate false risk signals.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Signal configuration
# ---------------------------------------------------------------------------

KNOWN_SIGNAL_SCORES = {
    "业绩预期下调": 1.5,
    "竞争格局恶化": 1.5,
    "盈利压力": 1.0,
    "资金流出": 1.0,
    "技术路线风险": 1.0,
}


# Each entry: (signal_name, risk_regex, exclusion_regex)
# Risk regex must match. Exclusion regex, if any matches, suppresses the signal.
# Regexes are applied to the combined text of claim_text + reasons.
SIGNAL_RULES: List[tuple] = [
    (
        "业绩预期下调",
        re.compile(
            r"(?:"
            r"业绩不及预期|收入不及预期|营收不及预期|"
            r"预期下调|指引.*下修|下修.*指引|"
            r"收入.*下降|营收.*下降|"
            r"需求量.*减少|发货.*减少|"
            r"净利润为负|亏损加剧|亏损扩大"
            r")"
        ),
        re.compile(
            r"(?:"
            r"指引上调|收入增长|营收增长|"
            r"亏损收窄|亏损减少|亏损改善|扭亏|盈利改善"
            r")"
        ),
    ),
    (
        "竞争格局恶化",
        re.compile(
            r"(?:"
            r"竞争格局恶化|竞争加剧|竞争.*激烈|"
            r"价格战|降价压力|降价.*竞争|"
            r"份额下滑|份额.*下降|"
            r"被([^不]{1,8}?)替代|"
            r"竞品挤压|替代风险"
            r")"
        ),
        re.compile(
            r"(?:"
            r"难以被替代|不被替代|未被替代|"
            r"竞争力提升|份额提升|份额.*增长"
            r")"
        ),
    ),
    (
        "盈利压力",
        re.compile(
            r"(?:"
            r"毛利率承压|毛利率下滑|毛利率下降|毛利压缩|"
            r"费用扩张|费用.*上升|费用.*增长|"
            r"利润侵蚀|盈利压力|"
            r"亏损扩大|亏损加剧|"
            r"不可能盈利|难以盈利|盈利困难"
            r")"
        ),
        re.compile(
            r"(?:"
            r"毛利率提升|毛利率改善|毛利.*改善|"
            r"盈利改善|扭亏|亏损收窄|亏损减少|亏损改善|"
            r"费用率下降|费用控制|费用.*下降|"
            r"利润增长|利润.*改善"
            r")"
        ),
    ),
    (
        "资金流出",
        re.compile(
            r"(?:"
            r"资金净流出|主力净流出|"
            r"减持压力|减持.*风险|"
            r"做空压力|做空.*风险|"
            r"做空|"
            r"退通风险|港股通.*退通|退市.*风险|"
            r"流动性恶化|流动性.*紧张"
            r")"
        ),
        re.compile(
            r"(?:"
            r"港股通纳入|纳入港股通|"
            r"流动性改善|流动性.*充裕|"
            r"资金净流入|主力净流入|"
            r"空单.*低|做空.*低|做空力量.*未.*大规模|"
            r"增持|回购"
            r")"
        ),
    ),
    (
        "技术路线风险",
        re.compile(
            r"(?:"
            r"技术路线不确定|技术路线.*风险|"
            r"架构迭代风险|架构.*风险|"
            r"认证受阻|未(?:通过|获|获得)[^，。；;]{0,20}认证|"
            r"功能安全风险|技术替代风险"
            r")"
        ),
        re.compile(
            r"(?:"
            r"(?<!未)通过[^，。；;]{0,20}认证|"
            r"(?<!未)获得[^，。；;]{0,20}认证|"
            r"(?<!未)获[^，。；;]{0,20}认证|"
            r"技术突破|技术.*领先"
            r")"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\]]+|www\.[^\s\]]+")
_FILE_PATH_RE = re.compile(r"(?:/[^\s:：,;，。\"'\]]{2,})+|\b[A-Za-z]:\\[^\s:：,;，。\"'\]]{2,}")
_CITATION_RE = re.compile(r"\[\^?\d+\]")
_RAW_ID_RE = re.compile(r"\brawid\w*\b", re.IGNORECASE)


def _sanitize_evidence_text(text: str) -> str:
    """Strip URLs, paths, citation markers, raw ids and collapse whitespace."""
    text = _URL_RE.sub("", text)
    text = _FILE_PATH_RE.sub("", text)
    text = _CITATION_RE.sub("", text)
    text = _RAW_ID_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Core derivation
# ---------------------------------------------------------------------------


def _resolve_confidence(action: str, confidence: Optional[int]) -> int:
    if confidence is None:
        if action == "verified":
            return 70
        if action == "supported":
            return 60
        return 0
    if action in ("verified", "supported"):
        return int(confidence)
    return 0


def _signal_status(action: str) -> str:
    if action == "verified":
        return "verified"
    if action == "supported":
        return "supported"
    return "unverified"


def _match_signal(text: str, signal_name: str, risk_re: re.Pattern, exclude_re: re.Pattern) -> Optional[str]:
    """Return matched term/phrase if risk pattern matches and exclusion does not."""
    if exclude_re.search(text):
        return None
    match = risk_re.search(text)
    if not match:
        return None
    return match.group(0)


def derive_structured_risk_signals_from_plan(plan, max_signals: int = 5) -> List[Dict[str, Any]]:
    """Convert a full ClaimVerificationPlan to structured risk signals.

    Matches full low-credit claim_text plus verification reasons. Does not
    truncate before matching. Deduplicates across the full plan, then caps.
    """
    low_by_id: Dict[str, Any] = {c.claim_id: c for c in getattr(plan, "low_credit_claims", [])}

    raw_signals: List[Dict[str, Any]] = []

    for verification in getattr(plan, "verifications", []):
        low = low_by_id.get(verification.claim_id)
        if low is None:
            continue

        claim_text = str(getattr(low, "claim_text", "") or "")
        reasons_text = " ".join(str(r) for r in getattr(verification, "reasons", []) or [])
        combined_text = f"{claim_text} {reasons_text}".strip()
        if not combined_text:
            continue

        action = str(getattr(verification, "action", "unverified") or "unverified")
        status = _signal_status(action)
        confidence = _resolve_confidence(action, getattr(verification, "confidence", None))

        for signal_name, risk_re, exclude_re in SIGNAL_RULES:
            matched_term = _match_signal(combined_text, signal_name, risk_re, exclude_re)
            if matched_term is None:
                continue

            sanitized = _sanitize_evidence_text(claim_text)
            raw_signals.append({
                "name": signal_name,
                "score": KNOWN_SIGNAL_SCORES.get(signal_name, 1.0),
                "confidence": confidence,
                "source": "claim_verification",
                "evidence_text": sanitized,
                "matched_terms": [matched_term],
                "status": status,
                "_sort_key": (
                    0 if status == "verified" else 1 if status == "supported" else 2,
                    -confidence,
                    -len(sanitized),
                ),
            })

    # Deduplicate by name: prefer verified > supported > unverified, then higher
    # confidence, then longer evidence text.
    by_name: Dict[str, Dict[str, Any]] = {}
    for sig in raw_signals:
        existing = by_name.get(sig["name"])
        if existing is None or sig["_sort_key"] < existing["_sort_key"]:
            by_name[sig["name"]] = sig

    signals = sorted(by_name.values(), key=lambda s: s["_sort_key"])
    signals = signals[:max_signals]

    for sig in signals:
        sig["evidence_text"] = _truncate(sig["evidence_text"], 180)
        del sig["_sort_key"]

    return signals
