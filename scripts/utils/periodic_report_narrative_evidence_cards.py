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

if __package__:
    from .annual_argument_schema import (
        annual_source_tail, CANONICAL_FAMILIES, CARD_SCHEMA_VERSION,
        ENVELOPE_SCHEMA_VERSION, FAMILY_LABELS, SELECTION_VERSION,
        SOURCE_UNIT_DECISIONS_VERSION,
        canonical_family_for_usage, has_concrete_annual_anchor,
        normalize_annual_source_text, validate_card_v2,
    )
    from .periodic_report_coverage_manifest import finalize_periodic_report_coverage_manifest
else:
    from annual_argument_schema import (
        annual_source_tail, CANONICAL_FAMILIES, CARD_SCHEMA_VERSION,
        ENVELOPE_SCHEMA_VERSION, FAMILY_LABELS, SELECTION_VERSION,
        SOURCE_UNIT_DECISIONS_VERSION,
        canonical_family_for_usage, has_concrete_annual_anchor,
        normalize_annual_source_text, validate_card_v2,
    )
    from periodic_report_coverage_manifest import finalize_periodic_report_coverage_manifest


SOURCE_TYPE = "periodic_report_narrative_evidence"
SOURCE_CREDIT = 75

_FINANCIAL_METRICS = (
    "毛利率", "毛利", "净利率", "净利润", "营业收入", "营业利润", "营业成本", "其他收益",
    "营收", "现金流", "应收账款", "存货", "资产减值", "减值损失", "费用率",
    "期间费用", "利润总额", "每股收益", "坏账准备", "可变现净值",
    "销售费用", "管理费用", "财务费用", "研发费用", "商誉", "商譽",
    "毛利率", "毛利", "營收", "應收賬款", "存貨", "減值", "壞賬", "收入确认", "收入確認",
)
_CAUSAL_TOKENS = ("主要系", "主要因", "由于", "由於", "所致", "受", "影响", "影響", "因此", "从而", "帶動", "带动", "随着", "隨著", "进而", "進而")
_FINANCIAL_ACTIONS = ("计提", "計提", "减值", "減值", "确认收入", "確認收入", "坏账", "壞賬", "跌价", "跌價", "核销", "核銷")
_PROGRESS_TOKENS = (
    "认证", "認證", "验证", "驗證", "量产", "量產", "批量", "交付", "供货", "供貨",
    "导入", "導入", "定点", "定點", "搭载", "搭載", "发布", "發佈", "完成", "进入",
    "進入", "实现", "實現", "升级", "升級", "更新", "推出", "突破", "合作",
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
    document_style = str(evidence_pack.get("document_style", "unknown")) if isinstance(evidence_pack, dict) else "unknown"
    diagnostics = _new_diagnostics()
    decisions_by_unit: dict[str, dict] = {}
    cards: list[dict] = []
    candidates: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            _reject(diagnostics, "invalid_block")
            continue
        block_id = str(block.get("id") or "").strip()
        if not block_id:
            _reject(diagnostics, "missing_block_id")
            continue
        diagnostics["source_blocks_seen"] += 1
        block_text = str(block.get("text") or "")
        cleaned, units = _materialize_source_units(block_id, block_text)
        diagnostics["source_units_seen"] += len(units)
        usage_hint = str(block.get("usage") or "").strip()

        prepared_units = []
        for unit in units:
            replacement = _extract_source_tail(
                unit, usage_hint, document_style, cleaned
            )
            if replacement is not None:
                unit = replacement
            decision = _new_source_unit_decision(unit)
            diagnostics["source_unit_decisions"].append(decision)
            decisions_by_unit[unit["unit_id"]] = decision
            noise_reason = _noise_reason(
                unit["text"], source_block_text=block_text, usage_hint=usage_hint
            )
            if noise_reason:
                _reject(diagnostics, noise_reason)
                decision["reason"] = _archive_safe_noise_reason(unit["text"]) or noise_reason
                prepared_units.append(None)
                continue
            signals = _family_signals(unit["text"])
            family = _primary_family(
                unit["text"], usage_hint, signals=signals, document_style=document_style
            )
            if family is None and has_concrete_annual_anchor(
                unit["text"]
            ) and not _has_technology_capability(unit["text"]):
                family = canonical_family_for_usage(usage_hint)
            if family is None:
                rejection_reason = (
                    "no_anchor"
                    if canonical_family_for_usage(usage_hint) == "technology_product_progress"
                    else "no_family_signal"
                )
                _reject(
                    diagnostics,
                    rejection_reason,
                )
                decision["reason"] = rejection_reason
                prepared_units.append(None)
                continue
            if _is_self_contained_atomic_fact(
                unit["text"], family, document_style=document_style, usage_hint=usage_hint
            ):
                state = "seed"
            elif has_concrete_annual_anchor(unit["text"]) or (
                family == "market_competition_outlook"
                and _market_argument_continues("", unit["text"])
            ):
                state = "continuation"
            else:
                _reject(diagnostics, "not_self_contained")
                decision["reason"] = "not_self_contained"
                prepared_units.append(None)
                continue
            diagnostics["usable_units"] += 1
            prepared_units.append((unit, family, state))

        unit_index = 0
        while unit_index < len(prepared_units):
            prepared = prepared_units[unit_index]
            if prepared is None:
                unit_index += 1
                continue
            unit, family, state = prepared
            if state != "seed":
                _reject(diagnostics, "not_self_contained")
                unit_index += 1
                continue
            bundle = [unit]
            next_index = unit_index + 1
            while next_index < len(prepared_units):
                following = prepared_units[next_index]
                if following is None:
                    break
                following_unit, following_family, following_state = following
                if not _continues_same_argument(
                    bundle, following_unit, family, following_family, following_state
                ):
                    break
                bundle.append(following_unit)
                next_index += 1

            source_excerpt = cleaned[bundle[0]["start_pos"]:bundle[-1]["end_pos"]]
            family, secondary_signals, selection_reason = resolve_argument_family(
                source_excerpt, usage_hint
            )
            if (
                canonical_family_for_usage(usage_hint) == "business_structure"
                and _is_hk_implicit_subject(source_excerpt, document_style, usage_hint)
            ):
                family = "business_structure"
                secondary_signals = [
                    item for item in _FAMILY_PRECEDENCE
                    if item != family and item in _family_signals(source_excerpt)
                ]
                selection_reason = "usage_primary:business_structure"
            if family is None:
                _reject(diagnostics, "no_family_signal")
                _mark_unit_decisions(decisions_by_unit, bundle, "no_family_signal")
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
            errors = validate_card_v2(candidate)
            if errors:
                _reject(diagnostics, "invalid_candidate")
                _mark_unit_decisions(decisions_by_unit, bundle, "invalid_candidate")
                continue
            cards.append(candidate)
            _mark_unit_decisions(decisions_by_unit, bundle, "selected", candidate["card_id"])
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
        for decision in diagnostics["source_unit_decisions"]:
            if decision["disposition"] == "selected":
                decision.update(disposition="rejected", reason="admission_invariant_violation",
                                selected_by_card_ids=[])

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
    diagnostics["coverage_manifest"] = finalize_periodic_report_coverage_manifest(
        evidence_pack.get("coverage_manifest") if isinstance(evidence_pack, dict) else None,
        source_unit_decisions=diagnostics["source_unit_decisions"], cards=cards,
        report_type=report_type, document_style=document_style)
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
    """Normalize whitespace and split complete source sentences in source order."""
    cleaned = normalize_annual_source_text(text)
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
    financial_override = family == "financial_quality_explanation" and _is_strong_financial_explanation(text)
    mapped_family = canonical_family_for_usage(usage_hint)
    reason = (
        "financial_override" if financial_override
        else "usage_primary" if mapped_family
        else "signal_primary"
    )
    if family and family not in signals:
        signals.add(family)
    secondary = [item for item in _FAMILY_PRECEDENCE if item != family and item in signals]
    return family, secondary, f"{reason}:{family}" if family else "no_family"


_FAMILY_PRECEDENCE = (
    "financial_quality_explanation",
    "technology_product_progress",
    "operating_progress",
    "market_competition_outlook",
    "business_structure",
)


def _primary_family(
    text: str, usage_hint: str, *, signals: set[str] | None = None,
    document_style: str = "unknown",
) -> str | None:
    resolved_signals = _family_signals(text) if signals is None else signals
    if _is_strong_financial_explanation(text) and _has_concrete_financial_fact(text):
        if _looks_like_risk_text(text) and not _is_concrete_risk_fact(
            text, "financial_quality_explanation", usage_hint
        ):
            pass
        else:
            return "financial_quality_explanation"
    mapped_family = canonical_family_for_usage(usage_hint)
    if mapped_family == "business_structure" and _is_hk_implicit_subject(
        text, document_style, usage_hint
    ):
        return mapped_family
    if mapped_family and _mapped_family_has_seed_signal(
        text, mapped_family, usage_hint=usage_hint
    ):
        return mapped_family
    if mapped_family == "operating_progress" and _has_concrete_business_fact(text):
        return "business_structure"
    if (
        mapped_family == "market_competition_outlook"
        and _market_argument_continues("", text)
        and not resolved_signals & {
            "technology_product_progress", "financial_quality_explanation",
            "operating_progress",
        }
    ):
        return mapped_family
    if mapped_family == "technology_product_progress" and has_concrete_annual_anchor(text):
        contextual = bool(re.match(r"^(?:该|本|相关|相關)(?:产品|產品)", text))
        if not _has_technology_capability(text) and (
            contextual or not (resolved_signals - {"technology_product_progress"})
        ):
            return mapped_family
    family = next(
        (
            item
            for item in _FAMILY_PRECEDENCE
            if item in resolved_signals
            and (
                item != "technology_product_progress"
                or _has_concrete_technology_fact(text, usage_hint)
            )
        ),
        None,
    )
    if family is not None:
        return family
    fallback = canonical_family_for_usage(usage_hint)
    if fallback == "technology_product_progress" and not _has_concrete_technology_fact(
        text, usage_hint
    ):
        return None
    return fallback if fallback and has_concrete_annual_anchor(text) else None


def _mapped_family_has_seed_signal(text: str, family: str, *, usage_hint: str) -> bool:
    if family == "technology_product_progress":
        return _has_concrete_technology_fact(text, usage_hint)
    checks = {
        "business_structure": _has_concrete_business_fact(text),
        "operating_progress": _has_operating_change(text),
        "market_competition_outlook": _has_concrete_market_fact(text),
        "financial_quality_explanation": _has_concrete_financial_fact(text),
    }
    return bool(checks.get(family))

def _extract_source_tail(
    unit: dict, usage_hint: str, document_style: str, cleaned_block: str
) -> dict | None:
    family = canonical_family_for_usage(usage_hint)
    if document_style != "a_share_annual" or family is None:
        return None
    tail = annual_source_tail(unit["text"]) or _embedded_annual_narrative_tail(
        unit["text"]
    )
    if not tail or _noise_reason(
        tail, source_block_text=tail, usage_hint=usage_hint
    ):
        return None
    start = cleaned_block.find(tail, unit["start_pos"], unit["end_pos"])
    return None if start < 0 else {**unit, "start_pos": start, "end_pos": start + len(tail), "text": tail}


def _embedded_annual_narrative_tail(text: str) -> str | None:
    if _looks_like_table_fragment(text) or _looks_like_block_table(text):
        narrative_starts = list(re.finditer(
            r"(?:依托|依託|基于|基於|凭借|憑藉)(?:于|於)?(?:本公司|公司|集团|集團)", text
        ))
        tail = text[narrative_starts[-1].start():].strip() if narrative_starts else ""
    else:
        return None
    return tail if tail.endswith(("。", "；", ";", "！", "？", "!", "?")) else None


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
    if _has_concrete_technology_fact(text) or _has_technology_capability(text):
        signals.add("technology_product_progress")
    if _matching_tokens(text, _OPERATING_TOKENS) and _has_operating_change(text):
        signals.add("operating_progress")
    has_product_app = _has_named_product_application_relation(text)
    if _has_company_or_business_context(text) and _matching_tokens(text, _BUSINESS_TOKENS) or has_product_app:
        signals.add("business_structure")
    if _has_market_judgment(text) and not has_product_app:
        signals.add("market_competition_outlook")
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
        "source_unit_decisions_version": SOURCE_UNIT_DECISIONS_VERSION,
        "source_unit_decisions": [],
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
        "invalid_candidate": "invalid_unit",
    }.get(reason, reason)
    counts[stable_reason] = counts.get(stable_reason, 0) + 1


def _new_source_unit_decision(unit: dict) -> dict:
    return {
        "source_block_id": str(unit.get("block_id") or ""),
        "source_unit_id": str(unit.get("unit_id") or ""),
        "source_text_hash": hashlib.sha256(normalize_annual_source_text(
            unit.get("text")).encode("utf-8")).hexdigest(),
        "source_order": int(unit.get("ordinal") or 0),
        "disposition": "rejected",
        "reason": "not_self_contained",
        "selected_by_card_ids": [],
    }


def _mark_unit_decisions(decisions: dict[str, dict], units: Sequence[dict], reason: str, card_id: str = "") -> None:
    for unit in units:
        decision = decisions[unit["unit_id"]]
        decision["reason"] = reason
        if card_id:
            decision.update(disposition="selected", selected_by_card_ids=[card_id])


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


def _noise_reason(
    text: str, *, source_block_text: str = "", usage_hint: str = ""
) -> str | None:
    compact = _compact_text(text)
    if len(compact) < 5:
        return "too_short"
    if _contains_llm_judgment(text):
        return "llm_phrase"
    if _looks_like_structural_unit(text):
        return "audit_or_policy"
    if _looks_like_checkbox_or_page_marker(text):
        return "checkbox_or_page_marker"
    if _looks_like_audit_or_policy(text):
        return "audit_or_policy"
    rd_narrative = _has_concrete_technology_fact(text, usage_hint)
    if _looks_like_table_fragment(text) and not rd_narrative:
        return "table_or_ocr"
    if _looks_like_definition_or_hash_fragment(text):
        return "definition_or_hash"
    if (
        source_block_text
        and _looks_like_industry_barrier_block(source_block_text)
        and not (
            _has_company_position_fact(text)
            or rd_narrative and _matching_tokens(text, _PROGRESS_TOKENS)
        )
    ):
        return "audit_or_policy"
    if _looks_like_structural_boilerplate(text):
        return "audit_or_policy"
    if usage_hint in {"rd_product_progress", "rd_table", "rd_investment_table"} and source_block_text:
        if _looks_like_interleaved_rd_table(source_block_text):
            return "table_or_ocr"
    mixed_narrative_table = usage_hint in {"rd_investment_table", "profitability_commentary"}
    if (
        source_block_text and not mixed_narrative_table
        and _looks_like_block_table(source_block_text)
        and (_looks_like_table_fragment(text) or _looks_like_block_table(text))
    ):
        return "table_or_ocr"
    if source_block_text and not mixed_narrative_table and _looks_like_block_boilerplate(source_block_text):
        return "audit_or_policy"
    return None


def _looks_like_structural_unit(text: str) -> bool:
    return _direct_structural_unit_reason(text) is not None


def _direct_structural_unit_reason(text: str) -> str | None:
    compact = _compact_text(text)
    tokens = ("分行业", "分產品", "分产品", "分地区", "分地區", "分销售模式", "分銷售模式")
    label = re.split(r"情况|說明|说明", compact, maxsplit=1)[0]
    section_label = bool(re.match(r"^(?:\(\d+\)\.?)?主营业务分", compact)) and len(label) < len(compact) and sum(token in label for token in tokens) >= 2
    regulation = compact.startswith(("公司需遵守", "本公司需遵守")) and any(token in compact for token in ("自律监管指引", "自律監管指引", "行业信息披露", "行業信息披露", "披露要求"))
    return "section_label" if section_label else "regulatory_disclosure" if regulation else None


def _looks_like_industry_barrier_block(text: str) -> bool:
    compact = _compact_text(text)
    barrier_tokens = (
        "技术壁垒", "技術壁壘", "准入门槛", "准入門檻", "客户验证周期长", "客戶驗證周期長",
        "新进入者难以快速打开市场", "新進入者難以快速打開市場", "持续研发与人才壁垒",
        "持續研發與人才壁壘", "综合护城河", "綜合護城河", "行业需要跨学科复合型人才",
        "行業需要跨學科複合型人才", "竞争焦点集中", "競爭焦點集中", "竞争格局集中", "競爭格局集中",
    )
    return sum(token in compact for token in barrier_tokens) >= 2


def _has_company_position_fact(text: str) -> bool:
    return bool(re.search(
        r"(?:公司|本公司|集团|集團).{0,100}(?:客户需求|客戶需求|技术积累|技術積累|"
        r"国产化|國產化|国产替代|國產替代|市场份额|市場份額|行业地位|行業地位)",
        _compact_text(text),
    ))


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
    return _direct_audit_policy_reason(text) is not None


def _direct_audit_policy_reason(text: str) -> str | None:
    compact = _compact_text(text)
    if any(token in text for token in _POLICY_TOKENS) and not any(token in text for token in _CAUSAL_TOKENS):
        return "accounting_policy_definition"
    audit_tokens = ("关键审计事项", "關鍵審計事項", "审计程序", "審計程序", "我们实施", "我們實施", "审计应对", "審計應對")
    if sum(token in compact for token in audit_tokens) >= 2:
        return "audit_procedure"
    policy_patterns = ("成本法核算", "权益法核算", "權益法核算", "持有待售", "借款费用资本化", "借款費用資本化")
    return "accounting_policy_definition" if sum(token in compact for token in policy_patterns) >= 2 else None


def _archive_safe_noise_reason(text: str) -> str | None:
    return (_direct_structural_unit_reason(text)
            or ("checkbox_or_page_marker" if _looks_like_checkbox_or_page_marker(text) else None)
            or _direct_audit_policy_reason(text)
            or ("definition_or_hash" if _looks_like_definition_or_hash_fragment(text) else None))


def _looks_like_table_fragment(text: str) -> bool:
    compact = _compact_text(text)
    if _is_complete_financial_comparison(text):
        return False
    if sum(token in compact for token in _TABLE_TOKENS) >= 3:
        return True
    if re.search(r"产品类型.*产品介绍.*应用领域", compact) or re.search(r"產品類型.*產品介紹.*應用領域", compact):
        return True
    if sum(token in compact for token in ("项目", "进展", "预计目标", "研发投入")) >= 3 and len(re.findall(r"\d", text)) >= 2:
        return True
    numbers = re.findall(r"(?<![A-Za-z0-9])\d[\d,.]*(?![A-Za-z0-9])", text)
    narrative = _matching_tokens(text, _CAUSAL_TOKENS + _PROGRESS_TOKENS + _OPERATING_TOKENS)
    digit_ratio = sum(char.isdigit() for char in compact) / max(len(compact), 1)
    return (len(numbers) >= 6 or digit_ratio > 0.35) and not narrative


def _is_complete_financial_comparison(text: str) -> bool:
    return bool(
        _matching_tokens(text, _FINANCIAL_METRICS)
        and len(re.findall(r"\d+(?:[,.]\d+)?%?", text)) >= 2
        and _matching_tokens(text, ("同比", "环比", "较上期", "较上年", "增加", "减少", "提升", "下降", "变动", "變動", "保持稳定", "保持穩定", "保持相对稳定", "保持相對穩定", "分别为", "分別為"))
    )


def _looks_like_interleaved_rd_table(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    seams = len(re.findall(r"[一-鿿]\s+[一-鿿]", text))
    compact_length = max(len(_compact_text(text)), 1)
    has_subject = bool(re.search(r"(?:公司|本公司|报告期|報告期|[A-Za-z]{1,}[0-9][A-Za-z0-9.\-]*)[^。；;！？!?]{0,40}(?:研发|研發|量产|量產|交付|验证|驗證|生产|生產)", _compact_text(text)))
    return len(lines) >= 2 and seams >= 4 and seams / compact_length > 0.05 and not has_subject


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
    operating_mode = ("营销及销售模式", "營銷及銷售模式", "按市场需求规划产能")
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
    if any(token in compact for token in ("债券变动列示", "債券變動列示")) and len(
        re.findall(r"-?\(?\d[\d,.]*\)?", text)
    ) >= 2:
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


def _continues_same_argument(
    bundle: Sequence[dict], following: dict, family: str,
    following_family: str, following_state: str,
) -> bool:
    """Return whether the next unit extends, rather than restarts, the argument."""
    if following_family != family:
        return False
    previous_text = bundle[-1]["text"]
    following_text = following["text"]
    if family == "financial_quality_explanation":
        extends = _financial_argument_continues(previous_text, following_text)
    elif previous_text.endswith(("；", ";")):
        extends = False
    elif family == "market_competition_outlook":
        extends = _market_argument_continues(previous_text, following_text)
    elif family == "technology_product_progress":
        previous_products = _named_products(previous_text)
        following_products = _named_products(following_text)
        extends = not (
            previous_products and following_products
            and previous_products != following_products
        )
    elif family == "operating_progress":
        extends = not following_text.startswith(("报告期", "報告期", "本期", "本年度"))
    else:
        extends = not bool(re.match(
            r"^(?:(?:报告期内|報告期內|本年度|本期)[，,]?)?(?:公司|本公司|集團|集团)",
            _compact_text(following_text),
        ))
    if not extends or following_state != "seed":
        return extends
    if family == "market_competition_outlook" and _market_argument_continues("", following_text):
        return True
    following_subjects = _bundle_subject_tokens((following,), family)
    new_subjects = following_subjects - _bundle_subject_tokens(bundle, family)
    if family == "technology_product_progress":
        return not new_subjects
    if family == "financial_quality_explanation":
        return _financial_argument_continues(previous_text, following_text) or not (
            _is_strong_financial_explanation(following_text) and new_subjects
        )
    if family == "operating_progress":
        return not (
            following_text.startswith(("报告期", "報告期", "本期", "本年度"))
            and new_subjects
        )
    return not new_subjects


def _bundle_subject_tokens(units: Sequence[dict], family: str) -> set[str]:
    text = "".join(unit["text"] for unit in units)
    if family == "technology_product_progress":
        subjects = _named_products(text)
        if subjects:
            subjects.add("product_portfolio")
        groups = (("product_portfolio", ("新产品", "新產品", "产品", "產品", "推出", "专利", "專利", "研发项目", "研發項目", "自主知识产权", "自主知識產權")), ("rd_spend", ("研发费用", "研發費用", "研发投入", "研發投入", "研发支出", "研發支出", "占营业收入", "占營業收入", "占收入")), ("rd_staff", ("研发人员", "研發人員", "技术人员", "技術人員", "人才队伍", "人才隊伍", "招贤纳士", "招賢納士")))
        subjects.update(label for label, tokens in groups if any(token in text for token in tokens))
        return subjects
    if family in {"business_structure", "market_competition_outlook"}:
        return _named_products(text) | set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}(?:行业|行業|市场|市場|客户|客戶|战略|戰略)", text))
    return set(_matching_tokens(text, _FINANCIAL_METRICS if family == "financial_quality_explanation" else _OPERATING_TOKENS))


def _market_argument_continues(previous_text: str, following_text: str) -> bool:
    compact_following = _compact_text(following_text).lstrip("，、:：")
    continuation_prefixes = (
        "其中", "同时", "同時", "此外", "并且", "並且", "但", "但是", "然而", "不过", "不過",
        "相较", "相較", "一方面", "另一方面", "受此", "在此基础上", "在此基礎上", "从而", "從而",
        "面对这一风险", "面对风险", "针对这一风险", "为应对",
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


def _is_self_contained_atomic_fact(
    text: str, family: str, *, document_style: str = "unknown", usage_hint: str = ""
) -> bool:
    if len(_compact_text(text)) < 5:
        return False
    if _looks_like_audit_or_policy(text) or _looks_like_structural_boilerplate(text):
        return False
    if _looks_like_risk_text(text) and not _is_concrete_risk_fact(text, family, usage_hint):
        return False
    if family == "business_structure":
        return (
            _has_concrete_business_fact(text)
            or usage_hint in {"business_model", "hk_business_overview"}
            and "模式" in text and bool(re.search(r"[A-Za-z]+[0-9][A-Za-z0-9.\-]*", text))
            or _is_hk_implicit_subject(text, document_style, usage_hint)
        )
    if family == "technology_product_progress":
        return _has_concrete_technology_fact(text, usage_hint)
    if family == "operating_progress":
        return _has_operating_change(text)
    if family == "market_competition_outlook":
        base = _has_concrete_market_fact(text) or _has_market_judgment(text) and has_concrete_annual_anchor(text) or (
            document_style == "hkex_annual"
            and usage_hint == "hk_market_outlook"
            and _has_company_or_business_context(text)
            and _has_market_judgment(text)
        )
    elif family == "financial_quality_explanation":
        base = _has_concrete_financial_fact(text)
    else:
        return False
    return base


def _is_hk_implicit_subject(text: str, document_style: str, usage_hint: str) -> bool:
    return (
        document_style == "hkex_annual"
        and usage_hint in {"hk_business_overview", "hk_customer_ecosystem", "hk_product_progress"}
        and bool(re.search(r"[A-Za-z][A-Za-z0-9]{2,}|[一-鿿A-Za-z0-9]+(?:平台|產品|产品|解決方案|解决方案|生態|生态|系統|系统|方案)", text))
        and any(token in text for token in ("提供", "為", "为", "發佈", "发布", "驗證", "验证", "量產", "量产", "客戶", "客户", "市場", "市场", "應用", "应用", "部署", "適配", "适配", "服務", "服务", "導入", "导入", "定點", "定点"))
    )


def _has_concrete_business_fact(text: str) -> bool:
    compact = _compact_text(text)
    if _looks_like_structural_unit(text):
        return False
    subject = bool(_named_products(compact)) or any(
        token in compact for token in (
            "公司", "本公司", "集团", "集團", "业务", "業務", "产品", "產品",
            "主营", "主營", "平台", "芯片", "晶片", "解决方案", "解決方案", "研发投入", "研發投入",
        )
    )
    profile = any(token in compact for token in ("主营", "主營", "主要从事", "主要從事"))
    relation = bool(re.search(
        r"(?:主要)?(?:应用|應用|用于|用於|服务|服務)(?:于|於)?|(?:面向|包括|涵盖|涵蓋|拥有|擁有|符合|认证|認證)|"
        r"(?:是|为|為).{1,50}(?:供应商|供應商|提供商|服务商|服務商)|(?:采用|採用).{0,30}(?:销售|銷售|经营|經營|商业|商業)模式|"
        r"(?:致力于|致力於).{0,30}(?:打造|平台|服务|服務)|(?:为|為|向)客户提供|(?:与|與).{0,100}(?:合作|夥伴)|"
        r"(?:分为|分為)|客户.{0,50}(?:采购|採購)|(?:建立|转化为|轉化為).{0,35}(?:客户|客戶)(?:关系|關係)|"
        r"(?:为|為).{0,20}(?:业务|業務).{0,20}(?:提供|支撑|支持)|"
        r"(?:建立|构建|構建|打造).{0,30}(?:平台|生态|生態|产品线|產品線|客户关系|客戶關係)|"
        r"(?:产品|產品).{0,20}授权.{0,30}(?:合同|周期|週期|期限)|"
        r"(?:研发|研發).{0,20}(?:按照|依照).{0,40}(?:顺序|順序)|"
        r"(?:通过|通過).{0,20}(?:直销|直銷).{0,20}(?:销售|銷售)",
        compact,
    )) or any(token in compact for token in (
        "进入量产", "進入量產", "持续销售", "持續銷售", "持续采购", "持續採購",
        "型号升级", "型號升級", "安全事故", "开发并积累", "開發並積累",
    ))
    return subject and (profile or relation)


def _has_named_product_application_relation(text: str) -> bool:
    return bool(re.search(r"(?:产品|產品).{0,12}(?:应用于|應用於|服务于|服務於|面向)\s*[一-鿿A-Za-z0-9]{2,}", text))


def _looks_like_risk_text(text: str) -> bool:
    return "风险" in text or "風險" in text or any(token in text for token in _RISK_TOKENS)


def _is_concrete_risk_fact(text: str, family: str, usage_hint: str) -> bool:
    if canonical_family_for_usage(usage_hint) is None:
        return False
    compact = _compact_text(text)
    hypothetical = any(token in compact for token in ("如果", "若", "可能", "或将", "或將"))
    anchored = bool(re.search(r"20\d{2}年|报告期|報告期|本期", compact)) or bool(_named_products(compact)) or bool(re.search(r"[一-鿿A-Za-z0-9]{2,}(?:客户|客戶|供应商|供應商)", compact))
    anchored = anchored or bool(re.search(
        r"[一-鿿]{2,12}(?:主要从事|主要從事|自身因素|经营状况|經營狀況)", compact
    )) or bool(
        _matching_tokens(compact, _FINANCIAL_METRICS)
        and any(token in compact for token in ("余额", "餘額", "账面", "賬面", "信用政策", "损益", "損益"))
    )
    if family == "financial_quality_explanation":
        subject = bool(_matching_tokens(compact, _FINANCIAL_METRICS))
        relation = bool(_matching_tokens(compact, _CAUSAL_TOKENS + _FINANCIAL_ACTIONS)) or bool(re.search(
            r"(?:制定|根据|根據|已有).{0,30}(?:计划|計劃|订单|訂單|采购|採購|生产|生產|预测|預測)|(?:下降|减少|減少|跌价|跌價|减值|減值|坏账|壞賬|亏损|虧損|损失|損失)", compact
        ))
    elif family == "market_competition_outlook":
        subject = bool(re.search(r"[一-鿿A-Za-z0-9]{2,}(?:行业|行業|客户|客戶|供应商|供應商)", compact)) or any(
            token in compact for token in ("人才", "人才队伍", "人才隊伍", "技术人员", "技術人員", "研发团队", "研發團隊", "技术团队", "技術團隊", "招贤纳士", "招賢納士")
        )
        relation = any(token in compact for token in (
            "竞争加剧", "競爭加劇", "门槛", "門檻", "争夺", "爭奪", "流失", "引进", "引進", "培训", "培訓", "集中度", "挑战", "挑戰", "拓展", "合作", "激励", "激勵", "业绩不达预期", "業績不達預期",
        ))
    else:
        return False
    return subject and relation and (not hypothetical or anchored)


def _has_concrete_technology_fact(text: str, usage_hint: str = "") -> bool:
    if _looks_like_risk_text(text) or _looks_like_audit_or_policy(text):
        return False
    compact = _compact_text(text)
    named = bool(_named_products(text)) or bool(re.search(
        r"(?:SoC|Wi-?Fi\d*|(?<![A-Z])[A-Z]{2,5}(?![A-Z])|[“\"](?:[A-Z][A-Za-z0-9]{3,})[”\"]|IP(?:核|core)|"
        r"(?:平台|工具|模型)[A-Z][A-Za-z0-9]{2,}|[A-Z][A-Za-z0-9]{2,}(?:平台|工具|模型))",
        compact,
    ))
    rd_subject = bool(re.search(r"(?:研发|研發)(?:策略|范围|範圍|人员|人員|投入|项目|項目)", text))
    specific_product = bool(re.search(
        r"(?:电平转换|電平轉換|芯片|晶片|智能影像|AIoT|先进|先進).{0,8}(?:芯片|晶片|产品|產品|架构|架構|制程|製程)", text
    ))
    relation = any(token in text for token in (
        *_PROGRESS_TOKENS, "亮相", "规划", "規劃", "扩展", "擴展", "研发中", "研發中",
        "自研", "开发", "開發", "积累", "積累", "范围包括", "範圍包括",
        "能够", "能夠", "支持", "具备", "具備", "分配", "搭载", "搭載", "推进", "推進", "布局", "佈局",
    ))
    capability = bool(re.search(
        r"(?:产品线|產品線|平台|解决方案|解決方案|芯片|晶片|系统|系統|技术|技術).{0,30}"
        r"(?:具备|具備|支持|实现|實現|用于|用於|应用|應用|搭载|搭載|采用|採用|保障|满足|滿足)",
        compact,
    )) or bool(re.search(
        r"(?:具备|具備|支持|实现|實現).{0,40}(?:信号|訊號|数据|數據|图像|圖像|晶圆|晶圓|"
        r"接口|频段|頻段|带宽|帶寬|功耗|电源|電源|安全|稳定|穩定|自动化|自動化)",
        compact,
    )) or bool(re.search(
        r"(?:芯片|晶片|产品|產品).{0,30}(?:可|能够|能夠).{0,8}(?:解决|解決|计算|計算|监测|監測|提供).{2,}",
        compact,
    ))
    measured_change = rd_subject and bool(re.search(r"\d", text)) and bool(
        _matching_tokens(text, ("同比", "环比", "增长", "增長", "增加", "提升", "逐年", "占", "佔"))
    )
    if _has_technology_capability(text) and not (named or measured_change or "范围" in text or "範圍" in text):
        return False
    return (named or rd_subject or specific_product) and (relation or measured_change) or capability


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
    compact = _compact_text(text)
    has_report_period = bool(re.search(r"(?:报告期|報告期|本期|本年度|目前|20\d{2}年)", compact))
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
        "产能过剩", "產能過剩", "战略", "戰略", "未来", "未來", "市场机遇", "市場機遇", "市场表现", "市場表現", "验证周期", "驗證周期",
    )
    return bool(_matching_tokens(text, judgment_tokens))


def _has_concrete_market_fact(text: str) -> bool:
    compact = _compact_text(text)
    subject = _has_market_judgment(compact) or bool(_named_products(compact)) or bool(re.search(r"(?:SoC|MCU|芯片|晶片|客户|客戶|企业|企業|厂商|廠商|行业|行業|市场|市場|光模块|光模塊|解决方案|解決方案|汽车|汽車|眼镜|眼鏡)", compact)) or bool(re.search(r"(?:领域|領域).{0,30}(?:产品|產品).{0,50}(?:验证周期|驗證周期)", compact))
    relation = any(token in compact for token in (
        "预计", "預計", "市场规模", "市場規模", "需求", "要求", "采用", "採用", "成果", "拓展", "擴展", "合作", "協作", "共同定义", "共同定義",
        "覆盖", "覆蓋", "横向", "橫向", "展望", "竞争", "競爭", "集中度", "挑战", "挑戰",
        "增长", "增長", "成长", "成長", "提升", "扩大", "擴大", "景气", "景氣", "承压", "承壓", "布局", "佈局", "投入", "专注", "專注", "商业化", "商業化", "进展", "進展", "验证周期", "驗證周期",
        "国产化", "國產化", "国产替代", "國產替代",
        "占据主导", "佔據主導", "市场份额", "市場份額",
    ))
    return subject and relation


def _has_concrete_financial_fact(text: str) -> bool:
    if _looks_like_audit_or_policy(text) or _looks_like_structural_boilerplate(text):
        return False
    compact = _compact_text(text)
    subject = bool(_matching_tokens(compact, _FINANCIAL_METRICS)) or bool(re.search(r"(?:资本|資本|项目|項目|现金|現金|付款|電匯|电汇|航信)", compact))
    relation = bool(_matching_tokens(compact, _CAUSAL_TOKENS + _FINANCIAL_ACTIONS)) or bool(_matching_tokens(
        compact, ("同比", "环比", "较上期", "較上期", "较上年", "較上年", "变动", "變動", "增加", "减少", "提升", "下降", "支出", "投入", "耗资", "耗資", "差异", "差異", "保持稳定", "保持穩定", "保持相对稳定", "保持相對穩定", "稳中有升", "穩中有升")
    )) or bool(re.search(r"依靠.{0,20}(?:回款|付款).{0,10}(?:维持|維持)", compact))
    relation = relation or bool(re.search(
        r"(?:报告期|報告期|本期).{0,60}(?:收购|收購|交割|并表|並表).{0,100}"
        r"(?:形成商誉|形成商譽)|(?:完成|实施|實施).{0,20}(?:股权|股權)?"
        r"(?:收购|收購).{0,40}(?:交割|并表|並表)",
        compact,
    ))
    reported_measure = bool(re.search(r"\d+(?:\.\d+)?%", compact)) and bool(re.search(
        r"(?:20\d{2}\s*年|报告期|報告期|截至|为|為|达到|達到|实现|實現)", compact
    ))
    return subject and (relation or reported_measure)


def _has_financial_change(text: str) -> bool:
    return bool(_matching_tokens(text, ("同比", "环比", "提升", "下降", "增加", "减少", "變動", "保持稳定", "保持穩定", "保持相对稳定", "保持相對穩定", "稳中有升", "穩中有升", "为", "為")))


def _is_strong_financial_explanation(text: str) -> bool:
    return bool(_matching_tokens(text, _FINANCIAL_METRICS)) and bool(_matching_tokens(text, _CAUSAL_TOKENS + _FINANCIAL_ACTIONS) or _has_financial_change(text))


def _has_company_or_business_context(text: str) -> bool:
    return any(token in text for token in ("公司", "本公司", "集团", "集團", "我们", "我們", "主营", "主營", "业务", "業務"))


def _is_complete_argument(text: str, family: str) -> bool:
    anchors = _fact_anchors(text, family)
    has_relation = bool(_matching_tokens(text, _CAUSAL_TOKENS))
    if family == "financial_quality_explanation":
        return has_relation and len(anchors) >= 2
    if family == "technology_product_progress":
        return has_relation and len(anchors) >= 2
    return has_relation and len(anchors) >= 3


def _financial_argument_continues(previous_text: str, following_text: str) -> bool:
    del previous_text
    return bool(re.search(r"^(?:主要因|主要系|由于|由於|因此|从而|從而|随着|隨著|进而|進而|基于|基於|根据|根據|加之|同时|同時|此外)|进而|進而|从而|從而", following_text))


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


def _matching_tokens(text: str, tokens: Sequence[str]) -> list[str]:
    return [token for token in tokens if token in text]


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)
