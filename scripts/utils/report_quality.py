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


def check_report_file(path: str | Path) -> QualityResult:
    """Check a Markdown report file."""
    report_path = Path(path)
    text = report_path.read_text(encoding="utf-8")
    return check_report_text(text, path=str(report_path))


def check_report_text(text: str, path: str = "<memory>") -> QualityResult:
    """Check report Markdown text and return structured issues."""
    issues: List[QualityIssue] = []
    normalized = _normalize(text)

    issues.extend(_check_required_signals(normalized))
    issues.extend(_check_contradictions(normalized))

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


def _check_required_signals(text: str) -> Iterable[QualityIssue]:
    for code, (label, patterns) in REQUIRED_SIGNALS.items():
        if not any(re.search(p, text, flags=re.IGNORECASE) for p in patterns):
            yield QualityIssue(
                code=f"missing_{code}",
                severity="error",
                message=f"报告缺少必要质量要素：{label}",
            )


def _check_contradictions(text: str) -> Iterable[QualityIssue]:
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
