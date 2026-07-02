"""LLM synthesis skill."""

import json
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
    from ..industry_news_relevance import build_industry_relevance_manifest
    from ..peer_comparison_material import build_peer_comparison_material
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
    from industry_news_relevance import build_industry_relevance_manifest
    from peer_comparison_material import build_peer_comparison_material


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

CURATED_EXTERNAL_NARRATIVE_SOURCE_TYPES = {
    "curated_external_analysis_evidence",
    "xueqiu_column_observation",
    "xueqiu_comment_observation",
    "xueqiu_selected_observation",
    "zhihu_selected_observation",
    "wechat_selected_observation",
    "wechat_column_observation",
}

CURATED_EXTERNAL_NARRATIVE_VERIFICATION_STATUSES = {
    "professional_observation",
    "tentative_unverified",
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

        baseline = self._synthesize(stock_name, stock_raw, keep_posts, ctx)
        ctx.set("synthesis", baseline)
        core_facts = self._select_core_facts(
            baseline.get("core_facts", []),
            ctx.get("periodic_report_filing_core_facts", []),
        )
        ctx.set("core_facts", core_facts)
        ctx.set("synthesis_text", self._flatten_synthesis_text(baseline))
        ctx.set("synthesis_items_count", baseline.get("_items_count", 0))
        ctx.set("synthesis_sources", baseline.get("_sources", []))
        ctx.set("industry_relevance_manifest", baseline.get("_industry_relevance_manifest", {}))

        # Build peer comparison material from deterministic metrics.
        ctx.set("peer_comparison_material", build_peer_comparison_material(
            stock_name=stock_name,
            competitor_metrics=ctx.get("competitor_metrics"),
            stock_config=ctx.get("stock_config"),
        ))

        # Optional experimental paths: annual-report materials and broker-research
        # digest notes may enter the DISPLAY synthesis only.  Canonical synthesis,
        # core_facts, synthesis_text, and synthesis_sources stay baseline so risk
        # scoring and Knowledge persistence never see display-only material.
        display_items = []
        fulltext_items = []
        narrative_card_items = []
        broker_digest_items = []
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
            display_text = self._flatten_synthesis_text(display)
            ctx.set("synthesis_display", display)
            ctx.set("synthesis_display_sources", display.get("_sources", []))
            ctx.set("synthesis_text_with_periodic_display_materials", display_text)
            if fulltext_items:
                ctx.set("synthesis_text_with_periodic_report_fulltext", display_text)
            if narrative_card_items:
                ctx.set("synthesis_text_with_periodic_narrative_cards", display_text)
            if broker_digest_items:
                ctx.set("synthesis_text_with_broker_research_digest", display_text)

        # Curated external materials: separate deep-analysis-only display paths.
        # These branches intentionally do not reuse ctx["synthesis_display"].
        self._build_viewpoint_narrative_deep_analysis_display(ctx)
        if not ctx.get("deep_analysis_display"):
            self._build_viewpoint_digest_deep_analysis_display(ctx)

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

        try:
            narrative = json.loads(Path(narrative_json).read_text(encoding="utf-8"))
        except Exception as exc:
            ctx.set("curated_external_viewpoint_narrative_status", "reader_error")
            ctx.set("curated_external_viewpoint_narrative_stats", {"rejection_reasons": [str(exc)]})
            return

        status = str(narrative.get("status") or "")
        ctx.set("curated_external_viewpoint_narrative_status", status)
        ctx.set("curated_external_viewpoint_narrative_stats", narrative.get("stats") or {})
        if status != "ok":
            return

        paragraphs = [p for p in narrative.get("paragraphs") or [] if isinstance(p, dict)]
        citations = self._normalize_viewpoint_narrative_citations(narrative.get("citations") or {})
        paragraphs = self._hydrate_viewpoint_narrative_citation_refs(paragraphs, citations)
        if not paragraphs or not citations:
            ctx.set("curated_external_viewpoint_narrative_status", "empty")
            return

        display = {
            "industry_logic": self._flatten_viewpoint_narrative_paragraphs(paragraphs),
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "core_facts": [],
            "citations": citations,
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": paragraphs,
            "_curated_external_taxonomy_version": "external_viewpoint.v1",
            "_items_count": len(paragraphs),
            "_sources": list(citations.values()),
        }
        lint = lint_curated_external_display_text(display)
        ctx.set("curated_external_viewpoint_narrative_lint", lint)
        if not lint.get("ok"):
            ctx.set("curated_external_viewpoint_narrative_status", "lint_failed")
            return

        ctx.set("deep_analysis_display", display)
        ctx.set("deep_analysis_display_sources", display.get("_sources", []))
        ctx.set("synthesis_text_with_curated_external_viewpoint_narrative", self._flatten_synthesis_text(display))
        ctx.set("curated_external_viewpoint_narrative_status", "ok")

    @staticmethod
    def _normalize_viewpoint_narrative_citations(citations: Dict[Any, Any]) -> Dict[int, dict]:
        normalized = {}
        for key, value in (citations or {}).items():
            try:
                ref_id = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(value, dict):
                continue
            if (
                value.get("source_type") in CURATED_EXTERNAL_NARRATIVE_SOURCE_TYPES
                and value.get("verification_status") in CURATED_EXTERNAL_NARRATIVE_VERIFICATION_STATUSES
            ):
                normalized[ref_id] = value
        return normalized

    @classmethod
    def _hydrate_viewpoint_narrative_citation_refs(cls, paragraphs: list, citations: Dict[int, dict]) -> list:
        """Fill missing paragraph citation refs from claim_refs and citation claim_id metadata."""
        claim_to_ref: Dict[str, int] = {}
        suffix_to_ref: Dict[str, int] = {}
        for ref_id, meta in citations.items():
            claim_id = str(meta.get("claim_id") or "").strip()
            if not claim_id:
                continue
            claim_to_ref[claim_id] = ref_id
            suffix_to_ref[claim_id.rsplit(":", 1)[-1]] = ref_id

        hydrated = []
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
            existing_refs = paragraph.get("citation_refs") or []
            if existing_refs:
                hydrated.append(paragraph)
                continue
            refs = []
            seen = set()
            for claim_ref in paragraph.get("claim_refs") or []:
                claim_key = str(claim_ref or "").strip()
                ref_id = claim_to_ref.get(claim_key)
                if ref_id is None:
                    ref_id = suffix_to_ref.get(claim_key.rsplit(":", 1)[-1])
                if ref_id is None or ref_id in seen:
                    continue
                seen.add(ref_id)
                refs.append(ref_id)
            hydrated.append({**paragraph, "citation_refs": refs} if refs else paragraph)
        return hydrated

    @classmethod
    def _flatten_viewpoint_narrative_paragraphs(cls, paragraphs: list) -> str:
        parts = []
        for paragraph in paragraphs:
            heading = str(paragraph.get("heading") or "").strip()
            text = str(paragraph.get("text") or "").strip()
            refs = paragraph.get("citation_refs") or []
            rendered = cls._attach_refs_to_sentence(text, refs)
            if heading:
                parts.append(f"{heading}：{rendered}")
            elif rendered:
                parts.append(rendered)
        return "\n\n".join(parts)

    @staticmethod
    def _attach_refs_to_sentence(text: str, refs: list) -> str:
        ref_text = "".join(f"[^{int(ref)}]" for ref in refs if str(ref).isdigit())
        stripped = str(text or "").strip()
        if not ref_text:
            return stripped
        if stripped.endswith(("。", "；", ";", "！", "？")):
            return f"{stripped[:-1]}{ref_text}{stripped[-1]}"
        return f"{stripped}{ref_text}"

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
        ctx.set("synthesis_text_with_curated_external_viewpoint_digest", self._flatten_synthesis_text(display))
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
        if cv_context:
            all_data["claim_verification_context"] = cv_context
        result = synthesizer.synthesize(stock_name, all_data)
        result = self._fill_citation_metadata(result, items)
        result = self._enrich_core_fact_provenance(result)

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
        items = adapt_all(
            xueqiu_items=keep_posts,
            zhihu_items=zhihu.get("report_items", []),
            reports=stock_raw.get("reports", []),
            announcements=stock_raw.get("announcements", []),
            fundflow=stock_raw.get("fundflow", []),
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

    def _source_list(self, items: list) -> List[str]:
        return sorted({item.source_platform for item in items if item.source_platform})

    def _flatten_synthesis_text(self, synthesis: dict) -> str:
        return "\n".join(str(synthesis.get(k, "")) for k in SYNTHESIS_KEYS if synthesis.get(k))

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

    def _template_synthesize(
        self,
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
                    "formal_first 已排除雪球/知乎/微信等社媒材料；在正式来源补足前，"
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
