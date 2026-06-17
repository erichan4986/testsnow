"""Bounded LLM analysis helper v2 for annual/semiannual report evidence packs.

This module is intentionally helper-only in Phase A:
- no CLI
- no Source Intake / evidence-note / pipeline wiring
- no import-time LLM client dependency

The LLM input is built only from deterministic evidence-pack blocks, not the full
report text. Output is typed as `periodic_report_analysis` with
`source_credit: 75` and `verification_status: professional_analysis`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = "periodic_report_llm_analysis.v2"

_MAX_BLOCKS_DEFAULT = 30
_MAX_CHARS_PER_BLOCK = 2000
_MAX_PROMPT_CHARS = 30000
_MAX_SECTIONS = 12
_MAX_CARDS = 8
_MAX_FINANCIAL_RISKS = 8
_MAX_FOLLOW_UP_QUESTIONS = 8
_MAX_SUMMARY_CHARS = 1200

_CITATION_RE = re.compile(r"\[\^?\w+\]")
_URL_RE = re.compile(r"https?://\S+")
_REPEATED_SPACE_RE = re.compile(r"\s+")

_ILLEGAL_SUBSTRINGS = (
    "confirmed_fact",
    "fact_candidate",
    "核心事实",
    "已证实",
)

_ALLOWED_SECTION_USAGES = frozenset({
    "company_profile",
    "product_capacity_profile",
    "market_outlook",
    "management_market_view",
    "business_model",
    "sales_certification_model",
    "segment_performance",
    "margin_driver",
    "production_inventory_signal",
    "customer_concentration",
    "rd_investment",
    "rd_progress",
    "capex_capacity",
    "cash_flow_capex",
    "cash_flow_quality",
    "balance_sheet_risk",
    "accounting_policy_risk",
    "governance_signal",
    "management_claim_to_verify",
})

_ALLOWED_RISK_TYPES = frozenset({
    "customer_concentration",
    "ar_customer_concentration",
    "supplier_concentration",
    "revenue_quality",
    "margin_pressure",
    "inventory_risk",
    "ar_aging",
    "bill_collection_risk",
    "asset_impairment",
    "capex_overrun",
    "capacity_digestion",
    "cash_flow_weakness",
    "cash_flow_sustainability",
    "financial_asset_dependency",
    "related_party_risk",
    "litigation",
    "pledge",
    "goodwill",
    "government_grant_dependency",
    "accounting_policy",
    "audit_key_matter",
    "governance_signal",
    "subsequent_event",
})

_ALLOWED_CARD_TYPES = frozenset({
    "company_profile_card",
    "market_outlook_card",
    "financial_snapshot_card",
    "segment_card",
    "rd_card",
    "channel_supplier_card",
    "risk_card",
})


class PeriodicReportLLMv2Error(Exception):
    """Raised when the LLM output cannot be validated."""


def build_periodic_report_llm_v2_prompt(
    evidence_pack: Dict[str, Any],
    *,
    max_blocks: int = _MAX_BLOCKS_DEFAULT,
) -> Dict[str, Any]:
    """Build a bounded prompt dict from a deterministic evidence pack."""
    if not isinstance(evidence_pack, dict):
        raise TypeError("evidence_pack must be a dict")

    blocks = evidence_pack.get("blocks") or []
    selected = blocks[:max_blocks]
    item_map: Dict[str, Dict[str, Any]] = {}
    prompt_blocks: List[Dict[str, str]] = []

    for index, block in enumerate(selected):
        usage = block.get("usage", "other")
        block_id = block.get("id") or f"{usage}-{index}"
        item_map[block_id] = block
        text = _clean_text(str(block.get("text", "")))
        text = _truncate_text(text, _MAX_CHARS_PER_BLOCK)
        prompt_blocks.append({
            "id": block_id,
            "usage": usage,
            "section": str(block.get("section", "")),
            "title": _clean_text(str(block.get("title", ""))),
            "metric_rule": _metric_rule_for_usage(str(usage)),
            "text": text,
        })

    schema_example = json.dumps({
        "schema_version": SCHEMA_VERSION,
        "company_profile": {
            "summary": "公司主要从事...",
            "evidence_refs": ["business_overview-0"],
        },
        "cards": [
            {
                "card_type": "segment_card",
                "title": "主营结构与毛利率",
                "bullets": ["分产品收入、同比、毛利率..."],
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 75,
            }
        ],
        "sections": [
            {
                "usage": "segment_performance",
                "title": "主营业务表现",
                "summary": "...",
                "evidence_refs": ["segment_margin_table-0"],
                "confidence": 75,
            }
        ],
        "financial_risks": [
            {
                "risk_type": "customer_concentration",
                "summary": "...",
                "evidence_refs": ["customer_supplier_table-0"],
                "severity": "medium",
                "confidence": 75,
            }
        ],
        "follow_up_questions": [
            {
                "question": "...",
                "evidence_refs": ["rd_table-0"],
            }
        ],
    }, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是一个保守的定期报告证据摘要助手。你的任务是把年报/半年报规则摘录压缩成最终股票报告可复用的中间素材，"
        "不是生成最终投资报告。输出应围绕“年报事实 + 管理层解释 + 可跟踪问题”，"
        "不能补充外部事实，不能将管理层表述升级为确认事实，不得给出买卖建议，不得给出估值结论。\n\n"
        "输出必须是严格 JSON，且必须完全匹配以下 schema，不要 Markdown 代码块，不要解释。\n\n"
        "允许的最顶层字段只有：schema_version、company_profile、cards、sections、financial_risks、"
        "follow_up_questions。禁止出现顶层 summary、content、description、name、industry 等字段。\n\n"
        "schema 示例（每项只允许列出的字段）：\n"
        f"{schema_example}\n\n"
        "字段规则：\n"
        "- company_profile 只允许：summary、evidence_refs。\n"
        "- cards 每项只允许：card_type、title、bullets、evidence_refs、confidence。\n"
        "- cards 是最终股票报告复用的材料卡片，优先产出这些卡片，而不是写成完整分析文章。\n"
        "- cards[].card_type 只允许：company_profile_card、financial_snapshot_card、segment_card、"
        "rd_card、channel_supplier_card、risk_card。\n"
        "- company_profile_card 写产品、应用、经营模式、行业地位；financial_snapshot_card 写营收、归母、"
        "扣非、经营现金流、资产/净资产；segment_card 写分产品/地区/渠道收入、毛利率、同比；"
        "rd_card 写研发费用、研发强度、资本化、人员、专利、新品/项目；channel_supplier_card 写经销占比、"
        "客户集中、供应商集中；risk_card 写存货跌价、收入确认、现金流、商誉、金融资产、汇率、政府补助等线索。\n"
        "- cards[].bullets 必须是字符串数组，每条 bullet 是一条可复用材料，必须尽量保留关键数字。\n"
        "- sections 每项只允许：usage、title、summary、evidence_refs、confidence。\n"
        "- financial_risks 每项只允许：risk_type、summary、evidence_refs、severity、confidence。\n"
        "- follow_up_questions 必须是对象数组，每项只允许：question、evidence_refs；禁止字符串数组。\n"
        "- 禁止 content、description、business_summary、name、industry 等未列字段。\n"
        "- sections[].usage 只允许：company_profile、product_capacity_profile、market_outlook、"
        "management_market_view、business_model、sales_certification_model、segment_performance、"
        "margin_driver、production_inventory_signal、customer_concentration、rd_investment、"
        "rd_progress、capex_capacity、cash_flow_capex、cash_flow_quality、balance_sheet_risk、"
        "accounting_policy_risk、governance_signal、management_claim_to_verify。\n"
        "- financial_risks[].risk_type 只允许：customer_concentration、supplier_concentration、"
        "ar_customer_concentration、revenue_quality、margin_pressure、inventory_risk、ar_aging、"
        "bill_collection_risk、asset_impairment、capex_overrun、capacity_digestion、"
        "cash_flow_weakness、cash_flow_sustainability、financial_asset_dependency、"
        "related_party_risk、litigation、pledge、goodwill、government_grant_dependency、"
        "accounting_policy、audit_key_matter、governance_signal、subsequent_event。\n"
        f"- sections 最多 {_MAX_SECTIONS} 条。\n"
        f"- cards 最多 {_MAX_CARDS} 张，每张最多 8 条 bullets。\n"
        f"- financial_risks 最多 {_MAX_FINANCIAL_RISKS} 条。\n"
        f"- follow_up_questions 最多 {_MAX_FOLLOW_UP_QUESTIONS} 条。\n"
        "- evidence_refs 必须引用下方提供的 block id。\n"
        "- summary 中禁止引入证据中没有的数字、日期、产品名、客户名、capex 数据或增长率。\n"
        "- 遇到收入、毛利率、产销存、研发投入、客户集中、现金流、资产减值等表格或附注时，"
        "必须保留关键数字；不得只写增长、下降、提升、承压、较高、较大等模糊描述。\n"
        "- segment_performance / margin_driver 必须优先写收入金额、同比增减、毛利率、毛利率同比增减；"
        "若证据同时有多个产品线，应分别列出主要产品线。\n"
        "- production_inventory_signal 必须优先写销售量、生产量、库存量及同比变化。\n"
        "- rd_investment 必须优先写研发投入金额、研发投入占营业收入比例、研发人员数量、资本化金额或比例。\n"
        "- customer_concentration 必须优先写前五大客户占比和第一大客户占比（若证据中存在）。\n"
        "- cash_flow_capex 必须优先写经营现金流、购建长期资产现金流、投资活动现金流净额（若证据中存在）。\n"
        "- confidence 必须是 0 到 100 的整数。\n"
        "- 禁止出现以下任何字符串或概念：confirmed_fact、fact_candidate、核心事实、已证实。\n"
        "- 禁止出现 Markdown 引用标记，例如 [^1]、[1]、[^verified]、[^supported]、"
        "[^needs_review]、[^unverified]。\n"
        "- 禁止出现 raw URLs。\n\n"
        "表达规范：\n"
        "- 输出定位是定期报告证据摘要：服务于后续多源综合，不替代最终报告。\n"
        "- 对 risk 写成公司披露的风险或规则观察到的 tensions，不得写成风险已经发生。\n"
        "- 对 management_view 写成管理层表述/年报称，不得写成独立事实。\n"
        "- 对 financial_risks 写成财报排雷观察，不得写成会计造假结论。\n"
        "- 不得直接给出买卖建议、仓位建议或估值结论。\n"
        "- 如果证据不足，输出 follow-up question，不要编造结论。"
    )

    user_parts = [
        f"报告类型：{evidence_pack.get('report_type', 'unknown')}",
        f"审计状态：{evidence_pack.get('audit_status', 'unknown')}",
        "",
        "摘录块（仅基于这些块总结）：",
        "",
    ]
    for prompt_block in prompt_blocks:
        user_parts.append(
            f"id: {prompt_block['id']}\n"
            f"usage: {prompt_block['usage']}\n"
            f"section: {prompt_block['section']}\n"
            f"title: {prompt_block['title']}\n"
            f"metric_rule: {prompt_block['metric_rule']}\n"
            f"text: {prompt_block['text']}"
        )

    user_prompt = "\n\n".join(user_parts)
    if len(user_prompt) > _MAX_PROMPT_CHARS:
        user_prompt = _truncate_text(user_prompt, _MAX_PROMPT_CHARS)

    return {
        "system": system_prompt,
        "user": user_prompt,
        "item_map": item_map,
        "report_meta": {
            "report_type": evidence_pack.get("report_type", "unknown"),
            "audit_status": evidence_pack.get("audit_status", "unknown"),
        },
    }


def validate_periodic_report_llm_v2_output(
    raw_text: str,
    evidence_pack: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate and sanitize raw LLM JSON output against the evidence pack.

    Raises PeriodicReportLLMv2Error when the whole analysis must be rejected.
    Returns a dict with the same shape as the final helper output but without
    credit metadata; callers should add those fields.
    """
    if not isinstance(raw_text, str):
        raise PeriodicReportLLMv2Error("raw_text must be a string")

    item_map = _build_item_map(evidence_pack)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PeriodicReportLLMv2Error(f"JSON parse failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise PeriodicReportLLMv2Error("JSON root must be an object")

    if parsed.get("schema_version") != SCHEMA_VERSION:
        raise PeriodicReportLLMv2Error(
            f"schema_version mismatch: {parsed.get('schema_version')!r}"
        )

    # Reject illegal status markers anywhere in parsed content first.
    _reject_illegal_content(parsed)

    _normalize_top_level_keys(parsed)

    company_profile = parsed.get("company_profile") or {}
    cards = parsed.get("cards") or []
    sections = parsed.get("sections") or []
    financial_risks = parsed.get("financial_risks") or []
    follow_up_questions = parsed.get("follow_up_questions") or []

    if not isinstance(cards, list):
        raise PeriodicReportLLMv2Error("cards must be a list")
    if not isinstance(sections, list):
        raise PeriodicReportLLMv2Error("sections must be a list")
    if not isinstance(financial_risks, list):
        raise PeriodicReportLLMv2Error("financial_risks must be a list")
    if not isinstance(follow_up_questions, list):
        raise PeriodicReportLLMv2Error("follow_up_questions must be a list")

    if len(cards) > _MAX_CARDS:
        raise PeriodicReportLLMv2Error(f"too many cards: {len(cards)}")
    if len(sections) > _MAX_SECTIONS:
        raise PeriodicReportLLMv2Error(f"too many sections: {len(sections)}")
    if len(financial_risks) > _MAX_FINANCIAL_RISKS:
        raise PeriodicReportLLMv2Error(f"too many financial_risks: {len(financial_risks)}")
    if len(follow_up_questions) > _MAX_FOLLOW_UP_QUESTIONS:
        raise PeriodicReportLLMv2Error(f"too many follow_up_questions: {len(follow_up_questions)}")

    normalized_company_profile = _normalize_company_profile(company_profile, item_map)
    valid_cards = _normalize_cards(cards, item_map)
    valid_sections = _normalize_sections(sections, item_map)
    valid_risks = _normalize_financial_risks(financial_risks, item_map)
    valid_questions = _normalize_questions(follow_up_questions, item_map)

    if not normalized_company_profile and not valid_cards and not valid_sections and not valid_risks and not valid_questions:
        raise PeriodicReportLLMv2Error("no valid analysis content remains")

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": evidence_pack.get("report_type", "unknown"),
        "audit_status": evidence_pack.get("audit_status", "unknown"),
        "company_profile": normalized_company_profile,
        "cards": valid_cards,
        "sections": valid_sections,
        "financial_risks": valid_risks,
        "follow_up_questions": valid_questions,
    }


def summarize_periodic_report_with_llm_v2(
    evidence_pack: Dict[str, Any],
    client: object,
) -> Dict[str, Any]:
    """Run bounded LLM analysis on an evidence pack and return a safe result."""
    if not client:
        raise ValueError("client is required")

    blocks = evidence_pack.get("blocks") or []
    if not blocks:
        return _empty_analysis(evidence_pack)

    prompt = build_periodic_report_llm_v2_prompt(evidence_pack)
    raw_response = _call_client(client, prompt)
    validated = validate_periodic_report_llm_v2_output(raw_response, evidence_pack)

    return {
        **validated,
        "source_type": "periodic_report_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": True,
    }


def render_periodic_report_llm_v2_markdown(analysis: Dict[str, Any]) -> str:
    """Render a compact Markdown preview of the LLM analysis."""
    if not isinstance(analysis, dict):
        return ""

    lines = [
        "# 定期报告证据摘要",
        "",
        f"- 报告类型：{analysis.get('report_type', 'unknown')}",
        f"- 审计状态：{analysis.get('audit_status', 'unknown')}",
        f"- 来源类型：{analysis.get('source_type', 'periodic_report_analysis')}",
        f"- 信用等级：{analysis.get('source_credit', 75)}",
        f"- 核验状态：{analysis.get('verification_status', 'professional_analysis')}",
        "",
        "> 本摘要是供最终股票报告复用的中间素材，仅基于规则摘录和 LLM 压缩；"
        "不直接给出估值结论、买卖建议或仓位建议，不参与评分或建议。",
        "",
    ]

    profile = analysis.get("company_profile") or {}
    if profile.get("summary"):
        lines.extend([
            "## 公司画像",
            "",
            _escape_md(str(profile["summary"])),
            "",
            f"**依据**：{', '.join(str(r) for r in profile.get('evidence_refs', []))}",
            "",
        ])

    sections = analysis.get("sections") or []
    cards = analysis.get("cards") or []
    if cards:
        lines.append("## 材料卡片")
        lines.append("")
        for card in cards:
            title = _escape_md(str(card.get("title", "")))
            card_type = str(card.get("card_type", ""))
            confidence = card.get("confidence", "—")
            refs = card.get("evidence_refs") or []
            lines.append(f"### {title} ({card_type}，置信度 {confidence})")
            lines.append("")
            for bullet in card.get("bullets") or []:
                lines.append(f"- {_escape_md(str(bullet))}")
            if refs:
                lines.append(f"- 依据：{', '.join(str(r) for r in refs)}")
            lines.append("")

    if sections:
        lines.append("## 分析要点")
        lines.append("")
        for section in sections:
            title = _escape_md(str(section.get("title", "")))
            usage = str(section.get("usage", ""))
            summary = _escape_md(str(section.get("summary", "")))
            confidence = section.get("confidence", "—")
            refs = section.get("evidence_refs") or []
            lines.append(f"### {title} ({usage}，置信度 {confidence})")
            lines.append("")
            lines.append(summary)
            lines.append("")
            if refs:
                lines.append(f"**依据摘录**：{', '.join(str(r) for r in refs)}")
                lines.append("")

    risks = analysis.get("financial_risks") or []
    if risks:
        lines.append("## 财务风险观察")
        lines.append("")
        for risk in risks:
            risk_type = str(risk.get("risk_type", ""))
            summary = _escape_md(str(risk.get("summary", "")))
            severity = str(risk.get("severity", ""))
            confidence = risk.get("confidence", "—")
            refs = risk.get("evidence_refs") or []
            lines.append(f"- **{risk_type}**（{severity}，置信度 {confidence}）：{summary}")
            if refs:
                lines.append(f"  - 依据：{', '.join(str(r) for r in refs)}")
        lines.append("")

    questions = analysis.get("follow_up_questions") or []
    if questions:
        lines.append("## 后续跟踪问题")
        lines.append("")
        for index, question in enumerate(questions, 1):
            q = _escape_md(str(question.get("question", "")))
            refs = question.get("evidence_refs") or []
            ref_text = f"（依据：{', '.join(str(r) for r in refs)}）" if refs else ""
            lines.append(f"{index}. {q} {ref_text}")
        lines.append("")

    if not profile and not cards and not sections and not risks and not questions:
        lines.append("未生成有效分析要点。")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_item_map(evidence_pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    item_map: Dict[str, Dict[str, Any]] = {}
    for index, block in enumerate(evidence_pack.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        block_id = block.get("id") or f"{block.get('usage', 'other')}-{index}"
        item_map[block_id] = block
    return item_map


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

    raise PeriodicReportLLMv2Error(
        "client must provide .chat(prompt) or .chat.completions.create(...)"
    )


def _metric_rule_for_usage(usage: str) -> str:
    rules = {
        "financial_summary_table": "保留营业收入、归母净利润、扣非归母净利润、经营现金流、资产总额、归母净资产及同比变化。",
        "segment_margin_table": "保留分产品收入金额、收入同比、毛利率、毛利率同比增减；不要只写增长/下降。",
        "segment_table": "保留收入金额、占比和同比增减；不要只写结构变化。",
        "production_sales_inventory_table": "保留销售量、生产量、库存量及同比变化。",
        "rd_investment_table": "保留研发人员数量、研发投入金额、研发投入占营业收入比例、资本化金额或比例。",
        "rd_table": "保留关键项目名称、阶段性进展和是否达到供货/结题条件。",
        "customer_supplier_table": "保留前五大客户/供应商占比、第一大客户/供应商占比和金额。",
        "supplier_concentration_table": "保留前五大供应商采购金额、占年度采购总额比例、第一大供应商占比和金额。",
        "ar_customer_concentration_note": "保留应收账款前五名客户占比、担保/信用增级信息。",
        "cash_flow_capex_table": "保留经营现金流、购建长期资产现金流、投资活动现金流净额及同比变化。",
        "asset_impairment_note": "保留资产减值损失金额和减值原因。",
        "bills_receivable_note": "保留票据类型和期末余额/信用风险信息。",
        "financial_assets_note": "保留交易性金融资产金额、理财/公允价值变动等来源属性。",
    }
    return rules.get(usage, "若证据含有金额、比例、同比、数量或日期，summary 应尽量保留关键数字。")


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


def _reject_illegal_content(parsed: Dict[str, Any]) -> None:
    """Reject output that contains forbidden status markers in any string value."""
    text = _stringify_values(parsed).lower()
    for substring in _ILLEGAL_SUBSTRINGS:
        if substring in text:
            raise PeriodicReportLLMv2Error(f"illegal content detected: {substring!r}")


def _stringify_values(obj: Any) -> str:
    """Recursively concatenate all string values in a parsed structure."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_stringify_values(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_stringify_values(v) for v in obj)
    return ""


def _validate_evidence_refs(refs: Any, item_map: Dict[str, Any]) -> List[str]:
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, str) and ref in item_map]


def _reject_invalid_evidence_refs(refs: Any, item_map: Dict[str, Any]) -> None:
    """Fail closed when refs are missing or invalid."""
    if not isinstance(refs, list) or not refs:
        raise PeriodicReportLLMv2Error("invalid evidence_refs")
    for ref in refs:
        if not isinstance(ref, str) or ref not in item_map:
            raise PeriodicReportLLMv2Error("invalid evidence_refs")


def _has_citation_markers(text: str) -> bool:
    return bool(_CITATION_RE.search(text))


def _has_raw_url(text: str) -> bool:
    return bool(_URL_RE.search(text))


def _normalize_company_profile(
    profile: Any,
    item_map: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not isinstance(profile, dict):
        return None
    summary = str(profile.get("summary", ""))
    if _has_citation_markers(summary):
        raise PeriodicReportLLMv2Error("company_profile contains citation marker")
    if _has_raw_url(summary):
        raise PeriodicReportLLMv2Error("company_profile contains raw URL")
    summary = _sanitize_text(summary)
    if not summary:
        return None
    refs = profile.get("evidence_refs")
    _reject_invalid_evidence_refs(refs, item_map)
    refs = _validate_evidence_refs(refs, item_map)
    if not refs:
        return None
    if not _check_fidelity(summary, refs, item_map):
        return None
    return {"summary": summary, "evidence_refs": refs}


def _normalize_sections(
    sections: Iterable[Any],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    valid: List[Dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        usage = str(section.get("usage", "")).strip().lower()
        if usage not in _ALLOWED_SECTION_USAGES:
            continue
        title = _sanitize_text(str(section.get("title", "")))
        summary = str(section.get("summary", ""))
        if _has_citation_markers(summary) or _has_citation_markers(title):
            continue
        if _has_raw_url(summary) or _has_raw_url(title):
            raise PeriodicReportLLMv2Error("section contains raw URL")
        summary = _sanitize_text(summary)
        if not summary:
            continue
        refs = section.get("evidence_refs")
        _reject_invalid_evidence_refs(refs, item_map)
        refs = _validate_evidence_refs(refs, item_map)
        if not refs:
            continue
        confidence = _normalize_confidence(section.get("confidence"))
        if confidence is None:
            continue
        if not _check_fidelity(summary, refs, item_map):
            continue
        valid.append({
            "usage": usage,
            "title": title,
            "summary": summary,
            "evidence_refs": refs,
            "confidence": confidence,
        })
    return valid


def _normalize_financial_risks(
    risks: Iterable[Any],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    valid: List[Dict[str, Any]] = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        risk_type = str(risk.get("risk_type", "")).strip().lower()
        if risk_type not in _ALLOWED_RISK_TYPES:
            continue
        summary = str(risk.get("summary", ""))
        if _has_citation_markers(summary):
            continue
        if _has_raw_url(summary):
            raise PeriodicReportLLMv2Error("financial_risk contains raw URL")
        summary = _sanitize_text(summary)
        if not summary:
            continue
        refs = risk.get("evidence_refs")
        _reject_invalid_evidence_refs(refs, item_map)
        refs = _validate_evidence_refs(refs, item_map)
        if not refs:
            continue
        severity = str(risk.get("severity", "")).strip().lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        confidence = _normalize_confidence(risk.get("confidence"))
        if confidence is None:
            continue
        if not _check_fidelity(summary, refs, item_map):
            continue
        valid.append({
            "risk_type": risk_type,
            "summary": summary,
            "evidence_refs": refs,
            "severity": severity,
            "confidence": confidence,
        })
    return valid


def _normalize_top_level_keys(parsed: Dict[str, Any]) -> None:
    allowed = {
        "schema_version",
        "company_profile",
        "cards",
        "sections",
        "financial_risks",
        "follow_up_questions",
    }
    extras = set(parsed.keys()) - allowed
    if extras:
        raise PeriodicReportLLMv2Error(f"unsupported top-level field: {sorted(extras)[0]!r}")


def _normalize_questions(
    questions: Iterable[Any],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if any(not isinstance(q, dict) for q in questions):
        raise PeriodicReportLLMv2Error("follow_up_questions must be object list")
    valid: List[Dict[str, Any]] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        q = str(question.get("question", ""))
        if _has_citation_markers(q):
            continue
        if _has_raw_url(q):
            raise PeriodicReportLLMv2Error("follow_up_question contains raw URL")
        q = _sanitize_text(q)
        if not q:
            continue
        refs = question.get("evidence_refs")
        _reject_invalid_evidence_refs(refs, item_map)
        refs = _validate_evidence_refs(refs, item_map)
        if not refs:
            continue
        valid.append({"question": q, "evidence_refs": refs})
    return valid


def _normalize_cards(
    cards: Iterable[Any],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    valid: List[Dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        card_type = str(card.get("card_type", "")).strip().lower()
        if card_type not in _ALLOWED_CARD_TYPES:
            continue
        title = _sanitize_text(str(card.get("title", "")))
        if _has_citation_markers(title):
            continue
        if _has_raw_url(title):
            raise PeriodicReportLLMv2Error("card contains raw URL")
        raw_bullets = card.get("bullets")
        if not isinstance(raw_bullets, list):
            continue
        bullets: List[str] = []
        for bullet in raw_bullets[:8]:
            if not isinstance(bullet, str):
                continue
            if _has_citation_markers(bullet):
                continue
            if _has_raw_url(bullet):
                raise PeriodicReportLLMv2Error("card contains raw URL")
            cleaned = _sanitize_text(bullet)
            if cleaned:
                bullets.append(cleaned)
        if not bullets:
            continue
        refs = card.get("evidence_refs")
        _reject_invalid_evidence_refs(refs, item_map)
        refs = _validate_evidence_refs(refs, item_map)
        if not refs:
            continue
        confidence = _normalize_confidence(card.get("confidence"))
        if confidence is None:
            continue
        if not all(_check_fidelity(bullet, refs, item_map) for bullet in bullets):
            continue
        valid.append({
            "card_type": card_type,
            "title": title,
            "bullets": bullets,
            "evidence_refs": refs,
            "confidence": confidence,
        })
    return valid


def _normalize_confidence(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        confidence = value
    else:
        try:
            confidence = int(value)
        except (TypeError, ValueError):
            return None
    if confidence < 0 or confidence > 100:
        return None
    return confidence


def _sanitize_text(text: str) -> str:
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _REPEATED_SPACE_RE.sub(" ", text)
    return text.strip()


def _clean_text(text: str) -> str:
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    text = _REPEATED_SPACE_RE.sub(" ", text)
    return text.strip()


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _empty_analysis(evidence_pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_type": "periodic_report_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": True,
        "report_type": evidence_pack.get("report_type", "unknown"),
        "audit_status": evidence_pack.get("audit_status", "unknown"),
        "company_profile": {},
        "cards": [],
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    }


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# Fidelity helpers
# ---------------------------------------------------------------------------


def _check_fidelity(summary: str, refs: List[str], item_map: Dict[str, Any]) -> bool:
    """Return True if summary numbers/entities are grounded in refs."""
    evidence_text = "\n".join(_ref_text(ref, item_map) for ref in refs)
    evidence_text = _normalize_for_fidelity(evidence_text)
    summary_norm = _normalize_for_fidelity(summary)

    # Contextual years: allow the report year to appear without requiring it in
    # every referenced block.
    contextual_years = _extract_contextual_years(summary_norm)

    # Verbatim numbers: every concrete value must appear in evidence after unit
    # normalization, except for derived growth rates and contextual years.
    for number, raw in _extract_numbers(summary_norm):
        if raw in contextual_years:
            continue
        if _number_supported_by_evidence(number, raw, evidence_text):
            continue
        if _is_derived_growth_rate(raw, refs, item_map):
            continue
        return False

    # Entity fidelity: strict normalized substring matching for product/customer names.
    for entity in _extract_entities(summary_norm):
        if entity not in evidence_text:
            return False

    return True


def _ref_text(ref: str, item_map: Dict[str, Any]) -> str:
    block = item_map.get(ref) or {}
    parts = [
        str(block.get("section", "")),
        str(block.get("title", "")),
        str(block.get("text", "")),
    ]
    return "\n".join(parts)


def _normalize_for_fidelity(text: str) -> str:
    """Normalize text for fidelity checks: units, commas, whitespace, CJK spacing."""
    text = text.replace(",", "")
    text = re.sub(r"\s+", "", text)
    # Normalize common units to a canonical form (yuan).
    text = _normalize_units(text)
    return text


def _normalize_units(text: str) -> str:
    """Convert yuan units to a canonical numeric string in yuan."""
    # Replace 亿元 with *1e8, 万元 with *1e4.
    text = re.sub(r"(-?[\d\.]+)\s*亿元", lambda m: _convert_yuan(m.group(1), 100_000_000), text)
    text = re.sub(r"(-?[\d\.]+)\s*万元", lambda m: _convert_yuan(m.group(1), 10_000), text)
    return text


def _convert_yuan(raw: str, multiplier: int) -> str:
    number = _parse_number(raw)
    if number is None:
        return raw
    return str(int(round(number * multiplier)))


def _extract_numbers(text: str) -> List[Tuple[Optional[float], str]]:
    """Return parsed numbers and raw tokens from normalized text."""
    results: List[Tuple[Optional[float], str]] = []
    for match in re.finditer(r"-?\d+(?:\.\d+)?(?:%|pct|个百分点)?", text):
        prev_char = text[match.start() - 1] if match.start() > 0 else ""
        next_char = text[match.end()] if match.end() < len(text) else ""
        if _is_model_code_neighbor(prev_char) or _is_model_code_neighbor(next_char):
            continue
        raw = match.group(0)
        number = _parse_number(raw.replace("%", "").replace("pct", "").replace("个百分点", ""))
        results.append((number, raw))
    return results


def _is_model_code_neighbor(char: str) -> bool:
    return bool(char and re.match(r"[A-Za-z]", char))


def _number_supported_by_evidence(
    number: Optional[float],
    raw: str,
    evidence_text: str,
) -> bool:
    if number is None:
        return False
    if raw in evidence_text or str(number) in evidence_text:
        return True
    # Percentages and point changes should match verbatim or be derivable; do
    # not allow fuzzy matching for small ratio-like figures.
    if "%" in raw or "pct" in raw or "个百分点" in raw:
        return False
    # Allow rounded yuan amounts such as 4.43亿元 to match 443,494,353.42元.
    if abs(number) < 10_000:
        return False
    for evidence_number, _ in _extract_numbers(evidence_text):
        if evidence_number is None or abs(evidence_number) < 10_000:
            continue
        tolerance = max(10_000.0, abs(evidence_number) * 0.01)
        if abs(evidence_number - number) <= tolerance:
            return True
    return False


def _extract_contextual_years(text: str) -> List[str]:
    """Allow report-year references without requiring them in every block."""
    years = set()
    for match in re.finditer(r"20\d{2}\s*(?:年|年度|财年)?", text):
        years.add(match.group(0).replace(" ", ""))
        # Also add the bare year.
        years.add(match.group(0)[:4])
    return list(years)


def _extract_entities(text: str) -> List[str]:
    """Extract explicit product/customer/supplier names from summary.

    Phase A uses strict substring matching: a name mentioned after 客户/产品/供应商
    must appear in the referenced evidence. The capture is bounded by common
    follow-ups to avoid over-matching narrative text.
    """
    entities: List[str] = []
    predicate_chars = set("占高较风险的是为达约等主来源合计销售收入贡献订单来看向及与在")
    pattern = re.compile(
        r"(?:客户|产品|供应商)\s*(?:[是为叫]?[：:]?)?"
        r"([一-鿿A-Za-z0-9（）()]{1,8}?)"
        r"(?=\s*(?:占比|销售|收入|订单|贡献|合计|的|是|为|达|约|分别|主要|等|，|。|；|！|？|$))"
    )
    for match in pattern.finditer(text):
        entity = match.group(1)
        if any(ch in predicate_chars for ch in entity):
            continue
        entities.append(entity)
    return entities


def _is_derived_growth_rate(raw: str, refs: List[str], item_map: Dict[str, Any]) -> bool:
    """Check whether raw looks like a growth rate derivable from two period values."""
    if "%" not in raw and "pct" not in raw and "百分点" not in raw:
        return False
    value = _parse_number(raw.replace("%", "").replace("pct", "").replace("个百分点", ""))
    if value is None:
        return False
    evidence_text = "\n".join(_ref_text(ref, item_map) for ref in refs)
    evidence_text = _normalize_for_fidelity(evidence_text)
    # Look for two numbers in evidence that could produce this growth rate.
    numbers = []
    for match in re.finditer(r"-?[\d\.]+(?:%|pct|个百分点)?", evidence_text):
        n = _parse_number(match.group(0).replace("%", "").replace("pct", "").replace("个百分点", ""))
        if n is not None and abs(n) < 1_000_000_000_000:
            numbers.append(n)
    for i, a in enumerate(numbers):
        for b in numbers[i + 1 :]:
            if b == 0:
                continue
            derived = (a - b) / abs(b) * 100
            if abs(derived - value) < 0.5:
                return True
    return False


def _parse_number(value: str) -> Optional[float]:
    try:
        cleaned = str(value).replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return float(cleaned)
    except (TypeError, ValueError):
        return None
