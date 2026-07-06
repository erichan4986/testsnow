"""Deterministic source-boundary checks for generated report Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List
import json
import re


FORMAL_ANALYSIS_SOCIAL_TOKENS = (
    "雪球",
    "知乎",
    "微信公众号",
    "微信精选",
    "精选外部",
    "外部观点",
    "雪球专栏观察",
    "雪球评论观察",
    "雪球精选观察",
    "微信公众号精选观察",
    "知乎精选观察",
)

DISPLAY_ONLY_LEAK_TOKENS = (
    "雪球专栏观察",
    "雪球评论观察",
    "雪球精选观察",
    "微信公众号精选观察",
    "知乎精选观察",
    "精选外部观察",
    "精选外部材料",
    "外部观点与待验证变量",
)

CURATED_EXTERNAL_DISCLAIMER_TOKENS = (
    "仅作为专业观察",
    "不等同于官方确认事实",
    "不参与评分",
)


@dataclass
class SourceBoundaryIssue:
    code: str
    message: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "evidence": self.evidence}


@dataclass
class SourceBoundaryResult:
    path: str | None
    issues: List[SourceBoundaryIssue]

    @property
    def passed(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def check_report_source_boundary_file(path: Path) -> SourceBoundaryResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    result = check_report_source_boundary_text(text)
    result.path = str(path)
    return result


def check_report_source_boundary_text(text: str) -> SourceBoundaryResult:
    body = str(text or "")
    issues: List[SourceBoundaryIssue] = []

    profile = _parse_deep_analysis_profile(body)

    formal_region = _formal_deep_analysis_region(body, profile)
    for token in FORMAL_ANALYSIS_SOCIAL_TOKENS:
        line = _first_line_containing(formal_region, token)
        if line:
            issues.append(
                SourceBoundaryIssue(
                    code="social_source_in_formal_analysis",
                    message="4.1-4.3 formal analysis contains social/external viewpoint source token",
                    evidence=line,
                )
            )
            break

    external_region = _curated_external_region(body, profile)
    if external_region and not all(token in external_region for token in CURATED_EXTERNAL_DISCLAIMER_TOKENS):
        issues.append(
            SourceBoundaryIssue(
                code="missing_4_4_disclaimer",
                message="4.4 external viewpoint section is missing the display-only disclaimer",
                evidence=_first_heading_line(external_region) or "4.4 section",
            )
        )

    protected_text = _remove_curated_external_region(body, profile)
    protected_text = _remove_global_reference_sections(protected_text)
    protected_text = _drop_static_data_source_banner(protected_text)
    for token in DISPLAY_ONLY_LEAK_TOKENS:
        line = _first_line_containing(protected_text, token)
        if line:
            issues.append(
                SourceBoundaryIssue(
                    code="external_viewpoint_leak_outside_4_4",
                    message="display-only external viewpoint label appears outside 4.4",
                    evidence=line,
                )
            )
            break

    return SourceBoundaryResult(path=None, issues=issues)


def format_source_boundary_result(result: SourceBoundaryResult) -> str:
    label = result.path or "<text>"
    if result.passed:
        return f"PASS: {label}\nNo source-boundary issues found."
    lines = [f"FAIL: {label}"]
    for issue in result.issues:
        lines.append(f"- [{issue.code}] {issue.message}")
        if issue.evidence:
            lines.append(f"  evidence: {issue.evidence}")
    return "\n".join(lines)


def source_boundary_results_to_json(results: list[SourceBoundaryResult]) -> str:
    return json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2)


def _formal_deep_analysis_region(text: str, profile: dict | None = None) -> str:
    start = _find_heading(text, r"^###\s+4\.1\b")
    if start < 0:
        return ""
    search_from = _after_heading_line(text, start)
    if profile and profile.get("profile") == "formal_medium":
        section43_start = _find_heading(text, r"^###\s+4\.3\b", search_from)
        if section43_start >= 0:
            return text[start:section43_start]
    # For formal_thin_external_rich the display-only external viewpoint map
    # lives in 4.2 and is allowed to contain social/external source tokens.
    # Scan 4.1 and 4.3 only, skipping the 4.2 external viewpoint map region.
    if profile and profile.get("profile") == "formal_thin_external_rich":
        if _is_annual_broker_external_layout(profile):
            section43_start = _find_heading(text, r"^###\s+4\.3\b", search_from)
            if section43_start >= 0:
                return text[start:section43_start]
        section42_start = _find_heading(text, r"^###\s+4\.2\b", search_from)
        if section42_start >= 0:
            section43_start = _find_heading(text, r"^###\s+4\.3\b", _after_heading_line(text, section42_start))
            if section43_start >= 0:
                before_42 = text[start:section42_start]
                after_42_heading = _after_heading_line(text, section43_start)
                end = _find_heading(text, r"^###\s+4\.4\b", after_42_heading)
                if end < 0:
                    end = _find_heading(text, r"^##\s+[^#]", after_42_heading)
                if end < 0:
                    end = len(text)
                return before_42 + text[section43_start:end]
    end = _find_heading(text, r"^###\s+4\.4\b", search_from)
    if end < 0:
        end = _find_heading(text, r"^##\s+[^#]", search_from)
    if end < 0:
        end = len(text)
    return text[start:end]


def _parse_deep_analysis_profile(text: str) -> dict | None:
    match = re.search(r"<!--\s*deep_analysis_profile:\s*(.*?)\s*-->", text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception:
        return None


def _is_annual_broker_external_layout(profile: dict | None) -> bool:
    return bool(
        profile
        and profile.get("profile") == "formal_thin_external_rich"
        and profile.get("formal_thin_layout_variant") == "annual_broker_external_checklist"
    )


def _curated_external_section_pattern(profile: dict | None) -> str:
    if _is_annual_broker_external_layout(profile):
        return r"^###\s+4\.3\b"
    if profile and profile.get("profile") == "formal_medium":
        return r"^###\s+4\.3\b"
    if profile and profile.get("profile") == "formal_thin_external_rich":
        return r"^###\s+4\.2\b"
    return r"^###\s+4\.4\b"


def _curated_external_region(text: str, profile: dict | None = None) -> str:
    start = _find_heading(text, _curated_external_section_pattern(profile))
    if start < 0:
        return ""
    end = _find_heading(text, r"^##\s+[^#]", _after_heading_line(text, start))
    if end < 0:
        end = len(text)
    return text[start:end]


def _remove_curated_external_region(text: str, profile: dict | None = None) -> str:
    start = _find_heading(text, _curated_external_section_pattern(profile))
    if start < 0:
        return text
    end = _find_heading(text, r"^##\s+[^#]", _after_heading_line(text, start))
    if end < 0:
        end = len(text)
    return text[:start] + "\n" + text[end:]


def _remove_global_reference_sections(text: str) -> str:
    """Remove report-wide reference appendices from display-only leak scans."""
    cleaned = text
    for heading in (r"^##\s+引用来源\b",):
        start = _find_heading(cleaned, heading)
        if start < 0:
            continue
        end = _find_heading(cleaned, r"^##\s+[^#]", _after_heading_line(cleaned, start))
        if end < 0:
            end = len(cleaned)
        cleaned = cleaned[:start] + "\n" + cleaned[end:]
    return cleaned


def _find_heading(text: str, pattern: str, start: int = 0) -> int:
    match = re.search(pattern, text[start:], flags=re.M)
    return -1 if match is None else start + match.start()


def _after_heading_line(text: str, start: int) -> int:
    line_end = text.find("\n", start)
    return len(text) if line_end < 0 else line_end + 1


def _first_line_containing(text: str, token: str) -> str:
    for line in str(text or "").splitlines():
        if token in line:
            return line.strip()
    return ""


def _first_heading_line(text: str) -> str:
    for line in str(text or "").splitlines():
        if line.lstrip().startswith("#"):
            return line.strip()
    return ""


def _drop_static_data_source_banner(text: str) -> str:
    lines = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("**数据来源**") or stripped.startswith("数据来源"):
            continue
        lines.append(line)
    return "\n".join(lines)
