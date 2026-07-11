"""Build source-unit-owned annual narrative argument cards.

The producer is deliberately local and deterministic.  It turns the supplied
periodic-report blocks into canonical v2 cards without calling a model,
rewriting source text, or applying a business-card limit.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Iterable, Sequence

from annual_argument_schema import (
    CANONICAL_FAMILIES,
    CARD_SCHEMA_VERSION,
    ENVELOPE_SCHEMA_VERSION,
    FAMILY_LABELS,
    SELECTION_VERSION,
    validate_card_v2,
)


SOURCE_TYPE = "periodic_report_narrative_evidence"
SOURCE_CREDIT = 75

_USAGE_FALLBACKS = {
    "business_overview": "business_structure",
    "business_model": "business_structure",
    "product_capacity_profile": "business_structure",
    "sales_certification_model": "business_structure",
    "hk_business_overview": "business_structure",
    "hk_customer_ecosystem": "business_structure",
    "segment_table": "operating_progress",
    "production_sales_inventory_table": "operating_progress",
    "management_strategy": "operating_progress",
    "management_market_view": "market_competition_outlook",
    "industry_outlook": "market_competition_outlook",
    "market_demand_outlook": "market_competition_outlook",
    "competitive_position": "market_competition_outlook",
    "future_strategy": "market_competition_outlook",
    "hk_market_outlook": "market_competition_outlook",
    "rd_product_progress": "technology_product_progress",
    "rd_table": "technology_product_progress",
    "rd_investment_table": "technology_product_progress",
    "hk_product_progress": "technology_product_progress",
    "profitability_commentary": "financial_quality_explanation",
    "hk_financial_commentary": "financial_quality_explanation",
    "cash_flow_capex_table": "financial_quality_explanation",
    "asset_impairment_note": "financial_quality_explanation",
    "ar_aging_note": "financial_quality_explanation",
    "inventory_note": "financial_quality_explanation",
    "audit_key_matters": "financial_quality_explanation",
    "government_grant_note": "financial_quality_explanation",
    "financial_assets_note": "financial_quality_explanation",
    "goodwill_note": "financial_quality_explanation",
}

_FINANCIAL_METRICS = (
    "毛利率", "毛利", "净利率", "净利润", "营业收入", "营业利润", "营业成本",
    "营收", "现金流", "应收账款", "存货", "资产减值", "减值损失", "费用率",
    "期间费用", "利润总额", "每股收益", "坏账准备", "可变现净值",
    "毛利率", "毛利", "營收", "應收賬款", "存貨", "減值", "壞賬", "收入确认", "收入確認",
)
_CAUSAL_TOKENS = ("主要系", "由于", "由於", "所致", "受", "影响", "影響", "因此", "从而", "帶動", "带动")
_FINANCIAL_ACTIONS = ("计提", "計提", "减值", "減值", "确认收入", "確認收入", "坏账", "壞賬", "跌价", "跌價", "核销", "核銷")
_PROGRESS_TOKENS = (
    "认证", "認證", "验证", "驗證", "量产", "量產", "批量", "交付", "供货", "供貨",
    "导入", "導入", "定点", "定點", "搭载", "搭載", "发布", "發佈", "完成", "进入",
    "進入", "实现", "實現", "升级", "升級", "更新", "推出",
)
_TECH_TOKENS = ("芯片", "晶片", "SoC", "平台", "平台式", "算法", "算法", "工艺", "工藝", "IP核", "模型", "技术体系", "技術體系", "研发", "研發", "研发能力", "研發能力")
_OPERATING_TOKENS = ("报告期", "報告期", "本期", "本年度", "销量", "銷量", "产量", "產量", "产能", "產能", "订单", "訂單", "库存", "庫存", "收入", "出货", "出貨", "同比", "环比", "增長", "增长")
_MARKET_TOKENS = ("管理层", "管理層", "认为", "認為", "行业", "行業", "市场", "市場", "需求", "景气", "景氣", "竞争", "競爭", "份额", "份額", "战略", "戰略", "展望", "趋势", "趨勢", "国产替代", "產能過剩")
_BUSINESS_TOKENS = ("主营", "主營", "主要从事", "主要從事", "业务", "業務", "产品", "產品", "客户", "客戶", "应用", "應用", "供应商", "供應商", "解决方案", "解決方案", "服务", "服務", "产业链", "產業鏈")

_LLM_PHRASES = ("需要跟踪", "建议关注", "投资者应", "估值中枢", "配置价值")
_TABLE_TOKENS = ("项目 本期", "項目 本期", "单位：", "單位：", "期初余额", "期末余额", "期初餘額", "期末餘額", "序号", "序號", "金额", "金額", "比例", "占比")
_RISK_TOKENS = ("风险提示", "風險提示", "风险因素", "風險因素", "不确定性", "不確定性", "可能导致", "可能導致")
_POLICY_TOKENS = ("会计政策", "會計政策", "初始计量", "初始計量", "后续计量", "後續計量", "确认和计量", "確認和計量")

_MAX_ANCHORED_FACT_SCORE = 2
_MAX_SOURCE_UNIT_SCORE = 1
_COMPLETE_ARGUMENT_BONUS = 4


def build_periodic_report_narrative_evidence_cards(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    evidence_pack: dict,
    raw_text: str = "",
    max_cards_per_type: int | None = None,
    max_total_cards: int | None = None,
) -> dict:
    """Return uncapped, source-unit-owned canonical annual argument cards.

    The two historical limit parameters are retained as ignored call
    compatibility only; the canonical path never truncates admitted cards.
    """
    del raw_text, max_cards_per_type, max_total_cards
    blocks = evidence_pack.get("blocks") if isinstance(evidence_pack, dict) else []
    blocks = blocks or []
    diagnostics = _new_diagnostics()
    cards: list[dict] = []
    candidates: list[dict] = []
    seen_by_family: dict[str, list[dict]] = defaultdict(list)

    for block in blocks:
        if not isinstance(block, dict):
            _reject(diagnostics, "invalid_block")
            continue
        block_id = str(block.get("id") or "").strip()
        if not block_id:
            _reject(diagnostics, "missing_block_id")
            continue
        diagnostics["source_blocks_seen"] += 1
        cleaned, units = _materialize_source_units(block_id, str(block.get("text") or ""))
        diagnostics["source_units_seen"] += len(units)
        usage_hint = str(block.get("usage") or "").strip()

        prepared_units = []
        for unit in units:
            noise_reason = _noise_reason(unit["text"], source_block_text=cleaned)
            if noise_reason:
                _reject(diagnostics, noise_reason)
                prepared_units.append(None)
                continue
            signals = _family_signals(unit["text"])
            fallback = _usage_fallback_family(unit["text"], usage_hint)
            eligible_signals = [
                family
                for family in signals
                if _is_primary_eligible_signal(family, unit["text"], signals)
            ]
            if not eligible_signals and fallback is None:
                _reject(diagnostics, "no_family_signal")
                prepared_units.append(None)
                continue
            admission_families = eligible_signals or [fallback]
            if not any(
                _is_self_contained_atomic_fact(unit["text"], family)
                for family in admission_families
            ):
                _reject(diagnostics, "not_self_contained")
                prepared_units.append(None)
                continue
            diagnostics["usable_units"] += 1
            prepared_units.append((unit, signals))

        unit_index = 0
        while unit_index < len(prepared_units):
            prepared = prepared_units[unit_index]
            if prepared is None:
                unit_index += 1
                continue
            unit, bundle_signals = prepared
            bundle = [unit]
            next_index = unit_index + 1
            while next_index < len(prepared_units):
                following = prepared_units[next_index]
                if following is None:
                    break
                following_unit, following_signals = following
                if not _units_may_continue_same_argument(
                    bundle, bundle_signals, following_unit, following_signals,
                ):
                    break
                bundle.append(following_unit)
                bundle_signals = bundle_signals | following_signals
                next_index += 1

            source_excerpt = cleaned[bundle[0]["start_pos"]:bundle[-1]["end_pos"]]
            family, secondary_signals, selection_reason = resolve_argument_family(source_excerpt, usage_hint)
            if family is None:
                _reject(diagnostics, "no_family_signal")
                unit_index = next_index
                continue
            complete = _is_complete_argument(source_excerpt, family)
            candidate = _build_candidate(
                stock_code=stock_code,
                stock_name=stock_name,
                report_year=report_year,
                report_type=report_type,
                source_block_id=block_id,
                cleaned_block=cleaned,
                units=bundle,
                family=family,
                secondary_signals=secondary_signals,
                selection_reason=selection_reason,
                argument_complete=complete,
            )
            unit_index = next_index
            diagnostics["candidates_by_family"][family] += 1
            candidates.append(candidate)
            if _is_semantic_duplicate(candidate, seen_by_family[family]):
                _reject(diagnostics, "semantic_duplicate")
                continue
            errors = validate_card_v2(candidate)
            if errors:
                _reject(diagnostics, "invalid_candidate")
                continue
            seen_by_family[family].append(candidate)
            cards.append(candidate)
            diagnostics["admitted_by_family"][family] += 1
            diagnostics["argument_complete_counts"]["complete" if complete else "atomic"] += 1

    candidate_errors = _candidate_invariant_errors(candidates, diagnostics["usable_units"])
    admitted_errors = _candidate_invariant_errors(cards, diagnostics["usable_units"])
    invariant_errors = tuple(dict.fromkeys((*candidate_errors, *admitted_errors)))
    diagnostics["candidate_explosion"] = bool(invariant_errors)
    diagnostics["candidate_explosion_block_ids"] = _candidate_explosion_block_ids(candidates)
    diagnostics["admission_invariant_violation"] = bool(invariant_errors)
    if invariant_errors:
        diagnostics["invariant_errors"] = list(invariant_errors)
        cards = []
        diagnostics["admitted_by_family"] = _family_counter()
        diagnostics["argument_complete_counts"] = {"complete": 0, "atomic": 0}

    diagnostics["missing_families"] = [
        family for family in CANONICAL_FAMILIES if not diagnostics["admitted_by_family"][family]
    ]
    diagnostics["cards"] = [{
        "card_id": card["card_id"],
        "source_unit_ids": list(card["source_unit_ids"]),
        "fact_anchors": list(card["fact_anchors"]),
        "secondary_signals": list(card["secondary_signals"]),
        "score_parts": dict(card["score_parts"]),
        "selection_reason": card["selection_reason"],
    } for card in cards]
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "selection_version": SELECTION_VERSION,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_year": report_year,
        "report_type": report_type,
        "cards": cards,
        "candidate_cards": list(cards),
        "diagnostics": diagnostics,
    }


def _materialize_source_units(block_id: str, text: str) -> tuple[str, list[dict]]:
    """Normalize whitespace once and retain punctuation-preserving source offsets."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    units = []
    for ordinal, match in enumerate(re.finditer(r".+?(?:[。；;！？!?]|$)", cleaned)):
        value = match.group(0).strip()
        if not value:
            continue
        start = cleaned.find(value, match.start(), match.end())
        units.append({
            "unit_id": f"{block_id}:u{ordinal}",
            "block_id": block_id,
            "ordinal": ordinal,
            "start_pos": start,
            "end_pos": start + len(value),
            "text": value,
        })
    return cleaned, units


def resolve_argument_family(text: str, usage_hint: str = "") -> tuple[str | None, list[str], str]:
    """Resolve exactly one family using the locked precedence order."""
    signals = _family_signals(text)
    family = _primary_family(text, usage_hint, signals=signals)
    primary_signal = family is not None and _is_primary_eligible_signal(family, text, signals)
    reason = "signal" if primary_signal else ""
    if family and not primary_signal:
        signals.add(family)
        reason = "usage_hint"
    secondary = [item for item in _FAMILY_PRECEDENCE if item != family and item in signals]
    return family, secondary, f"{reason}:{family}" if family else "no_family"


_FAMILY_PRECEDENCE = (
    "financial_quality_explanation",
    "technology_product_progress",
    "operating_progress",
    "market_competition_outlook",
    "business_structure",
)


def _primary_family(text: str, usage_hint: str, *, signals: set[str] | None = None) -> str | None:
    resolved_signals = _family_signals(text) if signals is None else signals
    family = next(
        (
            item for item in _FAMILY_PRECEDENCE
            if _is_primary_eligible_signal(item, text, resolved_signals)
        ),
        None,
    )
    if family is not None:
        return family
    return _usage_fallback_family(text, usage_hint)


def _usage_fallback_family(text: str, usage_hint: str) -> str | None:
    fallback = _USAGE_FALLBACKS.get(usage_hint)
    if fallback == "technology_product_progress" and not _has_product_progress(text):
        return None
    return fallback if fallback and _has_atomic_anchor(text) else None


def _is_primary_eligible_signal(family: str, text: str, signals: set[str]) -> bool:
    if family not in signals:
        return False
    return family != "technology_product_progress" or _has_product_progress(text)


def _family_signals(text: str) -> set[str]:
    signals: set[str] = set()
    financial_hits = _matching_tokens(text, _FINANCIAL_METRICS)
    market_hits = _matching_tokens(text, _MARKET_TOKENS)
    if financial_hits and (
        _matching_tokens(text, _CAUSAL_TOKENS)
        or _matching_tokens(text, _FINANCIAL_ACTIONS)
        or (len(set(financial_hits)) >= 2 and _has_financial_change(text))
        or (not market_hits and _has_financial_change(text))
    ):
        signals.add("financial_quality_explanation")
    if _has_product_progress(text) or _has_technology_capability(text):
        signals.add("technology_product_progress")
    if _matching_tokens(text, _OPERATING_TOKENS) and _has_operating_change(text):
        signals.add("operating_progress")
    if _has_market_judgment(text):
        signals.add("market_competition_outlook")
    if _matching_tokens(text, _BUSINESS_TOKENS) and _has_company_or_business_context(text):
        signals.add("business_structure")
    return signals


def _build_candidate(
    *,
    stock_code: str,
    stock_name: str,
    report_year: int,
    report_type: str,
    source_block_id: str,
    cleaned_block: str,
    units: Sequence[dict],
    family: str,
    secondary_signals: Sequence[str],
    selection_reason: str,
    argument_complete: bool,
) -> dict:
    first, last = units[0], units[-1]
    excerpt = cleaned_block[first["start_pos"]:last["end_pos"]]
    anchors = _fact_anchors(excerpt, family)
    score_parts = {
        "anchored_fact": min(len(anchors), _MAX_ANCHORED_FACT_SCORE),
        "argument_complete": _COMPLETE_ARGUMENT_BONUS if argument_complete else 0,
        "source_unit_count": min(len(units), _MAX_SOURCE_UNIT_SCORE),
    }
    card_seed = "|".join((stock_code, str(report_year), report_type, source_block_id, *[unit["unit_id"] for unit in units]))
    return {
        "schema_version": CARD_SCHEMA_VERSION,
        "selection_version": SELECTION_VERSION,
        "card_id": f"annual-argument:{hashlib.sha256(card_seed.encode('utf-8')).hexdigest()[:20]}",
        "argument_family": family,
        "argument_complete": argument_complete,
        "title": FAMILY_LABELS[family],
        "source_block_id": source_block_id,
        "source_unit_ids": [unit["unit_id"] for unit in units],
        "source_units": [dict(unit) for unit in units],
        "source_excerpt": excerpt,
        "fact_anchors": anchors,
        "secondary_signals": list(secondary_signals),
        "score_parts": score_parts,
        "quality_score": sum(score_parts.values()),
        "selection_reason": selection_reason,
        "source_type": SOURCE_TYPE,
        "source_credit": SOURCE_CREDIT,
        "report_year": report_year,
        "report_type": report_type,
    }


def _candidate_invariant_errors(candidates: Sequence[dict], usable_unit_count: int) -> tuple[str, ...]:
    """Detect cardinality and source-unit ownership violations deterministically."""
    errors = []
    if len(candidates) > usable_unit_count:
        errors.append("candidate_count_exceeds_usable_units")
    source_unit_ids = [
        unit_id
        for candidate in candidates
        if isinstance(candidate, dict)
        for unit_id in candidate.get("source_unit_ids", [])
    ]
    if len(source_unit_ids) != len(set(source_unit_ids)):
        errors.append("reused_source_units")
    return tuple(errors)


def _new_diagnostics() -> dict:
    return {
        "source_blocks_seen": 0,
        "source_units_seen": 0,
        "usable_units": 0,
        "candidates_by_family": _family_counter(),
        "admitted_by_family": _family_counter(),
        "argument_complete_counts": {"complete": 0, "atomic": 0},
        "rejection_counts": {
            "incomplete": 0,
            "no_anchor": 0,
            "table_noise": 0,
            "ocr_damage": 0,
            "boilerplate": 0,
            "duplicate": 0,
            "reused_source_units": 0,
            "invalid_unit": 0,
        },
        "missing_families": [],
        "candidate_explosion": False,
        "candidate_explosion_block_ids": [],
        "admission_invariant_violation": False,
        "v1_adapter_use_count": 0,
        "cards": 0,
    }


def _family_counter() -> dict:
    return {family: 0 for family in CANONICAL_FAMILIES}


def _reject(diagnostics: dict, reason: str) -> None:
    counts = diagnostics["rejection_counts"]
    stable_reason = {
        "too_short": "invalid_unit",
        "invalid_block": "invalid_unit",
        "missing_block_id": "invalid_unit",
        "llm_phrase": "boilerplate",
        "risk_disclosure": "boilerplate",
        "checkbox_or_page_marker": "ocr_damage",
        "audit_or_policy": "boilerplate",
        "table_or_ocr": "table_noise",
        "definition_or_hash": "boilerplate",
        "no_family_signal": "no_anchor",
        "not_self_contained": "incomplete",
        "semantic_duplicate": "duplicate",
        "invalid_candidate": "invalid_unit",
    }.get(reason, reason)
    counts[stable_reason] = counts.get(stable_reason, 0) + 1


def _candidate_explosion_block_ids(candidates: Iterable[dict]) -> list[str]:
    candidates_by_block: Counter[str] = Counter(
        str(candidate.get("source_block_id") or "")
        for candidate in candidates if isinstance(candidate, dict)
    )
    units_by_block: Counter[str] = Counter(
        str(unit.get("block_id") or "")
        for candidate in candidates if isinstance(candidate, dict)
        for unit in candidate.get("source_units", []) if isinstance(unit, dict)
    )
    implicated = {
        block_id for block_id, candidate_count in candidates_by_block.items()
        if candidate_count > units_by_block[block_id]
    }
    blocks_by_unit_id: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        block_id = str(candidate.get("source_block_id") or "")
        for unit_id in candidate.get("source_unit_ids", []):
            if isinstance(unit_id, str):
                blocks_by_unit_id[unit_id].append(block_id)
    for blocks in blocks_by_unit_id.values():
        if len(blocks) > 1:
            implicated.update(blocks)
    return sorted(block_id for block_id in implicated if block_id)


def _noise_reason(text: str, *, source_block_text: str = "") -> str | None:
    compact = _compact_text(text)
    if len(compact) < 5:
        return "too_short"
    if _contains_llm_judgment(text):
        return "llm_phrase"
    if any(token in text for token in _RISK_TOKENS) or "风险" in text or "風險" in text:
        return "risk_disclosure"
    if _looks_like_checkbox_or_page_marker(text):
        return "checkbox_or_page_marker"
    if _looks_like_audit_or_policy(text):
        return "audit_or_policy"
    if _looks_like_table_fragment(text):
        return "table_or_ocr"
    if _looks_like_definition_or_hash_fragment(text):
        return "definition_or_hash"
    if _looks_like_structural_boilerplate(text):
        return "audit_or_policy"
    if source_block_text and _looks_like_block_table(source_block_text):
        return "table_or_ocr"
    if source_block_text and _looks_like_block_boilerplate(source_block_text):
        return "audit_or_policy"
    return None


def _looks_like_checkbox_or_page_marker(text: str) -> bool:
    compact = _compact_text(text)
    if any(mark in compact for mark in ("□", "", "☑", "■", "√")) and "适用" in compact:
        return True
    if compact.count("适用") >= 3 and "不适用" in compact:
        return True
    if "年度报告全文" in compact and (len(compact) < 100 or re.search(r"\d{1,4}/\d{1,4}", compact)):
        return True
    return bool(re.search(r"\d{1,4}\s*/\s*\d{1,4}", text))


def _looks_like_audit_or_policy(text: str) -> bool:
    compact = _compact_text(text)
    if any(token in text for token in _POLICY_TOKENS) and not any(token in text for token in _CAUSAL_TOKENS):
        return True
    audit_tokens = ("关键审计事项", "關鍵審計事項", "审计程序", "審計程序", "我们实施", "我們實施", "审计应对", "審計應對")
    if sum(token in compact for token in audit_tokens) >= 2:
        return True
    policy_patterns = ("成本法核算", "权益法核算", "權益法核算", "持有待售", "借款费用资本化", "借款費用資本化")
    return sum(token in compact for token in policy_patterns) >= 2


def _looks_like_table_fragment(text: str) -> bool:
    compact = _compact_text(text)
    if sum(token in compact for token in _TABLE_TOKENS) >= 3:
        return True
    if re.search(r"产品类型.*产品介绍.*应用领域", compact) or re.search(r"產品類型.*產品介紹.*應用領域", compact):
        return True
    numbers = re.findall(r"(?<![A-Za-z0-9])\d[\d,.]*(?![A-Za-z0-9])", text)
    narrative = _matching_tokens(text, _CAUSAL_TOKENS + _PROGRESS_TOKENS + _OPERATING_TOKENS)
    digit_ratio = sum(char.isdigit() for char in compact) / max(len(compact), 1)
    return (len(numbers) >= 6 or digit_ratio > 0.35) and not narrative


def _looks_like_definition_or_hash_fragment(text: str) -> bool:
    compact = _compact_text(text)
    if "释义项指释义内容" in compact or "釋義項指釋義內容" in compact:
        return True
    if re.search(r"^[^。；;]{1,45}(?:指的是|是指|\s指\s)", text):
        return True
    return bool(re.fullmatch(r"[0-9a-fA-F]{24,}", compact))


def _looks_like_structural_boilerplate(text: str) -> bool:
    """Reject report structure without relying on a family-specific marker."""
    compact = _compact_text(text)
    if "#" in text and text.count("#") >= 2:
        return True
    if "ESG" in text and any(token in compact for token in (
        "信息披露", "披露标准", "ESG实践", "ESG整體工作成果", "ESG整体工作成果",
        "ESG指导委员会", "ESG報告", "ESG报告", "合规治理",
    )):
        return True
    if "ESG" in text and "策略" in compact:
        return True
    operating_mode = ("生产模式", "生產模式", "营销及销售模式", "營銷及銷售模式", "按市场需求规划产能")
    if any(token in compact for token in operating_mode):
        return True
    barrier_tokens = (
        "从产业格局来看", "產業格局", "技术壁垒", "技術壁壘", "准入门槛", "准入門檻",
        "客户验证周期长", "客戶驗證周期長", "新进入者难以快速打开市场", "新進入者難以快速打開市場",
        "持续研发与人才壁垒", "持續研發與人才壁壘", "综合护城河", "綜合護城河",
        "行业需要跨学科复合型人才", "行業需要跨學科複合型人才",
    )
    if compact.startswith("从产业格局来看") or sum(token in compact for token in barrier_tokens) >= 2:
        return True
    procurement_tokens = ("采购模式", "採購模式", "供应商采购", "供應商採購", "供应商准入", "供應商准入", "供应商考核", "供應商考核", "供应商能力发展", "供應商能力發展", "供应商的导入与培养", "供應商的導入與培養")
    if sum(token in compact for token in procurement_tokens) >= 2:
        return True
    governance_tokens = ("现场结合通讯方式召开会议次数", "董事对公司有关事项提出异议", "董事会下设专门委员会", "审计委员会", "薪酬委员会", "提名委员会", "战略委员会")
    if sum(token in compact for token in governance_tokens) >= 2:
        return True
    importance_tokens = ("重要性标准确定方法", "项目重要性标准", "重要的应收账款坏账准备", "收回或转回金额")
    if sum(token in compact for token in importance_tokens) >= 2:
        return True
    personnel_tokens = ("研发人员的数量", "研发人员数量占公司总人数的比例", "研发人员学历结构", "学历结构类别", "研发人员年龄结构", "年龄结构类别")
    if sum(token in compact for token in personnel_tokens) >= 2:
        return True
    debt_tokens = ("本金額", "应付债券", "應付債券", "債券變動列示", "债券变动列示", "確認應付利息", "确认应付利息", "遞延收益", "递延收益", "交易成本", "償還", "偿还")
    if len(re.findall(r"-?\(?\d[\d,.]*\)?", text)) >= 4 and sum(token in compact for token in debt_tokens) >= 3:
        return True
    audit_tokens = (
        "关键审计事项是我们根据职业判断", "對財務報表整體進行審計", "对财务报表整体进行审计",
        "不对这些事项单独发表意见", "注册会计师对财务报表审计的责任", "包括与这些关键审计事项相关的责任",
        "审计程序中包括以下程序", "潛在減值相關的審計程序", "潜在减值相关的审计程序",
        "关键财务报告内部控制的设计和运行有效性", "关键假设进行敏感性分析", "执行敏感性分析",
        "我们获取了管理层聘请的外部评估师", "外部评估师的胜任能力", "内部估值专家协助",
        "将管理层在上一年度计算预计未来现金流量", "评价是否存在管理层偏向的迹象",
    )
    if sum(token in compact for token in audit_tokens) >= 2:
        return True
    policy_groups = (
        ("资产负债表日", "成本与可变现净值孰低", "差额计提", "估计售价", "估计的销售费用"),
        ("持有待售", "处置组", "商誉的账面价值", "按比例抵减", "转回金额计入当期损益"),
        ("资产减值损失转回", "会计处理", "后续资产负债表日", "减记的金额予以恢复"),
        ("商誉减值", "本公司至少每年测试商誉是否发生减值", "未来现金流量", "折现率"),
        ("存货跌价准备", "成本与可变现净值孰低", "鉴定存货减值要求管理层", "做出判断和估计"),
        ("确定存货的可变现净值", "确凿证据", "持有存货的目的", "资产负债表日后事项"),
        ("计提存货跌价准备后", "以前减记存货价值的影响因素已经消失", "予以转回", "转回的金额计入当期损益"),
        ("长期股权投资", "同一控制下的企业合并", "最终控制方", "调整资本公积", "调整留存收益"),
        ("非同一控制下企业合并", "可辨认资产", "负债及或有负债", "收购日", "合并成本", "确认为商誉"),
        ("成本法核算", "权益法核算", "金融工具确认和计量"),
        ("借款费用资本化", "确认原则", "符合资本化条件", "投资性房地产"),
        ("非上市股权投资的公允价值", "估值方法", "相关假设和估计", "公允价值发生重大变化"),
    )
    if any(sum(token in compact for token in group) >= 3 for group in policy_groups):
        return True
    if any(token in compact for token in (
        "符合资本化条件的资产", "资产减值损失金额内转回", "持有待售类别前的账面价值",
        "不再继续划分为持有待售类别", "按照《企业会计准则",
    )):
        return True
    catalog_tokens = ("政策目录", "主管部门", "相关政策内容", "国家发改委", "国家数据局", "中国证监会", "关于促进数据产业高质量发展的指导意见")
    if sum(token in compact for token in catalog_tokens) >= 2:
        return True
    if "年度报告全文" in compact and ("图" in compact[:80] or "资料来源" in compact[:120]):
        return True
    if "损失以" in compact and "填列" in compact and len(re.findall(r"-?\d[\d,.]*", text)) >= 2:
        return True
    if "主要为" in text and len(re.findall(r"-?\d[\d,.]*%?", text)) >= 2 and any(
        token in compact for token in ("信用减值损失", "公允价值变动损益", "资产减值损失", "资产处置收益", "投资收益")
    ):
        return True
    return any(text.lstrip().startswith(prefix) for prefix in (
        "优化等举措", "加速技术突破", "加速技術突破", "续研发", "續研發", "力、众多",
        "推动产品", "進一步提升", "进一步提升", "该段缺少前文主语", "該段缺少前文主語",
    ))


def _looks_like_block_boilerplate(text: str) -> bool:
    """Catch multi-sentence structural material that no single unit can prove."""
    compact = _compact_text(text)
    audit_procedure = (
        "关键审计事项是我们根据职业判断", "这些事项的应对以对财务报表整体进行审计",
        "不对这些事项单独发表意见", "注册会计师对财务报表审计的责任",
        "审计程序中包括以下程序", "基于所实施的审计程序", "关键财务报告内部控制的设计和运行有效性",
        "关键假设进行敏感性分析", "执行敏感性分析", "外部评估师的胜任能力",
        "内部估值专家协助", "评价是否存在管理层偏向的迹象",
    )
    if any(token in compact for token in audit_procedure):
        return True
    policy_fragments = (
        "存货跌价准备的确认标准和计提方法", "当其可变现净值低于成本时", "存货跌价准备通常按",
        "借款费用资本化的确认原则", "其他借款费用，在发生时", "符合资本化条件的资产",
        "商誉减值测试评估中采用的关键假设", "未来现金流量的现值", "税前折现率",
    )
    return any(token in compact for token in policy_fragments)


def _looks_like_block_table(text: str) -> bool:
    compact = _compact_text(text)
    if re.search(r"\.{3,}|…{2,}", text):
        return True
    table_headers = (
        "主要研发项目名称", "项目目的", "项目进展", "拟达到的目标", "预计对公司未来发展的影响",
        "营业收入", "营业成本", "毛利率", "销售量", "生产量", "库存量", "报告期投资额",
        "上年同期投资额", "变动幅度", "分产品", "产品类型", "产品介绍", "图片示例",
        "主要技术特点", "应用领域", "产品或终端样图",
    )
    return sum(token in compact for token in table_headers) >= 3


def _contains_llm_judgment(text: str) -> bool:
    if "这意味着" in text or "这说明" in text:
        return True
    return "需要跟踪" in text and not any(
        token in text for token in ("客户", "產品", "产品", "项目", "主机厂", "主機廠", "车型", "車型", "量产", "量產", "验证", "驗證")
    )


def _continues_same_argument(bundle: Sequence[dict], following: dict, family: str) -> bool:
    """Allow only adjacent source units that extend the same assertion."""
    previous_text = bundle[-1]["text"]
    following_text = following["text"]
    if previous_text.endswith(("；", ";")):
        return False
    if family == "market_competition_outlook":
        return _market_argument_continues(previous_text, following_text)
    if family == "technology_product_progress":
        previous_products = _named_products(previous_text)
        following_products = _named_products(following_text)
        return not (previous_products and following_products and previous_products != following_products)
    if family == "operating_progress":
        return not following_text.startswith(("报告期", "報告期", "本期", "本年度"))
    if family == "financial_quality_explanation":
        return bool(_matching_tokens(previous_text + following_text, _CAUSAL_TOKENS))
    return not following_text.startswith(("公司", "本公司", "集團", "集团"))


def _units_may_continue_same_argument(
    bundle: Sequence[dict],
    bundle_signals: set[str],
    following: dict,
    following_signals: set[str],
) -> bool:
    """Use compatible evidence signals for continuity without choosing a primary family."""
    for family in _FAMILY_PRECEDENCE:
        if family in bundle_signals & following_signals and _continues_same_argument(
            bundle, following, family,
        ):
            return True
    return False


def _market_argument_continues(previous_text: str, following_text: str) -> bool:
    compact_following = _compact_text(following_text).lstrip("，、:：")
    continuation_prefixes = (
        "其中", "同时", "同時", "此外", "并且", "並且", "但", "但是", "但是", "然而", "不过", "不過",
        "相较", "相較", "一方面", "另一方面", "受此", "在此基础上", "在此基礎上", "从而", "從而",
    )
    if compact_following.startswith(continuation_prefixes):
        return True
    return bool(_market_subject_tokens(previous_text) & _market_subject_tokens(following_text))


def _market_subject_tokens(text: str) -> set[str]:
    """Extract short, non-generic subject fragments for market argument continuity."""
    generic_characters = frozenset(
        "公司集团我們我们管理层層认为認為行业業市场場需求保持增长增長竞争競爭景气氣价格價承压壓"
        "产能產能规模模高端低端客户戶服务務供应應商未来來预计預計发展發展趋势勢影响響提升下降增加减少"
    )
    subjects = set()
    for phrase in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", _compact_text(text)):
        for size in range(2, min(len(phrase), 4) + 1):
            for index in range(len(phrase) - size + 1):
                token = phrase[index:index + size]
                if any(character not in generic_characters for character in token):
                    subjects.add(token)
    return subjects


def _is_self_contained_atomic_fact(text: str, family: str) -> bool:
    if len(_compact_text(text)) < 5:
        return False
    if family == "business_structure":
        return _has_company_or_business_context(text)
    if family == "technology_product_progress":
        return _has_product_progress(text) or bool(_matching_tokens(text, _TECH_TOKENS))
    if family == "operating_progress":
        return _has_operating_change(text)
    if family == "market_competition_outlook":
        return bool(_matching_tokens(text, _MARKET_TOKENS))
    return bool(_matching_tokens(text, _FINANCIAL_METRICS))


def _has_product_progress(text: str) -> bool:
    return bool(_named_products(text)) and bool(_matching_tokens(text, _PROGRESS_TOKENS))


def _named_products(text: str) -> set[str]:
    candidates = re.findall(
        r"(?:[A-Za-z]{1,}[0-9][A-Za-z0-9.\-]*|\d(?:\.\d)?T|[\u4e00-\u9fffA-Za-z0-9]+系列)",
        text,
    )
    return {
        candidate for candidate in candidates
        if len(candidate) > 2 or (candidate.startswith("M") and "模型" in text)
    }


def _has_operating_change(text: str) -> bool:
    change_tokens = ("增长", "增長", "下降", "提升", "增加", "减少", "減少", "实现", "實現", "交付", "出货", "出貨", "同比", "环比")
    operating_anchor = ("销量", "銷量", "产量", "產量", "产能", "產能", "订单", "訂單", "收入", "营收", "營收", "交付", "出货", "出貨", "库存", "庫存")
    has_report_period = bool(re.search(r"(?:报告期|報告期|本期|本年度|20\d{2}年)", text))
    return (
        has_report_period
        and bool(_matching_tokens(text, change_tokens))
        and bool(_matching_tokens(text, operating_anchor))
    )


def _has_technology_capability(text: str) -> bool:
    capability_tokens = (
        "研发中心", "研發中心", "研发平台", "研發平台", "平台建设", "平台建設", "核心技术体系", "核心技術體系",
        "工艺研发和创新能力", "工藝研發和創新能力", "研发资源", "研發資源", "多年集成电路研发实践", "多年集成電路研發實踐",
        "核心管理团队", "核心管理團隊", "骨干研发队伍", "骨幹研發隊伍", "导入验证到稳定量产", "導入驗證到穩定量產",
    )
    return sum(token in text for token in capability_tokens) >= 2


def _has_market_judgment(text: str) -> bool:
    judgment_tokens = (
        "管理层", "管理層", "认为", "認為", "行业", "行業", "竞争", "競爭", "景气", "景氣",
        "市场份额", "市場份額", "展望", "趋势", "趨勢", "预计", "預計", "市场规模", "市場規模",
        "产能过剩", "產能過剩", "战略", "戰略", "未来", "未來", "市场机遇", "市場機遇",
    )
    return bool(_matching_tokens(text, judgment_tokens))


def _has_financial_change(text: str) -> bool:
    return bool(_matching_tokens(text, ("同比", "环比", "提升", "下降", "增加", "减少", "變動", "保持稳定", "保持穩定", "为", "為")))


def _has_company_or_business_context(text: str) -> bool:
    return any(token in text for token in ("公司", "本公司", "集团", "集團", "我们", "我們", "主营", "主營", "业务", "業務"))


def _has_atomic_anchor(text: str) -> bool:
    return bool(_fact_anchors(text, "business_structure"))


def _is_complete_argument(text: str, family: str) -> bool:
    anchors = _fact_anchors(text, family)
    has_relation = bool(_matching_tokens(text, _CAUSAL_TOKENS))
    if family == "financial_quality_explanation":
        return has_relation and len(anchors) >= 2
    if family == "technology_product_progress":
        return has_relation and len(anchors) >= 2
    return has_relation and len(anchors) >= 3


def _fact_anchors(text: str, family: str) -> list[str]:
    anchors = []
    for value in re.findall(r"(?:20\d{2}年?|\d+(?:\.\d+)?%|[A-Za-z]{1,}[0-9][A-Za-z0-9.\-]*|\d(?:\.\d)?T)", text):
        anchors.append(value)
    family_tokens = {
        "business_structure": _BUSINESS_TOKENS,
        "operating_progress": _OPERATING_TOKENS,
        "market_competition_outlook": _MARKET_TOKENS,
        "technology_product_progress": _TECH_TOKENS + _PROGRESS_TOKENS,
        "financial_quality_explanation": _FINANCIAL_METRICS + _CAUSAL_TOKENS,
    }[family]
    anchors.extend(_matching_tokens(text, family_tokens)[:3])
    if not anchors:
        anchors.append(text[: min(len(text), 24)])
    return _unique(anchors)


def _is_semantic_duplicate(candidate: dict, admitted: Sequence[dict]) -> bool:
    for existing in admitted:
        if candidate["source_excerpt"] == existing["source_excerpt"]:
            return True
        if _distinct_product_or_period(candidate["source_excerpt"], existing["source_excerpt"]):
            continue
        if _ngram_similarity(candidate["source_excerpt"], existing["source_excerpt"]) >= 0.72:
            return True
    return False


def _distinct_product_or_period(left: str, right: str) -> bool:
    left_entities = set(re.findall(r"(?:20\d{2}|[A-Za-z]{1,}[0-9][A-Za-z0-9.\-]*|\d(?:\.\d)?T)", left))
    right_entities = set(re.findall(r"(?:20\d{2}|[A-Za-z]{1,}[0-9][A-Za-z0-9.\-]*|\d(?:\.\d)?T)", right))
    return bool(left_entities and right_entities and left_entities != right_entities)


def _ngram_similarity(left: str, right: str, size: int = 3) -> float:
    left_grams = _char_ngrams(_compact_text(left), size)
    right_grams = _char_ngrams(_compact_text(right), size)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def _char_ngrams(value: str, size: int) -> set[str]:
    if len(value) <= size:
        return {value} if value else set()
    return {value[index:index + size] for index in range(len(value) - size + 1)}


def _matching_tokens(text: str, tokens: Sequence[str]) -> list[str]:
    return [token for token in tokens if token in text]


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)
