"""Experimental full-text periodic report LLM analysis path.

This module intentionally runs in parallel to the deterministic evidence-pack
path.  It keeps larger annual-report chunks for LLM reading, while reusing the
v2 validator so outputs remain grounded by evidence refs.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from periodic_report_evidence_pack import build_periodic_report_evidence_pack
from periodic_report_llm_analysis_v2 import (
    PeriodicReportLLMv2Error,
    _check_fidelity,
    _has_citation_markers,
    _has_raw_url,
    _normalize_confidence,
    _sanitize_text,
)


FULLTEXT_SCHEMA_VERSION = "periodic_report_fulltext_pack.v1"
FULLTEXT_ANALYSIS_SCHEMA_VERSION = "periodic_report_fulltext_analysis.v1"
FIXED_ANALYSIS_SECTION_TITLES = (
    "公司画像",
    "主营业务表现",
    "客户与订单结构",
    "研发与技术进展",
    "管理层市场判断",
    "财务风险与跟踪指标",
)
FINANCIAL_RISK_CANDIDATE_TYPES = (
    "profit_quality",
    "revenue_recognition",
    "customer_concentration",
    "supplier_concentration",
    "inventory_impairment",
    "receivables_collection",
    "cash_flow_quality",
    "capex_capacity",
    "asset_impairment",
    "rd_conversion",
    "government_grant_dependency",
    "financial_asset_dependency",
    "goodwill_impairment",
    "fx_overseas_exposure",
    "related_party_governance",
    "audit_internal_control",
    "litigation_contingency",
    "other_material_risk",
)
_ALLOWED_RISK_IMPORTANCE = frozenset({"high", "medium", "low"})

_DEFAULT_CHUNK_CHARS = 8000
_DEFAULT_MAX_TOTAL_CHARS = 120000
_DEFAULT_MAX_CHUNKS = 18
_DEFAULT_MAX_PROMPT_CHARS = 140000

_SECTION_HEADING_RE = re.compile(r"(?m)^\s*(?:#\s*)?(第[一二三四五六七八九十]+[节章节][^\n\r]{0,60})")
_CITATION_RE = re.compile(r"\[\^?\w+\]")
_URL_RE = re.compile(r"https?://\S+")
_SPACE_RE = re.compile(r"\s+")


class PeriodicReportFulltextError(Exception):
    """Raised when full-text LLM analysis output is invalid."""


def build_periodic_report_fulltext_pack(
    text: str,
    *,
    report_type: str = "auto",
    chunk_chars: int = _DEFAULT_CHUNK_CHARS,
    max_total_chars: int = _DEFAULT_MAX_TOTAL_CHARS,
    max_chunks: int = _DEFAULT_MAX_CHUNKS,
) -> Dict[str, Any]:
    """Build larger section-aware evidence chunks from a periodic report text."""
    if not text:
        return {
            "schema_version": FULLTEXT_SCHEMA_VERSION,
            "report_type": "unknown" if report_type == "auto" else report_type,
            "audit_status": "unknown",
            "blocks": [],
            "experimental": True,
        }

    metadata = build_periodic_report_evidence_pack(text, report_type=report_type)
    cleaned = _clean_fulltext(text)
    sections = _split_major_sections(cleaned)
    if not sections:
        sections = [("全文", cleaned)]

    blocks: List[Dict[str, Any]] = []
    used_chars = 0
    for section_index, (heading, content) in enumerate(sections):
        if used_chars >= max_total_chars or len(blocks) >= max_chunks:
            break
        remaining = max_total_chars - used_chars
        if remaining <= 0:
            break
        for chunk_index, chunk in enumerate(_chunk_text(content, min(chunk_chars, remaining))):
            if used_chars >= max_total_chars or len(blocks) >= max_chunks:
                break
            chunk = chunk[: max_total_chars - used_chars]
            usage = _usage_for_fulltext_heading(heading)
            blocks.append({
                "id": f"fulltext-{section_index}-{chunk_index}",
                "usage": usage,
                "section": _clean_line(heading),
                "title": _clean_line(heading),
                "text": chunk,
                "source_span": {"start": 0, "end": 0},
            })
            used_chars += len(chunk)

    return {
        "schema_version": FULLTEXT_SCHEMA_VERSION,
        "report_type": metadata.get("report_type", "unknown"),
        "audit_status": metadata.get("audit_status", "unknown"),
        "blocks": blocks,
        "experimental": True,
        "max_total_chars": max_total_chars,
        "chunk_chars": chunk_chars,
    }


def build_periodic_report_fulltext_prompt(
    fulltext_pack: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
    max_prompt_chars: int = _DEFAULT_MAX_PROMPT_CHARS,
) -> Dict[str, Any]:
    """Build a large-context prompt for the experimental full-text path."""
    blocks = fulltext_pack.get("blocks") or []
    schema_example = {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "sections": [
            {
                "title": "管理层市场判断",
                "judgments": [
                    {
                        "judgment": "管理层认为下游...，这意味着...",
                        "evidence_refs": ["fulltext-2-0"],
                        "confidence": 80,
                    }
                ],
            }
        ],
        "financial_risks": [
            {
                "risk_type": "inventory_impairment",
                "importance": "high",
                "summary": "存货...，资产减值...",
                "mechanism": "若需求转弱，可能继续计提跌价并压制毛利率。",
                "tracking_indicators": ["存货余额", "跌价准备", "毛利率"],
                "evidence_refs": ["fulltext-7-0"],
                "confidence": 85,
            },
            {
                "risk_type": "other_material_risk",
                "custom_label": "型号批产节奏风险",
                "importance": "high",
                "summary": "年报称...",
                "mechanism": "该风险不在候选池内，但会影响收入确认和产能利用率。",
                "tracking_indicators": ["订单节奏", "产能利用率"],
                "evidence_refs": ["fulltext-2-0"],
                "confidence": 80,
            },
        ],
    }
    section_names = " / ".join(FIXED_ANALYSIS_SECTION_TITLES)
    system = (
        "你是一个保守但有判断力的定期报告分析助手。当前使用的是全文/大块年报实验路径："
        "输入不是关键词摘录，而是年报较大章节块。目标是产出最终股票报告可复用的六段判断摘要，"
        "不是简单事实列表，也不是最终投资报告。\n\n"
        "允许在证据范围内做判断：你可以写“这意味着/说明/需要跟踪/形成压力/构成支撑”等分析，"
        "但每个判断必须绑定 evidence_refs，且判断中的数字、日期、产品名、客户名、供应商名必须来自对应证据块。"
        "不得补充外部事实，不得给出买卖建议、仓位建议或估值结论。\n\n"
        "必须输出严格 JSON，不要 Markdown 代码块，不要解释。schema_version 必须为 "
        f"{FULLTEXT_ANALYSIS_SCHEMA_VERSION}。允许顶层字段只有：schema_version、sections、financial_risks。\n\n"
        f"schema 示例：{schema_example}\n\n"
        "如果用户消息中提供 required_business_metrics，它是确定性表格摘录，只能作为写作覆盖清单和数值校验参考；"
        "不得把 required_business_metrics 作为 LLM 输出顶层字段，也不得把其中的 evidence-pack id "
        "（例如 segment_margin_table-0、production_sales_inventory_table-0、customer_supplier_table-0）写入 evidence_refs。"
        "evidence_refs 只能引用 fulltext-* id。\n\n"
        f"sections 必须且只能按以下 6 段输出，顺序也必须一致：{section_names}。"
        "每段必须包含 title 和 judgments。judgments 是对象数组，每项只允许字段：judgment、evidence_refs、confidence。"
        "每段建议 2-5 条 judgment；证据不足时可以为空数组，但不得新增第七段。\n\n"
        "六段写法要求：\n"
        "1. 公司画像：写公司做什么、产品/服务边界、经营模式、行业位置，并解释这些特征对分析有什么意义。\n"
        "2. 主营业务表现：写收入、利润、分产品/分地区/分渠道、毛利率、产销存变化，并解释增长质量或压力点。\n"
        "3. 客户与订单结构：写客户集中、供应商集中、经销/直销、订单节奏、回款敏感性，并解释依赖或韧性。\n"
        "4. 研发与技术进展：写研发费用、研发强度、资本化、研发人员、专利、新产品/项目进展，并解释技术路线和转化风险。\n"
        "5. 管理层市场判断：保留下游行业、市场规模、CAGR、供需结构、价格趋势、竞争格局等年报中的关键数字和表述；"
        "必须写成“年报称/管理层认为”，不得升级为外部确认事实。\n"
        "6. 财务风险与跟踪指标：写存货跌价、收入确认、现金流、应收/票据、capex、商誉、金融资产、汇率、政府补助、治理信号，"
        "并给出后续要跟踪的指标。\n\n"
        "不要只摘事实。每条 judgment 应包含“事实/数据 + 分析含义/风险/跟踪意义”。"
        "如果证据块中出现“前五名客户/前五大客户/客户A/供应商/经销/直销/采购计划/订单节奏/应收账款前五名”等内容，"
        "“客户与订单结构”这一段不得为空，必须至少形成 1 条 judgment。"
        "financial_risks 是开放式财务风险排查：候选池不是上限。"
        "先扫描候选池：profit_quality、revenue_recognition、customer_concentration、supplier_concentration、"
        "inventory_impairment、receivables_collection、cash_flow_quality、capex_capacity、asset_impairment、"
        "rd_conversion、government_grant_dependency、financial_asset_dependency、goodwill_impairment、"
        "fx_overseas_exposure、related_party_governance、audit_internal_control、litigation_contingency。"
        "然后按这家公司实际重要性选出 5-9 个 Top Risks。若年报出现候选池外但重要的风险，"
        "必须用 risk_type=other_material_risk，并填写 custom_label。"
        "每条 financial_risks 只允许字段：risk_type、custom_label、importance、summary、mechanism、"
        "tracking_indicators、evidence_refs、confidence。importance 只允许 high/medium/low。"
        "summary 写证据数字，mechanism 写风险传导机制，tracking_indicators 写后续跟踪指标。"
        "financial_risks 必须输出 5-9 条，按重要性排序；不能只写在“财务风险与跟踪指标”正文段里。"
        "如果证据中出现经销/价格调整/前五名客户/前五名供应商/存货/跌价准备/应收账款/应收票据/"
        "经营现金流/购建固定资产/在建工程/资产减值/交易性金融资产/投资收益/政府补助/商誉/汇率/"
        "诉讼/冻结资金/内控/审计意见/董事异议等关键词，应优先判断是否进入 financial_risks。"
        "禁止 raw URL，禁止 [^1]、[1]、[^verified]、[^supported] 等引用标记。"
        "禁止 confirmed_fact、fact_candidate、核心事实、已证实。"
    )
    user_parts = [
        f"报告类型：{fulltext_pack.get('report_type', 'unknown')}",
        f"审计状态：{fulltext_pack.get('audit_status', 'unknown')}",
    ]
    if required_metrics:
        user_parts.extend([
            "required_business_metrics（确定性摘录，禁止将其中 id 用作 evidence_refs）：",
            json.dumps(required_metrics, ensure_ascii=False, sort_keys=True),
        ])
    user_parts.append("以下为大块年报原文证据。只基于这些 fulltext-* 块输出 JSON：")
    for block in blocks:
        user_parts.append(
            f"id: {block.get('id')}\n"
            f"usage: {block.get('usage')}\n"
            f"section: {block.get('section')}\n"
            f"title: {block.get('title')}\n"
            f"text:\n{block.get('text', '')}"
        )
    user = "\n\n".join(user_parts)
    if len(user) > max_prompt_chars:
        user = user[: max_prompt_chars - 1].rstrip() + "…"
    return {
        "system": system,
        "user": user,
        "item_map": {block.get("id"): block for block in blocks if block.get("id")},
        "report_meta": {
            "report_type": fulltext_pack.get("report_type", "unknown"),
            "audit_status": fulltext_pack.get("audit_status", "unknown"),
        },
    }


def summarize_periodic_report_fulltext_with_llm(
    fulltext_pack: Dict[str, Any],
    client: object,
    *,
    required_metrics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run the experimental full-text prompt and validate fixed-section judgments."""
    if not client:
        raise ValueError("client is required")
    if not fulltext_pack.get("blocks"):
        return _empty_fulltext_analysis(fulltext_pack)
    prompt = build_periodic_report_fulltext_prompt(
        fulltext_pack,
        required_metrics=required_metrics,
    )
    raw_response = _call_client(client, prompt)
    validated = validate_periodic_report_fulltext_output(raw_response, fulltext_pack)
    return {
        **validated,
        "source_type": "periodic_report_fulltext_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": False,
        "experimental": True,
    }


def render_periodic_report_fulltext_markdown(
    analysis: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
) -> str:
    """Render fixed-section full-text analysis as Markdown."""
    if not isinstance(analysis, dict):
        return ""

    lines = [
        "# 定期报告全文判断摘要",
        "",
        f"- 报告类型：{analysis.get('report_type', 'unknown')}",
        f"- 审计状态：{analysis.get('audit_status', 'unknown')}",
        f"- 来源类型：{analysis.get('source_type', 'periodic_report_fulltext_analysis')}",
        f"- 信用等级：{analysis.get('source_credit', 75)}",
        f"- 核验状态：{analysis.get('verification_status', 'professional_analysis')}",
        "",
        "> 本摘要是全文/大块年报实验路径产物：允许基于证据做分析判断，但每条判断必须绑定 evidence_refs；"
        "不直接进入核心事实、评分、风险评分或最终建议。",
        "",
    ]
    lines.extend(_render_required_metrics_lines(required_metrics))
    for section in analysis.get("sections") or []:
        title = _escape_md(str(section.get("title", "")))
        lines.extend([f"## {title}", ""])
        judgments = section.get("judgments") or []
        if not judgments:
            lines.extend(["未形成可引用判断。", ""])
        else:
            for item in judgments:
                judgment = _escape_md(str(item.get("judgment", "")))
                confidence = item.get("confidence", "—")
                refs = item.get("evidence_refs") or []
                ref_text = f"；依据：{', '.join(str(ref) for ref in refs)}" if refs else ""
                lines.append(f"- {judgment}（置信度 {confidence}{ref_text}）")
            lines.append("")
        if section.get("title") == "财务风险与跟踪指标":
            risks = analysis.get("financial_risks") or []
            if risks:
                lines.extend(["### 重点财务风险清单", ""])
                for risk in risks:
                    label = str(risk.get("custom_label") or risk.get("risk_type", ""))
                    importance = str(risk.get("importance", ""))
                    confidence = risk.get("confidence", "—")
                    refs = risk.get("evidence_refs") or []
                    summary = _escape_md(str(risk.get("summary", "")))
                    mechanism = _escape_md(str(risk.get("mechanism", "")))
                    indicators = "、".join(str(item) for item in risk.get("tracking_indicators") or [])
                    ref_text = f"；依据：{', '.join(str(ref) for ref in refs)}" if refs else ""
                    lines.append(f"- **{_escape_md(label)}**（{importance}，置信度 {confidence}{ref_text}）：{summary}")
                    if mechanism:
                        lines.append(f"  - 机制：{mechanism}")
                    if indicators:
                        lines.append(f"  - 跟踪指标：{_escape_md(indicators)}")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_periodic_report_fulltext_output(
    raw_text: str,
    fulltext_pack: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate fixed-section full-text LLM output against evidence chunks."""
    if not isinstance(raw_text, str):
        raise PeriodicReportFulltextError("raw_text must be a string")

    try:
        import json

        parsed = json.loads(_extract_json_payload(raw_text))
    except Exception as exc:
        raise PeriodicReportFulltextError(f"JSON parse failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise PeriodicReportFulltextError("JSON root must be an object")
    if parsed.get("schema_version") != FULLTEXT_ANALYSIS_SCHEMA_VERSION:
        raise PeriodicReportFulltextError(
            f"schema_version mismatch: {parsed.get('schema_version')!r}"
        )
    extra_keys = set(parsed) - {"schema_version", "sections", "financial_risks"}
    if extra_keys:
        raise PeriodicReportFulltextError(f"unsupported top-level field: {sorted(extra_keys)[0]}")
    _reject_illegal_content(parsed)

    item_map = _build_item_map(fulltext_pack)
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        raise PeriodicReportFulltextError("sections must be a list")
    titles = [section.get("title") if isinstance(section, dict) else None for section in sections]
    if titles != list(FIXED_ANALYSIS_SECTION_TITLES):
        raise PeriodicReportFulltextError("sections must match fixed six titles")

    normalized_sections: List[Dict[str, Any]] = []
    for section in sections:
        judgments = section.get("judgments", [])
        if judgments is None:
            judgments = []
        if not isinstance(judgments, list):
            raise PeriodicReportFulltextError("judgments must be a list")
        normalized_judgments = []
        for judgment in judgments:
            if not isinstance(judgment, dict):
                continue
            extra_item_keys = set(judgment) - {"judgment", "evidence_refs", "confidence", "importance"}
            if extra_item_keys:
                raise PeriodicReportFulltextError(
                    f"unsupported judgment field: {sorted(extra_item_keys)[0]}"
                )
            refs = judgment.get("evidence_refs")
            _reject_invalid_evidence_refs(refs, item_map)
            confidence = _normalize_confidence(judgment.get("confidence"))
            if confidence is None:
                continue
            text = str(judgment.get("judgment", ""))
            if _has_citation_markers(text):
                raise PeriodicReportFulltextError("judgment contains citation marker")
            if _has_raw_url(text):
                raise PeriodicReportFulltextError("judgment contains raw URL")
            text = _sanitize_text(text)
            if not text:
                continue
            if not _check_fidelity(text, refs, item_map):
                continue
            normalized_judgments.append({
                "judgment": text,
                "evidence_refs": list(refs),
                "confidence": confidence,
            })
        normalized_sections.append({
            "title": str(section.get("title")),
            "judgments": normalized_judgments,
        })

    financial_risks = parsed.get("financial_risks") or []
    normalized_risks = _normalize_financial_risks(financial_risks, item_map)
    normalized_risks = _backfill_risks_from_sections(normalized_sections, normalized_risks)
    normalized_risks = _deduplicate_financial_risks(normalized_risks)

    return {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "report_type": fulltext_pack.get("report_type", "unknown"),
        "audit_status": fulltext_pack.get("audit_status", "unknown"),
        "sections": normalized_sections,
        "financial_risks": normalized_risks,
    }


def _split_major_sections(text: str) -> List[tuple[str, str]]:
    matches = [
        match for match in _SECTION_HEADING_RE.finditer(text)
        if not _looks_like_toc_heading(match.group(0))
    ]
    if not matches:
        return []
    sections: List[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = _clean_line(match.group(1))
        content = text[start:end].strip()
        if heading and content:
            sections.append((heading, content))
    return sections


def _looks_like_toc_heading(line: str) -> bool:
    compact = line.strip()
    return "..." in compact or "……" in compact or bool(re.search(r"\.{3,}\s*\d+\s*$", compact))


def _chunk_text(text: str, chunk_chars: int) -> List[str]:
    if len(text) <= chunk_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        boundary = max(text.rfind("\n", start, end), text.rfind("。", start, end))
        if boundary > start + chunk_chars // 2:
            end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def _usage_for_fulltext_heading(heading: str) -> str:
    compact = re.sub(r"\s+", "", heading)
    if "公司简介" in compact or "财务指标" in compact:
        return "fulltext_financial_snapshot"
    if "管理层讨论" in compact:
        return "fulltext_management_discussion"
    if "重要事项" in compact:
        return "fulltext_important_events"
    if "财务报告" in compact:
        return "fulltext_financial_notes"
    if "公司治理" in compact:
        return "fulltext_governance"
    if "风险" in compact or "重要提示" in compact:
        return "fulltext_risk_disclosure"
    return "fulltext_section"


def _call_client(client: object, prompt: Dict[str, Any]) -> str:
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
    raise PeriodicReportLLMv2Error(
        "client must provide .chat(prompt) or .chat.completions.create(...)"
    )


def _extract_completion_text(response: object) -> str:
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


def _normalize_financial_risks(
    risks: Any,
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not isinstance(risks, list):
        raise PeriodicReportFulltextError("financial_risks must be a list")
    normalized: List[Dict[str, Any]] = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        extra_keys = set(risk) - {
            "risk_type",
            "custom_label",
            "importance",
            "summary",
            "mechanism",
            "tracking_indicators",
            "evidence_refs",
            "confidence",
        }
        if extra_keys:
            raise PeriodicReportFulltextError(
                f"unsupported financial_risk field: {sorted(extra_keys)[0]}"
            )
        risk_type = _normalize_risk_type(str(risk.get("risk_type", "")).strip(), risk)
        if risk_type not in FINANCIAL_RISK_CANDIDATE_TYPES:
            raise PeriodicReportFulltextError(f"unsupported risk_type: {risk_type}")
        custom_label = _normalize_custom_label(risk.get("custom_label", ""))
        if risk_type == "other_material_risk" and not custom_label:
            raise PeriodicReportFulltextError("other_material_risk requires custom_label")
        importance = str(risk.get("importance", "")).strip()
        if importance not in _ALLOWED_RISK_IMPORTANCE:
            continue
        refs = risk.get("evidence_refs")
        _reject_invalid_evidence_refs(refs, item_map)
        confidence = _normalize_confidence(risk.get("confidence"))
        if confidence is None:
            continue

        summary = _sanitize_text(str(risk.get("summary", "")))
        mechanism = _sanitize_text(str(risk.get("mechanism", "")))
        tracking_indicators = risk.get("tracking_indicators") or []
        if not isinstance(tracking_indicators, list):
            continue
        tracking_indicators = [
            _sanitize_text(str(item)) for item in tracking_indicators if _sanitize_text(str(item))
        ]
        combined_text = " ".join([summary, mechanism, " ".join(tracking_indicators)]).strip()
        if not combined_text:
            continue
        if _has_citation_markers(combined_text):
            raise PeriodicReportFulltextError("financial_risk contains citation marker")
        if _has_raw_url(combined_text):
            raise PeriodicReportFulltextError("financial_risk contains raw URL")
        if not _check_fidelity(combined_text, refs, item_map):
            continue

        normalized_risk = {
            "risk_type": risk_type,
            "importance": importance,
            "summary": summary,
            "mechanism": mechanism,
            "tracking_indicators": tracking_indicators,
            "evidence_refs": list(refs),
            "confidence": confidence,
        }
        if custom_label:
            normalized_risk["custom_label"] = custom_label
        normalized.append(normalized_risk)
    return normalized


def _backfill_risks_from_sections(
    sections: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    existing = {_risk_semantic_key(risk) for risk in risks}
    backfilled = list(risks)
    for section in sections:
        for judgment in section.get("judgments") or []:
            text = str(judgment.get("judgment", ""))
            risk_type = _infer_risk_type_from_text(text)
            semantic_key = _risk_semantic_key({"risk_type": risk_type})
            if not risk_type or semantic_key in existing:
                continue
            refs = judgment.get("evidence_refs") or []
            confidence = judgment.get("confidence", 70)
            backfilled.append({
                "risk_type": risk_type,
                "importance": _importance_for_inferred_risk(risk_type),
                "summary": text,
                "mechanism": _mechanism_for_inferred_risk(risk_type),
                "tracking_indicators": _tracking_indicators_for_inferred_risk(risk_type),
                "evidence_refs": list(refs),
                "confidence": confidence,
            })
            existing.add(semantic_key)
    return backfilled


def _deduplicate_financial_risks(risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for risk in risks:
        key = _risk_semantic_key(risk)
        if key in seen:
            continue
        if _is_duplicate_collection_of_cashflow(risk, deduped):
            continue
        seen.add(key)
        deduped.append(risk)
    return deduped


def _is_duplicate_collection_of_cashflow(
    risk: Dict[str, Any],
    existing_risks: List[Dict[str, Any]],
) -> bool:
    if risk.get("risk_type") != "receivables_collection":
        return False
    text = " ".join([
        str(risk.get("summary", "")),
        str(risk.get("mechanism", "")),
        " ".join(str(item) for item in risk.get("tracking_indicators") or []),
    ])
    if "经营" not in text or "现金流" not in text:
        return False
    refs = set(risk.get("evidence_refs") or [])
    for existing in existing_risks:
        if existing.get("risk_type") != "cash_flow_quality":
            continue
        existing_refs = set(existing.get("evidence_refs") or [])
        if refs and refs == existing_refs:
            return True
    return False


def _risk_semantic_key(risk: Dict[str, Any]) -> str:
    risk_type = str(risk.get("risk_type", ""))
    label = str(risk.get("custom_label", ""))
    text = f"{risk_type} {label}"
    if "诉讼" in text or "冻结" in text:
        return "litigation_contingency"
    if "治理" in text or "董事异议" in text or "内控" in text or "审计" in text:
        return "governance_or_internal_control"
    return risk_type if risk_type != "other_material_risk" else f"other:{label}"


def _normalize_risk_type(risk_type: str, risk: Dict[str, Any]) -> str:
    text = " ".join([
        str(risk.get("summary", "")),
        str(risk.get("mechanism", "")),
        " ".join(str(item) for item in risk.get("tracking_indicators") or []),
    ])
    inferred = _infer_risk_type_from_text(text)
    if risk_type == "revenue_recognition" and inferred in {"cash_flow_quality", "receivables_collection"}:
        return inferred
    return risk_type


def _infer_risk_type_from_text(text: str) -> str:
    if any(token in text for token in ("前五名客户", "前五大客户", "客户A", "客户集中")):
        return "customer_concentration"
    if any(token in text for token in ("前五名供应商", "前五大供应商", "供应商集中", "供应商采购", "采购总额", "台积电")):
        return "supplier_concentration"
    if any(token in text for token in ("存货", "库存", "跌价")):
        return "inventory_impairment"
    if any(token in text for token in ("经营活动现金流", "经营现金流", "现金流量净额", "现金流与净利润")):
        return "cash_flow_quality"
    if any(token in text for token in ("回款", "应收账款", "应收票据", "商业承兑", "航信", "电汇")):
        return "receivables_collection"
    if any(token in text for token in ("在建工程", "购建固定资产", "资本开支", "转固", "产能利用率")):
        return "capex_capacity"
    if any(token in text for token in ("资产减值", "设备减值", "减值损失")):
        return "asset_impairment"
    if any(token in text for token in ("交易性金融资产", "理财", "投资收益", "公允价值变动")):
        return "financial_asset_dependency"
    if any(token in text for token in ("政府补助", "其他收益")):
        return "government_grant_dependency"
    if any(token in text for token in ("商誉", "并购", "收购")):
        return "goodwill_impairment"
    if any(token in text for token in ("汇率", "外币", "香港", "海外")):
        return "fx_overseas_exposure"
    if any(token in text for token in ("内控", "内部控制", "审计意见", "强调事项")):
        return "audit_internal_control"
    if any(token in text for token in ("董事异议", "董事会异议", "治理", "关联交易")):
        return "related_party_governance"
    if any(token in text for token in ("诉讼", "冻结资金", "财产保全")):
        return "litigation_contingency"
    if any(token in text for token in ("扣非", "净利润", "毛利率", "增收不增利", "利润质量")):
        return "profit_quality"
    if any(token in text for token in ("收入确认", "经销", "价格调整", "冲减收入", "合同资产")):
        return "revenue_recognition"
    if any(token in text for token in ("研发投入", "研发费用", "研发资本化", "客户导入")):
        return "rd_conversion"
    return ""


def _importance_for_inferred_risk(risk_type: str) -> str:
    if risk_type in {"customer_concentration", "inventory_impairment", "cash_flow_quality"}:
        return "high"
    return "medium"


def _mechanism_for_inferred_risk(risk_type: str) -> str:
    mechanisms = {
        "customer_concentration": "客户或订单节奏变化会放大收入、回款和产能利用率波动。",
        "supplier_concentration": "关键供应商价格、产能或交付变化会影响成本、交付和毛利率。",
        "inventory_impairment": "库存消化不及预期可能导致跌价准备增加，并压制后续毛利率和利润。",
        "cash_flow_quality": "经营现金流与利润背离会影响盈利质量和现金回收持续性判断。",
        "receivables_collection": "回款方式和应收票据变化会影响现金流稳定性与信用风险。",
        "capex_capacity": "资本开支和在建工程转固后，若需求不足会带来折旧和产能利用率压力。",
        "asset_impairment": "资产减值反映部分资产预期收益下降，可能影响后续利润质量。",
        "financial_asset_dependency": "理财和公允价值收益不具备经营持续性，可能扰动利润。",
        "audit_internal_control": "内控或审计异常会增加财务信息质量和治理风险。",
        "related_party_governance": "治理分歧或关联事项会影响决策效率和信息透明度。",
    }
    return mechanisms.get(risk_type, "该风险已在年报证据中出现，可能影响后续经营质量或财务表现。")


def _tracking_indicators_for_inferred_risk(risk_type: str) -> List[str]:
    indicators = {
        "customer_concentration": ["第一大客户收入占比", "前五大客户收入占比", "订单节奏"],
        "supplier_concentration": ["前五大供应商采购占比", "主要供应商价格", "交付周期"],
        "inventory_impairment": ["存货余额", "库存量", "跌价准备", "毛利率"],
        "cash_flow_quality": ["经营活动现金流量净额", "净利润", "经营现金流/净利润"],
        "receivables_collection": ["应收账款余额", "应收票据余额", "回款方式"],
        "capex_capacity": ["在建工程", "购建长期资产现金流", "产能利用率", "折旧摊销"],
        "asset_impairment": ["资产减值损失", "减值资产类型", "后续转回或新增计提"],
        "financial_asset_dependency": ["交易性金融资产", "投资收益", "公允价值变动收益"],
        "audit_internal_control": ["内控审计意见", "整改进展", "资金管理制度执行"],
        "related_party_governance": ["董事异议", "关联交易", "诉讼进展"],
    }
    return indicators.get(risk_type, ["相关风险证据", "后续披露变化"])


def _build_item_map(fulltext_pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    item_map: Dict[str, Dict[str, Any]] = {}
    for index, block in enumerate(fulltext_pack.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        block_id = block.get("id") or f"fulltext-{index}"
        item_map[str(block_id)] = block
    return item_map


def _normalize_custom_label(value: Any) -> str:
    label = _sanitize_text(str(value or ""))
    if label.lower() in {"none", "null", "n/a", "na"} or label in {"无", "不适用", "无自定义标签"}:
        return ""
    return label


def _extract_json_payload(raw_text: str) -> str:
    text = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    if text.startswith("{"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1].strip()
    return text


def _reject_invalid_evidence_refs(refs: Any, item_map: Dict[str, Any]) -> None:
    if not isinstance(refs, list) or not refs:
        raise PeriodicReportFulltextError("invalid evidence_refs")
    for ref in refs:
        if not isinstance(ref, str) or ref not in item_map:
            raise PeriodicReportFulltextError("invalid evidence_refs")


def _reject_illegal_content(parsed: Dict[str, Any]) -> None:
    text = _stringify_values(parsed).lower()
    for substring in ("confirmed_fact", "fact_candidate", "核心事实", "已证实"):
        if substring in text:
            raise PeriodicReportFulltextError(f"illegal content detected: {substring!r}")


def _stringify_values(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_stringify_values(value) for value in obj.values())
    if isinstance(obj, list):
        return " ".join(_stringify_values(value) for value in obj)
    return ""


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _render_required_metrics_lines(metrics: Dict[str, Any] | None) -> List[str]:
    if not isinstance(metrics, dict):
        return []
    lines = ["## 必备经营指标摘录", ""]

    segment_rows = metrics.get("segment_rows") or []
    if segment_rows:
        lines.extend([
            "### 分产品/业务毛利率",
            "",
            "| 项目 | 收入 | 收入同比 | 毛利率 | 毛利率变化 |",
            "|------|------|----------|--------|------------|",
        ])
        for row in segment_rows:
            lines.append(
                "| {label} | {revenue} | {revenue_yoy} | {gross_margin} | {gross_margin_delta} |".format(
                    label=_escape_md(str(row.get("label", ""))),
                    revenue=_escape_md(_metric_cell(row.get("revenue"))),
                    revenue_yoy=_escape_md(_metric_cell(row.get("revenue_yoy"))),
                    gross_margin=_escape_md(_metric_cell(row.get("gross_margin"))),
                    gross_margin_delta=_escape_md(_metric_cell(row.get("gross_margin_delta"))),
                )
            )
        lines.append("")

    inventory_rows = metrics.get("inventory_rows") or []
    if inventory_rows:
        lines.extend([
            "### 产销库存",
            "",
            "| 项目 | 生产量 | 销售量 | 库存量 | 库存同比 |",
            "|------|--------|--------|--------|----------|",
        ])
        for row in inventory_rows:
            lines.append(
                "| {label} | {production} | {sales} | {inventory} | {inventory_yoy} |".format(
                    label=_escape_md(str(row.get("label", ""))),
                    production=_escape_md(_metric_cell(row.get("production_volume"))),
                    sales=_escape_md(_metric_cell(row.get("sales_volume"))),
                    inventory=_escape_md(_metric_cell(row.get("inventory_volume"))),
                    inventory_yoy=_escape_md(_metric_cell(row.get("inventory_yoy"))),
                )
            )
        lines.append("")

    for title, key in (("分地区", "region_rows"), ("销售模式", "sales_mode_rows")):
        rows = metrics.get(key) or []
        if not rows:
            continue
        lines.extend([
            f"### {title}",
            "",
            "| 项目 | 收入 | 收入同比 | 毛利率 |",
            "|------|------|----------|--------|",
        ])
        for row in rows:
            lines.append(
                "| {label} | {revenue} | {revenue_yoy} | {gross_margin} |".format(
                    label=_escape_md(str(row.get("label", ""))),
                    revenue=_escape_md(_metric_cell(row.get("revenue"))),
                    revenue_yoy=_escape_md(_metric_cell(row.get("revenue_yoy"))),
                    gross_margin=_escape_md(_metric_cell(row.get("gross_margin"))),
                )
            )
        lines.append("")

    concentration_lines = []
    for label, key in (("客户集中度", "customer_concentration"), ("供应商集中度", "supplier_concentration")):
        concentration = metrics.get(key) or {}
        if not concentration.get("present"):
            continue
        concentration_lines.append(
            "- {label}：前五合计 {top_amount} / {top_pct}；第一大 {largest_amount} / {largest_pct}".format(
                label=label,
                top_amount=_metric_cell(concentration.get("top_five_amount")) or "未提取",
                top_pct=_metric_cell(concentration.get("top_five_percentage")) or "未提取",
                largest_amount=_metric_cell(concentration.get("largest_amount")) or "未提取",
                largest_pct=_metric_cell(concentration.get("largest_percentage")) or "未提取",
            )
        )
    if concentration_lines:
        lines.extend(["### 客户/供应商集中度", "", *concentration_lines, ""])

    if lines == ["## 必备经营指标摘录", ""]:
        lines.extend(["未提取到分产品、产销库存、区域/模式或客户供应商集中度表。", ""])
    return lines


def _metric_cell(cell: Any) -> str:
    if not isinstance(cell, dict):
        return ""
    text = str(cell.get("text") or "")
    unit = str(cell.get("unit") or "")
    normalized = str(cell.get("normalized") or "")
    if unit == "万元" and normalized.endswith("万元"):
        return normalized
    if unit in {"%", "pct"}:
        return text
    if unit and text and not text.endswith(unit):
        return f"{text}{unit}"
    return text


def _clean_fulltext(text: str) -> str:
    text = text.replace("　", " ")
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _is_page_noise(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _is_page_noise(line: str) -> bool:
    if re.match(r"^\d+\s*$", line):
        return True
    if "年度报告全文" in line and len(line) < 60:
        return True
    return False


def _clean_line(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def _empty_fulltext_analysis(fulltext_pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "source_type": "periodic_report_fulltext_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": False,
        "experimental": True,
        "report_type": fulltext_pack.get("report_type", "unknown"),
        "audit_status": fulltext_pack.get("audit_status", "unknown"),
        "company_profile": {},
        "cards": [],
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    }
