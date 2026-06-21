"""Narrative evidence cards helper for periodic reports.

This helper extracts short, evidence-bound narrative cards from report text
blocks produced by ``periodic_report_evidence_pack``. It is deliberately
read-only: it does not access the network, call an LLM, or write files.

v1 is helper-only. Cards are not persisted to Knowledge, not fed into scoring,
and not synthesized by KnowledgeSynthesizer.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


CARDS_SCHEMA_VERSION = "periodic_report_narrative_evidence_cards.v1"
CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v1"
SOURCE_TYPE = "periodic_report_narrative_evidence"

_CARD_TYPES = (
    "business_model",
    "operation_update",
    "management_market_view",
    "rd_product_progress",
    "financial_note",
)

_USAGE_TO_CARD_TYPES: Dict[str, Tuple[str, ...]] = {
    "business_overview": ("business_model",),
    "business_model": ("business_model",),
    "product_capacity_profile": ("business_model", "rd_product_progress"),
    "sales_certification_model": ("business_model",),
    "management_strategy": ("operation_update", "rd_product_progress"),
    "management_market_view": ("operation_update", "management_market_view"),
    "industry_outlook": ("management_market_view",),
    "risk_disclosure": ("management_market_view",),
    "segment_table": ("operation_update",),
    "production_sales_inventory_table": ("operation_update",),
    "rd_table": ("rd_product_progress",),
    "rd_investment_table": ("rd_product_progress",),
    "cash_flow_capex_table": ("financial_note",),
    "asset_impairment_note": ("financial_note",),
    "ar_aging_note": ("financial_note",),
    "inventory_note": ("financial_note",),
    "audit_key_matters": ("financial_note",),
    "governance_dissent": ("financial_note",),
    "government_grant_note": ("financial_note",),
    "financial_assets_note": ("financial_note",),
    "goodwill_note": ("financial_note",),
}

_CARD_TYPE_MARKERS: Dict[str, Tuple[str, ...]] = {
    "business_model": (
        "主营业务",
        "经营模式",
        "产品主要应用",
        "主要产品",
        "客户",
        "销售模式",
        "应用领域",
        "产业链",
    ),
    "operation_update": (
        "报告期内",
        "销量",
        "产量",
        "产能",
        "订单",
        "库存",
        "客户导入",
        "项目投产",
        "同比增长",
        "销售收入",
    ),
    "management_market_view": (
        "行业",
        "竞争",
        "价格承压",
        "景气",
        "需求",
        "市场",
        "政策",
        "国产替代",
        "技术周期",
        "产能过剩",
        "格局",
    ),
    "rd_product_progress": (
        "研发",
        "专利",
        "量产",
        "认证",
        "验证",
        "导入",
        "技术突破",
        "新产品",
        "工程化",
        "产业化",
        "小批量供货",
    ),
    "financial_note": (
        "现金流",
        "减值",
        "存货",
        "应收",
        "审计",
        "政府补助",
        "投资",
        "商誉",
        "金融资产",
        "跌价准备",
        "关键审计事项",
        "董事异议",
    ),
}

_CARD_TYPE_TITLES: Dict[str, str] = {
    "business_model": "主营业务与产品",
    "operation_update": "经营情况更新",
    "management_market_view": "管理层市场判断",
    "rd_product_progress": "研发与产品进展",
    "financial_note": "财务备注",
}

# Tokens that suggest an LLM added interpretive language rather than original
# report text. "说明" alone appears in ordinary filing notes ("年报附注说明"),
# so only causal model-like phrases are rejected outright. "需要跟踪" may appear
# in original forward-looking statements, so it is only rejected when it lacks a
# concrete customer/product/project context.
_LLM_PHRASES = ("这意味着", "这说明", "需要跟踪")
_LLM_CONTEXTUAL_EXCEPTION_TOKENS = ("客户", "产品", "项目", "主机厂", "车型", "量产", "验证")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_TOC_RE = re.compile(r"\.{3,}|…{2,}")
_TABLE_STRUCTURE_TOKENS = (
    "主要研发项目名称",
    "项目目的",
    "项目进展",
    "拟达到的目标",
    "预计对公司未来发展的影响",
    "营业收入",
    "营业成本",
    "毛利率",
    "销售量",
    "生产量",
    "库存量",
)

_MIN_EXCERPT_LENGTH = 40
_MAX_EXCERPT_LENGTH = 500


def build_periodic_report_narrative_evidence_cards(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    evidence_pack: dict,
    max_cards_per_type: int = 3,
    max_total_cards: int = 12,
) -> dict:
    """Build narrative evidence cards from an evidence pack."""
    diagnostics: List[Dict[str, Any]] = []
    blocks = evidence_pack.get("blocks") or []
    if not blocks:
        diagnostics.append({"code": "empty_evidence_pack"})
        return _envelope(
            stock_code=stock_code,
            stock_name=stock_name,
            report_year=report_year,
            report_type=report_type,
            cards=[],
            diagnostics=diagnostics,
        )

    candidates = _collect_candidates(blocks, diagnostics)
    if not candidates:
        diagnostics.append({"code": "no_candidate_snippets"})

    typed_cards: Dict[str, List[Dict[str, Any]]] = {ct: [] for ct in _CARD_TYPES}
    seen_excerpts: Set[str] = set()

    for snippet, block_id, card_type, score, _source_order in candidates:
        excerpt = _normalize_excerpt(snippet)
        if not _is_valid_excerpt(excerpt):
            diagnostics.append({
                "code": "filtered_invalid_excerpt",
                "card_type": card_type,
                "reason": "length_or_quality",
            })
            continue
        if excerpt in seen_excerpts:
            continue
        seen_excerpts.add(excerpt)
        typed_cards[card_type].append(
            _build_card(
                stock_code=stock_code,
                stock_name=stock_name,
                report_year=report_year,
                report_type=report_type,
                card_type=card_type,
                card_index=len(typed_cards[card_type]),
                source_block_id=block_id,
                excerpt=excerpt,
                score=score,
            )
        )

    cards = _truncate_cards(typed_cards, max_cards_per_type, max_total_cards)
    return _envelope(
        stock_code=stock_code,
        stock_name=stock_name,
        report_year=report_year,
        report_type=report_type,
        cards=cards,
        diagnostics=diagnostics,
    )


def _envelope(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    cards: List[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "schema_version": CARDS_SCHEMA_VERSION,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_year": report_year,
        "report_type": report_type,
        "cards": cards,
        "diagnostics": diagnostics,
    }


def _collect_candidates(
    blocks: Iterable[Dict[str, Any]],
    diagnostics: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, int, int]]:
    """Return (snippet, block_id, card_type, score, source_order) candidates."""
    candidates: List[Tuple[str, str, str, int, int]] = []
    source_order = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "")
        usage = str(block.get("usage") or "")
        text = str(block.get("text") or "")
        if not block_id or not usage or not text:
            continue
        card_types = _USAGE_TO_CARD_TYPES.get(usage, ())
        if not card_types:
            continue
        for snippet in _split_snippets(text):
            for card_type in card_types:
                markers = _CARD_TYPE_MARKERS.get(card_type, ())
                score = _score_snippet(snippet, markers)
                if score <= 0:
                    continue
                candidates.append((snippet, block_id, card_type, score, source_order))
                source_order += 1
    return sorted(
        candidates,
        key=lambda item: (_CARD_TYPES.index(item[2]), -item[3], item[4]),
    )


def _split_snippets(text: str) -> List[str]:
    """Split block text into sentence-like snippets."""
    normalized = re.sub(r"\s+", " ", text).strip()
    pieces = re.split(r"(?<=[。；;])\s+", normalized)
    return [piece.strip(" 　：:") for piece in pieces if len(piece.strip()) >= _MIN_EXCERPT_LENGTH]


def _score_snippet(snippet: str, markers: Iterable[str]) -> int:
    return sum(1 for marker in markers if marker in snippet)


def _normalize_excerpt(text: str) -> str:
    excerpt = re.sub(r"\s+", " ", text).strip()
    if len(excerpt) > _MAX_EXCERPT_LENGTH:
        excerpt = excerpt[: _MAX_EXCERPT_LENGTH - 1].rstrip() + "…"
    return excerpt


def _is_valid_excerpt(excerpt: str) -> bool:
    if len(excerpt) < _MIN_EXCERPT_LENGTH or len(excerpt) > _MAX_EXCERPT_LENGTH:
        return False
    if _TOC_RE.search(excerpt):
        return False
    if _URL_RE.search(excerpt):
        return False
    if _looks_like_table_fragment(excerpt):
        return False
    if _looks_like_audit_matter_boilerplate(excerpt):
        return False
    if _looks_like_accounting_policy_boilerplate(excerpt):
        return False
    if _contains_llm_phrase(excerpt):
        return False
    return True


def _looks_like_audit_matter_boilerplate(snippet: str) -> bool:
    audit_boilerplate_tokens = (
        "关键审计事项是我们根据职业判断",
        "对财务报表整体进行审计",
        "不对这些事项单独发表意见",
        "forming our opinion thereon",
        "do not provide a separate opinion",
    )
    return sum(1 for token in audit_boilerplate_tokens if token in snippet) >= 2


def _looks_like_accounting_policy_boilerplate(snippet: str) -> bool:
    """Filter generic accounting-policy text that is not company-specific."""
    if _looks_like_policy_without_company_context(snippet):
        return True
    policy_token_groups = (
        (
            "资产负债表日",
            "采用",
            "成本与可变现净值孰低",
            "差额计提",
            "估计售价",
            "估计的销售费用",
            "相关税费",
        ),
        (
            "持有待售",
            "处置组",
            "商誉的账面价值",
            "按比例抵减",
            "账面价值所占比重",
            "转回金额计入当期损益",
        ),
        (
            "资产减值损失转回",
            "会计处理",
            "后续资产负债表日",
            "持有待售",
            "减记的金额予以恢复",
            "转回金额计入当期损益",
        ),
    )
    return any(
        sum(1 for token in token_group if token in snippet) >= 3
        for token_group in policy_token_groups
    )


def _looks_like_policy_without_company_context(snippet: str) -> bool:
    policy_tokens = ("会计处理", "初始计量", "后续计量", "持有待售", "孰低计量")
    company_context_tokens = (
        "报告期",
        "本期",
        "本年度",
        "期末余额",
        "原因",
        "主要系",
        "由于",
        "受",
        "影响",
        "同比",
    )
    return (
        sum(1 for token in policy_tokens if token in snippet) >= 2
        and not any(token in snippet for token in company_context_tokens)
    )


def _looks_like_table_fragment(snippet: str) -> bool:
    """Return True for dense numeric/table-only snippets."""
    if sum(1 for token in _TABLE_STRUCTURE_TOKENS if token in snippet) >= 3:
        return True
    numbers = re.findall(r"(?<![A-Za-z0-9])\d[\d,\.]*(?![A-Za-z0-9])", snippet)
    if len(numbers) >= 3:
        return True
    non_space = re.sub(r"\s+", "", snippet)
    if non_space:
        digit_ratio = sum(1 for ch in non_space if ch.isdigit()) / len(non_space)
        if digit_ratio > 0.35:
            return True
    return False


def _contains_llm_phrase(excerpt: str) -> bool:
    for phrase in _LLM_PHRASES:
        if phrase not in excerpt:
            continue
        if phrase == "需要跟踪":
            if any(token in excerpt for token in _LLM_CONTEXTUAL_EXCEPTION_TOKENS):
                continue
        return True
    return False


def _build_card(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    card_type: str,
    card_index: int,
    source_block_id: str,
    excerpt: str,
    score: int,
) -> Dict[str, Any]:
    card_id = (
        f"periodic:{stock_code}:{report_year}:{report_type}:"
        f"narrative:{card_type}:{card_index}"
    )
    confidence = "medium_high" if score >= 2 else "medium"
    keywords = [m for m in _CARD_TYPE_MARKERS.get(card_type, ()) if m in excerpt]
    return {
        "schema_version": CARD_SCHEMA_VERSION,
        "source_type": SOURCE_TYPE,
        "card_id": card_id,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_year": report_year,
        "report_type": report_type,
        "card_type": card_type,
        "title": _CARD_TYPE_TITLES.get(card_type, card_type),
        "source_block_id": source_block_id,
        "evidence_refs": [source_block_id],
        "source_excerpt": excerpt,
        "keywords": keywords[:5],
        "confidence": confidence,
        "source_credit": 75,
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "experimental": True,
    }


def _truncate_cards(
    typed_cards: Dict[str, List[Dict[str, Any]]],
    max_cards_per_type: int,
    max_total_cards: int,
) -> List[Dict[str, Any]]:
    """Apply per-type cap then global cap in fixed card_type order.

    Cards keep their per-type stable index; the global cap only limits how many
    card types are included.
    """
    cards: List[Dict[str, Any]] = []
    for card_type in _CARD_TYPES:
        group = typed_cards.get(card_type, [])[:max_cards_per_type]
        cards.extend(group)
        if len(cards) >= max_total_cards:
            break
    return cards[:max_total_cards]
