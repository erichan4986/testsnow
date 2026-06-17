"""Bounded LLM analysis helper for annual/semiannual report excerpts.

This module is intentionally helper-only in Phase 1:
- no CLI
- no Source Intake / evidence-note / pipeline wiring
- no import-time LLM client dependency

The LLM input is built only from deterministic extractor items, not the full
report text.  Output is typed as `periodic_report_analysis` with
`source_credit: 75` and `verification_status: professional_analysis`.

Phase 1 does NOT implement deterministic number/entity novelty detection.
Because of that, Phase 1 output must NOT be used as a source for new numbers,
new factual claims, Source Intake observations, core facts, synthesis context,
risk scoring, or recommendations.  A Phase 1.1 guard must reject summaries that
introduce numbers, dates, products, customers, capex figures, growth rates, or
named entities absent from the referenced extractor evidence before any pipeline
integration.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = "periodic_report_llm_analysis.v1"

_ALLOWED_SECTION_USAGES = frozenset({
    "management_narrative",
    "business_change",
    "risk_tension",
    "financial_red_flag",
    "capital_allocation",
})

_USAGE_PRIORITY = {
    "financial_forensics": 0,
    "risk_disclosure": 1,
    "management_view": 2,
    "capital_action": 3,
}

_MAX_ITEMS_DEFAULT = 20
_MAX_EVIDENCE_CHARS = 700
_MAX_PROMPT_EXCERPT_CHARS = 12000
_MAX_SECTIONS = 8
_MAX_FOLLOW_UP_QUESTIONS = 8
_MAX_SUMMARY_CHINESE_CHARS = 500

_CITATION_RE = re.compile(r"\[\^?\w+\]")
_URL_RE = re.compile(r"https?://\S+")
_REPEATED_SPACE_RE = re.compile(r"\s+")

_ILLEGAL_SUBSTRINGS = (
    "confirmed_fact",
    "fact_candidate",
    "核心事实",
    "已证实",
)


class PeriodicReportLLMError(Exception):
    """Raised when the LLM output cannot be validated."""


def build_periodic_report_llm_prompt(
    extractor_result: Dict[str, Any],
    *,
    max_items: int = _MAX_ITEMS_DEFAULT,
) -> Dict[str, Any]:
    """Build a bounded prompt dict from deterministic extractor output.

    Returns a dict with keys:
      - system: system-level instructions and guardrails
      - user: user-level content containing the selected excerpts
      - item_map: {item_id -> original extractor item} for validator reference
      - report_meta: {report_type, audit_status, industry}
    """
    if not isinstance(extractor_result, dict):
        raise TypeError("extractor_result must be a dict")

    items = extractor_result.get("items") or []
    selected = _select_items(items, max_items=max_items)
    item_map: Dict[str, Dict[str, Any]] = {}
    prompt_items: List[Dict[str, str]] = []

    for index, item in enumerate(selected):
        usage = item.get("usage", "other")
        item_id = f"{usage}-{index}"
        item_map[item_id] = item
        evidence = _clean_evidence(str(item.get("evidence", "")))
        evidence = _truncate_evidence(evidence, _MAX_EVIDENCE_CHARS)
        prompt_items.append({
            "id": item_id,
            "usage": usage,
            "severity": str(item.get("severity", "info")),
            "title": _clean_evidence(str(item.get("title", ""))),
            "evidence": evidence,
        })

    system_prompt = (
        "你是一个保守的年报/半年报分析助手。你的任务是基于下面给出的规则摘录进行总结和归类，"
        "不能补充外部事实，不能将管理层表述升级为确认事实。\n\n"
        "输出要求：\n"
        "- 仅输出 JSON，不要 Markdown 代码块，不要解释。\n"
        "- JSON schema_version 必须是：\"" + SCHEMA_VERSION + "\"\n"
        "- sections 中每个对象必须包含 usage、title、summary、evidence_refs、confidence。\n"
        "- sections[].usage 只允许：management_narrative、business_change、risk_tension、"
        "financial_red_flag、capital_allocation。\n"
        f"- sections 最多 {_MAX_SECTIONS} 条，优先保留最有信息量、最需要复核的要点。\n"
        f"- follow_up_questions 最多 {_MAX_FOLLOW_UP_QUESTIONS} 条。\n"
        "- follow_up_question 不允许出现在 sections[].usage；问题只能放在顶层 follow_up_questions。\n"
        "- evidence_refs 必须引用下方提供的 item id。\n"
        "- summary 中禁止引入证据中没有的数字、日期、产品名、客户名、capex 数据或增长率。\n"
        "- confidence 必须是 0 到 100 的整数。\n"
        "- 禁止出现以下任何字符串或概念：confirmed_fact、fact_candidate、核心事实、已证实。\n"
        "- 禁止出现 Markdown 引用标记，例如 [^1]、[1]、[^verified]、[^supported]、"
        "[^needs_review]、[^unverified]。\n"
        "- 禁止出现 raw URLs。\n\n"
        "表达规范：\n"
        "- 对 risk_disclosure 写成公司披露的风险，不得写成风险已经发生。\n"
        "- 对 management_view 写成管理层表述/公司称/年报称，不得写成独立事实。\n"
        "- 对 financial_forensics 写成规则观察或待复核线索，不得写成会计造假结论。\n"
        "- 如果证据不足，输出 follow-up question，不要编造结论。"
    )

    user_parts = [
        f"报告类型：{extractor_result.get('report_type', 'unknown')}",
        f"审计状态：{extractor_result.get('audit_status', 'unknown')}",
        f"行业 profile：{extractor_result.get('industry', 'generic')}",
        "",
        "摘录条目（仅基于这些条目总结）：",
        "",
    ]
    for prompt_item in prompt_items:
        user_parts.append(
            f"id: {prompt_item['id']}\n"
            f"usage: {prompt_item['usage']}\n"
            f"severity: {prompt_item['severity']}\n"
            f"title: {prompt_item['title']}\n"
            f"evidence: {prompt_item['evidence']}"
        )

    user_prompt = "\n\n".join(user_parts)
    if len(user_prompt) > _MAX_PROMPT_EXCERPT_CHARS:
        user_prompt = _truncate_text(user_prompt, _MAX_PROMPT_EXCERPT_CHARS)

    return {
        "system": system_prompt,
        "user": user_prompt,
        "item_map": item_map,
        "report_meta": {
            "report_type": extractor_result.get("report_type", "unknown"),
            "audit_status": extractor_result.get("audit_status", "unknown"),
            "industry": extractor_result.get("industry", "generic"),
        },
    }


def validate_periodic_report_llm_output(
    raw_text: str,
    item_map: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and sanitize raw LLM JSON output.

    Raises PeriodicReportLLMError when the whole analysis must be rejected.
    Returns a dict with the same shape as the final helper output but without
    credit metadata; callers should add those fields.
    """
    if not isinstance(raw_text, str):
        raise PeriodicReportLLMError("raw_text must be a string")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PeriodicReportLLMError(f"JSON parse failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise PeriodicReportLLMError("JSON root must be an object")

    if parsed.get("schema_version") != SCHEMA_VERSION:
        raise PeriodicReportLLMError(
            f"schema_version mismatch: {parsed.get('schema_version')!r}"
        )

    _reject_illegal_content(raw_text)

    sections = parsed.get("sections") or []
    follow_up_questions = parsed.get("follow_up_questions") or []

    if not isinstance(sections, list):
        raise PeriodicReportLLMError("sections must be a list")
    if not isinstance(follow_up_questions, list):
        raise PeriodicReportLLMError("follow_up_questions must be a list")

    if len(sections) > _MAX_SECTIONS:
        raise PeriodicReportLLMError(
            f"too many sections: {len(sections)} > {_MAX_SECTIONS}"
        )
    if len(follow_up_questions) > _MAX_FOLLOW_UP_QUESTIONS:
        raise PeriodicReportLLMError(
            f"too many follow_up_questions: {len(follow_up_questions)} > {_MAX_FOLLOW_UP_QUESTIONS}"
        )

    valid_sections: List[Dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        _reject_invalid_evidence_refs(section.get("evidence_refs"), item_map)
        normalized = _normalize_section(section, item_map)
        if normalized:
            valid_sections.append(normalized)

    valid_questions: List[Dict[str, Any]] = []
    for question in follow_up_questions:
        if not isinstance(question, dict):
            continue
        _reject_invalid_evidence_refs(question.get("evidence_refs"), item_map)
        normalized = _normalize_question(question, item_map)
        if normalized:
            valid_questions.append(normalized)

    if not valid_sections and not valid_questions:
        raise PeriodicReportLLMError("no valid sections or follow-up questions remain")

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": parsed.get("report_type", "unknown"),
        "audit_status": parsed.get("audit_status", "unknown"),
        "sections": valid_sections,
        "follow_up_questions": valid_questions,
    }


def summarize_periodic_report_with_llm(
    extractor_result: Dict[str, Any],
    client: object,
    *,
    max_items: int = _MAX_ITEMS_DEFAULT,
) -> Dict[str, Any]:
    """Run bounded LLM analysis on extractor output and return a safe result.

    The returned dict includes credit/verification metadata so callers can
    render or preview it without promoting it to a fact.
    """
    if not client:
        raise ValueError("client is required")

    items = extractor_result.get("items") or []
    if not items:
        return _empty_analysis(extractor_result)

    prompt = build_periodic_report_llm_prompt(extractor_result, max_items=max_items)
    item_map = prompt["item_map"]

    raw_response = _call_client(client, prompt)
    validated = validate_periodic_report_llm_output(raw_response, item_map)

    return {
        **validated,
        "report_type": extractor_result.get("report_type", "unknown"),
        "audit_status": extractor_result.get("audit_status", "unknown"),
        "source_type": "periodic_report_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": True,
    }


def render_periodic_report_llm_markdown(analysis: Dict[str, Any]) -> str:
    """Render a compact Markdown preview of the LLM analysis."""
    if not isinstance(analysis, dict):
        return ""

    lines = [
        "# 年报/半年报 LLM 分析预览",
        "",
        f"- 报告类型：{analysis.get('report_type', 'unknown')}",
        f"- 审计状态：{analysis.get('audit_status', 'unknown')}",
        f"- 来源类型：{analysis.get('source_type', 'periodic_report_analysis')}",
        f"- 信用等级：{analysis.get('source_credit', 75)}",
        f"- 核验状态：{analysis.get('verification_status', 'professional_analysis')}",
        "",
        "> 本预览仅基于规则摘录的 LLM 压缩总结，管理层观点和财报排雷仅供复核，"
        "不等同于确认事实，不参与评分或建议。",
        "",
    ]

    sections = analysis.get("sections") or []
    if sections:
        lines.append("## 分析要点")
        lines.append("")
        for section in sections:
            title = _escape_md(str(section.get("title", "")))
            usage = str(section.get("usage", ""))
            summary = _escape_md(str(section.get("summary", "")))
            confidence = section.get("confidence", "—")
            refs = section.get("evidence_refs") or []
            lines.append(f"### {title} ({usage}, 置信度 {confidence})")
            lines.append("")
            lines.append(summary)
            lines.append("")
            if refs:
                lines.append(f"**依据摘录**：{', '.join(str(r) for r in refs)}")
                lines.append("")

    questions = analysis.get("follow_up_questions") or []
    if questions:
        lines.append("## 待验证问题")
        lines.append("")
        for index, question in enumerate(questions, 1):
            q = _escape_md(str(question.get("question", "")))
            refs = question.get("evidence_refs") or []
            ref_text = f"（依据：{', '.join(str(r) for r in refs)}）" if refs else ""
            lines.append(f"{index}. {q} {ref_text}")
        lines.append("")

    if not sections and not questions:
        lines.append("未生成有效分析要点。")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _select_items(
    items: Iterable[Dict[str, Any]],
    *,
    max_items: int,
) -> List[Dict[str, Any]]:
    """Select and prioritize extractor items for the LLM prompt."""
    scored: List[Tuple[int, int, Dict[str, Any]]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        usage = item.get("usage", "other")
        priority = _USAGE_PRIORITY.get(usage, 99)
        scored.append((priority, index, item))

    scored.sort(key=lambda x: (x[0], x[1]))
    return [item for _, _, item in scored[:max_items]]


def _clean_evidence(text: str) -> str:
    """Remove citation markers, URLs, and collapse whitespace."""
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _REPEATED_SPACE_RE.sub(" ", text)
    return text.strip()


def _truncate_evidence(text: str, max_chars: int) -> str:
    """Truncate evidence so the returned string length never exceeds max_chars."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _call_client(client: object, prompt: Dict[str, Any]) -> str:
    """Call a duck-typed client. Prefer `.chat(prompt)` if present."""
    system = prompt.get("system", "")
    user = prompt.get("user", "")
    full_prompt = f"{system}\n\n{user}".strip()

    chat_fn = getattr(client, "chat", None)
    if callable(chat_fn):
        return str(chat_fn(full_prompt))

    completions = getattr(client, "chat", None)
    if hasattr(completions, "completions"):
        completions = completions.completions
    if hasattr(completions, "create"):
        response = completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=getattr(client, "model", "default"),
        )
        return _extract_completion_text(response)

    raise PeriodicReportLLMError(
        "client must provide .chat(prompt) or .chat.completions.create(...)"
    )


def _extract_completion_text(response: object) -> str:
    """Extract text from a chat.completion response object."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            return str(message.get("content", ""))
        return str(response.get("content", ""))
    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        if hasattr(first, "message"):
            return str(getattr(first.message, "content", ""))
        if isinstance(first, dict):
            message = first.get("message", {})
            return str(message.get("content", ""))
    return str(response)


def _reject_illegal_content(text: str) -> None:
    """Reject output that contains forbidden status markers anywhere."""
    lower = text.lower()
    for substring in _ILLEGAL_SUBSTRINGS:
        if substring in lower:
            raise PeriodicReportLLMError(
                f"illegal content detected: {substring!r}"
            )


def _validate_evidence_refs(
    refs: Any,
    item_map: Dict[str, Any],
) -> List[str]:
    """Return only refs that exist in the item_map."""
    if not isinstance(refs, list):
        return []
    valid: List[str] = []
    for ref in refs:
        if isinstance(ref, str) and ref in item_map:
            valid.append(ref)
    return valid


def _reject_invalid_evidence_refs(refs: Any, item_map: Dict[str, Any]) -> None:
    """Fail closed when the LLM references evidence that was not provided."""
    if not isinstance(refs, list) or not refs:
        raise PeriodicReportLLMError("invalid evidence_refs")
    for ref in refs:
        if not isinstance(ref, str) or ref not in item_map:
            raise PeriodicReportLLMError("invalid evidence_refs")


def _has_citation_markers(text: str) -> bool:
    return bool(_CITATION_RE.search(text))


def _chinese_char_count(text: str) -> int:
    """Approximate Chinese-character count for summary length guard."""
    return sum(1 for ch in text if "一" <= ch <= "鿿")


def _normalize_section(
    section: Dict[str, Any],
    item_map: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Validate and sanitize a single section; return None if it should drop."""
    usage = str(section.get("usage", "")).strip().lower()
    if usage not in _ALLOWED_SECTION_USAGES:
        return None

    title = _sanitize_text(str(section.get("title", "")))
    summary = str(section.get("summary", ""))
    if _has_citation_markers(summary) or _has_citation_markers(title):
        return None
    summary = _sanitize_text(summary)
    if not summary:
        return None

    if _chinese_char_count(summary) > _MAX_SUMMARY_CHINESE_CHARS:
        return None

    refs = _validate_evidence_refs(section.get("evidence_refs"), item_map)
    if not refs:
        return None

    confidence = section.get("confidence")
    if not isinstance(confidence, int) or isinstance(confidence, bool):
        try:
            confidence = int(confidence)
        except (TypeError, ValueError):
            return None
    if confidence < 0 or confidence > 100:
        return None

    return {
        "usage": usage,
        "title": title,
        "summary": summary,
        "evidence_refs": refs,
        "confidence": confidence,
    }


def _normalize_question(
    question: Dict[str, Any],
    item_map: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Validate and sanitize a single follow-up question."""
    q = str(question.get("question", ""))
    if _has_citation_markers(q):
        return None
    q = _sanitize_text(q)
    if not q:
        return None

    refs = _validate_evidence_refs(question.get("evidence_refs"), item_map)
    if not refs:
        return None

    return {
        "question": q,
        "evidence_refs": refs,
    }


def _sanitize_text(text: str) -> str:
    """Remove citations, URLs, and normalize whitespace."""
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _REPEATED_SPACE_RE.sub(" ", text)
    return text.strip()


def _empty_analysis(extractor_result: Dict[str, Any]) -> Dict[str, Any]:
    """Return an empty analysis without calling the LLM."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source_type": "periodic_report_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": True,
        "report_type": extractor_result.get("report_type", "unknown"),
        "audit_status": extractor_result.get("audit_status", "unknown"),
        "sections": [],
        "follow_up_questions": [],
    }


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
