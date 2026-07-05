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

try:
    from .source_direct_relevance import OPERATING_VARIABLE_TERMS
except ImportError:
    from source_direct_relevance import OPERATING_VARIABLE_TERMS


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
    fundflow_material = _load_fundflow_material_sidecar(report_path)
    return check_report_text(
        text,
        path=str(report_path),
        industry_relevance_manifest=manifest,
        peer_comparison_material=peer_material,
        fundflow_material_pack=fundflow_material,
    )


def check_report_text(
    text: str,
    path: str = "<memory>",
    industry_relevance_manifest: dict | None = None,
    peer_comparison_material: dict | None = None,
    fundflow_material_pack: dict | None = None,
) -> QualityResult:
    """Check report Markdown text and return structured issues."""
    issues: List[QualityIssue] = []
    normalized = _normalize(text)

    profile = _parse_deep_analysis_profile(text)

    issues.extend(_check_required_signals(normalized))
    issues.extend(_check_contradictions(normalized))
    issues.extend(_check_curated_external_inline_footnotes(text))
    issues.extend(_check_industry_chain_claims(text, industry_relevance_manifest))
    issues.extend(_check_peer_comparison_quality(text, peer_comparison_material))
    issues.extend(_check_fundflow_claims(text, fundflow_material_pack))
    issues.extend(_check_deep_analysis_subsections(text))
    issues.extend(_check_product_industry_mismatch(text))
    issues.extend(_check_financial_fact_unit_sanity(text))
    issues.extend(_check_financial_missing_contradictions(text))
    issues.extend(_check_financial_profit_direction_contradictions(text))
    issues.extend(_check_header_config_missing(text))
    issues.extend(_check_evidence_depth_warnings(text, profile))
    issues.extend(_check_evidence_profile_gates(text))

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


def _is_annual_broker_external_layout(profile: dict | None) -> bool:
    return bool(
        profile
        and profile.get("profile") == "formal_thin_external_rich"
        and profile.get("formal_thin_layout_variant") == "annual_broker_external_checklist"
    )


def _external_map_section_id(profile: dict | None) -> str:
    return "4.3" if _is_annual_broker_external_layout(profile) else "4.2"


def _extract_external_map_section(text: str, profile: dict | None) -> tuple[str, str]:
    section_id = _external_map_section_id(profile)
    return section_id, _extract_deep_analysis_subsection(text, section_id)


def _load_industry_relevance_manifest_sidecar(report_path: Path) -> dict | None:
    sidecar = report_path.with_name(f"{report_path.stem}_industry_relevance_manifest.json")
    if not sidecar.exists():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _load_fundflow_material_sidecar(report_path: Path) -> dict | None:
    sidecar = report_path.with_name(f"{report_path.stem}_fundflow_material.json")
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


def _extract_markdown_section(text: str, heading: str) -> str:
    pattern = rf"(?ms)^##\s*{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _check_fundflow_claims(text: str, fundflow_material_pack: dict | None) -> Iterable[QualityIssue]:
    section43 = _extract_deep_analysis_subsection(text, "4.3")
    if not section43:
        return
    has_directional_amount = re.search(
        r"(?:主力|超大单|大单|小单)[^。\n|]{0,30}(?:净流入|净流出|流入|流出)[^。\n|]{0,20}\d+(?:\.\d+)?万"
        r"|\d+(?:\.\d+)?万[^。\n|]{0,30}(?:主力|超大单|大单|小单)[^。\n|]{0,20}(?:净流入|净流出|流入|流出)",
        section43,
    )
    has_inferred_fundflow_claim = re.search(
        r"(?:主力资金|资金面|资金流向|主动买盘|买盘|卖盘)[^\n]{0,80}"
        r"(?:压制|支撑|带动|推升|走弱|改善|流入|流出|净流入|净流出)"
        r"|(?:营收|收入|利润|毛利率|订单)[^\n]{0,100}(?:主动买盘|买盘|卖盘|资金面|主力资金)",
        section43,
    )
    if not has_directional_amount and not has_inferred_fundflow_claim:
        return
    rows = (fundflow_material_pack or {}).get("rows") or []
    if rows:
        return
    yield QualityIssue(
        code="fundflow_claim_without_fundflow_pack",
        severity="error",
        message="4.3 出现资金流向/买卖盘判断，但缺少 fundflow_material_pack sidecar 支撑。",
        evidence="4.3 fund-flow claim without deterministic pack",
    )


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
# Fudan trial pipeline quality gates
# ---------------------------------------------------------------------------


def _check_deep_analysis_subsections(text: str) -> Iterable[QualityIssue]:
    if "## 四、深度分析" not in text:
        return
    profile = _parse_deep_analysis_profile(text)
    profile_name = profile.get("profile") if profile else None
    # thin_all explicitly skips forced 4.2/4.3 inference.
    if profile_name == "thin_all":
        required = ("4.1",)
    else:
        required = ("4.1", "4.2", "4.3")
    missing = [
        section
        for section in required
        if not re.search(rf"(?m)^###\s*{re.escape(section)}\s+", text)
    ]
    if missing:
        yield QualityIssue(
            code="missing_deep_analysis_subsection",
            severity="error",
            message="深度分析缺少必备 {} 子章节，renderer 不应静默省略。".format(
                "/".join(required)
            ),
            evidence="missing=" + ",".join(missing),
        )


def _check_product_industry_mismatch(text: str) -> Iterable[QualityIssue]:
    sections_text = "\n".join([
        _extract_deep_analysis_subsection(text, "4.1"),
        _extract_deep_analysis_subsection(text, "4.2"),
    ])
    normalized = _normalize(sections_text)
    if not normalized:
        return

    unrelated_theme = "MLCC" in normalized.upper()
    negated_relation = any(
        phrase in normalized
        for phrase in ("不直接涉及", "无直接关系", "不属于", "不同于", "并非")
    )
    if unrelated_theme and negated_relation:
        yield QualityIssue(
            code="product_industry_mismatch",
            severity="error",
            message="4.1/4.2 将与公司无直接关系的行业主题写成公司逻辑，存在产品/行业错配。",
            evidence="MLCC with negated direct relation",
        )


def _check_financial_fact_unit_sanity(text: str) -> Iterable[QualityIssue]:
    normalized = _normalize(text)
    has_small_core_amount = re.search(
        r"(营业收入|归母净利润|净利润|经营现金流[^|。\n]*)[^。\n|]*\|?[^。\n|]{0,20}\d+(?:\.\d+)?万元",
        normalized,
    )
    has_yi_amount = re.search(
        r"(营业收入|归母净利润|净利润|经营现金流[^。,\n]*)[^。,\n]{0,20}\d+(?:\.\d+)?亿",
        normalized,
    )
    if has_small_core_amount and has_yi_amount:
        yield QualityIssue(
            code="financial_fact_unit_conflict",
            severity="error",
            message="核心财务事实出现万元级金额，但同报告存在亿元级同类指标，疑似结构化年报单位归一化错误。",
            evidence=has_small_core_amount.group(0),
        )


def _check_financial_missing_contradictions(text: str) -> Iterable[QualityIssue]:
    section42 = _extract_deep_analysis_subsection(text, "4.2")
    if not section42:
        return

    normalized_report = _normalize(text)
    normalized_42 = _normalize(section42)
    checks = [
        (
            "revenue",
            re.search(r"营业收入[^。,\n]{0,20}\d+(?:\.\d+)?亿", normalized_report),
            re.search(r"未提供[^。,\n]*(?:营收|营业收入)|(?:营收|营业收入)[^。,\n]*未提供", normalized_42),
        ),
        (
            "profit",
            re.search(r"(?:归母净利润|净利润)[^。,\n]{0,20}\d+(?:\.\d+)?亿", normalized_report),
            re.search(r"未提供[^。,\n]*(?:利润|净利润)|(?:利润|净利润)[^。,\n]*未提供", normalized_42),
        ),
    ]
    for metric, has_fact, has_missing_text in checks:
        if has_fact and has_missing_text:
            yield QualityIssue(
                code="financial_data_missing_contradiction",
                severity="error",
                message="4.2 声称财务指标未提供，但报告已有同一指标的正式财务数据。",
                evidence=f"metric={metric}; missing_text={has_missing_text.group(0)}",
            )
            return


def _check_financial_profit_direction_contradictions(text: str) -> Iterable[QualityIssue]:
    normalized_report = _normalize(text)
    formal_text = "\n".join(
        part
        for part in (
            _extract_markdown_section(text, "执行摘要"),
            _extract_deep_analysis_subsection(text, "4.1"),
            _extract_deep_analysis_subsection(text, "4.2"),
        )
        if part
    )
    normalized_formal = _normalize(formal_text)

    negative_profit_signal = re.search(
        r"(?:归母净利|归母净利润|净利润|净利|盈利)[^。；\n]{0,80}(?:腰斩|修复|同比[-－—]\d|同比下降|同比下滑|同比减少|下降\d|下滑\d|减少\d|-\d+(?:\.\d+)?%)",
        normalized_report,
    )
    positive_profit_wording = re.search(
        r"(?:利润高增|利润增长|净利润增长|归母净利润增长|营收与利润增长|利润增速[^。；\n]{0,20}超预期|持续验证利润高增|(?:归母净利润|净利润|净利|利润)[^。；\n]{0,20}(?:同比)?大幅增长|(?:归母净利润|净利润|净利|利润)同比增长)",
        normalized_formal,
    )
    if negative_profit_signal and positive_profit_wording:
        yield QualityIssue(
            code="financial_profit_direction_contradiction",
            severity="error",
            message="报告同时出现净利同比下滑信号与正式章节利润高增/增长表述，需统一财务口径或显式解释差异。",
            evidence=f"negative={negative_profit_signal.group(0)}; positive={positive_profit_wording.group(0)}",
        )


def _check_header_config_missing(text: str) -> Iterable[QualityIssue]:
    normalized = _normalize(text)
    industry_missing = "**所属赛道**:—" in normalized or "**所属赛道**：—" in normalized
    competitors_missing = "**可比公司**:—" in normalized or "**可比公司**：—" in normalized
    if industry_missing or competitors_missing:
        yield QualityIssue(
            code="header_config_missing",
            severity="warning",
            message="报告头部行业或可比公司仍为空，需检查 stock_config 与常量 fallback 是否接入。",
        )


def _check_evidence_depth_warnings(text: str, profile: dict | None = None) -> Iterable[QualityIssue]:
    yield from _check_section_too_generic(text)
    yield from _check_vague_supply_chain_position(text)
    yield from _check_fundamentals_repeats_core_facts(text)
    yield from _check_external_viewpoint_overcompressed(text, profile)


# ---------------------------------------------------------------------------
# Evidence-adaptive deep analysis gates
# ---------------------------------------------------------------------------


def _parse_deep_analysis_profile(text: str) -> dict | None:
    match = re.search(r"<!--\s*deep_analysis_profile:\s*(.*?)\s*-->", text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception:
        return None


def _check_evidence_profile_gates(text: str) -> Iterable[QualityIssue]:
    profile = _parse_deep_analysis_profile(text)
    if "## 四、深度分析" not in text:
        return

    yield from _check_profile_routing_trace_missing(text, profile)
    yield from _check_formal_thin_forced_legacy_deep_sections(text, profile)
    yield from _check_funding_claim_without_funding_support(text, profile)
    yield from _check_useless_core_fact(text)
    yield from _check_external_map_disclaimer_and_framing(text, profile)


def _check_profile_routing_trace_missing(text: str, profile: dict | None) -> Iterable[QualityIssue]:
    if profile is None:
        yield QualityIssue(
            code="profile_routing_trace_missing",
            severity="error",
            message="第四章缺少可解析的 deep_analysis_profile HTML 注释，无法校验证据自适应路由。",
        )


def _check_formal_thin_forced_legacy_deep_sections(text: str, profile: dict | None) -> Iterable[QualityIssue]:
    if not profile or profile.get("profile") != "formal_thin_external_rich":
        return
    for heading in ("### 4.1 产业逻辑与竞争格局", "### 4.2 业绩路径与多空分歧", "### 4.3 资金面与催化剂时间线"):
        if heading in text:
            yield QualityIssue(
                code="formal_thin_forced_legacy_deep_sections",
                severity="error",
                message=f"形态为 formal_thin_external_rich 但报告仍出现旧模板章节：{heading}。",
                evidence=heading,
            )


def _check_funding_claim_without_funding_support(text: str, profile: dict | None) -> Iterable[QualityIssue]:
    if not profile:
        return
    if _is_annual_broker_external_layout(profile):
        return
    section43 = _extract_deep_analysis_subsection(text, "4.3")
    if not section43:
        return
    normalized = _normalize(section43)
    funding_claim = re.search(
        r"(?:主力|超大单|大单|小单)[^。\n|]{0,30}(?:净流入|净流出|流入|流出)"
        r"|(?:主动买盘|被动卖盘|资金净流入|主力净卖出|北向|融资余额|融资融券|机构持仓|持仓结构|股东人数)",
        normalized,
    )
    if not funding_claim:
        return
    funding_support = (profile.get("formal_section_support") or {}).get("funding_support", 0)
    if funding_support and funding_support > 0:
        return
    yield QualityIssue(
        code="funding_claim_without_funding_support",
        severity="error",
        message="4.3 出现资金面判断但 profile 中 funding_support 为 0。",
        evidence=funding_claim.group(0),
    )


def _check_useless_core_fact(text: str) -> Iterable[QualityIssue]:
    section = _extract_markdown_section(text, "三、核心事实基座")
    if not section:
        return
    useless_patterns = (
        r"年报已发布",
        r"年度报告已发布",
        r"业绩预告已披露",
        r"预告已披露",
        r"分红已实施",
        r"权益分派已实施",
    )
    for pattern in useless_patterns:
        match = re.search(pattern, _normalize(section))
        if match:
            yield QualityIssue(
                code="useless_core_fact",
                severity="warning",
                message="核心事实基座包含仅表示文档存在的事实，应移除。",
                evidence=match.group(0),
            )


def _check_external_map_disclaimer_and_framing(text: str, profile: dict | None) -> Iterable[QualityIssue]:
    if not profile or profile.get("profile") != "formal_thin_external_rich":
        return
    section_id, section = _extract_external_map_section(text, profile)
    if not section:
        return
    normalized = _normalize(section)
    if "preview" not in normalized.lower() and "不参与评分" not in section and "display-only" not in normalized:
        yield QualityIssue(
            code="external_map_missing_display_only_disclaimer",
            severity="error",
            message=f"{section_id} 外部观点地图缺少 display-only / 不参与评分免责声明。",
        )
    # Scan only the claim body, excluding the blockquote disclaimer, for
    # strong confirmation terms.  The disclaimer itself contains words like
    # "确认" and must not trigger an unverified-claim framing error.
    claim_body = re.sub(r"(?m)^>.*$", "", section).strip()
    low_credit_only = not re.search(r"来源[:：]\s*(?:公告|年报|研报|官方|交易所)", section)
    if low_credit_only:
        confirmation_terms = ("确认", "已经", "确定", "进入供应链", "订单落地", "客户为")
        normalized_claim = _normalize(claim_body)
        for term in confirmation_terms:
            if term == "确认" and "未确认" in normalized_claim:
                continue
            if term in normalized_claim:
                yield QualityIssue(
                    code="external_map_unverified_claim_framing",
                    severity="error",
                    message=f"{section_id} 外部观点地图在低信用来源下使用强确认表述：{term}。",
                    evidence=term,
                )
                return
        for line in claim_body.splitlines():
            normalized_line = _normalize(line)
            if "反方约束" in normalized_line or "待验证证据" in normalized_line:
                continue
            market_position_term = next(
                (term for term in ("市占率", "份额", "占比") if term in normalized_line),
                None,
            )
            if not market_position_term:
                continue
            has_external_framing = re.search(
                r"外部材料称|外部观点称|据外部材料|据外部观点|该说法需|需(?:正式)?验证|待(?:正式)?验证|未经官方确认|不等同于官方确认|未确认",
                normalized_line,
            )
            if has_external_framing:
                continue
            yield QualityIssue(
                code="external_map_unverified_claim_framing",
                severity="error",
                message=f"{section_id} 外部观点地图在低信用来源下使用强确认表述：{market_position_term}。",
                evidence=market_position_term,
            )
            return


_GENERIC_TEMPLATE_TERMS = (
    "需关注",
    "验证变量",
    "供应链位置",
    "产业链位置",
    "市场情绪",
    "后续跟踪",
    "有望受益",
    "结构性机会",
    "景气度",
    "催化剂",
    "不确定性",
)

_EXPLANATION_TERMS = (
    "原因",
    "主要系",
    "主要由于",
    "受",
    "影响",
    "公司解释",
    "管理层",
    "变动原因",
    "所致",
)


def _check_section_too_generic(text: str) -> Iterable[QualityIssue]:
    for section_id in ("4.1", "4.2", "4.3"):
        section = _extract_deep_analysis_subsection(text, section_id)
        if not section:
            continue
        normalized = _normalize(section)
        hits = [term for term in _GENERIC_TEMPLATE_TERMS if term in normalized]
        if len(hits) < 2:
            continue
        if _has_specific_content(section):
            continue
        yield QualityIssue(
            code="section_too_generic",
            severity="warning",
            message=f"{section_id} 使用模板化变量词但缺少产品、数字、时间、公司或引用支撑。",
            evidence="terms=" + ",".join(hits[:4]),
        )


def _has_specific_content(section: str) -> bool:
    if re.search(r"\d+(?:\.\d+)?", section):
        return True
    if re.search(r"20\d{2}|Q[1-4]|[一二三四]季度|\d+月|\d+日", section, flags=re.IGNORECASE):
        return True
    if re.search(r"\[\^\d+\]", section):
        return True
    if re.search(r"(?:FPGA|FPAI|MCU|EEPROM|CPO|800G|1\.6T|CIS|SoC|NPU|NAND|Flash|DRAM|AI芯片|光模块)", section, flags=re.IGNORECASE):
        return True
    if re.search(r"[\u4e00-\u9fff]{2,}(?:股份|科技|电子|微电|创新|国微|光电|智控|生物|智能)", section):
        return True
    return False


def _check_vague_supply_chain_position(text: str) -> Iterable[QualityIssue]:
    section41 = _extract_deep_analysis_subsection(text, "4.1")
    if not section41:
        return
    normalized = _normalize(section41)
    has_supply_position = any(
        phrase in normalized
        for phrase in ("供应链位置", "产业链位置", "产业链地位", "供应链地位")
    )
    if not has_supply_position:
        return
    if any(term in normalized for term in OPERATING_VARIABLE_TERMS):
        return
    yield QualityIssue(
        code="vague_supply_chain_position",
        severity="warning",
        message="4.1 供应链/产业链位置表述缺少供应商、客户、产能、供需、库存、订单、价格或交期变量。",
        evidence="supply-chain position without operating variable",
    )


def _check_fundamentals_repeats_core_facts(text: str) -> Iterable[QualityIssue]:
    section42 = _extract_deep_analysis_subsection(text, "4.2")
    if not section42:
        return
    normalized = _normalize(section42)
    metric_hits = 0
    for pattern in (
        r"营业收入[^。；\n|]{0,30}\d+(?:\.\d+)?亿",
        r"(?:归母净利润|净利润)[^。；\n|]{0,30}\d+(?:\.\d+)?亿",
        r"毛利率[^。；\n|]{0,30}\d+(?:\.\d+)?%",
    ):
        if re.search(pattern, normalized):
            metric_hits += 1
    if metric_hits < 2:
        return
    if any(term in normalized for term in _EXPLANATION_TERMS):
        return
    yield QualityIssue(
        code="fundamentals_repeats_core_facts",
        severity="warning",
        message="4.2 重复核心财务数字但缺少变化原因、公司解释或管理层解释。",
        evidence=f"metric_hits={metric_hits}",
    )


def _check_external_viewpoint_overcompressed(text: str, profile: dict | None = None) -> Iterable[QualityIssue]:
    # New evidence-adaptive layout: external viewpoint map lives in 4.2 for
    # formal_thin_external_rich.  Visible reasoning cards are no longer required;
    # we check each reasoning-card marker individually rather than accepting any.
    if profile and profile.get("profile") == "formal_thin_external_rich":
        section_id, section = _extract_external_map_section(text, profile)
        if not section:
            return
        if not re.search(r"外部材料|外部观点|雪球|知乎|微信|精选外部", section):
            return
        markers = (
            ("**外部观点链**：", "外部观点链"),
            ("**支持线索**：", "支持线索"),
            ("**反方约束**：", "反方约束"),
            ("**待验证证据**：", "待验证证据"),
        )
        missing = [label for marker, label in markers if marker not in section]
        if not re.search(r"\[\^\d+\]", section):
            missing.append("inline citations")
        if missing:
            yield QualityIssue(
                code="external_viewpoint_overcompressed",
                severity="warning",
                message=f"{section_id} 外部观点地图缺少必要结构或 inline citations：{', '.join(missing)}。",
                evidence="missing=" + ",".join(missing),
            )
        return

    # Legacy 4.4 path: keep an external observation from being a bare paragraph.
    section44 = _extract_deep_analysis_subsection(text, "4.4")
    if not section44:
        return
    if not re.search(r"雪球|知乎|微信|精选外部|外部材料|外部观点", section44):
        return
    normalized44 = _normalize(section44)
    has_disclaimer = (
        "preview" in normalized44.lower()
        or "不参与评分" in section44
        or "display-only" in normalized44
    )
    has_inline_citations = re.search(r"\[\^\d+\]", section44) is not None
    if not has_disclaimer or not has_inline_citations:
        yield QualityIssue(
            code="external_viewpoint_overcompressed",
            severity="warning",
            message="4.4 外部观察缺少 display-only 免责声明或 inline citations，可能过度压缩。",
            evidence="4.4 external observation missing disclaimer or citations",
        )


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
