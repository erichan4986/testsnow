"""Narrative evidence cards helper for periodic reports.

This helper extracts short, evidence-bound narrative cards from report text
blocks produced by ``periodic_report_evidence_pack``. It is deliberately
read-only: it does not access the network, call an LLM, or write files.

v1 is helper-only. Cards are not persisted to Knowledge, not fed into scoring,
and not synthesized by KnowledgeSynthesizer.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


CARDS_SCHEMA_VERSION = "periodic_report_narrative_evidence_cards.v1"
CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v1"
SOURCE_TYPE = "periodic_report_narrative_evidence"

_CARD_TYPES = (
    "business_model",
    "operation_update",
    "management_market_view",
    "market_outlook",
    "margin_competitiveness",
    "rd_product_progress",
    "financial_note",
)

_USAGE_TO_CARD_TYPES: Dict[str, Tuple[str, ...]] = {
    "business_overview": ("business_model",),
    "business_model": ("business_model",),
    "product_capacity_profile": ("business_model", "rd_product_progress"),
    "sales_certification_model": ("business_model",),
    "management_strategy": ("operation_update", "rd_product_progress"),
    "management_market_view": ("management_market_view", "market_outlook"),
    "industry_outlook": ("management_market_view", "market_outlook"),
    "market_demand_outlook": ("management_market_view", "market_outlook"),
    "competitive_position": ("management_market_view", "margin_competitiveness"),
    "future_strategy": ("management_market_view", "market_outlook"),
    "profitability_commentary": ("management_market_view", "margin_competitiveness"),
    "segment_table": ("operation_update",),
    "production_sales_inventory_table": ("operation_update",),
    "rd_product_progress": ("rd_product_progress",),
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
        "核心竞争力",
        "竞争优势",
        "行业地位",
        "市场份额",
        "价格承压",
        "景气",
        "需求",
        "市场",
        "市场规模",
        "复合增长率",
        "资本开支",
        "算力",
        "AI",
        "光模块",
        "数据中心",
        "ASIC",
        "GPU",
        "1.6T",
        "3.2T",
        "800G",
        "硅光",
        "相干",
        "发展战略",
        "未来发展",
        "发展趋势",
        "政策",
        "国产替代",
        "技术周期",
        "产能过剩",
        "格局",
        "毛利率",
        "盈利能力",
        "规模效应",
    ),
    "market_outlook": (
        "市场需求",
        "市场规模",
        "复合增长率",
        "行业景气",
        "景气度",
        "需求",
        "市场",
        "预计",
        "预测",
        "未来",
        "资本开支",
        "算力",
        "AI",
        "数据中心",
        "国产替代",
        "政策",
        "增长",
    ),
    "margin_competitiveness": (
        "毛利率",
        "盈利能力",
        "产品结构",
        "高端产品",
        "出货占比",
        "规模效应",
        "价格承压",
        "价格",
        "成本",
        "竞争力",
        "竞争优势",
        "行业地位",
        "市场份额",
        "交付能力",
        "产品制造能力",
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
        "小批量交付",
        "客户验证",
        "热界面材料",
        "导热材料",
        "TIM",
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
    "market_outlook": "市场前景判断",
    "margin_competitiveness": "毛利率与竞争力",
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
    "报告期投资额",
    "上年同期投资额",
    "适用 □不适用",
    "适用 □不适用",
)

_GENERIC_GLOSSARY_TERMS = {
    "A股",
    "IC",
    "公司",
    "本公司",
    "董事会",
    "监事会",
    "股东会",
    "股东大会",
    "报告期",
    "本报告期",
    "年度",
    "报告期末",
    "本报告期末",
    "上年同期",
    "元",
    "万元",
    "亿元",
    "元、万元",
    "元、万元、亿元",
    "人民币元",
    "人民币万元",
    "芯片",
    "半导体",
    "集成电路",
    "晶圆",
    "封装",
    "测试",
    "中国证监会",
    "上交所",
    "深交所",
    "证券交易所",
    "公司章程",
    "公司法",
    "证券法",
    "保荐机构",
    "审计机构",
}

_GENERIC_GLOSSARY_SUBSTRINGS = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "合伙企业",
    "股权投资",
    "投资基金",
    "企业管理",
    "证券交易所",
    "证券有限",
    "会计师事务所",
    "公司章程",
    "中华人民共和国",
    "中国证券登记结算",
)

_TECH_TERM_HINTS = (
    "芯片",
    "模组",
    "模块",
    "工艺",
    "算法",
    "技术",
    "平台",
    "系统",
    "封装",
    "验证",
    "仿真",
    "版图",
    "模型",
    "软件",
    "工具",
    "核",
    "转换器",
    "管理",
    "计量",
    "光模块",
    "碳纤维",
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
    raw_text: str = "",
    max_cards_per_type: int = 12,
    max_total_cards: int = 24,
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

    dynamic_terms = _extract_dynamic_terms(blocks, raw_text=raw_text)
    block_text_by_id = {
        str(block.get("id")): str(block.get("text") or "")
        for block in blocks
        if isinstance(block, dict) and block.get("id")
    }
    candidates = _collect_candidates(blocks, diagnostics, dynamic_terms)
    if not candidates:
        diagnostics.append({"code": "no_candidate_snippets"})

    typed_cards: Dict[str, List[Dict[str, Any]]] = {ct: [] for ct in _CARD_TYPES}
    seen_excerpts: Set[Tuple[str, str]] = set()
    seen_fingerprints: Dict[str, List[str]] = {}

    for snippet, block_id, card_type, score, _source_order, matched_terms in candidates:
        excerpt = _normalize_excerpt(snippet, card_type)
        if not _is_valid_excerpt(excerpt, card_type):
            diagnostics.append({
                "code": "filtered_invalid_excerpt",
                "card_type": card_type,
                "reason": "length_or_quality",
            })
            continue
        dedupe_scope = _dedupe_scope(card_type)
        seen_fingerprints.setdefault(dedupe_scope, [])
        excerpt_key = (dedupe_scope, excerpt)
        if excerpt_key in seen_excerpts:
            continue
        fingerprint = _excerpt_fingerprint(excerpt)
        if _is_near_duplicate_fingerprint(fingerprint, seen_fingerprints[dedupe_scope]):
            continue
        seen_excerpts.add(excerpt_key)
        seen_fingerprints[dedupe_scope].append(fingerprint)
        typed_cards[card_type].append(
            _build_card(
                stock_code=stock_code,
                stock_name=stock_name,
                report_year=report_year,
                report_type=report_type,
                card_type=card_type,
                card_index=len(typed_cards[card_type]),
                source_block_id=block_id,
                source_block_text=block_text_by_id.get(block_id, ""),
                excerpt=excerpt,
                score=score,
                dynamic_terms=matched_terms,
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


def _dedupe_scope(card_type: str) -> str:
    if card_type in {"business_model", "rd_product_progress"}:
        return "business_and_rd"
    return card_type


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
    dynamic_terms: Sequence[str],
) -> List[Tuple[str, str, str, int, int, Tuple[str, ...]]]:
    """Return (snippet, block_id, card_type, score, source_order, terms) candidates."""
    candidates: List[Tuple[str, str, str, int, int, Tuple[str, ...]]] = []
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
            matched_terms = _matched_dynamic_terms(snippet, dynamic_terms)
            for card_type in card_types:
                markers = _CARD_TYPE_MARKERS.get(card_type, ())
                score = _score_snippet(snippet, markers, matched_terms)
                if score <= 0:
                    continue
                candidates.append((snippet, block_id, card_type, score, source_order, matched_terms))
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


def _score_snippet(snippet: str, markers: Iterable[str], dynamic_terms: Sequence[str] = ()) -> int:
    marker_score = sum(1 for marker in markers if marker in snippet)
    if marker_score <= 0:
        return 0
    return marker_score + min(len(dynamic_terms), 4) * 2


def _max_excerpt_length(card_type: str = "") -> int:
    if card_type == "margin_competitiveness":
        return 800
    return _MAX_EXCERPT_LENGTH


def _normalize_excerpt(text: str, card_type: str = "") -> str:
    excerpt = re.sub(r"\s+", " ", text).strip()
    excerpt = _trim_product_feature_table_header(excerpt)
    max_chars = _max_excerpt_length(card_type)
    if len(excerpt) > max_chars:
        excerpt = _truncate_at_sentence_boundary(excerpt, max_chars)
    return excerpt


def _source_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _trim_product_feature_table_header(excerpt: str) -> str:
    header_tokens = ("产品类型", "图片示例", "主要技术特点", "主要应用领域")
    if sum(1 for token in header_tokens if token in excerpt) < 3:
        return excerpt
    header_end = max(excerpt.find(token) + len(token) for token in header_tokens if token in excerpt)
    tail = excerpt[header_end:].lstrip(" 　：:，,。；;")
    for anchor in ("依托于公司", "公司自主研发", "报告期内", "该产品", "该系列产品"):
        anchor_pos = tail.find(anchor)
        if anchor_pos >= 0:
            return tail[anchor_pos:].strip()
    return tail.strip() or excerpt


def _truncate_at_sentence_boundary(text: str, max_chars: int) -> str:
    window = text[:max_chars].rstrip()
    cut_positions = [
        window.rfind(mark)
        for mark in ("。", "；", ";")
    ]
    cut = max(cut_positions)
    if cut >= _MIN_EXCERPT_LENGTH:
        return window[: cut + 1].rstrip()
    return text[: max_chars - 1].rstrip() + "…"


def _excerpt_fingerprint(excerpt: str) -> str:
    text = re.sub(r"^[#>\s\d一二三四五六七八九十、（）()：:.-]+", "", excerpt)
    text = re.sub(r"(销售模式|经营模式|主营业务|主要产品|报告期内)", "", text)
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _is_near_duplicate_fingerprint(fingerprint: str, seen: Iterable[str]) -> bool:
    if len(fingerprint) < _MIN_EXCERPT_LENGTH:
        return False
    for existing in seen:
        if not existing:
            continue
        shorter, longer = sorted((fingerprint, existing), key=len)
        if shorter == longer:
            return True
        if len(shorter) >= _MIN_EXCERPT_LENGTH and shorter in longer:
            return len(shorter) / len(longer) >= 0.72
    return False


def _is_valid_excerpt(excerpt: str, card_type: str = "") -> bool:
    if len(excerpt) < _MIN_EXCERPT_LENGTH or len(excerpt) > _max_excerpt_length(card_type):
        return False
    if _TOC_RE.search(excerpt):
        return False
    if _URL_RE.search(excerpt):
        return False
    if _looks_like_hash_fragment(excerpt):
        return False
    if _looks_like_applicability_checkbox_fragment(excerpt):
        return False
    if _looks_like_table_fragment(excerpt, card_type):
        return False
    if _looks_like_policy_catalog_fragment(excerpt):
        return False
    if _looks_like_chart_caption_fragment(excerpt):
        return False
    if _looks_like_income_statement_line_fragment(excerpt):
        return False
    if _looks_like_definition_fragment(excerpt):
        return False
    if card_type != "financial_note" and _looks_like_risk_paragraph(excerpt):
        return False
    if _looks_like_page_bullet_fragment(excerpt):
        return False
    if _looks_like_audit_matter_boilerplate(excerpt):
        return False
    if _looks_like_audit_response_procedure(excerpt):
        return False
    if _looks_like_accounting_policy_boilerplate(excerpt):
        return False
    if _contains_llm_phrase(excerpt):
        return False
    return True


def _looks_like_audit_matter_boilerplate(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    audit_boilerplate_tokens = (
        "关键审计事项是我们根据职业判断",
        "对财务报表整体进行审计",
        "不对这些事项单独发表意见",
        "基于所实施的审计程序",
        "管理层在商誉减值测试评估中采用的关键假设",
        "了解、评估了与管理层计提商誉减值相关的内部控制",
        "测试了相关控制设计和执行的有效性",
        "forming our opinion thereon",
        "do not provide a separate opinion",
    )
    return sum(
        1
        for token in audit_boilerplate_tokens
        if token in snippet or _compact_text(token) in compact_snippet
    ) >= 2


def _looks_like_audit_response_procedure(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    strong_procedure_tokens = (
        "审计程序中包括以下程序",
        "潜在减值相关的审计程序",
        "关键财务报告内部控制的设计和运行有效性",
        "对管理层编制预计未来现金流量的现值时采用的关键假设进行敏感性分析",
        "将管理层在上一年度计算预计未来现金流量的现值时使用的关键假设与本年度的实际结果进行比较",
        "关键假设进行敏感性分析",
        "评价是否存在管理层偏向的迹象",
    )
    if any(token in snippet or _compact_text(token) in compact_snippet for token in strong_procedure_tokens):
        return True
    procedure_tokens = (
        "我们获取了管理层聘请的外部评估师",
        "外部评估师的胜任能力",
        "内部估值专家协助",
        "商誉减值测试时所用的税前折现率",
        "关键财务报告内部控制",
        "设计和运行有效性",
        "关键假设进行敏感性分析",
        "执行敏感性分析",
    )
    if "执行敏感性分析" in snippet or "执行敏感性分析" in compact_snippet:
        return True
    return sum(
        1
        for token in procedure_tokens
        if token in snippet or _compact_text(token) in compact_snippet
    ) >= 2


def _looks_like_hash_fragment(snippet: str) -> bool:
    return snippet.count("#") >= 2


def _looks_like_risk_paragraph(snippet: str) -> bool:
    risk_heading = re.search(r"(^|[#\s、，。])[^。；;]{0,18}风险", snippet)
    return bool(risk_heading and ("将面临" in snippet or "可能导致" in snippet or "风险" in snippet[:40]))


def _looks_like_accounting_policy_boilerplate(snippet: str) -> bool:
    """Filter generic accounting-policy text that is not company-specific."""
    compact_snippet = _compact_text(snippet)
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
        (
            "商誉减值",
            "本公司至少每年测试商誉是否发生减值",
            "未来现金流量",
            "现值",
            "折现率",
        ),
        (
            "存货跌价准备",
            "本公司根据存货会计政策",
            "成本与可变现净值孰低",
            "鉴定存货减值要求管理层",
            "做出判断和估计",
        ),
        (
            "存货跌价准备的确认标准和计提方法",
            "资产负债表日",
            "成本与可变现净值孰低计量",
            "可变现净值低于成本",
            "提取存货跌价准备",
            "差额提取",
        ),
        (
            "计提存货跌价准备后",
            "以前减记存货价值的影响因素已经消失",
            "可变现净值高于其账面价值",
            "予以转回",
            "转回的金额计入当期损益",
        ),
        (
            "长期股权投资",
            "同一控制下的企业合并",
            "最终控制方合并财务报表",
            "初始投资成本",
            "调整资本公积",
            "调整留存收益",
        ),
        (
            "长期股权投资",
            "非同一控制下的企业合并",
            "购买日",
            "合并成本",
            "发行的权益性证券",
            "公允价值",
        ),
        (
            "非上市股权投资的公允价值",
            "本公司根据对当前市场状况的判断",
            "估值方法",
            "相关假设和估计",
            "公允价值发生重大变化",
        ),
    )
    return any(
        sum(1 for token in token_group if token in snippet or token in compact_snippet) >= 3
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


def _looks_like_applicability_checkbox_fragment(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    has_checkbox = any(mark in compact_snippet for mark in ("□", "", "☑", "■", "√"))
    if has_checkbox and compact_snippet.count("适用") >= 4:
        return True
    return (
        has_checkbox
        and "适用" in compact_snippet
        and "不适用" in compact_snippet
        and "年度报告" in compact_snippet
    )


def _looks_like_page_bullet_fragment(snippet: str) -> bool:
    return "年度报告全文" in snippet and any(mark in snippet for mark in ("", "> -"))


def _looks_like_policy_catalog_fragment(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    catalog_tokens = (
        "政策目录",
        "主管部门",
        "相关政策内容",
        "国家发改委",
        "国家数据局",
        "中国证监会",
        "关于促进数据产业高质量发展的指导意见",
    )
    return sum(1 for token in catalog_tokens if token in snippet or token in compact_snippet) >= 2


def _looks_like_chart_caption_fragment(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    return (
        "年度报告全文" in compact_snippet
        and "图" in compact_snippet[:80]
        and ("来源" in compact_snippet[:120] or "资料来源" in compact_snippet[:120])
    )


def _looks_like_income_statement_line_fragment(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    if (
        "损失以" in compact_snippet
        and "填列" in compact_snippet
        and len(re.findall(r"-?\d[\d,\.]*", snippet)) >= 2
    ):
        return True
    if "主要为" not in snippet:
        return False
    numbers = re.findall(r"-?\d[\d,\.]*%?", snippet)
    profit_loss_line_tokens = (
        "信用减值损失",
        "公允价值变动损益",
        "资产减值损失",
        "资产处置收益",
        "投资收益",
        "营业外收入",
        "营业外支出",
    )
    starts_with_checkbox_answer = bool(re.match(r"^\s*(?:是|否)\s+", snippet))
    return (
        len(numbers) >= 2
        and any(token in snippet for token in profit_loss_line_tokens)
        and (starts_with_checkbox_answer or len(snippet) <= 120)
    )


def _looks_like_definition_fragment(snippet: str) -> bool:
    compact_snippet = _compact_text(snippet)
    if "释义项指释义内容" in compact_snippet:
        return True
    definition_patterns = (
        r"^[^。；;]{1,45}指的是",
        r"^[^。；;]{1,45}是指",
        r"^[^。；;]{1,45}\s指\s",
    )
    if any(re.search(pattern, snippet) for pattern in definition_patterns):
        return True
    return snippet.count("指") >= 2 and any(token in snippet for token in ("释义", "指的是", "是指"))


def _looks_like_table_fragment(snippet: str, card_type: str = "") -> bool:
    """Return True for dense numeric/table-only snippets."""
    if sum(1 for token in _TABLE_STRUCTURE_TOKENS if token in snippet) >= 3:
        return True
    numbers = re.findall(r"(?<![A-Za-z0-9])\d[\d,\.]*(?![A-Za-z0-9])", snippet)
    narrative_number_card_types = {"management_market_view", "margin_competitiveness"}
    if len(numbers) >= 3 and card_type not in narrative_number_card_types:
        return True
    non_space = re.sub(r"\s+", "", snippet)
    if non_space:
        digit_ratio = sum(1 for ch in non_space if ch.isdigit()) / len(non_space)
        if digit_ratio > 0.35 and card_type not in narrative_number_card_types:
            return True
    return False


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _contains_llm_phrase(excerpt: str) -> bool:
    for phrase in _LLM_PHRASES:
        if phrase not in excerpt:
            continue
        if phrase == "需要跟踪":
            if any(token in excerpt for token in _LLM_CONTEXTUAL_EXCEPTION_TOKENS):
                continue
        return True
    return False


def _extract_dynamic_terms(blocks: Iterable[Dict[str, Any]], raw_text: str = "") -> Tuple[str, ...]:
    terms: List[str] = []
    seen: Set[str] = set()
    for term in _extract_terms_from_text(raw_text or ""):
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = str(block.get("text") or "")
        if not text:
            continue
        for term in _extract_terms_from_text(text):
            if term in seen:
                continue
            seen.add(term)
            terms.append(term)
    # Longer terms first avoids letting a generic suffix dominate matching.
    return tuple(sorted(terms, key=lambda term: (-len(_compact_text(term)), term)))


def _extract_terms_from_text(text: str) -> List[str]:
    normalized = _normalize_for_term_extraction(text)
    candidates: List[str] = []
    candidates.extend(_extract_alias_terms_before_zhi(normalized))
    candidates.extend(_extract_parenthesized_definition_terms(normalized))
    return [term for term in (_normalize_term(term) for term in candidates) if _is_useful_dynamic_term(term)]


def _normalize_for_term_extraction(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([A-Za-z0-9])\s*-\s*([A-Za-z0-9])", r"\1-\2", text)
    return text.strip()


def _extract_alias_terms_before_zhi(text: str) -> List[str]:
    terms: List[str] = []
    for match in re.finditer(r"([^。；;\n]{1,48}?)\s+指(?:\s|的是)", text):
        raw = _clean_alias_candidate(match.group(1))
        terms.extend(_split_term_aliases(raw))
    return terms


def _clean_alias_candidate(raw: str) -> str:
    raw = re.sub(r"^.*?(释义项|常用词语释义)\s+", "", raw).strip()
    if "。" in raw:
        raw = raw.rsplit("。", 1)[-1].strip()
    tokens = [token for token in raw.split() if token]
    if len(tokens) <= 1:
        return raw
    two_part_suffixes = ("核", "转换器", "芯片", "工艺", "技术", "管理", "计量", "模块", "模组")
    if tokens[-1] in two_part_suffixes and re.search(r"[A-Za-z0-9/+.\-]", tokens[-2]):
        return f"{tokens[-2]} {tokens[-1]}"
    return tokens[-1]


def _extract_parenthesized_definition_terms(text: str) -> List[str]:
    terms: List[str] = []
    for match in re.finditer(
        r"([\u4e00-\u9fffA-Za-z0-9/+.\-\s]{2,30})[（(]\s*([A-Za-z][A-Za-z0-9/+.\-]{1,16})\s*[）)]\s*(?:指的是|是指)",
        text,
    ):
        chinese_name = match.group(1).strip(" 　、，（(")
        acronym = match.group(2)
        terms.extend((chinese_name, acronym))
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9/+.\-]{1,16})\b\s*(?:指的是|是指)", text):
        terms.append(match.group(1))
    return terms


def _split_term_aliases(raw: str) -> List[str]:
    raw = raw.strip(" 　：:")
    raw = re.sub(r"^[#>\d一二三四五六七八九十、（）()：:.-]+", "", raw)
    pieces = re.split(r"\s+[／/]\s+|、|,|，|或|及", raw)
    return [piece.strip(" 　：:（）()") for piece in pieces if piece.strip()]


def _normalize_term(term: str) -> str:
    term = re.sub(r"\s+", " ", term).strip(" 　：:，,。；;（）()")
    term = re.sub(r"\s*/\s*", "/", term)
    term = term.strip("/")
    return term


def _is_useful_dynamic_term(term: str) -> bool:
    if not term:
        return False
    compact = _compact_text(term)
    if len(compact) < 2 or len(compact) > 24:
        return False
    if compact in _GENERIC_GLOSSARY_TERMS:
        return False
    if any(token in compact for token in _GENERIC_GLOSSARY_SUBSTRINGS):
        return False
    if re.fullmatch(r"[\d年月日至.\-/]+", compact):
        return False
    if re.fullmatch(r"[A-Z]", compact):
        return False
    if re.fullmatch(r"[A-Z][A-Za-z0-9/+.\-]{1,16}", compact):
        return True
    if re.search(r"[A-Za-z]\d|\d[A-Za-z]", compact):
        return True
    return any(hint in compact for hint in _TECH_TERM_HINTS)


def _matched_dynamic_terms(snippet: str, dynamic_terms: Sequence[str]) -> Tuple[str, ...]:
    if not dynamic_terms:
        return ()
    compact_snippet = _compact_text(snippet)
    matched: List[str] = []
    for term in dynamic_terms:
        if term in snippet or _compact_text(term) in compact_snippet:
            matched.append(term)
    return tuple(matched)


def _merge_keywords(markers: Iterable[str], dynamic_terms: Sequence[str], excerpt: str) -> List[str]:
    keywords: List[str] = []
    seen: Set[str] = set()
    for keyword in list(markers) + list(dynamic_terms):
        if keyword in seen:
            continue
        if keyword in excerpt or _compact_text(keyword) in _compact_text(excerpt):
            seen.add(keyword)
            keywords.append(keyword)
    return keywords


def _build_card(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    card_type: str,
    card_index: int,
    source_block_id: str,
    source_block_text: str,
    excerpt: str,
    score: int,
    dynamic_terms: Sequence[str] = (),
) -> Dict[str, Any]:
    card_id = (
        f"periodic:{stock_code}:{report_year}:{report_type}:"
        f"narrative:{card_type}:{card_index}"
    )
    confidence = "medium_high" if score >= 2 else "medium"
    keywords = _merge_keywords(_CARD_TYPE_MARKERS.get(card_type, ()), dynamic_terms, excerpt)
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
        "source_excerpt_hash": _source_text_hash(excerpt),
        "source_block_hash": _source_text_hash(source_block_text or excerpt),
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
        group = _select_diverse_cards(typed_cards.get(card_type, []), max_cards_per_type)
        cards.extend(group)
        if len(cards) >= max_total_cards:
            break
    return cards[:max_total_cards]


def _select_diverse_cards(group: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    selected: List[Dict[str, Any]] = []
    selected_ids: Set[int] = set()
    seen_blocks: Set[str] = set()

    for index, card in enumerate(group):
        block_id = str(card.get("source_block_id") or "")
        if block_id in seen_blocks:
            continue
        selected.append(card)
        selected_ids.add(index)
        seen_blocks.add(block_id)
        if len(selected) >= limit:
            return selected

    for index, card in enumerate(group):
        if index in selected_ids:
            continue
        selected.append(card)
        if len(selected) >= limit:
            break
    return selected
