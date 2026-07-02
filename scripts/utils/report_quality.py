"""Report quality checks for generated stock reports.

This module is intentionally independent from the report renderers. It checks
the final Markdown artifact so existing report-generation entry points can stay
unchanged while quality expectations become executable.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class QualityIssue:
    """A single report quality issue."""

    code: str
    severity: str
    message: str
    evidence: str = ""


@dataclass
class QualityResult:
    """Aggregate quality check result."""

    path: str
    passed: bool
    issues: List[QualityIssue]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "passed": self.passed,
            "issues": [asdict(i) for i in self.issues],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


REQUIRED_SIGNALS = {
    "trend": ("趋势", [r"趋势", r"trend_state", r"上升趋势", r"下降趋势", r"震荡趋势"]),
    "daily": ("日线", [r"日线", r"MA20", r"MA60"]),
    "weekly": ("周线", [r"周线", r"周线大背景", r"weekly"]),
    "volume": ("成交量/成交额", [r"成交量", r"成交额", r"量能", r"volume"]),
    "volatility": ("波动率/BOLL/ATR", [r"波动率", r"波动", r"BOLL", r"ATR", r"布林"]),
    "score": ("评分", [r"评分", r"\d+(?:\.\d+)?/10", r"\d+(?:\.\d+)?/100"]),
    "confidence": ("可信度", [r"可信度", r"置信度", r"confidence"]),
    "risk": ("风险提示", [r"风险提示", r"风险等级", r"风险因子", r"风险评分"]),
}

WEAK_TREND_PATTERNS = [
    r"下降趋势",
    r"趋势走弱",
    r"趋势已走弱",
    r"趋势结构转弱",
    r"已触发趋势失效",
    r"当前趋势失效",
    r"中期趋势结构已破坏",
    r"破坏期",
    r"当前[^。\n]*跌破MA60",
    r"价格[^。\n]*跌破MA60",
]

STRONG_RECOMMENDATION_PATTERNS = [
    r"强烈看多",
    r"积极配置",
    r"建议加仓",
    r"趋势仍可跟踪",
]

BLOCKED_ENTRY_STRONG_RECOMMENDATION_PATTERNS = [
    r"强烈看多",
    r"积极配置",
    r"建议加仓",
]

BLOCKED_ENTRY_PATTERNS = [
    r"关注/不操作",
    r"盈亏比不足",
    r"BIAS[^。\n]*严重正偏离",
]

# Risk-like terms that may appear in 4.4 display-only external observations.
_DISPLAY_ONLY_RISK_TERMS = [
    r"退通",
    r"解禁",
    r"减持",
    r"自研替代",
    r"价格战",
    r"毛利率承压",
    r"估值偏高",
    r"做空",
]

# ---------------------------------------------------------------------------
# Peer comparison material quality gates
# ---------------------------------------------------------------------------

# Social-only source ref prefixes (error).
_PEER_SOCIAL_PREFIXES = (
    "雪球:", "知乎:", "微信:", "精选外部:", "社区:",
)

# Allowed source ref prefixes for peer comparison material.
_PEER_ALLOWED_PREFIXES = (
    "公告:", "年报:", "研报:", "指标:", "行业研报:", "行业资讯:", "iwencai:",
)

# Strong comparison terms (error) — check 4.1/4.2.
_PEER_STRONG_TERMS = [
    "行业第一",
    "唯一",
    "全面领先",
    "显著优于",
    "远强于",
    "优于",
    "领先",
    "远超",
    "全面占优",
    "更具优势",
]

# Weak comparison terms (warning) — check 4.1/4.2.
_PEER_WEAK_TERMS = [
    "对标",
    "差距",
    "落后于",
    "不及",
    "接近",
    "略高于",
    "略低于",
    "窄于",
    "好于",
    "弱于",
    "行业平均",
    "同行平均",
]


def _extract_header(text: str, section_prefix: str) -> str:
    """Extract the `### 综合评分: ... | EV: ...（...）` line under a section."""
    normalized_text = _normalize(text)
    normalized_prefix = _normalize(section_prefix)
    parts = normalized_text.split(normalized_prefix)
    if len(parts) < 2:
        return ""
    section = parts[1].split("\n## ")[0]
    for line in section.splitlines():
        if line.strip().startswith("###综合评分:"):
            return line.strip()
    return ""


def check_report_file(path: str | Path) -> QualityResult:
    """Check a Markdown report file."""
    report_path = Path(path)
    text = report_path.read_text(encoding="utf-8")
    manifest = _load_industry_relevance_manifest_sidecar(report_path)
    peer_material = _load_peer_comparison_material_sidecar(report_path)
    return check_report_text(
        text,
        path=str(report_path),
        industry_relevance_manifest=manifest,
        peer_comparison_material=peer_material,
    )


def check_report_text(
    text: str,
    path: str = "<memory>",
    industry_relevance_manifest: dict | None = None,
    peer_comparison_material: dict | None = None,
) -> QualityResult:
    """Check report Markdown text and return structured issues."""
    issues: List[QualityIssue] = []
    normalized = _normalize(text)

    issues.extend(_check_required_signals(normalized))
    issues.extend(_check_contradictions(normalized))
    issues.extend(_check_curated_external_inline_footnotes(text))
    issues.extend(_check_industry_chain_claims(text, industry_relevance_manifest))
    issues.extend(_check_peer_comparison_quality(text, peer_comparison_material))

    error_count = sum(1 for i in issues if i.severity == "error")
    return QualityResult(path=path, passed=error_count == 0, issues=issues)


def format_quality_result(result: QualityResult) -> str:
    """Human-readable CLI output."""
    status = "PASS" if result.passed else "FAIL"
    lines = [f"{status}: {result.path}"]
    if not result.issues:
        lines.append("No quality issues found.")
        return "\n".join(lines)

    for issue in result.issues:
        lines.append(f"- [{issue.severity.upper()}] {issue.code}: {issue.message}")
        if issue.evidence:
            lines.append(f"  evidence: {issue.evidence}")
    return "\n".join(lines)


def _normalize(text: str) -> str:
    return text.replace(" ", "").replace("\u3000", "")


def _load_industry_relevance_manifest_sidecar(report_path: Path) -> dict | None:
    sidecar = report_path.with_name(f"{report_path.stem}_industry_relevance_manifest.json")
    if not sidecar.exists():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _check_required_signals(text: str) -> Iterable[QualityIssue]:
    for code, (label, patterns) in REQUIRED_SIGNALS.items():
        if not any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
            yield QualityIssue(
                code=f"missing_{code}",
                severity="error",
                message=f"报告缺少必要质量要素：{label}",
            )


def _check_contradictions(text: str) -> Iterable[QualityIssue]:
    normalized = _normalize(text)

    # EV: N/A% formatting
    if re.search(r"EV:\s*N/A%", normalized):
        yield QualityIssue(
            code="ev_na_percent",
            severity="error",
            message="EV 显示为 N/A%，格式错误；缺失 EV 应显示为 N/A（无百分号）。",
        )

    # Summary / section 1 consistency
    summary_header = _extract_header(text, "## 执行摘要")
    section1_header = _extract_header(text, "## 一、综合评分与推荐")
    if summary_header and section1_header and summary_header != section1_header:
        yield QualityIssue(
            code="summary_score_label_mismatch",
            severity="error",
            message="执行摘要与一、综合评分与推荐的评分/EV/推荐标签不一致。",
            evidence=f"summary={summary_header}; section1={section1_header}",
        )

    # Blocked entry + strong recommendation
    blocked_entry = any(re.search(p, text, flags=re.IGNORECASE) for p in BLOCKED_ENTRY_PATTERNS)
    strong_recommendation = any(re.search(p, text) for p in STRONG_RECOMMENDATION_PATTERNS)
    blocked_entry_strong_recommendation = any(
        re.search(p, text) for p in BLOCKED_ENTRY_STRONG_RECOMMENDATION_PATTERNS
    )
    if blocked_entry and blocked_entry_strong_recommendation:
        yield QualityIssue(
            code="contradiction_blocked_entry_strong_recommendation",
            severity="warning",
            message="报告出现入场质量不足/追高风险信号，同时包含偏积极建议，需人工复核。",
        )

    # Risk position label mismatch: if label is constrained, risk advice should not be aggressive
    if re.search(r"（看多但等待入场|看多但避免追高|看多但控制仓位|风险控制优先）", normalized):
        if ">**仓位建议**:积极配置，最大仓位20%" in normalized:
            yield QualityIssue(
                code="risk_position_label_mismatch",
                severity="error",
                message="推荐标签已受入场约束降级，但风险仓位建议仍为积极配置 20%，存在不一致。",
            )

    # Display-only 4.4 risk observations should have explanation when formal risk score is low
    section44 = ""
    section44_match = re.search(
        r"(?ms)^#{2,4}\s*(?:4\.4\s*)?(?:精选外部观察|外部观点与待验证变量)（Preview）\s*$"
        r"(.*?)(?=^##\s|\Z)",
        text,
    )
    if section44_match:
        section44 = _normalize(section44_match.group(1))
    if section44 and any(re.search(term, section44) for term in _DISPLAY_ONLY_RISK_TERMS):
        risk_score = _extract_score(normalized, [r"风险等级[:：]?(\d+(?:\.\d+)?)/10"])
        if risk_score is not None and risk_score <= 2.0:
            risk_section = ""
            if "##综合风险评分" in normalized:
                risk_section = normalized.split("##综合风险评分")[1].split("\n## ")[0]
            if not re.search(r"display-only|不计入综合风险评分|外部观察说明", risk_section):
                yield QualityIssue(
                    code="display_only_risk_without_explanation",
                    severity="warning",
                    message="4.4 display-only 外部观察包含风险线索，但风险板块未解释其不计入综合风险评分。",
                )

    weak = any(re.search(p, text, flags=re.IGNORECASE) for p in WEAK_TREND_PATTERNS)
    if not weak:
        return

    total_score = _extract_score(text, [r"综合评分[:：]?(\d+(?:\.\d+)?)/10"])
    technical_score = _extract_table_score(text, ["技术面强度", "技术"])
    trend_health = _extract_score(text, [r"趋势健康度[【:：]?(\d+(?:\.\d+)?)/100"])

    if total_score is not None and total_score >= 8.0:
        yield QualityIssue(
            code="contradiction_weak_trend_high_total_score",
            severity="error",
            message="报告同时出现趋势走弱/破坏信号与过高综合评分。",
            evidence=f"综合评分={total_score}/10",
        )

    if technical_score is not None and technical_score >= 8.0:
        yield QualityIssue(
            code="contradiction_weak_trend_high_technical_score",
            severity="error",
            message="报告同时出现趋势走弱/破坏信号与过高技术面评分。",
            evidence=f"技术面评分={technical_score}/10",
        )

    if trend_health is not None and total_score is not None:
        if trend_health < 45 and total_score >= 7.5:
            yield QualityIssue(
                code="contradiction_low_trend_health_high_total_score",
                severity="error",
                message="趋势健康度偏低，但综合评分偏高。",
                evidence=f"趋势健康度={trend_health}/100, 综合评分={total_score}/10",
            )

    if strong_recommendation:
        yield QualityIssue(
            code="contradiction_weak_trend_strong_recommendation",
            severity="warning",
            message="报告出现趋势走弱/破坏信号，同时包含偏积极建议，需人工复核。",
        )


def _check_curated_external_inline_footnotes(text: str) -> Iterable[QualityIssue]:
    section44_match = re.search(
        r"(?ms)^#{2,4}\s*(?:4\.4\s*)?(?:精选外部观察|外部观点与待验证变量)（Preview）\s*$"
        r"(.*?)(?=^##\s|\Z)",
        text,
    )
    if not section44_match:
        return

    section44 = section44_match.group(1)
    if "本节引用来源" not in section44 or not re.search(r"(?m)^-\s*\[\^\d+\]", section44):
        return

    body = section44.split("本节引用来源", 1)[0]
    if re.search(r"\[\^\d+\]", body):
        return

    yield QualityIssue(
        code="curated_external_missing_inline_footnotes",
        severity="error",
        message="4.4 外部观察有本节引用来源，但正文段落缺少 inline footnote，引用不可追溯。",
    )


_INDUSTRY_CHAIN_TRIGGER_TERMS = [
    "传导",
    "对应",
    "暴露",
    "受益",
    "催化",
    "排产",
    "待验证变量",
]

_INDUSTRY_CHAIN_STRONG_CONFIRMATION_TERMS = [
    "直接受益",
    "确认受益",
    "确定催化",
    "已经传导",
    "必然传导",
    "锁定受益",
]


def _check_industry_chain_claims(text: str, manifest: dict | None) -> Iterable[QualityIssue]:
    if not manifest:
        return

    section43 = _extract_deep_analysis_subsection(text, "4.3")
    if not section43:
        return
    normalized_section = _normalize(section43)
    if not any(term in normalized_section for term in _INDUSTRY_CHAIN_TRIGGER_TERMS):
        return

    chains = manifest.get("events_catalysts_chains") or []
    if not chains:
        yield QualityIssue(
            code="industry_chain_manifest_missing",
            severity="error",
            message="4.3 出现行业传导/受益链条表达，但缺少可校验的行业相关性 sidecar。",
        )
        return

    for term in _INDUSTRY_CHAIN_STRONG_CONFIRMATION_TERMS:
        if term in normalized_section:
            yield QualityIssue(
                code="industry_chain_unmatched_claim",
                severity="error",
                message="4.3 行业链条使用了强确认/受益表达，必须改为待验证变量或提供正式来源确认。",
                evidence=term,
            )
            return

    for chain in chains:
        allowed_terms = [_normalize(str(term)) for term in chain.get("allowed_terms", []) if str(term).strip()]
        if allowed_terms and all(term in normalized_section for term in allowed_terms):
            return

    yield QualityIssue(
        code="industry_chain_unmatched_claim",
        severity="error",
        message="4.3 行业链条表达无法匹配 deterministic relevance_chain，可能存在 LLM 自行补链条。",
    )


def _extract_deep_analysis_subsection(text: str, section_number: str) -> str:
    pattern = rf"(?ms)^###\s*{re.escape(section_number)}\s+[^\n]*\n(.*?)(?=^###\s*\d\.\d\s+|^##\s|\Z)"
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _extract_score(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


def _extract_table_score(text: str, labels: list[str]) -> float | None:
    for label in labels:
        pattern = rf"\|[^|\n]*{re.escape(label)}[^|\n]*\|[^|\n]*\|(\d+(?:\.\d+)?)\|"
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


# ---------------------------------------------------------------------------
# Peer comparison material helpers
# ---------------------------------------------------------------------------


def _load_peer_comparison_material_sidecar(report_path: Path) -> dict | None:
    """Load peer comparison material sidecar adjacent to the report file."""
    sidecar = report_path.with_name(f"{report_path.stem}_peer_comparison_material.json")
    if not sidecar.exists():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _extract_section_41(text: str) -> str:
    """Extract 4.1 行业逻辑与竞争格局 section text."""
    return _extract_deep_analysis_subsection(text, "4.1")


def _extract_section_42(text: str) -> str:
    """Extract 4.2 基本面与估值分析 section text."""
    return _extract_deep_analysis_subsection(text, "4.2")


def _check_peer_comparison_quality(
    text: str,
    peer_material: dict | None,
) -> Iterable[QualityIssue]:
    """Check peer comparison quality gates.

    Checks:
    - peer_pack_social_leak: social-only source refs in pack.
    - unsupported_peer_superlative: strong peer terms in 4.1/4.2 without pack support.
    - peer_claim_without_peer_pack: weak peer terms in 4.1/4.2 without pack.
    """
    # --- Gate 1: peer_pack_social_leak ---
    if peer_material:
        rows = peer_material.get("rows") or []
        for row in rows:
            refs = row.get("source_refs") or []
            for ref in refs:
                ref_text = str(ref or "")
                is_social_ref = any(ref_text.startswith(prefix) for prefix in _PEER_SOCIAL_PREFIXES)
                is_allowed_ref = any(ref_text.startswith(prefix) for prefix in _PEER_ALLOWED_PREFIXES)
                if is_social_ref or not is_allowed_ref:
                    yield QualityIssue(
                        code="peer_pack_social_leak",
                        severity="error",
                        message=f"同行比较 material 包含非正式来源引用: {ref_text}",
                        evidence=f"row metric={row.get('metric')}, peer={row.get('peer')}",
                    )

    # Extract 4.1 and 4.2 sections
    section41 = _extract_section_41(text)
    section42 = _extract_section_42(text)
    sections_text = f"{section41}\n{section42}"

    _normalized_41_42 = _normalize(sections_text)

    # Determine if pack has usable rows
    has_high_confidence_rows = False
    has_any_rows = False
    if peer_material:
        rows = peer_material.get("rows") or []
        has_any_rows = bool(rows)
        for row in rows:
            if row.get("confidence", 0) >= 0.70 and row.get("source_refs"):
                has_high_confidence_rows = True
                break

    # --- Gate 2: unsupported_peer_superlative ---
    strong_match_found = any(
        term in _normalized_41_42
        for term in _PEER_STRONG_TERMS
    )
    if strong_match_found and not has_high_confidence_rows:
        yield QualityIssue(
            code="unsupported_peer_superlative",
            severity="error",
            message="4.1/4.2 出现强同行比较表达，但同行比较 material 缺少达标行支撑",
            evidence="strong terms detected in 4.1/4.2 without high-confidence peer pack rows",
        )

    # --- Gate 3: peer_claim_without_peer_pack ---
    weak_match_found = any(
        term in _normalized_41_42
        for term in _PEER_WEAK_TERMS
    )
    if weak_match_found and not has_any_rows:
        yield QualityIssue(
            code="peer_claim_without_peer_pack",
            severity="warning",
            message="4.1/4.2 出现弱同行比较表达，但同行比较 material 不存在或无数据行",
            evidence="weak peer terms in 4.1/4.2 without peer comparison material",
        )
