"""Heuristic prose-quality checks for generated stock reports.

These checks are intentionally advisory. They look at the final Markdown
artifact and surface readability / repetition warnings without changing the
existing hard report-quality gate.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

try:
    from .deep_analysis_topic_ownership import TOPIC_FAMILIES
except ImportError:
    from deep_analysis_topic_ownership import TOPIC_FAMILIES


LONG_PARAGRAPH_CHARS = 260
LONG_SENTENCE_CHARS = 110
BORROWED_THEME_SENTENCE_CHARS = 110

THEME_TERMS = [
    "AI算力",
    "800G",
    "1.6T",
    "硅光",
    "CPO",
    "NPO",
    "XPO",
    "英伟达",
    "谷歌",
    "北美云厂商",
    "资本开支",
    "预付款",
    "毛利率",
    "估值",
    "融资盘",
    "融资余额",
]

AIISH_PATTERNS = [
    r"综合来看",
    r"展望未来",
    r"与此同时",
    r"核心驱动力",
    r"结构性繁荣",
    r"有望持续受益",
    r"在[^。\n，,]{0,30}背景下",
]

STRONG_ASSERTION_PATTERNS = [
    r"锁定",
    r"近乎垄断",
    r"垄断级",
    r"确定性极强",
    r"必然",
    r"必须",
    r"已确认",
    r"确认获得",
    r"已验证",
]


@dataclass
class ProseIssue:
    """A single prose-quality warning."""

    code: str
    severity: str
    message: str
    evidence: str = ""
    section: str = ""


@dataclass
class ProseQualityResult:
    """Aggregate prose-quality result."""

    path: str
    passed: bool
    issues: List[ProseIssue]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "passed": self.passed,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def check_report_prose_file(path: str | Path) -> ProseQualityResult:
    """Check a Markdown report file for advisory prose-quality issues."""
    report_path = Path(path)
    text = report_path.read_text(encoding="utf-8")
    return check_report_prose_text(text, path=str(report_path))


def check_report_prose_text(text: str, path: str = "<memory>") -> ProseQualityResult:
    """Check Markdown report prose and return warning-only issues."""
    sections = _extract_deep_analysis_sections(text)
    issues: List[ProseIssue] = []

    main_sections = {key: value for key, value in sections.items() if key in {"4.1", "4.2", "4.3"}}
    issues.extend(_check_nested_headings(main_sections))
    issues.extend(_check_long_paragraphs_and_sentences(main_sections))
    issues.extend(_check_repeated_themes(main_sections))
    issues.extend(_check_theme_reexpanded_outside_owner(main_sections))
    issues.extend(_check_aiish_transitions(main_sections))
    issues.extend(_check_strong_assertions(main_sections))
    if "4.4" in sections:
        issues.extend(_check_duplicate_4_4_citations(sections["4.4"]))

    # Current checker is advisory: warnings should not fail the report pipeline.
    return ProseQualityResult(path=path, passed=True, issues=issues)


def format_prose_quality_result(result: ProseQualityResult) -> str:
    """Human-readable CLI output."""
    lines = [f"PASS: {result.path}"]
    if not result.issues:
        lines.append("No prose-quality warnings found.")
        return "\n".join(lines)

    for issue in result.issues:
        location = f" ({issue.section})" if issue.section else ""
        lines.append(f"- [{issue.severity.upper()}] {issue.code}{location}: {issue.message}")
        if issue.evidence:
            lines.append(f"  evidence: {issue.evidence}")
    return "\n".join(lines)


def _extract_deep_analysis_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^###\s+(4\.\d)\s+[^\n]*$", text, flags=re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        next_major = re.search(
            r"^##\s+(?:[一二三四五六七八九十]+[、.．]|综合风险评分|风险提示|引用来源)",
            text[start:end],
            flags=re.MULTILINE,
        )
        if next_major:
            end = start + next_major.start()
        sections[key] = text[start:end].strip()
    return sections


def _check_nested_headings(sections: dict[str, str]) -> Iterable[ProseIssue]:
    for section, body in sections.items():
        for line in body.splitlines():
            stripped = line.strip()
            if re.match(r"^##+\s+", stripped):
                yield ProseIssue(
                    code="nested_heading_in_deep_analysis",
                    severity="warning",
                    section=section,
                    message="4.1-4.3 正文中出现 Markdown 子标题，建议改成加粗行内标签，避免破坏章节层级。",
                    evidence=stripped,
                )


def _check_long_paragraphs_and_sentences(sections: dict[str, str]) -> Iterable[ProseIssue]:
    for section, body in sections.items():
        for paragraph in _iter_prose_paragraphs(body):
            plain = _strip_markdown(paragraph)
            if len(plain) > LONG_PARAGRAPH_CHARS:
                yield ProseIssue(
                    code="long_paragraph",
                    severity="warning",
                    section=section,
                    message=f"深度分析段落过长，建议拆成观点、证据、推导两到三段（>{LONG_PARAGRAPH_CHARS}字）。",
                    evidence=f"{len(plain)} chars: {_preview(plain)}",
                )
            for sentence in _split_sentences(plain):
                if len(sentence) > LONG_SENTENCE_CHARS:
                    yield ProseIssue(
                        code="long_sentence",
                        severity="warning",
                        section=section,
                        message=f"单句过长，建议拆句或改成表格/分号结构（>{LONG_SENTENCE_CHARS}字）。",
                        evidence=f"{len(sentence)} chars: {_preview(sentence)}",
                    )


def _check_repeated_themes(sections: dict[str, str]) -> Iterable[ProseIssue]:
    repeated = []
    for term in THEME_TERMS:
        present_in = [
            section for section, body in sections.items() if re.search(re.escape(term), body, flags=re.IGNORECASE)
        ]
        if len(present_in) >= 3:
            repeated.append(f"{term}({','.join(present_in)})")
    if repeated:
        yield ProseIssue(
            code="repeated_theme_across_sections",
            severity="warning",
            message="4.1/4.2/4.3 出现跨章节主题重复，建议把产业、业绩、资金面的信息边界拆开。",
            evidence="; ".join(repeated[:12]),
        )


def _check_theme_reexpanded_outside_owner(sections: dict[str, str]) -> Iterable[ProseIssue]:
    for family in TOPIC_FAMILIES:
        owner_section = family.get("owner_section", "")
        terms = family.get("terms", [])
        for section, body in sections.items():
            if section == owner_section:
                continue
            prose_hits = _borrowed_theme_prose_hits(body, terms)
            table_hits = _borrowed_theme_table_hits(body, terms)
            if not _is_reexpanded(prose_hits, table_hits):
                continue
            matched_terms = sorted({term for hit in prose_hits + table_hits for term in hit["terms"]})
            evidence = {
                "term_family": family.get("family", ""),
                "terms": matched_terms,
                "owner_section": owner_section,
                "offending_section": section,
                "prose_paragraph_count": len(prose_hits),
                "table_row_count": len(table_hits),
                "sample": _preview((prose_hits or table_hits)[0]["text"], limit=90),
            }
            yield ProseIssue(
                code="theme_reexpanded_outside_owner",
                severity="warning",
                section=section,
                message="非本节拥有的主题被重复展开，建议改成一句上下文或绑定到本节变量的单行表格。",
                evidence=json.dumps(evidence, ensure_ascii=False),
            )


def _borrowed_theme_prose_hits(body: str, terms: list[str]) -> list[dict]:
    hits = []
    for paragraph in _iter_prose_paragraphs(body):
        matched_terms = _matched_terms(paragraph, terms)
        if matched_terms:
            hits.append({
                "text": paragraph,
                "terms": matched_terms,
                "chars": len(_strip_markdown(paragraph)),
            })
    return hits


def _borrowed_theme_table_hits(body: str, terms: list[str]) -> list[dict]:
    hits = []
    for row in _iter_table_rows(body):
        matched_terms = _matched_terms(row, terms)
        if matched_terms:
            hits.append({"text": row, "terms": matched_terms})
    return hits


def _is_reexpanded(prose_hits: list[dict], table_hits: list[dict]) -> bool:
    if len(prose_hits) > 1:
        return True
    if len(table_hits) > 1:
        return True
    if prose_hits and table_hits:
        return True
    if prose_hits and prose_hits[0].get("chars", 0) > BORROWED_THEME_SENTENCE_CHARS:
        return True
    return False


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if re.search(re.escape(term), text, flags=re.IGNORECASE)]


def _check_aiish_transitions(sections: dict[str, str]) -> Iterable[ProseIssue]:
    hits = []
    combined = "\n".join(sections.values())
    for pattern in AIISH_PATTERNS:
        for match in re.finditer(pattern, combined):
            hits.append(match.group(0))
    if len(hits) >= 3:
        unique_hits = []
        for hit in hits:
            if hit not in unique_hits:
                unique_hits.append(hit)
        yield ProseIssue(
            code="aiish_transition_overuse",
            severity="warning",
            message="深度分析中模板化过渡词偏多，建议改成更具体的变量、时间点或数据承接。",
            evidence="; ".join(unique_hits[:10]),
        )


def _check_strong_assertions(sections: dict[str, str]) -> Iterable[ProseIssue]:
    hits = []
    combined = "\n".join(sections.values())
    for pattern in STRONG_ASSERTION_PATTERNS:
        for match in re.finditer(pattern, combined):
            hits.append(match.group(0))
    if hits:
        yield ProseIssue(
            code="strong_assertion_wording",
            severity="warning",
            message="深度分析含强确认/强垄断措辞，建议改成按来源置信度分层的审慎表述。",
            evidence="; ".join(dict.fromkeys(hits)),
        )


def _check_duplicate_4_4_citations(section_body: str) -> Iterable[ProseIssue]:
    urls = re.findall(r"https?://[^\s|）)]+", section_body)
    counts: dict[str, int] = {}
    for url in urls:
        counts[url] = counts.get(url, 0) + 1
    duplicates = [f"{url} x{count}" for url, count in counts.items() if count > 1]

    fallback_counts: dict[str, int] = {}
    for line in section_body.splitlines():
        key = _citation_fallback_key(line)
        if key:
            fallback_counts[key] = fallback_counts.get(key, 0) + 1
    duplicates.extend(f"{key} x{count}" for key, count in fallback_counts.items() if count > 1)
    if duplicates:
        yield ProseIssue(
            code="duplicate_4_4_citation_source",
            severity="warning",
            section="4.4",
            message="4.4 引用列表存在同源重复，建议合并同一 URL 或同一文章来源。",
            evidence="; ".join(duplicates[:10]),
        )


def _citation_fallback_key(line: str) -> str:
    if not re.match(r"^\s*-\s+\[\^\d+\]", line):
        return ""
    if re.search(r"https?://", line):
        return ""

    source_match = re.match(r"^\s*-\s+\[\^\d+\]\s*([^|]+)", line)
    source = source_match.group(1).strip() if source_match else ""
    author_match = re.search(r"作者:\s*([^|《]+)", line)
    author = author_match.group(1).strip() if author_match else ""
    title_match = re.search(r"《([^》]+)》", line)
    title = title_match.group(1).strip() if title_match else ""
    if not (source and (author or title)):
        return ""
    return "|".join([source, author, title])


def _iter_prose_paragraphs(body: str) -> Iterable[str]:
    for raw in re.split(r"\n\s*\n", body):
        paragraph = raw.strip()
        if not paragraph:
            continue
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            continue
        if all(_is_non_prose_line(line) for line in lines):
            continue
        yield " ".join(line for line in lines if not _is_non_prose_line(line))


def _is_non_prose_line(line: str) -> bool:
    return (
        line.startswith("|")
        or line.startswith("- ")
        or line.startswith("> ")
        or line.startswith("#")
        or line.startswith("**本节引用来源")
        or re.match(r"^\[\^\d+\]:", line) is not None
    )


def _iter_table_rows(body: str) -> Iterable[str]:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?", stripped):
            continue
        yield stripped


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；])", text)
    return [part.strip() for part in parts if part.strip()]


def _strip_markdown(text: str) -> str:
    text = re.sub(r"\[\^?\d+\]", "", text)
    text = re.sub(r"[*_`#>|\-]", "", text)
    return re.sub(r"\s+", "", text)


def _preview(text: str, limit: int = 80) -> str:
    normalized = re.sub(r"\s+", "", text)
    return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."
