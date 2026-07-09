"""LLM synthesis skill."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..knowledge_synthesizer import KnowledgeSynthesizer
    from ..source_adapter import adapt_all
    from ..synthesis_credit import (
        credit_usage_rules_text,
        derive_synthesis_usage,
        format_synthesis_source_line,
        is_core_fact_supporting_source,
        format_claim_verification_appendix,
    )
    from ..synthesis_source_policy import (
        is_canonical_synthesis_source,
        is_formal_display_source,
    )
    from ..periodic_report_narrative_card_synthesis_items import (
        load_periodic_narrative_card_synthesis_items,
    )
    from ..broker_research_digest_synthesis_items import (
        load_broker_research_digest_synthesis_items,
    )
    from ..synthesis_display_deduper import dedupe_synthesis_display_items
    from ..curated_external_display_lint import lint_curated_external_display_text
    from ..curated_external_display import build_curated_external_narrative_display, flatten_synthesis_text
    from ..industry_news_relevance import build_industry_relevance_manifest
    from ..peer_comparison_material import build_peer_comparison_material
    from ..fundflow_material import build_fundflow_material_pack
    from ..annual_report_material_pack import build_annual_report_material_pack
else:
    from skill_pipeline import BaseSkill, SkillContext
    from knowledge_synthesizer import KnowledgeSynthesizer
    from source_adapter import adapt_all
    from synthesis_credit import (
        credit_usage_rules_text,
        derive_synthesis_usage,
        format_synthesis_source_line,
        is_core_fact_supporting_source,
        format_claim_verification_appendix,
    )
    from synthesis_source_policy import (
        is_canonical_synthesis_source,
        is_formal_display_source,
    )
    from periodic_report_narrative_card_synthesis_items import (
        load_periodic_narrative_card_synthesis_items,
    )
    from broker_research_digest_synthesis_items import (
        load_broker_research_digest_synthesis_items,
    )
    from synthesis_display_deduper import dedupe_synthesis_display_items
    from curated_external_display_lint import lint_curated_external_display_text
    from curated_external_display import build_curated_external_narrative_display, flatten_synthesis_text
    from industry_news_relevance import build_industry_relevance_manifest
    from peer_comparison_material import build_peer_comparison_material
    from fundflow_material import build_fundflow_material_pack
    from annual_report_material_pack import build_annual_report_material_pack


SYNTHESIS_KEYS = [
    "industry_logic",
    "fundamentals",
    "valuation_debate",
    "funding_sentiment",
    "events_catalysts",
]

CURATED_EXTERNAL_TOPIC_ALIASES = {
    "supply_delivery_capacity": "order_capacity_delivery",
    "order_capacity": "order_capacity_delivery",
    "delivery_capacity": "order_capacity_delivery",
    "supply_chain": "order_capacity_delivery",
    "technology_route": "technology_route",
    "tech_route": "technology_route",
    "industry_logic": "technology_route",
    "financial_quality": "financial_quality",
    "fundamentals": "financial_quality",
    "earnings_quality": "financial_quality",
    "competition_commercialization": "competition_commercialization",
    "commercialization": "competition_commercialization",
    "market_expectation": "market_expectation",
    "capital_market": "market_expectation",
    "risk_rumor_rebuttal": "risk_rumor_rebuttal",
    "watch_variable": "risk_rumor_rebuttal",
    "dissent": "risk_rumor_rebuttal",
}

class SynthesisSkill(BaseSkill):
    """LLM 综合叙事生成。"""
    name = "synthesis"

    def __init__(self, llm_client=None, synthesizer=None, **kwargs):
        super().__init__(**kwargs)
        self.llm_client = llm_client
        self.synthesizer = synthesizer

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        keep_posts = ctx.get("keep_posts", [])

        # Build peer comparison material from deterministic metrics.
        # Must be done BEFORE baseline synthesis so _build_prompt can
        # add peer appendix to 4.1/4.2 theme prompts.
        peer_material = build_peer_comparison_material(
            stock_name=stock_name,
            competitor_metrics=ctx.get("competitor_metrics"),
            stock_config=ctx.get("stock_config"),
        )
        ctx.set("peer_comparison_material", peer_material)

        # Build formal material packs early so evidence profile can read them.
        financial_fact_pack = self._build_formal_financial_fact_pack(
            ctx.get("periodic_report_filing_core_facts", [])
        )
        if financial_fact_pack.get("facts"):
            ctx.set("formal_financial_fact_pack", financial_fact_pack)
        financial_explanation_pack = ctx.get("periodic_report_explanation_pack") or {}
        if isinstance(financial_explanation_pack, dict) and financial_explanation_pack.get("rows"):
            ctx.set("formal_financial_explanation_pack", financial_explanation_pack)
        fundflow_material_pack = build_fundflow_material_pack(stock_raw.get("fundflow", []))
        if fundflow_material_pack.get("rows"):
            ctx.set("fundflow_material_pack", fundflow_material_pack)

        # Build annual-report material pack and deterministic memo skeleton.
        annual_material_pack: Dict[str, Any] = {}
        stock_name_for_annual = ctx.get("stock_name")
        if stock_name_for_annual:
            base_dir = ctx.get("knowledge_base_dir") or Path(__file__).resolve().parents[3] / "knowledge"
            try:
                annual_material_pack = build_annual_report_material_pack(
                    stock_name=stock_name_for_annual,
                    base_dir=base_dir,
                    max_cards=8,
                    per_type_limit=2,
                )
            except Exception:
                pass
        if annual_material_pack:
            ctx.set("annual_report_material_pack", annual_material_pack)
        ctx.set("annual_report_memo", self._build_annual_report_memo(ctx))
        ctx.set("broker_research_memo", self._build_broker_research_memo(ctx))

        # Build canonical synthesis items once.
        items = self._build_synthesis_items(stock_raw, keep_posts, ctx=ctx)

        # Curated external display is independent of baseline synthesis; build it first.
        self._build_viewpoint_narrative_deep_analysis_display(ctx)
        if not ctx.get("deep_analysis_display"):
            self._build_viewpoint_digest_deep_analysis_display(ctx)

        # Evidence-adaptive routing: profile decides which deep-analysis prompts run.
        profile = self._build_evidence_profile(ctx, items)
        ctx.set("deep_analysis_evidence_profile", profile)
        ctx.set("deep_analysis_material_coverage", self._build_material_coverage_diagnostics(ctx))

        if profile["profile"] in {"formal_rich", "formal_medium"}:
            baseline = self._synthesize(stock_name, stock_raw, keep_posts, ctx, items=items)
        else:
            source_policy = self._canonical_synthesis_source_policy(ctx)
            formal_first_insufficient = source_policy == "formal_first"
            if ctx is not None and formal_first_insufficient:
                ctx.set("formal_first_sources_insufficient", True)
            baseline = self._empty_baseline_synthesis(stock_raw, items, source_policy=source_policy, formal_first_insufficient=formal_first_insufficient)
        ctx.set("synthesis", baseline)
        core_facts = self._select_core_facts(
            baseline.get("core_facts", []),
            ctx.get("periodic_report_filing_core_facts", []),
        )
        ctx.set("core_facts", core_facts)
        ctx.set("synthesis_text", flatten_synthesis_text(baseline))
        ctx.set("synthesis_items_count", baseline.get("_items_count", 0))
        ctx.set("synthesis_sources", baseline.get("_sources", []))
        ctx.set("industry_relevance_manifest", baseline.get("_industry_relevance_manifest", {}))

        # Optional experimental paths: annual-report materials and broker-research
        # digest notes may enter the DISPLAY synthesis only.  Canonical synthesis,
        # core_facts, synthesis_text, and synthesis_sources stay baseline so risk
        # scoring and Knowledge persistence never see display-only material.
        # Formal-rich and formal-medium reports keep the legacy deep-analysis
        # sections, so they may use display-only formal materials to improve
        # readability. Thin layouts use the external viewpoint map / formal
        # summary instead.
        display_items = []
        fulltext_items = []
        narrative_card_items = []
        broker_digest_items = []
        if profile["profile"] in {"formal_rich", "formal_medium"}:
            if ctx.get("include_periodic_report_fulltext_in_synthesis"):
                fulltext_items = self._eligible_periodic_report_fulltext_items(ctx)
                display_items.extend(fulltext_items)
            if ctx.get("include_periodic_narrative_cards_in_synthesis_display"):
                narrative_card_items = self._eligible_periodic_narrative_card_items(ctx)
                display_items.extend(narrative_card_items)
            if ctx.get("include_broker_research_digest_in_synthesis_display"):
                broker_digest_items = self._eligible_broker_research_digest_items(ctx)
                display_items.extend(broker_digest_items)
        if display_items:
            display = self._synthesize(
                stock_name,
                stock_raw,
                keep_posts,
                ctx,
                extra_items=display_items,
            )
            display_text = flatten_synthesis_text(display)
            ctx.set("synthesis_display", display)
            ctx.set("synthesis_display_sources", display.get("_sources", []))
            ctx.set("synthesis_text_with_periodic_display_materials", display_text)
            if fulltext_items:
                ctx.set("synthesis_text_with_periodic_report_fulltext", display_text)
            if narrative_card_items:
                ctx.set("synthesis_text_with_periodic_narrative_cards", display_text)
            if broker_digest_items:
                ctx.set("synthesis_text_with_broker_research_digest", display_text)

        return ctx

    @staticmethod
    def _select_core_facts(baseline_core_facts: list, filing_core_facts: list) -> list:
        """Prefer baseline core facts only when at least one is renderable."""
        baseline_core_facts = baseline_core_facts or []
        filing_core_facts = filing_core_facts or []
        supportable_statuses = {"supported", "partially_supported"}
        has_supportable_baseline = any(
            isinstance(fact, dict)
            and fact.get("provenance_status", "missing_ref") in supportable_statuses
            for fact in baseline_core_facts
        )
        if has_supportable_baseline or not filing_core_facts:
            return baseline_core_facts
        return filing_core_facts

    @staticmethod
    def _eligible_periodic_report_fulltext_items(ctx: SkillContext) -> list:
        """Return only legitimate periodic-report full-text material items."""
        items = ctx.get("periodic_report_fulltext_items", []) or []
        eligible = []
        for item in items:
            extra = getattr(item, "extra", {}) or {}
            if (
                extra.get("source_type") == "periodic_report_fulltext_analysis"
                and extra.get("source_credit") == 75
                and extra.get("verification_status") == "professional_analysis"
                and extra.get("claim_status") == "professional_analysis"
                and extra.get("experimental") is True
            ):
                eligible.append(item)
        return eligible

    @staticmethod
    def _eligible_periodic_narrative_card_items(ctx: SkillContext) -> list:
        """Load persisted periodic-report narrative cards as display-only items."""
        stock_name = ctx.get("stock_name")
        if not stock_name:
            return []
        base_dir = ctx.get("knowledge_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        max_cards = ctx.get("periodic_narrative_cards_max_display_items", 12)
        try:
            max_cards = int(max_cards)
        except (TypeError, ValueError):
            max_cards = 12
        try:
            return load_periodic_narrative_card_synthesis_items(
                stock_name=stock_name,
                base_dir=base_dir,
                max_cards=max_cards,
                use_pack=True,
                per_type_limit=3,
            )
        except Exception:
            return []

    @staticmethod
    def _eligible_broker_research_digest_items(ctx: SkillContext) -> list:
        """Load persisted broker-research digest notes as display-only items."""
        stock_name = ctx.get("stock_name")
        if not stock_name:
            return []
        base_dir = ctx.get("knowledge_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        max_items = ctx.get("broker_research_digest_max_display_items", 5)
        try:
            max_items = int(max_items)
        except (TypeError, ValueError):
            max_items = 5
        try:
            return load_broker_research_digest_synthesis_items(
                stock_name=stock_name,
                base_dir=base_dir,
                max_items=max_items,
            )
        except Exception:
            return []

    @staticmethod
    def _annual_narrative_cards(ctx: SkillContext, material: Dict[str, Any]) -> List[Dict[str, Any]]:
        selected = [
            c for c in (material.get("selected_narrative_cards") or [])
            if isinstance(c, dict)
        ]
        if selected:
            return selected
        pack = ctx.get("periodic_report_narrative_evidence_cards") or {}
        cards: List[Dict[str, Any]] = []
        for c in pack.get("cards") or []:
            if not isinstance(c, dict):
                continue
            excerpt = c.get("excerpt") or c.get("source_excerpt")
            if not excerpt:
                continue
            cards.append({
                "card_id": c.get("card_id"),
                "card_type": c.get("card_type"),
                "title": c.get("title"),
                "excerpt": excerpt,
                "source_block_id": c.get("source_block_id"),
                "report_year": c.get("report_year"),
                "report_type": c.get("report_type"),
                "source_credit": c.get("source_credit", 75),
            })
        return cards

    @staticmethod
    def _clean_annual_memo_excerpt(text: str, max_chars: int = 300) -> str:
        """Keep annual-report flavor while stripping visible PDF/table noise."""
        cleaned = str(text or "")
        cleaned = re.sub(
            r"[\u4e00-\u9fffA-Za-z0-9（）()·]{0,50}(?:集团股份有限公司|股份有限公司|有限公司)\s*20\d{2}年(?:年度报告|半年度报告)",
            "",
            cleaned,
        )
        cleaned = re.sub(r"20\d{2}年(?:年度报告|半年度报告)", "", cleaned)
        cleaned = re.sub(r"\b\d{1,3}/\d{1,3}\b", "", cleaned)
        cleaned = re.sub(r"\b\d{1,3}/(?=\s|$)", "", cleaned)
        for header in (
            "产品类型 产品介绍 应用领域 产品或终端样图",
            "产品类型 产品介绍 应用领域",
            "产品或终端样图",
        ):
            cleaned = cleaned.replace(header, "")
        cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，,。；;")
        if len(cleaned) > max_chars:
            cut = cleaned[:max_chars]
            for sep in ("。", "；", "，", " "):
                idx = cut.rfind(sep)
                if idx >= int(max_chars * 0.6):
                    cut = cut[:idx + 1]
                    break
            cleaned = cut.strip(" ，,；;")
        return cleaned

    @staticmethod
    def _looks_like_annual_table_fragment(text: str) -> bool:
        compact = re.sub(r"\s+", "", str(text or ""))
        markers = ("主要由", "系列构", "接口", "存储容量", "模组", "屏模组")
        return len(compact) >= 80 and sum(1 for marker in markers if marker in compact) >= 4

    @staticmethod
    def _build_annual_report_memo(ctx: SkillContext) -> Dict[str, Any]:
        """Build a deterministic annual-report memo skeleton from existing packs."""
        material = ctx.get("annual_report_material_pack") or {}
        fact_pack = ctx.get("formal_financial_fact_pack") or {}
        explanation_pack = ctx.get("formal_financial_explanation_pack") or {}
        filing_core = ctx.get("periodic_report_filing_core_facts") or []

        forbidden = ("知乎", "雪球", "券商认为", "研报预计")
        warnings: List[str] = []
        valid_cards: List[Dict[str, Any]] = []
        seen_card_bodies: set[str] = set()
        narrative_cards = SynthesisSkill._annual_narrative_cards(ctx, material)
        for card in narrative_cards:
            if not isinstance(card, dict):
                continue
            text = str(card.get("excerpt") or card.get("title") or "")
            cleaned_text = SynthesisSkill._clean_annual_memo_excerpt(text)
            if SynthesisSkill._looks_like_annual_table_fragment(cleaned_text):
                continue
            body_key = re.sub(r"\s+", "", cleaned_text)
            if body_key and body_key in seen_card_bodies:
                continue
            if body_key:
                seen_card_bodies.add(body_key)
            hit = next((t for t in forbidden if t in text), "")
            if hit:
                warnings.append(f"skipped forbidden token '{hit}': {card.get('card_id')}")
                continue
            card = dict(card)
            card["excerpt"] = cleaned_text
            valid_cards.append(card)

        for fact in filing_core:
            if isinstance(fact, dict) and "0.00亿元" in str(fact.get("data") or ""):
                m = str(fact.get("fact") or "")
                if "营收" in m or "收入" in m or "利润" in m:
                    warnings.append(f"suspicious zero metric: {m}={fact.get('data')}")

        product_types = {"business_model", "rd_product_progress", "technology_platform", "management_market_view", "operation_update"}
        has_product = any(str(c.get("card_type")) in product_types for c in valid_cards)
        has_material = bool(narrative_cards or fact_pack.get("facts") or explanation_pack.get("rows"))

        citations: Dict[int, Dict[str, Any]] = {}
        src_to_ref: Dict[tuple, int] = {}
        nxt = 1

        def _ref(key: tuple, meta: Dict[str, Any]) -> int:
            nonlocal nxt
            if key in src_to_ref:
                return src_to_ref[key]
            src_to_ref[key] = nxt
            citations[nxt] = meta
            nxt += 1
            return nxt - 1

        def _annual_row(title, body, iref, src, source_type, citation_key, citation_title="", source_credit=None, display_group=""):
            meta: Dict[str, Any] = {"source": "公司年报", "title": citation_title or src, "source_type": source_type}
            if source_credit is not None:
                meta["source_credit"] = source_credit
            row = {"title": title, "body": body, "internal_refs": [iref],
                   "citation_refs": [_ref(citation_key, meta)], "source_ref_ids": [src]}
            if display_group:
                row["display_group"] = display_group
            return row

        def _suspicious_zero_metric(metric: object, value: object) -> bool:
            metric_text = str(metric or "")
            value_text = str(value or "")
            return "0.00亿元" in value_text and any(t in metric_text for t in ("营收", "收入", "利润"))

        confirmed: List[Dict[str, Any]] = []
        for f in fact_pack.get("facts") or []:
            if isinstance(f, dict) and f.get("metric") is not None and f.get("value") is not None:
                if _suspicious_zero_metric(f.get("metric"), f.get("value")):
                    warning = f"suspicious zero metric: {f.get('metric')}={f.get('value')}"
                    if warning not in warnings:
                        warnings.append(warning)
                    continue
                s = str(f.get("source") or "公司年报")
                metric = str(f["metric"])
                confirmed.append(_annual_row(
                    metric, f"{metric}：{f['value']}", f"fact:{metric}", s,
                    "periodic_report_filing_fact", ("fact", s, f["metric"]),
                ))

        explanation_rows: List[Dict[str, Any]] = []
        for r in explanation_pack.get("rows") or []:
            if isinstance(r, dict):
                m = r.get("metric") or r.get("topic")
                b = r.get("normalized_summary") or r.get("excerpt")
                if m and b:
                    s = str(r.get("source_doc") or "公司年报")
                    source_ref = r.get("source_ref") or ""
                    explanation_rows.append(_annual_row(
                        str(m), str(b), f"explanation:{source_ref}", s,
                        "periodic_report_explanation", ("explanation", s, source_ref),
                        display_group="financial_explanation",
                    ))

        card_group = {
            "business_model": "product_business",
            "operation_update": "operation_update",
            "management_market_view": "management_view",
            "market_outlook": "management_view",
            "margin_competitiveness": "competitiveness_rd",
            "technology_platform": "competitiveness_rd",
            "rd_product_progress": "competitiveness_rd",
            "financial_note": "financial_explanation",
        }
        for c in valid_cards[:8]:
            title = str(c.get("title") or "年报内容")
            body = str(c.get("excerpt") or c.get("title") or "")
            sid = c.get("source_block_id") or c.get("card_id") or ""
            explanation_rows.append(_annual_row(
                title, body, str(c.get("card_id") or ""), str(sid),
                "periodic_report_narrative_evidence", ("card", sid), title, c.get("source_credit", 75),
                display_group=card_group.get(str(c.get("card_type") or ""), "product_business"),
            ))

        has_usable_rows = bool(confirmed or explanation_rows)
        status = (
            "absent" if not has_material else
            "ready" if len(valid_cards) >= 4 and has_product and has_usable_rows else
            "deterministic_fallback" if has_usable_rows else
            "blocked" if warnings else "deterministic_fallback"
        )

        return {
            "schema": "annual_report_memo.v1",
            "status": status,
            "source_layer": "annual_report",
            "sections": {
                "confirmed": confirmed,
                "annual_report_explanation": explanation_rows,
                "not_disclosed": [{"title": "未充分披露项", "body": "重要客户、订单、产能、供应链、管理层指引或细分拆分未在正式材料中充分披露。", "internal_refs": [], "citation_refs": [], "source_ref_ids": []}],
                "inconclusive": [{"title": "不能下结论", "body": "不得用营收/利润推断主力资金或市场行为。", "internal_refs": [], "citation_refs": [], "source_ref_ids": []}],
            },
            "validation": {"warnings": warnings, "numeric_terms_checked": True, "unsupported_numbers": [], "strong_claims": []},
            "citations": citations,
        }

    @staticmethod
    def _build_broker_research_memo(ctx: SkillContext) -> Dict[str, Any]:
        """Build a deterministic broker-research memo from existing digest items."""
        raw_items = ctx.get("broker_research_digest_items")
        items = raw_items if raw_items is not None else SynthesisSkill._eligible_broker_research_digest_items(ctx)
        family_map = {
            "broker_core_view": "core_view",
            "broker_product_driver": "product_driver",
            "broker_earnings_forecast": "earnings_forecast",
            "broker_risk_note": "risk_note",
            "broker_valuation_method": "valuation_method",
        }
        title_map = {
            "broker_core_view": "券商核心观点",
            "broker_product_driver": "产业与产品判断",
            "broker_earnings_forecast": "盈利预测与估值假设",
            "broker_risk_note": "风险提示",
            "broker_valuation_method": "估值方法",
        }
        selected: List[Any] = []
        seen: set = set()
        for item in items or []:
            extra = getattr(item, "extra", {}) or {}
            if (
                extra.get("source_type") != "broker_research"
                or extra.get("claim_status") != "professional_analysis"
                or extra.get("confirmed_fact") is True
                or extra.get("scoring_eligible") is True
                or extra.get("risk_score_eligible") is True
            ):
                continue
            card_type = str(extra.get("card_type") or "")
            family = family_map.get(card_type)
            excerpt = " ".join(str(getattr(item, "content", "") or "").split())
            if not family or not excerpt:
                continue
            key = (family, str(extra.get("viewpoint_cluster") or excerpt[:80]))
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)

        families = {
            family_map.get(str((getattr(item, "extra", {}) or {}).get("card_type") or ""))
            for item in selected
        }
        families.discard(None)
        institutions: List[str] = []
        for item in selected:
            institution = str((getattr(item, "extra", {}) or {}).get("institution") or getattr(item, "author", "") or "").strip()
            if institution and institution not in institutions:
                institutions.append(institution)
        report_titles = {
            str(getattr(item, "title", "") or "").strip()
            for item in selected
            if str(getattr(item, "title", "") or "").strip()
        }
        admitted = (
            (len(selected) >= 2 and len(families) >= 2)
            or (len(report_titles) == 1 and len(families) >= 2)
            or (len(institutions) >= 2 and len(selected) >= 2)
        )
        status = "absent"
        if admitted:
            status = "single_institution" if len(institutions) <= 1 or len(report_titles) <= 1 else "ready"

        citations: Dict[int, Dict[str, Any]] = {}
        sections: List[Dict[str, Any]] = []
        forecast_ranges: List[Dict[str, Any]] = []
        risks: List[Dict[str, Any]] = []

        def _source_id(item: Any) -> str:
            extra = getattr(item, "extra", {}) or {}
            seed = str(extra.get("viewpoint_cluster") or getattr(item, "title", "") or getattr(item, "content", ""))
            return f"broker_research_digest:{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"

        def _row(item: Any, ref_id: int) -> Dict[str, Any]:
            extra = getattr(item, "extra", {}) or {}
            card_type = str(extra.get("card_type") or "")
            institution = str(extra.get("institution") or getattr(item, "author", "") or "券商").strip()
            text = " ".join(str(getattr(item, "content", "") or "").split())
            if card_type == "broker_risk_note":
                body = text if text.startswith("研报提示") else f"研报提示：{text}"
            else:
                body = text if re.match(r"^(券商|研报|机构)", text) else f"{institution}认为：{text}"
            sid = _source_id(item)
            citations[ref_id] = {
                "source": "券商研报",
                "title": str(getattr(item, "title", "") or title_map.get(card_type, "券商研报")),
                "author": institution,
                "source_type": "broker_research",
                "source_credit": 72,
                "claim_status": "professional_analysis",
                "verification_status": "professional_observation",
            }
            return {
                "title": title_map.get(card_type, "券商观点"),
                "body": body,
                "internal_refs": [sid.replace("broker_research_digest:", "broker:card:")],
                "citation_refs": [ref_id],
                "source_ref_ids": [sid],
            }

        if status != "absent":
            for ref_id, item in enumerate(selected[:6], start=1):
                row = _row(item, ref_id)
                card_type = str((getattr(item, "extra", {}) or {}).get("card_type") or "")
                if card_type == "broker_risk_note":
                    risks.append({"body": row["body"], **{k: row[k] for k in ("internal_refs", "citation_refs", "source_ref_ids")}})
                elif card_type == "broker_earnings_forecast":
                    forecast_ranges.append({
                        "metric": "研报盈利预测",
                        "period": "未拆分",
                        "range": row["body"],
                        **{k: row[k] for k in ("internal_refs", "citation_refs", "source_ref_ids")},
                    })
                else:
                    sections.append(row)

        return {
            "schema": "broker_research_memo.v1",
            "status": status,
            "source_layer": "broker_research",
            "institutions": institutions,
            "sections": sections,
            "forecast_ranges": forecast_ranges,
            "risks": risks,
            "diagnostics": {
                "input_item_count": len(items or []),
                "usable_card_count": len(selected),
                "content_families": sorted(families),
                "institution_count": len(institutions),
            },
            "validation": {"attributed_forecasts_only": True, "entered_scoring": False, "entered_target_price": False},
            "citations": citations,
        }

    @staticmethod
    def _build_material_coverage_diagnostics(ctx: SkillContext) -> Dict[str, Any]:
        """Return lightweight source-layer coverage diagnostics for chapter 4.

        This is audit-only metadata. It is not used for routing, scoring,
        target price, risk score, or recommendation wording.
        """
        annual_pack = ctx.get("annual_report_material_pack") or {}
        annual_diag = annual_pack.get("diagnostics") or {}
        annual_memo = ctx.get("annual_report_memo") or {}
        annual_sections = annual_memo.get("sections") or {}

        broker_memo = ctx.get("broker_research_memo") or {}
        broker_diag = broker_memo.get("diagnostics") or {}
        raw_broker = SynthesisSkill._broker_raw_report_coverage(ctx)
        memo_institutions = broker_memo.get("institutions") or []
        uncovered_raw_institutions = [
            name for name in raw_broker["institutions"]
            if name not in memo_institutions
        ]

        deep_display = ctx.get("deep_analysis_display") or {}
        topic_groups = deep_display.get("_curated_external_topic_groups") or {}
        topic_claim_count = 0
        if isinstance(topic_groups, dict):
            topic_claim_count = sum(len(v) for v in topic_groups.values() if isinstance(v, list))

        return {
            "schema": "deep_analysis_material_coverage.v1",
            "annual": {
                "memo_status": annual_memo.get("status", "absent"),
                "narrative_cards_seen": int(annual_diag.get("cards_seen") or 0),
                "narrative_cards_selected": int(annual_diag.get("cards_selected") or 0),
                "by_type_seen": annual_diag.get("by_type_seen") or {},
                "by_type_selected": annual_diag.get("by_type_selected") or {},
                "confirmed_row_count": len(annual_sections.get("confirmed") or []),
                "explanation_row_count": len(annual_sections.get("annual_report_explanation") or []),
                "memo_row_count": (
                    len(annual_sections.get("confirmed") or [])
                    + len(annual_sections.get("annual_report_explanation") or [])
                ),
                "validation_warning_count": len((annual_memo.get("validation") or {}).get("warnings") or []),
            },
            "broker": {
                "memo_status": broker_memo.get("status", "absent"),
                "raw_manifest_status": raw_broker["status"],
                "raw_report_count": raw_broker["report_count"],
                "raw_institution_count": len(raw_broker["institutions"]),
                "raw_institutions": raw_broker["institutions"],
                "uncovered_raw_institutions": uncovered_raw_institutions,
                "digest_item_count": int(broker_diag.get("input_item_count") or broker_diag.get("usable_card_count") or 0),
                "memo_usable_card_count": int(broker_diag.get("usable_card_count") or 0),
                "memo_row_count": (
                    len(broker_memo.get("sections") or [])
                    + len(broker_memo.get("forecast_ranges") or [])
                    + len(broker_memo.get("risks") or [])
                ),
                "memo_institution_count": int(broker_diag.get("institution_count") or len(broker_memo.get("institutions") or [])),
                "memo_institutions": memo_institutions,
                "content_families": broker_diag.get("content_families") or [],
            },
            "external": {
                "citation_source_count": len(deep_display.get("citations") or {}),
                "reasoning_card_count": len(deep_display.get("_curated_external_reasoning_cards") or []),
                "narrative_paragraph_count": len(deep_display.get("_curated_external_narrative_paragraphs") or []),
                "topic_group_count": len(topic_groups) if isinstance(topic_groups, dict) else 0,
                "topic_claim_count": topic_claim_count,
                "status": (
                    ctx.get("curated_external_viewpoint_narrative_status")
                    or ctx.get("curated_external_viewpoint_digest_status")
                    or "absent"
                ),
            },
        }

    @staticmethod
    def _broker_raw_report_coverage(ctx: SkillContext) -> Dict[str, Any]:
        stock_name = str(ctx.get("stock_name") or "").strip()
        stock_code = str((ctx.get("stock_codes") or {}).get(stock_name) or "").strip()
        root = ctx.get("broker_research_cache_root")
        cache_root = Path(root) if root else Path(__file__).resolve().parents[3] / "data" / "raw" / "broker_research_reports"
        candidates: List[Path] = []
        if stock_name and stock_code:
            candidates.append(cache_root / f"{stock_name}_{stock_code}" / "manifest.json")
        if stock_name:
            candidates.append(cache_root / stock_name / "manifest.json")
            candidates.extend(sorted(cache_root.glob(f"{stock_name}_*/manifest.json")))

        manifest_path = next((p for p in candidates if p.exists()), None)
        if manifest_path is None:
            return {"status": "missing", "report_count": 0, "institutions": []}
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "unreadable", "report_count": 0, "institutions": []}
        reports = payload.get("reports") if isinstance(payload, dict) else []
        if not isinstance(reports, list):
            reports = []
        institutions: List[str] = []
        for report in reports:
            if not isinstance(report, dict):
                continue
            institution = str(report.get("institution") or report.get("orgName") or "").strip()
            if institution and institution not in institutions:
                institutions.append(institution)
        return {"status": "ok", "report_count": len(reports), "institutions": institutions}

    def _build_viewpoint_narrative_deep_analysis_display(self, ctx: SkillContext) -> None:
        """Build deep-analysis-only display from cached full-body narrative JSON."""
        enabled = bool(
            ctx.get("include_curated_external_viewpoint_narrative_in_deep_analysis_display")
            or getattr(self, "include_curated_external_viewpoint_narrative_in_deep_analysis_display", False)
        )
        if not enabled:
            return

        narrative_json = ctx.get("curated_external_viewpoint_narrative_json") or getattr(
            self, "curated_external_viewpoint_narrative_json", ""
        )
        if not narrative_json:
            ctx.set("curated_external_viewpoint_narrative_status", "missing_config")
            ctx.set(
                "curated_external_viewpoint_narrative_stats",
                {"rejection_reasons": ["curated_external_viewpoint_narrative_json not set"]},
            )
            return

        result = build_curated_external_narrative_display(narrative_json)
        ctx.set("curated_external_viewpoint_narrative_status", result.get("status"))
        ctx.set("curated_external_viewpoint_narrative_stats", result.get("stats") or {})
        if result.get("lint"):
            ctx.set("curated_external_viewpoint_narrative_lint", result.get("lint"))
        if result.get("status") != "ok":
            return

        display = result.get("display") or {}
        ctx.set("deep_analysis_display", display)
        ctx.set("deep_analysis_display_sources", display.get("_sources", []))
        ctx.set("synthesis_text_with_curated_external_viewpoint_narrative", result.get("synthesis_text") or "")
        ctx.set("curated_external_viewpoint_narrative_status", "ok")

    def _build_viewpoint_digest_deep_analysis_display(self, ctx: SkillContext) -> None:
        """Build deep-analysis-only display from cached full-body viewpoint digest."""
        enabled = bool(
            ctx.get("include_curated_external_viewpoint_digest_in_deep_analysis_display")
            or getattr(self, "include_curated_external_viewpoint_digest_in_deep_analysis_display", False)
        )
        if not enabled:
            return

        digest_json = ctx.get("curated_external_viewpoint_digest_json") or getattr(
            self, "curated_external_viewpoint_digest_json", ""
        )
        if not digest_json:
            ctx.set("curated_external_viewpoint_digest_status", "missing_config")
            ctx.set("curated_external_viewpoint_digest_stats", {"rejection_reasons": ["curated_external_viewpoint_digest_json not set"]})
            return

        try:
            digest = json.loads(Path(digest_json).read_text(encoding="utf-8"))
        except Exception as exc:
            ctx.set("curated_external_viewpoint_digest_status", "reader_error")
            ctx.set("curated_external_viewpoint_digest_stats", {"rejection_reasons": [str(exc)]})
            return

        status = str(digest.get("status") or "")
        ctx.set("curated_external_viewpoint_digest_status", status)
        ctx.set("curated_external_viewpoint_digest_stats", digest.get("stats") or {})
        if status != "ok":
            return

        claims = [
            claim for claim in (digest.get("claims") or [])
            if self._is_safe_curated_external_viewpoint_claim(claim)
        ]
        if not claims:
            ctx.set("curated_external_viewpoint_digest_status", "empty")
            return

        claims = self._dedupe_viewpoint_digest_claims_for_display(claims)
        display = self._deterministic_viewpoint_digest_display(ctx.get("stock_name"), claims)
        lint = lint_curated_external_display_text(display)
        ctx.set("curated_external_viewpoint_digest_lint", lint)
        if not lint.get("ok"):
            ctx.set("curated_external_viewpoint_digest_status", "lint_failed")
            return

        ctx.set("deep_analysis_display", display)
        ctx.set("deep_analysis_display_sources", display.get("_sources", []))
        ctx.set("synthesis_text_with_curated_external_viewpoint_digest", flatten_synthesis_text(display))
        ctx.set("curated_external_viewpoint_digest_status", "ok")

    @staticmethod
    def _is_safe_curated_external_viewpoint_claim(claim: Dict[str, Any]) -> bool:
        if not isinstance(claim, dict):
            return False
        return (
            claim.get("schema_version") == "curated_external_viewpoint_claim.v1"
            and claim.get("quality_action") == "preview_only"
            and claim.get("knowledge_eligible") is False
            and claim.get("synthesis_display_only") is True
            and claim.get("scoring_eligible") is False
            and claim.get("risk_score_eligible") is False
            and claim.get("verification_status") == "professional_observation"
            and str(claim.get("source_quote") or "").strip()
            and str(claim.get("source_quote_hash") or "").strip()
        )

    @staticmethod
    def _build_evidence_profile(ctx: SkillContext, items: list) -> dict:
        """Deterministic evidence profile used to route Chapter 4 layout."""
        stock_name = ctx.get("stock_name", "")
        stock_config = ctx.get("stock_config") or {}
        fact_pack = ctx.get("formal_financial_fact_pack") or {}
        explanation_pack = ctx.get("periodic_report_explanation_pack") or {}
        fundflow_pack = ctx.get("fundflow_material_pack") or {}
        deep_display = ctx.get("deep_analysis_display") or {}
        peer_material = ctx.get("peer_comparison_material") or {}

        canonical_items = [it for it in items if is_canonical_synthesis_source(it)]

        def _dedupe_items(seq: list) -> list:
            seen: set = set()
            result: list = []
            for it in seq:
                extra = getattr(it, "extra", {}) or {}
                key = (it.source_platform, it.title, it.url)
                if key in seen:
                    continue
                seen.add(key)
                result.append(it)
            return result

        industry_items = _dedupe_items(
            KnowledgeSynthesizer._filter_items_for_theme("industry_logic", canonical_items, stock_name, stock_config)
        )
        fundamentals_items = _dedupe_items(
            KnowledgeSynthesizer._filter_items_for_theme("fundamentals", canonical_items, stock_name, stock_config)
        )
        funding_items = _dedupe_items(
            [it for it in canonical_items if KnowledgeSynthesizer._is_funding_sentiment_item(it)]
        )
        events_items = _dedupe_items(
            KnowledgeSynthesizer._filter_items_for_theme("events_catalysts", canonical_items, stock_name, stock_config)
        )

        has_fundflow_pack = bool(fundflow_pack.get("rows"))
        section_support = {
            "industry": len(industry_items),
            "fundamentals": len(fundamentals_items),
            "funding_support": len(funding_items) if (funding_items or has_fundflow_pack) else 0,
            "catalyst_support": len(events_items),
        }

        useful_fact_metrics = {
            "营业收入", "归母净利润", "净利润", "毛利率", "经营现金流", "经营现金流量净额",
            "订单", "客户", "产能", "产量", "价格", "交付", "交期", "库存", "存货",
            "供需", "采购", "备货", "供应商", "指引", "费用率", "研发费用", "销售费用",
            "管理费用", "产品", "产品线", "收入", "成本", "毛利", "营收", "净利",
        }
        useless_fact_metrics = {"年报发布", "年度报告发布", "业绩预告披露", "预告披露", "分红实施", "权益分派"}

        formal_insight_facts = 0
        for fact in (fact_pack.get("facts") or []):
            if not isinstance(fact, dict):
                continue
            metric = str(fact.get("metric") or "")
            if any(m in metric for m in useless_fact_metrics):
                continue
            if any(m in metric for m in useful_fact_metrics):
                formal_insight_facts += 1

        topic_groups = deep_display.get("_curated_external_topic_groups") or {}
        reasoning_cards = deep_display.get("_curated_external_reasoning_cards") or []
        citations = deep_display.get("citations", {}) or {}
        external_topics = len(topic_groups)
        external_claims = len({str(c.get("claim_id") or i): c for i, c in enumerate(reasoning_cards)})
        external_sources = len(citations)
        distinct_authors = len({
            (str(m.get("source") or ""), str(m.get("author") or ""))
            for m in citations.values() if isinstance(m, dict)
        })
        single_source = external_sources == 1 and (external_topics >= 3 or external_claims >= 6)

        has_any_formal = any(section_support.values())
        has_any_item = bool(items)
        has_external_display = bool(deep_display)
        external_rich = external_topics >= 3 or external_claims >= 6
        reasons: List[str] = []
        if formal_insight_facts >= 5 and section_support["industry"] >= 2 and section_support["fundamentals"] >= 2:
            profile = "formal_rich"
            reasons.append("formal_support_sufficient")
        elif has_external_display and external_rich and formal_insight_facts < 5:
            profile = "formal_thin_external_rich"
            reasons.append("formal_thin_external_rich")
            if single_source:
                reasons.append("single_source_external_rich")
        elif has_any_formal or has_any_item:
            profile = "formal_medium"
            reasons.append("formal_support_partial")
        else:
            profile = "thin_all"
            reasons.append("material_insufficient")

        legacy_profile = profile in {"formal_rich", "formal_medium"}
        section_decisions = {
            "industry": "legacy" if (legacy_profile and section_support["industry"] >= 2) else ("formal_summary" if profile == "formal_thin_external_rich" else "skipped"),
            "fundamentals": "legacy" if (legacy_profile and section_support["fundamentals"] >= 2) else ("formal_summary" if profile == "formal_thin_external_rich" else "skipped"),
            "funding": "legacy" if (legacy_profile and section_support["funding_support"] >= 1) else ("fallback" if section_support["catalyst_support"] >= 1 else "skipped"),
            "catalysts": "timeline" if section_support["catalyst_support"] >= 1 else ("fallback" if legacy_profile else "skipped"),
        }

        annual_memo = ctx.get("annual_report_memo") or {}
        broker_memo = ctx.get("broker_research_memo") or {}
        return {
            "profile": profile,
            "formal_insight_facts": formal_insight_facts,
            "formal_section_support": section_support,
            "external_viewpoint_topics": external_topics,
            "external_usable_claims": external_claims,
            "external_source_count": external_sources,
            "external_distinct_author_count": distinct_authors,
            "single_source_external_rich": single_source,
            "external_signal_count": 0,
            "section_decisions": section_decisions,
            "reasons": reasons,
            "annual_memo_status": annual_memo.get("status", "absent"),
            "broker_memo_status": broker_memo.get("status", "absent"),
            "broker_single_institution": broker_memo.get("status") == "single_institution",
            "broker_usable_card_count": broker_memo.get("diagnostics", {}).get("usable_card_count", 0),
            "broker_content_families": broker_memo.get("diagnostics", {}).get("content_families", []),
            "broker_institution_count": len(broker_memo.get("institutions") or []),
            "memo_refs_resolved": bool(annual_memo.get("citations") or broker_memo.get("citations")),
            "formal_thin_layout_variant": (
                "annual_broker_external_checklist" if profile == "formal_thin_external_rich" else None
            ),
        }

    def _deterministic_viewpoint_digest_display(self, stock_name: str, claims: list) -> dict:
        grouped = {
            "industry_logic": [],
            "fundamentals": [],
            "valuation_debate": [],
            "funding_sentiment": [],
            "events_catalysts": [],
        }
        topic_groups = {}
        citations = {}

        for ref_id, claim in enumerate(claims, start=1):
            line = self._format_viewpoint_digest_observation(claim, ref_id)
            bucket = self._viewpoint_digest_bucket(claim)
            grouped[bucket].append(line)
            topic_key = self._external_viewpoint_topic_key(claim)
            topic_groups.setdefault(topic_key, []).append(
                self._viewpoint_digest_topic_row(claim, ref_id)
            )
            citations[ref_id] = self._viewpoint_digest_citation(claim)

        return {
            "industry_logic": self._join_curated_external_observations(
                stock_name,
                "产业链、竞争格局或技术路径增量观点",
                grouped["industry_logic"],
            ),
            "fundamentals": self._join_curated_external_observations(
                stock_name,
                "业绩质量、周期或供需变量",
                grouped["fundamentals"],
            ),
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": self._join_curated_external_observations(
                stock_name,
                "事件、政策或待验证变量",
                grouped["events_catalysts"],
            ),
            "core_facts": [],
            "citations": citations,
            "_curated_external_topic_groups": topic_groups,
            "_curated_external_taxonomy_version": "external_viewpoint.v1",
            "_items_count": len(claims),
            "_sources": list(citations.values()),
        }

    @classmethod
    def _dedupe_viewpoint_digest_claims_for_display(cls, claims: list) -> list:
        """Collapse obvious same-theme repeats while keeping the full digest auditable."""
        deduped = []
        seen = set()
        for claim in claims:
            key = cls._viewpoint_digest_semantic_key(claim)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(claim)
        return deduped

    @staticmethod
    def _viewpoint_digest_semantic_key(claim: Dict[str, Any]) -> str:
        text = " ".join(
            str(claim.get(field) or "")
            for field in ("topic", "claim", "source_quote", "why_incremental")
        )
        lower_text = text.lower()

        if "800g" in lower_text and any(token in text for token in ("1500万", "1200万", "交付计划", "交付下调", "传言")):
            return "800g_delivery_rumor"
        if any(token in text for token in ("预付款", "物料", "原材料", "磷化铟", "光芯片", "供应链")):
            return "material_supply_tightness"
        if "cpo" in lower_text and any(token in text for token in ("可插拔", "Scale Out", "scale out", "替代")):
            return "cpo_vs_pluggable"
        if any(token in text for token in ("NPO", "XPO", "Scale Up", "scale up", "光进铜退")):
            return "npo_xpo_timeline"
        if any(token in text for token in ("2026", "2027", "2028")) and any(
            token in text for token in ("需求指引", "客户需求", "资本开支", "capex", "CapEx")
        ):
            return "customer_demand_capex_guide"

        fingerprint_source = str(claim.get("source_quote_hash") or claim.get("claim_id") or claim.get("claim") or "")
        return f"claim:{fingerprint_source[:32]}"

    @staticmethod
    def _viewpoint_digest_bucket(claim: Dict[str, Any]) -> str:
        topic_key = SynthesisSkill._external_viewpoint_topic_key(claim)
        claim_type = str(claim.get("claim_type") or "")
        if topic_key in ("financial_quality", "order_capacity_delivery"):
            return "fundamentals"
        if topic_key in ("risk_rumor_rebuttal", "market_expectation") or claim_type in ("dissent", "watch_variable"):
            return "events_catalysts"
        return "industry_logic"

    @classmethod
    def _external_viewpoint_topic_key(cls, claim: Dict[str, Any]) -> str:
        raw_topic = str(claim.get("topic") or claim.get("primary_topic") or "").strip()
        if raw_topic in CURATED_EXTERNAL_TOPIC_ALIASES:
            return CURATED_EXTERNAL_TOPIC_ALIASES[raw_topic]

        text = " ".join(
            str(claim.get(field) or "")
            for field in ("topic", "claim", "source_quote", "why_incremental", "claim_type")
        )
        lower_text = text.lower()
        if any(token in text for token in ("传言", "否认", "制裁", "清单", "反证", "回应", "1260H")):
            return "risk_rumor_rebuttal"
        if any(token in text for token in ("预付款", "交付", "产能", "订单", "供应链", "物料", "客户需求", "需求指引")):
            return "order_capacity_delivery"
        if any(token in text for token in ("NPO", "XPO", "CPO", "LPO", "硅光", "可插拔", "光进铜退", "技术路线")):
            return "technology_route"
        if any(token in text for token in ("营收", "利润", "毛利率", "费用", "现金流", "亏损", "研发开支")):
            return "financial_quality"
        if any(token in text for token in ("竞争", "商业化", "定点", "标杆车型", "市场份额", "客户拓展")):
            return "competition_commercialization"
        if any(token in text for token in ("估值", "股价", "市值", "资金", "情绪", "预期差", "机构持仓", "IPO")):
            return "market_expectation"
        if any(token in lower_text for token in ("capex", "800g", "1.6t", "scale up", "scale out")):
            return "technology_route"
        return "other"

    @classmethod
    def _viewpoint_digest_topic_row(cls, claim: Dict[str, Any], ref_id: int) -> dict:
        title = " ".join(str(claim.get("source_title") or claim.get("title") or "外部观点").split())[:80]
        claim_text = str(claim.get("claim") or "").strip().rstrip("。")
        why = str(claim.get("why_incremental") or "").strip().rstrip("。")
        suffix = f"（{why}）" if why else ""
        return {
            "heading": title,
            "text": f"{claim_text}{suffix}。",
            "citation_refs": [ref_id],
            "claim_id": claim.get("claim_id", ""),
            "topic": cls._external_viewpoint_topic_key(claim),
        }

    @staticmethod
    def _format_viewpoint_digest_observation(claim: Dict[str, Any], ref_id: int) -> str:
        title = " ".join(str(claim.get("source_title") or claim.get("title") or "外部观点").split())[:80]
        claim_text = str(claim.get("claim") or "").strip().rstrip("。")
        why = str(claim.get("why_incremental") or "").strip().rstrip("。")
        suffix = f"（{why}）" if why else ""
        return f"《{title}》观察到：{claim_text}{suffix}[^{ref_id}]"

    @staticmethod
    def _viewpoint_digest_citation(claim: Dict[str, Any]) -> dict:
        return {
            "source": "微信公众号精选观察",
            "author": claim.get("source_account") or claim.get("account") or "",
            "title": claim.get("source_title") or claim.get("title") or "外部观点",
            "url": claim.get("source_ref") or claim.get("url") or "",
            "source_type": "curated_external_analysis_evidence",
            "source_credit": claim.get("source_credit", 55),
            "verification_status": claim.get("verification_status", "professional_observation"),
            "claim_id": claim.get("claim_id", ""),
            "source_quote_hash": claim.get("source_quote_hash", ""),
        }

    @staticmethod
    def _is_template_fallback_synthesis(synthesis: dict) -> bool:
        """Detect the generic non-LLM template so curated cards can still render."""
        if not isinstance(synthesis, dict):
            return True
        if synthesis.get("citations"):
            return False
        text = "\n".join(str(synthesis.get(key, "")) for key in SYNTHESIS_KEYS)
        return "LLM 合成未启用或未产生有效输出" in text

    @staticmethod
    def _join_curated_external_observations(stock_name: str, label: str, lines: list) -> str:
        if not lines:
            return ""
        return f"精选外部材料仅作为专业观察，提示 {stock_name} 的{label}包括：" + "；".join(lines)

    def _synthesize(
        self,
        stock_name: str,
        stock_raw: dict,
        keep_posts: list,
        ctx: SkillContext = None,
        extra_items: list = None,
        items: list = None,
        deduped_sources_key: str = "synthesis_display_deduped_sources",
    ) -> dict:
        """调用 KnowledgeSynthesizer 或降级模板生成综合叙事。"""
        source_policy = self._canonical_synthesis_source_policy(ctx)
        enable_cv = bool(ctx.get("enable_claim_verification_context")) if ctx else False
        cv_context = None
        cv_status = None
        cv_error = ""

        if enable_cv:
            try:
                cv_status, cv_context, cv_error = self._build_claim_verification_context(stock_name, ctx)
            except Exception as exc:
                cv_status = "error"
                cv_context = None
                cv_error = f"claim verification build failed: {exc}"

        if ctx is not None:
            ctx.set("claim_verification_status", cv_status)
            ctx.set("claim_verification_error", cv_error)
            if cv_context:
                ctx.set("claim_verification_summary", cv_context)

        if self.llm_client and hasattr(self.llm_client, "chat"):
            return self._legacy_llm_synthesize(stock_name, stock_raw, keep_posts, cv_context)

        fundflow_material_pack = build_fundflow_material_pack(stock_raw.get("fundflow", []))
        if fundflow_material_pack.get("rows") and ctx is not None:
            ctx.set("fundflow_material_pack", fundflow_material_pack)

        if items is None:
            items = self._build_synthesis_items(stock_raw, keep_posts, ctx=ctx, extra_items=extra_items)
            if extra_items:
                items, deduped_sources = dedupe_synthesis_display_items(items)
                if ctx is not None:
                    ctx.set(deduped_sources_key, deduped_sources)
        if not items:
            if ctx is not None and source_policy == "formal_first":
                ctx.set("formal_first_sources_insufficient", True)
            return self._template_synthesize(
                stock_raw,
                items_count=0,
                sources=[],
                source_policy=source_policy,
            )

        synthesizer = self.synthesizer or KnowledgeSynthesizer(client=self.llm_client)
        all_data = {"items": items}
        if ctx and ctx.get("stock_config"):
            all_data["stock_config"] = ctx.get("stock_config")
        if ctx:
            financial_fact_pack = self._build_formal_financial_fact_pack(
                ctx.get("periodic_report_filing_core_facts", [])
            )
            if financial_fact_pack.get("facts"):
                ctx.set("formal_financial_fact_pack", financial_fact_pack)
                all_data["formal_financial_fact_pack"] = financial_fact_pack
            financial_explanation_pack = ctx.get("periodic_report_explanation_pack") or {}
            if isinstance(financial_explanation_pack, dict) and financial_explanation_pack.get("rows"):
                all_data["formal_financial_explanation_pack"] = financial_explanation_pack
        if cv_context:
            all_data["claim_verification_context"] = cv_context
        if ctx and ctx.get("peer_comparison_material"):
            all_data["peer_comparison_material"] = ctx.get("peer_comparison_material")
        if fundflow_material_pack.get("rows"):
            all_data["fundflow_material_pack"] = fundflow_material_pack
        result = synthesizer.synthesize(stock_name, all_data)
        result = self._fill_citation_metadata(result, items)
        result = self._enrich_core_fact_provenance(result)
        if ctx:
            fact_pack = ctx.get("formal_financial_fact_pack") or all_data.get("formal_financial_fact_pack") or {}
            result = self._sanitize_financial_missing_contradictions(result, fact_pack)
            result = self._sanitize_financial_direction_contradictions(result, fact_pack)
        result = self._sanitize_indirect_industry_citations_from_43(result, stock_name)

        if not any(result.get(k) for k in SYNTHESIS_KEYS):
            return self._template_synthesize(
                stock_raw,
                items_count=len(items),
                sources=self._source_list(items),
                source_policy=source_policy,
            )

        result["_items_count"] = len(items)
        result["_sources"] = self._source_list(items)
        result["_industry_relevance_manifest"] = build_industry_relevance_manifest(items)
        return result

    @staticmethod
    def _build_formal_financial_fact_pack(filing_core_facts: list) -> dict:
        """Build a compact formal financial pack for 4.2 prompts only."""
        facts = []
        for fact in filing_core_facts or []:
            if not isinstance(fact, dict):
                continue
            metric = str(fact.get("fact") or "")
            value = str(fact.get("data") or "")
            if not metric or not value:
                continue
            if metric not in {"营业收入", "归母净利润", "经营现金流量净额"}:
                continue
            if not SynthesisSkill._is_reliable_financial_value(value):
                continue
            source_labels = fact.get("source_labels") or []
            source = "、".join(str(label) for label in source_labels if label)
            facts.append({
                "metric": metric,
                "value": value,
                "period": source,
                "source": fact.get("evidence_type") or "periodic_report_filing_fact",
            })
        return {
            "schema": "formal_financial_fact_pack.v1",
            "facts": facts,
        }

    @staticmethod
    def _sanitize_financial_missing_contradictions(result: dict, fact_pack: dict) -> dict:
        """Remove LLM claims that revenue/profit are missing when formal facts exist."""
        available_parts = SynthesisSkill._available_financial_parts(fact_pack, result)
        if not available_parts:
            return result

        text = str(result.get("fundamentals") or "")
        if not text:
            return result

        missing_pattern = re.compile(
            r"[^。；\n]*(?:未提供[^。；\n]*(?:营收|营业收入|利润|净利润)|"
            r"(?:营收|营业收入|利润|净利润)[^。；\n]*未提供)[^。；\n]*[。；]?"
        )
        if not missing_pattern.search(text):
            return result

        replacement = (
            "正式财务事实包显示，"
            + "，".join(available_parts)
            + "；订单、客户、费用率或指引等未在正式事实包中出现的指标仍需等待后续公告。"
        )
        result = dict(result)
        result["fundamentals"] = missing_pattern.sub(replacement, text, count=1).strip()
        return result

    @staticmethod
    def _sanitize_financial_direction_contradictions(result: dict, fact_pack: dict) -> dict:
        """Align annual net-profit wording with deterministic formal financial facts."""
        replacement = SynthesisSkill._annual_net_profit_decline_replacement(fact_pack)
        if not replacement:
            return result

        sanitized = dict(result)
        for key in ("industry_logic", "fundamentals", "valuation_debate"):
            text = str(sanitized.get(key) or "")
            if text:
                sanitized[key] = SynthesisSkill._replace_false_annual_profit_growth(text, replacement)

        core_facts = []
        changed = False
        for fact in sanitized.get("core_facts") or []:
            if not isinstance(fact, dict):
                core_facts.append(fact)
                continue
            fact_blob = f"{fact.get('fact', '')} {fact.get('data', '')}"
            if SynthesisSkill._has_false_annual_profit_growth(fact_blob):
                changed = True
                continue
            core_facts.append(fact)
        if changed:
            sanitized["core_facts"] = core_facts
        return sanitized

    @staticmethod
    def _annual_net_profit_decline_replacement(fact_pack: dict) -> str:
        for fact in ((fact_pack or {}).get("facts") or []):
            if not isinstance(fact, dict):
                continue
            metric = str(fact.get("metric") or "")
            value = str(fact.get("value") or "").strip()
            if "净利润" not in metric or not value:
                continue
            if SynthesisSkill._is_net_profit_decline_value(value):
                return f"正式财务口径显示归母净利润{value}"
        return ""

    @staticmethod
    def _is_net_profit_decline_value(value: Any) -> bool:
        text = str(value or "").replace("－", "-").replace("—", "-")
        return bool(re.search(r"(?:同比)?(?:下降|下滑|减少)|-\d+(?:\.\d+)?%", text))

    @staticmethod
    def _replace_false_annual_profit_growth(text: str, replacement: str) -> str:
        cleaned = str(text or "")
        table_title_replacement = "估值溢价需等待盈利修复验证"
        for pattern in (
            r"(?:2025年)?年报显示利润随营收增长[，,、]?\s*营收扩张是利润增长主因",
            r"(?:2025年)?年报显示利润随营收增长",
            r"营收扩张是利润增长主因",
        ):
            cleaned = re.sub(pattern, replacement, cleaned)
        for pattern in (
            r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)[^。；\n|]{0,16}同比增速显著",
            r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)同比大幅增长",
            r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)同比增长",
            r"2025年[^。；\n|]{0,16}利润高增",
        ):
            cleaned = re.sub(pattern, replacement, cleaned)
        for pattern in (
            r"高成长性应享有高估值溢价",
            r"高成长性支撑估值溢价",
        ):
            cleaned = re.sub(pattern, table_title_replacement, cleaned)
        return cleaned

    @staticmethod
    def _has_false_annual_profit_growth(text: str) -> bool:
        return bool(
            re.search(
                r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)[^。；\n|]{0,16}同比增速显著|"
                r"(?:公司)?2025年(?:归母净利润|归母净利|净利润|净利|利润)同比(?:大幅)?增长|"
                r"2025年[^。；\n|]{0,16}利润高增|"
                r"(?:2025年)?年报显示利润随营收增长|"
                r"营收扩张是利润增长主因",
                str(text or ""),
            )
        )

    @staticmethod
    def _available_financial_parts(fact_pack: dict, result: dict) -> list:
        """Return reliable revenue/profit snippets for missing-data sanitization."""
        facts = {
            str(fact.get("metric") or ""): str(fact.get("value") or "")
            for fact in ((fact_pack or {}).get("facts") or [])
            if isinstance(fact, dict) and SynthesisSkill._is_reliable_financial_value(fact.get("value"))
        }
        available_parts = []
        if facts.get("营业收入"):
            available_parts.append(f"营业收入{facts['营业收入']}")
        if facts.get("归母净利润"):
            available_parts.append(f"归母净利润{facts['归母净利润']}")
        if available_parts:
            return available_parts

        fallback_parts = []
        seen_metrics = set()
        for fact in (result.get("core_facts") or []):
            if not isinstance(fact, dict):
                continue
            status = str(fact.get("provenance_status") or "supported")
            confidence = str(fact.get("confidence") or "")
            if status in {"invalid_ref", "unsupported"}:
                continue
            if status == "missing_ref" and confidence not in {"高", "high", "High"}:
                continue
            label = str(fact.get("fact") or "").strip()
            value = SynthesisSkill._brief_financial_value(fact.get("data"))
            if not label or not value or not SynthesisSkill._is_reliable_financial_value(value):
                continue
            if ("营收" in label or "营业收入" in label) and "revenue" not in seen_metrics:
                fallback_parts.append(f"{label}{value}")
                seen_metrics.add("revenue")
            elif "归母净利润" in label and "profit" not in seen_metrics:
                fallback_parts.append(f"{label}{value}")
                seen_metrics.add("profit")
        return fallback_parts

    @staticmethod
    def _brief_financial_value(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return re.split(r"[，,；;。]", text, maxsplit=1)[0].strip()

    @staticmethod
    def _is_reliable_financial_value(value: Any) -> bool:
        text = str(value or "").strip().replace(",", "")
        if not text:
            return False
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return False
        try:
            return abs(float(match.group(0))) > 1e-9
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _sanitize_indirect_industry_citations_from_43(result: dict, stock_name: str) -> dict:
        """Remove indirect industry/news citations from 4.3 synthesis text."""
        bad_refs = SynthesisSkill._indirect_industry_ref_ids(result.get("citations") or {}, stock_name)
        if not bad_refs:
            return result

        changed = False
        sanitized = dict(result)
        for key in ("funding_sentiment", "events_catalysts"):
            text = str(result.get(key) or "")
            if not text:
                continue
            cleaned = SynthesisSkill._drop_lines_with_refs(text, bad_refs)
            if cleaned != text:
                sanitized[key] = cleaned
                changed = True
        return sanitized if changed else result

    @staticmethod
    def _indirect_industry_ref_ids(citations: dict, stock_name: str) -> set:
        stock_text = str(stock_name or "").strip()
        bad_refs = set()
        for raw_ref, meta in (citations or {}).items():
            if not isinstance(meta, dict):
                continue
            source = str(meta.get("source") or "").strip()
            source_type = str(meta.get("source_type") or "").strip()
            title = str(meta.get("title") or "").strip()
            direct_company = bool(stock_text and stock_text in title)
            is_industry_or_news = (
                source in {"行业资讯", "新闻", "行业研报"}
                or source_type in {"mainstream_media", "industry_research"}
            )
            if is_industry_or_news and not direct_company:
                try:
                    bad_refs.add(int(raw_ref))
                except (TypeError, ValueError):
                    continue
        return bad_refs

    @staticmethod
    def _drop_lines_with_refs(text: str, bad_refs: set) -> str:
        bad_markers = {f"[^{ref}]" for ref in bad_refs}
        kept = []
        for line in str(text or "").splitlines():
            if any(marker in line for marker in bad_markers):
                continue
            kept.append(line)
        return "\n".join(kept).strip()

    def _build_claim_verification_context(
        self, stock_name: str, ctx: SkillContext
    ):
        """Build sanitized claim verification context. Returns (status, context, error)."""
        try:
            from claim_verification import (
                build_claim_verification_plan,
                summarize_claim_verification_plan,
            )
        except Exception as exc:
            return "error", None, f"failed to import claim verification: {exc}"

        base_dir = ctx.get("claim_verification_base_dir")
        if not base_dir:
            base_dir = Path(__file__).resolve().parents[3] / "knowledge"
        max_verified = ctx.get("claim_verification_max_verified", 6)
        max_supported = ctx.get("claim_verification_max_supported", 4)
        max_unverified = ctx.get("claim_verification_max_unverified", 4)

        try:
            plan = build_claim_verification_plan(stock_name, str(base_dir), dry_run=True)
            summary = summarize_claim_verification_plan(
                plan,
                max_verified=int(max_verified),
                max_supported=int(max_supported),
                max_unverified=int(max_unverified),
            )
        except Exception as exc:
            return "error", None, f"claim verification build failed: {exc}"

        counts = summary.get("counts", {})
        total_usable = (
            counts.get("verified", 0)
            + counts.get("supported", 0)
            + counts.get("unverified", 0)
            + counts.get("needs_review", 0)
        )
        if total_usable == 0 and counts.get("high_credit_claims", 0) == 0:
            return "empty", None, ""

        return "ok", summary, ""

    def _legacy_llm_synthesize(self, stock_name: str, stock_raw: dict, keep_posts: list, cv_context: Dict = None) -> dict:
        """兼容旧测试/调用方：使用 chat(prompt) 的简化 LLM 客户端。"""
        prompt = self._build_prompt(stock_name, stock_raw, keep_posts, cv_context)
        try:
            response = self.llm_client.chat(prompt)
            if isinstance(response, dict):
                response.setdefault("core_facts", [])
                response.setdefault("citations", {})
                response["_legacy_prompt"] = prompt
                return response
            return self._template_synthesize(stock_raw)
        except Exception:
            return self._template_synthesize(stock_raw)

    @staticmethod
    def _eligible_external_baseline_items(ctx: SkillContext = None) -> list:
        """Return canonical external evidence items allowed into baseline synthesis."""
        if ctx is None:
            return []
        eligible = []
        for item in ctx.get("external_evidence_keep_items", []) or []:
            extra = getattr(item, "extra", {}) or {}
            if extra.get("synthesis_display_only") is True:
                continue
            if not is_canonical_synthesis_source(item):
                continue
            if not (extra.get("knowledge_eligible") or extra.get("report_eligible")):
                continue
            eligible.append(item)
        return eligible

    def _build_synthesis_items(self, stock_raw: dict, keep_posts: list, ctx: SkillContext = None, extra_items: list = None):
        zhihu = stock_raw.get("zhihu", {})
        source_policy = self._canonical_synthesis_source_policy(ctx)
        fundflow_material_pack = ctx.get("fundflow_material_pack") if ctx else None
        fundflow = (
            stock_raw.get("fundflow", [])
            if (fundflow_material_pack and fundflow_material_pack.get("rows"))
            else []
        )
        items = adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu.get("report_items", []),
            reports=stock_raw.get("reports", []),
            announcements=stock_raw.get("announcements", []),
            fundflow=fundflow,
            news=stock_raw.get("news", []),
        )
        if source_policy == "formal_first":
            items = [item for item in items if is_canonical_synthesis_source(item)]
        baseline_external_items = self._eligible_external_baseline_items(ctx)
        if baseline_external_items:
            items = list(items) + baseline_external_items
        # Extra material-layer items (e.g. periodic-report full text) are
        # appended LAST so ordinary source numbering stays stable.
        if extra_items:
            extras = list(extra_items)
            if source_policy == "formal_first":
                extras = [item for item in extras if is_formal_display_source(item)]
            items = list(items) + extras
        return items

    def _canonical_synthesis_source_policy(self, ctx: SkillContext = None) -> str:
        raw_policy = None
        if ctx is not None:
            raw_policy = ctx.get("canonical_synthesis_source_policy")
        if not raw_policy:
            raw_policy = getattr(self, "canonical_synthesis_source_policy", "legacy_mixed")
        policy = str(raw_policy or "legacy_mixed").strip()
        if policy == "formal_first":
            return "formal_first"
        return "legacy_mixed"

    def _fill_citation_metadata(self, synthesis: dict, items: list) -> dict:
        citations = synthesis.get("citations", {}) or {}
        filled = {}
        for raw_ref_id, meta in citations.items():
            try:
                ref_id = int(raw_ref_id)
            except (TypeError, ValueError):
                ref_id = raw_ref_id

            item = items[ref_id - 1] if isinstance(ref_id, int) and 1 <= ref_id <= len(items) else None
            if item is None:
                filled[ref_id] = meta
                continue

            extra = item.extra or {}
            filled[ref_id] = {
                "source": item.source_platform,
                "author": item.author,
                "title": item.title,
                "url": item.url,
                "date": item.publish_time,
                "interaction_score": item.interaction_score,
                "source_credit": extra.get("source_credit"),
                "source_type": extra.get("source_type"),
                "verification_status": extra.get("verification_status"),
            }
            # Forward curated external traceability fields when present.
            for trace_key in (
                "card_id",
                "source_ref",
                "source_excerpt_hash",
                "source_block_hash",
                "topic",
                "synthesis_display_only",
                "quality_action",
                "scoring_eligible",
                "risk_score_eligible",
            ):
                if trace_key in extra:
                    filled[ref_id][trace_key] = extra[trace_key]
        synthesis["citations"] = filled
        return synthesis

    def _enrich_core_fact_provenance(self, synthesis: dict) -> dict:
        """Deterministically enrich core_facts with source labels, evidence type, and provenance status.

        Uses existing citation metadata; does not call LLM or add new data sources.
        Only high-credit official/announcement/exchange sources can support core facts;
        news/research/community/AgentReach/fundflow sources are rejected by the hard filter.
        """
        core_facts = synthesis.get("core_facts", []) or []
        if not core_facts:
            return synthesis

        citations = synthesis.get("citations", {}) or {}
        # Build an int-keyed lookup from possibly string-keyed citations
        citation_lookup = {}
        for raw_key, meta in citations.items():
            try:
                int_key = int(raw_key)
            except (TypeError, ValueError):
                int_key = raw_key
            citation_lookup[int_key] = meta

        for fact in core_facts:
            raw_refs = fact.get("source_refs", []) or []
            refs = []
            for r in raw_refs:
                if isinstance(r, bool):
                    continue
                if isinstance(r, int):
                    r_int = r
                elif isinstance(r, str) and r.strip().isdigit():
                    r_int = int(r.strip())
                else:
                    continue
                if r_int > 0:
                    refs.append(r_int)

            accepted_labels = []
            invalid_or_excluded = False
            seen_labels = set()

            for ref in refs:
                meta = citation_lookup.get(ref)
                if not meta or not isinstance(meta, dict):
                    invalid_or_excluded = True
                    continue

                source = str(meta.get("source", "")).strip()
                if not source:
                    invalid_or_excluded = True
                    continue

                # Deterministic hard filter: only allowed sources support core facts.
                if not is_core_fact_supporting_source(source, meta):
                    invalid_or_excluded = True
                    continue

                family = self._normalize_source_family(source)
                if family not in seen_labels:
                    seen_labels.add(family)
                    if len(accepted_labels) < 2:
                        accepted_labels.append(family)

            fact["source_labels"] = accepted_labels
            fact["evidence_type"] = self._derive_evidence_type(accepted_labels)
            fact["provenance_status"] = self._derive_provenance_status(refs, accepted_labels, invalid_or_excluded)

        return synthesis

    @staticmethod
    def _normalize_source_family(source: str) -> str:
        """Map fine-grained source_platform values to stable source families."""
        s = source.strip()
        lower = s.lower()

        if "知乎" in s:
            return "知乎"
        if lower in ("xueqiu", "雪球"):
            return "雪球"
        if "研报" in s or lower == "research_report":
            return "研报"
        if "公告" in s or lower == "announcement":
            return "公告"
        if "资金流向" in s or lower == "fundflow":
            return "资金流向"
        if "新闻" in s or lower == "news":
            return "新闻"
        return s

    @staticmethod
    def _derive_evidence_type(labels: list) -> str:
        if not labels:
            return "unknown"

        families = set(labels)
        if len(families) > 1:
            return "mixed"

        label = labels[0]
        if label == "公告":
            return "announcement"
        if label == "研报":
            return "research_report"
        if label in ("雪球", "知乎"):
            return "community"
        if label == "新闻":
            return "news"
        if label == "资金流向":
            return "fundflow"
        return "unknown"

    @staticmethod
    def _derive_provenance_status(refs: list, accepted_labels: list, invalid_or_excluded: bool) -> str:
        if not refs:
            return "missing_ref"
        if accepted_labels:
            if invalid_or_excluded:
                return "partially_supported"
            return "supported"
        return "invalid_ref"

    @staticmethod
    def _source_list(items: list) -> List[str]:
        return sorted({item.source_platform for item in items if item.source_platform})

    @staticmethod
    def _empty_baseline_synthesis(stock_raw: dict, items: list, source_policy: str = "legacy_mixed", formal_first_insufficient: bool = False) -> dict:
        if formal_first_insufficient:
            return SynthesisSkill._template_synthesize(
                stock_raw,
                items_count=len(items),
                sources=SynthesisSkill._source_list(items),
                source_policy=source_policy,
            )
        return {
            "industry_logic": "",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [],
            "citations": {},
            "_items_count": len(items),
            "_sources": SynthesisSkill._source_list(items),
            "_source_policy": source_policy,
        }

    def _build_prompt(self, stock_name: str, stock_raw: dict, keep_posts: list, cv_context: Dict = None) -> str:
        """构建 LLM prompt（legacy chat 路径，复用现代路径的信用规则）。"""
        tech = stock_raw.get("technical", {})
        reports = stock_raw.get("reports", [])
        anns = stock_raw.get("announcements", [])
        zhihu = stock_raw.get("zhihu", {}).get("report_items", [])

        prompt = f"""请基于以下数据，为股票「{stock_name}」生成综合分析：

技术面指标：{tech.get("indicators", {})}
最新研报数量：{len(reports)}
最新公告数量：{len(anns)}
知乎相关文章数量：{len(zhihu)}
高质量社区帖子数量：{len(keep_posts)}

{credit_usage_rules_text()}

请按以下 JSON 格式返回：
{{
  "industry_logic": "行业逻辑分析（100字以内）",
  "fundamentals": "基本面分析（100字以内）",
  "valuation_debate": "估值多空辩论（100字以内）",
  "funding_sentiment": "资金情绪分析（100字以内）",
  "events_catalysts": "事件催化分析（100字以内）"
}}
"""
        if cv_context:
            appendix = self._format_claim_verification_appendix(cv_context)
            if appendix:
                prompt += "\n\n---\n\n" + appendix
        return prompt

    def _format_claim_verification_appendix(self, context: Dict) -> str:
        """Render guarded non-citable appendix for legacy prompt."""
        return format_claim_verification_appendix(context, is_legacy=True)

    @staticmethod
    def _template_synthesize(
        stock_raw: dict,
        items_count: int = 0,
        sources: List[str] = None,
        source_policy: str = "legacy_mixed",
    ) -> dict:
        """无 LLM 时的降级模板，只描述可验证状态，不生成伪基本面结论。"""
        tech = stock_raw.get("technical", {})
        indicators = tech.get("indicators", {})
        resonance = indicators.get("_resonance", {})
        score = resonance.get("composite_score", 5)
        sources = sources or []
        source_text = "、".join(sources) if sources else "无可用多源内容"
        formal_sources_insufficient = source_policy == "formal_first" and items_count == 0

        if score >= 7:
            trend = "整体偏多"
        elif score <= 3:
            trend = "整体偏空"
        else:
            trend = "震荡整理"

        if formal_sources_insufficient:
            return {
                "industry_logic": (
                    f"formal_first 模式下正式材料不足：当前可用于 4.1-4.3 的公告、研报、年报或"
                    f"主流新闻不足；仅保留技术面降级摘要，技术面综合评分 {score}，{trend}。"
                ),
                "fundamentals": (
                    "formal_first 已排除非正式材料；在正式来源补足前，"
                    "不生成完整基本面叙事。"
                ),
                "valuation_debate": "估值多空分歧需等待可引用的正式材料补足后再展开。",
                "funding_sentiment": "资金面与情绪仅保留原始数据，未生成推断性叙事。",
                "events_catalysts": "事件催化仅保留原始公告/新闻线索，未生成推断性叙事。",
                "core_facts": [],
                "citations": {},
                "_items_count": items_count,
                "_sources": sources,
                "_source_policy": source_policy,
                "_formal_first_sources_insufficient": True,
            }

        return {
            "industry_logic": f"当前仅完成技术面降级摘要：技术面综合评分 {score}，{trend}。",
            "fundamentals": f"基本面 LLM 合成未启用或未产生有效输出；已收集 {items_count} 条候选内容，来源：{source_text}。",
            "valuation_debate": "估值多空分歧需等待可引用的研报、公告、新闻或高质量社区内容完成合成后再展开。",
            "funding_sentiment": "资金面与情绪仅保留原始数据，未生成推断性叙事。",
            "events_catalysts": "事件催化仅保留原始公告/新闻线索，未生成推断性叙事。",
            "core_facts": [],
            "citations": {},
            "_items_count": items_count,
            "_sources": sources,
            "_source_policy": source_policy,
        }
